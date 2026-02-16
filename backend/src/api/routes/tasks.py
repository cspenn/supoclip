# start backend/src/api/routes/tasks.py
"""
Task API routes using refactored architecture.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
import json
import logging

from ...database import get_db
from ...services.task_service import TaskService
from ...services.user_preferences_service import UserPreferencesService
from ...workers.job_queue import JobQueue
from ...workers.tasks import process_video_task
from ...config import Config

logger = logging.getLogger(__name__)
config = Config()
router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/")
async def list_tasks(
    request: Request, db: AsyncSession = Depends(get_db), limit: int = 50
):
    """
    Get all tasks for the authenticated user.
    """
    user_id = request.headers.get("user_id")

    # Use default user_id if auth is disabled
    if not user_id:
        if config.disable_auth:
            user_id = config.default_user_id
        else:
            raise HTTPException(status_code=401, detail="User authentication required")

    try:
        task_service = TaskService(db, config)
        tasks = await task_service.get_user_tasks(user_id, limit)

        return {"tasks": tasks, "total": len(tasks)}

    except Exception as e:
        logger.error(f"Error retrieving user tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving tasks: {e}")


@router.post("/")
async def create_task(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Create a new task and enqueue it for processing.
    Returns task_id immediately.
    """
    data = await request.json()
    headers = request.headers

    raw_source = data.get("source")
    user_id = headers.get("user_id")

    # Get font options
    font_options = data.get("font_options", {})
    font_family = font_options.get("font_family", "TikTokSans-Regular")
    font_size = font_options.get("font_size", 24)
    font_color = font_options.get("font_color", "#FFFFFF")

    if not raw_source or not raw_source.get("url"):
        raise HTTPException(status_code=400, detail="Source URL is required")

    # Use default user_id if auth is disabled
    if not user_id:
        if config.disable_auth:
            user_id = config.default_user_id
        else:
            raise HTTPException(status_code=401, detail="User authentication required")

    try:
        # Get clip length settings from request or use defaults
        min_length = data.get("min_length", 10)
        max_length = data.get("max_length", 45)

        # Load user preferences including logo settings
        pref_service = UserPreferencesService(db)

        # Merge preferences: request > user prefs > defaults
        request_opts = {
            "font_family": font_family,
            "font_size": font_size,
            "font_color": font_color,
        }

        preferences = await pref_service.merge_with_request_options(
            user_id, request_opts
        )
        logo_path = pref_service.get_logo_path(preferences)
        logo_corner_position = preferences.get("logo_corner_position", "top-right")

        # Convert Path to string for serialization (job queue requires JSON-serializable args)
        logo_path_str = str(logo_path) if logo_path else None

        task_service = TaskService(db, config)

        # Create task
        task_id = await task_service.create_task_with_source(
            user_id=user_id,
            url=raw_source["url"],
            title=raw_source.get("title"),
            font_family=font_family,
            font_size=font_size,
            font_color=font_color,
        )

        # Get source type for worker
        source_type = task_service.video_service.determine_source_type(
            raw_source["url"]
        )

        # Enqueue job for worker with clip length and logo parameters
        job_id = await JobQueue.enqueue_job(
            process_video_task,
            task_id,
            raw_source["url"],
            source_type,
            user_id,
            font_family,
            font_size,
            font_color,
            min_length,
            max_length,
            logo_path_str,
            logo_corner_position,
        )

        logger.info(
            f"Task {task_id} created and job {job_id} enqueued with clip length settings: min={min_length}s, max={max_length}s, logo={'enabled' if logo_path_str else 'disabled'}"
        )

        return {
            "task_id": task_id,
            "job_id": job_id,
            "message": "Task created and queued for processing",
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {e}")


@router.get("/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get task details."""
    try:
        task_service = TaskService(db, config)
        task = await task_service.get_task_with_clips(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task: {e}")


@router.get("/{task_id}/clips")
async def get_task_clips(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get all clips for a task."""
    try:
        task_service = TaskService(db, config)
        task = await task_service.get_task_with_clips(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": task_id,
            "clips": task.get("clips", []),
            "total_clips": len(task.get("clips", [])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving clips: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving clips: {e}")


@router.get("/{task_id}/progress")
async def get_task_progress_sse(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    SSE endpoint for real-time progress updates.
    Streams progress updates as Server-Sent Events.
    """
    from ...workers.local_progress import get_progress_tracker

    async def event_generator():
        """Generate SSE events for task progress."""
        # First, check if task exists
        task_service = TaskService(db, config)
        task = await task_service.task_repo.get_task_by_id(db, task_id)

        if not task:
            yield {"event": "error", "data": json.dumps({"error": "Task not found"})}
            return

        # Send initial task status
        yield {
            "event": "status",
            "data": json.dumps(
                {
                    "task_id": task_id,
                    "status": task.get("status"),
                    "progress": task.get("progress", 0),
                    "message": task.get("progress_message", ""),
                }
            ),
        }

        # If task is already completed or error, close connection
        if task.get("status") in ("completed", "error"):
            yield {"event": "close", "data": json.dumps({"status": task.get("status")})}
            return

        # Get local progress tracker
        tracker = get_progress_tracker()

        try:
            # Subscribe to progress updates
            async for progress in tracker.subscribe(task_id):
                yield {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "task_id": progress.task_id,
                            "progress": progress.progress,
                            "message": progress.message,
                            "status": progress.status,
                            "updated_at": progress.updated_at.isoformat(),
                        }
                    ),
                }

                # Close connection if task is done
                if progress.status in ("completed", "error"):
                    yield {
                        "event": "close",
                        "data": json.dumps({"status": progress.status}),
                    }
                    break

        except Exception as e:
            logger.error(f"Error streaming progress: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@router.patch("/{task_id}")
async def update_task(
    task_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Update task details (title)."""
    try:
        data = await request.json()
        title = data.get("title")

        if not title:
            raise HTTPException(status_code=400, detail="Title is required")

        task_service = TaskService(db, config)

        # Get task to verify it exists
        task = await task_service.task_repo.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Update source title
        await task_service.source_repo.update_source_title(db, task["source_id"], title)

        return {"message": "Task updated successfully", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating task: {e}")


@router.delete("/{task_id}")
async def delete_task(
    task_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Delete a task and all its associated clips."""
    try:
        headers = request.headers
        user_id = headers.get("user_id")

        # Use default user_id if auth is disabled
        if not user_id:
            if config.disable_auth:
                user_id = config.default_user_id
            else:
                raise HTTPException(
                    status_code=401, detail="User authentication required"
                )

        task_service = TaskService(db, config)

        # Get task to verify ownership
        task = await task_service.task_repo.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this task"
            )

        # Delete clips and task
        await task_service.delete_task(task_id)

        return {"message": "Task deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting task: {e}")


@router.delete("/{task_id}/clips/{clip_id}")
async def delete_clip(
    task_id: str, clip_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Delete a specific clip."""
    try:
        headers = request.headers
        user_id = headers.get("user_id")

        # Use default user_id if auth is disabled
        if not user_id:
            if config.disable_auth:
                user_id = config.default_user_id
            else:
                raise HTTPException(
                    status_code=401, detail="User authentication required"
                )

        task_service = TaskService(db, config)

        # Verify task ownership
        task = await task_service.task_repo.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this clip"
            )

        # Delete the clip
        await task_service.clip_repo.delete_clip(db, clip_id)

        return {"message": "Clip deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting clip: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting clip: {e}")


# end backend/src/api/routes/tasks.py
