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
from src.pipeline.subtitles import SubtitleStyle

log = structlog.get_logger()

# Output-resolution preset -> video height in pixels (used for subtitle MarginV).
_RESOLUTION_HEIGHTS: dict[str, int] = {"480p": 854, "720p": 1280, "1080p": 1920}
_DEFAULT_VIDEO_HEIGHT: int = 1920

# ---------------------------------------------------------------------------
# Hex color validation
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def is_valid_hex_color(value: str) -> bool:
    """Return True if *value* is a valid 6-digit CSS hex colour.

    Args:
        value: The string to validate, e.g. ``'#FFFFFF'``.

    Returns:
        True when the string matches ``#RRGGBB`` exactly.
    """
    return bool(_HEX_COLOR_RE.match(value))


# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------


def _extract_font_family(ttf_path: Path) -> str | None:
    """Extract the internal font family name from a single TTF file.

    Prefers nameID 1 (Family name) and falls back to nameID 4 (Full name).
    Records whose ``toUnicode()`` decoding fails are skipped so a later
    record with the same nameID can still supply the name.

    Args:
        ttf_path: Path to a ``*.ttf`` file to inspect.

    Returns:
        The decoded font family name, or ``None`` when the file cannot be
        parsed or no usable name record is present.
    """
    try:
        name_table = TTFont(str(ttf_path))["name"]
    except Exception:
        log.warning("settings.discover_fonts.parse_error", path=str(ttf_path))
        return None

    for name_id in (1, 4):
        for record in name_table.names:
            if record.nameID != name_id:
                continue
            try:
                return str(record.toUnicode())
            except Exception:
                continue
    return None


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
    for ttf_path in fonts_dir.glob("*.ttf"):
        family = _extract_font_family(ttf_path)
        if family:
            names.append(family)

    names = sorted(set(names))
    if not names:
        names = ["Arial"]
    if current_value and current_value not in names:
        names = [current_value] + names
    return names


# ---------------------------------------------------------------------------
# Preview HTML builders
# ---------------------------------------------------------------------------

_PREVIEW_SAMPLE_TEXT = "Every moment is a fresh beginning."
_PREVIEW_SAMPLE_TEXT_BR = _PREVIEW_SAMPLE_TEXT.replace(" a ", " a<br>")
_PREVIEW_BG_COLOR = "#1a1a1a"


def _build_subtitle_style(
    font_family: str,
    font_size: int,
    font_color: str,
    stroke_color: str,
    stroke_width: float,
    shadow_offset: int,
) -> str:
    """Build the common CSS style string for subtitle text in previews.

    Args:
        font_family: CSS font-family value.
        font_size: Font size in CSS pixels.
        font_color: Hex colour string for the text.
        stroke_color: Hex colour string for the stroke/shadow.
        stroke_width: Stroke width in pixels.
        shadow_offset: Drop-shadow offset in pixels.

    Returns:
        A semicolon-separated CSS style string.
    """
    return (
        f"color: {font_color};"
        f"font-family: {font_family}, sans-serif;"
        f"font-size: {font_size}px;"
        f"font-weight: bold;"
        f"-webkit-text-stroke: {stroke_width}px {stroke_color};"
        f"text-shadow: {shadow_offset}px {shadow_offset}px 2px {stroke_color};"
    )


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
    style = _build_subtitle_style(font_family, font_size, font_color, stroke_color, stroke_width, shadow_offset)
    return (
        f'<div style="background-color: {_PREVIEW_BG_COLOR}; padding: 16px; border-radius: 8px;">'
        f'<span style="{style}">'
        f"{_PREVIEW_SAMPLE_TEXT_BR}"
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
    scaled_size = max(8, round(font_size * 0.4))
    scale = scaled_size / font_size if font_size > 0 else 1.0
    scaled_sw = round(stroke_width * scale, 1)
    scaled_so = max(1, round(shadow_offset * scale))
    text_style = _build_subtitle_style(font_family, scaled_size, font_color, stroke_color, scaled_sw, scaled_so)
    return (
        '<div style="width: 180px; height: 320px; margin: 16px auto;'
        f" background-color: {_PREVIEW_BG_COLOR}; border: 2px solid #555;"
        ' border-radius: 8px; position: relative; overflow: hidden;">'
        f'<span style="position: absolute; left: 50%;'
        f" transform: translateX(-50%); top: {subtitle_y}%;"
        f' text-align: center; width: 90%; white-space: normal; {text_style}">'
        f"{_PREVIEW_SAMPLE_TEXT}"
        "</span>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Preferences -> pipeline style mapping
# ---------------------------------------------------------------------------


def subtitle_style_from_prefs(
    prefs: UserPreferences,
    output_resolution: str | None = None,
) -> SubtitleStyle:
    """Map persisted ``UserPreferences`` onto a pipeline ``SubtitleStyle``.

    This is the seam that the audit's C-1 finding identified as missing: the
    Settings page persists a full subtitle style, but nothing converted it into
    the ``SubtitleStyle`` the clip pipeline consumes, so every clip rendered
    with ``subtitle_style=None`` and no captions.

    Args:
        prefs: The persisted user preferences row.
        output_resolution: Resolution preset whose height drives the subtitle
            ``MarginV`` math. Falls back to ``prefs.output_resolution`` when not
            given.

    Returns:
        A ``SubtitleStyle`` carrying the user's font, size, colors, stroke,
        shadow and vertical position.
    """
    resolution = output_resolution or prefs.output_resolution
    video_height = _RESOLUTION_HEIGHTS.get(resolution, _DEFAULT_VIDEO_HEIGHT)
    return SubtitleStyle(
        font_family=prefs.font_family,
        font_size=prefs.font_size,
        font_color=prefs.font_color,
        outline_color=prefs.font_stroke_color,
        outline_width=prefs.font_stroke_width,
        shadow_depth=float(prefs.font_shadow_offset),
        position_y_pct=prefs.subtitle_position_y,
        video_height=video_height,
    )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def load_prefs() -> UserPreferences:
    """Load user preferences from the database, returning defaults if absent.

    Returns:
        The persisted UserPreferences row, or an in-memory default instance.
    """
    async with get_session() as session:
        prefs = await session.get(UserPreferences, 1)
        if prefs is None:
            log.debug("settings.load_prefs.no_row_found")
            prefs = UserPreferences(
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
        return prefs


async def save_prefs(data: dict) -> None:  # type: ignore[type-arg]
    """Upsert user preferences to the singleton row (id=1).

    Args:
        data: Mapping of field names to new values.
    """
    async with get_session() as session:
        prefs = await session.get(UserPreferences, 1)
        if prefs is None:
            prefs = UserPreferences(id=1)
            session.add(prefs)
            log.debug("settings.save_prefs.creating_row")

        prefs.font_family = data["font_family"]
        prefs.font_size = int(data["font_size"])
        prefs.font_color = data["font_color"]
        prefs.font_stroke_color = data["font_stroke_color"]
        prefs.font_stroke_width = float(data["font_stroke_width"])
        prefs.font_shadow_offset = int(data["font_shadow_offset"])
        prefs.subtitle_position_y = int(data["subtitle_position_y"])
        prefs.min_clip_length = int(data["min_clip_length"])
        prefs.max_clip_length = int(data["max_clip_length"])
        prefs.output_resolution = data["output_resolution"]
        prefs.ai_prompt = data.get("ai_prompt") or None
        prefs.logo_path = data.get("logo_path") or None

        log.info("settings.save_prefs.saved")


# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------


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
            ).classes("w-full")

            size_label = ui.label(f"Font Size: {prefs.font_size}pt").classes("mt-4")
            font_size = ui.slider(min=8, max=72, value=prefs.font_size, step=1).classes("w-full")

            font_color = ui.color_input(
                label="Font Color",
                value=prefs.font_color,
            ).classes("w-full mt-4")

            stroke_color = ui.color_input(
                label="Stroke Color",
                value=prefs.font_stroke_color,
            ).classes("w-full mt-4")

            stroke_label = ui.label(f"Stroke Width: {prefs.font_stroke_width:.1f}").classes("mt-4")
            stroke_width = ui.slider(min=0, max=8, value=prefs.font_stroke_width, step=0.5).classes("w-full")

            shadow_label = ui.label(f"Shadow Offset: {prefs.font_shadow_offset}px").classes("mt-4")
            shadow_offset = ui.slider(min=0, max=8, value=prefs.font_shadow_offset, step=1).classes("w-full")

            subtitle_label = ui.label(f"Subtitle Y Position: {prefs.subtitle_position_y}% from top").classes("mt-4")
            subtitle_y = ui.slider(min=50, max=95, value=prefs.subtitle_position_y, step=1).classes("w-full")

            # Live preview
            ui.label("Preview").classes("mt-6 text-sm font-semibold text-gray-500")
            typo_preview = ui.html("", sanitize=False).classes("w-full mt-2")
            phone_preview = ui.html("", sanitize=False).classes("w-full mt-4")

        # ------------------------------------------------------------------ #
        # Clip settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Clip Settings").classes("text-xl font-semibold mb-4")

            min_label = ui.label(f"Min Clip Length: {prefs.min_clip_length}s").classes("mt-2")
            min_clip = ui.slider(min=10, max=60, value=prefs.min_clip_length, step=1).classes("w-full")

            max_label = ui.label(f"Max Clip Length: {prefs.max_clip_length}s").classes("mt-4")
            max_clip = ui.slider(min=10, max=90, value=prefs.max_clip_length, step=1).classes("w-full")

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

            ai_prompt = (
                ui.textarea(
                    label="Custom AI Prompt",
                    value=prefs.ai_prompt or "",
                    placeholder="Leave blank to use the default prompt…",
                )
                .classes("w-full")
                .props("rows=6")
            )

        # ------------------------------------------------------------------ #
        # Logo settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Logo").classes("text-xl font-semibold mb-4")

            logo_display = ui.label(f"Current logo: {prefs.logo_path or 'None'}").classes("text-sm text-gray-500")

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

            ui.button("Clear Logo", on_click=clear_logo).classes("mt-2 bg-gray-500 text-white")

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

            ui.button("Save Settings", on_click=save).classes("bg-green-600 text-white flex-1")
            ui.button("Reset to Defaults", on_click=reset).classes("bg-gray-500 text-white flex-1")

    # ---------------------------------------------------------------------- #
    # Reactive wiring — define after all widget references exist
    # ---------------------------------------------------------------------- #

    def _update_preview(_event: object = None) -> None:
        """Update all slider labels and refresh the live preview HTML."""
        fam = str(font_family.value or "Arial")
        size = int(font_size.value)
        fc = str(font_color.value or "#FFFFFF")
        sc = str(stroke_color.value or "#000000")
        sw = float(stroke_width.value)
        so = int(shadow_offset.value)
        sy = int(subtitle_y.value)
        mc_min = int(min_clip.value)
        mc_max = int(max_clip.value)

        size_label.set_text(f"Font Size: {size}pt")
        stroke_label.set_text(f"Stroke Width: {sw:.1f}")
        shadow_label.set_text(f"Shadow Offset: {so}px")
        subtitle_label.set_text(f"Subtitle Y Position: {sy}% from top")
        min_label.set_text(f"Min Clip Length: {mc_min}s")
        max_label.set_text(f"Max Clip Length: {mc_max}s")

        typo_preview.set_content(_build_typo_html(fam, size, fc, sc, sw, so))
        phone_preview.set_content(_build_phone_html(fam, size, fc, sc, sw, so, sy))

    # Wire all interactive widgets — update on release only (Quasar `change` event).
    font_family.on("change", _update_preview)
    font_color.on("change", _update_preview)
    stroke_color.on("change", _update_preview)
    font_size.on("change", _update_preview)
    stroke_width.on("change", _update_preview)
    shadow_offset.on("change", _update_preview)
    subtitle_y.on("change", _update_preview)
    min_clip.on("change", _update_preview)
    max_clip.on("change", _update_preview)

    # Initialise preview with saved values
    _update_preview()


# end src/pages/settings.py
