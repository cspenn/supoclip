# start src/services/video_service.py
"""Pipeline orchestration service for SupoClip video processing.

Coordinates the full processing pipeline:
    download (if URL) -> transcribe -> analyze -> generate clips

Progress is reported via a plain callable so this module stays
UI-agnostic (works with NiceGUI, SSE, WebSocket, or tests).
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.config import Config
from src.database import get_session
from src.models import GeneratedClip, Task
from src.pipeline.analyze import AnalysisError, TranscriptSegment, analyze_transcript
from src.pipeline.download import (
    DownloadError,
    download_youtube_video,
    validate_youtube_url,
)

logger = logging.getLogger(__name__)

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
    subtitle_style: object | None = None  # SubtitleStyle once pipeline/subtitles exists
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
        error: Optional error description for failed tasks.
    """
    async with get_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            logger.warning("task_not_found: task_id=%s", task_id)
            return

        task.status = status
        task.progress = progress
        if message is not None:
            task.progress_message = message
        if error is not None:
            task.progress_message = error

        await session.flush()
        logger.info(
            "task_status_updated: task_id=%s status=%s progress=%d",
            task_id,
            status,
            progress,
        )


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
        logger.info("clip_saved: %s task_id=%s", clip_path.name, task_id)


# ---------------------------------------------------------------------------
# Concurrent clip generation
# ---------------------------------------------------------------------------


async def _generate_clips_concurrently(
    source_video: Path,
    segments: list[TranscriptSegment],
    words: list[dict],
    task_id: str,
    clip_options: object,
    clips_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> list[tuple[Path, TranscriptSegment]]:
    """Generate all clips concurrently using asyncio.TaskGroup.

    Each clip is generated independently; failures are logged and skipped
    so a single bad segment does not abort the entire batch.

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
    except ImportError:
        logger.error("pipeline_clip_not_found: src.pipeline.clip is not available")
        return []

    results: list[tuple[Path, TranscriptSegment]] = []
    lock = asyncio.Lock()
    total = len(segments)

    async def _generate_one(
        index: int,
        segment: TranscriptSegment,
    ) -> None:
        clip_filename = f"{task_id}_clip_{index + 1:02d}.mp4"
        clip_path = clips_dir / clip_filename
        try:
            await generate_clip(
                source_video=source_video,
                segment=segment,
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
                "clip_generated: %s start=%.3f end=%.3f",
                clip_filename,
                segment.start_time,
                segment.end_time,
            )
        except ClipGenerationError as exc:
            logger.warning("clip_generation_failed: %s reason=%s", clip_filename, exc)
        except Exception as exc:
            logger.warning(
                "clip_generation_unexpected_error: %s error=%s", clip_filename, exc
            )

    async with asyncio.TaskGroup() as tg:
        for idx, seg in enumerate(segments):
            tg.create_task(_generate_one(idx, seg))

    # Sort by original segment order (start_time ascending).
    results.sort(key=lambda pair: pair[1].start_time)
    return results


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
                logger.warning("progress_callback_error: %s", cb_exc)

    cfg = Config()
    clips_dir = Path(cfg.temp_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # --- 0% Preparing ---
    _notify(0, "Preparing...")
    await _update_task_status(request.task_id, "processing", 0, "Preparing...")

    source_video: Path | None = None

    try:
        # --- Step 1: Obtain video file ---
        is_youtube = validate_youtube_url(request.source)

        if is_youtube:
            _notify(10, "Downloading video...")
            await _update_task_status(
                request.task_id, "processing", 10, "Downloading video..."
            )
            try:
                source_video = await download_youtube_video(
                    request.source,
                    output_dir=Path(cfg.temp_dir),
                )
            except DownloadError as exc:
                await _update_task_status(request.task_id, "failed", 10, error=str(exc))
                raise
        else:
            source_video = Path(request.source)
            if not source_video.exists():
                msg = f"Video file not found: {request.source}"
                await _update_task_status(request.task_id, "failed", 10, error=msg)
                raise FileNotFoundError(msg)

        # --- Step 2: Transcribe ---
        _notify(20, "Transcribing...")
        await _update_task_status(request.task_id, "processing", 20, "Transcribing...")

        try:
            from src.pipeline.transcribe import format_transcript_text, transcribe_video

            transcription = await transcribe_video(source_video)
            transcript_text = format_transcript_text(transcription)
            words: list[dict] = transcription
        except ImportError:
            # pipeline/transcribe not yet written — surface a clear error.
            msg = "Transcription pipeline module not available"
            await _update_task_status(request.task_id, "failed", 20, error=msg)
            raise RuntimeError(msg) from None
        except Exception as exc:
            await _update_task_status(request.task_id, "failed", 20, error=str(exc))
            raise

        # --- Step 3: AI analysis ---
        _notify(40, "Analyzing transcript...")
        await _update_task_status(
            request.task_id, "processing", 40, "Analyzing transcript..."
        )

        try:
            segments = await analyze_transcript(
                transcript_text=transcript_text,
                words=words,
                min_length_s=float(request.min_clip_length),
                max_length_s=float(request.max_clip_length),
                custom_prompt=request.custom_prompt,
            )
        except AnalysisError as exc:
            await _update_task_status(request.task_id, "failed", 40, error=str(exc))
            raise

        # --- Step 4: Generate clips ---
        _notify(50, "Generating clips...")
        await _update_task_status(
            request.task_id, "processing", 50, "Generating clips..."
        )

        try:
            from src.pipeline.clip import ClipOptions
        except ImportError:
            ClipOptions = None  # type: ignore[assignment,misc]

        clip_options = (
            ClipOptions(
                output_resolution=request.output_resolution,
                subtitle_style=request.subtitle_style,
                logo_path=request.logo_path,
            )
            if ClipOptions is not None
            else object()
        )

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

        # Persist each clip to the database.
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

        # --- Complete ---
        _notify(100, "Complete")
        await _update_task_status(request.task_id, "completed", 100, "Complete")

        logger.info(
            "pipeline_complete: task_id=%s clips=%d", request.task_id, len(clip_paths)
        )
        return ProcessingResult(
            task_id=request.task_id,
            clips=clip_paths,
            clip_metadata=clip_metadata,
        )

    except Exception as exc:
        logger.error(
            "pipeline_error: task_id=%s error=%s", request.task_id, exc, exc_info=True
        )
        return ProcessingResult(
            task_id=request.task_id,
            error=str(exc),
        )


# end src/services/video_service.py
