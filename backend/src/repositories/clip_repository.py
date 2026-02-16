# start backend/src/repositories/clip_repository.py
"""
Clip repository - handles all database operations for generated clips.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Any
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


def parse_sqlite_datetime(dt_value: str | datetime | None) -> datetime | None:
    """
    Convert SQLite TEXT datetime to Python datetime object.

    SQLite stores DATETIME as TEXT in ISO 8601 format. When using raw SQL
    via SQLAlchemy's text() wrapper, these values are returned as strings
    instead of datetime objects. This function handles the conversion.

    Args:
        dt_value: Either a datetime string, datetime object, or None

    Returns:
        datetime object or None
    """
    if dt_value is None or isinstance(dt_value, datetime):
        return dt_value
    return datetime.fromisoformat(dt_value)


class ClipRepository:
    """Repository for clip-related database operations."""

    @staticmethod
    async def create_clip(
        db: AsyncSession,
        task_id: str,
        filename: str,
        file_path: str,
        start_time: str,
        end_time: str,
        duration: float,
        clip_text: str,
        relevance_score: float,
        reasoning: str,
        clip_order: int,
    ) -> str:
        """Create a new clip record and return its ID.

        Args:
            db: Database session.
            task_id: Parent task ID.
            filename: Clip filename.
            file_path: Full path to clip file.
            start_time: Clip start timestamp (MM:SS format).
            end_time: Clip end timestamp (MM:SS format).
            duration: Clip duration in seconds.
            clip_text: Transcript text for this clip.
            relevance_score: AI relevance score (0-1).
            reasoning: AI reasoning for clip selection.
            clip_order: Order index within the task.

        Returns:
            UUID string of the created clip.
        """
        clip_id = str(uuid.uuid4())
        await db.execute(
            text(
                """
                INSERT INTO generated_clips
                (id, task_id, filename, file_path, start_time, end_time, duration,
                 text, relevance_score, reasoning, clip_order)
                VALUES
                (:id, :task_id, :filename, :file_path, :start_time, :end_time, :duration,
                 :text, :relevance_score, :reasoning, :clip_order)
                RETURNING id
            """
            ),
            {
                "id": clip_id,
                "task_id": task_id,
                "filename": filename,
                "file_path": file_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "text": clip_text,
                "relevance_score": relevance_score,
                "reasoning": reasoning,
                "clip_order": clip_order,
            },
        )
        logger.debug(f"Created clip {clip_id} for task {task_id}")
        return clip_id

    @staticmethod
    async def get_clips_by_task(
        db: AsyncSession, task_id: str, backend_url: str = "http://localhost:8008"
    ) -> list[dict[str, Any]]:
        """
        Get all clips for a specific task, ordered by clip_order.

        Args:
            db: Database session
            task_id: Task ID to get clips for
            backend_url: Base URL of the backend server (for constructing full clip URLs)

        Returns:
            List of clip dictionaries with full video URLs
        """
        result = await db.execute(
            text(
                """
                SELECT id, filename, file_path, start_time, end_time, duration,
                       text, relevance_score, reasoning, clip_order, created_at
                FROM generated_clips
                WHERE task_id = :task_id
                ORDER BY clip_order ASC
            """
            ),
            {"task_id": task_id},
        )

        clips = [
            {
                "id": row.id,
                "filename": row.filename,
                "file_path": row.file_path,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration": row.duration,
                "text": row.text,
                "relevance_score": row.relevance_score,
                "reasoning": row.reasoning,
                "clip_order": row.clip_order,
                "created_at": parse_sqlite_datetime(row.created_at),
                "video_url": f"{backend_url}/clips/{row.filename}",
            }
            for row in result.fetchall()
        ]

        return clips

    @staticmethod
    async def get_clips_count(db: AsyncSession, task_id: str) -> int:
        """Get the count of clips for a task.

        Args:
            db: Database session.
            task_id: Task ID to count clips for.

        Returns:
            Number of clips associated with the task.
        """
        result = await db.execute(
            text(
                "SELECT COUNT(*) as count FROM generated_clips WHERE task_id = :task_id"
            ),
            {"task_id": task_id},
        )
        return int(count) if (count := result.scalar()) is not None else 0

    @staticmethod
    async def delete_clips_by_task(db: AsyncSession, task_id: str) -> int:
        """Delete all clips for a task.

        Args:
            db: Database session.
            task_id: Task ID whose clips should be deleted.

        Returns:
            Number of clips deleted.
        """
        result = await db.execute(
            text("DELETE FROM generated_clips WHERE task_id = :task_id"),
            {"task_id": task_id},
        )
        await db.commit()
        deleted_count = getattr(result, "rowcount", None) or 0
        logger.info(f"Deleted {deleted_count} clips for task {task_id}")
        return deleted_count

    @staticmethod
    async def delete_clip(db: AsyncSession, clip_id: str) -> None:
        """Delete a single clip by ID.

        Args:
            db: Database session.
            clip_id: Clip ID to delete.
        """
        await db.execute(
            text("DELETE FROM generated_clips WHERE id = :clip_id"),
            {"clip_id": clip_id},
        )
        await db.commit()
        logger.info(f"Deleted clip {clip_id}")


# end backend/src/repositories/clip_repository.py
