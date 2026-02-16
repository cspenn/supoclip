# start backend/src/repositories/source_repository.py
"""
Source repository - handles all database operations for video sources.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
import logging

logger = logging.getLogger(__name__)


class SourceRepository:
    """Repository for source-related database operations."""

    @staticmethod
    async def create_source(
        db: AsyncSession,
        source_type: str,
        title: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new source record and return its ID.

        Args:
            db: Database session.
            source_type: Source type ("youtube", "video_url", or "upload").
            title: Display title for the source.
            url: Optional source URL (not persisted in model).
            metadata: Optional metadata dictionary (not persisted in model).

        Returns:
            UUID string of the created source.
        """
        from ..models import Source

        source = Source()
        source.type = source_type
        source.title = title
        # Note: url and metadata are not stored in the Source model
        # They are handled separately in video processing services

        db.add(source)
        await db.flush()

        source_id = source.id
        logger.info(f"Created source {source_id}: {title} ({source_type})")
        return source_id

    @staticmethod
    async def get_source_by_id(
        db: AsyncSession, source_id: str
    ) -> dict[str, Any] | None:
        """Get source by ID.

        Args:
            db: Database session.
            source_id: Source ID to retrieve.

        Returns:
            Source dictionary, or None if not found.
        """
        from sqlalchemy import text

        result = await db.execute(
            text("SELECT * FROM sources WHERE id = :source_id"),
            {"source_id": source_id},
        )
        if not (row := result.fetchone()):
            return None

        return {
            "id": row.id,
            "type": row.type,
            "title": row.title,
            "url": getattr(row, "url", None),
            "metadata": getattr(row, "metadata", None),
            "created_at": row.created_at,
        }

    @staticmethod
    async def update_source_title(db: AsyncSession, source_id: str, title: str) -> None:
        """Update the title of a source.

        Args:
            db: Database session.
            source_id: Source ID to update.
            title: New title string.
        """
        from sqlalchemy import text

        await db.execute(
            text("UPDATE sources SET title = :title WHERE id = :source_id"),
            {"title": title, "source_id": source_id},
        )
        await db.commit()
        logger.info(f"Updated source {source_id} title to: {title}")


# end backend/src/repositories/source_repository.py
