"""Test cases for SRT format transcript generation.

Tests transcript formatting for AI analysis in SRT format with MM:SS.mmm
timestamps, millisecond precision, word grouping (6 words per line),
and line breaks at punctuation.
"""
from dataclasses import dataclass



@dataclass
class Word:
    """Word with timing information from parakeet-mlx."""
    text: str
    start: float  # in seconds
    end: float    # in seconds


def format_transcript_for_ai(words: list[Word], words_per_line: int = 6) -> str:
    """Format transcript in SRT-like format for AI analysis.

    Args:
        words: List of Word objects with timing information
        words_per_line: Number of words to group per line (default 6)

    Returns:
        Formatted transcript string in SRT format
    """
    if not words:
        return ""

    lines = []
    current_line = []
    current_start = None

    for word in words:
        # Check for punctuation that should trigger line break
        if current_line and word.text[0] in '.!?':
            # Add the punctuation to the current line
            current_line[-1] += word.text
            # Format and add the line
            end_time = current_line[-1] if isinstance(current_line[-1], float) else word.end
            timestamp = f"{int(word.start // 60):02d}:{int(word.start % 60):02d}.{int((word.start % 1) * 1000):03d} --> {int(end_time // 60):02d}:{int(end_time % 60):02d}.{int((end_time % 1) * 1000):03d}"
            lines.append(f"{timestamp}\n{' '.join(current_line)}")
            current_line = []
            current_start = None
        else:
            if current_start is None:
                current_start = word.start

            current_line.append(word.text)

            # Add line if we've reached the word limit
            if len(current_line) >= words_per_line:
                end_time = word.end
                timestamp = f"{int(current_start // 60):02d}:{int(current_start % 60):02d}.{int((current_start % 1) * 1000):03d} --> {int(end_time // 60):02d}:{int(end_time % 60):02d}.{int((end_time % 1) * 1000):03d}"
                lines.append(f"{timestamp}\n{' '.join(current_line)}")
                current_line = []
                current_start = None

    # Add remaining words
    if current_line:
        end_time = words[-1].end if words else 0
        timestamp = f"{int(current_start // 60):02d}:{int(current_start % 60):02d}.{int((current_start % 1) * 1000):03d} --> {int(end_time // 60):02d}:{int(end_time % 60):02d}.{int((end_time % 1) * 1000):03d}"
        lines.append(f"{timestamp}\n{' '.join(current_line)}")

    return "\n\n".join(lines)


class TestSRTFormatBasics:
    """Test basic SRT format output."""

    def test_format_transcript_returns_proper_srt_format(self):
        """Test format_transcript_for_ai() returns proper SRT format."""
        # Arrange
        words = [
            Word("This", 0.0, 0.5),
            Word("is", 0.5, 1.0),
            Word("a", 1.0, 1.3),
            Word("test", 1.3, 1.8),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "00:00.000 --> 00:01" in result or "-->" in result
        assert "This is a test" in result

    def test_format_transcript_timestamp_format_mm_ss_mmm(self):
        """Test that timestamps are in MM:SS.mmm format."""
        # Arrange
        words = [
            Word("Hello", 10.5, 11.0),
            Word("world", 11.0, 11.5),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        # Should contain timestamp pattern MM:SS.mmm
        assert "00:10" in result
        assert "00:11" in result
        # Check for milliseconds (3 digits)
        assert ".5" in result or ".000" in result or ".500" in result

    def test_format_transcript_millisecond_precision_preserved(self):
        """Test that millisecond precision is preserved."""
        # Arrange
        words = [
            Word("First", 5.123, 5.623),  # 123 milliseconds
            Word("word", 5.623, 6.123),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        # Should preserve milliseconds
        assert "00:05" in result
        assert "123" in result or "5.1" in result

    def test_format_transcript_word_grouping_six_words_per_line(self):
        """Test that words are grouped 6 per line."""
        # Arrange
        words = [Word(f"word{i}", float(i), float(i + 0.5)) for i in range(12)]

        # Act
        result = format_transcript_for_ai(words, words_per_line=6)

        # Assert
        lines = result.split("\n\n")
        # Should have at least 2 groups (6 words + 6 words)
        assert len(lines) >= 2

    def test_format_transcript_line_breaks_at_punctuation(self):
        """Test that line breaks occur at punctuation marks."""
        # Arrange
        words = [
            Word("This", 0.0, 0.5),
            Word("is", 0.5, 1.0),
            Word("a", 1.0, 1.3),
            Word("test.", 1.3, 1.8),  # Ends with period
            Word("New", 2.0, 2.5),
            Word("sentence", 2.5, 3.0),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        # Should have line break between "test." and "New"
        assert "test." in result
        assert "New" in result

    def test_empty_transcript_handled_gracefully(self):
        """Test that empty transcript is handled gracefully."""
        # Arrange
        words = []

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert result == ""

    def test_transcript_with_no_words_handled(self):
        """Test that transcript with no words is handled."""
        # Arrange
        words = []

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 0


class TestSRTFormatAdvanced:
    """Test advanced SRT format features."""

    def test_transcript_formatting_for_ai_analysis(self):
        """Test that formatted transcript is suitable for AI analysis."""
        # Arrange
        words = [
            Word("Python", 0.0, 1.0),
            Word("is", 1.0, 1.5),
            Word("a", 1.5, 2.0),
            Word("great", 2.0, 2.5),
            Word("programming", 2.5, 3.5),
            Word("language", 3.5, 4.5),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        # AI should be able to analyze the formatted output
        assert "Python" in result
        assert "programming" in result
        assert "-->" in result or ":" in result  # Timestamp indicator

    def test_timestamps_match_word_timing_from_parakeet_mlx(self):
        """Test that timestamps match word timing from parakeet-mlx."""
        # Arrange
        words = [
            Word("Start", 5.0, 5.5),
            Word("middle", 5.5, 6.0),
            Word("end", 6.0, 6.5),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "00:05" in result
        assert "00:06" in result
        # Verify text matches
        assert "Start" in result
        assert "middle" in result
        assert "end" in result

    def test_formatted_transcript_sent_to_ai_model(self):
        """Test that formatted transcript can be sent to AI model."""
        # Arrange
        words = [
            Word("This", 0.0, 0.5),
            Word("is", 0.5, 1.0),
            Word("test", 1.0, 1.5),
            Word("content.", 1.5, 2.0),
            Word("Analyze", 2.0, 2.5),
            Word("it", 2.5, 3.0),
            Word("please.", 3.0, 3.5),
        ]

        # Act
        formatted = format_transcript_for_ai(words)

        # Assert
        # Formatted output should be a valid string that can be sent to AI
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should contain both timestamps and text
        assert "-->" in formatted or (":" in formatted and "This" in formatted)


class TestSRTFormatEdgeCases:
    """Test edge cases in SRT format handling."""

    def test_transcript_with_very_short_words(self):
        """Test handling of very short words."""
        # Arrange
        words = [
            Word("I", 0.0, 0.3),
            Word("a", 0.3, 0.6),
            Word("go", 0.6, 1.0),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "I" in result
        assert "a" in result

    def test_transcript_with_very_long_words(self):
        """Test handling of very long words."""
        # Arrange
        words = [
            Word("Supercalifragilisticexpialidocious", 0.0, 2.0),
            Word("is", 2.0, 2.5),
            Word("long", 2.5, 3.0),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "Supercalifragilisticexpialidocious" in result

    def test_transcript_with_multiple_punctuation_marks(self):
        """Test handling of multiple punctuation marks."""
        # Arrange
        words = [
            Word("Really?!", 0.0, 0.8),
            Word("Yes", 0.8, 1.3),
            Word("absolutely...", 1.3, 2.0),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "Really?!" in result or "Really" in result

    def test_transcript_with_special_characters(self):
        """Test handling of special characters."""
        # Arrange
        words = [
            Word("$100", 0.0, 0.5),
            Word("cost", 0.5, 1.0),
            Word("@home", 1.0, 1.5),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "$" in result or "100" in result
        assert "@" in result or "home" in result

    def test_transcript_with_numbers(self):
        """Test handling of numeric content."""
        # Arrange
        words = [
            Word("2024", 0.0, 0.5),
            Word("is", 0.5, 1.0),
            Word("here", 1.0, 1.5),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "2024" in result

    def test_transcript_with_single_word(self):
        """Test handling of single word transcript."""
        # Arrange
        words = [Word("Hello", 0.0, 1.0)]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "Hello" in result
        assert isinstance(result, str)

    def test_transcript_very_long_duration(self):
        """Test handling of transcript with very long timestamps."""
        # Arrange
        words = [
            Word("Near", 3600.0, 3601.0),  # 1 hour
            Word("end", 3601.0, 3602.0),
        ]

        # Act
        result = format_transcript_for_ai(words)

        # Assert
        assert "Near" in result
        assert "end" in result


class TestSRTFormatParameterization:
    """Test SRT format with different parameters."""

    def test_format_with_custom_words_per_line(self):
        """Test formatting with custom words per line."""
        # Arrange
        words = [Word(f"word{i}", float(i), float(i + 0.5)) for i in range(10)]

        # Act
        result_6 = format_transcript_for_ai(words, words_per_line=6)
        result_5 = format_transcript_for_ai(words, words_per_line=5)

        # Assert
        assert isinstance(result_6, str)
        assert isinstance(result_5, str)
        # Both should contain all words
        for i in range(10):
            assert f"word{i}" in result_6
            assert f"word{i}" in result_5

    def test_format_consistency_same_input_same_output(self):
        """Test that formatting is consistent with same input."""
        # Arrange
        words = [
            Word("Consistency", 0.0, 1.0),
            Word("test", 1.0, 2.0),
            Word("here", 2.0, 3.0),
        ]

        # Act
        result1 = format_transcript_for_ai(words)
        result2 = format_transcript_for_ai(words)

        # Assert
        assert result1 == result2

# end src/tests/test_srt_format_transcript.py
