# start tests/unit/test_ai_structured.py
"""
Comprehensive tests for src/ai_structured.py to achieve 100% line coverage.

Covers:
- build_user_prompt() with custom_prompt (line 117)
- _validate_transcript_input() empty and short (lines 172-173, 178-179)
- _validate_and_adjust_segments() identical timestamps (lines 256-260)
- _validate_and_adjust_segments() negative duration (lines 266-270)
- _validate_and_adjust_segments() too long segments / trimming (lines 282-304)
- _validate_and_adjust_segments() ValueError/IndexError (lines 312-316)
- analyze_transcript_structured() missing API key (line 354)
- analyze_transcript_structured() empty response (line 392)
- analyze_transcript_structured() JSONDecodeError (lines 417-419)
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_structured import (
    build_system_prompt,
    build_user_prompt,
    _get_duration,
    _analyze_response_durations,
    _validate_transcript_input,
    _build_final_analysis,
    _validate_and_adjust_segments,
    analyze_transcript_structured,
)
from src.ai_types.ai_models import TranscriptSegment, TranscriptAnalysis

# Minimum-length transcript for tests requiring >= 50 chars
LONG_TRANSCRIPT = (
    "This is a much longer transcript to satisfy the 50 character minimum requirement. " * 3
)


class TestBuildUserPrompt:
    """Tests for build_user_prompt()."""

    def test_build_user_prompt_basic(self):
        """Test basic user prompt without custom prompt."""
        result = build_user_prompt("Test transcript", 10, 45)
        assert "Test transcript" in result
        assert "10-45 seconds" in result
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_build_user_prompt_with_custom(self):
        """Test user prompt includes custom prompt (line 117)."""
        result = build_user_prompt("Test transcript", 15, 60, "Focus on humor")
        assert "Test transcript" in result
        assert "15-60 seconds" in result
        assert "ADDITIONAL INSTRUCTIONS" in result
        assert "Focus on humor" in result

    def test_build_user_prompt_structure(self):
        """Test user prompt has expected parts."""
        result = build_user_prompt("My transcript", 10, 45)
        assert "Analyze this video transcript" in result
        assert "compelling" in result.lower()
        assert "Transcript:\nMy transcript" in result


class TestBuildSystemPrompt:
    """Tests for build_system_prompt()."""

    def test_build_system_prompt_default_params(self):
        """Test system prompt with default duration values."""
        result = build_system_prompt()
        assert "10" in result
        assert "45" in result

    def test_build_system_prompt_custom_params(self):
        """Test system prompt with custom duration values."""
        result = build_system_prompt(min_length=15, max_length=60)
        assert "15" in result
        assert "60" in result


class TestGetDuration:
    """Tests for _get_duration() helper."""

    def test_get_duration_basic(self):
        """Test basic duration calculation."""
        segment = TranscriptSegment(
            start_time="01:00",
            end_time="01:15",
            text="Test",
            relevance_score=0.8,
            reasoning="Test",
        )
        assert _get_duration(segment) == 15.0

    def test_get_duration_with_milliseconds(self):
        """Test duration with millisecond precision."""
        segment = TranscriptSegment(
            start_time="01:00.500",
            end_time="01:15.750",
            text="Test",
            relevance_score=0.8,
            reasoning="Test",
        )
        assert abs(_get_duration(segment) - 15.25) < 0.001

    def test_get_duration_negative(self):
        """Test negative duration when end < start."""
        segment = TranscriptSegment(
            start_time="02:00",
            end_time="01:00",
            text="Test",
            relevance_score=0.8,
            reasoning="Test",
        )
        assert _get_duration(segment) < 0


class TestAnalyzeResponseDurations:
    """Tests for _analyze_response_durations()."""

    def test_analyze_durations_valid_segments(self):
        """Test analyzing durations of valid segments."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="Segment 1",
                relevance_score=0.9,
                reasoning="Test",
            ),
            TranscriptSegment(
                start_time="02:00",
                end_time="02:20",
                text="Segment 2",
                relevance_score=0.8,
                reasoning="Test",
            ),
        ]
        durations = _analyze_response_durations(segments)
        assert len(durations) == 2
        assert durations[0] == 15.0
        assert durations[1] == 20.0

    def test_analyze_durations_ultra_short_warning(self):
        """Test warning logged for ultra-short segments."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:01",
                text="Ultra short",
                relevance_score=0.8,
                reasoning="Test",
            ),
            TranscriptSegment(
                start_time="02:00",
                end_time="02:02",
                text="Also short",
                relevance_score=0.7,
                reasoning="Test",
            ),
        ]
        durations = _analyze_response_durations(segments)
        assert len(durations) == 2
        # Average is 1.5s which is < 5.0 threshold
        assert sum(durations) / len(durations) < 5.0

    def test_analyze_durations_empty_list(self):
        """Test with empty segment list."""
        durations = _analyze_response_durations([])
        assert durations == []

    def test_analyze_durations_invalid_segments_suppressed(self):
        """Test invalid segments are silently suppressed."""
        segments = [
            TranscriptSegment(
                start_time="invalid",
                end_time="also_invalid",
                text="Bad timestamps",
                relevance_score=0.8,
                reasoning="Test",
            ),
        ]
        durations = _analyze_response_durations(segments)
        assert len(durations) == 0

    def test_analyze_durations_zero_duration_excluded(self):
        """Test zero duration segments are excluded."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:00",
                text="Zero duration",
                relevance_score=0.8,
                reasoning="Test",
            ),
        ]
        durations = _analyze_response_durations(segments)
        assert len(durations) == 0


class TestValidateTranscriptInput:
    """Tests for _validate_transcript_input()."""

    def test_validate_empty_transcript(self):
        """Test empty string raises ValueError (lines 172-173)."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            _validate_transcript_input("")

    def test_validate_whitespace_transcript(self):
        """Test whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            _validate_transcript_input("   ")

    def test_validate_none_like_empty(self):
        """Test empty string (falsy) raises ValueError."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            _validate_transcript_input("")

    def test_validate_short_transcript(self):
        """Test short transcript raises ValueError (lines 178-179)."""
        short_text = "Short text"
        with pytest.raises(ValueError, match="Transcript too short"):
            _validate_transcript_input(short_text)

    def test_validate_49_chars(self):
        """Test 49 chars (after strip) raises ValueError."""
        # 49 printable chars + whitespace padding
        text = "A" * 49
        with pytest.raises(ValueError, match="Transcript too short"):
            _validate_transcript_input(text)

    def test_validate_50_chars_passes(self):
        """Test exactly 50 chars passes."""
        text = "A" * 50
        _validate_transcript_input(text)  # Should not raise

    def test_validate_long_transcript_passes(self):
        """Test long transcript passes."""
        _validate_transcript_input(LONG_TRANSCRIPT)


class TestBuildFinalAnalysis:
    """Tests for _build_final_analysis()."""

    def test_build_final_analysis_success(self):
        """Test building final analysis with valid segments."""
        analysis = TranscriptAnalysis(
            most_relevant_segments=[],
            summary="Original summary",
            key_topics=["topic1"],
        )
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="Good segment",
                relevance_score=0.9,
                reasoning="Test",
            ),
            TranscriptSegment(
                start_time="02:00",
                end_time="02:20",
                text="Another good segment",
                relevance_score=0.7,
                reasoning="Test",
            ),
        ]
        result = _build_final_analysis(analysis, segments, [15.0, 20.0], 10, 45)
        assert len(result.most_relevant_segments) == 2
        # Should be sorted by relevance (highest first)
        assert result.most_relevant_segments[0].relevance_score == 0.9
        assert result.summary == "Original summary"

    def test_build_final_analysis_no_segments_raises(self):
        """Test raises ValueError when no validated segments (with durations)."""
        analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00",
                    end_time="01:01",
                    text="Rejected",
                    relevance_score=0.8,
                    reasoning="Test",
                ),
            ],
            summary="Test",
            key_topics=[],
        )
        with pytest.raises(ValueError, match="No valid segments found"):
            _build_final_analysis(analysis, [], [1.0], 10, 45)

    def test_build_final_analysis_no_segments_no_durations(self):
        """Test raises ValueError with N/A duration when no durations available."""
        analysis = TranscriptAnalysis(
            most_relevant_segments=[],
            summary="Empty",
            key_topics=[],
        )
        with pytest.raises(ValueError, match="N/A"):
            _build_final_analysis(analysis, [], [], 10, 45)


class TestValidateAndAdjustSegments:
    """Tests for _validate_and_adjust_segments()."""

    def test_valid_segment_accepted(self):
        """Test valid segment passes validation."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="This is a complete thought with enough content",
                relevance_score=0.9,
                reasoning="Good content",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 1

    def test_insufficient_text_rejected(self):
        """Test segment with insufficient text is rejected."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="Hi",
                relevance_score=0.9,
                reasoning="Too few words",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_empty_text_rejected(self):
        """Test segment with empty text is rejected."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="   ",
                relevance_score=0.9,
                reasoning="Whitespace only",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_identical_timestamps_rejected(self):
        """Test segment with identical start/end times is rejected (lines 256-260)."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:00",
                text="Segment with identical timestamps should be rejected",
                relevance_score=0.9,
                reasoning="Same times",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_negative_duration_rejected(self):
        """Test segment with negative duration is rejected (lines 266-270)."""
        segments = [
            TranscriptSegment(
                start_time="02:00",
                end_time="01:00",
                text="Segment with end time before start time is invalid",
                relevance_score=0.9,
                reasoning="Negative duration",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_underlength_segment_rejected(self):
        """Test segment shorter than min_length is rejected."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:05",
                text="This segment is only five seconds which is too short",
                relevance_score=0.9,
                reasoning="Under minimum",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_too_long_segment_trimmed(self):
        """Test segment longer than max_length is trimmed (lines 282-304)."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="02:30",
                text="This is a very long segment that exceeds the maximum length requirement",
                relevance_score=0.9,
                reasoning="Good but too long",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 1
        # The end_time should have been trimmed
        assert result[0].start_time == "01:00"
        # End should be 01:00 + 45s = 01:45
        assert "01:45" in result[0].end_time
        # Reasoning should note auto-trim
        assert "Auto-trimmed" in result[0].reasoning

    def test_value_error_in_timestamp_parsing(self):
        """Test segment with unparseable timestamps is skipped (lines 312-316)."""
        segments = [
            TranscriptSegment(
                start_time="invalid:ts",
                end_time="00:15.000",
                text="Segment with invalid timestamp format that cannot be parsed",
                relevance_score=0.8,
                reasoning="Bad format",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_index_error_in_timestamp_parsing(self):
        """Test segment with malformed timestamp triggers IndexError path (lines 312-316)."""
        segments = [
            TranscriptSegment(
                start_time="",
                end_time="00:15.000",
                text="Segment with empty start timestamp that may cause IndexError",
                relevance_score=0.8,
                reasoning="Empty start",
            )
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 0

    def test_mixed_segments_validation(self):
        """Test mix of valid and invalid segments."""
        segments = [
            TranscriptSegment(
                start_time="01:00",
                end_time="01:15",
                text="This is a valid segment with enough content here",
                relevance_score=0.95,
                reasoning="Good",
            ),
            TranscriptSegment(
                start_time="02:00",
                end_time="02:00",
                text="Identical timestamps means this segment is invalid",
                relevance_score=0.9,
                reasoning="Bad timestamps",
            ),
            TranscriptSegment(
                start_time="03:00",
                end_time="03:20",
                text="Another valid segment with different content",
                relevance_score=0.85,
                reasoning="Also good",
            ),
        ]
        result = _validate_and_adjust_segments(segments, 10, 45)
        assert len(result) == 2


class TestAnalyzeTranscriptStructured:
    """Tests for analyze_transcript_structured() main function."""

    @pytest.mark.asyncio
    async def test_missing_groq_api_key(self):
        """Test raises ValueError when GROQ_API_KEY not configured (line 354)."""
        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = ""
            mock_config_cls.return_value = mock_config

            with pytest.raises(ValueError, match="GROQ_API_KEY not configured"):
                await analyze_transcript_structured(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_empty_response_from_groq(self):
        """Test raises ValueError when Groq returns empty response (line 392)."""
        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = ""

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                with pytest.raises(ValueError, match="Empty response from Groq API"):
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_none_response_from_groq(self):
        """Test raises ValueError when Groq returns None content."""
        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = None

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                with pytest.raises(ValueError, match="Empty response from Groq API"):
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_json_decode_error(self):
        """Test handles JSONDecodeError from malformed response (lines 417-419)."""
        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "not valid json {{{{"

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                with pytest.raises(Exception, match="Invalid JSON response from Groq"):
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_generic_exception_reraise(self):
        """Test generic exceptions are re-raised (lines 420-422)."""
        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_client.chat.completions.create = AsyncMock(
                    side_effect=RuntimeError("API connection failed")
                )

                with pytest.raises(RuntimeError, match="API connection failed"):
                    await analyze_transcript_structured(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        """Test full successful analysis pipeline."""
        response_data = {
            "most_relevant_segments": [
                {
                    "start_time": "01:00.000",
                    "end_time": "01:15.000",
                    "text": "This is a complete thought that makes sense alone",
                    "relevance_score": 0.95,
                    "reasoning": "Strong hook with compelling narrative",
                }
            ],
            "summary": "Test video summary",
            "key_topics": ["topic1", "topic2"],
        }

        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = json.dumps(response_data)

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                result = await analyze_transcript_structured(LONG_TRANSCRIPT)

                assert len(result.most_relevant_segments) == 1
                assert result.summary == "Test video summary"
                assert result.key_topics == ["topic1", "topic2"]

    @pytest.mark.asyncio
    async def test_successful_analysis_with_custom_prompt(self):
        """Test analysis passes custom prompt through."""
        response_data = {
            "most_relevant_segments": [
                {
                    "start_time": "01:00.000",
                    "end_time": "01:20.000",
                    "text": "A segment matching custom criteria with enough words",
                    "relevance_score": 0.9,
                    "reasoning": "Matches custom instructions",
                }
            ],
            "summary": "Custom analysis",
            "key_topics": ["custom"],
        }

        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = json.dumps(response_data)

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                result = await analyze_transcript_structured(
                    LONG_TRANSCRIPT,
                    custom_prompt="Focus on comedy moments",
                )

                assert len(result.most_relevant_segments) == 1

    @pytest.mark.asyncio
    async def test_empty_transcript_rejected(self):
        """Test empty transcript is rejected before API call."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            await analyze_transcript_structured("")

    @pytest.mark.asyncio
    async def test_short_transcript_rejected(self):
        """Test short transcript is rejected before API call."""
        with pytest.raises(ValueError, match="Transcript too short"):
            await analyze_transcript_structured("Short")

    @pytest.mark.asyncio
    async def test_all_segments_rejected_after_validation(self):
        """Test ValueError when all segments fail validation."""
        response_data = {
            "most_relevant_segments": [
                {
                    "start_time": "01:00",
                    "end_time": "01:01",
                    "text": "Too short a clip fragment",
                    "relevance_score": 0.9,
                    "reasoning": "Fragment",
                },
                {
                    "start_time": "02:00",
                    "end_time": "02:02",
                    "text": "Another too-short fragment here",
                    "relevance_score": 0.8,
                    "reasoning": "Also fragment",
                },
            ],
            "summary": "All invalid",
            "key_topics": [],
        }

        with patch("src.ai_structured.Config") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.groq_api_key = "test-key"
            mock_config_cls.return_value = mock_config

            with patch("src.ai_structured.AsyncGroq") as mock_groq:
                mock_client = AsyncMock()
                mock_groq.return_value = mock_client

                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = json.dumps(response_data)

                mock_client.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                with pytest.raises(ValueError, match="No valid segments found"):
                    await analyze_transcript_structured(LONG_TRANSCRIPT)


# end tests/unit/test_ai_structured.py
