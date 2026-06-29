# start src/services/video_service.py
"""Pipeline orchestration service for SupoClip video processing.

Coordinates the full processing pipeline:
    download (if URL) -> transcribe -> analyze -> generate clips

Progress is reported via a plain callable so this module stays
UI-agnostic (works with NiceGUI, SSE, WebSocket, or tests).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete

from src.config import get_config

if TYPE_CHECKING:
    from src.pipeline.clip import ClipOptions
    from src.pipeline.subtitles import SubtitleStyle

from src.database import get_session
from src.models import GeneratedClip, Task
from src.pipeline.analyze import AnalysisError, TranscriptSegment, analyze_transcript
from src.pipeline.download import (
    DownloadError,
    download_youtube_video,
    validate_youtube_url,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

type ProgressCallback = Callable[[int, str], None]
"""Called with (progress_pct: int, message: str) to report pipeline progress."""


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ProcessingRequest:
    """A request to process a video into clips.

    Attributes:
        source: YouTube URL or absolute local file path.
        task_id: Database Task UUID that tracks this processing run.
        min_clip_length: Minimum clip duration in seconds.
        max_clip_length: Maximum clip duration in seconds.
        output_resolution: Target resolution string, e.g. ``"1080p"``.
        subtitle_style: Optional subtitle styling configuration.
        logo_path: Optional path to a logo image for branding overlays.
        custom_prompt: Optional additional instructions for the AI analysis.
    """

    source: str
    task_id: str
    min_clip_length: int = 15
    max_clip_length: int = 45
    output_resolution: str = "1080p"
    subtitle_style: SubtitleStyle | None = None
    logo_path: Path | None = None
    custom_prompt: str | None = None


@dataclass(slots=True)
class ProcessingResult:
    """Result of processing a video through the full pipeline.

    Attributes:
        task_id: Database Task UUID that was processed.
        clips: Paths to successfully generated clip files.
        clip_metadata: Per-clip metadata dicts (start_time, end_time, text, score, title).
        error: Human-readable error message if processing failed.
    """

    task_id: str
    clips: list[Path] = field(default_factory=list)
    clip_metadata: list[dict] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _update_task_status(
    task_id: str,
    status: str,
    progress: int,
    message: str | None = None,
    error: str | None = None,
) -> None:
    """Update the task status in the database.

    Args:
        task_id: Task UUID to update.
        status: New status string — ``'processing'``, ``'completed'``, or ``'failed'``.
        progress: Progress percentage in the range 0–100.
        message: Optional human-readable status message shown in the UI.
        error: Optional error description for failed tasks. When provided it is
            persisted to ``task.error_message`` and also mirrored into
            ``task.progress_message`` so the live status reflects the failure.
    """
    async with get_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            logger.warning("task_not_found", task_id=task_id)
            return

        task.status = status
        task.progress = progress
        if message is not None:
            task.progress_message = message
        if error is not None:
            task.error_message = error
            task.progress_message = error

        await session.flush()
        logger.info(
            "task_status_updated",
            task_id=task_id,
            status=status,
            progress=progress,
        )


async def _delete_existing_clips(task_id: str) -> None:
    """Delete any existing GeneratedClip rows for a task.

    Makes clip persistence idempotent: re-processing the same task replaces
    its clips instead of appending duplicate rows.

    Args:
        task_id: Parent task UUID whose clip rows should be removed.
    """
    async with get_session() as session:
        await session.execute(delete(GeneratedClip).where(GeneratedClip.task_id == task_id))
        await session.flush()
        logger.info("existing_clips_deleted", task_id=task_id)


async def _save_generated_clip(
    task_id: str,
    clip_path: Path,
    segment: TranscriptSegment,
    clip_order: int,
) -> None:
    """Persist a generated clip record to the database.

    Args:
        task_id: Parent task UUID.
        clip_path: Absolute path to the generated clip file.
        segment: The TranscriptSegment this clip was generated from.
        clip_order: Zero-based position within the task's clip list.
    """
    duration = segment.end_time - segment.start_time

    async with get_session() as session:
        clip = GeneratedClip(
            task_id=task_id,
            filename=clip_path.name,
            start_time=segment.start_time,
            end_time=segment.end_time,
            duration=duration,
            title=segment.title,
            transcript_text=segment.text,
            score=segment.score,
        )
        session.add(clip)
        await session.flush()
        logger.info("clip_saved", filename=clip_path.name, task_id=task_id)


# ---------------------------------------------------------------------------
# Concurrent clip generation
# ---------------------------------------------------------------------------


async def _generate_clips_concurrently(
    source_video: Path,
    segments: list[TranscriptSegment],
    words: list[dict],
    task_id: str,
    clip_options: ClipOptions | None,
    clips_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> list[tuple[Path, TranscriptSegment]]:
    """Generate all clips concurrently using asyncio.TaskGroup.

    Concurrency is bounded by an :class:`asyncio.Semaphore` sized from the
    ``max_workers`` config value so that no more than N ffmpeg subprocesses
    run at once. Each clip is generated independently; failures are logged
    and skipped so a single bad segment does not abort the entire batch.

    Args:
        source_video: Path to the source video file.
        segments: Selected segments from AI analysis.
        words: Word-level transcript data for subtitle alignment.
        task_id: Task ID used to name output files.
        clip_options: Clip generation options (ClipOptions from pipeline/clip).
        clips_dir: Directory where clip files will be saved.
        progress_callback: Optional progress callable called after each clip.

    Returns:
        List of ``(clip_path, segment)`` tuples for clips that were
        generated successfully.
    """
    # Import lazily so this module is importable even before pipeline/clip exists.
    try:
        from src.pipeline.clip import ClipGenerationError, generate_clip
        from src.pipeline.clip import TranscriptSegment as ClipSegment
    except ImportError:
        logger.error("pipeline_clip_not_found")
        return []

    results: list[tuple[Path, TranscriptSegment]] = []
    lock = asyncio.Lock()
    total = len(segments)
    max_workers = getattr(get_config(), "max_workers", 2)
    semaphore = asyncio.Semaphore(max_workers)

    async def _generate_one(
        index: int,
        segment: TranscriptSegment,
    ) -> None:
        clip_filename = f"{task_id}_clip_{index + 1:02d}.mp4"
        clip_path = clips_dir / clip_filename
        clip_segment = ClipSegment(
            start_s=segment.start_time,
            end_s=segment.end_time,
            text=segment.text,
            relevance_score=segment.score,
        )
        try:
            async with semaphore:
                await generate_clip(
                    source_video=source_video,
                    segment=clip_segment,
                    words=words,
                    output_path=clip_path,
                    options=clip_options,
                )
            async with lock:
                results.append((clip_path, segment))
                done = len(results)

            if progress_callback is not None:
                pct = 50 + int((done / total) * 50)
                progress_callback(pct, f"Generated clip {done}/{total}")

            logger.info(
                "clip_generated",
                filename=clip_filename,
                start=segment.start_time,
                end=segment.end_time,
            )
        except ClipGenerationError as exc:
            logger.warning("clip_generation_failed", filename=clip_filename, reason=str(exc))
        except Exception as exc:
            logger.warning(
                "clip_generation_unexpected_error",
                filename=clip_filename,
                error=str(exc),
            )

    async with asyncio.TaskGroup() as tg:
        for idx, seg in enumerate(segments):
            tg.create_task(_generate_one(idx, seg))

    # Sort by original segment order (start_time ascending).
    results.sort(key=lambda pair: pair[1].start_time)
    return results


# ---------------------------------------------------------------------------
# Pipeline stage helpers
# ---------------------------------------------------------------------------


async def _obtain_source(
    request: ProcessingRequest,
    temp_dir: Path,
    notify: ProgressCallback,
) -> Path:
    """Obtain the source video file for processing.

    Downloads a YouTube URL or validates a local file path.

    Args:
        request: Processing request describing the source.
        temp_dir: Directory where downloaded videos are stored.
        notify: Safe progress notifier called with ``(pct, message)``.

    Returns:
        Path to the source video file.

    Raises:
        DownloadError: If a YouTube download fails.
        FileNotFoundError: If a local source file does not exist.
    """
    if validate_youtube_url(request.source):
        notify(10, "Downloading video...")
        await _update_task_status(request.task_id, "processing", 10, "Downloading video...")
        try:
            return await download_youtube_video(request.source, output_dir=temp_dir)
        except DownloadError as exc:
            await _update_task_status(request.task_id, "failed", 10, error=str(exc))
            raise

    source_video = Path(request.source)
    if not source_video.exists():
        msg = f"Video file not found: {request.source}"
        await _update_task_status(request.task_id, "failed", 10, error=msg)
        raise FileNotFoundError(msg)
    return source_video


async def _run_transcription(
    request: ProcessingRequest,
    source_video: Path,
    notify: ProgressCallback,
) -> tuple[str, list[dict]]:
    """Transcribe the source video to word-level transcript data.

    Args:
        request: Processing request (used for status updates).
        source_video: Path to the source video file.
        notify: Safe progress notifier called with ``(pct, message)``.

    Returns:
        Tuple of ``(transcript_text, words)`` where ``words`` is the
        word-level transcript used for subtitle alignment.

    Raises:
        RuntimeError: If the transcription pipeline module is unavailable.
        Exception: Any transcription error is re-raised after status update.
    """
    notify(20, "Transcribing...")
    await _update_task_status(request.task_id, "processing", 20, "Transcribing...")

    try:
        from src.pipeline.transcribe import format_transcript_text, transcribe_video

        transcription = await asyncio.to_thread(transcribe_video, source_video)
        transcript_text = format_transcript_text(transcription)
        return transcript_text, transcription
    except ImportError:
        # pipeline/transcribe not yet written — surface a clear error.
        msg = "Transcription pipeline module not available"
        await _update_task_status(request.task_id, "failed", 20, error=msg)
        raise RuntimeError(msg) from None
    except Exception as exc:
        await _update_task_status(request.task_id, "failed", 20, error=str(exc))
        raise


async def _run_analysis(
    request: ProcessingRequest,
    transcript_text: str,
    words: list[dict],
    notify: ProgressCallback,
) -> list[TranscriptSegment]:
    """Run AI analysis to select viral segments.

    Args:
        request: Processing request with clip-length bounds and custom prompt.
        transcript_text: Formatted transcript text for the LLM.
        words: Word-level transcript data passed to analysis.
        notify: Safe progress notifier called with ``(pct, message)``.

    Returns:
        List of selected :class:`TranscriptSegment` objects.

    Raises:
        AnalysisError: If analysis fails (re-raised after status update).
    """
    notify(40, "Analyzing transcript...")
    await _update_task_status(request.task_id, "processing", 40, "Analyzing transcript...")

    try:
        return await analyze_transcript(
            transcript_text=transcript_text,
            words=words,
            min_length_s=float(request.min_clip_length),
            max_length_s=float(request.max_clip_length),
            custom_prompt=request.custom_prompt,
        )
    except AnalysisError as exc:
        await _update_task_status(request.task_id, "failed", 40, error=str(exc))
        raise


def _build_clip_options(request: ProcessingRequest) -> ClipOptions | None:
    """Build clip generation options if the clip pipeline is available.

    Args:
        request: Processing request carrying resolution and branding options.

    Returns:
        A ``ClipOptions`` instance, or ``None`` if the clip module is absent.
    """
    try:
        from src.pipeline.clip import ClipOptions
    except ImportError:
        return None

    return ClipOptions(
        output_resolution=request.output_resolution,
        subtitle_style=request.subtitle_style,
        logo_path=request.logo_path,
    )


async def _run_clip_generation(
    request: ProcessingRequest,
    source_video: Path,
    segments: list[TranscriptSegment],
    words: list[dict],
    clips_dir: Path,
    notify: ProgressCallback,
    progress_callback: ProgressCallback | None,
) -> tuple[list[Path], list[dict]]:
    """Generate clips, persist them idempotently, and build result metadata.

    Args:
        request: Processing request (used for status updates and task ID).
        source_video: Path to the source video file.
        segments: Selected segments from AI analysis.
        words: Word-level transcript data for subtitle alignment.
        clips_dir: Directory where clip files are written.
        notify: Safe progress notifier called with ``(pct, message)``.
        progress_callback: Raw progress callback forwarded to clip generation.

    Returns:
        Tuple of ``(clip_paths, clip_metadata)``.

    Raises:
        RuntimeError: If segments exist but every clip generation failed.
    """
    notify(50, "Generating clips...")
    await _update_task_status(request.task_id, "processing", 50, "Generating clips...")

    clip_options = _build_clip_options(request)

    generated = await _generate_clips_concurrently(
        source_video=source_video,
        segments=segments,
        words=words,
        task_id=request.task_id,
        clip_options=clip_options,
        clips_dir=clips_dir,
        progress_callback=progress_callback,
    )

    if not generated and segments:
        msg = "All clip generations failed"
        await _update_task_status(request.task_id, "failed", 50, error=msg)
        raise RuntimeError(msg)

    # Replace any prior clips so re-processing the task is idempotent.
    await _delete_existing_clips(request.task_id)
    for order, (clip_path, segment) in enumerate(generated):
        await _save_generated_clip(
            task_id=request.task_id,
            clip_path=clip_path,
            segment=segment,
            clip_order=order,
        )

    clip_paths = [p for p, _ in generated]
    clip_metadata = [
        {
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "text": seg.text,
            "score": seg.score,
            "title": seg.title,
        }
        for _, seg in generated
    ]
    return clip_paths, clip_metadata


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------


async def process_video(
    request: ProcessingRequest,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingResult:
    """Process a video through the full pipeline.

    Orchestrates: download (if URL) → transcribe → analyze → generate clips.
    Updates the database Task record at each stage so the UI can poll
    for progress without needing a direct connection to this coroutine.

    Progress callback is called with ``(pct, message)`` at each stage:

    - ``0%``  ``"Preparing..."``
    - ``10%`` ``"Downloading video..."`` (YouTube only)
    - ``20%`` ``"Transcribing..."``
    - ``40%`` ``"Analyzing transcript..."``
    - ``50%`` ``"Generating clips..."`` (updated per clip)
    - ``100%`` ``"Complete"``

    Args:
        request: Processing configuration including source, task ID, and options.
        progress_callback: Optional callable ``(progress_pct, message)`` for
            real-time progress reporting to the UI.

    Returns:
        :class:`ProcessingResult` with paths to generated clips and metadata.
        On failure, ``result.error`` contains the human-readable error message.
    """

    def _notify(pct: int, msg: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(pct, msg)
            except Exception as cb_exc:
                logger.warning("progress_callback_error", error=str(cb_exc))

    cfg = get_config()
    temp_dir = Path(cfg.temp_dir)
    clips_dir = temp_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # --- 0% Preparing ---
    _notify(0, "Preparing...")
    await _update_task_status(request.task_id, "processing", 0, "Preparing...")

    try:
        source_video = await _obtain_source(request, temp_dir, _notify)
        transcript_text, words = await _run_transcription(request, source_video, _notify)
        segments = await _run_analysis(request, transcript_text, words, _notify)
        clip_paths, clip_metadata = await _run_clip_generation(
            request,
            source_video,
            segments,
            words,
            clips_dir,
            _notify,
            progress_callback,
        )

        # --- Complete ---
        _notify(100, "Complete")
        await _update_task_status(request.task_id, "completed", 100, "Complete")

        logger.info("pipeline_complete", task_id=request.task_id, clips=len(clip_paths))
        return ProcessingResult(
            task_id=request.task_id,
            clips=clip_paths,
            clip_metadata=clip_metadata,
        )

    except Exception as exc:
        logger.error(
            "pipeline_error",
            task_id=request.task_id,
            error=str(exc),
            exc_info=True,
        )
        return ProcessingResult(
            task_id=request.task_id,
            error=str(exc),
        )


# end src/services/video_service.py
