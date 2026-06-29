# start tests/integration/test_settings_persistence.py
"""Integration tests for UserPreferences DB round-trips.

Tests cover:
- Save and load round-trip (all fields persisted correctly)
- Update existing preferences (partial field updates persist)
- Defaults when no row exists (graceful None return)
"""

import pytest

from src.database import get_session
from src.models import UserPreferences


@pytest.mark.asyncio
async def test_save_and_load_round_trip(test_db: None) -> None:
    """Create a UserPreferences row and verify all fields load back correctly."""
    async with get_session() as session:
        prefs = UserPreferences(
            id=1,
            font_family="Roboto",
            font_size=32,
            font_color="#FF0000",
            font_stroke_color="#00FF00",
            font_stroke_width=3.5,
            font_shadow_offset=2,
            subtitle_position_y=80,
            min_clip_length=10,
            max_clip_length=60,
            output_resolution="720p",
            ai_prompt="Find the most exciting moments.",
            logo_path="/tmp/logo.png",
        )
        session.add(prefs)

    # Reload in a fresh session to confirm persistence
    async with get_session() as session:
        loaded = await session.get(UserPreferences, 1)

    assert loaded is not None
    assert loaded.id == 1
    assert loaded.font_family == "Roboto"
    assert loaded.font_size == 32
    assert loaded.font_color == "#FF0000"
    assert loaded.font_stroke_color == "#00FF00"
    assert loaded.font_stroke_width == pytest.approx(3.5)
    assert loaded.font_shadow_offset == 2
    assert loaded.subtitle_position_y == 80
    assert loaded.min_clip_length == 10
    assert loaded.max_clip_length == 60
    assert loaded.output_resolution == "720p"
    assert loaded.ai_prompt == "Find the most exciting moments."
    assert loaded.logo_path == "/tmp/logo.png"


@pytest.mark.asyncio
async def test_update_existing_preferences(test_db: None) -> None:
    """Create a row then update specific fields and verify only those change."""
    async with get_session() as session:
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
        )
        session.add(prefs)

    # Update a subset of fields
    async with get_session() as session:
        existing = await session.get(UserPreferences, 1)
        assert existing is not None
        existing.font_family = "Montserrat"
        existing.font_size = 28
        existing.subtitle_position_y = 70
        existing.ai_prompt = "Look for emotional moments."

    # Verify updates persisted and other fields remain unchanged
    async with get_session() as session:
        updated = await session.get(UserPreferences, 1)

    assert updated is not None
    assert updated.font_family == "Montserrat"
    assert updated.font_size == 28
    assert updated.subtitle_position_y == 70
    assert updated.ai_prompt == "Look for emotional moments."
    # Fields not touched must retain original values
    assert updated.font_color == "#FFFFFF"
    assert updated.font_stroke_color == "#000000"
    assert updated.font_stroke_width == pytest.approx(2.0)
    assert updated.font_shadow_offset == 1
    assert updated.min_clip_length == 15
    assert updated.max_clip_length == 45
    assert updated.output_resolution == "1080p"
    assert updated.logo_path is None


@pytest.mark.asyncio
async def test_no_row_returns_none(test_db: None) -> None:
    """Query for UserPreferences when DB is empty and confirm None is returned."""
    async with get_session() as session:
        result = await session.get(UserPreferences, 1)

    assert result is None


# end tests/integration/test_settings_persistence.py
