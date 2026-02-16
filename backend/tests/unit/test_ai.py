# start tests/unit/test_ai.py
"""
Comprehensive tests for src/ai.py to achieve 100% line coverage.

Covers:
- _get_llm_model() lazy initialization (lines 84-95)
- _get_transcript_agent() lazy initialization (lines 105-112)
- validate_clean_start() legacy wrapper (line 149)
- TranscriptSegmentValidator.validate_timestamps ValueError path (lines 279-280)
- TranscriptSegmentValidator.validate_segment timestamp failure (line 305)
- TranscriptSegmentValidator.validate_segment duration calc failure (lines 313-314)
- _analyze_with_structured_model() (lines 324-358)
- _analyze_with_standard_model() (lines 366-401)
- _validate_transcript() (lines 413-423)
- _build_analysis_prompt() (lines 442-457)
- _should_use_structured_model() (lines 466-467)
- get_most_relevant_parts_by_transcript() (lines 477-505)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai import (
    _get_llm_model,
    _get_transcript_agent,
    validate_clean_start,
    CleanStartValidator,
    TimestampParser,
    TimestampFormatValidator,
    TranscriptSegmentValidator,
    _analyze_with_structured_model,
    _analyze_with_standard_model,
    _validate_transcript,
    _build_analysis_prompt,
    _should_use_structured_model,
    get_most_relevant_parts_by_transcript,
)
from src.ai_types.ai_models import TranscriptSegment, TranscriptAnalysis

# Minimum-length transcript for tests requiring >= 50 chars
LONG_TRANSCRIPT = (
    "This is a much longer transcript to satisfy the 50 character minimum requirement. " * 3
)


def _make_mock_config(**overrides):
    """Create a mock Config object with sensible defaults and optional overrides."""
    mock_cfg = MagicMock()
    mock_cfg.local_llm_enabled = True
    mock_cfg.local_llm_base_url = "http://localhost:6969/v1"
    mock_cfg.llm = ""
    mock_cfg.groq_api_key = ""
    mock_cfg.get_llm_model = MagicMock(return_value=MagicMock(name="mock_model"))
    for key, value in overrides.items():
        setattr(mock_cfg, key, value)
    return mock_cfg


class TestGetLlmModel:
    """Tests for _get_llm_model() lazy initialization."""

    def test_get_llm_model_local_llm_enabled(self):
        """Test _get_llm_model with local LLM enabled (lines 84-89)."""
        import src.ai as ai_module

        ai_module._llm_model = None

        mock_model = MagicMock()
        mock_cfg = _make_mock_config(local_llm_enabled=True)
        mock_cfg.get_llm_model.return_value = mock_model

        with patch.object(ai_module, "config", mock_cfg):
            result = _get_llm_model()
            assert result is mock_model
            mock_cfg.get_llm_model.assert_called_once()

        ai_module._llm_model = None

    def test_get_llm_model_cloud_llm(self):
        """Test _get_llm_model with cloud LLM (local disabled) (lines 90-91)."""
        import src.ai as ai_module

        ai_module._llm_model = None

        mock_model = MagicMock()
        mock_cfg = _make_mock_config(local_llm_enabled=False, llm="groq:llama-model")
        mock_cfg.get_llm_model.return_value = mock_model

        with patch.object(ai_module, "config", mock_cfg):
            result = _get_llm_model()
            assert result is mock_model

        ai_module._llm_model = None

    def test_get_llm_model_cached(self):
        """Test _get_llm_model returns cached model on second call."""
        import src.ai as ai_module

        ai_module._llm_model = None

        mock_model = MagicMock()
        mock_cfg = _make_mock_config(local_llm_enabled=True)
        mock_cfg.get_llm_model.return_value = mock_model

        with patch.object(ai_module, "config", mock_cfg):
            result1 = _get_llm_model()
            result2 = _get_llm_model()
            assert result1 is result2
            assert mock_cfg.get_llm_model.call_count == 1

        ai_module._llm_model = None

    def test_get_llm_model_value_error(self):
        """Test _get_llm_model raises ValueError on configuration error (lines 92-94)."""
        import src.ai as ai_module

        ai_module._llm_model = None

        mock_cfg = _make_mock_config()
        mock_cfg.get_llm_model.side_effect = ValueError("No LLM configured")

        with patch.object(ai_module, "config", mock_cfg):
            with pytest.raises(ValueError, match="No LLM configured"):
                _get_llm_model()

        ai_module._llm_model = None


class TestGetTranscriptAgent:
    """Tests for _get_transcript_agent() lazy initialization."""

    def test_get_transcript_agent_creates_agent(self):
        """Test _get_transcript_agent creates an Agent on first call (lines 105-112)."""
        import src.ai as ai_module

        ai_module._transcript_agent = None
        ai_module._llm_model = None

        mock_model = MagicMock()
        mock_agent = MagicMock()
        mock_cfg = _make_mock_config(local_llm_enabled=True)
        mock_cfg.get_llm_model.return_value = mock_model

        with patch.object(ai_module, "config", mock_cfg):
            with patch("src.ai.Agent", return_value=mock_agent) as mock_agent_cls:
                result = _get_transcript_agent()
                assert result is mock_agent
                mock_agent_cls.assert_called_once()

        ai_module._transcript_agent = None
        ai_module._llm_model = None

    def test_get_transcript_agent_cached(self):
        """Test _get_transcript_agent returns cached agent."""
        import src.ai as ai_module

        mock_agent = MagicMock()
        ai_module._transcript_agent = mock_agent

        result = _get_transcript_agent()
        assert result is mock_agent

        ai_module._transcript_agent = None


class TestValidateCleanStart:
    """Tests for validate_clean_start() legacy wrapper (line 149)."""

    def test_validate_clean_start_valid(self):
        """Test legacy wrapper with valid text."""
        is_valid, reason = validate_clean_start("The main thing you need to know")
        assert is_valid is True
        assert reason == "Clean start"

    def test_validate_clean_start_invalid(self):
        """Test legacy wrapper with forbidden start."""
        is_valid, reason = validate_clean_start("And the next thing")
        assert is_valid is False
        assert "forbidden" in reason.lower()


class TestTranscriptSegmentValidatorEdgeCases:
    """Tests for edge cases in TranscriptSegmentValidator."""

    def test_validate_timestamps_value_error(self):
        """Test validate_timestamps with unparseable timestamp (lines 279-280)."""
        segment = TranscriptSegment(
            start_time="invalid:ts",
            end_time="00:10.000",
            text="Valid text here",
            relevance_score=0.8,
            reasoning="Test",
        )
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        assert not is_valid
        assert "Invalid timestamp format" in reason

    def test_validate_timestamps_value_error_end_time(self):
        """Test validate_timestamps when end_time is unparseable."""
        segment = TranscriptSegment(
            start_time="00:05.000",
            end_time="bad:time",
            text="Valid text here",
            relevance_score=0.8,
            reasoning="Test",
        )
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        assert not is_valid
        assert "Invalid timestamp format" in reason

    def test_validate_segment_timestamp_failure_returns_zero_duration(self):
        """Test validate_segment when timestamp duration is too short (line 305)."""
        segment = TranscriptSegment(
            start_time="00:10.000",
            end_time="00:12.000",
            text="This segment is too short to be valid",
            relevance_score=0.8,
            reasoning="Too short",
        )
        is_valid, reason, duration = TranscriptSegmentValidator.validate_segment(segment)
        assert not is_valid
        assert "Timestamp validation" in reason
        assert duration == 0.0

    def test_validate_segment_duration_calc_failure(self):
        """Test validate_segment when final duration calc fails (lines 313-314)."""
        segment = TranscriptSegment(
            start_time="02:00.000",
            end_time="02:15.000",
            text="This is a valid segment with good content",
            relevance_score=0.9,
            reasoning="Good segment",
        )

        # We need calculate_duration to succeed on the first call (in validate_timestamps)
        # and raise ValueError on the second call (in validate_segment's final calc).
        call_count = 0
        original_calc = TimestampParser.calculate_duration

        def calc_side_effect(start, end):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return original_calc(start, end)
            raise ValueError("Simulated failure")

        with patch.object(TimestampParser, "calculate_duration", calc_side_effect):
            is_valid, reason, duration = TranscriptSegmentValidator.validate_segment(
                segment
            )
            assert not is_valid
            assert "Duration calculation failed" in reason
            assert duration == 0.0


class TestAnalyzeWithStructuredModel:
    """Tests for _analyze_with_structured_model()."""

    @pytest.mark.asyncio
    async def test_analyze_with_structured_model_success(self):
        """Test successful structured model analysis (lines 324-349)."""
        mock_structured_result = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:15.000",
                    text="This is a great segment with compelling content",
                    relevance_score=0.9,
                    reasoning="Strong hook",
                )
            ],
            summary="Test summary",
            key_topics=["topic1", "topic2"],
        )

        with patch(
            "src.ai_structured.analyze_transcript_structured",
            new_callable=AsyncMock,
            return_value=mock_structured_result,
        ):
            result = await _analyze_with_structured_model(
                LONG_TRANSCRIPT, 10, 45, None
            )
            assert len(result.most_relevant_segments) == 1
            assert result.summary == "Test summary"
            assert result.key_topics == ["topic1", "topic2"]
            assert result.most_relevant_segments[0].start_time == "01:00.000"

    @pytest.mark.asyncio
    async def test_analyze_with_structured_model_with_custom_prompt(self):
        """Test structured model with custom prompt."""
        mock_result = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="02:00.000",
                    end_time="02:20.000",
                    text="Custom prompt targeted content here",
                    relevance_score=0.85,
                    reasoning="Matches custom criteria",
                )
            ],
            summary="Custom analysis",
            key_topics=["custom"],
        )

        with patch(
            "src.ai_structured.analyze_transcript_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_analyze:
            result = await _analyze_with_structured_model(
                LONG_TRANSCRIPT, 10, 45, "Focus on tips"
            )
            mock_analyze.assert_called_once_with(
                LONG_TRANSCRIPT,
                min_length=10,
                max_length=45,
                custom_prompt="Focus on tips",
            )
            assert len(result.most_relevant_segments) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_structured_model_value_error(self):
        """Test structured model wraps ValueError (lines 350-355)."""
        with patch(
            "src.ai_structured.analyze_transcript_structured",
            new_callable=AsyncMock,
            side_effect=ValueError("No valid segments found"),
        ):
            with pytest.raises(ValueError, match="AI analysis failed"):
                await _analyze_with_structured_model(LONG_TRANSCRIPT, 10, 45, None)

    @pytest.mark.asyncio
    async def test_analyze_with_structured_model_generic_error(self):
        """Test structured model re-raises generic exceptions (lines 356-358)."""
        with patch(
            "src.ai_structured.analyze_transcript_structured",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API down"),
        ):
            with pytest.raises(RuntimeError, match="API down"):
                await _analyze_with_structured_model(LONG_TRANSCRIPT, 10, 45, None)


class TestAnalyzeWithStandardModel:
    """Tests for _analyze_with_standard_model()."""

    @pytest.mark.asyncio
    async def test_analyze_with_standard_model_success(self):
        """Test successful standard model analysis (lines 366-401)."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:15.000",
                    text="This is great content for a short clip",
                    relevance_score=0.95,
                    reasoning="Strong hook with compelling narrative",
                ),
                TranscriptSegment(
                    start_time="03:00.000",
                    end_time="03:20.000",
                    text="Another valuable segment with tips and insights",
                    relevance_score=0.85,
                    reasoning="Valuable actionable content",
                ),
            ],
            summary="Test video about content creation",
            key_topics=["content", "creation"],
        )

        mock_result = MagicMock()
        mock_result.data = mock_analysis

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        ai_module._transcript_agent = mock_agent

        try:
            result = await _analyze_with_standard_model("Test prompt text")
            assert len(result.most_relevant_segments) == 2
            assert result.most_relevant_segments[0].relevance_score == 0.95
            assert result.summary == "Test video about content creation"
        finally:
            ai_module._transcript_agent = None

    @pytest.mark.asyncio
    async def test_analyze_with_standard_model_filters_invalid(self):
        """Test standard model filters out invalid segments."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:15.000",
                    text="Valid segment with enough content here",
                    relevance_score=0.9,
                    reasoning="Good",
                ),
                TranscriptSegment(
                    start_time="02:00.000",
                    end_time="02:00.000",
                    text="Invalid segment same start and end time",
                    relevance_score=0.8,
                    reasoning="Bad timestamps",
                ),
                TranscriptSegment(
                    start_time="03:00.000",
                    end_time="03:30.000",
                    text="And this starts with a forbidden word which is bad",
                    relevance_score=0.7,
                    reasoning="Forbidden start",
                ),
            ],
            summary="Mixed validity test",
            key_topics=["test"],
        )

        mock_result = MagicMock()
        mock_result.data = mock_analysis

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        ai_module._transcript_agent = mock_agent

        try:
            result = await _analyze_with_standard_model("Test prompt")
            assert len(result.most_relevant_segments) == 1
            assert result.most_relevant_segments[0].start_time == "01:00.000"
        finally:
            ai_module._transcript_agent = None

    @pytest.mark.asyncio
    async def test_analyze_with_standard_model_empty_result(self):
        """Test standard model when all segments filtered returns empty."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:00.000",
                    text="Invalid timestamp same start and end time",
                    relevance_score=0.9,
                    reasoning="Bad",
                ),
            ],
            summary="All invalid",
            key_topics=["test"],
        )

        mock_result = MagicMock()
        mock_result.data = mock_analysis

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        ai_module._transcript_agent = mock_agent

        try:
            result = await _analyze_with_standard_model("Test prompt")
            assert len(result.most_relevant_segments) == 0
            assert result.summary == "All invalid"
        finally:
            ai_module._transcript_agent = None


class TestValidateTranscript:
    """Tests for _validate_transcript() (lines 413-423)."""

    def test_validate_transcript_empty(self):
        """Test empty transcript raises ValueError (lines 413-415)."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            _validate_transcript("")

    def test_validate_transcript_whitespace(self):
        """Test whitespace-only transcript raises ValueError."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            _validate_transcript("   ")

    def test_validate_transcript_too_short(self):
        """Test short transcript raises ValueError (lines 419-423)."""
        short = "Too short text"
        with pytest.raises(ValueError, match="Transcript too short"):
            _validate_transcript(short)

    def test_validate_transcript_exactly_50_chars(self):
        """Test transcript with exactly 50 chars passes."""
        text = "A" * 50
        _validate_transcript(text)

    def test_validate_transcript_valid(self):
        """Test valid transcript passes."""
        _validate_transcript(LONG_TRANSCRIPT)


class TestBuildAnalysisPrompt:
    """Tests for _build_analysis_prompt() (lines 442-457)."""

    def test_build_analysis_prompt_basic(self):
        """Test basic prompt building without custom prompt."""
        result = _build_analysis_prompt("Test transcript", 10, 45, None)
        assert "Test transcript" in result
        assert "10-45 seconds" in result
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_build_analysis_prompt_with_custom(self):
        """Test prompt building with custom prompt."""
        result = _build_analysis_prompt("Test transcript", 15, 60, "Focus on humor")
        assert "Test transcript" in result
        assert "15-60 seconds" in result
        assert "ADDITIONAL INSTRUCTIONS" in result
        assert "Focus on humor" in result

    def test_build_analysis_prompt_structure(self):
        """Test prompt has expected structure."""
        result = _build_analysis_prompt("My transcript", 10, 45, None)
        assert result.startswith("Analyze this video transcript")
        assert "Transcript:\nMy transcript" in result


class TestShouldUseStructuredModel:
    """Tests for _should_use_structured_model() (lines 466-467)."""

    def test_llama4_scout(self):
        """Test returns True for llama-4-scout model."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(
            local_llm_enabled=False,
            llm="groq:meta-llama/llama-4-scout-17b-16e-instruct",
        )
        with patch.object(ai_module, "config", mock_cfg):
            assert _should_use_structured_model() is True

    def test_llama4_maverick(self):
        """Test returns True for llama-4-maverick model."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(
            local_llm_enabled=False,
            llm="groq:meta-llama/llama-4-maverick-17b",
        )
        with patch.object(ai_module, "config", mock_cfg):
            assert _should_use_structured_model() is True

    def test_other_model(self):
        """Test returns False for non-Llama4 model."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(local_llm_enabled=False, llm="openai:gpt-4")
        with patch.object(ai_module, "config", mock_cfg):
            assert _should_use_structured_model() is False

    def test_local_llm_enabled(self):
        """Test returns False when local LLM is enabled (uses empty string)."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(local_llm_enabled=True)
        with patch.object(ai_module, "config", mock_cfg):
            assert _should_use_structured_model() is False


class TestGetMostRelevantPartsByTranscript:
    """Tests for get_most_relevant_parts_by_transcript() (lines 470-505)."""

    @pytest.mark.asyncio
    async def test_structured_model_path(self):
        """Test main function routes to structured model (lines 487-490)."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:15.000",
                    text="Great content segment for testing",
                    relevance_score=0.9,
                    reasoning="Test",
                )
            ],
            summary="Test summary",
            key_topics=["test"],
        )

        mock_cfg = _make_mock_config(
            local_llm_enabled=False,
            llm="groq:meta-llama/llama-4-scout-17b-16e-instruct",
        )

        with patch.object(ai_module, "config", mock_cfg):
            with patch(
                "src.ai._analyze_with_structured_model",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ) as mock_structured:
                result = await get_most_relevant_parts_by_transcript(
                    LONG_TRANSCRIPT, 10, 45
                )
                mock_structured.assert_called_once()
                assert result is mock_analysis

    @pytest.mark.asyncio
    async def test_standard_model_path(self):
        """Test main function routes to standard model (lines 493-496)."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[
                TranscriptSegment(
                    start_time="01:00.000",
                    end_time="01:15.000",
                    text="Standard model content segment",
                    relevance_score=0.9,
                    reasoning="Test",
                )
            ],
            summary="Standard summary",
            key_topics=["standard"],
        )

        mock_cfg = _make_mock_config(local_llm_enabled=True)

        with patch.object(ai_module, "config", mock_cfg):
            with patch(
                "src.ai._analyze_with_standard_model",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ) as mock_standard:
                result = await get_most_relevant_parts_by_transcript(
                    LONG_TRANSCRIPT, 10, 45
                )
                mock_standard.assert_called_once()
                assert result is mock_analysis

    @pytest.mark.asyncio
    async def test_with_custom_prompt(self):
        """Test main function passes custom prompt and logs it (line 480)."""
        import src.ai as ai_module

        mock_analysis = TranscriptAnalysis(
            most_relevant_segments=[],
            summary="Empty",
            key_topics=[],
        )

        mock_cfg = _make_mock_config(local_llm_enabled=True)

        with patch.object(ai_module, "config", mock_cfg):
            with patch(
                "src.ai._analyze_with_standard_model",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ):
                result = await get_most_relevant_parts_by_transcript(
                    LONG_TRANSCRIPT,
                    10,
                    45,
                    custom_prompt="Focus on humor and comedy",
                )
                assert result is mock_analysis

    @pytest.mark.asyncio
    async def test_empty_transcript_error(self):
        """Test main function raises ValueError for empty transcript."""
        with pytest.raises(ValueError, match="Cannot analyze empty transcript"):
            await get_most_relevant_parts_by_transcript("")

    @pytest.mark.asyncio
    async def test_short_transcript_error(self):
        """Test main function raises ValueError for short transcript."""
        with pytest.raises(ValueError, match="Transcript too short"):
            await get_most_relevant_parts_by_transcript("Short")

    @pytest.mark.asyncio
    async def test_value_error_reraise(self):
        """Test main function re-raises ValueError from analysis (lines 499-501)."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(local_llm_enabled=True)

        with patch.object(ai_module, "config", mock_cfg):
            with patch(
                "src.ai._analyze_with_standard_model",
                new_callable=AsyncMock,
                side_effect=ValueError("AI analysis failed"),
            ):
                with pytest.raises(ValueError, match="AI analysis failed"):
                    await get_most_relevant_parts_by_transcript(LONG_TRANSCRIPT)

    @pytest.mark.asyncio
    async def test_generic_error_reraise(self):
        """Test main function re-raises generic exceptions (lines 502-505)."""
        import src.ai as ai_module

        mock_cfg = _make_mock_config(local_llm_enabled=True)

        with patch.object(ai_module, "config", mock_cfg):
            with patch(
                "src.ai._analyze_with_standard_model",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Connection failed"),
            ):
                with pytest.raises(RuntimeError, match="Connection failed"):
                    await get_most_relevant_parts_by_transcript(LONG_TRANSCRIPT)


# end tests/unit/test_ai.py
