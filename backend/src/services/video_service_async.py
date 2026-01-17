# start backend/src/services/video_service_async.py

"""Asynchronous video processing service.

This service handles the /start-with-progress endpoint which processes videos
asynchronously with SSE progress tracking. Can handle unlimited processing time.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import get_most_relevant_parts_by_transcript
from ..config import Config
from ..database import AsyncSessionLocal
from ..models import GeneratedClip, Source, Task
from ..video_utils import (
    create_clips_with_transitions,
    extract_text_from_cache,
    format_ms_to_timestamp_precise,
    get_video_transcript,
    parse_timestamp_to_seconds,
    snap_segment_to_sentence_start,
)
from ..utils.async_helpers import run_in_thread
from ..youtube_utils import download_youtube_video, get_youtube_video_title

logger = logging.getLogger(__name__)

# Minimum file size in bytes to validate clip is not corrupted
MIN_CLIP_FILE_SIZE_BYTES = 1000  # 1 KB minimum


class AsyncVideoProcessingService:
    """Asynchronous video processing service.

    Handles the /start-with-progress endpoint which processes videos with SSE progress tracking.
    Can handle unlimited processing time - returns task_id for client to track progress.
    """

    def __init__(self, db: AsyncSession, config: Config):
        """Initialize the async video processing service.

        Args:
            db: Database session
            config: Application configuration
        """
        self.db = db
        self.config = config

    async def create_task(
        self,
        raw_source: dict[str, Any],
        user_id: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ) -> str:
        """Create task and start background processing.

        This method creates the initial task record and spawns a background
        task to process the video asynchronously.

        Args:
            raw_source: Source information with URL
            user_id: Authenticated user ID
            font_family: Font family name for subtitles
            font_size: Font size for subtitles
            font_color: Font color for subtitles

        Returns:
            Task ID for SSE progress tracking
        """
        logger.info("[SERVICE=ASYNC] Creating task for async processing")

        # Create source
        source = Source()
        source.type = source.decide_source_type(raw_source["url"])

        # Get title based on source type
        if source.type == "youtube":
            try:
                title = get_youtube_video_title(raw_source["url"])
                source.title = title or "YouTube Video"
                if not title:
                    logger.warning(
                        "[SERVICE=ASYNC] Could not get YouTube title, using default"
                    )
                logger.info(f"[SERVICE=ASYNC] YouTube video title: {source.title}")
            except Exception as e:
                logger.warning(
                    f"[SERVICE=ASYNC] Could not get YouTube title, using default: {e}"
                )
                source.title = "YouTube Video"
        else:
            source.title = raw_source.get("title", "Uploaded Video")

        self.db.add(source)
        await self.db.flush()

        task = Task(
            user_id=user_id,
            source_id=source.id,
            generated_clips_ids=None,
            status="processing",
            font_family=font_family,
            font_size=font_size,
            font_color=font_color,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.db.add(task)
        await self.db.commit()

        logger.info(f"[SERVICE=ASYNC] Task created with ID: {task.id}")
        return task.id

    @staticmethod
    def _resolve_video_path(source_type: str, raw_source: dict[str, Any]) -> Path:
        """Resolve video path based on source type.

        Args:
            source_type: Type of source ("youtube" or "upload")
            raw_source: Source information with URL

        Returns:
            Path to the video file

        Raises:
            Exception: If video cannot be resolved
        """
        if source_type == "youtube":
            logger.info("[SERVICE=ASYNC] Downloading YouTube video...")
            video_path = download_youtube_video(raw_source["url"])
            if not video_path:
                raise Exception("Failed to download video")
            logger.info(f"[SERVICE=ASYNC] Video downloaded to: {video_path}")
            return video_path

        video_path = raw_source["url"]
        if isinstance(video_path, str) and not Path(video_path).exists():
            raise Exception("Uploaded video file not found")
        return Path(video_path) if isinstance(video_path, str) else video_path

    @staticmethod
    def _apply_verbatim_text_to_segment(
        segment: dict[str, Any], video_path: Path
    ) -> None:
        """Apply verbatim transcript text to a segment, snapping to sentence start.

        Modifies segment in-place.

        Args:
            segment: Segment dictionary to update
            video_path: Path to video file
        """
        original_start_ts = segment["start_time"]
        start_sec = parse_timestamp_to_seconds(original_start_ts)

        # Snap to sentence start (within 2 second window)
        new_start_sec, snap_word, snap_reason = snap_segment_to_sentence_start(
            video_path, start_sec, search_window_seconds=2.0
        )

        # Update start time if snapped
        if abs(new_start_sec - start_sec) > 0.01:
            new_start_ts = format_ms_to_timestamp_precise(int(new_start_sec * 1000))
            logger.info(
                f"[SYNC] Snapped segment start: {original_start_ts} -> {new_start_ts} ({snap_reason})"
            )
            segment["start_time"] = new_start_ts
            segment["original_ai_start_time"] = original_start_ts

        # Extract verbatim text from transcript cache
        verbatim_text = extract_text_from_cache(
            video_path,
            parse_timestamp_to_seconds(segment["start_time"]),
            parse_timestamp_to_seconds(segment["end_time"]),
        )

        if verbatim_text:
            original_ai_text = segment["text"]
            segment["text"] = verbatim_text
            logger.info(
                f"[SYNC] Replaced text: '{original_ai_text[:30]}...' -> '{verbatim_text[:30]}...'"
            )
        else:
            logger.warning(
                f"[SYNC] Could not extract verbatim text for segment {segment['start_time']} - keeping AI text"
            )

    async def process_video_async(
        self,
        task_id: str,
        raw_source: dict[str, Any],
        user_id: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        clip_min_length: int = 10,
        clip_target_length: int = 30,
        clip_max_length: int = 45,
        custom_ai_prompt: Optional[str] = None,
        logo_path: Optional[str] = None,
        logo_corner_position: str = "top-right",
        output_resolution: str = "720p",
        subtitle_style: Optional[dict[str, Any]] = None,
        subtitle_position: Optional[dict[str, Any]] = None,
    ) -> None:
        """Process video asynchronously in background.

        This method is spawned as a background task and handles the entire
        video processing pipeline with error handling and status updates.

        Args:
            task_id: Task ID to update
            raw_source: Source information with URL
            user_id: Authenticated user ID
            font_family: Font family name for subtitles
            font_size: Font size for subtitles
            font_color: Font color for subtitles
            clip_min_length: Minimum clip length in seconds
            clip_target_length: Target clip length in seconds
            clip_max_length: Maximum clip length in seconds
            custom_ai_prompt: Optional custom AI prompt override
            logo_path: Optional path to user logo
            logo_corner_position: Corner position for logo
            output_resolution: Target resolution - "480p", "720p", or "1080p"
        """
        try:
            logger.info(
                f"[SERVICE=ASYNC] Starting background processing for task {task_id}"
            )
            await self._update_task_status(task_id, "processing")

            # Get source from database
            async with AsyncSessionLocal() as db:
                source_result = await db.execute(
                    text(
                        "SELECT * FROM sources WHERE id IN (SELECT source_id FROM tasks WHERE id = :task_id)"
                    ),
                    {"task_id": task_id},
                )
                source_data = source_result.fetchone()
                if not source_data:
                    raise Exception("Source not found")

            logger.info(f"[SERVICE=ASYNC] Task {task_id}: Analyzing video source...")

            # Resolve video path based on source type
            video_path = self._resolve_video_path(source_data.type, raw_source)

            # Process video
            if video_path:
                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: Generating transcript with AssemblyAI..."
                )
                transcript = get_video_transcript(video_path)
                logger.info(
                    f"[SERVICE=ASYNC] Transcript generated (length: {len(transcript)} characters)"
                )

                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: AI analyzing content for best clips..."
                )
                relevant_parts = await get_most_relevant_parts_by_transcript(
                    transcript,
                    min_length=clip_min_length,
                    max_length=clip_max_length,
                    custom_prompt=custom_ai_prompt,
                )
                logger.info(
                    f"[SERVICE=ASYNC] AI analysis complete - found {len(relevant_parts.most_relevant_segments)} segments"
                )

                # Convert to JSON format
                relevant_segments_json = [
                    {
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "text": segment.text,
                        "relevance_score": segment.relevance_score,
                        "reasoning": segment.reasoning,
                    }
                    for segment in relevant_parts.most_relevant_segments
                ]

                # Apply verbatim transcript text to each segment
                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: Applying verbatim text extraction..."
                )
                for segment in relevant_segments_json:
                    self._apply_verbatim_text_to_segment(segment, video_path)

                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: Creating {len(relevant_segments_json)} video clips with transitions..."
                )
                clips_output_dir = Path(self.config.temp_dir) / "clips"
                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: Font settings - Family: {font_family}, Size: {font_size}, Color: {font_color}"
                )
                # Run sync video processing in thread pool to avoid blocking asyncio loop
                # (required because BrowserSubtitleRenderer uses sync Playwright API)
                clips_info = await run_in_thread(
                    create_clips_with_transitions,
                    video_path,
                    relevant_segments_json,
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
                logger.info(
                    f"[SERVICE=ASYNC] Generated {len(clips_info)} video clips with transitions"
                )

                logger.info(
                    f"[SERVICE=ASYNC] Task {task_id}: Saving clips to database..."
                )
                async with AsyncSessionLocal() as db:
                    clip_ids = []
                    for i, clip_info in enumerate(clips_info):
                        # Validate clip file exists and has content
                        clip_path = Path(clip_info["path"])
                        if not clip_path.exists():
                            logger.error(
                                f"[SERVICE=ASYNC] Clip file does not exist: {clip_path}"
                            )
                            continue

                        file_size = clip_path.stat().st_size
                        if file_size < MIN_CLIP_FILE_SIZE_BYTES:
                            logger.error(
                                f"[SERVICE=ASYNC] Clip file too small ({file_size} bytes): {clip_path}"
                            )
                            continue

                        clip_record = GeneratedClip(
                            task_id=task_id,
                            filename=clip_info["filename"],
                            file_path=clip_info["path"],
                            start_time=clip_info["start_time"],
                            end_time=clip_info["end_time"],
                            duration=clip_info["duration"],
                            text=clip_info["text"],
                            relevance_score=clip_info["relevance_score"],
                            reasoning=clip_info["reasoning"],
                            clip_order=i + 1,
                        )
                        db.add(clip_record)
                        await db.flush()
                        clip_ids.append(clip_record.id)

                    # Update task with clip IDs
                    await db.execute(
                        text(
                            "UPDATE tasks SET generated_clips_ids = :clip_ids WHERE id = :task_id"
                        ),
                        {"clip_ids": json.dumps(clip_ids), "task_id": task_id},
                    )
                    await db.commit()

            # Mark as completed
            await self._update_task_status(task_id, "completed")
            logger.info(f"[SERVICE=ASYNC] Task {task_id} completed successfully!")

        except Exception as e:
            logger.error(f"[SERVICE=ASYNC] Error processing task {task_id}: {e}")
            # Store error message for user visibility (Fix 3: Better error reporting)
            await self._update_task_status(task_id, "error", error_message=str(e))
            logger.error(f"[SERVICE=ASYNC] Task {task_id} marked as error: {e}")

    async def _update_task_status(
        self, task_id: str, status: str, error_message: Optional[str] = None
    ) -> None:
        """Update task status in database.

        Args:
            task_id: Task ID to update
            status: New status value
            error_message: Optional error message to store for user visibility
        """
        async with AsyncSessionLocal() as db:
            if error_message:
                # Store error message in progress_message field for user visibility
                await db.execute(
                    text(
                        "UPDATE tasks SET status = :status, progress_message = :error_msg WHERE id = :task_id"
                    ),
                    {"status": status, "error_msg": error_message, "task_id": task_id},
                )
            else:
                await db.execute(
                    text("UPDATE tasks SET status = :status WHERE id = :task_id"),
                    {"status": status, "task_id": task_id},
                )
            await db.commit()


# end backend/src/services/video_service_async.py
