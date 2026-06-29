# start tests/unit/test_history.py
"""Unit tests for src/pages/history.py."""

from __future__ import annotations

import functools
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.pages.history import (
    _format_date,
    _load_tasks,
    _render_empty_state,
    _render_navigation,
    _render_task_row,
    _truncate,
    delete_task,
    render,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str,
    source_url: str = "https://youtu.be/abc123",
    status: str = "completed",
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a mock Task object.

    Args:
        task_id: Value for ``task.id``.
        source_url: Value for ``task.source_url``.
        status: Value for ``task.status``.
        created_at: Value for ``task.created_at``; defaults to a fixed UTC time.

    Returns:
        MagicMock configured to look like a Task ORM instance.
    """
    task = MagicMock()
    task.id = task_id
    task.source_url = source_url
    task.status = status
    task.created_at = created_at or datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC)
    return task


# ---------------------------------------------------------------------------
# Pure utility tests
# ---------------------------------------------------------------------------


class TestFormatDate:
    """Tests for _format_date()."""

    def test_formats_datetime_correctly(self) -> None:
        """_format_date returns the expected human-readable string."""
        dt = datetime(2026, 3, 17, 14, 30, 0, tzinfo=UTC)
        assert _format_date(dt) == "Mar 17, 2026 14:30"

    def test_formats_single_digit_day_with_leading_zero(self) -> None:
        """Day component is zero-padded to two digits."""
        dt = datetime(2026, 1, 5, 9, 5, 0, tzinfo=UTC)
        result = _format_date(dt)
        assert "Jan 05, 2026" in result

    def test_formats_time_component(self) -> None:
        """Hour and minute are included in the formatted output."""
        dt = datetime(2026, 6, 1, 23, 59, 0, tzinfo=UTC)
        result = _format_date(dt)
        assert "23:59" in result


class TestTruncate:
    """Tests for _truncate()."""

    def test_short_string_unchanged(self) -> None:
        """Strings at or below max_len are returned as-is."""
        assert _truncate("hello", 10) == "hello"

    def test_exact_max_len_unchanged(self) -> None:
        """A string exactly at max_len is not truncated."""
        s = "a" * 50
        assert _truncate(s) == s

    def test_long_string_truncated_with_ellipsis(self) -> None:
        """Strings longer than max_len are cut and appended with '…'."""
        s = "a" * 60
        result = _truncate(s)
        assert result.endswith("…")
        assert len(result) == 51  # 50 chars + ellipsis

    def test_custom_max_len(self) -> None:
        """Custom max_len parameter is respected."""
        result = _truncate("hello world", max_len=5)
        assert result == "hello…"


# ---------------------------------------------------------------------------
# delete_task() tests
# ---------------------------------------------------------------------------


class TestDeleteTask:
    """Tests for delete_task()."""

    async def test_deletes_existing_task_and_reloads(self) -> None:
        """delete_task() removes the task from the DB and calls ui.navigate.reload."""
        mock_task = _make_task("task-001")
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_task)
        clip_result = MagicMock()
        clip_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=clip_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pages.history.get_session", return_value=mock_session),
            patch("src.pages.history.remove_clip_files") as mock_remove,
            patch("src.pages.history.ui") as mock_ui,
        ):
            await delete_task("task-001")

        mock_session.get.assert_awaited_once()
        mock_session.delete.assert_awaited_once_with(mock_task)
        mock_session.commit.assert_awaited_once()
        mock_remove.assert_called_once_with([])
        mock_ui.navigate.reload.assert_called_once()

    async def test_no_error_when_task_not_found(self) -> None:
        """delete_task() is a no-op (no exception) when task_id does not exist."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pages.history.get_session", return_value=mock_session),
            patch("src.pages.history.ui"),
        ):
            await delete_task("nonexistent-id")

        mock_session.delete.assert_not_awaited()

    async def test_reload_called_even_when_task_missing(self) -> None:
        """ui.navigate.reload() is called regardless of whether the task existed."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.pages.history.get_session", return_value=mock_session),
            patch("src.pages.history.ui") as mock_ui,
        ):
            await delete_task("nonexistent-id")

        mock_ui.navigate.reload.assert_called_once()

    async def test_deletes_clip_files_from_disk(self, tmp_path: Path) -> None:
        """delete_task() removes the task's clip .mp4 files from the clips dir."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        f1 = clips_dir / "clip_001.mp4"
        f2 = clips_dir / "clip_002.mp4"
        f1.write_bytes(b"a")
        f2.write_bytes(b"b")

        mock_task = _make_task("task-001")
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_task)
        clip_result = MagicMock()
        clip_result.all.return_value = [("clip_001.mp4",), ("clip_002.mp4",)]
        mock_session.execute = AsyncMock(return_value=clip_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        cfg = MagicMock()
        cfg.temp_dir = tmp_path

        with (
            patch("src.pages.history.get_session", return_value=mock_session),
            patch("src.pages._util.get_config", return_value=cfg),
            patch("src.pages.history.ui"),
        ):
            await delete_task("task-001")

        assert not f1.exists()
        assert not f2.exists()
        mock_session.delete.assert_awaited_once_with(mock_task)

    async def test_delete_button_handler_runs_delete_coroutine(self) -> None:
        """The row's delete button on_click is a partial that awaits delete_task."""
        task = _make_task("task-xyz")
        captured: list[dict] = []

        def capture_button(*args: object, **kwargs: object) -> MagicMock:
            captured.append(dict(kwargs))
            btn = MagicMock()
            btn.props.return_value = btn
            btn.tooltip.return_value = btn
            return btn

        with (
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history.delete_task", new=AsyncMock()) as mock_delete,
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.card.return_value = cm
            mock_ui.row.return_value = cm
            mock_ui.badge.return_value = MagicMock()
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.button.side_effect = capture_button

            _render_task_row(task, clip_count=1)

            handlers = [kw.get("on_click") for kw in captured if kw.get("on_click") is not None]
            partials = [h for h in handlers if isinstance(h, functools.partial)]
            assert len(partials) == 1, "delete button must use a functools.partial handler"

            # Invoking the handler must actually run the async delete coroutine.
            await partials[0]()

        mock_delete.assert_awaited_once_with("task-xyz")


# ---------------------------------------------------------------------------
# render() tests — with tasks
# ---------------------------------------------------------------------------


class TestRenderWithTasks:
    """Tests for render() when tasks are present in the database."""

    async def test_renders_three_tasks(self) -> None:
        """render() calls _render_task_row once per task returned by _load_tasks."""
        tasks = [
            _make_task("t1", status="completed"),
            _make_task("t2", status="processing"),
            _make_task("t3", status="failed"),
        ]
        clip_counts = {"t1": 3, "t2": 0, "t3": 1}

        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(return_value=(tasks, clip_counts)),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row") as mock_row,
            patch("src.pages.history._render_empty_state") as mock_empty,
        ):
            # Provide a context manager stub for ui.row() and ui.column()
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.column.return_value = cm

            await render()

        assert mock_row.call_count == 3
        mock_empty.assert_not_called()

    async def test_clip_counts_passed_correctly(self) -> None:
        """render() passes the correct clip count to each task row."""
        tasks = [_make_task("t1"), _make_task("t2")]
        clip_counts = {"t1": 5, "t2": 2}
        row_calls: list[tuple[object, int]] = []

        def capture_row(task: object, count: int) -> None:
            row_calls.append((task, count))

        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(return_value=(tasks, clip_counts)),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row", side_effect=capture_row),
            patch("src.pages.history._render_empty_state"),
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.column.return_value = cm

            await render()

        assert row_calls[0] == (tasks[0], 5)
        assert row_calls[1] == (tasks[1], 2)

    async def test_missing_clip_count_defaults_to_zero(self) -> None:
        """render() defaults clip count to 0 for tasks absent from clip_counts."""
        tasks = [_make_task("t1")]
        clip_counts: dict[str, int] = {}  # no entry for "t1"
        row_calls: list[tuple[object, int]] = []

        def capture_row(task: object, count: int) -> None:
            row_calls.append((task, count))

        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(return_value=(tasks, clip_counts)),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row", side_effect=capture_row),
            patch("src.pages.history._render_empty_state"),
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.column.return_value = cm

            await render()

        assert row_calls[0] == (tasks[0], 0)


# ---------------------------------------------------------------------------
# render() tests — empty state
# ---------------------------------------------------------------------------


class TestRenderEmptyState:
    """Tests for render() when the task list is empty."""

    async def test_renders_empty_state_when_no_tasks(self) -> None:
        """render() calls _render_empty_state and skips _render_task_row when empty."""
        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(return_value=([], {})),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row") as mock_row,
            patch("src.pages.history._render_empty_state") as mock_empty,
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.column.return_value = cm

            await render()

        mock_empty.assert_called_once()
        mock_row.assert_not_called()

    async def test_no_task_cards_rendered_when_empty(self) -> None:
        """render() does not attempt to create any card UI for an empty task list."""
        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(return_value=([], {})),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row") as mock_row,
            patch("src.pages.history._render_empty_state"),
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.card = MagicMock(return_value=cm)

            await render()

        mock_row.assert_not_called()


# ---------------------------------------------------------------------------
# render() error handling
# ---------------------------------------------------------------------------


class TestRenderErrorHandling:
    """Tests for render() when the database query raises an exception."""

    async def test_shows_notification_on_db_error(self) -> None:
        """render() shows a negative notification when _load_tasks raises."""
        with (
            patch(
                "src.pages.history._load_tasks",
                new=AsyncMock(side_effect=RuntimeError("DB unavailable")),
            ),
            patch("src.pages.history.ui") as mock_ui,
            patch("src.pages.history._render_navigation"),
            patch("src.pages.history._render_task_row") as mock_row,
            patch("src.pages.history._render_empty_state") as mock_empty,
        ):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm

            await render()

        mock_ui.notify.assert_called_once()
        call_kwargs = mock_ui.notify.call_args
        assert call_kwargs.kwargs.get("type") == "negative" or (len(call_kwargs.args) > 1 and call_kwargs.args[1] == "negative")
        mock_row.assert_not_called()
        mock_empty.assert_not_called()


# ---------------------------------------------------------------------------
# _load_tasks() direct tests (lines 61-75)
# ---------------------------------------------------------------------------


class TestLoadTasks:
    """Tests for _load_tasks() exercising the real DB query path."""

    async def test_returns_tasks_and_clip_counts(self) -> None:
        """_load_tasks() returns tasks list and clip_counts dict from the session."""
        mock_task = _make_task("t1")

        # task_result stub
        task_scalars = MagicMock()
        task_scalars.all.return_value = [mock_task]
        task_result = MagicMock()
        task_result.scalars.return_value = task_scalars

        # count_result stub: returns iterable of (task_id, count) rows
        count_result = MagicMock()
        count_result.all.return_value = [("t1", 2)]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[task_result, count_result])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.pages.history.get_session", return_value=mock_session):
            tasks, clip_counts = await _load_tasks()

        assert tasks == [mock_task]
        assert clip_counts == {"t1": 2}

    async def test_returns_empty_lists_when_no_tasks(self) -> None:
        """_load_tasks() returns empty list and empty dict when the DB has no rows."""
        task_scalars = MagicMock()
        task_scalars.all.return_value = []
        task_result = MagicMock()
        task_result.scalars.return_value = task_scalars

        count_result = MagicMock()
        count_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[task_result, count_result])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.pages.history.get_session", return_value=mock_session):
            tasks, clip_counts = await _load_tasks()

        assert tasks == []
        assert clip_counts == {}

    async def test_executes_two_queries(self) -> None:
        """_load_tasks() issues exactly two SQL queries: tasks then clip counts."""
        task_scalars = MagicMock()
        task_scalars.all.return_value = []
        task_result = MagicMock()
        task_result.scalars.return_value = task_scalars

        count_result = MagicMock()
        count_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[task_result, count_result])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.pages.history.get_session", return_value=mock_session):
            await _load_tasks()

        assert mock_session.execute.await_count == 2


# ---------------------------------------------------------------------------
# _render_navigation() direct tests (lines 99-102)
# ---------------------------------------------------------------------------


class TestRenderNavigation:
    """Tests for _render_navigation() exercising the real UI widget path."""

    def test_render_navigation_executes_without_error(self) -> None:
        """_render_navigation() runs through all widget calls without raising."""
        # The NiceGUI stub in conftest handles all ui.* calls — just call it.
        _render_navigation()

    def test_render_navigation_calls_ui_row(self) -> None:
        """_render_navigation() creates a ui.row context manager."""
        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm

            _render_navigation()

        mock_ui.row.assert_called_once()

    def test_render_navigation_adds_home_and_settings_links(self) -> None:
        """_render_navigation() creates link widgets for Home and Settings."""
        link_targets: list[str] = []

        def capture_link(label: str, target: str) -> MagicMock:
            link_targets.append(target)
            m = MagicMock()
            m.classes.return_value = m
            return m

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.row.return_value = cm
            mock_ui.link.side_effect = capture_link
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))

            _render_navigation()

        assert "/" in link_targets
        assert "/settings" in link_targets


# ---------------------------------------------------------------------------
# _render_task_row() direct tests (lines 112-125)
# ---------------------------------------------------------------------------


class TestRenderTaskRow:
    """Tests for _render_task_row() exercising the real UI widget path."""

    def test_render_task_row_executes_without_error(self) -> None:
        """_render_task_row() runs to completion without raising for a known status."""
        task = _make_task("t1", status="completed")
        # NiceGUI stub in conftest handles all ui.* calls
        _render_task_row(task, clip_count=3)

    def test_render_task_row_uses_status_color(self) -> None:
        """_render_task_row() passes the correct color for a known status."""
        task = _make_task("t1", status="failed")
        badge_kwargs: list[dict] = []

        def capture_badge(*args: object, **kwargs: object) -> MagicMock:
            badge_kwargs.append({"args": args, "kwargs": kwargs})
            return MagicMock()

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.card.return_value = cm
            mock_ui.row.return_value = cm
            mock_ui.badge.side_effect = capture_badge
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.button.return_value = MagicMock(props=MagicMock(return_value=MagicMock(tooltip=MagicMock())))

            _render_task_row(task, clip_count=1)

        assert badge_kwargs, "ui.badge should have been called"
        assert badge_kwargs[0]["kwargs"].get("color") == "negative"

    def test_render_task_row_unknown_status_uses_grey(self) -> None:
        """_render_task_row() falls back to 'grey' for an unrecognised status."""
        task = _make_task("t1", status="unknown_status")
        badge_kwargs: list[dict] = []

        def capture_badge(*args: object, **kwargs: object) -> MagicMock:
            badge_kwargs.append({"args": args, "kwargs": kwargs})
            return MagicMock()

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.card.return_value = cm
            mock_ui.row.return_value = cm
            mock_ui.badge.side_effect = capture_badge
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.button.return_value = MagicMock(props=MagicMock(return_value=MagicMock(tooltip=MagicMock())))

            _render_task_row(task, clip_count=0)

        assert badge_kwargs[0]["kwargs"].get("color") == "grey"

    def test_render_task_row_singular_clip_label(self) -> None:
        """_render_task_row() labels '1 clip' (not '1 clips') for a single clip."""
        task = _make_task("t1", status="completed")
        label_texts: list[str] = []

        def capture_label(text: str) -> MagicMock:
            label_texts.append(text)
            return MagicMock(classes=MagicMock(return_value=MagicMock()))

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.card.return_value = cm
            mock_ui.row.return_value = cm
            mock_ui.badge.return_value = MagicMock()
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.side_effect = capture_label
            mock_ui.button.return_value = MagicMock(props=MagicMock(return_value=MagicMock(tooltip=MagicMock())))

            _render_task_row(task, clip_count=1)

        assert any("1 clip" in t and "clips" not in t for t in label_texts)

    def test_render_task_row_plural_clip_label(self) -> None:
        """_render_task_row() labels '3 clips' for a count other than 1."""
        task = _make_task("t1", status="completed")
        label_texts: list[str] = []

        def capture_label(text: str) -> MagicMock:
            label_texts.append(text)
            return MagicMock(classes=MagicMock(return_value=MagicMock()))

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.card.return_value = cm
            mock_ui.row.return_value = cm
            mock_ui.badge.return_value = MagicMock()
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.side_effect = capture_label
            mock_ui.button.return_value = MagicMock(props=MagicMock(return_value=MagicMock(tooltip=MagicMock())))

            _render_task_row(task, clip_count=3)

        assert any("3 clips" in t for t in label_texts)


# ---------------------------------------------------------------------------
# _render_empty_state() direct tests (lines 133-138)
# ---------------------------------------------------------------------------


class TestRenderEmptyStateDirect:
    """Tests for _render_empty_state() exercising the real UI widget path."""

    def test_render_empty_state_executes_without_error(self) -> None:
        """_render_empty_state() runs through all widget calls without raising."""
        # NiceGUI stub in conftest handles all ui.* calls
        _render_empty_state()

    def test_render_empty_state_creates_column(self) -> None:
        """_render_empty_state() creates a ui.column context manager."""
        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.column.return_value = cm
            mock_ui.icon.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.link.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))

            _render_empty_state()

        mock_ui.column.assert_called_once()

    def test_render_empty_state_links_to_home(self) -> None:
        """_render_empty_state() includes a link to '/' for processing a new video."""
        link_targets: list[str] = []

        def capture_link(label: str, target: str) -> MagicMock:
            link_targets.append(target)
            return MagicMock(classes=MagicMock(return_value=MagicMock()))

        with patch("src.pages.history.ui") as mock_ui:
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cm)
            cm.__exit__ = MagicMock(return_value=False)
            mock_ui.column.return_value = cm
            mock_ui.icon.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.label.return_value = MagicMock(classes=MagicMock(return_value=MagicMock()))
            mock_ui.link.side_effect = capture_link

            _render_empty_state()

        assert "/" in link_targets


# end tests/unit/test_history.py
