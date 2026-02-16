# start backend/src/repositories/task_repository.py
"""
Task repository - handles all database operations for tasks.
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
    try:
        return datetime.fromisoformat(dt_value)
    except ValueError as e:
        logger.warning(f"Failed to parse datetime '{dt_value}': {e}")
        return None


class TaskRepository:
    """Repository for task-related database operations."""

    @staticmethod
    async def create_task(
        db: AsyncSession,
        user_id: str,
        source_id: str,
        status: str = "processing",
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ) -> str:
        """Create a new task and return its ID.

        Args:
            db: Database session.
            user_id: Owner user ID.
            source_id: Associated source ID.
            status: Initial task status.
            font_family: Font family for subtitles.
            font_size: Font size in pixels.
            font_color: Font color hex code.

        Returns:
            UUID string of the created task.
        """
        task_id = str(uuid.uuid4())
        await db.execute(
            text(
                """
                INSERT INTO tasks (id, user_id, source_id, status, font_family, font_size, font_color)
                VALUES (:id, :user_id, :source_id, :status, :font_family, :font_size, :font_color)
                RETURNING id
            """
            ),
            {
                "id": task_id,
                "user_id": user_id,
                "source_id": source_id,
                "status": status,
                "font_family": font_family,
                "font_size": font_size,
                "font_color": font_color,
            },
        )
        await db.commit()
        logger.info(f"Created task {task_id} for user {user_id}")
        return task_id

    @staticmethod
    async def get_task_by_id(db: AsyncSession, task_id: str) -> dict[str, Any] | None:
        """Get task by ID with source information.

        Args:
            db: Database session.
            task_id: Task ID to retrieve.

        Returns:
            Task dictionary with source details, or None if not found.
        """
        result = await db.execute(
            text(
                """
                SELECT t.*, s.title as source_title, s.type as source_type
                FROM tasks t
                LEFT JOIN sources s ON t.source_id = s.id
                WHERE t.id = :task_id
            """
            ),
            {"task_id": task_id},
        )
        if not (row := result.fetchone()):
            return None

        return {
            "id": row.id,
            "user_id": row.user_id,
            "source_id": row.source_id,
            "source_title": row.source_title,
            "source_type": row.source_type,
            "status": row.status,
            "progress": getattr(row, "progress", None),
            "progress_message": getattr(row, "progress_message", None),
            "generated_clips_ids": row.generated_clips_ids,
            "font_family": row.font_family,
            "font_size": row.font_size,
            "font_color": row.font_color,
            "created_at": parse_sqlite_datetime(row.created_at),
            "updated_at": parse_sqlite_datetime(row.updated_at),
        }

    @staticmethod
    async def update_task_status(
        db: AsyncSession,
        task_id: str,
        status: str,
        progress: int | None = None,
        progress_message: str | None = None,
    ) -> None:
        """Update task status and optional progress.

        Args:
            db: Database session.
            task_id: Task ID to update.
            status: New status value.
            progress: Optional progress percentage (0-100).
            progress_message: Optional progress message string.
        """
        params = {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "progress_message": progress_message,
        }

        # Build dynamic query based on what's provided
        set_parts = ["status = :status"]

        if progress is not None:
            set_parts.append("progress = :progress")

        if progress_message is not None:
            set_parts.append("progress_message = :progress_message")

        # Build complete query (no comma before WHERE)
        query = f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = :task_id"

        await db.execute(text(query), params)
        await db.commit()
        logger.info(
            f"Updated task {task_id} status to {status}"
            + (f" (progress: {progress}%)" if progress else "")
        )

    @staticmethod
    async def update_task_clips(
        db: AsyncSession, task_id: str, clip_ids: list[str]
    ) -> None:
        """Update task with generated clip IDs.

        Args:
            db: Database session.
            task_id: Task ID to update.
            clip_ids: List of clip ID strings to store as JSON.
        """
        import json

        # SQLite requires JSON column values to be serialized to JSON strings
        clip_ids_json = json.dumps(clip_ids)
        await db.execute(
            text(
                "UPDATE tasks SET generated_clips_ids = :clip_ids WHERE id = :task_id"
            ),
            {"clip_ids": clip_ids_json, "task_id": task_id},
        )
        await db.commit()
        logger.info(f"Updated task {task_id} with {len(clip_ids)} clips")

    @staticmethod
    async def get_user_tasks(
        db: AsyncSession, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get all tasks for a user ordered by creation date descending.

        Args:
            db: Database session.
            user_id: User ID to retrieve tasks for.
            limit: Maximum number of tasks to return.

        Returns:
            List of task dictionaries with source info and clip counts.
        """
        result = await db.execute(
            text(
                """
                SELECT t.*, s.title as source_title, s.type as source_type,
                       (SELECT COUNT(*) FROM generated_clips WHERE task_id = t.id) as clips_count
                FROM tasks t
                LEFT JOIN sources s ON t.source_id = s.id
                WHERE t.user_id = :user_id
                ORDER BY t.created_at DESC
                LIMIT :limit
            """
            ),
            {"user_id": user_id, "limit": limit},
        )

        tasks = [
            {
                "id": row.id,
                "user_id": row.user_id,
                "source_id": row.source_id,
                "source_title": row.source_title,
                "source_type": row.source_type,
                "status": row.status,
                "clips_count": row.clips_count,
                "created_at": parse_sqlite_datetime(row.created_at),
                "updated_at": parse_sqlite_datetime(row.updated_at),
            }
            for row in result.fetchall()
        ]

        return tasks

    @staticmethod
    async def user_exists(db: AsyncSession, user_id: str) -> bool:
        """Check if a user exists in the database.

        Args:
            db: Database session.
            user_id: User ID to check.

        Returns:
            True if user exists, False otherwise.
        """
        result = await db.execute(
            text("SELECT 1 FROM users WHERE id = :user_id"), {"user_id": user_id}
        )
        return result.fetchone() is not None

    @staticmethod
    async def delete_task(db: AsyncSession, task_id: str) -> None:
        """Delete a task by ID.

        Args:
            db: Database session.
            task_id: Task ID to delete.
        """
        await db.execute(
            text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id}
        )
        await db.commit()
        logger.info(f"Deleted task {task_id}")


# end backend/src/repositories/task_repository.py
