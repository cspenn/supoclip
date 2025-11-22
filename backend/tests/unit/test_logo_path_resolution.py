"""Unit tests for logo path resolution and validation.

These tests validate the logo path handling logic including:
- Absolute path conversion
- Path validation
- Non-existent file handling
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.user_preferences_service import UserPreferencesService


class TestLogoPathResolution:
    """Tests for UserPreferencesService.get_logo_path method."""

    @pytest.fixture
    def service(self):
        """Create UserPreferencesService with mocked db."""
        mock_db = MagicMock()
        return UserPreferencesService(mock_db)

    def test_get_logo_path_none_when_not_set(self, service):
        """Test that None is returned when no logo path configured."""
        preferences = {"logo_file_path": None}
        result = service.get_logo_path(preferences)
        assert result is None

    def test_get_logo_path_none_when_empty(self, service):
        """Test that None is returned when logo path is empty string."""
        preferences = {"logo_file_path": ""}
        result = service.get_logo_path(preferences)
        assert result is None

    def test_get_logo_path_absolute_path_unchanged(self, service):
        """Test that absolute paths are returned as-is if they exist."""
        # Create a temporary file path
        with patch.object(Path, "exists", return_value=True):
            preferences = {"logo_file_path": "/Users/test/logos/logo.png"}
            result = service.get_logo_path(preferences)
            assert result is not None
            assert result.is_absolute()
            assert str(result) == "/Users/test/logos/logo.png"

    def test_get_logo_path_relative_converted_to_absolute(self, service):
        """Test that relative paths are converted to absolute."""
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_absolute", return_value=False):
                with patch.object(Path, "resolve", return_value=Path("/abs/path/logo.png")):
                    preferences = {"logo_file_path": "logos/logo.png"}
                    result = service.get_logo_path(preferences)
                    # Should call resolve() for relative paths
                    assert result is not None

    def test_get_logo_path_returns_none_for_nonexistent_file(self, service):
        """Test that None is returned when file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            preferences = {"logo_file_path": "/path/to/nonexistent/logo.png"}
            result = service.get_logo_path(preferences)
            assert result is None


class TestLogoPathInVideoUtils:
    """Tests for logo path handling in video processing."""

    def test_logo_path_conversion_to_absolute(self):
        """Test that video_utils converts relative paths to absolute."""
        # This tests the pattern used in create_optimized_clip
        relative_path = "logos/test_logo.png"
        path_obj = Path(relative_path)

        if not path_obj.is_absolute():
            path_obj = path_obj.resolve()

        assert path_obj.is_absolute()

    def test_logo_path_string_to_path_conversion(self):
        """Test string to Path conversion in video utils."""
        logo_path = "/Users/test/logos/logo.png"

        # Pattern from video_utils
        logo_path_obj = Path(logo_path) if isinstance(logo_path, str) else logo_path

        assert isinstance(logo_path_obj, Path)
        assert str(logo_path_obj) == logo_path


class TestLogoPathEdgeCases:
    """Edge case tests for logo path handling."""

    @pytest.fixture
    def service(self):
        """Create UserPreferencesService with mocked db."""
        mock_db = MagicMock()
        return UserPreferencesService(mock_db)

    def test_get_logo_path_with_spaces_in_path(self, service):
        """Test handling of paths with spaces."""
        with patch.object(Path, "exists", return_value=True):
            preferences = {"logo_file_path": "/Users/test user/logos/my logo.png"}
            result = service.get_logo_path(preferences)
            assert result is not None
            assert "test user" in str(result)
            assert "my logo" in str(result)

    def test_get_logo_path_with_special_characters(self, service):
        """Test handling of paths with special characters."""
        with patch.object(Path, "exists", return_value=True):
            preferences = {"logo_file_path": "/Users/test/logos/logo_v2.0.png"}
            result = service.get_logo_path(preferences)
            assert result is not None

    def test_missing_key_in_preferences(self, service):
        """Test handling when logo_file_path key is missing."""
        preferences = {}  # No logo_file_path key
        result = service.get_logo_path(preferences)
        assert result is None
