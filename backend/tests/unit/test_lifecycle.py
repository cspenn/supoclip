# start backend/tests/unit/test_lifecycle.py
"""Comprehensive tests for lifecycle.py to achieve 100% line coverage.

Covers:
- initialize_font_service: normal flow (load bundled fonts, spawn background task)
- _detect_system_fonts_background: success and error paths
- lifespan: full startup + shutdown, shutdown error handling
"""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from src.lifecycle import (
    initialize_font_service,
    _detect_system_fonts_background,
    lifespan,
)


# ---------------------------------------------------------------------------
# initialize_font_service
# ---------------------------------------------------------------------------


class TestInitializeFontService:
    @pytest.mark.asyncio
    async def test_normal_flow(self) -> None:
        """Loads bundled fonts, caches them, and starts background font detection."""
        mock_session = AsyncMock()
        mock_config = MagicMock()
        mock_config.temp_dir = "/tmp/test"

        mock_font_service = AsyncMock()
        mock_font_service.get_bundled_fonts = AsyncMock(
            return_value=[MagicMock(), MagicMock()]
        )
        mock_font_service.cache_fonts = AsyncMock()

        with patch("src.lifecycle.FontService", return_value=mock_font_service), \
             patch("src.lifecycle.set_font_service") as mock_set, \
             patch("src.lifecycle.asyncio.create_task") as mock_create_task:
            await initialize_font_service(mock_session, mock_config)

        mock_set.assert_called_once_with(mock_font_service)
        mock_font_service.get_bundled_fonts.assert_awaited_once()
        mock_font_service.cache_fonts.assert_awaited_once()
        mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# _detect_system_fonts_background
# ---------------------------------------------------------------------------


class TestDetectSystemFontsBackground:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Detects and caches system fonts successfully."""
        mock_service = AsyncMock()
        mock_service.detect_system_fonts = AsyncMock(
            return_value=[MagicMock(), MagicMock(), MagicMock()]
        )
        mock_service.cache_fonts = AsyncMock()

        await _detect_system_fonts_background(mock_service)

        mock_service.detect_system_fonts.assert_awaited_once()
        mock_service.cache_fonts.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Logs error when font detection fails."""
        mock_service = AsyncMock()
        mock_service.detect_system_fonts = AsyncMock(
            side_effect=RuntimeError("font detection failed")
        )

        with caplog.at_level(logging.ERROR):
            await _detect_system_fonts_background(mock_service)

        assert "font detection failed" in caplog.text


# ---------------------------------------------------------------------------
# lifespan
# ---------------------------------------------------------------------------


class TestLifespan:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """Full startup and shutdown cycle."""
        app = FastAPI()

        mock_config = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_queue = MagicMock()
        mock_queue.start_workers = AsyncMock()
        mock_queue.stop_workers = AsyncMock()

        with patch("src.lifecycle.Config", return_value=mock_config), \
             patch("src.lifecycle.init_db", new_callable=AsyncMock) as mock_init, \
             patch("src.lifecycle.AsyncSessionLocal", return_value=mock_session), \
             patch("src.lifecycle.initialize_font_service", new_callable=AsyncMock) as mock_font, \
             patch("src.lifecycle.get_job_queue", return_value=mock_queue), \
             patch("src.lifecycle.close_db", new_callable=AsyncMock) as mock_close:
            async with lifespan(app):
                pass  # app is "running"

        mock_init.assert_awaited_once()
        mock_font.assert_awaited_once()
        mock_queue.start_workers.assert_awaited_once()
        mock_queue.stop_workers.assert_awaited_once()
        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_worker_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Continues shutdown even if stopping workers raises an error."""
        app = FastAPI()

        mock_config = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_queue = MagicMock()
        mock_queue.start_workers = AsyncMock()
        mock_queue.stop_workers = AsyncMock(side_effect=RuntimeError("stop failed"))

        with patch("src.lifecycle.Config", return_value=mock_config), \
             patch("src.lifecycle.init_db", new_callable=AsyncMock), \
             patch("src.lifecycle.AsyncSessionLocal", return_value=mock_session), \
             patch("src.lifecycle.initialize_font_service", new_callable=AsyncMock), \
             patch("src.lifecycle.get_job_queue", return_value=mock_queue), \
             patch("src.lifecycle.close_db", new_callable=AsyncMock) as mock_close:
            with caplog.at_level(logging.ERROR):
                async with lifespan(app):
                    pass

        assert "stop failed" in caplog.text
        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_startup_error_still_shuts_down(self) -> None:
        """If startup fails, shutdown still happens (finally block)."""
        app = FastAPI()

        mock_config = MagicMock()

        with patch("src.lifecycle.Config", return_value=mock_config), \
             patch("src.lifecycle.init_db", new_callable=AsyncMock, side_effect=RuntimeError("db init failed")), \
             patch("src.lifecycle.close_db", new_callable=AsyncMock) as mock_close, \
             patch("src.lifecycle.get_job_queue") as mock_get_queue:
            # get_job_queue in finally block should still be called
            mock_queue = MagicMock()
            mock_queue.stop_workers = AsyncMock()
            mock_get_queue.return_value = mock_queue

            with pytest.raises(RuntimeError, match="db init failed"):
                async with lifespan(app):
                    pass

        mock_close.assert_awaited_once()


# end backend/tests/unit/test_lifecycle.py
