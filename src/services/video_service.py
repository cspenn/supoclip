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
from typing import Any

from src.config import Config
from src.database import get_session
from src.models import GeneratedClip, Task
from src.pipeline.analyze import AnalysisError, TranscriptSegment, analyze_transcript
from src.pipeline.download import (
    DownloadError,
    download_youtube_video,
    validate_youtube_url,
)

# Legacy imports — used by the VideoService compatibility shim and old tests.
# Wrapped in try/except so the module imports cleanly in the new pipeline
# even if the old modules are not present.
try:
    from src.utils.async_helpers import run_in_thread  # type: ignore[import]
except ImportError:
    run_in_thread = None  # type: ignore[assignment]

try:
    from src.youtube_utils import (  # type: ignore[import]
        get_youtube_video_id,
        get_youtube_video_title,
    )
except ImportError:
    get_youtube_video_id = None  # type: ignore[assignment]
    get_youtube_video_title = None  # type: ignore[assignment]

try:
    from src.video_utils import (  # type: ignore[import]
        create_clips_with_transitions,
        format_ms_to_timestamp_precise,
        get_video_transcript,
        parse_timestamp_to_seconds,
        snap_segment_to_sentence_start,
    )
except ImportError:
    create_clips_with_transitions = None  # type: ignore[assignment]
    format_ms_to_timestamp_precise = None  # type: ignore[assignment]
    get_video_transcript = None  # type: ignore[assignment]
    parse_timestamp_to_seconds = None  # type: ignore[assignment]
    snap_segment_to_sentence_start = None  # type: ignore[assignment]

try:
    from src.ai import get_most_relevant_parts_by_transcript  # type: ignore[import]
except ImportError:
    get_most_relevant_parts_by_transcript = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
_config = Config()

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


# ---------------------------------------------------------------------------
# Backward-compatibility layer (removed in C7 cleanup)
# ---------------------------------------------------------------------------


class VideoDownloadError(Exception):
    """Raised when video download fails."""


class VideoNotFoundError(Exception):
    """Raised when a local video file is not found."""


class VideoProcessingResponse:
    """Helper for building legacy video processing response dicts."""

    @staticmethod
    def build_response(
        segments_json: list[dict[str, Any]],
        clips_info: list[dict[str, Any]],
        relevant_parts: Any,
    ) -> dict[str, Any]:
        """Build the video processing response dictionary.

        Args:
            segments_json: List of segment dictionaries.
            clips_info: List of generated clip info dictionaries.
            relevant_parts: TranscriptAnalysis result with summary and topics.

        Returns:
            Response dictionary with segments, clips, summary, and key_topics.
        """
        return {
            "segments": segments_json,
            "clips": clips_info,
            "summary": relevant_parts.summary if relevant_parts else None,
            "key_topics": relevant_parts.key_topics if relevant_parts else None,
        }

    @staticmethod
    def segments_to_json(segments: list[Any]) -> list[dict[str, Any]]:
        """Convert segment objects to JSON-serializable dicts.

        Args:
            segments: List of TranscriptSegment objects.

        Returns:
            List of dicts with start_time, end_time, text, relevance_score, reasoning.
        """
        return [
            {
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "text": seg.text,
                "relevance_score": seg.relevance_score,
                "reasoning": seg.reasoning,
            }
            for seg in segments
        ]


class VideoService:
    """Backward-compatibility service class.

    .. deprecated::
        Use :func:`process_video` directly.  This class will be removed in C7.
    """

    @staticmethod
    async def _get_video_path(url: str, source_type: str) -> Path:
        """Get video path by downloading or validating an existing path.

        Args:
            url: Video URL or file path.
            source_type: ``'youtube'`` or ``'upload'``.

        Returns:
            Path to the video file.

        Raises:
            VideoDownloadError: If YouTube download fails.
            VideoNotFoundError: If uploaded file not found.
        """
        if source_type == "youtube":
            video_path = await VideoService.download_video(url)
            if not video_path:
                raise VideoDownloadError(f"Failed to download video from URL: {url}")
            return video_path

        video_path = Path(url)
        if not video_path.exists():
            raise VideoNotFoundError(f"Video file not found at path: {url}")
        return video_path

    @staticmethod
    async def download_video(url: str) -> Path | None:
        """Download a YouTube video asynchronously via thread pool.

        Args:
            url: YouTube video URL to download.

        Returns:
            Path to the downloaded video file, or None if download fails.
        """
        try:
            logger.info("Starting video download: %s", url)
            if run_in_thread is None:
                raise RuntimeError("async_helpers.run_in_thread not available")
            video_path = await run_in_thread(  # type: ignore[misc]
                # The old youtube_utils.download_youtube_video (sync)
                __import__("src.youtube_utils", fromlist=["download_youtube_video"]).download_youtube_video,
                url,
            )
            if not video_path:
                logger.error("Failed to download video: %s", url)
                return None
            logger.info("Video downloaded: %s", video_path)
            return video_path
        except Exception as exc:
            logger.error("Download error for %s: %s", url, exc, exc_info=True)
            raise

    @staticmethod
    async def get_video_title(url: str) -> str:
        """Return YouTube video title, or 'YouTube Video' on failure.

        Args:
            url: YouTube video URL.

        Returns:
            Title string.
        """
        try:
            if run_in_thread and get_youtube_video_title:
                title = await run_in_thread(get_youtube_video_title, url)  # type: ignore[misc]
                return title or "YouTube Video"
            return "YouTube Video"
        except Exception as exc:
            logger.warning("Failed to get video title: %s", exc)
            return "YouTube Video"

    @staticmethod
    async def generate_transcript(video_path: Path) -> str:
        """Generate transcript from video using parakeet-mlx via thread pool.

        Args:
            video_path: Path to the video file.

        Returns:
            Formatted transcript string with word-level timestamps.
        """
        try:
            logger.info("Generating transcript for: %s", video_path)
            if run_in_thread is None or get_video_transcript is None:
                raise RuntimeError("video_utils not available")
            transcript = await run_in_thread(get_video_transcript, video_path)  # type: ignore[misc]
            logger.info("Transcript generated: %d characters", len(transcript))
            return transcript
        except Exception as exc:
            logger.error("Transcript error for %s: %s", video_path, exc, exc_info=True)
            raise

    @staticmethod
    async def analyze_transcript(
        transcript: str,
        min_length: int = 10,
        max_length: int = 45,
        custom_ai_prompt: str | None = None,
    ) -> Any:
        """Analyze transcript with AI to find relevant segments.

        Args:
            transcript: Video transcript text.
            min_length: Minimum clip length in seconds.
            max_length: Maximum clip length in seconds.
            custom_ai_prompt: Optional custom AI prompt override.

        Returns:
            TranscriptAnalysis with validated segments sorted by relevance.
        """
        logger.info("Starting AI analysis of transcript")
        if get_most_relevant_parts_by_transcript is None:
            raise RuntimeError("src.ai not available")
        relevant_parts = await get_most_relevant_parts_by_transcript(
            transcript,
            min_length=min_length,
            max_length=max_length,
            custom_prompt=custom_ai_prompt,
        )
        logger.info(
            "AI analysis complete: %d segments",
            len(relevant_parts.most_relevant_segments),
        )
        return relevant_parts

    @staticmethod
    async def create_video_clips(
        video_path: Path,
        segments: list[dict[str, Any]],
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        output_resolution: str = "720p",
        logo_path: str | None = None,
        logo_corner_position: str | None = "top-right",
        subtitle_style: dict[str, Any] | None = None,
        subtitle_position: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Create video clips from segments with transitions and subtitles.

        Args:
            video_path: Path to source video file.
            segments: List of segment dicts.
            font_family: Font family for subtitles.
            font_size: Font size for subtitles.
            font_color: Font colour for subtitles.
            output_resolution: Target resolution preset.
            logo_path: Optional logo image path.
            logo_corner_position: Logo position.
            subtitle_style: Optional subtitle style overrides.
            subtitle_position: Optional subtitle position overrides.

        Returns:
            List of clip info dictionaries.
        """
        if run_in_thread is None or create_clips_with_transitions is None:
            raise RuntimeError("video_utils not available")
        try:
            logger.info(
                "Creating %d video clips at %s", len(segments), output_resolution
            )
            clips_output_dir = Path(_config.temp_dir) / "clips"
            clips_output_dir.mkdir(parents=True, exist_ok=True)

            clips_info = await run_in_thread(  # type: ignore[misc]
                create_clips_with_transitions,
                video_path,
                segments,
                clips_output_dir,
                font_family,
                font_size,
                font_color,
                logo_path,
                logo_corner_position,
                output_resolution,
                subtitle_style,
                subtitle_position,
            )
            logger.info("Created %d clips", len(clips_info))
            return clips_info
        except Exception as exc:
            logger.error("Clip creation error: %s", exc, exc_info=True)
            raise

    @staticmethod
    def determine_source_type(url: str) -> str:
        """Return ``'youtube'`` or ``'upload'`` for a given URL.

        Args:
            url: Video URL or file path.

        Returns:
            ``'youtube'`` or ``'upload'``.
        """
        if get_youtube_video_id is not None:
            return "youtube" if get_youtube_video_id(url) else "upload"
        return "youtube" if validate_youtube_url(url) else "upload"

    @staticmethod
    def _validate_clip_duration_params(
        min_length: int, max_length: int
    ) -> tuple[int, int]:
        """Validate and normalise clip duration parameters.

        Args:
            min_length: Minimum clip length in seconds.
            max_length: Maximum clip length in seconds.

        Returns:
            Tuple of ``(validated_min_length, validated_max_length)``.
        """
        if min_length < 10:
            logger.warning("min_length %ds too short. Setting to 10s.", min_length)
            min_length = 10
        if min_length > 60:
            logger.warning("min_length %ds exceeds 60s. Capping.", min_length)
            min_length = 60
        if max_length > 120:
            logger.warning("max_length %ds exceeds 120s. Capping.", max_length)
            max_length = 120
        if max_length < min_length:
            logger.warning(
                "max_length < min_length. Adjusting to %ds.", min_length + 10
            )
            max_length = min_length + 10
        return min_length, max_length

    @staticmethod
    def _apply_verbatim_text_to_segment(
        segment: dict[str, Any], video_path: Path
    ) -> None:
        """Apply verbatim transcript text to a segment, snapping to sentence start.

        Modifies *segment* in-place.

        Args:
            segment: Segment dictionary to update.
            video_path: Path to video file for transcript cache lookup.
        """
        if parse_timestamp_to_seconds is None or snap_segment_to_sentence_start is None:
            return

        try:
            from src.video_utils import extract_text_from_cache  # type: ignore[import]
        except ImportError:
            return

        original_start_ts = segment["start_time"]
        start_sec = parse_timestamp_to_seconds(original_start_ts)
        new_start_sec, _, snap_reason = snap_segment_to_sentence_start(
            video_path, start_sec
        )

        if abs(new_start_sec - start_sec) > 0.01 and format_ms_to_timestamp_precise:
            new_start_ts = format_ms_to_timestamp_precise(int(new_start_sec * 1000))
            logger.info(
                "Snapped segment start: %s -> %s (%s)",
                original_start_ts,
                new_start_ts,
                snap_reason,
            )
            segment["start_time"] = new_start_ts
            segment["original_ai_start_time"] = original_start_ts

        verbatim = extract_text_from_cache(
            video_path,
            parse_timestamp_to_seconds(segment["start_time"]),
            parse_timestamp_to_seconds(segment["end_time"]),
        )
        if verbatim:
            segment["text"] = verbatim
        else:
            logger.warning(
                "Could not extract verbatim text for %s", segment["start_time"]
            )

    @staticmethod
    async def process_video_complete(
        url: str,
        source_type: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        min_length: int = 10,
        max_length: int = 45,
        output_resolution: str = "720p",
        logo_path: str | None = None,
        logo_corner_position: str | None = "top-right",
        progress_callback: Callable | None = None,
        custom_ai_prompt: str | None = None,
        subtitle_style: dict[str, Any] | None = None,
        subtitle_position: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the complete video processing pipeline (legacy entrypoint).

        Args:
            url: Video URL or file path.
            source_type: ``'youtube'`` or ``'upload'``.
            font_family: Font family for subtitles.
            font_size: Font size for subtitles.
            font_color: Font colour for subtitles.
            min_length: Minimum clip length in seconds.
            max_length: Maximum clip length in seconds.
            output_resolution: Target resolution preset.
            logo_path: Optional logo image path.
            logo_corner_position: Logo corner position.
            progress_callback: Optional async callback ``(int, str)``.
            custom_ai_prompt: Optional custom AI prompt.
            subtitle_style: Optional subtitle style overrides.
            subtitle_position: Optional subtitle position overrides.

        Returns:
            Dict with ``segments``, ``clips``, ``summary``, ``key_topics``.
        """
        try:
            logger.info(
                "🟢 Processing video with parameters: "
                "font_family=%s, font_size=%d, font_color=%s, "
                "clip_length=%ds-%ds, output_resolution=%s",
                font_family,
                font_size,
                font_color,
                min_length,
                max_length,
                output_resolution,
            )

            if progress_callback:
                await progress_callback(10, "Downloading video...")
            video_path = await VideoService._get_video_path(url, source_type)

            if progress_callback:
                await progress_callback(30, "Generating transcript...")
            transcript = await VideoService.generate_transcript(video_path)

            if progress_callback:
                await progress_callback(50, "Analyzing content with AI...")
            min_length, max_length = VideoService._validate_clip_duration_params(
                min_length, max_length
            )
            relevant_parts = await VideoService.analyze_transcript(
                transcript,
                min_length=min_length,
                max_length=max_length,
                custom_ai_prompt=custom_ai_prompt,
            )

            if progress_callback:
                await progress_callback(70, "Creating video clips...")
            segments_json = VideoProcessingResponse.segments_to_json(
                relevant_parts.most_relevant_segments
            )
            for segment in segments_json:
                VideoService._apply_verbatim_text_to_segment(segment, video_path)

            clips_info = await VideoService.create_video_clips(
                video_path,
                segments_json,
                font_family,
                font_size,
                font_color,
                output_resolution,
                logo_path,
                logo_corner_position,
                subtitle_style,
                subtitle_position,
            )

            if progress_callback:
                await progress_callback(100, "Processing complete!")

            return VideoProcessingResponse.build_response(
                segments_json, clips_info, relevant_parts
            )

        except Exception as exc:
            logger.error("Error in legacy pipeline: %s", exc, exc_info=True)
            raise


# end src/services/video_service.py
