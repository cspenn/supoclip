# start backend/src/services/video_service_async.py

"""Asynchronous video processing service.

This service handles the /start-with-progress endpoint which processes videos
asynchronously with SSE progress tracking. Can handle unlimited processing time.

Architecture note: This service is responsible for task lifecycle management
(DB operations, status updates, clip persistence) while delegating the core
video processing pipeline to VideoService.process_video_complete(). This avoids
duplicating the download -> transcribe -> analyze -> create-clips pipeline.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config
from ..database import AsyncSessionLocal
from ..models import GeneratedClip, Source, Task
from .video_service import VideoService
from ..youtube_utils import get_youtube_video_title

logger = logging.getLogger(__name__)

# Minimum file size in bytes to validate clip is not corrupted
MIN_CLIP_FILE_SIZE_BYTES = 1000  # 1 KB minimum


class AsyncVideoProcessingService:
    """Asynchronous video processing service.

    Handles the /start-with-progress endpoint which processes videos with SSE progress tracking.
    Can handle unlimited processing time - returns task_id for client to track progress.

    This service owns:
    - Task/Source creation in the database
    - Task status updates
    - Clip file validation and persistence to the database

    It delegates the core video processing pipeline (download, transcribe, analyze,
    create clips) to VideoService.process_video_complete(), which is the single
    source of truth for that logic.
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

    async def process_video_async(
        self,
        task_id: str,
        raw_source: dict[str, Any],
        user_id: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        clip_min_length: int = 10,
        clip_max_length: int = 45,
        custom_ai_prompt: str | None = None,
        logo_path: str | None = None,
        logo_corner_position: str = "top-right",
        output_resolution: str = "720p",
        subtitle_style: dict[str, Any] | None = None,
        subtitle_position: dict[str, Any] | None = None,
    ) -> None:
        """Process video asynchronously in background.

        This method is spawned as a background task. It delegates the core
        video processing to VideoService.process_video_complete() and handles
        task lifecycle (status updates, clip persistence, error handling).

        Args:
            task_id: Task ID to update
            raw_source: Source information with URL
            user_id: Authenticated user ID
            font_family: Font family name for subtitles
            font_size: Font size for subtitles
            font_color: Font color for subtitles
            clip_min_length: Minimum clip length in seconds
            clip_max_length: Maximum clip length in seconds
            custom_ai_prompt: Optional custom AI prompt override
            logo_path: Optional path to user logo
            logo_corner_position: Corner position for logo
            output_resolution: Target resolution - "480p", "720p", or "1080p"
            subtitle_style: Optional subtitle style overrides
            subtitle_position: Optional subtitle position overrides
        """
        try:
            logger.info(
                f"[SERVICE=ASYNC] Starting background processing for task {task_id}"
            )
            await self._update_task_status(task_id, "processing")

            # Get source type from database
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

            source_type = source_data.type
            logger.info(
                f"[SERVICE=ASYNC] Task {task_id}: Source type is '{source_type}'"
            )

            # Delegate to VideoService for the core processing pipeline.
            # VideoService.process_video_complete handles: download, transcribe,
            # AI analysis, verbatim text extraction, and clip creation.
            result = await VideoService.process_video_complete(
                url=raw_source["url"],
                source_type=source_type,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
                min_length=clip_min_length,
                max_length=clip_max_length,
                output_resolution=output_resolution,
                logo_path=logo_path,
                logo_corner_position=logo_corner_position,
                custom_ai_prompt=custom_ai_prompt,
                subtitle_style=subtitle_style,
                subtitle_position=subtitle_position,
            )

            clips_info = result["clips"]

            # Save clips to database with file validation
            logger.info(
                f"[SERVICE=ASYNC] Task {task_id}: Saving {len(clips_info)} clips to database..."
            )
            clip_ids: list[str] = []
            async with AsyncSessionLocal() as db:
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

            # Postcondition: only mark completed if valid clips were produced
            if clip_ids:
                await self._update_task_status(task_id, "completed")
                logger.info(f"[SERVICE=ASYNC] Task {task_id} completed successfully!")
            else:
                await self._update_task_status(
                    task_id,
                    "error",
                    error_message="No valid clips were produced -- all clips were invalid or skipped.",
                )
                logger.error(
                    f"[SERVICE=ASYNC] Task {task_id} failed: no valid clips produced"
                )

        except Exception as e:
            logger.error(f"[SERVICE=ASYNC] Error processing task {task_id}: {e}")
            # Store error message for user visibility
            await self._update_task_status(task_id, "error", error_message=str(e))
            logger.error(f"[SERVICE=ASYNC] Task {task_id} marked as error: {e}")

    async def _update_task_status(
        self, task_id: str, status: str, error_message: str | None = None
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
