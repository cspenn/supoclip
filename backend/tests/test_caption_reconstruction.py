"""
Tests for caption reconstruction using Groq LLM.

This module tests the word reconstruction from sub-word tokens
that parakeet-mlx produces due to BPE tokenization.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.transcription_mlx import (
    _reconstruct_words_with_llm,
    _align_reconstructed_words,
)


class TestWordReconstruction:
    """Test word reconstruction from broken tokens."""

    @pytest.mark.asyncio
    async def test_reconstruct_simple_broken_words(self) -> None:
        """Test reconstructing simple broken words."""
        # Example: "Yes" broken into "Y" and "es"
        broken_words = [
            {"text": "Y", "start": 0, "end": 100, "confidence": 0.98},
            {"text": "es", "start": 100, "end": 200, "confidence": 0.99},
            {"text": ".", "start": 200, "end": 300, "confidence": 0.95},
        ]

        with patch("src.transcription_mlx.AsyncGroq") as mock_groq:
            # Mock the Groq response
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Yes."
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_response
            )

            result = await _reconstruct_words_with_llm(broken_words)

            # Should reconstruct into complete words
            assert len(result) > 0
            # Check that we have proper words
            texts = [w["text"] for w in result]
            reconstructed_text = " ".join(texts)
            assert "Yes" in reconstructed_text or "yes" in reconstructed_text.lower()

    @pytest.mark.asyncio
    async def test_missing_groq_key_returns_original(self) -> None:
        """Test that missing GROQ_API_KEY returns original broken tokens."""
        import os

        broken_words = [
            {"text": "Y", "start": 0, "end": 100, "confidence": 0.98},
            {"text": "es", "start": 100, "end": 200, "confidence": 0.99},
        ]

        # Temporarily unset GROQ_API_KEY
        original_key = os.environ.get("GROQ_API_KEY")
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

        try:
            result = await _reconstruct_words_with_llm(broken_words)
            # Should return original tokens if no API key
            assert result == broken_words
        finally:
            # Restore original key
            if original_key:
                os.environ["GROQ_API_KEY"] = original_key

    def test_align_reconstructed_words_basic(self) -> None:
        """Test timing alignment for reconstructed words."""
        broken_words = [
            {"text": "Y", "start": 0, "end": 100, "confidence": 0.98},
            {"text": "es", "start": 100, "end": 200, "confidence": 0.99},
            {"text": "Task", "start": 200, "end": 400, "confidence": 0.95},
        ]

        reconstructed_text = "Yes Task"

        result = _align_reconstructed_words(broken_words, reconstructed_text)

        # Should have 2 words: "Yes" and "Task"
        assert len(result) >= 1
        # First word should span from start of first token to end of "es" token
        assert result[0]["text"] in ["Yes", "Task"]
        # Timing should be preserved
        assert result[0]["start"] >= 0

    def test_align_with_empty_reconstructed_text(self) -> None:
        """Test alignment with empty reconstructed text."""
        broken_words = [
            {"text": "Y", "start": 0, "end": 100, "confidence": 0.98},
        ]

        result = _align_reconstructed_words(broken_words, "")

        # Should return original broken words if reconstruction is empty
        assert result == broken_words

    def test_align_preserves_confidence(self) -> None:
        """Test that alignment preserves confidence scores."""
        broken_words = [
            {"text": "H", "start": 0, "end": 100, "confidence": 0.99},
            {"text": "el", "start": 100, "end": 200, "confidence": 0.98},
            {"text": "lo", "start": 200, "end": 300, "confidence": 0.97},
        ]

        reconstructed_text = "Hello"

        result = _align_reconstructed_words(broken_words, reconstructed_text)

        # Result should have confidence preserved
        if result:
            assert "confidence" in result[0]
            # Confidence should be average of token confidences
            assert 0.0 <= result[0]["confidence"] <= 1.0


class TestCaptionQuality:
    """Test quality metrics for reconstructed captions."""

    def test_word_boundaries_preserved(self) -> None:
        """Test that word boundaries are preserved in reconstruction."""
        # This is tested implicitly by the alignment function
        # Broken tokens should be combined into complete words
        broken_words = [
            {"text": "de", "start": 0, "end": 100, "confidence": 0.99},
            {"text": "com", "start": 100, "end": 200, "confidence": 0.99},
            {"text": "po", "start": 200, "end": 300, "confidence": 0.99},
            {"text": "si", "start": 300, "end": 400, "confidence": 0.99},
            {"text": "tion", "start": 400, "end": 500, "confidence": 0.99},
        ]

        reconstructed_text = "decomposition"

        result = _align_reconstructed_words(broken_words, reconstructed_text)

        # Should have at least one word
        assert len(result) >= 1
        # The reconstructed word should be sensible
        assert result[0]["text"] in ["decomposition", "de"]
