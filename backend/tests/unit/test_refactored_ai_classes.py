# start tests/unit/test_refactored_ai_classes.py
"""
Unit tests for refactored AI helper classes.

Tests the extracted classes from VUW-COMP-006:
- CleanStartValidator
- TimestampParser
- TranscriptSegmentValidator
"""

import pytest
from src.ai import (
    CleanStartValidator,
    TimestampParser,
    TranscriptSegmentValidator,
    TranscriptSegment,
)


class TestCleanStartValidator:
    """Tests for CleanStartValidator class."""

    def test_validate_clean_start_returns_tuple(self):
        """Verify validate() returns tuple of (bool, str)."""
        result = CleanStartValidator.validate("The main thing")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_validate_allows_clean_starts(self):
        """Verify clean starts are accepted."""
        test_cases = [
            "The main thing you need to know",
            "Here's what I discovered",
            "This is incredibly important",
            "Amazing things happen when",
            "Technology revolutionizes everything",
        ]
        for text in test_cases:
            is_valid, reason = CleanStartValidator.validate(text)
            assert is_valid, f"Should accept '{text}' but got: {reason}"

    def test_validate_rejects_forbidden_starts(self):
        """Verify forbidden starts are rejected."""
        test_cases = {
            "And the next thing": "and",
            "But wait there's more": "but",
            "So here's what happens": "so",
            "Well I'm telling you": "well",
            "Because that's the way": "because",
            "Also don't forget": "also",
            "Um let me think": "um",
            "Uh I think so": "uh",
            "You know what they say": "you know",
            "I mean obviously": "i mean",
            "Like really amazing": "like",
        }
        for text, forbidden_word in test_cases.items():
            is_valid, reason = CleanStartValidator.validate(text)
            assert not is_valid, f"Should reject '{text}'"
            assert forbidden_word in reason.lower()

    def test_validate_case_insensitive(self):
        """Verify validation is case-insensitive."""
        test_cases = [
            "AND the next thing",
            "AND The Next Thing",
            "And The Next Thing",
            "BUT wait",
            "But Wait",
            "SO here's",
            "So Here's",
        ]
        for text in test_cases:
            is_valid, _ = CleanStartValidator.validate(text)
            assert not is_valid, f"Should reject '{text}' (case-insensitive)"

    def test_validate_whitespace_handling(self):
        """Verify validation handles whitespace correctly."""
        text_with_spaces = "   And the thing   "
        is_valid, _ = CleanStartValidator.validate(text_with_spaces)
        assert not is_valid, "Should reject text with leading forbidden word"

    def test_validate_partial_matches_not_rejected(self):
        """Verify words containing forbidden patterns are allowed."""
        test_cases = [
            "Android is great",  # Contains "and" but doesn't start with "and "
            "Bummer you missed it",  # Contains "but" but doesn't start with "but "
            "Like-minded people",  # Contains "like" but word boundary matters
        ]
        for text in test_cases:
            is_valid, _ = CleanStartValidator.validate(text)
            assert is_valid, f"Should accept '{text}' (partial match is OK)"

    def test_forbidden_starts_constant(self):
        """Verify FORBIDDEN_STARTS constant is defined and populated."""
        assert hasattr(CleanStartValidator, "FORBIDDEN_STARTS")
        assert isinstance(CleanStartValidator.FORBIDDEN_STARTS, list)
        assert len(CleanStartValidator.FORBIDDEN_STARTS) > 0
        # All items should end with space or be multi-word
        for item in CleanStartValidator.FORBIDDEN_STARTS:
            assert item.endswith(" ") or " " in item or item == "like "


class TestTimestampParser:
    """Tests for TimestampParser class."""

    def test_parse_timestamp_valid_format(self):
        """Verify parsing valid MM:SS timestamps."""
        test_cases = {
            "00:00": 0,
            "00:10": 10,
            "01:00": 60,
            "02:30": 150,
            "10:45": 645,
            "59:59": 3599,
        }
        for timestamp, expected_seconds in test_cases.items():
            result = TimestampParser.parse_timestamp(timestamp)
            assert result == expected_seconds, f"'{timestamp}' should parse to {expected_seconds}s"

    def test_parse_timestamp_invalid_format_raises_error(self):
        """Verify invalid timestamps raise ValueError."""
        invalid_timestamps = [
            "invalid",
            "1:2:3",  # Too many colons
            "1",  # No colon
            "abc:def",  # Non-numeric
            "",
            ":",
        ]
        for timestamp in invalid_timestamps:
            with pytest.raises(ValueError):
                TimestampParser.parse_timestamp(timestamp)

    def test_calculate_duration_basic(self):
        """Verify duration calculation between two timestamps."""
        test_cases = {
            ("00:00", "00:10"): 10,
            ("00:00", "01:00"): 60,
            ("01:00", "01:30"): 30,
            ("02:25", "02:35"): 10,
            ("10:00", "10:05"): 5,
        }
        for (start, end), expected_duration in test_cases.items():
            result = TimestampParser.calculate_duration(start, end)
            assert result == expected_duration

    def test_calculate_duration_invalid_timestamps(self):
        """Verify duration calculation with invalid timestamps raises error."""
        with pytest.raises(ValueError):
            TimestampParser.calculate_duration("invalid", "00:10")

    def test_validate_duration_positive_duration(self):
        """Verify validation accepts positive durations above minimum."""
        valid_durations = [5, 10, 15, 30, 60, 120]
        for duration in valid_durations:
            is_valid, _ = TimestampParser.validate_duration(duration)
            assert is_valid, f"Duration {duration}s should be valid"

    def test_validate_duration_minimum_requirement(self):
        """Verify validation rejects durations below minimum."""
        min_duration = TimestampParser.MIN_DURATION_SECONDS
        invalid_durations = [0, -1, -10, 1, 2, min_duration - 1]
        for duration in invalid_durations:
            is_valid, reason = TimestampParser.validate_duration(duration)
            assert not is_valid, f"Duration {duration}s should be invalid"
            assert "min" in reason.lower() or duration <= 0

    def test_min_duration_seconds_constant(self):
        """Verify MIN_DURATION_SECONDS is defined."""
        assert hasattr(TimestampParser, "MIN_DURATION_SECONDS")
        assert isinstance(TimestampParser.MIN_DURATION_SECONDS, int)
        assert TimestampParser.MIN_DURATION_SECONDS > 0


class TestTranscriptSegmentValidator:
    """Tests for TranscriptSegmentValidator class."""

    def test_validate_text_content_valid(self):
        """Verify validation accepts sufficient text content."""
        valid_texts = [
            "This is a test",
            "Hello world test",
            "One two three four five",
            "A very long piece of text with many words that should definitely pass",
        ]
        for text in valid_texts:
            is_valid, _ = TranscriptSegmentValidator.validate_text_content(text)
            assert is_valid, f"Should accept '{text}'"

    def test_validate_text_content_empty(self):
        """Verify validation rejects empty text."""
        is_valid, reason = TranscriptSegmentValidator.validate_text_content("")
        assert not is_valid
        assert "empty" in reason.lower()

    def test_validate_text_content_whitespace_only(self):
        """Verify validation rejects whitespace-only text."""
        is_valid, reason = TranscriptSegmentValidator.validate_text_content("   ")
        assert not is_valid

    def test_validate_text_content_too_few_words(self):
        """Verify validation rejects text with too few words."""
        min_words = TranscriptSegmentValidator.MIN_WORD_COUNT
        text_one_word = "Hello"
        text_two_words = "Hello world"

        is_valid, reason = TranscriptSegmentValidator.validate_text_content(text_one_word)
        assert not is_valid, "Should reject single word"

        is_valid, reason = TranscriptSegmentValidator.validate_text_content(text_two_words)
        if min_words > 2:
            assert not is_valid, f"Should reject {min_words - 1} words"

    def test_validate_timestamps_valid_segment(self):
        """Verify timestamp validation accepts valid segments."""
        segment = TranscriptSegment(
            start_time="00:00",
            end_time="00:10",
            text="Test text",
            relevance_score=0.8,
            reasoning="Good test",
        )
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        assert is_valid, f"Valid segment should pass: {reason}"

    def test_validate_timestamps_identical_times(self):
        """Verify validation rejects identical start and end times."""
        segment = TranscriptSegment(
            start_time="00:10",
            end_time="00:10",
            text="Test text",
            relevance_score=0.8,
            reasoning="Identical times",
        )
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        assert not is_valid
        assert "identical" in reason.lower()

    def test_validate_timestamps_too_short(self):
        """Verify validation rejects segments that are too short."""
        min_duration = TimestampParser.MIN_DURATION_SECONDS
        segment = TranscriptSegment(
            start_time="00:00",
            end_time=f"00:{min_duration - 1:02d}",  # One second short
            text="Test text",
            relevance_score=0.8,
            reasoning="Too short",
        )
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        assert not is_valid, f"Should reject segment shorter than {min_duration}s"

    def test_validate_segment_comprehensive(self):
        """Verify comprehensive segment validation."""
        # Valid segment
        valid_segment = TranscriptSegment(
            start_time="02:25",
            end_time="02:35",
            text="This is the main thing you need to know",
            relevance_score=0.9,
            reasoning="Strong content",
        )
        is_valid, reason, duration = TranscriptSegmentValidator.validate_segment(valid_segment)
        assert is_valid, f"Valid segment should pass: {reason}"
        assert duration == 10, "Duration should be 10s"

    def test_validate_segment_with_forbidden_start(self):
        """Verify comprehensive validation rejects forbidden starts."""
        segment = TranscriptSegment(
            start_time="02:25",
            end_time="02:35",
            text="And here's the thing you need to know",
            relevance_score=0.9,
            reasoning="But starts with 'And'",
        )
        is_valid, reason, _ = TranscriptSegmentValidator.validate_segment(segment)
        assert not is_valid, "Should reject segment with forbidden start"
        assert "forbidden" in reason.lower() or "and" in reason.lower()

    def test_validate_segment_empty_text(self):
        """Verify comprehensive validation rejects empty text."""
        segment = TranscriptSegment(
            start_time="02:25",
            end_time="02:35",
            text="",
            relevance_score=0.9,
            reasoning="Empty text",
        )
        is_valid, reason, _ = TranscriptSegmentValidator.validate_segment(segment)
        assert not is_valid, "Should reject empty text"
        assert "text" in reason.lower()

    def test_min_word_count_constant(self):
        """Verify MIN_WORD_COUNT constant is defined."""
        assert hasattr(TranscriptSegmentValidator, "MIN_WORD_COUNT")
        assert isinstance(TranscriptSegmentValidator.MIN_WORD_COUNT, int)
        assert TranscriptSegmentValidator.MIN_WORD_COUNT >= 1


# end tests/unit/test_refactored_ai_classes.py
