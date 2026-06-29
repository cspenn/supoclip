# start src/database.py
"""Async SQLAlchemy database engine and session management.

The engine is initialized lazily on first use or via init_db().
This avoids module-level side effects that break tests and imports.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Re-exported so existing `from src.database import Base` callers keep working.
from src.db_base import Base

log = structlog.get_logger()

# Module-level state (lazily initialized)
_engine = None
_session_factory = None

__all__ = ["Base", "close_db", "get_engine", "get_session", "init_db"]


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

    # Import models here to ensure they're registered with Base before
    # create_all runs. A failure to import models is a real bug — let it
    # propagate rather than silently creating an empty schema.
    import src.models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)

    log.info("database.initialized")


def _add_missing_columns(connection: Connection) -> None:
    """Add any model columns missing from existing tables (additive migration).

    ``create_all`` only creates absent tables — it never alters an existing one.
    This project has no migration framework, so an additive column (e.g. a new
    nullable field) would otherwise be invisible on a pre-existing database and
    break inserts. For each mapped table that already exists, this issues an
    ``ALTER TABLE ... ADD COLUMN`` for every model column not yet present.

    Only safe for additive, nullable columns (SQLite cannot add a NOT NULL
    column without a default). Idempotent: freshly created tables already have
    every column, so nothing is altered.

    Args:
        connection: A synchronous SQLAlchemy connection (via ``run_sync``).
    """
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            col_type = column.type.compile(dialect=connection.dialect)
            connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
            log.info("database.column_added", table=table.name, column=column.name)


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
