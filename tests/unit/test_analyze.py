# start tests/unit/test_analyze.py
"""Unit tests for src/pipeline/analyze.py — unified LLM transcript analysis."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.analyze import (
    AnalysisError,
    TranscriptSegment,
    _should_use_structured_output,
    analyze_transcript,
    build_system_prompt,
    validate_segments,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LONG_TRANSCRIPT = (
    "This is a much longer transcript that easily exceeds the fifty character "
    "minimum requirement for transcript analysis testing. " * 3
)


def _make_segment(
    start: float = 0.0,
    end: float = 20.0,
    text: str = "This is a complete and interesting thought.",
    score: float = 0.8,
    title: str = "",
) -> TranscriptSegment:
    """Return a TranscriptSegment with sensible defaults."""
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        score=score,
        title=title,
    )


# ---------------------------------------------------------------------------
# validate_segments — filtering logic
# ---------------------------------------------------------------------------


class TestValidateSegments:
    """Tests for validate_segments()."""

    def test_valid_segment_passes(self):
        """A segment within bounds with clean start is accepted."""
        segs = [_make_segment(0.0, 20.0, "The main idea here is very clear.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 1

    def test_zero_duration_rejected(self):
        """Segment where start_time == end_time is rejected."""
        segs = [_make_segment(10.0, 10.0, "Zero duration segment text here.")]
        result = validate_segments(segs, 5.0, 45.0)
        assert len(result) == 0

    def test_negative_duration_rejected(self):
        """Segment where end_time < start_time is rejected."""
        segs = [_make_segment(30.0, 10.0, "End before start should be rejected now.")]
        result = validate_segments(segs, 5.0, 45.0)
        assert len(result) == 0

    def test_too_short_rejected(self):
        """Segment shorter than min_length_s is rejected."""
        segs = [_make_segment(0.0, 5.0, "This short segment is five seconds only.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_too_long_rejected(self):
        """Segment longer than max_length_s is rejected."""
        segs = [_make_segment(0.0, 90.0, "This segment runs for ninety whole seconds.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_exactly_at_min_accepted(self):
        """Segment exactly at min_length_s is accepted."""
        segs = [_make_segment(0.0, 15.0, "Exactly fifteen seconds of great content.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 1

    def test_exactly_at_max_accepted(self):
        """Segment exactly at max_length_s is accepted."""
        segs = [_make_segment(0.0, 45.0, "Exactly forty-five seconds of great content.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 1

    def test_filler_and_rejected(self):
        """Segment starting with 'And' is rejected."""
        segs = [_make_segment(0.0, 20.0, "And then the speaker explained everything.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_but_rejected(self):
        """Segment starting with 'But' is rejected."""
        segs = [_make_segment(0.0, 20.0, "But the real insight came from this moment.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_so_rejected(self):
        """Segment starting with 'So' is rejected."""
        segs = [_make_segment(0.0, 20.0, "So what you need to know about this topic.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_um_rejected(self):
        """Segment starting with 'Um' is rejected."""
        segs = [_make_segment(0.0, 20.0, "Um the key point that everyone misses here.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_uh_rejected(self):
        """Segment starting with 'Uh' is rejected."""
        segs = [_make_segment(0.0, 20.0, "Uh let me explain the core concept now.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_like_rejected(self):
        """Segment starting with 'Like' is rejected."""
        segs = [_make_segment(0.0, 20.0, "Like the whole premise is completely wrong.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_you_know_rejected(self):
        """Segment starting with 'You know' is rejected."""
        segs = [_make_segment(0.0, 20.0, "You know the best part about this whole thing.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_filler_case_insensitive(self):
        """Filler-word check is case-insensitive."""
        segs = [_make_segment(0.0, 20.0, "AND then the speaker said something profound.")]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 0

    def test_empty_input_returns_empty(self):
        """Empty input list returns empty output."""
        result = validate_segments([], 15.0, 45.0)
        assert result == []

    def test_mixed_segments_filtered_correctly(self):
        """Mix of valid and invalid segments — only valid ones survive."""
        segs = [
            _make_segment(0.0, 20.0, "The first key insight is genuinely surprising."),   # valid
            _make_segment(0.0, 5.0, "And this too short filler segment gets cut out."),    # short + filler
            _make_segment(60.0, 90.0, "So this whole section is fascinating to watch."),   # filler
            _make_segment(100.0, 125.0, "Here is another perfectly valid standalone clip."), # valid
        ]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    """Tests for build_system_prompt()."""

    def test_contains_min_length(self):
        """Prompt contains the minimum length value."""
        result = build_system_prompt(10.0, 45.0)
        assert "10" in result

    def test_contains_max_length(self):
        """Prompt contains the maximum length value."""
        result = build_system_prompt(10.0, 45.0)
        assert "45" in result

    def test_custom_prompt_appended(self):
        """Custom prompt text is appended after the default prompt."""
        result = build_system_prompt(10.0, 45.0, custom_prompt="Focus on comedy.")
        assert "Focus on comedy." in result
        assert "ADDITIONAL INSTRUCTIONS" in result

    def test_no_custom_prompt_no_additional_instructions(self):
        """Without custom prompt, no 'ADDITIONAL INSTRUCTIONS' section appears."""
        result = build_system_prompt(10.0, 45.0)
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_custom_values_appear_correctly(self):
        """Non-default min/max values appear in the prompt."""
        result = build_system_prompt(20.0, 60.0)
        assert "20" in result
        assert "60" in result


# ---------------------------------------------------------------------------
# _should_use_structured_output
# ---------------------------------------------------------------------------


class TestShouldUseStructuredOutput:
    """Tests for _should_use_structured_output()."""

    def test_groq_llama_returns_true(self):
        """groq: prefix + llama in name → structured output."""
        assert _should_use_structured_output("groq:meta-llama/llama-4-scout-17b") is True

    def test_groq_llama_maverick_returns_true(self):
        """Llama 4 Maverick via Groq → structured output."""
        assert _should_use_structured_output("groq:meta-llama/llama-4-maverick-17b") is True

    def test_groq_non_llama_returns_false(self):
        """Groq model without 'llama' in name → no structured output."""
        assert _should_use_structured_output("groq:mixtral-8x7b-32768") is False

    def test_openai_returns_false(self):
        """OpenAI models do not use structured output path."""
        assert _should_use_structured_output("openai:gpt-4o") is False

    def test_anthropic_returns_false(self):
        """Anthropic models do not use structured output path."""
        assert _should_use_structured_output("anthropic:claude-3-5-sonnet") is False

    def test_local_model_returns_false(self):
        """Local model string → no structured output."""
        assert _should_use_structured_output("local-model") is False

    def test_empty_string_returns_false(self):
        """Empty model string → no structured output."""
        assert _should_use_structured_output("") is False

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        assert _should_use_structured_output("GROQ:META-LLAMA/LLAMA-4-SCOUT") is True


# ---------------------------------------------------------------------------
# analyze_transcript — integration (LLM calls mocked)
# ---------------------------------------------------------------------------


class TestAnalyzeTranscript:
    """Tests for analyze_transcript() with mocked LLM backends."""

    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self):
        """Empty transcript raises AnalysisError before any LLM call."""
        with pytest.raises(AnalysisError, match="empty transcript"):
            await analyze_transcript("", words=[])

    @pytest.mark.asyncio
    async def test_whitespace_transcript_raises(self):
        """Whitespace-only transcript raises AnalysisError."""
        with pytest.raises(AnalysisError, match="empty transcript"):
            await analyze_transcript("   \n\t  ", words=[])

    @pytest.mark.asyncio
    async def test_short_transcript_raises(self):
        """Transcript under 50 chars raises AnalysisError."""
        with pytest.raises(AnalysisError, match="too short"):
            await analyze_transcript("Too short.", words=[])

    @pytest.mark.asyncio
    async def test_returns_validated_segments_pydantic_ai(self):
        """analyze_transcript returns validated segments via Pydantic AI path."""
        mock_segments = [
            TranscriptSegment(start_time=10.0, end_time=30.0, text="The key insight explained.", score=0.9),
            TranscriptSegment(start_time=60.0, end_time=85.0, text="Here is the big reveal moment.", score=0.7),
        ]

        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(
                    LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0
                )

        assert len(result) == 2
        # Sorted by score descending.
        assert result[0].score == 0.9

    @pytest.mark.asyncio
    async def test_returns_validated_segments_groq(self):
        """analyze_transcript returns validated segments via Groq structured path."""
        mock_segments = [
            TranscriptSegment(start_time=5.0, end_time=25.0, text="Valuable content here now.", score=0.85),
        ]

        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = False
            mock_cfg.llm = "groq:meta-llama/llama-4-scout-17b"
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_groq_structured",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(
                    LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0
                )

        assert len(result) == 1
        assert result[0].score == 0.85

    @pytest.mark.asyncio
    async def test_no_valid_segments_raises_analysis_error(self):
        """When all segments are filtered out, AnalysisError is raised."""
        # All segments are too short (5s < 15s min).
        mock_segments = [
            TranscriptSegment(start_time=0.0, end_time=5.0, text="Fragment.", score=0.9),
        ]

        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ), pytest.raises(AnalysisError, match="No valid segments found"):
                await analyze_transcript(
                    LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0
                )

    @pytest.mark.asyncio
    async def test_llm_exception_wrapped_in_analysis_error(self):
        """Unexpected LLM exceptions are wrapped as AnalysisError."""
        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                side_effect=RuntimeError("connection refused"),
            ), pytest.raises(AnalysisError, match="LLM call failed"):
                await analyze_transcript(LONG_TRANSCRIPT, words=[])

    @pytest.mark.asyncio
    async def test_analysis_error_passthrough(self):
        """AnalysisError from backend propagates unchanged."""
        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                side_effect=AnalysisError("GROQ_API_KEY not configured"),
            ), pytest.raises(AnalysisError, match="GROQ_API_KEY not configured"):
                await analyze_transcript(LONG_TRANSCRIPT, words=[])

    @pytest.mark.asyncio
    async def test_segments_sorted_by_score_descending(self):
        """Returned segments are sorted by score, highest first."""
        mock_segments = [
            TranscriptSegment(start_time=0.0, end_time=20.0, text="Lower score clip here.", score=0.5),
            TranscriptSegment(start_time=30.0, end_time=60.0, text="Higher score clip now.", score=0.95),
        ]

        with patch("src.pipeline.analyze.Config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(
                    LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0
                )

        assert result[0].score == 0.95
        assert result[1].score == 0.5


# end tests/unit/test_analyze.py
