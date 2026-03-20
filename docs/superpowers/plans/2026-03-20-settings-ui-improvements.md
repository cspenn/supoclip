# Settings UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Settings page with a font family dropdown (TTF-discovered), reactive slider labels, and a live subtitle preview (typography card + 9:16 phone frame).

**Architecture:** Three isolated changes to `src/pages/settings.py`: (1) a module-level `_discover_fonts()` helper reads TTF files via fonttools; (2) two module-level HTML builder functions produce preview strings; (3) `render()` is updated to wire a `_update_preview()` closure over all font widgets and the preview `ui.html()` elements. All reactive label updates are folded into `_update_preview()` so one `change` handler per slider handles both label sync and preview refresh.

**Tech Stack:** Python 3.12, NiceGUI, fonttools (already in `pyproject.toml`), pytest with 100% coverage requirement.

---

## File Map

| File | What changes |
|------|-------------|
| `src/pages/settings.py` | Add `from pathlib import Path`, `from fontTools.ttLib import TTFont`, add `Config` to existing import; add `_discover_fonts()`, `_build_typo_html()`, `_build_phone_html()` at module level; update `render()` throughout |
| `tests/unit/test_settings.py` | Add `TestDiscoverFonts`, `TestBuildPreviewHtml`; update `_build_capturing_ui_mock` and `_build_ui_mock` to mock `ui.html`; add integration tests `test_font_family_select_not_input`, `test_reset_calls_update_preview` |

---

## Task 1: `_discover_fonts()` — Pure TTF Scanner

**Files:**
- Modify: `src/pages/settings.py` — new imports + `_discover_fonts()`
- Modify: `tests/unit/test_settings.py` — `TestDiscoverFonts` class

---

- [ ] **Step 1.1: Write failing tests for `_discover_fonts()`**

> **Note on test approach:** The design spec says `test_discover_fonts_with_valid_ttf` should use "a minimal valid TTF in `tests/fixtures/`". This plan uses `unittest.mock.patch` on `TTFont` instead, to avoid committing binary assets to the repository. The mock approach is equivalent in coverage: it verifies the same parsing logic paths without a real font binary.

Add this class to `tests/unit/test_settings.py` (after the `TestIsValidHexColor` class, before `TestLoadPrefs`). Also add `from unittest.mock import MagicMock, patch` to the existing mock import if not already present.

```python
# ---------------------------------------------------------------------------
# _discover_fonts
# ---------------------------------------------------------------------------


class TestDiscoverFonts:
    """Tests for the _discover_fonts() module-level helper."""

    def test_empty_dir_returns_arial(self, tmp_path: Path) -> None:
        """Empty fonts directory returns the Arial fallback."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path)
        assert result == ["Arial"]

    def test_valid_ttfs_returns_sorted_names(self, tmp_path: Path) -> None:
        """TTF files are parsed and names returned sorted alphabetically."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "barlow.ttf").write_bytes(b"fake")
        (tmp_path / "arial.ttf").write_bytes(b"fake")

        def _mock_ttfont(path: str) -> MagicMock:
            font = MagicMock()
            name_table = MagicMock()
            if "barlow" in path:
                r = MagicMock()
                r.nameID = 1
                r.toUnicode.return_value = "Barlow Condensed"
            else:
                r = MagicMock()
                r.nameID = 1
                r.toUnicode.return_value = "Arial"
            name_table.names = [r]
            font.__getitem__ = lambda _self, _key: name_table
            return font

        with patch("src.pages.settings.TTFont", side_effect=_mock_ttfont):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Arial", "Barlow Condensed"]

    def test_bad_file_is_skipped(self, tmp_path: Path) -> None:
        """Unparseable TTF files are skipped; valid ones still returned."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "good.ttf").write_bytes(b"fake")
        (tmp_path / "bad.ttf").write_bytes(b"invalid")

        good_font = MagicMock()
        good_record = MagicMock()
        good_record.nameID = 1
        good_record.toUnicode.return_value = "Good Font"
        good_name_table = MagicMock()
        good_name_table.names = [good_record]
        good_font.__getitem__ = lambda _self, _key: good_name_table

        def _mock_ttfont(path: str) -> MagicMock:
            if "bad" in path:
                raise Exception("Invalid font file")
            return good_font

        with patch("src.pages.settings.TTFont", side_effect=_mock_ttfont):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Good Font"]

    def test_all_files_fail_falls_back_to_arial(self, tmp_path: Path) -> None:
        """When all TTF files fail to parse, Arial fallback is returned."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "broken.ttf").write_bytes(b"garbage")

        with patch("src.pages.settings.TTFont", side_effect=Exception("parse error")):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Arial"]

    def test_current_value_not_in_list_is_prepended(self, tmp_path: Path) -> None:
        """current_value is prepended when not in the discovered list."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path, current_value="MyCustomFont")
        # tmp_path is empty → fallback ["Arial"], "MyCustomFont" prepended
        assert result == ["MyCustomFont", "Arial"]

    def test_current_value_already_in_list_not_duplicated(
        self, tmp_path: Path
    ) -> None:
        """current_value is not added when already present in the list."""
        from src.pages.settings import _discover_fonts

        result = _discover_fonts(fonts_dir=tmp_path, current_value="Arial")
        assert result == ["Arial"]  # not ["Arial", "Arial"]

    def test_nameids_fallback_to_nameid4(self, tmp_path: Path) -> None:
        """Falls back to nameID 4 when nameID 1 is absent."""
        from src.pages.settings import _discover_fonts

        (tmp_path / "font.ttf").write_bytes(b"fake")

        font = MagicMock()
        name_table = MagicMock()
        r4 = MagicMock()
        r4.nameID = 4
        r4.toUnicode.return_value = "Full Name Font"
        name_table.names = [r4]
        font.__getitem__ = lambda _self, _key: name_table

        with patch("src.pages.settings.TTFont", return_value=font):
            result = _discover_fonts(fonts_dir=tmp_path)

        assert result == ["Full Name Font"]
```

- [ ] **Step 1.2: Run failing tests**

```bash
uv run pytest tests/unit/test_settings.py::TestDiscoverFonts -v
```
Expected: `ImportError` — `_discover_fonts` doesn't exist yet.

- [ ] **Step 1.3: Add imports and `_discover_fonts()` to `settings.py`**

> **Note on `fonttools`:** The design spec lists `pyproject.toml` as a file to change and says "Add `fonttools` to `[project.dependencies]`". However, `fonttools>=4.45.0` is already present in `pyproject.toml` at line 22 (added in a prior task). No change to `pyproject.toml` is needed — the spec's requirement is already satisfied.

> **Note on `Config.FONTS_DIR` as a default argument:** `Config.FONTS_DIR` is declared as `ClassVar[Path] = Path("fonts")` in `src/config.py`. Because it is a class variable (not an instance attribute), it is set when the class is defined at module import time — not at function-call time. Using it as a default argument (`fonts_dir: Path = Config.FONTS_DIR`) is safe: there is no "mutable default" hazard, and the value is available at import time.

At the top of `src/pages/settings.py`, update imports:

```python
# start src/pages/settings.py
"""NiceGUI settings page for SupoClip.

Provides the UI for configuring font, clip, AI, and logo preferences.
All settings are persisted to the UserPreferences singleton row (id=1).
"""
from __future__ import annotations

import re
from pathlib import Path

import structlog
from fontTools.ttLib import TTFont
from nicegui import ui

from src.config import Config, get_config
from src.database import get_session
from src.models import UserPreferences

log = structlog.get_logger()
```

> **Important:** The `log = structlog.get_logger()` line must be preserved. The plan shows only the changed lines; do not delete `log` when updating imports.

Then, after the `is_valid_hex_color` function and before the database helpers, add:

```python
# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------


def _discover_fonts(
    fonts_dir: Path = Config.FONTS_DIR,
    current_value: str | None = None,
) -> list[str]:
    """Discover font family names from TTF files in fonts_dir.

    Args:
        fonts_dir: Directory to scan for ``*.ttf`` files.
            Defaults to :data:`Config.FONTS_DIR` (``fonts/``).
        current_value: Currently saved font family name.  If provided and
            not in the discovered list, it is prepended so the saved value
            is never silently dropped.

    Returns:
        Alphabetically sorted list of internal font family names.
        Falls back to ``["Arial"]`` when the directory is empty or all
        files fail to parse.
    """
    names: list[str] = []
    for ttf_path in sorted(fonts_dir.glob("*.ttf")):
        try:
            font = TTFont(str(ttf_path))
            name_table = font["name"]
            family: str | None = None
            # Prefer nameID 1 (Family name), fall back to nameID 4 (Full name)
            for name_id in (1, 4):
                for record in name_table.names:
                    if record.nameID == name_id:
                        try:
                            family = record.toUnicode()
                            break
                        except Exception:
                            continue
                if family:
                    break
            if family:
                names.append(family)
        except Exception:
            log.warning("settings.discover_fonts.parse_error", path=str(ttf_path))

    names = sorted(set(names))
    if not names:
        names = ["Arial"]
    if current_value and current_value not in names:
        names = [current_value] + names
    return names
```

- [ ] **Step 1.4: Run tests — must pass**

```bash
uv run pytest tests/unit/test_settings.py::TestDiscoverFonts -v
```
Expected: all 7 tests pass.

- [ ] **Step 1.5: Run full test suite — must still be 100%**

```bash
uv run pytest tests/ -q
```
Expected: all tests pass, `Total coverage: 100.00%`.

- [ ] **Step 1.6: Run linter**

```bash
uv run ruff check src/pages/settings.py tests/unit/test_settings.py
```
Expected: no errors. Fix any `I001` import ordering if flagged.

- [ ] **Step 1.7: Commit**

```bash
git add src/pages/settings.py tests/unit/test_settings.py
git commit -m "feat: add _discover_fonts() TTF scanner to settings page"
```

---

## Task 2: HTML Builder Helpers

**Files:**
- Modify: `src/pages/settings.py` — add `_build_typo_html()` and `_build_phone_html()`
- Modify: `tests/unit/test_settings.py` — add `TestBuildPreviewHtml` class

---

- [ ] **Step 2.1: Write failing tests for the HTML builders**

Add this class to `tests/unit/test_settings.py` (after `TestDiscoverFonts`, before `TestLoadPrefs`):

```python
# ---------------------------------------------------------------------------
# _build_typo_html / _build_phone_html
# ---------------------------------------------------------------------------


class TestBuildPreviewHtml:
    """Tests for the preview HTML builder functions."""

    def test_typo_html_contains_font_color(self) -> None:
        """Typography card HTML includes the font color."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FF0000",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "#FF0000" in html

    def test_typo_html_contains_font_size(self) -> None:
        """Typography card HTML includes the font size in px."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=36,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "36px" in html

    def test_typo_html_contains_stroke_color(self) -> None:
        """Typography card HTML includes the stroke color."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#ABCDEF",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "#ABCDEF" in html

    def test_typo_html_contains_stroke_width(self) -> None:
        """Typography card HTML includes the stroke width."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=3.5,
            shadow_offset=1,
        )
        assert "3.5px" in html

    def test_typo_html_contains_sample_text(self) -> None:
        """Typography card HTML contains the sample subtitle text."""
        from src.pages.settings import _build_typo_html

        html = _build_typo_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
        )
        assert "Every moment" in html

    def test_phone_html_contains_subtitle_y_position(self) -> None:
        """Phone frame HTML positions the text at the specified Y percentage."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=80,
        )
        assert "80%" in html

    def test_phone_html_contains_font_color(self) -> None:
        """Phone frame HTML includes the font color."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#12FF34",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=75,
        )
        assert "#12FF34" in html

    def test_phone_html_contains_sample_text(self) -> None:
        """Phone frame HTML contains the sample subtitle text."""
        from src.pages.settings import _build_phone_html

        html = _build_phone_html(
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            shadow_offset=1,
            subtitle_y=75,
        )
        assert "Every moment" in html
```

- [ ] **Step 2.2: Run failing tests**

```bash
uv run pytest tests/unit/test_settings.py::TestBuildPreviewHtml -v
```
Expected: `ImportError` — functions don't exist yet.

- [ ] **Step 2.3: Add `_build_typo_html()` and `_build_phone_html()` to `settings.py`**

Add after `_discover_fonts()` and before the database helpers section:

```python
# ---------------------------------------------------------------------------
# Preview HTML builders
# ---------------------------------------------------------------------------

_PREVIEW_SAMPLE_TEXT = "Every moment is a fresh beginning."


def _build_typo_html(
    font_family: str,
    font_size: int,
    font_color: str,
    stroke_color: str,
    stroke_width: float,
    shadow_offset: int,
) -> str:
    """Build the HTML string for the typography preview card.

    Args:
        font_family: CSS font-family value.
        font_size: Font size in points (rendered as px in the browser).
        font_color: Hex colour string for the text, e.g. ``'#FFFFFF'``.
        stroke_color: Hex colour string for the stroke/shadow.
        stroke_width: Stroke width in pixels.
        shadow_offset: Drop-shadow offset in pixels.

    Returns:
        An HTML string suitable for use in ``ui.html().set_content()``.
    """
    style = (
        f"color: {font_color};"
        f"font-family: {font_family}, sans-serif;"
        f"font-size: {font_size}px;"
        f"font-weight: bold;"
        f"-webkit-text-stroke: {stroke_width}px {stroke_color};"
        f"text-shadow: {shadow_offset}px {shadow_offset}px 2px {stroke_color};"
    )
    return (
        '<div style="background-color: #1a1a1a; padding: 16px; border-radius: 8px;">'
        f'<span style="{style}">'
        f"{_PREVIEW_SAMPLE_TEXT.replace(' a ', ' a<br>')}"
        "</span>"
        "</div>"
    )


def _build_phone_html(
    font_family: str,
    font_size: int,
    font_color: str,
    stroke_color: str,
    stroke_width: float,
    shadow_offset: int,
    subtitle_y: int,
) -> str:
    """Build the HTML string for the 9:16 phone-frame preview.

    Args:
        font_family: CSS font-family value.
        font_size: Full font size in points; scaled down for the small frame.
        font_color: Hex colour string for the text.
        stroke_color: Hex colour string for the stroke/shadow.
        stroke_width: Stroke width in pixels.
        shadow_offset: Drop-shadow offset in pixels.
        subtitle_y: Vertical position as a percentage from the top of the frame.

    Returns:
        An HTML string suitable for use in ``ui.html().set_content()``.
    """
    scaled_size = max(8, font_size // 3)
    text_style = (
        f"color: {font_color};"
        f"font-family: {font_family}, sans-serif;"
        f"font-size: {scaled_size}px;"
        f"font-weight: bold;"
        f"-webkit-text-stroke: {stroke_width}px {stroke_color};"
        f"text-shadow: {shadow_offset}px {shadow_offset}px 2px {stroke_color};"
    )
    return (
        '<div style="width: 120px; height: 213px; margin: 16px auto;'
        " background-color: #1a1a1a; border: 2px solid #555;"
        ' border-radius: 8px; position: relative; overflow: hidden;">'
        f'<span style="position: absolute; left: 50%;'
        f" transform: translateX(-50%); top: {subtitle_y}%;"
        f' text-align: center; white-space: nowrap; {text_style}">'
        f"{_PREVIEW_SAMPLE_TEXT}"
        "</span>"
        "</div>"
    )
```

- [ ] **Step 2.4: Run tests — must pass**

```bash
uv run pytest tests/unit/test_settings.py::TestBuildPreviewHtml -v
```
Expected: all 8 tests pass.

- [ ] **Step 2.5: Run full suite**

```bash
uv run pytest tests/ -q
```
Expected: all tests pass, 100% coverage.

- [ ] **Step 2.6: Lint**

```bash
uv run ruff check src/pages/settings.py tests/unit/test_settings.py
```

- [ ] **Step 2.7: Commit**

```bash
git add src/pages/settings.py tests/unit/test_settings.py
git commit -m "feat: add preview HTML builder helpers to settings page"
```

---

## Task 3: Wire `render()` — Dropdown, Labels, Preview, Reset

This is the largest task. It rewrites `render()` to store label references, replace the font input with a select, add the preview `ui.html()` elements, define `_update_preview()` as a closure, wire all callbacks, and update `reset()`. Tests are updated in parallel.

**Files:**
- Modify: `src/pages/settings.py` — rewrite `render()`
- Modify: `tests/unit/test_settings.py` — update mock helpers; add new tests

---

- [ ] **Step 3.1: Update mock helpers to support `ui.html` and label tracking**

In `tests/unit/test_settings.py`, make two changes:

**Change 1 — `_build_capturing_ui_mock`:**

Add `"html"` to the for-loop (line 517) to initialise the attribute before override:
```python
    for name in ("column", "card", "row", "label", "input", "textarea", "select", "html"):
        getattr(mock_ui, name).side_effect = _make_elem
```

Then after line `mock_ui.notify.side_effect = _notify`, add the html-element and label-element tracking side-effects:

```python
    html_elements: list[MagicMock] = []
    captured["html_elements"] = html_elements

    def _html(*_args: object, **_kwargs: object) -> MagicMock:
        elem = _make_elem()
        html_elements.append(elem)
        return elem

    mock_ui.html.side_effect = _html

    label_elements: list[MagicMock] = []
    captured["label_elements"] = label_elements

    def _label_capture(*_args: object, **_kwargs: object) -> MagicMock:
        elem = _make_elem(*_args, **_kwargs)
        label_elements.append(elem)
        return elem

    mock_ui.label.side_effect = _label_capture
```

(Both `side_effect` assignments override the initial `_make_elem` set in the for-loop above — this is intentional.)

**Change 2 — `_build_ui_mock`:**

Add `"html"` to the widget name tuple:
```python
    for name in (
        "column",
        "card",
        "row",
        "label",
        "input",
        "html",
        "slider",
        "color_input",
        "textarea",
        "select",
        "upload",
        "button",
        "notify",
    ):
```

- [ ] **Step 3.1.5: Verify existing tests still pass after mock changes**

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: all existing tests pass (the mock additions are additive; no existing behaviour changes).

- [ ] **Step 3.2: Add `_discover_fonts` autouse fixture and new integration test stubs**

After Step 3.4, `render()` will call `_discover_fonts(current_value=prefs.font_family)`, which scans the real `fonts/` directory. To maintain unit test isolation, add an `autouse` fixture to `TestHandlerCallbacks` that patches it for the entire class. This covers all eight pre-existing tests and the two new tests in one change.

**Add this fixture inside `class TestHandlerCallbacks`, as the first member (before the existing test methods):**

```python
    @pytest.fixture(autouse=True)
    def _patch_discover_fonts(self) -> None:  # type: ignore[override]
        """Patch _discover_fonts for all TestHandlerCallbacks tests.

        After render() calls _discover_fonts(), without this patch every
        TestHandlerCallbacks test would scan the real fonts/ directory,
        violating unit test isolation.  Tests that need a different return
        value can override with their own explicit patch inside the test.
        """
        with patch("src.pages.settings._discover_fonts", return_value=["Arial"]):
            yield
```

> **Note:** The two new tests added below (`test_font_family_uses_select_not_input` and `test_reset_calls_update_preview`) also include explicit `patch("src.pages.settings._discover_fonts", ...)` in their own `with` blocks. The inner patch takes precedence — both are redundant, but the explicit inner patch documents intent clearly and the `autouse` fixture is a safety net.

**Add these two tests to `TestHandlerCallbacks` in `tests/unit/test_settings.py`:**

```python
    async def test_font_family_uses_select_not_input(
        self, tmp_path: Path
    ) -> None:
        """font_family widget is a ui.select, not a ui.input."""
        import src.pages.settings as settings_mod

        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, _captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
        ):
            await settings_mod.render()

        # ui.select must have been called with label="Font Family"
        select_calls = mock_ui.select.call_args_list
        font_family_select = any(
            "Font Family" in str(call) for call in select_calls
        )
        assert font_family_select, (
            f"ui.select not called with Font Family; calls={select_calls}"
        )

        # ui.input must NOT have been called with label="Font Family"
        input_calls = mock_ui.input.call_args_list
        font_family_input = any(
            "Font Family" in str(call) for call in input_calls
        )
        assert not font_family_input, (
            f"ui.input was incorrectly called with Font Family; calls={input_calls}"
        )

    async def test_reset_calls_update_preview(self, tmp_path: Path) -> None:
        """reset() triggers _update_preview(), updating both html preview elements."""
        import src.pages.settings as settings_mod

        notify_calls: list[tuple] = []
        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock(notify_calls=notify_calls)

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
        ):
            await settings_mod.render()
            reset_cb = next(
                (v for k, v in captured.items() if "Reset" in k), None
            )
            assert reset_cb is not None, (
                f"Reset callback missing; keys={list(captured)}"
            )
            # Clear call counts from the initial _update_preview() call at render time
            html_elements: list[MagicMock] = captured["html_elements"]  # type: ignore[assignment]
            for elem in html_elements:
                elem.set_content.reset_mock()

            reset_cb()  # type: ignore[operator]

        # After reset, _update_preview() must have been called — both html elements updated
        assert len(html_elements) >= 2, (
            f"Expected ≥2 html elements (typo + phone); got {len(html_elements)}"
        )
        assert html_elements[0].set_content.called, "typo_preview.set_content not called after reset"
        assert html_elements[1].set_content.called, "phone_preview.set_content not called after reset"
```

- [ ] **Step 3.2.5: Add `TestUpdatePreview` direct tests (also red until render() is updated)**

> **Testing scope note:** These tests verify `_update_preview()` via its initial call at the end of `render()`. The `on_change=` wiring for `font_color` and `stroke_color` (set in their constructors) is not exercised by these tests because `_build_capturing_ui_mock`'s `_color_input` side-effect discards the `on_change` kwarg. This is an acceptable gap: the real NiceGUI wires `on_change` correctly, and the design spec's Testing section does not explicitly require a test for color-input change events triggering `_update_preview`.

Add this class to `tests/unit/test_settings.py` (after `TestHandlerCallbacks`, before the `Helpers` section):

```python
# ---------------------------------------------------------------------------
# _update_preview closure — verified via initial call at end of render()
# ---------------------------------------------------------------------------


class TestUpdatePreview:
    """Verify that _update_preview() updates labels and preview HTML elements.

    _update_preview is a closure inside render().  It is called once at the
    end of render() to initialise the preview.  These tests drive it through
    that initial call using specific pref values and assert on the resulting
    mock state.
    """

    async def test_update_preview_sets_label_texts(self, tmp_path: Path) -> None:
        """_update_preview() calls set_text on all six slider labels correctly."""
        import src.pages.settings as settings_mod

        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        prefs = _make_default_prefs()
        prefs.font_size = 32
        prefs.font_stroke_width = 3.5
        prefs.font_shadow_offset = 2
        prefs.subtitle_position_y = 80
        prefs.min_clip_length = 20
        prefs.max_clip_length = 50
        mock_ui, captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=prefs),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
        ):
            await settings_mod.render()

        # Collect every set_text() call across all captured label mocks
        set_text_args: list[str] = []
        for elem in captured["label_elements"]:  # type: ignore[index]
            for call in elem.set_text.call_args_list:
                if call.args:
                    set_text_args.append(str(call.args[0]))

        assert any("Font Size: 32pt" in s for s in set_text_args), (
            f"Expected 'Font Size: 32pt'; got set_text calls: {set_text_args}"
        )
        assert any("Stroke Width: 3.5" in s for s in set_text_args), (
            f"Expected 'Stroke Width: 3.5'; got: {set_text_args}"
        )
        assert any("Shadow Offset: 2px" in s for s in set_text_args), (
            f"Expected 'Shadow Offset: 2px'; got: {set_text_args}"
        )
        assert any("Subtitle Y Position: 80% from top" in s for s in set_text_args), (
            f"Expected 'Subtitle Y Position: 80% from top'; got: {set_text_args}"
        )
        assert any("Min Clip Length: 20s" in s for s in set_text_args), (
            f"Expected 'Min Clip Length: 20s'; got: {set_text_args}"
        )
        assert any("Max Clip Length: 50s" in s for s in set_text_args), (
            f"Expected 'Max Clip Length: 50s'; got: {set_text_args}"
        )

    async def test_update_preview_calls_set_content_on_both_html_elements(
        self, tmp_path: Path
    ) -> None:
        """_update_preview() calls set_content() on both typo and phone html elements."""
        import src.pages.settings as settings_mod

        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        mock_ui, captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=_make_default_prefs()),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
        ):
            await settings_mod.render()

        html_elements: list[MagicMock] = captured["html_elements"]  # type: ignore[assignment]
        assert len(html_elements) >= 2, (
            f"Expected ≥2 html elements (typo + phone frame); got {len(html_elements)}"
        )
        assert html_elements[0].set_content.called, (
            "typo_preview.set_content() was not called by _update_preview()"
        )
        assert html_elements[1].set_content.called, (
            "phone_preview.set_content() was not called by _update_preview()"
        )

    async def test_update_preview_preview_html_contains_font_settings(
        self, tmp_path: Path
    ) -> None:
        """The HTML passed to typo_preview.set_content() contains color, size, and stroke."""
        import src.pages.settings as settings_mod

        cfg_mock = MagicMock()
        cfg_mock.temp_dir = tmp_path
        prefs = _make_default_prefs()
        prefs.font_color = "#FF1234"
        prefs.font_size = 28
        prefs.font_stroke_width = 4.0
        mock_ui, captured = _build_capturing_ui_mock()

        with (
            patch(
                "src.pages.settings.load_prefs",
                new=AsyncMock(return_value=prefs),
            ),
            patch("src.pages.settings.get_config", return_value=cfg_mock),
            patch("src.pages.settings.ui", new=mock_ui),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
        ):
            await settings_mod.render()

        html_elements: list[MagicMock] = captured["html_elements"]  # type: ignore[assignment]
        assert html_elements, "No html elements captured"
        typo_html = str(html_elements[0].set_content.call_args)
        assert "#FF1234" in typo_html, f"Expected '#FF1234' in typo HTML; got: {typo_html}"
        assert "28px" in typo_html, f"Expected '28px' in typo HTML; got: {typo_html}"
        assert "4.0px" in typo_html, f"Expected '4.0px' in typo HTML; got: {typo_html}"
```

- [ ] **Step 3.3: Run the new tests — they must fail**

```bash
uv run pytest tests/unit/test_settings.py::TestHandlerCallbacks::test_font_family_uses_select_not_input tests/unit/test_settings.py::TestHandlerCallbacks::test_reset_calls_update_preview tests/unit/test_settings.py::TestUpdatePreview -v
```
Expected: FAIL (render() still has `ui.input` for font family; no html elements created).

- [ ] **Step 3.4: Rewrite `render()` in `settings.py`**

Replace the entire `render()` function (lines 106–317) with the implementation below. Key changes vs. the original:
- `font_options = _discover_fonts(current_value=prefs.font_family)` at top
- `ui.input` for font_family → `ui.select(options=font_options, ...)`
- Every slider: label reference stored, slider reference stored
- `typo_preview = ui.html("")` and `phone_preview = ui.html("")` added at bottom of Font Settings card
- `_update_preview()` closure defined after all widgets
- All 6 sliders wired: `.on("change", lambda _: _update_preview())`
- `font_family`, `font_color`, `stroke_color` wired: `.on("change", lambda _: _update_preview())`
- `_update_preview()` called once to initialise
- `reset()` calls `_update_preview()` at end

```python
async def render() -> None:
    """Render the settings page with all preference controls.

    Loads existing preferences on page load and populates every control.
    Save persists all values; Reset restores defaults without touching the DB.
    """
    prefs = await load_prefs()
    config = get_config()
    font_options = _discover_fonts(current_value=prefs.font_family)

    # Mutable state for logo path — updated by upload handler
    logo_state: dict[str, str | None] = {"path": prefs.logo_path}

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        ui.label("Settings").classes("text-3xl font-bold")

        # ------------------------------------------------------------------ #
        # Font settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Font Settings").classes("text-xl font-semibold mb-4")

            font_family = ui.select(
                label="Font Family",
                options=font_options,
                value=prefs.font_family,
                on_change=lambda _: _update_preview(),
            ).classes("w-full")

            size_label = ui.label(f"Font Size: {prefs.font_size}pt").classes("mt-4")
            font_size = ui.slider(min=8, max=72, value=prefs.font_size, step=1).classes(
                "w-full"
            )

            font_color = ui.color_input(
                label="Font Color",
                value=prefs.font_color,
                on_change=lambda _: _update_preview(),
            ).classes("w-full mt-4")

            stroke_color = ui.color_input(
                label="Stroke Color",
                value=prefs.font_stroke_color,
                on_change=lambda _: _update_preview(),
            ).classes("w-full mt-4")

            stroke_label = ui.label(
                f"Stroke Width: {prefs.font_stroke_width:.1f}"
            ).classes("mt-4")
            stroke_width = ui.slider(
                min=0, max=8, value=prefs.font_stroke_width, step=0.5
            ).classes("w-full")

            shadow_label = ui.label(
                f"Shadow Offset: {prefs.font_shadow_offset}px"
            ).classes("mt-4")
            shadow_offset = ui.slider(
                min=0, max=8, value=prefs.font_shadow_offset, step=1
            ).classes("w-full")

            subtitle_label = ui.label(
                f"Subtitle Y Position: {prefs.subtitle_position_y}% from top"
            ).classes("mt-4")
            subtitle_y = ui.slider(
                min=50, max=95, value=prefs.subtitle_position_y, step=1
            ).classes("w-full")

            # Live preview
            ui.label("Preview").classes("mt-6 text-sm font-semibold text-gray-500")
            typo_preview = ui.html("").classes("w-full mt-2")
            phone_preview = ui.html("").classes("w-full mt-4")

        # ------------------------------------------------------------------ #
        # Clip settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Clip Settings").classes("text-xl font-semibold mb-4")

            min_label = ui.label(f"Min Clip Length: {prefs.min_clip_length}s").classes(
                "mt-2"
            )
            min_clip = ui.slider(
                min=10, max=60, value=prefs.min_clip_length, step=1
            ).classes("w-full")

            max_label = ui.label(f"Max Clip Length: {prefs.max_clip_length}s").classes(
                "mt-4"
            )
            max_clip = ui.slider(
                min=10, max=90, value=prefs.max_clip_length, step=1
            ).classes("w-full")

            output_resolution = ui.select(
                label="Output Resolution",
                options=["720p", "1080p"],
                value=prefs.output_resolution,
            ).classes("w-full mt-4")

        # ------------------------------------------------------------------ #
        # AI settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("AI Settings").classes("text-xl font-semibold mb-4")

            ai_prompt = ui.textarea(
                label="Custom AI Prompt",
                value=prefs.ai_prompt or "",
                placeholder="Leave blank to use the default prompt…",
            ).classes("w-full").props("rows=6")

        # ------------------------------------------------------------------ #
        # Logo settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Logo").classes("text-xl font-semibold mb-4")

            logo_display = ui.label(
                f"Current logo: {prefs.logo_path or 'None'}"
            ).classes("text-sm text-gray-500")

            def handle_logo_upload(e: object) -> None:
                """Persist the uploaded logo file and update the display label.

                Args:
                    e: NiceGUI UploadEventArguments carrying ``name`` and
                       ``content`` (file-like bytes object).
                """
                name: str = getattr(e, "name", "logo")
                content = getattr(e, "content", None)
                if content is None:
                    ui.notify("Upload failed — no content received.", color="negative")
                    return

                logo_dir = config.temp_dir / "logo"
                logo_dir.mkdir(parents=True, exist_ok=True)
                dest = logo_dir / name
                dest.write_bytes(content.read())
                logo_state["path"] = str(dest)
                logo_display.text = f"Current logo: {dest}"
                log.info("settings.logo_uploaded", path=str(dest))

            ui.upload(
                label="Upload Logo",
                on_upload=handle_logo_upload,
            ).props('accept="image/*"').classes("mt-2")

            def clear_logo() -> None:
                """Clear the stored logo path from state and the display."""
                logo_state["path"] = None
                logo_display.text = "Current logo: None"
                log.info("settings.logo_cleared")

            ui.button("Clear Logo", on_click=clear_logo).classes(
                "mt-2 bg-gray-500 text-white"
            )

        # ------------------------------------------------------------------ #
        # Save / Reset buttons
        # ------------------------------------------------------------------ #
        with ui.row().classes("w-full gap-4 mt-4"):

            async def save() -> None:
                """Validate and persist all settings to the database."""
                min_val = int(min_clip.value)
                max_val = int(max_clip.value)
                if max_val < min_val:
                    ui.notify(
                        "Max clip length must be >= min clip length.",
                        color="negative",
                    )
                    return

                font_color_val: str = font_color.value or "#FFFFFF"
                stroke_color_val: str = stroke_color.value or "#000000"

                if not is_valid_hex_color(font_color_val):
                    ui.notify(
                        f"Invalid font color '{font_color_val}'. Use #RRGGBB format.",
                        color="negative",
                    )
                    return

                if not is_valid_hex_color(stroke_color_val):
                    ui.notify(
                        f"Invalid stroke color '{stroke_color_val}'. Use #RRGGBB format.",
                        color="negative",
                    )
                    return

                await save_prefs(
                    {
                        "font_family": font_family.value or "Arial",
                        "font_size": int(font_size.value),
                        "font_color": font_color_val,
                        "font_stroke_color": stroke_color_val,
                        "font_stroke_width": float(stroke_width.value),
                        "font_shadow_offset": int(shadow_offset.value),
                        "subtitle_position_y": int(subtitle_y.value),
                        "min_clip_length": min_val,
                        "max_clip_length": max_val,
                        "output_resolution": output_resolution.value or "1080p",
                        "ai_prompt": ai_prompt.value or None,
                        "logo_path": logo_state["path"],
                    }
                )
                ui.notify("Settings saved!", color="positive")

            def reset() -> None:
                """Restore all controls to their default values."""
                # _update_preview is a co-local in render() defined after this
                # `with` block.  Python does NOT have block scope — `with`
                # blocks share the enclosing function's local namespace.
                # _update_preview will exist in render()'s locals by the time
                # reset() is ever called (user click happens after render()
                # returns).  This is safe; mypy strict=false does not flag it.
                font_family.value = "Arial"
                font_size.value = 24
                font_color.value = "#FFFFFF"
                stroke_color.value = "#000000"
                stroke_width.value = 2.0
                shadow_offset.value = 1
                subtitle_y.value = 75
                min_clip.value = 15
                max_clip.value = 45
                output_resolution.value = "1080p"
                ai_prompt.value = ""
                logo_state["path"] = None
                logo_display.text = "Current logo: None"
                _update_preview()
                ui.notify("Settings reset to defaults.", color="info")

            ui.button("Save Settings", on_click=save).classes(
                "bg-green-600 text-white flex-1"
            )
            ui.button("Reset to Defaults", on_click=reset).classes(
                "bg-gray-500 text-white flex-1"
            )

    # ---------------------------------------------------------------------- #
    # Reactive wiring — define after all widget references exist
    # ---------------------------------------------------------------------- #

    def _update_preview() -> None:
        """Update all slider labels and refresh the live preview HTML."""
        fam = str(font_family.value or "Arial")
        size = int(font_size.value)
        fc = str(font_color.value or "#FFFFFF")
        sc = str(stroke_color.value or "#000000")
        sw = float(stroke_width.value)
        so = int(shadow_offset.value)
        sy = int(subtitle_y.value)

        size_label.set_text(f"Font Size: {size}pt")
        stroke_label.set_text(f"Stroke Width: {sw:.1f}")
        shadow_label.set_text(f"Shadow Offset: {so}px")
        subtitle_label.set_text(f"Subtitle Y Position: {sy}% from top")
        min_label.set_text(f"Min Clip Length: {int(min_clip.value)}s")
        max_label.set_text(f"Max Clip Length: {int(max_clip.value)}s")

        typo_preview.set_content(_build_typo_html(fam, size, fc, sc, sw, so))
        phone_preview.set_content(_build_phone_html(fam, size, fc, sc, sw, so, sy))

    # Wire all sliders — update on release only (Quasar `change` event).
    # Dropdowns (font_family) and colour inputs (font_color, stroke_color)
    # are wired via on_change= kwarg in their constructors above.
    font_size.on("change", lambda _: _update_preview())
    stroke_width.on("change", lambda _: _update_preview())
    shadow_offset.on("change", lambda _: _update_preview())
    subtitle_y.on("change", lambda _: _update_preview())
    min_clip.on("change", lambda _: _update_preview())
    max_clip.on("change", lambda _: _update_preview())

    # Initialise preview with saved values
    _update_preview()
```

**Important note on `_update_preview` closure placement:** `_update_preview` is defined AFTER the `with ui.column()` block closes, so all widget references (`font_family`, `size_label`, etc.) are in scope. The `reset()` function references `_update_preview()` by name — Python closures resolve names at call time, not definition time, so calling `reset()` after `_update_preview` is defined works correctly even though `reset()` was defined earlier inside the `with` block.

> **⚠ Warning:** Do NOT run `uv run pytest tests/` (the full suite) between Steps 3.4 and 3.6. After Step 3.4, `render()` calls `_discover_fonts()` and `ui.html()`, but the existing `TestRender` tests have not yet been updated to patch these. Running the full suite here will produce failures. Only run the targeted tests specified in each step until Step 3.7 clears the full suite.

- [ ] **Step 3.5: Run the new integration tests**

```bash
uv run pytest tests/unit/test_settings.py::TestHandlerCallbacks::test_font_family_uses_select_not_input tests/unit/test_settings.py::TestHandlerCallbacks::test_reset_calls_update_preview -v
```
Expected: both pass.

- [ ] **Step 3.6: Update `TestRender` tests to patch `_discover_fonts` (mandatory)**

`_discover_fonts` is called inside `render()` and will attempt to scan the real `fonts/` directory. Always patch it in `TestRender`. Update both tests now, before running anything:

```python
    async def test_render_with_existing_prefs(self) -> None:
        """render() runs without error when DB returns an existing row."""
        existing = UserPreferences(
            id=1,
            font_family="Comic Sans",
            font_size=18,
            font_color="#FF00FF",
            font_stroke_color="#000000",
            font_stroke_width=1.0,
            font_shadow_offset=0,
            subtitle_position_y=70,
            min_clip_length=10,
            max_clip_length=30,
            output_resolution="720p",
            ai_prompt="Be concise.",
            logo_path="/tmp/logo.png",
        )

        with (
            patch("src.pages.settings.load_prefs", new=AsyncMock(return_value=existing)),
            patch("src.pages.settings.get_config", return_value=_mock_config()),
            patch("src.pages.settings._discover_fonts", return_value=["Arial", "Comic Sans"]),
            patch("src.pages.settings.ui", new=_build_ui_mock()),
        ):
            from src.pages.settings import render

            await render()

    async def test_render_with_no_existing_prefs(self) -> None:
        """render() runs without error when DB returns default preferences."""
        defaults = UserPreferences(
            id=1,
            font_family="Arial",
            font_size=24,
            font_color="#FFFFFF",
            font_stroke_color="#000000",
            font_stroke_width=2.0,
            font_shadow_offset=1,
            subtitle_position_y=75,
            min_clip_length=15,
            max_clip_length=45,
            output_resolution="1080p",
            ai_prompt=None,
            logo_path=None,
        )

        with (
            patch("src.pages.settings.load_prefs", new=AsyncMock(return_value=defaults)),
            patch("src.pages.settings.get_config", return_value=_mock_config()),
            patch("src.pages.settings._discover_fonts", return_value=["Arial"]),
            patch("src.pages.settings.ui", new=_build_ui_mock()),
        ):
            from src.pages.settings import render

            await render()
```

- [ ] **Step 3.7: Run the full settings test suite**

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: all tests pass.

- [ ] **Step 3.8: Run full test suite — must be 100%**

```bash
uv run pytest tests/ -q
```
Expected: all tests pass, `Total coverage: 100.00%`.

If coverage < 100%, run:
```bash
uv run pytest tests/ --cov=src --cov-report=term-missing -q 2>&1 | grep "MISS"
```
to find uncovered lines and add tests for them.

- [ ] **Step 3.9: Run linter and type checker**

```bash
uv run ruff check src/pages/settings.py tests/unit/test_settings.py
uv run mypy src/pages/settings.py
```
Expected: no errors. Common issues to fix:
- `mypy` may complain about `font_family.value` being `str | None` vs `str` — use `str(font_family.value or "Arial")`
- `ruff` may flag unused `Path` import if it was already imported — check

- [ ] **Step 3.10: Commit**

```bash
git add src/pages/settings.py tests/unit/test_settings.py
git commit -m "feat: settings page — font dropdown, reactive labels, live preview"
```

---

## Final Verification

- [ ] Run `uv run pytest tests/ -q` — all pass, 100% coverage
- [ ] Run `uv run ruff check src/ tests/` — zero errors
- [ ] Run `uv run mypy src/` — zero errors
- [ ] Manual smoke test: `uv run python -m src.main`, open http://localhost:8008/settings
  - Verify font family shows a dropdown (not a free text input)
  - Drag font size slider → label updates on release → preview updates
  - Drag subtitle Y slider → phone frame text repositions on release
  - Change font color → preview typography card updates
  - Click Reset → all sliders snap back, labels update, preview refreshes
