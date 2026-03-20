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
    scaled_size = max(8, font_size // 3)
    text_style = _build_subtitle_style(font_family, scaled_size, font_color, stroke_color, stroke_width, shadow_offset)
    return (
        '<div style="width: 120px; height: 213px; margin: 16px auto;'
        f" background-color: {_PREVIEW_BG_COLOR}; border: 2px solid #555;"
        ' border-radius: 8px; position: relative; overflow: hidden;">'
        f'<span style="position: absolute; left: 50%;'
        f" transform: translateX(-50%); top: {subtitle_y}%;"
        f' text-align: center; white-space: nowrap; {text_style}">'
        f"{_PREVIEW_SAMPLE_TEXT}"
        "</span>"
        "</div>"
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

    # Mutable state for logo path — updated by upload handler
    logo_state: dict[str, str | None] = {"path": prefs.logo_path}

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        ui.label("Settings").classes("text-3xl font-bold")

        # ------------------------------------------------------------------ #
        # Font settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Font Settings").classes("text-xl font-semibold mb-4")

            font_family = ui.input(
                label="Font Family",
                value=prefs.font_family,
                placeholder="e.g. Arial, TikTokSans-Regular",
            ).classes("w-full")

            ui.label(f"Font Size: {prefs.font_size}pt").classes("mt-4")
            font_size = ui.slider(min=8, max=72, value=prefs.font_size, step=1).classes(
                "w-full"
            )

            font_color = ui.color_input(
                label="Font Color", value=prefs.font_color
            ).classes("w-full mt-4")

            stroke_color = ui.color_input(
                label="Stroke Color", value=prefs.font_stroke_color
            ).classes("w-full mt-4")

            ui.label(f"Stroke Width: {prefs.font_stroke_width}").classes("mt-4")
            stroke_width = ui.slider(
                min=0, max=8, value=prefs.font_stroke_width, step=0.5
            ).classes("w-full")

            ui.label(f"Shadow Offset: {prefs.font_shadow_offset}px").classes("mt-4")
            shadow_offset = ui.slider(
                min=0, max=8, value=prefs.font_shadow_offset, step=1
            ).classes("w-full")

            ui.label(
                f"Subtitle Y Position: {prefs.subtitle_position_y}% from top"
            ).classes("mt-4")
            subtitle_y = ui.slider(
                min=50, max=95, value=prefs.subtitle_position_y, step=1
            ).classes("w-full")

        # ------------------------------------------------------------------ #
        # Clip settings
        # ------------------------------------------------------------------ #
        with ui.card().classes("w-full"):
            ui.label("Clip Settings").classes("text-xl font-semibold mb-4")

            ui.label(f"Min Clip Length: {prefs.min_clip_length}s").classes("mt-2")
            min_clip = ui.slider(
                min=10, max=60, value=prefs.min_clip_length, step=1
            ).classes("w-full")

            ui.label(f"Max Clip Length: {prefs.max_clip_length}s").classes("mt-4")
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
                ui.notify("Settings reset to defaults.", color="info")

            ui.button("Save Settings", on_click=save).classes(
                "bg-green-600 text-white flex-1"
            )
            ui.button("Reset to Defaults", on_click=reset).classes(
                "bg-gray-500 text-white flex-1"
            )
# end src/pages/settings.py
