# start tests/unit/conftest.py
"""Shared pytest configuration for unit tests.

Injects a lightweight ``nicegui`` stub into ``sys.modules`` before any test
module is collected, so that ``src/pages/*.py`` (which do ``from nicegui
import ui``) can be imported without the real NiceGUI package being installed
in the test environment.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _make_widget(*args, **kwargs) -> MagicMock:
    """Return a MagicMock that supports the most common NiceGUI widget fluent API.

    Args:
        *args: Positional arguments (ignored).
        **kwargs: Keyword arguments (ignored).

    Returns:
        A :class:`~unittest.mock.MagicMock` pre-configured for chaining and
        use as a context manager.
    """
    m = MagicMock()
    m.classes.return_value = m
    m.props.return_value = m
    m.style.return_value = m
    m.on.return_value = m
    m.bind_value.return_value = m
    m.set_visibility.return_value = None
    m.clear.return_value = None
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    return m


def _build_ui_module() -> types.SimpleNamespace:
    """Construct the ``nicegui.ui`` stub namespace.

    Returns:
        A :class:`types.SimpleNamespace` whose attributes mirror the
        NiceGUI ``ui`` components used across all page modules.
    """
    ns = types.SimpleNamespace()

    # Widget factories — each returns a self-chaining MagicMock.
    for _name in (
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
        "input",
        "select",
        "slider",
        "upload",
        "separator",
        "notify",
        "page",
        "image",
        "icon",
    ):
        setattr(ns, _name, _make_widget)

    # timer must track the .active attribute realistically.
    def _timer(interval=1.0, callback=None, **kwargs):  # noqa: ANN001, ANN002, ANN003
        t = MagicMock()
        t.active = True
        t._interval = interval
        t._callback = callback
        return t

    ns.timer = _timer

    # ui.download is a bare function, not a widget factory.
    ns.download = MagicMock()

    # ui.run is called only at app startup — stub it out entirely.
    ns.run = MagicMock()

    return ns


def _register_nicegui_stub() -> None:
    """Register a fake ``nicegui`` package in ``sys.modules``.

    Only registers if the real package is not already present, so this is safe
    to call when NiceGUI is installed as well.
    """
    if "nicegui" in sys.modules:
        return  # real package available — no stub needed

    nicegui_mod = types.ModuleType("nicegui")
    nicegui_mod.ui = _build_ui_module()  # type: ignore[attr-defined]

    # Some imports do ``from nicegui import app`` — stub that too.
    nicegui_mod.app = MagicMock()  # type: ignore[attr-defined]

    sys.modules["nicegui"] = nicegui_mod
    sys.modules["nicegui.ui"] = nicegui_mod.ui  # type: ignore[assignment]


# Register the stub at collection time, before any test module is imported.
_register_nicegui_stub()
# end tests/unit/conftest.py
