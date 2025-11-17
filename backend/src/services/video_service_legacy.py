# start backend/src/services/video_service_legacy.py

"""Legacy synchronous video processing service.

This service handles the original /start endpoint which processes videos
with a maximum 5-minute timeout. Kept for backward compatibility while
the new async service is being rolled out.
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
from ..models import GeneratedClip, Source, Task
from ..video_utils import create_clips_with_transitions, get_video_transcript
from ..youtube_utils import download_youtube_video, get_youtube_video_title

logger = logging.getLogger(__name__)


class LegacySyncVideoService:
    """Legacy synchronous video processing service.

    Handles the /start endpoint which processes videos with a max 5-minute timeout.
    Kept for backward compatibility while new async service is rolled out.
    """

    def __init__(self, db: AsyncSession, config: Config):
        """Initialize the legacy sync video service.

        Args:
            db: Database session
            config: Application configuration
        """
        self.db = db
        self.config = config

    async def process_video(
        self,
        raw_source: dict[str, Any],
        user_id: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        clip_min_length: int = 10,
        clip_target_length: int = 30,
        clip_max_length: int = 45,
        custom_ai_prompt: Optional[str] = None,
        logo_path: Optional[Path] = None,
        logo_corner_position: str = "top-right",
    ) -> dict[str, Any]:
        """Process video synchronously (max 5 min timeout).

        This method contains the exact logic extracted from the /start endpoint.
        It processes the video inline and returns clips immediately.

        Args:
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

        Returns:
            Dictionary containing task_id, clips, segments, and AI analysis
        """
        logger.info("[SERVICE=LEGACY] Starting synchronous video processing")

        # Create source
        source = Source()
        source.type = source.decide_source_type(raw_source["url"])
        logger.info(f"[SERVICE=LEGACY] Source type detected: {source.type}")

        # Get title based on source type
        if source.type == "youtube":
            logger.info("[SERVICE=LEGACY] Getting YouTube video title")
            title = get_youtube_video_title(raw_source["url"])
            source.title = title if title else "YouTube Video"
            if not title:
                logger.warning(
                    "[SERVICE=LEGACY] Could not get YouTube title, using default"
                )
            logger.info(f"[SERVICE=LEGACY] Video title: {source.title}")
        else:
            source.title = raw_source.get("title", "Uploaded Video")
            logger.info(f"[SERVICE=LEGACY] Custom title: {source.title}")

        relevant_segments_json = []
        clips_info = []
        relevant_parts = None

        # Save source and create task
        logger.info("[SERVICE=LEGACY] Saving source and creating task in database")
        self.db.add(source)
        await self.db.flush()
        logger.info(f"[SERVICE=LEGACY] Source saved with ID: {source.id}")

        task = Task(
            user_id=user_id,
            source_id=source.id,
            generated_clips_ids=None,
            font_family=font_family,
            font_size=font_size,
            font_color=font_color,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.db.add(task)
        await self.db.commit()
        logger.info(f"[SERVICE=LEGACY] Task created with ID: {task.id}")

        # Determine video path based on source type
        video_path = None
        if source.type == "youtube":
            logger.info("[SERVICE=LEGACY] Starting YouTube video download")
            video_path = download_youtube_video(raw_source["url"])
            if not video_path:
                logger.error("[SERVICE=LEGACY] Failed to download video")
                raise Exception("Failed to download video")
            logger.info(f"[SERVICE=LEGACY] Video downloaded to: {video_path}")
        else:
            # For uploaded videos, the URL is actually the file path
            video_path = raw_source["url"]
            logger.info(f"[SERVICE=LEGACY] Using uploaded video at: {video_path}")

            # Verify the uploaded file exists
            if isinstance(video_path, str) and not Path(video_path).exists():
                logger.error(
                    f"[SERVICE=LEGACY] Uploaded video file not found: {video_path}"
                )
                raise Exception("Uploaded video file not found")

        # Process video (same for both YouTube and uploaded videos)
        if video_path:
            logger.info(
                "[SERVICE=LEGACY] Starting transcript generation with AssemblyAI + SRT equalization"
            )
            transcript = get_video_transcript(video_path)
            logger.info(
                f"[SERVICE=LEGACY] AssemblyAI transcript generated with 10-char line equalization (length: {len(transcript)} characters)"
            )

            logger.info("[SERVICE=LEGACY] Starting AI analysis for relevant segments")
            relevant_parts = await get_most_relevant_parts_by_transcript(
                transcript,
                min_length=clip_min_length,
                max_length=clip_max_length,
                custom_prompt=custom_ai_prompt,
            )
            logger.info(
                f"[SERVICE=LEGACY] AI analysis complete - found {len(relevant_parts.most_relevant_segments)} segments"
            )

            # Convert to JSON format for response
            logger.info("[SERVICE=LEGACY] Converting AI results to JSON format")
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
            logger.info(
                f"[SERVICE=LEGACY] Created {len(relevant_segments_json)} segment records"
            )

            # Create clips from relevant segments with transitions and custom fonts
            logger.info(
                "[SERVICE=LEGACY] Starting video clip generation with transitions"
            )
            clips_output_dir = Path(self.config.temp_dir) / "clips"
            logger.info(f"[SERVICE=LEGACY] Output directory: {clips_output_dir}")
            logger.info(
                f"[SERVICE=LEGACY] Font settings - Family: {font_family}, Size: {font_size}, Color: {font_color}"
            )
            clips_info = create_clips_with_transitions(
                video_path,
                relevant_segments_json,
                clips_output_dir,
                font_family,
                font_size,
                font_color,
                logo_path,
                logo_corner_position,
            )
            logger.info(
                f"[SERVICE=LEGACY] Generated {len(clips_info)} video clips with transitions"
            )

            # Save clips to database
            logger.info("[SERVICE=LEGACY] Saving clips to database")
            clip_ids = []
            for i, clip_info in enumerate(clips_info):
                logger.info(
                    f"[SERVICE=LEGACY] Saving clip {i+1}/{len(clips_info)}: {clip_info['filename']}"
                )
                clip_record = GeneratedClip(
                    task_id=task.id,
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
                self.db.add(clip_record)
                await self.db.flush()
                clip_ids.append(clip_record.id)
                logger.info(
                    f"[SERVICE=LEGACY] Clip {i+1} saved with ID: {clip_record.id}"
                )

            # Update task with clip IDs
            logger.info(f"[SERVICE=LEGACY] Updating task with {len(clip_ids)} clip IDs")
            await self.db.execute(
                text(
                    "UPDATE tasks SET generated_clips_ids = :clip_ids WHERE id = :task_id"
                ),
                {"clip_ids": json.dumps(clip_ids), "task_id": task.id},
            )
            await self.db.commit()
            logger.info("[SERVICE=LEGACY] Task updated with clip IDs")
        else:
            logger.error("[SERVICE=LEGACY] No video path available for processing")
            raise Exception("No video available for processing")

        logger.info(f"[SERVICE=LEGACY] Task completed successfully! Task ID: {task.id}")
        logger.info(
            f"[SERVICE=LEGACY] Final results - Segments: {len(relevant_segments_json)}, Clips: {len(clips_info)}"
        )

        return {
            "message": "Task started successfully",
            "task_id": task.id,
            "relevant_segments": relevant_segments_json,
            "clips": clips_info,
            "summary": relevant_parts.summary if relevant_parts else None,
            "key_topics": relevant_parts.key_topics if relevant_parts else None,
        }


# end backend/src/services/video_service_legacy.py
