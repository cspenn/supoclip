# start backend/tests/unit/test_ai_output_validation.py
"""
Test suite for AI output quality and validation.

Tests that verify:
1. Zero segments validation - error raised when all segments rejected
2. Ultra-short segment detection - segments < 5 seconds are rejected
3. Error messages - clear user-visible error messages
4. Groq response handling - detection of problematic responses
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_structured import (
    TranscriptSegment,
    TranscriptAnalysis,
    analyze_transcript_structured,
)


LONG_TRANSCRIPT = "This is a much longer transcript to satisfy the 50 character minimum requirement. " * 10
class TestZeroSegmentsValidation:
    """Test that zero validated segments raises an error (Fix 1)."""

    @pytest.mark.asyncio
    async def test_all_segments_rejected_raises_error(self):
        """Test: Error raised when all AI segments are rejected as too short."""
        # Mock Groq API to return ultra-short segments
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            # Mock the API completion response
            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:00.56", "text": "Quick word", '
                '"relevance_score": 0.9, "reasoning": "Important moment"},'
                '{"start_time": "02:00", "end_time": "02:01.36", "text": "Another fragment", '
                '"relevance_score": 0.85, "reasoning": "Relevant"}'
                '], "summary": "Test video", "key_topics": ["test"]}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            # Set required environment variable
            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                # Act & Assert: Should raise ValueError with user-friendly message
                long_transcript = "This is a much longer transcript to satisfy the 50 character minimum. " * 5
                with pytest.raises(ValueError) as exc_info:
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

                # Verify error message explains the issue
                error_msg = str(exc_info.value)
                assert "No valid segments found" in error_msg
                assert "too short" in error_msg.lower()
                assert "AI model" in error_msg or "fragments" in error_msg

    @pytest.mark.asyncio
    async def test_zero_segments_error_message_helpful(self):
        """Test: Error message provides actionable guidance."""
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:02", "text": "Too brief", '
                '"relevance_score": 0.95, "reasoning": "Very important"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                with pytest.raises(ValueError) as exc_info:
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

                error_msg = str(exc_info.value)
                # Should mention possible causes
                assert (
                    "Groq" in error_msg
                    or "fragments" in error_msg.lower()
                    or "too short" in error_msg.lower()
                )


class TestSegmentRejectionLogging:
    """Test diagnostic logging for rejected segments (Fix 2)."""

    @pytest.mark.asyncio
    async def test_insufficient_text_logged(self, caplog):
        """Test: Insufficient text segments logged with details."""
        # Create segment with insufficient text
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:15", "text": "Hi", '
                '"relevance_score": 0.8, "reasoning": "Test"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                # Call analyze with capture logging
                import logging

                logger = logging.getLogger("ai_structured")
                with patch.object(logger, "warning") as mock_warning:
                    try:
                        await analyze_transcript_structured(LONG_TRANSCRIPT)
                    except ValueError:
                        pass  # Expected

                    # Should log REJECTED with details
                    assert mock_warning.called
                    call_args = str(mock_warning.call_args)
                    assert "REJECTED" in call_args or "Insufficient" in call_args

    @pytest.mark.asyncio
    async def test_too_short_segment_logged(self):
        """Test: Too-short segments logged with duration info."""
        # Create segment that's too short
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:03", '
                '"text": "This is not enough time for a clip", '
                '"relevance_score": 0.9, "reasoning": "Important"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                # Act
                import logging

                logger = logging.getLogger("ai_structured")
                with patch.object(logger, "warning") as mock_warning:
                    try:
                        await analyze_transcript_structured(LONG_TRANSCRIPT)
                    except ValueError:
                        pass  # Expected

                    # Assert: Should mention duration
                    assert mock_warning.called
                    call_args = str(mock_warning.call_args)
                    assert "3" in call_args or "min 5" in call_args


class TestValidSegmentsAccepted:
    """Test that valid segments are accepted and logged."""

    @pytest.mark.asyncio
    async def test_valid_segment_accepted(self):
        """Test: Segment with valid duration (>= 5 seconds) is accepted."""
        # Create valid segment
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:15", '
                '"text": "This is a complete thought that makes sense on its own.", '
                '"relevance_score": 0.95, "reasoning": "Engaging content"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                # Act
                result = await analyze_transcript_structured(LONG_TRANSCRIPT)

                # Assert: Should return valid segment
                assert len(result.most_relevant_segments) == 1
                assert result.most_relevant_segments[0].start_time == "01:00"
                assert result.most_relevant_segments[0].end_time == "01:15"

    @pytest.mark.asyncio
    async def test_multiple_valid_segments_accepted(self):
        """Test: Multiple valid segments are accepted."""
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:15", '
                '"text": "First valid clip with complete thought", '
                '"relevance_score": 0.95, "reasoning": "Important"},'
                '{"start_time": "02:00", "end_time": "02:20", '
                '"text": "Second valid clip with another complete thought", '
                '"relevance_score": 0.85, "reasoning": "Also important"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                # Act
                result = await analyze_transcript_structured(LONG_TRANSCRIPT)

                # Assert: Both should be accepted
                assert len(result.most_relevant_segments) == 2


class TestGroqResponseValidation:
    """Test Groq response validation for duration issues (Fix 5)."""

    @pytest.mark.asyncio
    async def test_ultra_short_response_detected(self):
        """Test: Ultra-short segment response triggers warning."""
        # Create response with ultra-short segments
        with patch("ai_structured.AsyncGroq") as mock_groq:
            mock_client = AsyncMock()
            mock_groq.return_value = mock_client

            mock_completion = MagicMock()
            mock_completion.choices = [MagicMock()]
            mock_completion.choices[0].message.content = (
                '{"most_relevant_segments": ['
                '{"start_time": "01:00", "end_time": "01:00.56", "text": "Too short", '
                '"relevance_score": 0.8, "reasoning": "Test"}'
                '], "summary": "Test", "key_topics": []}'
            )

            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_completion
            )

            with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
                import logging

                logger = logging.getLogger("ai_structured")
                with patch.object(logger, "warning") as mock_warning:
                    try:
                        await analyze_transcript_structured(LONG_TRANSCRIPT)
                    except ValueError:
                        pass  # Expected

                    # Should warn about short segments
                    assert mock_warning.called


# end backend/tests/unit/test_ai_output_validation.py
