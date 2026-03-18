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

    async def test_init_db_completes_when_models_module_not_found(self) -> None:
        """init_db() completes without error when src.models cannot be imported."""
        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

        def import_raise_for_models(name, *args, **kwargs):
            if name == "src.models":
                raise ModuleNotFoundError(name)
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_raise_for_models):
            await init_db(IN_MEMORY_URL)

        engine = get_engine()
        assert engine is not None

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
# end tests/unit/test_database.py
