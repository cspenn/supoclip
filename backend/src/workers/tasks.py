# start backend/src/workers/tasks.py
"""
Worker tasks - background jobs processed by local asyncio queue.

This module defines tasks that are executed asynchronously by the local
job queue (LocalJobQueue). Tasks are executed with asyncio workers.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
) -> Dict[str, Any]:
    """
    Background worker task to process a video.

    Args:
        task_id: Task ID to update
        url: Video URL or file path
        source_type: "youtube" or "upload"
        user_id: User ID who created the task
        font_family: Font family for subtitles
        font_size: Font size for subtitles
        font_color: Font color for subtitles

    Returns:
        Dict with processing results
    """
    from ..database import AsyncSessionLocal
    from ..services.task_service import TaskService
    from ..workers.local_progress import get_progress_tracker
    from ..config import Config

    logger.info(f"Worker processing task {task_id}")

    # Create progress tracker (local in-memory version)
    progress = get_progress_tracker()
    config = Config()

    async with AsyncSessionLocal() as db:
        task_service = TaskService(db, config)

        try:
            # Progress callback
            async def update_progress(percent: int, message: str) -> None:
                await progress.update(task_id, percent, message, "processing")
                logger.info(f"Task {task_id}: {percent}% - {message}")

            # Process the video
            result = await task_service.process_task(
                task_id=task_id,
                url=url,
                source_type=source_type,
                font_family=font_family,
                font_size=font_size,
                font_color=font_color,
                progress_callback=update_progress,
            )

            logger.info(f"Task {task_id} completed successfully")
            await progress.update(task_id, 100, "Completed", "completed")
            return result

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await progress.update(task_id, 0, f"Error: {str(e)}", "error")
            raise


# end backend/src/workers/tasks.py
