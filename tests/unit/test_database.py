# start tests/unit/test_database.py
"""Unit tests for src/database.py — lazy async SQLAlchemy engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import src.database as db_module
from src.database import close_db, get_engine, get_session, init_db

IN_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def reset_db_state():
    """Reset module-level engine/session_factory between each test."""
    # Ensure clean state before test
    db_module._engine = None
    db_module._session_factory = None
    yield
    # Tear down after test
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


class TestGetEngineBeforeInit:
    """Tests for get_engine() before init_db() is called."""

    def test_raises_runtime_error_before_init(self) -> None:
        """get_engine() raises RuntimeError when database not initialized."""
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()


class TestGetSessionBeforeInit:
    """Tests for get_session() before init_db() is called."""

    async def test_raises_runtime_error_before_init(self) -> None:
        """get_session() raises RuntimeError when database not initialized."""
        with pytest.raises(RuntimeError, match="Database not initialized"):
            async with get_session():
                pass


class TestInitDb:
    """Tests for init_db() initialization behavior."""

    async def test_initializes_successfully_with_sqlite_memory(self) -> None:
        """init_db() succeeds with in-memory SQLite URL."""
        await init_db(IN_MEMORY_URL)
        engine = get_engine()
        assert engine is not None

    async def test_idempotent_when_called_twice(self) -> None:
        """init_db() called twice does not raise and returns same engine."""
        await init_db(IN_MEMORY_URL)
        engine_first = get_engine()
        await init_db(IN_MEMORY_URL)
        engine_second = get_engine()
        assert engine_first is engine_second

    async def test_init_db_propagates_models_import_error(self) -> None:
        """init_db() fails loudly when src.models cannot be imported (M-8)."""
        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

        def import_raise_for_models(name, *args, **kwargs):
            if name == "src.models":
                raise ModuleNotFoundError(name)
            return real_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=import_raise_for_models),
            pytest.raises(ModuleNotFoundError, match="src.models"),
        ):
            await init_db(IN_MEMORY_URL)

    async def test_get_engine_returns_engine_after_init(self) -> None:
        """get_engine() returns an engine instance after init_db()."""
        await init_db(IN_MEMORY_URL)
        engine = get_engine()
        assert engine is not None


class TestGetSessionAfterInit:
    """Tests for get_session() after init_db() is called."""

    async def test_yields_async_session(self) -> None:
        """get_session() yields an AsyncSession after init."""
        await init_db(IN_MEMORY_URL)
        async with get_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_session_is_active(self) -> None:
        """Session obtained from get_session() is active."""
        await init_db(IN_MEMORY_URL)
        async with get_session() as session:
            assert session.is_active

    async def test_get_session_rolls_back_and_reraises_on_exception(self) -> None:
        """get_session() rolls back the session and re-raises when an exception occurs."""
        await init_db(IN_MEMORY_URL)
        with pytest.raises(ValueError, match="deliberate test error"):
            async with get_session() as session:
                assert session.is_active
                raise ValueError("deliberate test error")


class TestCloseDb:
    """Tests for close_db() shutdown behavior."""

    async def test_close_db_after_init(self) -> None:
        """close_db() disposes engine and resets state after init."""
        await init_db(IN_MEMORY_URL)
        assert db_module._engine is not None
        await close_db()
        assert db_module._engine is None
        assert db_module._session_factory is None

    async def test_close_db_before_init_does_not_raise(self) -> None:
        """close_db() is a no-op when called before init_db()."""
        await close_db()  # Should not raise

    async def test_get_engine_raises_after_close(self) -> None:
        """get_engine() raises RuntimeError after close_db()."""
        await init_db(IN_MEMORY_URL)
        await close_db()
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()


class TestAdditiveColumnSync:
    """Tests for _add_missing_columns (additive schema migration)."""

    async def test_adds_column_to_stale_table(self, tmp_path: object) -> None:
        """A pre-existing table missing a model column gets it added; missing tables skipped."""
        from sqlalchemy.ext.asyncio import create_async_engine

        import src.models  # noqa: F401  (register models on Base)
        from src.database import _add_missing_columns

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/stale.db")
        try:
            async with engine.begin() as conn:
                # Older schema: generated_clips WITHOUT thumbnail_filename; the
                # other model tables (tasks, user_preferences) don't exist yet.
                await conn.exec_driver_sql(
                    "CREATE TABLE generated_clips ("
                    "id TEXT PRIMARY KEY, task_id TEXT, filename TEXT, start_time REAL, "
                    "end_time REAL, duration REAL, title TEXT, transcript_text TEXT, "
                    "score REAL, created_at TEXT)"
                )
                await conn.run_sync(_add_missing_columns)
                rows = (await conn.exec_driver_sql("PRAGMA table_info(generated_clips)")).fetchall()
            columns = {row[1] for row in rows}
        finally:
            await engine.dispose()

        assert "thumbnail_filename" in columns


# end tests/unit/test_database.py
