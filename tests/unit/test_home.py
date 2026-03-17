# start tests/unit/test_home.py
"""Unit tests for src/pages/home.py — NiceGUI home page.

Covers:
- _is_youtube_url: valid YouTube URLs, youtu.be short-links, non-YouTube strings
- _create_task: persists a Task row and returns its UUID (mock DB session)
- _start_processing: constructs ProcessingRequest and calls process_video
- render: smoke-test that render() completes without exceptions (mock NiceGUI + DB)
- on_start handler logic via direct unit testing of helpers
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pages.home import (
    _RESOLUTIONS,
    _create_task,
    _is_youtube_url,
    _start_processing,
)

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _is_youtube_url
# ---------------------------------------------------------------------------


class TestIsYoutubeUrl:
    """Tests for the YouTube URL detection helper."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=abc123",
            "https://youtu.be/dQw4w9WgXcQ",
            "  https://www.youtube.com/shorts/abc  ",
        ],
    )
    def test_recognises_youtube_urls(self, url: str) -> None:
        """YouTube and youtu.be URLs must return True.

        Args:
            url: URL string to test.
        """
        assert _is_youtube_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "/tmp/my_video.mp4",
            "https://vimeo.com/123456789",
            "https://example.com/video.mp4",
            "",
            "just some text",
        ],
    )
    def test_rejects_non_youtube(self, url: str) -> None:
        """Non-YouTube strings and local paths must return False.

        Args:
            url: URL string to test.
        """
        assert _is_youtube_url(url) is False


# ---------------------------------------------------------------------------
# _create_task
# ---------------------------------------------------------------------------


class TestCreateTask:
    """Tests for the Task DB creation helper."""

    @pytest.mark.asyncio
    async def test_creates_task_and_returns_id(self) -> None:
        """_create_task must persist a Task and return the UUID string."""
        from contextlib import asynccontextmanager

        fake_task = MagicMock()
        fake_task.id = "test-uuid-1234"

        fake_session = AsyncMock()
        fake_session.add = MagicMock()
        fake_session.flush = AsyncMock()
        fake_session.refresh = AsyncMock()

        @asynccontextmanager
        async def _mock_get_session():
            yield fake_session

        with (
            patch("src.pages.home.get_session", _mock_get_session),
            patch("src.pages.home.Task", return_value=fake_task),
        ):
            result = await _create_task(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"
            )

        assert result == "test-uuid-1234"
        fake_session.add.assert_called_once_with(fake_task)
        fake_session.flush.assert_awaited_once()
        fake_session.refresh.assert_awaited_once_with(fake_task)

    @pytest.mark.asyncio
    async def test_creates_upload_task(self) -> None:
        """_create_task must work for upload source_type as well."""
        from contextlib import asynccontextmanager

        fake_task = MagicMock()
        fake_task.id = "upload-uuid-5678"

        fake_session = AsyncMock()
        fake_session.add = MagicMock()
        fake_session.flush = AsyncMock()
        fake_session.refresh = AsyncMock()

        @asynccontextmanager
        async def _mock_get_session():
            yield fake_session

        with (
            patch("src.pages.home.get_session", _mock_get_session),
            patch("src.pages.home.Task", return_value=fake_task),
        ):
            result = await _create_task("/tmp/video.mp4", "upload")

        assert result == "upload-uuid-5678"


# ---------------------------------------------------------------------------
# _start_processing
# ---------------------------------------------------------------------------


class TestStartProcessing:
    """Tests for the background pipeline launcher."""

    @pytest.mark.asyncio
    async def test_calls_process_video_with_correct_request(self) -> None:
        """_start_processing must build ProcessingRequest and call process_video."""
        mock_process = AsyncMock()

        with patch("src.pages.home.process_video", mock_process):
            await _start_processing(
                task_id="abc-123",
                source="https://youtu.be/test",
                min_len=15,
                max_len=45,
                resolution="1080p",
            )

        mock_process.assert_awaited_once()
        call_args = mock_process.call_args
        request = call_args.args[0]

        assert request.task_id == "abc-123"
        assert request.source == "https://youtu.be/test"
        assert request.min_clip_length == 15
        assert request.max_clip_length == 45
        assert request.output_resolution == "1080p"

    @pytest.mark.asyncio
    async def test_passes_local_path_unchanged(self) -> None:
        """_start_processing must forward a local file path as the source.

        Args: (none — parametrized via class context)
        """
        mock_process = AsyncMock()
        local = "/tmp/my_video.mp4"

        with patch("src.pages.home.process_video", mock_process):
            await _start_processing(
                task_id="xyz-789",
                source=local,
                min_len=20,
                max_len=60,
                resolution="720p",
            )

        request = mock_process.call_args.args[0]
        assert request.source == local
        assert request.output_resolution == "720p"


# ---------------------------------------------------------------------------
# Render smoke test
# ---------------------------------------------------------------------------


class TestRender:
    """Smoke tests for the render() function."""

    @pytest.mark.asyncio
    async def test_render_does_not_raise(self) -> None:
        """render() must complete without raising when NiceGUI is mocked."""

        # Minimal stubs that satisfy the ui.* calls made inside render().
        element_stub = MagicMock()
        element_stub.classes = MagicMock(return_value=element_stub)
        element_stub.props = MagicMock(return_value=element_stub)
        element_stub.on = MagicMock(return_value=element_stub)
        element_stub.value = "1080p"

        # Context manager stubs (for ui.column, ui.row, etc.)
        cm_stub = MagicMock()
        cm_stub.__enter__ = MagicMock(return_value=element_stub)
        cm_stub.__exit__ = MagicMock(return_value=False)
        cm_stub.classes = MagicMock(return_value=cm_stub)
        cm_stub.props = MagicMock(return_value=cm_stub)
        cm_stub.on = MagicMock(return_value=cm_stub)

        ui_mock = MagicMock()
        # column/row/etc. must return a context manager
        for attr in ("column", "row"):
            getattr(ui_mock, attr).return_value = cm_stub
        # Non-context-manager widgets return element_stub
        for attr in (
            "label",
            "input",
            "slider",
            "select",
            "upload",
            "button",
            "separator",
            "link",
            "notify",
        ):
            getattr(ui_mock, attr).return_value = element_stub

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

        # If we reach here the render() function completed without error.
        assert True


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------


def test_resolutions_list_contains_expected_options() -> None:
    """_RESOLUTIONS must contain both 720p and 1080p."""
    assert "720p" in _RESOLUTIONS
    assert "1080p" in _RESOLUTIONS
# end tests/unit/test_home.py
