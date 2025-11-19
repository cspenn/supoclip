# start backend/src/dependencies.py

"""FastAPI dependency injection functions."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Config
from .database import get_db
from .services.font_service import FontService

logger = logging.getLogger(__name__)

# Global font service instance
_font_service: Optional[FontService] = None


async def get_font_service() -> FontService:
    """Get or create font service instance."""
    global _font_service
    if _font_service is None:
        config = Config()
        _font_service = FontService(db_session=None, temp_dir=Path(config.temp_dir))
    return _font_service


def set_font_service(service: FontService) -> None:
    """Set the global font service instance."""
    global _font_service
    _font_service = service


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    """FastAPI dependency to extract and validate current user.

    Checks both 'X-User-ID' and 'user-id' header formats.
    Verifies user exists in database.

    Args:
        request: FastAPI request object
        db: Database session from dependency

    Returns:
        User ID string if valid

    Raises:
        HTTPException: 401 if user not authenticated or invalid
    """
    # Try multiple header formats for compatibility
    # Standard: X-User-ID (RFC 7230 compliant)
    # Alternative: user-id (lowercase hyphen)
    # Legacy: user_id (underscore - for backward compatibility)
    user_id = (
        request.headers.get("X-User-ID")
        or request.headers.get("user-id")
        or request.headers.get("user_id")
    )

    if not user_id or len(user_id.strip()) == 0:
        logger.warning("Authentication attempt with missing user ID")
        raise HTTPException(status_code=401, detail="User authentication required")

    # Verify user exists in database
    try:
        result = await db.execute(
            text("SELECT id FROM users WHERE id = :user_id LIMIT 1"),
            {"user_id": user_id},
        )
        user = result.fetchone()

        if not user:
            logger.warning(f"Authentication attempt for non-existent user: {user_id}")
            raise HTTPException(status_code=401, detail="User not found")
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
        raise HTTPException(
            status_code=500, detail="Authentication verification failed"
        )

    logger.info(f"User authenticated: {user_id}")
    return user_id


async def get_optional_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[str]:
    """Optional version of get_current_user.

    Returns None if user not authenticated instead of raising exception.
    Useful for endpoints that work with or without authentication.

    Args:
        request: FastAPI request object
        db: Database session from dependency

    Returns:
        User ID string if valid, None otherwise
    """
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


# end backend/src/dependencies.py
