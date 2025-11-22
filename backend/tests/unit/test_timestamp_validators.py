"""Unit tests for TimestampParser and TimestampFormatValidator classes.

These tests validate the timestamp parsing and format validation logic
that was added for improved caption-video synchronization.
"""

import pytest
from src.ai import TimestampParser, TimestampFormatValidator


class TestTimestampParser:
    """Tests for TimestampParser class."""

    def test_parse_timestamp_with_milliseconds(self):
        """Test parsing MM:SS.mmm format."""
        result = TimestampParser.parse_timestamp("02:35.450")
        assert result == pytest.approx(155.450, abs=0.001)

    def test_parse_timestamp_without_milliseconds(self):
        """Test parsing MM:SS format (backward compatibility)."""
        result = TimestampParser.parse_timestamp("02:35")
        assert result == pytest.approx(155.0, abs=0.001)

    def test_parse_timestamp_zero_minutes(self):
        """Test parsing timestamp with zero minutes."""
        result = TimestampParser.parse_timestamp("00:45.123")
        assert result == pytest.approx(45.123, abs=0.001)

    def test_parse_timestamp_large_minutes(self):
        """Test parsing timestamp with double-digit minutes."""
        result = TimestampParser.parse_timestamp("12:30.500")
        assert result == pytest.approx(750.500, abs=0.001)

    def test_parse_timestamp_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid format"):
            TimestampParser.parse_timestamp("2:35:00")  # HH:MM:SS format

    def test_parse_timestamp_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            TimestampParser.parse_timestamp("")

    def test_calculate_duration_with_milliseconds(self):
        """Test duration calculation with millisecond precision."""
        duration = TimestampParser.calculate_duration("01:00.000", "01:15.500")
        assert duration == pytest.approx(15.5, abs=0.001)

    def test_calculate_duration_negative(self):
        """Test negative duration when end < start."""
        duration = TimestampParser.calculate_duration("02:00.000", "01:00.000")
        assert duration < 0

    def test_validate_duration_valid(self):
        """Test valid duration passes validation."""
        is_valid, reason = TimestampParser.validate_duration(10.5)
        assert is_valid is True
        assert "Valid" in reason

    def test_validate_duration_too_short(self):
        """Test short duration fails validation."""
        is_valid, reason = TimestampParser.validate_duration(3.0)
        assert is_valid is False
        assert "Too short" in reason

    def test_validate_duration_zero(self):
        """Test zero duration fails validation."""
        is_valid, reason = TimestampParser.validate_duration(0)
        assert is_valid is False
        assert "Invalid" in reason or "must be positive" in reason

    def test_validate_duration_negative(self):
        """Test negative duration fails validation."""
        is_valid, reason = TimestampParser.validate_duration(-5.0)
        assert is_valid is False


class TestTimestampFormatValidator:
    """Tests for TimestampFormatValidator class."""

    def test_validate_precise_format(self):
        """Test MM:SS.mmm format passes validation."""
        is_valid, msg = TimestampFormatValidator.validate("02:35.450")
        assert is_valid is True
        assert "Format OK" in msg

    def test_validate_precise_format_single_digit_minute(self):
        """Test M:SS.mmm format passes validation."""
        is_valid, msg = TimestampFormatValidator.validate("2:35.450")
        assert is_valid is True

    def test_validate_imprecise_format(self):
        """Test MM:SS format returns False with warning."""
        is_valid, msg = TimestampFormatValidator.validate("02:35")
        assert is_valid is False
        assert "Missing milliseconds" in msg

    def test_validate_invalid_format(self):
        """Test invalid format returns False."""
        is_valid, msg = TimestampFormatValidator.validate("2:35:00")
        assert is_valid is False
        assert "Invalid timestamp format" in msg

    def test_validate_with_whitespace(self):
        """Test validation handles whitespace."""
        is_valid, msg = TimestampFormatValidator.validate("  02:35.450  ")
        assert is_valid is True

    def test_add_default_milliseconds_imprecise(self):
        """Test adding .000 to imprecise timestamps."""
        result = TimestampFormatValidator.add_default_milliseconds("02:35")
        assert result == "02:35.000"

    def test_add_default_milliseconds_precise(self):
        """Test precise timestamps are unchanged."""
        result = TimestampFormatValidator.add_default_milliseconds("02:35.450")
        assert result == "02:35.450"

    def test_add_default_milliseconds_with_whitespace(self):
        """Test whitespace handling."""
        result = TimestampFormatValidator.add_default_milliseconds("  02:35  ")
        assert result == "02:35.000"


class TestTimestampIntegration:
    """Integration tests combining parser and validator."""

    def test_full_validation_flow(self):
        """Test complete validation flow with format check and duration calculation."""
        start = "01:00.000"
        end = "01:15.500"

        # Validate format
        start_valid, _ = TimestampFormatValidator.validate(start)
        end_valid, _ = TimestampFormatValidator.validate(end)
        assert start_valid is True
        assert end_valid is True

        # Calculate duration
        duration = TimestampParser.calculate_duration(start, end)
        assert duration == pytest.approx(15.5, abs=0.001)

        # Validate duration
        is_valid, _ = TimestampParser.validate_duration(duration)
        assert is_valid is True

    def test_fallback_flow_for_imprecise_timestamps(self):
        """Test fallback handling when AI returns MM:SS format."""
        start = "01:00"
        end = "01:15"

        # Validator detects missing milliseconds
        start_valid, _ = TimestampFormatValidator.validate(start)
        end_valid, _ = TimestampFormatValidator.validate(end)
        assert start_valid is False
        assert end_valid is False

        # Apply fallback
        start_fixed = TimestampFormatValidator.add_default_milliseconds(start)
        end_fixed = TimestampFormatValidator.add_default_milliseconds(end)
        assert start_fixed == "01:00.000"
        assert end_fixed == "01:15.000"

        # Now parsing works
        duration = TimestampParser.calculate_duration(start_fixed, end_fixed)
        assert duration == pytest.approx(15.0, abs=0.001)
