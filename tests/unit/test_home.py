# start tests/unit/test_home.py
"""Unit tests for src/pages/home.py — NiceGUI home page.

Covers:
- _is_youtube_url: valid YouTube URLs, youtu.be short-links, non-YouTube strings
- _create_task: persists a Task row and returns its UUID (mock DB session)
- _start_processing: constructs ProcessingRequest and calls process_video
- render: smoke-test that render() completes without exceptions (mock NiceGUI + DB)
- handle_upload closure: no-content error path, readable content, raw bytes
- on_start closure: no-input error, min>=max error, task-creation failure, success,
  local file path
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
        async def _mock_get_session():  # type: ignore[return]
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
        async def _mock_get_session():  # type: ignore[return]
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
        element_stub = MagicMock()
        element_stub.classes = MagicMock(return_value=element_stub)
        element_stub.props = MagicMock(return_value=element_stub)
        element_stub.on = MagicMock(return_value=element_stub)
        element_stub.value = "1080p"

        cm_stub = MagicMock()
        cm_stub.__enter__ = MagicMock(return_value=element_stub)
        cm_stub.__exit__ = MagicMock(return_value=False)
        cm_stub.classes = MagicMock(return_value=cm_stub)
        cm_stub.props = MagicMock(return_value=cm_stub)
        cm_stub.on = MagicMock(return_value=cm_stub)

        ui_mock = MagicMock()
        for attr in ("column", "row"):
            getattr(ui_mock, attr).return_value = cm_stub
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

        assert True


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------


def test_resolutions_list_contains_expected_options() -> None:
    """_RESOLUTIONS must contain both 720p and 1080p."""
    assert "720p" in _RESOLUTIONS
    assert "1080p" in _RESOLUTIONS


# ---------------------------------------------------------------------------
# Helpers shared by handle_upload and on_start closure tests
# ---------------------------------------------------------------------------


def _make_element_stub() -> MagicMock:
    """Return a self-chaining NiceGUI element stub.

    Returns:
        A MagicMock with fluent API stubs for classes, props, and on.
    """
    stub = MagicMock()
    stub.classes.return_value = stub
    stub.props.return_value = stub
    stub.on.return_value = stub
    return stub


def _make_cm_stub() -> MagicMock:
    """Return a context-manager NiceGUI element stub.

    Returns:
        A MagicMock usable as a ``with`` statement target.
    """
    stub = MagicMock()
    stub.__enter__ = MagicMock(return_value=stub)
    stub.__exit__ = MagicMock(return_value=False)
    stub.classes.return_value = stub
    stub.props.return_value = stub
    stub.on.return_value = stub
    return stub


def _build_full_ui_mock(
    *,
    url_value: str = "",
    min_value: int = 10,
    max_value: int = 45,
    resolution_value: str = "1080p",
) -> tuple[MagicMock, dict[str, list]]:
    """Build a ui mock capturing on_upload and on_click callbacks from render().

    Args:
        url_value: Value to set on the URL input stub.
        min_value: Value to set on the min-length slider stub.
        max_value: Value to set on the max-length slider stub.
        resolution_value: Value to set on the resolution select stub.

    Returns:
        A 2-tuple of (ui_mock, callbacks) where callbacks is a dict with keys
        ``"upload"`` and ``"button"`` holding lists of captured callables.
    """
    callbacks: dict[str, list] = {"upload": [], "button": []}

    element = _make_element_stub()
    cm = _make_cm_stub()

    url_stub = _make_element_stub()
    url_stub.value = url_value

    min_stub = _make_element_stub()
    min_stub.value = min_value
    max_stub = _make_element_stub()
    max_stub.value = max_value
    slider_call_count = {"n": 0}

    def _slider_factory(*args: object, **kwargs: object) -> MagicMock:
        slider_call_count["n"] += 1
        return min_stub if slider_call_count["n"] == 1 else max_stub

    res_stub = _make_element_stub()
    res_stub.value = resolution_value

    def _select_factory(*args: object, **kwargs: object) -> MagicMock:
        return res_stub

    def _input_factory(*args: object, **kwargs: object) -> MagicMock:
        return url_stub

    def _upload_factory(*args: object, **kwargs: object) -> MagicMock:
        if "on_upload" in kwargs:
            callbacks["upload"].append(kwargs["on_upload"])
        return element

    def _button_factory(*args: object, **kwargs: object) -> MagicMock:
        if "on_click" in kwargs:
            callbacks["button"].append(kwargs["on_click"])
        return element

    ui_mock = MagicMock()
    ui_mock.column.return_value = cm
    ui_mock.row.return_value = cm
    ui_mock.input = _input_factory
    ui_mock.slider = _slider_factory
    ui_mock.select = _select_factory
    ui_mock.upload = _upload_factory
    ui_mock.button = _button_factory
    for attr in ("label", "separator", "link"):
        getattr(ui_mock, attr).return_value = element
    ui_mock.notify = MagicMock()
    ui_mock.navigate = MagicMock()

    return ui_mock, callbacks


# ---------------------------------------------------------------------------
# handle_upload closure (lines 145-155)
# ---------------------------------------------------------------------------


class TestHandleUpload:
    """Tests for the handle_upload closure defined inside render()."""

    @pytest.mark.asyncio
    async def test_handle_upload_with_no_content_notifies_error(self) -> None:
        """handle_upload must call ui.notify with color=negative when content is None."""
        ui_mock, callbacks = _build_full_ui_mock()

        # Patch must remain active when the callback runs so the closure resolves
        # ui.notify to ui_mock.notify rather than the conftest stub.
        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            assert len(callbacks["upload"]) == 1, "ui.upload must capture on_upload"
            handle_upload = callbacks["upload"][0]

            class _NoContentEvent:
                name = "test.mp4"

            handle_upload(_NoContentEvent())

        ui_mock.notify.assert_called_with("Upload failed: no content received.", color="negative")

    @pytest.mark.asyncio
    async def test_handle_upload_with_readable_content_saves_file(self) -> None:
        """handle_upload must write readable content to disk and notify on success."""
        ui_mock, callbacks = _build_full_ui_mock()

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            handle_upload = callbacks["upload"][0]
            fake_content = MagicMock()
            fake_content.read.return_value = b"fake video bytes"

            class _Event:
                name = "clip.mp4"
                content = fake_content

            mock_path_instance = MagicMock()
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_path_instance)

            with patch("src.pages.home.Path", return_value=mock_path_instance):
                handle_upload(_Event())

        mock_path_instance.write_bytes.assert_called_once_with(b"fake video bytes")
        ui_mock.notify.assert_called_with("File ready: clip.mp4", color="positive")

    @pytest.mark.asyncio
    async def test_handle_upload_with_bytes_content_saves_file(self) -> None:
        """handle_upload must write raw bytes content (no .read()) directly."""
        ui_mock, callbacks = _build_full_ui_mock()

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            handle_upload = callbacks["upload"][0]

            class _Event:
                name = "raw.mp4"
                content = b"raw bytes"

            mock_path_instance = MagicMock()
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_path_instance)

            with patch("src.pages.home.Path", return_value=mock_path_instance):
                handle_upload(_Event())

        mock_path_instance.write_bytes.assert_called_once_with(b"raw bytes")
        ui_mock.notify.assert_called_with("File ready: raw.mp4", color="positive")


# ---------------------------------------------------------------------------
# on_start closure (lines 213-256)
# ---------------------------------------------------------------------------


class TestOnStart:
    """Tests for the on_start async closure defined inside render()."""

    @pytest.mark.asyncio
    async def test_on_start_no_input_shows_error(self) -> None:
        """on_start must notify with negative color when no URL or file is given."""
        ui_mock, callbacks = _build_full_ui_mock(url_value="")

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            assert len(callbacks["button"]) == 1
            on_start = callbacks["button"][0]
            await on_start()

        ui_mock.notify.assert_called_with(
            "Please enter a YouTube URL or upload a video file.",
            color="negative",
        )

    @pytest.mark.asyncio
    async def test_on_start_min_gte_max_shows_error(self) -> None:
        """on_start must notify when min clip length >= max clip length."""
        ui_mock, callbacks = _build_full_ui_mock(
            url_value="https://www.youtube.com/watch?v=abc",
            min_value=45,
            max_value=30,
        )

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            on_start = callbacks["button"][0]
            await on_start()

        ui_mock.notify.assert_called_with(
            "Min clip length must be less than max clip length.",
            color="negative",
        )

    @pytest.mark.asyncio
    async def test_on_start_task_creation_failure_shows_error(self) -> None:
        """on_start must show error notification when _create_task raises."""
        ui_mock, callbacks = _build_full_ui_mock(
            url_value="https://www.youtube.com/watch?v=abc",
            min_value=10,
            max_value=45,
        )

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            on_start = callbacks["button"][0]

            with patch("src.pages.home._create_task", AsyncMock(side_effect=RuntimeError("DB error"))):
                await on_start()

        notify_calls = [str(c) for c in ui_mock.notify.call_args_list]
        assert any("Failed to create task" in c for c in notify_calls)

    @pytest.mark.asyncio
    async def test_on_start_success_creates_task_and_navigates(self) -> None:
        """on_start must create task, fire background job, and navigate to task page."""
        ui_mock, callbacks = _build_full_ui_mock(
            url_value="https://www.youtube.com/watch?v=abc",
            min_value=10,
            max_value=45,
            resolution_value="720p",
        )

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            on_start = callbacks["button"][0]
            mock_create = AsyncMock(return_value="task-id-9999")
            mock_start = AsyncMock()

            with (
                patch("src.pages.home._create_task", mock_create),
                patch("src.pages.home._start_processing", mock_start),
                patch("src.pages.home.asyncio.create_task", side_effect=lambda c: c.close()) as mock_create_task,
            ):
                await on_start()

        mock_create.assert_awaited_once()
        mock_create_task.assert_called_once()
        ui_mock.notify.assert_called_with("Processing started!", color="positive")
        ui_mock.navigate.to.assert_called_with("/task/task-id-9999")

    @pytest.mark.asyncio
    async def test_on_start_local_path_used_when_no_url(self) -> None:
        """on_start must use the uploaded local path when URL input is empty."""
        ui_mock, callbacks = _build_full_ui_mock(url_value="", min_value=10, max_value=45)

        with patch("src.pages.home.ui", ui_mock):
            from src.pages.home import render

            await render()

            # Seed uploaded_path by calling handle_upload inside the patch scope.
            assert len(callbacks["upload"]) == 1
            handle_upload = callbacks["upload"][0]

            class _UploadEvent:
                name = "local.mp4"
                content = b"bytes"

            mock_path_instance = MagicMock()
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_path_instance)
            mock_path_instance.__str__ = MagicMock(return_value="/tmp/local.mp4")

            with patch("src.pages.home.Path", return_value=mock_path_instance):
                handle_upload(_UploadEvent())

            on_start = callbacks["button"][0]
            mock_create = AsyncMock(return_value="local-task-id")

            with (
                patch("src.pages.home._create_task", mock_create),
                patch("src.pages.home._start_processing", AsyncMock()),
                patch("src.pages.home.asyncio.create_task", side_effect=lambda c: c.close()),
            ):
                await on_start()

        # source_type must be "upload" for a local file with no URL
        create_call_args = mock_create.call_args
        assert create_call_args.args[1] == "upload"
# end tests/unit/test_home.py
