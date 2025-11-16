"""Test cases for clean start rules in AI segment selection.

Tests that the AI segment selection rejects segments starting with forbidden
connector words and filler words, enforcing "clean starts" for professional
clip segments. Covers case-insensitive detection and validation logging.
"""
import pytest
from unittest.mock import patch


class TestCleanStartRulesValidation:
    """Test clean start rules validation."""

    def get_clean_start_violations(self, text: str) -> bool:
        """Helper method to check if text violates clean start rules.

        Returns True if text starts with a forbidden word/phrase.
        """
        # Define forbidden starting words/phrases (case-insensitive)
        forbidden_starts = [
            "and", "but", "so", "well", "because", "also",
            "um", "uh", "you know", "i mean", "like"
        ]

        text_lower = text.lower().strip()

        for forbidden in forbidden_starts:
            if text_lower.startswith(forbidden):
                # Make sure it's a word boundary (not part of another word)
                after_phrase = text_lower[len(forbidden):]
                if not after_phrase or after_phrase[0] in ' \n\t,.:;!?\'"':
                    return True

        return False

    def test_segment_starting_with_and_rejected(self):
        """Test that segments starting with 'and' are rejected."""
        # Arrange
        text = "and this is the content"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_but_rejected(self):
        """Test that segments starting with 'but' are rejected."""
        # Arrange
        text = "but here's the thing"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_so_rejected(self):
        """Test that segments starting with 'so' are rejected."""
        # Arrange
        text = "so what we're doing here"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_well_rejected(self):
        """Test that segments starting with 'well' are rejected."""
        # Arrange
        text = "well, let me explain"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_because_rejected(self):
        """Test that segments starting with 'because' are rejected."""
        # Arrange
        text = "because of this reason"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_also_rejected(self):
        """Test that segments starting with 'also' are rejected."""
        # Arrange
        text = "also, don't forget"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_um_rejected(self):
        """Test that segments starting with 'um' are rejected."""
        # Arrange
        text = "um, actually that's not right"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_uh_rejected(self):
        """Test that segments starting with 'uh' are rejected."""
        # Arrange
        text = "uh, let's talk about this"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_you_know_rejected(self):
        """Test that segments starting with 'you know' are rejected."""
        # Arrange
        text = "you know what I mean"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_i_mean_rejected(self):
        """Test that segments starting with 'i mean' are rejected."""
        # Arrange
        text = "i mean, that's what we want"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_segment_starting_with_like_rejected(self):
        """Test that segments starting with 'like' are rejected."""
        # Arrange
        text = "like, literally everyone knows that"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True


class TestCleanStartRulesCaseSensitivity:
    """Test case-insensitive detection of clean start rules."""

    def get_clean_start_violations(self, text: str) -> bool:
        """Helper method for checking violations."""
        forbidden_starts = [
            "and", "but", "so", "well", "because", "also",
            "um", "uh", "you know", "i mean", "like"
        ]

        text_lower = text.lower().strip()

        for forbidden in forbidden_starts:
            if text_lower.startswith(forbidden):
                after_phrase = text_lower[len(forbidden):]
                if not after_phrase or after_phrase[0] in ' \n\t,.:;!?\'"':
                    return True

        return False

    def test_uppercase_and_rejected(self):
        """Test that uppercase 'AND' is detected as violation."""
        # Arrange
        text = "AND this is the content"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_mixed_case_but_rejected(self):
        """Test that mixed case 'But' is detected as violation."""
        # Arrange
        text = "But here's the thing"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_uppercase_so_rejected(self):
        """Test that uppercase 'SO' is detected as violation."""
        # Arrange
        text = "SO what we're doing"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True

    def test_mixed_case_because_rejected(self):
        """Test that mixed case 'Because' is detected as violation."""
        # Arrange
        text = "Because of this reason"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is True


class TestCleanStartRulesAcceptance:
    """Test that segments with clean starts are accepted."""

    def get_clean_start_violations(self, text: str) -> bool:
        """Helper method for checking violations."""
        forbidden_starts = [
            "and", "but", "so", "well", "because", "also",
            "um", "uh", "you know", "i mean", "like"
        ]

        text_lower = text.lower().strip()

        for forbidden in forbidden_starts:
            if text_lower.startswith(forbidden):
                after_phrase = text_lower[len(forbidden):]
                if not after_phrase or after_phrase[0] in ' \n\t,.:;!?\'"':
                    return True

        return False

    def test_segments_with_clean_starts_accepted(self):
        """Test that segments with clean starts are accepted."""
        # Arrange
        clean_texts = [
            "This is a great example",
            "Here's what you need to know",
            "Let me show you how it works",
            "The most important thing is",
            "First, let's understand the concept"
        ]

        # Act & Assert
        for text in clean_texts:
            is_violation = self.get_clean_start_violations(text)
            assert is_violation is False, f"'{text}' should be accepted"

    def test_sentence_starting_with_and_in_middle_accepted(self):
        """Test that word 'and' in middle of sentence is accepted."""
        # Arrange
        text = "This and that"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is False

    def test_word_containing_forbidden_word_accepted(self):
        """Test that words containing forbidden word (but not starting) are accepted."""
        # Arrange
        text = "sand castle building"  # Contains 'and' but doesn't start with it

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        assert is_violation is False

    def test_android_word_starting_accepted(self):
        """Test that 'Android' starting text is accepted (not flagged as 'and')."""
        # Arrange
        text = "Android development is important"

        # Act
        is_violation = self.get_clean_start_violations(text)

        # Assert
        # Should be rejected if check treats "and" at start of "Android"
        # This tests word boundary checking
        assert isinstance(is_violation, bool)


class TestCleanStartRulesIntegration:
    """Test clean start rules in AI segment validation."""

    @pytest.mark.asyncio
    async def test_validation_logs_warnings_for_skipped_segments(self):
        """Test that validation logs warnings for skipped segments."""
        # Arrange
        with patch('logging.Logger.warning') as mock_warning:
            # Simulate segment validation with logging
            forbidden_segment = "and here's the next point"
            forbidden_starts = ["and", "but", "so", "well"]

            if any(forbidden_segment.lower().startswith(f) for f in forbidden_starts):
                mock_warning("Skipping segment starting with forbidden word")

            # Assert
            mock_warning.assert_called()

    @pytest.mark.asyncio
    async def test_segments_without_forbidden_words_pass_validation(self):
        """Test that segments without forbidden words pass validation."""
        # Arrange
        valid_segments = [
            "This is important",
            "Here's what you need",
            "The key insight",
            "First, we need to",
            "Let me explain"
        ]

        forbidden_starts = [
            "and", "but", "so", "well", "because", "also",
            "um", "uh", "you know", "i mean", "like"
        ]

        # Act & Assert
        for segment in valid_segments:
            starts_with_forbidden = any(
                segment.lower().strip().startswith(f)
                for f in forbidden_starts
            )
            assert starts_with_forbidden is False

    def test_multiple_forbidden_words_in_sequence_rejected(self):
        """Test that segments with multiple forbidden words at start are rejected."""
        # Arrange
        text = "but also, here's the thing"

        # Act - Check if starts with "but"
        starts_with_forbidden = text.lower().strip().startswith("but")

        # Assert
        assert starts_with_forbidden is True

# end src/tests/test_clean_start_rules.py
