# start src/database.py
"""Async SQLAlchemy database engine and session management.

The engine is initialized lazily on first use or via init_db().
This avoids module-level side effects that break tests and imports.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

log = structlog.get_logger()

# Module-level state (lazily initialized)
_engine = None
_session_factory = None


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_engine():
    """Return the async engine, creating it if necessary.

    Returns:
        The SQLAlchemy AsyncEngine instance.

    Raises:
        RuntimeError: If init_db() has not been called yet.
    """
    if _engine is None:
        msg = "Database not initialized. Call init_db() first."
        raise RuntimeError(msg)
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session as a context manager.

    Yields:
        An AsyncSession scoped to this context.

    Raises:
        RuntimeError: If init_db() has not been called yet.
    """
    if _session_factory is None:
        msg = "Database not initialized. Call init_db() first."
        raise RuntimeError(msg)
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(database_url: str) -> None:
    """Initialize the database engine and create all tables.

    This function is idempotent — safe to call multiple times.
    It creates the engine, session factory, and all ORM tables.

    Args:
        database_url: SQLAlchemy-compatible database URL.
            Example: 'sqlite+aiosqlite:///./supoclip.db'
    """
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        log.debug("database.already_initialized")
        return

    log.info("database.initializing", url=database_url)
    _engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    # Import models here to ensure they're registered with Base.
    # This is optional: if models haven't been written yet, skip gracefully.
    try:
        import src.models  # noqa: F401
    except ModuleNotFoundError:
        log.debug("database.models_not_found", note="Skipping model registration")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("database.initialized")


async def close_db() -> None:
    """Close the database engine and release connections.

    Call this during application shutdown.
    """
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("database.closed")
# end src/database.py
