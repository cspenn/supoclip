"""Test video_utils.parse_timestamp_to_seconds function with millisecond precision.

This test module validates that the timestamp parser in video_utils.py correctly
handles timestamps with millisecond precision (MM:SS.mmm and HH:MM:SS.mmm formats),
as returned by Groq Llama 4 Scout.
"""
import pytest
from src.video_utils import parse_timestamp_to_seconds


class TestParseTimestampMMSSFormat:
    """Test parsing of MM:SS format timestamps."""

    def test_parse_mm_ss_integer_seconds(self):
        """Test parsing MM:SS with integer seconds (backward compatibility)."""
        assert parse_timestamp_to_seconds("01:23") == pytest.approx(83.0)
        assert parse_timestamp_to_seconds("02:45") == pytest.approx(165.0)
        assert parse_timestamp_to_seconds("00:30") == pytest.approx(30.0)
        assert parse_timestamp_to_seconds("10:00") == pytest.approx(600.0)

    def test_parse_mm_ss_with_milliseconds(self):
        """Test parsing MM:SS.mmm with millisecond precision."""
        # This is the key fix - float() instead of int() for seconds
        assert parse_timestamp_to_seconds("01:23.456") == pytest.approx(83.456)
        assert parse_timestamp_to_seconds("01:45.789") == pytest.approx(105.789)
        assert parse_timestamp_to_seconds("05:30.100") == pytest.approx(330.1)
        assert parse_timestamp_to_seconds("10:00.999") == pytest.approx(600.999)

    def test_parse_mm_ss_milliseconds_edge_cases(self):
        """Test edge cases with millisecond precision."""
        assert parse_timestamp_to_seconds("00:00.001") == pytest.approx(0.001)
        assert parse_timestamp_to_seconds("00:59.999") == pytest.approx(59.999)
        assert parse_timestamp_to_seconds("59:59.999") == pytest.approx(3599.999)
        assert parse_timestamp_to_seconds("00:00.000") == pytest.approx(0.0)


class TestParseTimestampHHMMSSFormat:
    """Test parsing of HH:MM:SS format timestamps."""

    def test_parse_hh_mm_ss_integer_seconds(self):
        """Test parsing HH:MM:SS with integer seconds (backward compatibility)."""
        assert parse_timestamp_to_seconds("01:23:45") == pytest.approx(5025.0)
        assert parse_timestamp_to_seconds("00:05:30") == pytest.approx(330.0)
        assert parse_timestamp_to_seconds("02:00:00") == pytest.approx(7200.0)
        assert parse_timestamp_to_seconds("00:00:30") == pytest.approx(30.0)

    def test_parse_hh_mm_ss_with_milliseconds(self):
        """Test parsing HH:MM:SS.mmm with millisecond precision."""
        # This is the key fix - float() instead of int() for seconds
        assert parse_timestamp_to_seconds("01:23:45.123") == pytest.approx(5025.123)
        assert parse_timestamp_to_seconds("00:05:30.500") == pytest.approx(330.5)
        assert parse_timestamp_to_seconds("02:00:00.999") == pytest.approx(7200.999)
        assert parse_timestamp_to_seconds("00:00:30.100") == pytest.approx(30.1)

    def test_parse_hh_mm_ss_milliseconds_edge_cases(self):
        """Test edge cases for HH:MM:SS.mmm format."""
        assert parse_timestamp_to_seconds("00:00:00.001") == pytest.approx(0.001)
        assert parse_timestamp_to_seconds("23:59:59.999") == pytest.approx(86399.999)
        assert parse_timestamp_to_seconds("10:30:45.500") == pytest.approx(37845.5)
        assert parse_timestamp_to_seconds("00:00:00.000") == pytest.approx(0.0)


class TestParseTimestampPureSeconds:
    """Test parsing of pure seconds format."""

    def test_parse_pure_float_seconds(self):
        """Test parsing pure floating point seconds."""
        assert parse_timestamp_to_seconds("83.456") == pytest.approx(83.456)
        assert parse_timestamp_to_seconds("123.789") == pytest.approx(123.789)
        assert parse_timestamp_to_seconds("0.5") == pytest.approx(0.5)
        assert parse_timestamp_to_seconds("100") == pytest.approx(100.0)

    def test_parse_pure_integer_seconds(self):
        """Test parsing pure integer seconds."""
        assert parse_timestamp_to_seconds("30") == pytest.approx(30.0)
        assert parse_timestamp_to_seconds("123") == pytest.approx(123.0)
        assert parse_timestamp_to_seconds("0") == pytest.approx(0.0)


class TestParseTimestampWhitespace:
    """Test that whitespace is handled correctly."""

    def test_strip_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        assert parse_timestamp_to_seconds(" 01:23.456 ") == pytest.approx(83.456)
        assert parse_timestamp_to_seconds("  02:45  ") == pytest.approx(165.0)
        assert parse_timestamp_to_seconds("  01:23:45.123  ") == pytest.approx(5025.123)
        assert parse_timestamp_to_seconds("  100.5  ") == pytest.approx(100.5)


class TestParseTimestampErrorHandling:
    """Test error handling in timestamp parsing."""

    def test_invalid_format_returns_zero(self):
        """Test that invalid formats return 0.0 instead of raising exceptions."""
        assert parse_timestamp_to_seconds("invalid") == 0.0
        assert parse_timestamp_to_seconds("") == 0.0
        assert parse_timestamp_to_seconds("no:colons:here:extra") == 0.0
        assert parse_timestamp_to_seconds("12:34:56:78") == 0.0  # Too many parts

    def test_malformed_timestamps(self):
        """Test that malformed timestamps don't crash the parser."""
        assert parse_timestamp_to_seconds(":") == 0.0
        assert parse_timestamp_to_seconds("::") == 0.0
        assert parse_timestamp_to_seconds(":23") == 0.0
        assert parse_timestamp_to_seconds("abc:def") == 0.0


class TestIntegrationWithVideoProcessing:
    """Integration tests for timestamp parsing in video processing context."""

    def test_segment_duration_calculation(self):
        """Test that parsed timestamps can be used to calculate valid durations."""
        # Simulate what happens in create_clips_from_segments
        start_str = "00:03:08.120"
        end_str = "00:03:28.450"

        start_seconds = parse_timestamp_to_seconds(start_str)
        end_seconds = parse_timestamp_to_seconds(end_str)
        duration = end_seconds - start_seconds

        # Should get valid clip duration
        assert start_seconds == pytest.approx(188.120)
        assert end_seconds == pytest.approx(208.450)
        assert duration == pytest.approx(20.330, abs=0.001)
        assert duration > 5.0, "Duration should be greater than 5 seconds for valid clip"

    def test_multiple_clips_timestamp_sequence(self):
        """Test parsing multiple clip timestamps in sequence."""
        clips = [
            ("00:10.500", "00:30.750"),
            ("00:45.000", "01:05.200"),
            ("02:00.100", "02:25.800"),
        ]

        for start_str, end_str in clips:
            start = parse_timestamp_to_seconds(start_str)
            end = parse_timestamp_to_seconds(end_str)
            duration = end - start

            # All clips should have valid durations
            assert start >= 0, f"Start time should be non-negative for {start_str}"
            assert end > start, f"End time should be greater than start time for {start_str}-{end_str}"
            assert duration > 5.0, f"Duration should be > 5s for {start_str}-{end_str}, got {duration}"

    def test_backward_compatibility_with_old_formats(self):
        """Test that old timestamp formats still work."""
        # These might come from older AI models or cached data
        old_format_tests = [
            ("03:08", 188.0),
            ("05:45", 345.0),
            ("1:23", 83.0),
        ]

        for timestamp_str, expected in old_format_tests:
            result = parse_timestamp_to_seconds(timestamp_str)
            assert result == pytest.approx(expected), \
                f"Old format {timestamp_str} should parse to {expected}, got {result}"
