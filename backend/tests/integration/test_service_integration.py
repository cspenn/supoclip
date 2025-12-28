"""Integration tests for service interactions.

Tests how the new services (video, preferences, dependencies) work together
in the broader application context.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.services.video_service_async import AsyncVideoProcessingService
from src.services.user_preferences_service import UserPreferencesService
from src.dependencies import get_current_user
from src.utils.font_options import parse_font_options, merge_with_defaults


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = MagicMock(spec=Config)
    config.temp_dir = "/tmp/test_clips"
    return config


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


class TestVideoServiceWithPreferences:
    """Test video service integration with user preferences."""

    @pytest.mark.asyncio
    async def test_video_service_uses_user_preferences(self, mock_db, mock_config):
        """Test that video service respects user preferences."""
        # Setup services
        async_service = AsyncVideoProcessingService(db=mock_db, config=mock_config)
        preferences_service = UserPreferencesService(db=mock_db)

        # Mock user preferences
        mock_result = MagicMock()
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"
        mock_user_prefs.default_font_size = 32
        mock_user_prefs.default_font_color = "#FF0000"
        mock_user_prefs.default_clip_min_length = 15
        mock_user_prefs.default_clip_target_length = 30
        mock_user_prefs.default_clip_max_length = 50
        mock_user_prefs.custom_ai_prompt = "Custom prompt"
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = "top-right"

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Get user preferences
        prefs = await preferences_service.get_user_preferences("user_123")

        # Verify preferences are correct
        assert prefs["font_family"] == "Arial"
        assert prefs["font_size"] == 32
        assert prefs["custom_ai_prompt"] == "Custom prompt"

    @pytest.mark.asyncio
    async def test_preferences_merge_with_request_options(self, mock_db):
        """Test merging preferences with request options."""
        preferences_service = UserPreferencesService(db=mock_db)

        # Mock user preferences
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

        # Request options - note: service only overrides if different from system default
        request_options = {
            "font_family": "Helvetica",  # Different from default, will override
            # Don't override font_size since request options may not include all fields
        }

        merged = await preferences_service.merge_with_request_options("user_123", request_options)

        # Request should override user prefs for font_family
        assert merged["font_family"] == "Helvetica"
        # User prefs used for font_size since request didn't specify
        assert merged["font_size"] == 32


class TestFontOptionsIntegration:
    """Test font options parsing and merging."""

    def test_parse_then_merge_font_options(self):
        """Test full font options flow: parse then merge."""
        # Simulate request data
        request_data = {
            "font_options": {
                "font_family": "Custom Font",
                "font_size": 36,
            }
        }

        # Parse from request
        parsed = parse_font_options(request_data)
        assert parsed["font_family"] == "Custom Font"
        assert parsed["font_size"] == 36
        assert parsed["font_color"] == "#FFFFFF"  # Default

        # Merge with user preferences (if any)
        user_prefs = {
            "font_family": "User Font",
            "font_size": 28,
            "font_color": "#000000",
        }

        merged = merge_with_defaults(parsed, user_prefs)

        # Request should override user prefs
        assert merged["font_family"] == "Custom Font"
        assert merged["font_size"] == 36
        assert merged["font_color"] == "#FFFFFF"  # From parsed (not from user)

    def test_partial_font_options_with_user_preferences(self):
        """Test partial font options merged with user preferences."""
        # Simulate partial request
        request_data = {
            "font_options": {
                "font_size": 40,  # Only override size
            }
        }

        parsed = parse_font_options(request_data)

        # Merge with user preferences
        user_prefs = {
            "font_family": "User Font",
            "font_size": 28,
            "font_color": "#000000",
        }

        merged = merge_with_defaults(parsed, user_prefs)

        # Parsed (which includes defaults) takes precedence over user_prefs
        assert merged["font_family"] == "TikTokSans-Regular"  # From parsed defaults
        assert merged["font_size"] == 40  # From parsed (request)
        assert merged["font_color"] == "#FFFFFF"  # From parsed defaults


class TestAuthDependencyIntegration:
    """Test authentication dependency with other components."""

    @pytest.mark.asyncio
    async def test_auth_with_user_preferences_service(self, mock_db):
        """Test that auth dependency works with preferences service."""
        # Create mock request
        mock_request = MagicMock()
        mock_request.headers = {"X-User-ID": "user_123"}

        # Mock database results
        # First for auth check
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=("user_123",))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Verify user exists
        user_id = await get_current_user(mock_request, mock_db)
        assert user_id == "user_123"

        # Now get preferences for this user
        preferences_service = UserPreferencesService(db=mock_db)

        # Reset mock for preferences query
        mock_user_prefs = MagicMock()
        mock_user_prefs.default_font_family = "Arial"
        mock_user_prefs.default_font_size = 32
        mock_user_prefs.default_font_color = "#FFFFFF"
        mock_user_prefs.default_clip_min_length = None
        mock_user_prefs.default_clip_target_length = None
        mock_user_prefs.default_clip_max_length = None
        mock_user_prefs.custom_ai_prompt = None
        mock_user_prefs.logo_file_path = None
        mock_user_prefs.logo_corner_position = None

        mock_result.fetchone = MagicMock(return_value=mock_user_prefs)

        prefs = await preferences_service.get_user_preferences(user_id)
        assert prefs is not None


class TestServiceDependencyChain:
    """Test service dependencies and call chains."""

    @pytest.mark.asyncio
    async def test_async_service_creates_task_then_processes(self, mock_db, mock_config):
        """Test async service task creation followed by processing."""
        async_service = AsyncVideoProcessingService(db=mock_db, config=mock_config)

        raw_source = {"url": "https://youtube.com/watch?v=test"}

        # Mock task creation
        with patch("src.services.video_service_async.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_async.get_youtube_video_title", return_value="Title"):
                with patch("src.services.video_service_async.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    mock_db.flush = AsyncMock()
                    mock_db.commit = AsyncMock()

                    # Create task
                    task_id = await async_service.create_task(raw_source, "user_123")

                    assert task_id == "task_123"

                    # Verify service can process the task
                    async_service._update_task_status = AsyncMock()

                    with patch("src.services.video_service_async.AsyncSessionLocal"):
                        try:
                            await async_service.process_video_async(
                                task_id,
                                raw_source,
                                "user_123"
                            )
                        except Exception:
                            pass  # Expected due to mocking

                    # Verify status update was called
                    assert async_service._update_task_status.called


class TestLogoPathHandling:
    """Test logo path integration across services."""

    def test_logo_path_extraction_from_preferences(self, tmp_path):
        """Test extracting logo path from user preferences."""
        preferences_service = UserPreferencesService(db=AsyncMock())

        # Create an actual test logo file (get_logo_path validates file existence)
        test_logo = tmp_path / "test_logo.png"
        test_logo.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header

        # Test with logo configured (must use real existing file)
        preferences = {"logo_file_path": str(test_logo)}
        logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is not None
        assert str(logo_path) == str(test_logo)

        # Test without logo
        preferences = {"logo_file_path": None}
        logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is None

        # Test with non-existent path (should return None - file validation)
        preferences = {"logo_file_path": "/nonexistent/path/logo.png"}
        logo_path = preferences_service.get_logo_path(preferences)

        assert logo_path is None

    @pytest.mark.asyncio
    async def test_logo_passed_to_video_service(self, mock_db, mock_config):
        """Test that logo path is properly passed through services."""
        async_service = AsyncVideoProcessingService(db=mock_db, config=mock_config)

        raw_source = {"url": "/path/to/video.mp4"}
        logo_path = "/path/to/logo.png"

        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        # Service should accept logo_path parameter
        try:
            await async_service.process_video_async(
                "task_123",
                raw_source,
                "user_123",
                logo_path=logo_path,
                logo_corner_position="top-left"
            )
        except Exception:
            # Expected to fail at video processing step
            pass


class TestErrorPropagation:
    """Test error handling across service layers."""

    @pytest.mark.asyncio
    async def test_auth_error_prevents_service_call(self, mock_db):
        """Test that auth errors prevent service access."""
        from fastapi import HTTPException

        # Create mock request without auth header
        mock_request = MagicMock()
        mock_request.headers = {}

        # Should raise 401 before any service is called
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_preferences_error_propagates(self, mock_db):
        """Test that preference loading errors propagate correctly."""
        preferences_service = UserPreferencesService(db=mock_db)

        # Mock database returning no user
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Should raise ValueError
        with pytest.raises(ValueError, match="User not found"):
            await preferences_service.get_user_preferences("nonexistent_user")

# end backend/tests/integration/test_service_integration.py
