"""
Tests for word-level timestamp extraction from parakeet-mlx.

This module tests that _extract_words_from_result properly extracts
word-level tokens from AlignedSentence objects, NOT BPE sub-word tokens.

The key insight: parakeet-mlx provides word-level timestamps via
result.sentences[].tokens, not via result.tokens (which are sub-word).
"""

import pytest
from typing import Any
from dataclasses import dataclass
from src.transcription_mlx import _extract_words_from_result


@dataclass
class MockAlignedToken:
    """Mock AlignedToken from parakeet-mlx."""

    text: str
    start: float  # seconds
    end: float  # seconds
    confidence: float = 1.0


@dataclass
class MockAlignedSentence:
    """Mock AlignedSentence from parakeet-mlx with word-level tokens."""

    text: str
    start: float
    end: float
    tokens: list[MockAlignedToken]

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class MockAlignedResult:
    """
    Mock AlignedResult from parakeet-mlx.

    IMPORTANT: This simulates the real parakeet-mlx structure where:
    - result.tokens = flattened BPE sub-word tokens (WRONG for word extraction)
    - result.sentences[].tokens = word-level tokens (CORRECT for word extraction)
    """

    text: str
    sentences: list[MockAlignedSentence]
    # The flattened tokens list contains BPE sub-word fragments
    tokens: list[MockAlignedToken]


class TestWordExtraction:
    """Test word-level extraction from parakeet-mlx results."""

    def test_extracts_words_not_bpe_tokens(self) -> None:
        """
        Verify that extraction gets WORDS, not BPE sub-word tokens.

        This is the core test: if we're extracting from result.tokens directly,
        we'll get BPE fragments like ["Y", "es", "I", "th", "ink"].
        If we're extracting from result.sentences[].tokens correctly,
        we'll get words like ["Yes", "I", "think"].
        """
        # Create mock result with BOTH:
        # 1. BPE sub-word tokens in result.tokens (the WRONG source)
        # 2. Word-level tokens in result.sentences[].tokens (the RIGHT source)

        # BPE sub-word tokens (what result.tokens contains - WRONG)
        bpe_tokens = [
            MockAlignedToken(text="Y", start=0.0, end=0.1, confidence=0.99),
            MockAlignedToken(text="es", start=0.1, end=0.2, confidence=0.99),
            MockAlignedToken(text=",", start=0.2, end=0.25, confidence=0.99),
            MockAlignedToken(text="I", start=0.3, end=0.4, confidence=0.99),
            MockAlignedToken(text="th", start=0.4, end=0.5, confidence=0.99),
            MockAlignedToken(text="ink", start=0.5, end=0.7, confidence=0.99),
            MockAlignedToken(text="so", start=0.8, end=1.0, confidence=0.99),
            MockAlignedToken(text=".", start=1.0, end=1.1, confidence=0.99),
        ]

        # Word-level tokens (what sentences[].tokens contains - CORRECT)
        word_tokens = [
            MockAlignedToken(text="Yes,", start=0.0, end=0.25, confidence=0.99),
            MockAlignedToken(text="I", start=0.3, end=0.4, confidence=0.99),
            MockAlignedToken(text="think", start=0.4, end=0.7, confidence=0.99),
            MockAlignedToken(text="so.", start=0.8, end=1.1, confidence=0.99),
        ]

        sentence = MockAlignedSentence(
            text="Yes, I think so.",
            start=0.0,
            end=1.1,
            tokens=word_tokens,
        )

        result = MockAlignedResult(
            text="Yes, I think so.",
            sentences=[sentence],
            tokens=bpe_tokens,  # BPE fragments - should NOT be used
        )

        # Extract words
        words = _extract_words_from_result(result)

        # CRITICAL ASSERTION: We should get 4 WORDS, not 8 BPE tokens
        assert len(words) == 4, (
            f"Expected 4 words but got {len(words)}. "
            f"Texts: {[w['text'] for w in words]}. "
            "If you got 8, you're extracting BPE tokens instead of words!"
        )

        # Verify we got actual words, not fragments
        texts = [w["text"] for w in words]
        assert "Yes," in texts or "Yes" in texts[0], f"Expected 'Yes' but got {texts}"
        assert "think" in texts, f"Expected 'think' but got {texts}"
        assert "so." in texts or "so" in texts[-1], f"Expected 'so' but got {texts}"

        # Verify no BPE fragments leaked through
        assert "Y" not in texts, "BPE fragment 'Y' should not appear"
        assert "es" not in texts, "BPE fragment 'es' should not appear"
        assert "th" not in texts, "BPE fragment 'th' should not appear"
        assert "ink" not in texts, "BPE fragment 'ink' should not appear"

    def test_preserves_word_timing(self) -> None:
        """Verify that word timing is preserved correctly."""
        word_tokens = [
            MockAlignedToken(text="Hello", start=1.5, end=2.0, confidence=0.95),
            MockAlignedToken(text="world", start=2.1, end=2.8, confidence=0.98),
        ]

        sentence = MockAlignedSentence(
            text="Hello world",
            start=1.5,
            end=2.8,
            tokens=word_tokens,
        )

        result = MockAlignedResult(
            text="Hello world",
            sentences=[sentence],
            tokens=[],  # Empty - shouldn't matter if using sentences
        )

        words = _extract_words_from_result(result)

        assert len(words) == 2

        # Check first word timing (converted to milliseconds)
        assert words[0]["text"] == "Hello"
        assert words[0]["start"] == 1500  # 1.5 seconds = 1500ms
        assert words[0]["end"] == 2000  # 2.0 seconds = 2000ms

        # Check second word timing
        assert words[1]["text"] == "world"
        assert words[1]["start"] == 2100
        assert words[1]["end"] == 2800

    def test_handles_multiple_sentences(self) -> None:
        """Verify extraction works across multiple sentences."""
        sentence1 = MockAlignedSentence(
            text="First sentence.",
            start=0.0,
            end=1.0,
            tokens=[
                MockAlignedToken(text="First", start=0.0, end=0.4, confidence=0.99),
                MockAlignedToken(text="sentence.", start=0.5, end=1.0, confidence=0.99),
            ],
        )

        sentence2 = MockAlignedSentence(
            text="Second one.",
            start=1.2,
            end=2.0,
            tokens=[
                MockAlignedToken(text="Second", start=1.2, end=1.5, confidence=0.99),
                MockAlignedToken(text="one.", start=1.6, end=2.0, confidence=0.99),
            ],
        )

        result = MockAlignedResult(
            text="First sentence. Second one.",
            sentences=[sentence1, sentence2],
            tokens=[],
        )

        words = _extract_words_from_result(result)

        assert len(words) == 4
        texts = [w["text"] for w in words]
        assert texts == ["First", "sentence.", "Second", "one."]

    def test_preserves_confidence_scores(self) -> None:
        """Verify confidence scores are preserved."""
        word_tokens = [
            MockAlignedToken(text="Confident", start=0.0, end=0.5, confidence=0.99),
            MockAlignedToken(text="word", start=0.6, end=1.0, confidence=0.75),
        ]

        sentence = MockAlignedSentence(
            text="Confident word",
            start=0.0,
            end=1.0,
            tokens=word_tokens,
        )

        result = MockAlignedResult(
            text="Confident word",
            sentences=[sentence],
            tokens=[],
        )

        words = _extract_words_from_result(result)

        assert words[0]["confidence"] == 0.99
        assert words[1]["confidence"] == 0.75

    def test_skips_empty_tokens(self) -> None:
        """Verify empty/whitespace tokens are skipped."""
        word_tokens = [
            MockAlignedToken(text="Hello", start=0.0, end=0.5, confidence=0.99),
            MockAlignedToken(text="", start=0.5, end=0.6, confidence=0.99),  # Empty
            MockAlignedToken(text="  ", start=0.6, end=0.7, confidence=0.99),  # Whitespace
            MockAlignedToken(text="world", start=0.7, end=1.0, confidence=0.99),
        ]

        sentence = MockAlignedSentence(
            text="Hello world",
            start=0.0,
            end=1.0,
            tokens=word_tokens,
        )

        result = MockAlignedResult(
            text="Hello world",
            sentences=[sentence],
            tokens=[],
        )

        words = _extract_words_from_result(result)

        assert len(words) == 2
        assert [w["text"] for w in words] == ["Hello", "world"]

    def test_skips_invalid_timing(self) -> None:
        """Verify tokens with invalid timing (start >= end) are skipped."""
        word_tokens = [
            MockAlignedToken(text="Valid", start=0.0, end=0.5, confidence=0.99),
            MockAlignedToken(
                text="Invalid", start=0.5, end=0.5, confidence=0.99
            ),  # start == end
            MockAlignedToken(
                text="Also_Invalid", start=0.8, end=0.6, confidence=0.99
            ),  # start > end
            MockAlignedToken(text="Good", start=0.9, end=1.2, confidence=0.99),
        ]

        sentence = MockAlignedSentence(
            text="Valid Invalid Also_Invalid Good",
            start=0.0,
            end=1.2,
            tokens=word_tokens,
        )

        result = MockAlignedResult(
            text="Valid Invalid Also_Invalid Good",
            sentences=[sentence],
            tokens=[],
        )

        words = _extract_words_from_result(result)

        assert len(words) == 2
        assert [w["text"] for w in words] == ["Valid", "Good"]

    def test_fallback_to_tokens_if_no_sentences(self) -> None:
        """
        If result has no sentences attribute, fall back to tokens.

        This maintains backward compatibility with older parakeet-mlx versions
        or alternative result formats.
        """
        # Result with only tokens (no sentences)
        tokens = [
            MockAlignedToken(text="Fallback", start=0.0, end=0.5, confidence=0.99),
            MockAlignedToken(text="mode", start=0.6, end=1.0, confidence=0.99),
        ]

        # Create result WITHOUT sentences attribute
        result = type(
            "MockResult",
            (),
            {
                "text": "Fallback mode",
                "tokens": tokens,
            },
        )()

        words = _extract_words_from_result(result)

        # Should still extract something via fallback
        assert len(words) >= 1
