# Settings UI Improvements — Design Spec

**Date:** 2026-03-20
**Status:** Approved
**Scope:** `src/pages/settings.py` only

---

## Problem Statement

The Settings page has three usability gaps:

1. **Font Family is a free-text input.** Users must know the exact internal TTF family name that ffmpeg uses for the `ass` subtitle filter. Typos silently break subtitle rendering.
2. **Slider labels are static.** All six sliders show the initial saved value at page load but never update as the user drags. The correct reactive pattern already exists in `home.py` but was not applied to `settings.py`.
3. **No live preview.** There is no way to see what subtitle changes will look like before saving and re-running a clip.

---

## Design

### 1. Font Family Dropdown

**Replace** `ui.input(label="Font Family", ...)` with `ui.select(label="Font Family", ...)`.

**Required import:** `settings.py` currently imports only `get_config` from `src.config`. The `_discover_fonts` default argument requires the `Config` class directly. Add `from src.config import Config, get_config` (or add `Config` to the existing import).

**Font discovery function:**

```python
def _discover_fonts(
    fonts_dir: Path = Config.FONTS_DIR,
    current_value: str | None = None,
) -> list[str]:
```

- Scans `fonts_dir` for all `*.ttf` files.
- For each file, uses `fonttools` (`fonttools.ttLib.TTFont`) to read the `name` table and extract the internal family name (nameID 1, falling back to nameID 4).
- If a file fails to parse, skips it with a `structlog` warning.
- If the resulting list is empty after scanning (or after filtering failures), returns `["Arial"]`.
- Sorts the list alphabetically.
- If `current_value` is provided and not already in the list, prepends it. This ensures the currently saved font family is never silently dropped from the dropdown even if its TTF file was deleted.
- Returns `list[str]` of family names.

Accepting `fonts_dir` as a parameter (defaulting to `Config.FONTS_DIR`) makes the function directly testable via pytest's `tmp_path` fixture without any patching. The `current_value` parameter keeps the "prepend if missing" logic inside the pure helper rather than scattering it across `render()`.

Called once inside the async page handler: `font_options = _discover_fonts(current_value=prefs.font_family)`.

**Dependency:** Add `fonttools` to `[project.dependencies]` in `pyproject.toml`.

---

### 2. Reactive Slider Labels

All six sliders get reactive label updates. Rather than attaching two separate `.on("change", ...)` callbacks per slider (one for the label, one for the preview), the label update is folded inside `_update_preview()`. This means:

1. Create the label: `size_label = ui.label(f"Font Size: {prefs.font_size}pt")`
2. Create the slider: `font_size = ui.slider(min=8, max=72, value=prefs.font_size, step=1)`
3. Wire a single `change` handler: `font_size.on("change", lambda _: _update_preview())`

`_update_preview()` is responsible for both refreshing the preview HTML **and** updating all label texts from the current widget values. This eliminates duplicate callback registration and ensures labels and preview are always in sync.

The `change` event fires on mouse/touch release (not every drag tick). This is Quasar's `QSlider` behavior — `change` fires once on release, `update:model-value` fires every tick. Using `change` provides the "update on release" behavior the user requested without mid-drag flicker.

**Note on event wiring style:** Sliders use `.on("change", callback)` (post-construction event registration). Dropdowns and color inputs use the `on_change=callback` constructor kwarg. Both are valid NiceGUI API; they are equivalent for the `change` event. The difference is stylistic: `.on()` is used when wiring must happen after widget construction (e.g., when the callback closes over a widget created on the next line); `on_change=` is used when the callback is known at construction time.

**All six sliders and their label formats:**

| Slider | Location (card) | Label format |
|--------|----------------|-------------|
| Font Size | Font Settings | `Font Size: {n}pt` |
| Stroke Width | Font Settings | `Stroke Width: {n:.1f}` — uses `.1f` because `step=0.5` produces floats like `2.0`, `2.5` |
| Shadow Offset | Font Settings | `Shadow Offset: {n}px` |
| Subtitle Y Position | Font Settings | `Subtitle Y Position: {n}% from top` |
| Min Clip Length | Clip Settings | `Min Clip Length: {n}s` |
| Max Clip Length | Clip Settings | `Max Clip Length: {n}s` |

All six sliders — including `min_clip` and `max_clip` in the Clip Settings card — receive `.on("change", lambda _: _update_preview())`. Even though the clip-length sliders do not affect the visual preview, `_update_preview()` is responsible for updating their labels too (since label update is folded inside it). Wiring all six sliders to the same function keeps the pattern consistent.

**Reset behavior:** `reset_prefs()` sets `.value` directly on each widget. Programmatic `.value` assignment does not fire NiceGUI's `change` event. Therefore `reset_prefs()` must explicitly call `_update_preview()` after restoring all widget values to keep labels and preview in sync.

---

### 3. Live Preview

A preview section appended at the bottom of the Font Settings card, below the last slider and above the Save/Reset buttons.

**Structure (stacked vertically, full-width):**

```
┌─ Font Settings card ────────────────────────────┐
│  ... existing controls ...                       │
│                                                  │
│  ── Preview ──────────────────────────────────── │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  dark background                         │    │
│  │  "Every moment is a"                     │    │  ← typography card
│  │  "fresh beginning."                      │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌───── 9:16 phone frame (centered) ────────┐    │
│  │  dark 120×213px box                      │    │
│  │                                          │    │
│  │  [subtitle text at Y% from top]          │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  [Save]  [Reset to Defaults]                     │
└──────────────────────────────────────────────────┘
```

**Typography card:** A `ui.html()` element. Content is a `<div>` with:
- `background-color: #1a1a1a; padding: 16px; border-radius: 8px`
- Sample text as a `<span>` styled with `color`, `font-family`, `font-size`, `font-weight: bold`,
  `-webkit-text-stroke: {width}px {stroke_color}`, `text-shadow: {offset}px {offset}px 2px {stroke_color}`

**Phone frame:** A `ui.html()` element. Content is an outer `<div>` with:
- `width: 120px; height: 213px` (9:16), `margin: 16px auto`
- `background-color: #1a1a1a; border: 2px solid #555; border-radius: 8px; position: relative; overflow: hidden`
- Inner `<span>` with `position: absolute; left: 50%; transform: translateX(-50%); top: {y}%; text-align: center; white-space: nowrap` and the same text styles as the typography card

**Sample text:** `"Every moment is a fresh beginning."` (single line in the phone frame; two lines in the typography card via `<br>`).

**`_update_preview()` function:**

Defined in the page scope (closes over all widget references and both `ui.html()` elements). Signature:

```python
def _update_preview() -> None:
```

Responsibilities:
1. Read current values: `font_family.value`, `font_size.value`, `font_color.value`, `stroke_color.value`, `stroke_width.value`, `shadow_offset.value`, `subtitle_y.value`
2. Update all six slider labels via `label.set_text(...)`
3. Build typography card HTML string and call `typo_preview.set_content(html)`
4. Build phone frame HTML string and call `phone_preview.set_content(html)`

The `font_family.value` string is passed directly to the CSS `font-family` property. The preview will only render the font correctly if the family name happens to match a system-installed font in the user's browser; custom TTF files from `fonts/` are not served to the browser. No special handling is needed — pass it through as-is.

**Triggers:**
- All six sliders (Font Size, Stroke Width, Shadow Offset, Subtitle Y Position, Min Clip Length, Max Clip Length): `slider.on("change", lambda _: _update_preview())`
- Font family dropdown: `on_change=lambda _: _update_preview()`
- Font color input: `on_change=lambda _: _update_preview()`
- Stroke color input: `on_change=lambda _: _update_preview()`

`_update_preview()` is called once immediately after all widgets and preview elements are created to initialize the preview with the saved preference values.

`reset_prefs()` calls `_update_preview()` after restoring all widget values (see Section 2).

---

## Files Changed

| File | Change |
|------|--------|
| `src/pages/settings.py` | All three features; add `_discover_fonts()` helper; update `Config` import |
| `pyproject.toml` | Add `fonttools` to `[project.dependencies]` |
| `tests/unit/test_settings.py` | Tests for `_discover_fonts()`, `_update_preview()`, reset sync, mock updates |

---

## Dependencies

- `fonttools` — pure Python, no native code, well-maintained.

---

## Testing

**`_discover_fonts()` unit tests** (direct calls with `tmp_path`):
- `test_discover_fonts_empty_dir`: returns `["Arial"]` when directory has no `.ttf` files
- `test_discover_fonts_with_valid_ttf`: returns sorted family names from real fixture TTF files (use a minimal valid TTF in `tests/fixtures/`)
- `test_discover_fonts_bad_file`: skips unparseable files, returns remaining valid fonts, logs a warning
- `test_discover_fonts_current_value_in_list`: returns normal list when `current_value` is already present
- `test_discover_fonts_current_value_not_in_list`: prepends `current_value` when it is not in the discovered list
- `test_discover_fonts_empty_result_falls_back_to_arial`: returns `["Arial"]` when all TTF files fail to parse

**`_update_preview()` unit tests** (call directly with mock widget objects constructed in the test — no NiceGUI rendering needed):
- `test_update_preview_sets_label_texts`: construct mock label objects and mock slider/select/input objects with known `.value` properties; call `_update_preview()` directly; assert each label mock's `.set_text()` was called with the correctly formatted string
- `test_update_preview_calls_set_content_on_both_html_elements`: assert `typo_preview.set_content()` and `phone_preview.set_content()` are each called exactly once with a non-empty string
- `test_update_preview_preview_html_contains_font_settings`: assert the string passed to `typo_preview.set_content()` contains the expected hex color, font-size value, and stroke-width value

**Integration tests via `TestHandlerCallbacks`:**
- `test_font_family_select_not_input`: verify `ui.select` is called for font family (check the mock call list — `ui.input` should not be called with `label="Font Family"`)
- `test_reset_calls_update_preview`: verify `reset_prefs()` results in `typo_preview.set_content()` and `phone_preview.set_content()` both being called. Assert both `ui.html` element mocks have `.set_content` called at least once after the reset callback fires.

**Required mock updates in `test_settings.py`:**
- Both `_build_capturing_ui_mock()` and `_build_ui_mock()` must add `"html"` to their mocked widget set. The mock for `ui.html` should be a `MagicMock` — `MagicMock`'s `__getattr__` auto-generates `.set_content` as a callable mock, which is sufficient. No explicit `set_content = MagicMock()` attribute assignment is needed; auto-generated is acceptable and consistent with how other widget methods (`.classes()`, `.value`, etc.) are handled in the existing mocks.
- Slider mocks' auto-generated `.on()` from `MagicMock` is sufficient — it accepts calls without error. Callback behavior is tested by calling `_update_preview()` directly, not through event simulation.

---

## Non-Goals

- The preview is a CSS approximation only — it does not call ffmpeg or render an actual ASS subtitle file.
- Custom TTF fonts dropped in `fonts/` are not served to the browser. The CSS `font-family` value will only match system-installed fonts; custom fonts will visually fall back to the browser's default. This is expected and acceptable.
- No font upload UI — users drop `.ttf` files into `fonts/` manually per the existing workflow.
- The phone frame does not show a real video frame or thumbnail.
