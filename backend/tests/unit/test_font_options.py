"""Unit tests for font options parsing utilities.

Tests the utilities for extracting and validating font customization
options from API requests.
"""

import pytest
from src.utils.font_options import (
    parse_font_options,
    merge_with_defaults,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_COLOR,
)


class TestParseDefaultConstants:
    """Test default constants."""

    def test_default_font_family(self):
        """Test default font family constant."""
        assert DEFAULT_FONT_FAMILY == "TikTokSans-Regular"

    def test_default_font_size(self):
        """Test default font size constant."""
        assert DEFAULT_FONT_SIZE == 24

    def test_default_font_color(self):
        """Test default font color constant."""
        assert DEFAULT_FONT_COLOR == "#FFFFFF"


class TestParseFontOptions:
    """Test font options parsing."""

    def test_parse_font_options_with_all_options(self):
        """Test parsing when all font options are provided."""
        data = {
            "font_options": {
                "font_family": "Arial",
                "font_size": 32,
                "font_color": "#FF0000",
            }
        }
        result = parse_font_options(data)

        assert result["font_family"] == "Arial"
        assert result["font_size"] == 32
        assert result["font_color"] == "#FF0000"

    def test_parse_font_options_with_partial_options(self):
        """Test parsing when only some font options are provided."""
        data = {
            "font_options": {
                "font_family": "Arial",
            }
        }
        result = parse_font_options(data)

        assert result["font_family"] == "Arial"
        assert result["font_size"] == DEFAULT_FONT_SIZE
        assert result["font_color"] == DEFAULT_FONT_COLOR

    def test_parse_font_options_with_no_options(self):
        """Test parsing when no font options are provided."""
        data = {}
        result = parse_font_options(data)

        assert result["font_family"] == DEFAULT_FONT_FAMILY
        assert result["font_size"] == DEFAULT_FONT_SIZE
        assert result["font_color"] == DEFAULT_FONT_COLOR

    def test_parse_font_options_with_empty_font_options(self):
        """Test parsing when font_options key is empty dict."""
        data = {"font_options": {}}
        result = parse_font_options(data)

        assert result["font_family"] == DEFAULT_FONT_FAMILY
        assert result["font_size"] == DEFAULT_FONT_SIZE
        assert result["font_color"] == DEFAULT_FONT_COLOR

    def test_parse_font_options_returns_dict(self):
        """Test that parse_font_options always returns a dictionary."""
        data = {}
        result = parse_font_options(data)

        assert isinstance(result, dict)
        assert "font_family" in result
        assert "font_size" in result
        assert "font_color" in result

    def test_parse_font_options_font_size_override(self):
        """Test that font_size is properly overridden."""
        data = {"font_options": {"font_size": 48}}
        result = parse_font_options(data)

        assert result["font_size"] == 48

    def test_parse_font_options_font_color_override(self):
        """Test that font_color is properly overridden."""
        data = {"font_options": {"font_color": "#000000"}}
        result = parse_font_options(data)

        assert result["font_color"] == "#000000"


class TestMergeWithDefaults:
    """Test merging request options with defaults."""

    def test_merge_with_defaults_request_overrides(self):
        """Test that request options override defaults."""
        request_options = {"font_family": "Arial", "font_size": 32}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        assert result["font_family"] == "Arial"
        assert result["font_size"] == 32

    def test_merge_with_defaults_missing_in_request(self):
        """Test that defaults are used for missing request options."""
        request_options = {"font_family": "Arial"}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        assert result["font_family"] == "Arial"
        assert result["font_size"] == 24

    def test_merge_with_defaults_ignores_none_in_request(self):
        """Test that None values in request don't override defaults."""
        request_options = {"font_family": None, "font_size": 32}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        assert result["font_family"] == "Helvetica"
        assert result["font_size"] == 32

    def test_merge_with_defaults_empty_request(self):
        """Test merging with empty request options."""
        request_options = {}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        assert result == defaults

    def test_merge_with_defaults_empty_defaults(self):
        """Test merging with empty defaults."""
        request_options = {"font_family": "Arial", "font_size": 32}
        defaults = {}

        result = merge_with_defaults(request_options, defaults)

        assert result["font_family"] == "Arial"
        assert result["font_size"] == 32

    def test_merge_with_defaults_preserves_defaults_dict(self):
        """Test that defaults dict is not modified."""
        request_options = {"font_family": "Arial"}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        original_defaults = dict(defaults)
        merge_with_defaults(request_options, defaults)

        assert defaults == original_defaults

    def test_merge_with_defaults_handles_extra_keys_in_request(self):
        """Test merging with extra keys in request options."""
        request_options = {
            "font_family": "Arial",
            "extra_key": "extra_value"
        }
        defaults = {"font_family": "Helvetica"}

        result = merge_with_defaults(request_options, defaults)

        assert result["font_family"] == "Arial"
        assert result["extra_key"] == "extra_value"

    def test_merge_with_defaults_numeric_values(self):
        """Test merging with numeric values."""
        request_options = {"font_size": 0}
        defaults = {"font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        # 0 should not override the default since 0 is not None
        assert result["font_size"] == 0

    def test_merge_with_defaults_empty_string_value(self):
        """Test merging with empty string values."""
        request_options = {"font_family": ""}
        defaults = {"font_family": "Helvetica"}

        result = merge_with_defaults(request_options, defaults)

        # Empty string is not None, so it should be used
        assert result["font_family"] == ""

    def test_merge_with_defaults_returns_new_dict(self):
        """Test that merge returns a new dictionary."""
        request_options = {"font_family": "Arial"}
        defaults = {"font_family": "Helvetica", "font_size": 24}

        result = merge_with_defaults(request_options, defaults)

        # Modify result
        result["font_family"] = "Modified"

        # Original defaults should not be affected
        assert defaults["font_family"] == "Helvetica"

# end backend/tests/unit/test_font_options.py
