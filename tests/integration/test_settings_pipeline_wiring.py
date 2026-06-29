# start tests/integration/test_settings_pipeline_wiring.py
"""Seam tests for the Settings -> pipeline wiring (audit finding C-1).

The headline bug lives in the seam between files: the Settings page persists a
full subtitle style, but the home page never reads it, so every produced clip
has ``subtitle_style=None`` and no captions. Per-file unit tests cannot see this
seam — these tests assert the style actually flows from saved ``UserPreferences``
all the way to ``write_ass_file``.

These are RED until C-1 / Subtitle Playbook step S1 is implemented:
  * ``src.pages.settings.subtitle_style_from_prefs`` must exist and map every
    preference field onto a ``SubtitleStyle``.
  * ``src.pages.home.build_processing_request`` must load prefs and forward a
    non-None ``subtitle_style`` (plus custom prompt / logo) on the request.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.models import UserPreferences


def test_subtitle_style_from_prefs_maps_all_fields() -> None:
    """Every UserPreferences styling field maps onto the SubtitleStyle."""
    from src.pages.settings import subtitle_style_from_prefs

    prefs = UserPreferences(
        id=1,
        font_family="Bangers",
        font_size=40,
        font_color="#FF0000",
        font_stroke_color="#0000FF",
        font_stroke_width=3.0,
        font_shadow_offset=2,
        subtitle_position_y=70,
        min_clip_length=15,
        max_clip_length=45,
        output_resolution="1080p",
    )

    style = subtitle_style_from_prefs(prefs)

    assert style.font_family == "Bangers"
    assert style.font_size == 40
    assert style.font_color == "#FF0000"
    assert style.outline_color == "#0000FF"
    assert style.outline_width == pytest.approx(3.0)
    assert style.shadow_depth == pytest.approx(2.0)
    assert style.position_y_pct == 70
    # 1080p -> 1920px tall so MarginV math is correct for the real clip.
    assert style.video_height == 1920


def test_subtitle_style_video_height_follows_resolution() -> None:
    """The style's video_height tracks the chosen output resolution."""
    from src.pages.settings import subtitle_style_from_prefs

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
        output_resolution="720p",
    )
    # Explicit override also wins over the prefs' own resolution.
    assert subtitle_style_from_prefs(prefs).video_height == 1280
    assert subtitle_style_from_prefs(prefs, "1080p").video_height == 1920


@pytest.mark.asyncio
async def test_home_request_carries_subtitle_style(test_db: None) -> None:
    """build_processing_request loads prefs and forwards a non-None style."""
    from src.pages.home import build_processing_request
    from src.pages.settings import save_prefs

    await save_prefs(
        {
            "font_family": "Bangers",
            "font_size": 36,
            "font_color": "#FFEE00",
            "font_stroke_color": "#101010",
            "font_stroke_width": 2.5,
            "font_shadow_offset": 1,
            "subtitle_position_y": 80,
            "min_clip_length": 12,
            "max_clip_length": 40,
            "output_resolution": "1080p",
            "ai_prompt": "Focus on funny moments",
            "logo_path": None,
        }
    )

    request = await build_processing_request(
        source="https://youtu.be/abc",
        task_id="task-123",
        min_clip_length=12,
        max_clip_length=40,
        output_resolution="1080p",
    )

    assert request.subtitle_style is not None, "subtitle_style was not wired through"
    assert request.subtitle_style.font_family == "Bangers"
    assert request.subtitle_style.font_color == "#FFEE00"
    assert request.custom_prompt == "Focus on funny moments"


@pytest.mark.asyncio
async def test_video_service_forwards_style_to_write_ass_file(test_db: None, tmp_path: object) -> None:
    """video_service hands the request's style down to write_ass_file.

    Locks the downstream half of the seam: even if S1 wires the request, this
    fails if anything between ClipOptions and write_ass_file drops the style.
    ffmpeg itself is stubbed (we assert behaviour, not pixels — the real-output
    suite covers pixels), but write_ass_file runs for real.
    """
    from pathlib import Path

    import src.pipeline.clip as clip_mod
    from src.pipeline.clip import ClipOptions, generate_clip
    from src.pipeline.clip import TranscriptSegment as ClipSegment
    from src.pipeline.subtitles import SubtitleStyle

    style = SubtitleStyle(font_family="Bangers", font_color="#FF0000")
    out = Path(str(tmp_path)) / "clip.mp4"
    seg = ClipSegment(start_s=0.0, end_s=2.0, text="hi there")
    words = [{"text": "hi", "start_ms": 100, "end_ms": 600}]

    captured: dict[str, object] = {}

    with patch.object(clip_mod, "_run_ffmpeg") as mock_ff:
        mock_ff.return_value = type("R", (), {"returncode": 0, "stderr": b""})()
        with patch.object(clip_mod, "write_ass_file") as mock_write:
            mock_write.side_effect = lambda w, p, style=None: captured.__setitem__("style", style)
            await generate_clip(
                source_video=Path("tests/fixtures/sample_video.mp4"),
                segment=seg,
                words=words,
                output_path=out,
                options=ClipOptions(subtitle_style=style),
            )

    assert captured.get("style") is style, "style did not reach write_ass_file"


# end tests/integration/test_settings_pipeline_wiring.py
