"""Unit tests for UserPreferencesService.

Tests the user preferences service that centralizes preference loading,
merging with request options, and default handling.
Covers all methods and branches for 100% line coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_preferences_service import UserPreferencesService


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def preferences_service(mock_db):
    """Create a UserPreferencesService instance for testing."""
    return UserPreferencesService(db=mock_db)


def _make_user_prefs_row(**overrides):
    """Helper to create a mock user preferences row."""
    defaults = {
        "default_font_family": None,
        "default_font_size": None,
        "default_font_color": None,
        "default_clip_min_length": None,
        "default_clip_target_length": None,
        "default_clip_max_length": None,
        "custom_ai_prompt": None,
        "logo_file_path": None,
        "logo_corner_position": None,
        "output_resolution": None,
    }
    defaults.update(overrides)
    mock_row = MagicMock()
    for key, value in defaults.items():
        setattr(mock_row, key, value)
    return mock_row


def _setup_db_return(mock_db, row):
    """Helper to set up mock DB to return a specific row."""
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=row)
    mock_db.execute = AsyncMock(return_value=mock_result)


class TestUserPreferencesServiceInit:
    """Test service initialization."""

    def test_init_stores_db(self, mock_db):
        """Test that __init__ stores database session."""
        service = UserPreferencesService(db=mock_db)
        assert service.db == mock_db

    def test_default_preferences_are_defined(self):
        """Test that default preferences are properly defined."""
        assert UserPreferencesService.DEFAULT_PREFERENCES["font_family"] == "TikTokSans-Regular"
        assert UserPreferencesService.DEFAULT_PREFERENCES["font_size"] == 24
        assert UserPreferencesService.DEFAULT_PREFERENCES["font_color"] == "#FFFFFF"
        assert UserPreferencesService.DEFAULT_PREFERENCES["clip_min_length"] == 10
        assert UserPreferencesService.DEFAULT_PREFERENCES["clip_max_length"] == 45


class TestGetUserPreferences:
    """Test user preference loading."""

    @pytest.mark.asyncio
    async def test_get_user_preferences_returns_dict(self, preferences_service, mock_db):
        """Test that get_user_preferences returns a dictionary."""
        row = _make_user_prefs_row(
            default_font_family="Arial",
            default_font_size=32,
            default_font_color="#FF0000",
            default_clip_min_length=15,
            default_clip_target_length=30,
            default_clip_max_length=50,
            custom_ai_prompt="Custom prompt",
            logo_file_path="/path/to/logo.png",
            logo_corner_position="top-left",
        )
        _setup_db_return(mock_db, row)

        prefs = await preferences_service.get_user_preferences("user_123")

        assert isinstance(prefs, dict)
        assert "font_family" in prefs
        assert "font_size" in prefs
        assert "font_color" in prefs

    @pytest.mark.asyncio
    async def test_get_user_preferences_uses_defaults_for_none_values(self, preferences_service, mock_db):
        """Test that defaults are used when user preferences are None."""
        row = _make_user_prefs_row()
        _setup_db_return(mock_db, row)

        prefs = await preferences_service.get_user_preferences("user_123")

        assert prefs["font_family"] == "TikTokSans-Regular"
        assert prefs["font_size"] == 24
        assert prefs["font_color"] == "#FFFFFF"

    @pytest.mark.asyncio
    async def test_get_user_preferences_raises_for_missing_user(self, preferences_service, mock_db):
        """Test that ValueError is raised for non-existent user."""
        _setup_db_return(mock_db, None)

        with pytest.raises(ValueError, match="User not found"):
            await preferences_service.get_user_preferences("nonexistent_user")

    @pytest.mark.asyncio
    async def test_get_user_preferences_merges_with_defaults(self, preferences_service, mock_db):
        """Test that user preferences properly override defaults."""
        row = _make_user_prefs_row(
            default_font_family="Arial",
            default_font_color="#FF0000",
        )
        _setup_db_return(mock_db, row)

        prefs = await preferences_service.get_user_preferences("user_123")

        assert prefs["font_family"] == "Arial"
        assert prefs["font_color"] == "#FF0000"
        assert prefs["font_size"] == 24  # Default


class TestMergeWithRequestOptions:
    """Test merging request options with user preferences."""

    @pytest.mark.asyncio
    async def test_merge_with_request_options_request_overrides_user(self, preferences_service, mock_db):
        """Test that request options override user preferences."""
        row = _make_user_prefs_row(
            default_font_family="Arial",
            default_font_size=32,
            default_font_color="#FF0000",
        )
        _setup_db_return(mock_db, row)

        request_options = {
            "font_family": "Helvetica",
            "font_size": 16,
        }

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        assert merged["font_family"] == "Helvetica"
        assert merged["font_size"] == 16

    @pytest.mark.asyncio
    async def test_merge_with_request_options_user_used_when_request_missing(self, preferences_service, mock_db):
        """Test that user preferences are used when request doesn't specify values."""
        row = _make_user_prefs_row(
            default_font_family="Arial",
            default_font_size=32,
            default_font_color="#FF0000",
        )
        _setup_db_return(mock_db, row)

        merged = await preferences_service.merge_with_request_options("user_123", {})

        assert merged["font_family"] == "Arial"
        assert merged["font_size"] == 32

    @pytest.mark.asyncio
    async def test_merge_with_request_options_custom_ai_prompt(self, preferences_service, mock_db):
        """Test that custom AI prompt is merged correctly."""
        row = _make_user_prefs_row(custom_ai_prompt="User custom prompt")
        _setup_db_return(mock_db, row)

        request_options = {"custom_ai_prompt": "Request custom prompt"}

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        assert merged["custom_ai_prompt"] == "Request custom prompt"

    @pytest.mark.asyncio
    async def test_merge_clip_length_settings(self, preferences_service, mock_db):
        """Test that clip length settings are merged correctly."""
        row = _make_user_prefs_row(
            default_clip_min_length=5,
            default_clip_target_length=25,
            default_clip_max_length=40,
        )
        _setup_db_return(mock_db, row)

        request_options = {"clip_min_length": 15}

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        assert merged["clip_min_length"] == 15
        assert merged["clip_target_length"] == 25
        assert merged["clip_max_length"] == 40

    @pytest.mark.asyncio
    async def test_merge_request_same_as_default_does_not_override_user(self, preferences_service, mock_db):
        """Test that request values equal to system defaults don't override user prefs."""
        row = _make_user_prefs_row(default_font_family="Arial")
        _setup_db_return(mock_db, row)

        # Request font_family == system default "TikTokSans-Regular" should NOT override user "Arial"
        request_options = {"font_family": "TikTokSans-Regular"}

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # User pref "Arial" should be kept since request value equals system default
        assert merged["font_family"] == "Arial"


class TestGetLogoPath:
    """Test logo path extraction."""

    def test_get_logo_path_returns_path_object(self, preferences_service):
        """Test that get_logo_path returns a Path object when logo exists."""
        preferences = {"logo_file_path": "/path/to/logo.png"}

        with patch.object(Path, "exists", return_value=True):
            logo_path = preferences_service.get_logo_path(preferences)

            assert logo_path is not None
            assert isinstance(logo_path, Path)
            assert str(logo_path) == "/path/to/logo.png"

    def test_get_logo_path_returns_none_when_not_configured(self, preferences_service):
        """Test that get_logo_path returns None when logo is not configured."""
        preferences = {"logo_file_path": None}
        logo_path = preferences_service.get_logo_path(preferences)
        assert logo_path is None

    def test_get_logo_path_returns_none_for_empty_path(self, preferences_service):
        """Test that get_logo_path returns None for empty string."""
        preferences = {"logo_file_path": ""}
        logo_path = preferences_service.get_logo_path(preferences)
        assert logo_path is None

    def test_get_logo_path_relative_path_resolved(self, preferences_service, tmp_path):
        """Test that relative paths are resolved to absolute."""
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"PNG data")

        preferences = {"logo_file_path": str(logo_file)}

        logo_path = preferences_service.get_logo_path(preferences)
        assert logo_path is not None
        assert logo_path.is_absolute()

    def test_get_logo_path_not_found_tries_temp_dir(self, preferences_service, tmp_path):
        """Test logo path fallback to temp dir (lines 193-194)."""
        # Create logo in temp dir
        logo_in_temp = tmp_path / "logo.png"
        logo_in_temp.write_bytes(b"PNG data")

        preferences = {"logo_file_path": "logo.png"}

        mock_config = MagicMock()
        mock_config.temp_dir = str(tmp_path)

        with patch("src.config.Config", return_value=mock_config):
            logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is not None
        assert str(logo_path) == str(logo_in_temp)

    def test_get_logo_path_temp_dir_config_fails(self, preferences_service):
        """Test logo path when Config() raises exception (lines 195-196)."""
        preferences = {"logo_file_path": "logo.png"}

        with patch("src.config.Config",
                    side_effect=RuntimeError("config error")):
            logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is None

    def test_get_logo_path_not_found_anywhere(self, preferences_service, tmp_path):
        """Test logo path returns None when not found in temp dir either (line 198-199)."""
        preferences = {"logo_file_path": "nonexistent_logo.png"}

        mock_config = MagicMock()
        mock_config.temp_dir = str(tmp_path)

        with patch("src.config.Config", return_value=mock_config):
            logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is None


class TestUpdateUserLogo:
    """Test update_user_logo method (lines 213-225)."""

    @pytest.mark.asyncio
    async def test_update_user_logo_success(self, preferences_service, mock_db):
        """Test successful logo update for a user."""
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await preferences_service.update_user_logo(
            user_id="user_123",
            logo_path="/path/to/resized_logo.png",
            corner_position="bottom-left",
        )

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify the correct SQL parameters were passed
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["logo_path"] == "/path/to/resized_logo.png"
        assert params["position"] == "bottom-left"
        assert params["user_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_update_user_logo_different_corners(self, preferences_service, mock_db):
        """Test updating logo with different corner positions."""
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        for corner in ["top-left", "top-right", "bottom-left", "bottom-right"]:
            await preferences_service.update_user_logo(
                user_id="user_456",
                logo_path="/path/logo.png",
                corner_position=corner,
            )

        assert mock_db.execute.call_count == 4
        assert mock_db.commit.call_count == 4


# end backend/tests/unit/test_user_preferences_service.py
