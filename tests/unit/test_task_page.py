# start tests/unit/test_task_page.py
"""Unit tests for src/pages/task.py.

All NiceGUI UI calls and database sessions are mocked so the tests run
without a real event loop, browser, or database.

The ``nicegui`` stub is registered by ``tests/unit/conftest.py`` before
collection so that ``src.pages.task`` can be imported.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: build ORM instances without a live DB session
# ---------------------------------------------------------------------------


def _make_task(
    *,
    status: str = "completed",
    progress: int = 100,
    error_message: str | None = None,
    progress_message: str | None = None,
) -> MagicMock:
    """Build a MagicMock that behaves like a Task ORM instance.

    Using ``MagicMock`` rather than ``Task.__new__(Task)`` avoids triggering
    SQLAlchemy's ORM instrumentation, which requires an active mapper context.

    Args:
        status: Task status string.
        progress: Integer 0-100.
        error_message: Optional error text (populated when status='failed').
        progress_message: Optional human-readable progress text.

    Returns:
        A :class:`~unittest.mock.MagicMock` with Task-shaped attributes.
    """
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.source_url = "https://youtu.be/test_video"
    task.source_type = "youtube"
    task.status = status
    task.progress = progress
    task.progress_message = progress_message
    task.title = None
    task.settings_json = None
    task.error_message = error_message
    task.created_at = datetime.now(UTC)
    task.updated_at = datetime.now(UTC)
    return task


def _make_clip(task_id: str, *, index: int = 1) -> MagicMock:
    """Build a MagicMock that behaves like a GeneratedClip ORM instance.

    Using ``MagicMock`` avoids SQLAlchemy ORM instrumentation issues when
    creating instances outside a live session context.

    Args:
        task_id: Parent task UUID.
        index: Differentiator used to vary filenames and timing.

    Returns:
        A :class:`~unittest.mock.MagicMock` with GeneratedClip-shaped attributes.
    """
    clip = MagicMock()
    clip.id = str(uuid.uuid4())
    clip.task_id = task_id
    clip.filename = f"clip_{index:03d}.mp4"
    clip.start_time = float(index * 10)
    clip.end_time = float(index * 10 + 25)
    clip.duration = 25.0
    clip.title = f"Clip {index}"
    clip.transcript_text = f"Transcript for clip {index}."
    clip.score = 0.85
    clip.created_at = datetime.now(UTC)
    return clip


# ---------------------------------------------------------------------------
# Mock session factory helpers
# ---------------------------------------------------------------------------


def _mock_session(task: MagicMock | None, clips: list[MagicMock] | None = None):
    """Return an async context-manager mock that yields a DB session stub.

    The yielded session supports:

    * ``session.get(Model, pk)`` → returns *task* for Task queries, ``None``
      for unknown PKs
    * ``session.execute(stmt)`` → returns a result whose ``.scalars().all()``
      gives *clips*

    Args:
        task: The task mock to return from ``session.get``.
        clips: List of clip mocks to return from ``session.execute``.

    Returns:
        A :class:`~unittest.mock.MagicMock` configured as an async context
        manager.
    """
    clips = clips or []

    session = AsyncMock()
    session.get = AsyncMock(return_value=task)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = clips
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Fixture: build a per-test ui stub and patch it into the page module
# ---------------------------------------------------------------------------


def _build_ui_stub() -> MagicMock:
    """Construct a NiceGUI ``ui`` stub with tracking mocks.

    Returns:
        A :class:`~unittest.mock.MagicMock` whose attributes simulate the
        NiceGUI components used in ``src/pages/task.py``.
    """
    stub = MagicMock()

    # Widget factories return a self-chaining mock usable as a context manager.
    def _widget(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        m = MagicMock()
        m.classes.return_value = m
        m.props.return_value = m
        m.set_visibility.return_value = None
        m.clear.return_value = None
        m.text = ""
        m.value = 0.0
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        return m

    for name in (
        "label",
        "link",
        "button",
        "badge",
        "video",
        "card",
        "row",
        "column",
        "grid",
        "expansion",
        "linear_progress",
    ):
        getattr(stub, name).side_effect = _widget

    stub.download = MagicMock()

    # timer: track call count and capture arguments
    timer_instances: list[MagicMock] = []

    def _timer(interval=1.0, callback=None, **kwargs):  # noqa: ANN001, ANN002, ANN003
        t = MagicMock()
        t.active = True
        t._interval = interval
        t._callback = callback
        timer_instances.append(t)
        return t

    stub.timer.side_effect = _timer
    stub._timer_instances = timer_instances  # type: ignore[attr-defined]

    return stub


@pytest.fixture()
def ui_stub():
    """Provide a test-scoped NiceGUI ``ui`` stub patched into the page module.

    Yields:
        The stub injected as ``src.pages.task.ui``.
    """
    stub = _build_ui_stub()
    with patch("src.pages.task.ui", stub):
        yield stub


# ---------------------------------------------------------------------------
# Tests: completed task
# ---------------------------------------------------------------------------


class TestRenderCompleted:
    """render() with a completed task renders the clip grid without a timer."""

    @pytest.mark.asyncio
    async def test_no_timer_created(self, ui_stub: MagicMock) -> None:
        """A polling timer must not be created when the task is already done."""
        task = _make_task(status="completed", progress=100)
        clips = [_make_clip(task.id, index=i) for i in range(1, 4)]
        session_ctx = _mock_session(task, clips)

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        assert ui_stub.timer.call_count == 0

    @pytest.mark.asyncio
    async def test_video_rendered_per_clip(self, ui_stub: MagicMock) -> None:
        """ui.video must be called once for each clip returned by the DB."""
        task = _make_task(status="completed", progress=100)
        clips = [_make_clip(task.id, index=i) for i in range(1, 4)]
        session_ctx = _mock_session(task, clips)

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        assert ui_stub.video.call_count == len(clips)

    @pytest.mark.asyncio
    async def test_progress_section_hidden(self, ui_stub: MagicMock) -> None:
        """set_visibility is called at least once on a column widget.

        The progress section column calls set_visibility(False) when the task
        is already complete.  We verify that set_visibility was called on one
        of the column instances returned by ui.column during render().
        """
        task = _make_task(status="completed", progress=100)
        session_ctx = _mock_session(task, [])

        column_instances: list[MagicMock] = []
        original_side_effect = ui_stub.column.side_effect

        def _tracking_col(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            if original_side_effect:
                m = original_side_effect(*args, **kwargs)
            else:
                m = MagicMock()
            m.classes.return_value = m
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            column_instances.append(m)
            return m

        ui_stub.column.side_effect = _tracking_col

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        # At least one column must have had set_visibility called on it.
        set_vis_calls_found = any(
            m.set_visibility.called for m in column_instances
        )
        assert set_vis_calls_found


# ---------------------------------------------------------------------------
# Tests: processing / pending task
# ---------------------------------------------------------------------------


class TestRenderProcessing:
    """render() with an active task creates a 1-second polling timer."""

    @pytest.mark.asyncio
    async def test_timer_created_for_processing(self, ui_stub: MagicMock) -> None:
        """A ui.timer(1.0, ...) is created when status is 'processing'."""
        task = _make_task(
            status="processing",
            progress=40,
            progress_message="Transcribing audio…",
        )
        session_ctx = _mock_session(task, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        assert ui_stub.timer.call_count >= 1
        interval = ui_stub.timer.call_args[0][0]
        assert interval == 1.0

    @pytest.mark.asyncio
    async def test_timer_created_for_pending(self, ui_stub: MagicMock) -> None:
        """A ui.timer is also created when status is 'pending'."""
        task = _make_task(status="pending", progress=0)
        session_ctx = _mock_session(task, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        assert ui_stub.timer.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: failed task
# ---------------------------------------------------------------------------


class TestRenderFailed:
    """render() with a failed task shows the error banner."""

    @pytest.mark.asyncio
    async def test_no_timer_for_failed(self, ui_stub: MagicMock) -> None:
        """No polling timer is created for a task that has already failed."""
        task = _make_task(
            status="failed",
            progress=30,
            error_message="ffmpeg segfault: exit code 139",
        )
        session_ctx = _mock_session(task, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        assert ui_stub.timer.call_count == 0

    @pytest.mark.asyncio
    async def test_error_card_made_visible(self, ui_stub: MagicMock) -> None:
        """set_visibility is called on at least one card widget for a failed task.

        The error card calls set_visibility(True) when the task status is
        'failed'.  We verify that set_visibility was called on one of the card
        instances created during render().
        """
        task = _make_task(
            status="failed",
            progress=30,
            error_message="Download error",
        )
        session_ctx = _mock_session(task, [])

        card_instances: list[MagicMock] = []
        original_side_effect = ui_stub.card.side_effect

        def _tracking_card(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            if original_side_effect:
                m = original_side_effect(*args, **kwargs)
            else:
                m = MagicMock()
            m.classes.return_value = m
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            card_instances.append(m)
            return m

        ui_stub.card.side_effect = _tracking_card

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render(task.id)

        # At least one card must have had set_visibility called on it.
        set_vis_calls_found = any(
            m.set_visibility.called for m in card_instances
        )
        assert set_vis_calls_found


# ---------------------------------------------------------------------------
# Tests: task not found
# ---------------------------------------------------------------------------


class TestRenderNotFound:
    """render() with a non-existent task_id shows a graceful error message."""

    @pytest.mark.asyncio
    async def test_returns_without_raising(self, ui_stub: MagicMock) -> None:
        """render() must not raise for a missing task_id."""
        session_ctx = _mock_session(None, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            # Must complete without raising
            await render("nonexistent-task-id-0000")

    @pytest.mark.asyncio
    async def test_no_timer_for_missing_task(self, ui_stub: MagicMock) -> None:
        """No polling timer is created when the task does not exist."""
        session_ctx = _mock_session(None, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render("missing-task-id")

        assert ui_stub.timer.call_count == 0

    @pytest.mark.asyncio
    async def test_warning_card_rendered(self, ui_stub: MagicMock) -> None:
        """At least one ui.card is rendered for the not-found warning."""
        session_ctx = _mock_session(None, [])

        with patch("src.pages.task.get_session", return_value=session_ctx):
            from src.pages.task import render
            await render("missing-task-id-2")

        assert ui_stub.card.call_count >= 1


# ---------------------------------------------------------------------------
# Unit tests for pure helper functions
# ---------------------------------------------------------------------------


class TestTruncate:
    """Tests for the _truncate helper."""

    def test_short_string_unchanged(self) -> None:
        """Strings within the limit are returned unchanged."""
        from src.pages.task import _truncate

        assert _truncate("hello", max_len=10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        """A string exactly at the limit is returned unchanged."""
        from src.pages.task import _truncate

        s = "a" * 10
        assert _truncate(s, max_len=10) == s

    def test_long_string_truncated_with_ellipsis(self) -> None:
        """Strings over the limit are truncated and end with '…'."""
        from src.pages.task import _truncate

        result = _truncate("a" * 20, max_len=10)
        assert result.endswith("…")
        assert len(result) == 10

    def test_default_max_len_is_60(self) -> None:
        """Default max_len is _MAX_URL_DISPLAY_LEN (60 characters)."""
        from src.pages.task import _MAX_URL_DISPLAY_LEN, _truncate

        assert _MAX_URL_DISPLAY_LEN == 60
        long_url = "https://youtu.be/" + "x" * 60
        result = _truncate(long_url)
        assert len(result) == 60
        assert result.endswith("…")


class TestFormatSeconds:
    """Tests for the _format_seconds helper."""

    def test_zero(self) -> None:
        """Zero seconds formats as '00:00'."""
        from src.pages.task import _format_seconds

        assert _format_seconds(0.0) == "00:00"

    def test_under_one_minute(self) -> None:
        """45 seconds formats as '00:45'."""
        from src.pages.task import _format_seconds

        assert _format_seconds(45.0) == "00:45"

    def test_over_one_minute(self) -> None:
        """67 seconds formats as '01:07'."""
        from src.pages.task import _format_seconds

        assert _format_seconds(67.0) == "01:07"

    def test_fractional_seconds_truncated(self) -> None:
        """Fractional seconds are truncated to whole seconds."""
        from src.pages.task import _format_seconds

        assert _format_seconds(59.9) == "00:59"


class TestScoreColor:
    """Tests for the _score_color helper."""

    def test_none_score_returns_gray_class(self) -> None:
        """None score returns a gray Tailwind class."""
        from src.pages.task import _score_color

        assert "gray" in _score_color(None)

    def test_high_score_returns_green(self) -> None:
        """Score >= 0.8 returns a green class."""
        from src.pages.task import _score_color

        assert "green" in _score_color(0.95)
        assert "green" in _score_color(0.8)

    def test_mid_score_returns_yellow(self) -> None:
        """Score in [0.6, 0.8) returns a yellow class."""
        from src.pages.task import _score_color

        assert "yellow" in _score_color(0.7)
        assert "yellow" in _score_color(0.6)

    def test_low_score_returns_red(self) -> None:
        """Score < 0.6 returns a red class."""
        from src.pages.task import _score_color

        assert "red" in _score_color(0.5)
        assert "red" in _score_color(0.0)



# ---------------------------------------------------------------------------
# Helpers for timer-callback and _show_clips tests
# ---------------------------------------------------------------------------


def _make_session_ctx(
    task: "MagicMock | None",
    clips: "list[MagicMock] | None" = None,
) -> "MagicMock":
    clips = clips or []
    scalars_m = MagicMock()
    scalars_m.all.return_value = clips
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars_m
    session = AsyncMock()
    session.get = AsyncMock(return_value=task)
    session.execute = AsyncMock(return_value=exec_result)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_session_factory(*contexts: "MagicMock") -> object:
    ctx_list = list(contexts)
    idx_d = {"i": 0}
    fallback = ctx_list[-1] if ctx_list else MagicMock()

    def _factory() -> "MagicMock":
        i = idx_d["i"]
        idx_d["i"] += 1
        return ctx_list[i] if i < len(ctx_list) else fallback

    return _factory


# ---------------------------------------------------------------------------
# Tests: _refresh() timer callback (lines 232-260)
# ---------------------------------------------------------------------------


class TestRefreshCallback:
    @pytest.mark.asyncio
    async def test_refresh_completed_stops_timer(self, ui_stub: MagicMock) -> None:
        """Timer deactivates when DB task reaches completed status."""
        processing_task = _make_task(status="processing", progress=50)
        completed_task = _make_task(status="completed", progress=100)
        clips = [_make_clip(processing_task.id, index=1)]

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(completed_task, clips),
            _make_session_ctx(completed_task, clips),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            assert timer_instances, "Expected at least one timer"
            poll_timer = timer_instances[0]
            assert poll_timer._callback is not None

            await poll_timer._callback()

        assert poll_timer.active is False

    @pytest.mark.asyncio
    async def test_refresh_failed_stops_timer(self, ui_stub: MagicMock) -> None:
        """Timer deactivates when DB task reaches failed status."""
        processing_task = _make_task(status="processing", progress=50)
        failed_task = _make_task(
            status="failed",
            progress=50,
            error_message="Encoding crashed",
        )

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(failed_task),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        assert poll_timer.active is False

    @pytest.mark.asyncio
    async def test_refresh_failed_none_error_message(
        self, ui_stub: MagicMock
    ) -> None:
        """Fallback error message is used when error_message is None."""
        processing_task = _make_task(status="processing", progress=50)
        failed_task = _make_task(status="failed", progress=50, error_message=None)

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(failed_task),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        assert poll_timer.active is False

    @pytest.mark.asyncio
    async def test_refresh_task_missing_stops_timer(
        self, ui_stub: MagicMock
    ) -> None:
        """Timer deactivates when the task record disappears mid-poll."""
        processing_task = _make_task(status="processing", progress=50)

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(None),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        assert poll_timer.active is False

    @pytest.mark.asyncio
    async def test_refresh_still_processing_keeps_timer_active(
        self, ui_stub: MagicMock
    ) -> None:
        """Timer stays active when the task is still processing."""
        processing_task = _make_task(
            status="processing",
            progress=60,
            progress_message="Encoding clip 2/3",
        )

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(processing_task),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        assert poll_timer.active is True


# ---------------------------------------------------------------------------
# Tests: _show_clips() inner function (lines 203-223)
# ---------------------------------------------------------------------------


class TestShowClips:
    @pytest.mark.asyncio
    async def test_show_clips_renders_correct_video_count(
        self, ui_stub: MagicMock
    ) -> None:
        """_show_clips calls ui.video once per clip from the DB."""
        processing_task = _make_task(status="processing", progress=50)
        completed_task = _make_task(status="completed", progress=100)
        clips = [_make_clip(processing_task.id, index=i) for i in range(1, 3)]

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(completed_task, clips),
            _make_session_ctx(completed_task, clips),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        assert ui_stub.video.call_count == len(clips)

    @pytest.mark.asyncio
    async def test_show_clips_sets_status_label_with_clip_word(
        self, ui_stub: MagicMock
    ) -> None:
        """_show_clips sets status label text containing the word clip."""
        processing_task = _make_task(status="processing", progress=50)
        completed_task = _make_task(status="completed", progress=100)
        clips = [_make_clip(processing_task.id, index=1)]

        label_instances: list[MagicMock] = []
        original_effect = ui_stub.label.side_effect

        def _tracking_label(*args: object, **kwargs: object) -> MagicMock:
            m = original_effect(*args, **kwargs) if original_effect else MagicMock()
            label_instances.append(m)
            return m  # type: ignore[return-value]

        ui_stub.label.side_effect = _tracking_label

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(completed_task, clips),
            _make_session_ctx(completed_task, clips),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        texts_with_clip = [
            m.text
            for m in label_instances
            if isinstance(m.text, str) and "clip" in m.text
        ]
        assert texts_with_clip, (
            "Expected at least one label with clip in text after _show_clips. "
            f"Got: {[m.text for m in label_instances]}"
        )

    @pytest.mark.asyncio
    async def test_show_clips_uses_plural_for_multiple_clips(
        self, ui_stub: MagicMock
    ) -> None:
        """_show_clips uses clips plural when count is not 1."""
        processing_task = _make_task(status="processing", progress=50)
        completed_task = _make_task(status="completed", progress=100)
        clips = [_make_clip(processing_task.id, index=i) for i in range(1, 4)]

        label_instances: list[MagicMock] = []
        original_effect = ui_stub.label.side_effect

        def _tracking_label(*args: object, **kwargs: object) -> MagicMock:
            m = original_effect(*args, **kwargs) if original_effect else MagicMock()
            label_instances.append(m)
            return m  # type: ignore[return-value]

        ui_stub.label.side_effect = _tracking_label

        factory = _make_session_factory(
            _make_session_ctx(processing_task),
            _make_session_ctx(completed_task, clips),
            _make_session_ctx(completed_task, clips),
        )

        with patch("src.pages.task.get_session", side_effect=factory):
            from src.pages.task import render

            await render(processing_task.id)

            timer_instances = ui_stub._timer_instances  # type: ignore[attr-defined]
            poll_timer = timer_instances[0]

            await poll_timer._callback()

        texts_with_clips = [
            m.text
            for m in label_instances
            if isinstance(m.text, str) and "clips" in m.text
        ]
        assert texts_with_clips, (
            "Expected clips plural in at least one label text after _show_clips"
        )
# end tests/unit/test_task_page.py
