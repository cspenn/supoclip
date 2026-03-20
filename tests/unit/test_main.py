# start tests/unit/test_main.py
"""Unit tests for src/main.py — application entry point."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _passthrough_page_decorator(path: str):  # noqa: ANN001
    """Return a decorator that passes the function through unchanged."""
    def decorator(fn):  # noqa: ANN001, ANN202
        return fn
    return decorator


@contextmanager
def _isolated_main_import() -> Generator[types.ModuleType, None, None]:
    """Import src.main in isolation.

    Within this context manager:
    - ``nicegui.ui.page`` is a pass-through decorator so async page functions
      survive decoration as real coroutines.
    - Minimal stubs for all ``src.pages.*`` modules are injected into
      ``sys.modules`` so their ``render`` callables exist without loading the
      real NiceGUI page implementations.
    - All stubs are removed and the original state is restored on exit.

    Yields:
        The freshly imported ``src.main`` module.
    """
    import nicegui

    stub_names = (
        "src.pages.home",
        "src.pages.task",
        "src.pages.history",
        "src.pages.settings",
    )

    # Save originals
    original_page = nicegui.ui.page
    original_stubs = {name: sys.modules.pop(name, None) for name in stub_names}
    sys.modules.pop("src.main", None)

    # Install stubs
    for name in stub_names:
        mod = types.ModuleType(name)
        mod.render = AsyncMock()  # type: ignore[attr-defined]
        sys.modules[name] = mod

    # Install pass-through decorator
    nicegui.ui.page = _passthrough_page_decorator  # type: ignore[attr-defined]

    try:
        main_mod = importlib.import_module("src.main")
        yield main_mod
    finally:
        # Restore nicegui.ui.page
        nicegui.ui.page = original_page  # type: ignore[attr-defined]
        # Remove src.main so subsequent imports of the real module work cleanly
        sys.modules.pop("src.main", None)
        # Restore or remove page stubs
        for name in stub_names:
            sys.modules.pop(name, None)
            if original_stubs[name] is not None:
                sys.modules[name] = original_stubs[name]


# ---------------------------------------------------------------------------
# Build a module reference scoped to this test file's lifetime.
# We keep it alive only for the tests in this file.
# ---------------------------------------------------------------------------

with _isolated_main_import() as _main:
    # Keep a reference — the context manager cleaned sys.modules but the
    # module object itself is still valid for calling functions.
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHomePage:
    """Tests for home_page()."""

    async def test_calls_render(self) -> None:
        """home_page() calls src.pages.home.render exactly once."""
        mock_render = AsyncMock()
        with patch.dict(sys.modules, {"src.pages.home": MagicMock(render=mock_render)}):
            await _main.home_page()
        mock_render.assert_awaited_once_with()


class TestTaskPage:
    """Tests for task_page()."""

    async def test_calls_render_with_task_id(self) -> None:
        """task_page() calls src.pages.task.render with the task_id argument."""
        mock_render = AsyncMock()
        with patch.dict(sys.modules, {"src.pages.task": MagicMock(render=mock_render)}):
            await _main.task_page("abc123")
        mock_render.assert_awaited_once_with("abc123")


class TestHistoryPage:
    """Tests for history_page()."""

    async def test_calls_render(self) -> None:
        """history_page() calls src.pages.history.render exactly once."""
        mock_render = AsyncMock()
        with patch.dict(sys.modules, {"src.pages.history": MagicMock(render=mock_render)}):
            await _main.history_page()
        mock_render.assert_awaited_once_with()


class TestSettingsPage:
    """Tests for settings_page()."""

    async def test_calls_render(self) -> None:
        """settings_page() calls src.pages.settings.render exactly once."""
        mock_render = AsyncMock()
        with patch.dict(sys.modules, {"src.pages.settings": MagicMock(render=mock_render)}):
            await _main.settings_page()
        mock_render.assert_awaited_once_with()


class TestStartup:
    """Tests for _startup()."""

    async def test_calls_init_db_with_database_url(self) -> None:
        """_startup() calls init_db with the database_url from config."""
        fake_cfg = MagicMock()
        fake_cfg.database_url = "sqlite+aiosqlite:///./test.db"
        mock_init_db = AsyncMock()
        with (
            patch.object(_main, "get_config", return_value=fake_cfg),
            patch.object(_main, "init_db", mock_init_db),
        ):
            await _main._startup()
        mock_init_db.assert_awaited_once_with("sqlite+aiosqlite:///./test.db")


class TestShutdown:
    """Tests for _shutdown()."""

    async def test_calls_close_db(self) -> None:
        """_shutdown() calls close_db exactly once."""
        mock_close_db = AsyncMock()
        with patch.dict(
            sys.modules,
            {"src.database": MagicMock(close_db=mock_close_db)},
        ):
            await _main._shutdown()
        mock_close_db.assert_awaited_once_with()


class TestMain:
    """Tests for main()."""

    def test_registers_hooks_and_calls_ui_run(self) -> None:
        """main() registers startup/shutdown hooks and calls ui.run."""
        import nicegui

        nicegui.app.reset_mock()
        nicegui.ui.run = MagicMock()

        _main.main()

        nicegui.app.on_startup.assert_called_once()
        nicegui.app.on_shutdown.assert_called_once()
        nicegui.ui.run.assert_called_once_with(
            title="SupoClip", port=8008, show=False, reload=False
        )


class TestModuleLevelGuard:
    """Tests for the ``if __name__ in {"__main__", "__mp_main__"}:`` guard."""

    def test_guard_executes_main_when_name_is_dunder_main(self) -> None:
        """main() is invoked when module is executed with __name__=='__main__'.

        Coverage for line 64 (``main()`` inside the guard) is achieved by
        loading the module source under the name ``__main__`` so the guard
        evaluates to True.  ``ui.run`` is a MagicMock from the conftest stub,
        so the call does not block.
        """
        import nicegui

        original_page = nicegui.ui.page
        nicegui.ui.page = _passthrough_page_decorator  # type: ignore[attr-defined]
        nicegui.ui.run = MagicMock()
        nicegui.app.reset_mock()

        stub_names = (
            "src.pages.home",
            "src.pages.task",
            "src.pages.history",
            "src.pages.settings",
        )
        original_stubs = {name: sys.modules.pop(name, None) for name in stub_names}
        for name in stub_names:
            mod = types.ModuleType(name)
            mod.render = AsyncMock()  # type: ignore[attr-defined]
            sys.modules[name] = mod

        spec = importlib.util.spec_from_file_location(
            "__main__",
            "/Users/cspenn/Documents/github/supoclip/src/main.py",
        )
        assert spec is not None
        assert spec.loader is not None
        sentinel_mod = importlib.util.module_from_spec(spec)
        sys.modules["src.main"] = sentinel_mod
        try:
            spec.loader.exec_module(sentinel_mod)  # type: ignore[union-attr]
        finally:
            sys.modules.pop("src.main", None)
            nicegui.ui.page = original_page  # type: ignore[attr-defined]
            for name in stub_names:
                sys.modules.pop(name, None)
                if original_stubs[name] is not None:
                    sys.modules[name] = original_stubs[name]

        # main() was invoked by the guard, which calls ui.run
        nicegui.ui.run.assert_called_once_with(
            title="SupoClip", port=8008, show=False, reload=False
        )
# end tests/unit/test_main.py
