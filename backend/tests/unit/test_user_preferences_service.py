"""Unit tests for UserPreferencesService.

Tests the user preferences service that centralizes preference loading,
merging with request options, and default handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
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
        # Mock the database query result
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"
        mock_user_prefs.default_font_size = 32
        mock_user_prefs.default_font_color = "#FF0000"
        mock_user_prefs.default_clip_min_length = 15
        mock_user_prefs.default_clip_target_length = 30
        mock_user_prefs.default_clip_max_length = 50
        mock_user_prefs.custom_ai_prompt = "Custom prompt"
        mock_user_prefs.logo_file_path = "/path/to/logo.png"
        mock_user_prefs.logo_corner_position = "top-left"

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        prefs = await preferences_service.get_user_preferences("user_123")

        assert isinstance(prefs, dict)
        assert "font_family" in prefs
        assert "font_size" in prefs
        assert "font_color" in prefs

    @pytest.mark.asyncio
    async def test_get_user_preferences_uses_defaults_for_none_values(self, preferences_service, mock_db):
        """Test that defaults are used when user preferences are None."""
        # Mock user with all None preferences
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = None
        mock_user_prefs.default_font_size = None
        mock_user_prefs.default_font_color = None
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        prefs = await preferences_service.get_user_preferences("user_123")

        # Should use system defaults
        assert prefs["font_family"] == "TikTokSans-Regular"
        assert prefs["font_size"] == 24
        assert prefs["font_color"] == "#FFFFFF"

    @pytest.mark.asyncio
    async def test_get_user_preferences_raises_for_missing_user(self, preferences_service, mock_db):
        """Test that ValueError is raised for non-existent user."""
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="User not found"):
            await preferences_service.get_user_preferences("nonexistent_user")

    @pytest.mark.asyncio
    async def test_get_user_preferences_merges_with_defaults(self, preferences_service, mock_db):
        """Test that user preferences properly override defaults."""
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"  # Override default
        mock_user_prefs.default_font_size = None  # Use default
        mock_user_prefs.default_font_color = "#FF0000"  # Override default
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        prefs = await preferences_service.get_user_preferences("user_123")

        # User preferences should override
        assert prefs["font_family"] == "Arial"
        assert prefs["font_color"] == "#FF0000"
        # Defaults should be used for None values
        assert prefs["font_size"] == 24


class TestMergeWithRequestOptions:
    """Test merging request options with user preferences."""

    @pytest.mark.asyncio
    async def test_merge_with_request_options_request_overrides_user(self, preferences_service, mock_db):
        """Test that request options override user preferences."""
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"
        mock_user_prefs.default_font_size = 32
        mock_user_prefs.default_font_color = "#FF0000"
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        request_options = {
            "font_family": "Helvetica",  # Different from user pref
            "font_size": 16,  # Different from user pref
        }

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # Request options should override user preferences
        assert merged["font_family"] == "Helvetica"
        assert merged["font_size"] == 16

    @pytest.mark.asyncio
    async def test_merge_with_request_options_user_used_when_request_missing(self, preferences_service, mock_db):
        """Test that user preferences are used when request doesn't specify values."""
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"
        mock_user_prefs.default_font_size = 32
        mock_user_prefs.default_font_color = "#FF0000"
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        request_options = {}  # Empty request

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # User preferences should be used
        assert merged["font_family"] == "Arial"
        assert merged["font_size"] == 32

    @pytest.mark.asyncio
    async def test_merge_with_request_options_custom_ai_prompt(self, preferences_service, mock_db):
        """Test that custom AI prompt is merged correctly."""
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = None
        mock_user_prefs.default_font_size = None
        mock_user_prefs.default_font_color = None
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = "User custom prompt"
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        request_options = {
            "custom_ai_prompt": "Request custom prompt"
        }

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # Request option should override
        assert merged["custom_ai_prompt"] == "Request custom prompt"

    @pytest.mark.asyncio
    async def test_merge_clip_length_settings(self, preferences_service, mock_db):
        """Test that clip length settings are merged correctly."""
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = None
        mock_user_prefs.default_font_size = None
        mock_user_prefs.default_font_color = None
        mock_user_prefs.default_clip_min_length = 5
        mock_user_prefs.default_clip_target_length = 25
        mock_user_prefs.default_clip_max_length = 40
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        request_options = {
            "clip_min_length": 15
        }

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # Request should override min_length
        assert merged["clip_min_length"] == 15
        # User prefs should be used for others
        assert merged["clip_target_length"] == 25
        assert merged["clip_max_length"] == 40


class TestGetLogoPath:
    """Test logo path extraction."""

    def test_get_logo_path_returns_path_object(self, preferences_service):
        """Test that get_logo_path returns a Path object when logo is configured."""
        from pathlib import Path
        from unittest.mock import patch
        
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

# end backend/tests/unit/test_user_preferences_service.py
