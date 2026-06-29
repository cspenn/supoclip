# start tests/unit/test_analyze.py
"""Unit tests for src/pipeline/analyze.py — unified LLM transcript analysis."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import InsufficientSegmentsError
from src.pipeline.analyze import (
    AnalysisError,
    TranscriptSegment,
    _analyze_with_groq_structured,
    _analyze_with_pydantic_ai,
    _build_user_prompt,
    _parse_timestamp,
    _raw_segment_to_float_times,
    _raw_segments_to_transcript_segments,
    _RawAnalysis,
    _RawSegment,
    _should_use_structured_output,
    analyze_transcript,
    build_system_prompt,
    validate_segments,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LONG_TRANSCRIPT = (
    "This is a much longer transcript that easily exceeds the fifty character minimum requirement for transcript analysis testing. " * 3
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
            _make_segment(0.0, 20.0, "The first key insight is genuinely surprising."),  # valid
            _make_segment(0.0, 5.0, "And this too short filler segment gets cut out."),  # short + filler
            _make_segment(60.0, 90.0, "So this whole section is fascinating to watch."),  # filler
            _make_segment(100.0, 125.0, "Here is another perfectly valid standalone clip."),  # valid
        ]
        result = validate_segments(segs, 15.0, 45.0)
        assert len(result) == 2

    def test_no_bound_when_max_time_none(self):
        """Without a max_time_s bound, far-future timestamps still pass duration checks."""
        segs = [_make_segment(300.0, 320.0, "A clip that claims to start at five minutes.")]
        result = validate_segments(segs, 15.0, 45.0, max_time_s=None)
        assert len(result) == 1

    def test_start_beyond_bound_rejected(self):
        """Segment starting at/after the transcript bound is rejected (H-6)."""
        # Transcript is only ~150s long; a start at 300s is hallucinated.
        segs = [_make_segment(300.0, 320.0, "Hallucinated clip past the end of the video.")]
        result = validate_segments(segs, 15.0, 45.0, max_time_s=150.0)
        assert len(result) == 0

    def test_end_beyond_bound_rejected(self):
        """Segment ending well past the transcript bound is rejected (H-6)."""
        segs = [_make_segment(140.0, 200.0, "Starts in range but runs far past the end.")]
        result = validate_segments(segs, 15.0, 90.0, max_time_s=150.0)
        assert len(result) == 0

    def test_within_bound_accepted(self):
        """Segment fully within the transcript bound is accepted (H-6)."""
        segs = [_make_segment(100.0, 130.0, "A perfectly in-range standalone clip here.")]
        result = validate_segments(segs, 15.0, 45.0, max_time_s=150.0)
        assert len(result) == 1

    def test_end_at_bound_within_tolerance_accepted(self):
        """End-of-video clip ending just past the bound is kept via tolerance (H-6)."""
        # Bound 150.0; end 150.5 is within the 1.0s tolerance.
        segs = [_make_segment(130.0, 150.5, "The final clip ends right at the video's end.")]
        result = validate_segments(segs, 15.0, 45.0, max_time_s=150.0)
        assert len(result) == 1


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

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0)

        assert len(result) == 2
        # Sorted by score descending.
        assert result[0].score == 0.9

    @pytest.mark.asyncio
    async def test_returns_validated_segments_groq(self):
        """analyze_transcript returns validated segments via Groq structured path."""
        mock_segments = [
            TranscriptSegment(start_time=5.0, end_time=25.0, text="Valuable content here now.", score=0.85),
        ]

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = False
            mock_cfg.llm_model = "groq:meta-llama/llama-4-scout-17b"
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_groq_structured",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0)

        assert len(result) == 1
        assert result[0].score == 0.85

    @pytest.mark.asyncio
    async def test_no_valid_segments_raises_analysis_error(self):
        """When all segments are filtered out, AnalysisError is raised."""
        # All segments are too short (5s < 15s min).
        mock_segments = [
            TranscriptSegment(start_time=0.0, end_time=5.0, text="Fragment.", score=0.9),
        ]

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch(
                    "src.pipeline.analyze._analyze_with_pydantic_ai",
                    new_callable=AsyncMock,
                    return_value=mock_segments,
                ),
                pytest.raises(AnalysisError, match="No valid segments found"),
            ):
                await analyze_transcript(LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0)

    @pytest.mark.asyncio
    async def test_llm_exception_wrapped_in_analysis_error(self):
        """Unexpected LLM exceptions are wrapped as AnalysisError."""
        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch(
                    "src.pipeline.analyze._analyze_with_pydantic_ai",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("connection refused"),
                ),
                pytest.raises(AnalysisError, match="LLM call failed"),
            ):
                await analyze_transcript(LONG_TRANSCRIPT, words=[])

    @pytest.mark.asyncio
    async def test_analysis_error_passthrough(self):
        """AnalysisError from backend propagates unchanged."""
        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch(
                    "src.pipeline.analyze._analyze_with_pydantic_ai",
                    new_callable=AsyncMock,
                    side_effect=AnalysisError("GROQ_API_KEY not configured"),
                ),
                pytest.raises(AnalysisError, match="GROQ_API_KEY not configured"),
            ):
                await analyze_transcript(LONG_TRANSCRIPT, words=[])

    @pytest.mark.asyncio
    async def test_segments_sorted_by_score_descending(self):
        """Returned segments are sorted by score, highest first."""
        mock_segments = [
            TranscriptSegment(start_time=0.0, end_time=20.0, text="Lower score clip here.", score=0.5),
            TranscriptSegment(start_time=30.0, end_time=60.0, text="Higher score clip now.", score=0.95),
        ]

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0)

        assert result[0].score == 0.95
        assert result[1].score == 0.5

    @pytest.mark.asyncio
    async def test_no_valid_segments_raises_insufficient_segments_error(self):
        """When all segments are filtered out, the error is InsufficientSegmentsError (H-13)."""
        mock_segments = [
            TranscriptSegment(start_time=0.0, end_time=5.0, text="Fragment.", score=0.9),
        ]

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch(
                    "src.pipeline.analyze._analyze_with_pydantic_ai",
                    new_callable=AsyncMock,
                    return_value=mock_segments,
                ),
                pytest.raises(InsufficientSegmentsError),
            ):
                await analyze_transcript(LONG_TRANSCRIPT, words=[], min_length_s=15.0, max_length_s=45.0)

    @pytest.mark.asyncio
    async def test_custom_prompt_forwarded_to_user_prompt(self):
        """custom_prompt reaches the user-turn content sent to the backend (H-5)."""
        mock_segments = [
            TranscriptSegment(start_time=10.0, end_time=30.0, text="Engaging content here.", score=0.9),
        ]
        backend = AsyncMock(return_value=mock_segments)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch("src.pipeline.analyze._analyze_with_pydantic_ai", backend):
                await analyze_transcript(
                    LONG_TRANSCRIPT,
                    words=[],
                    min_length_s=15.0,
                    max_length_s=45.0,
                    custom_prompt="Prioritize dramatic confrontations.",
                )

        # _analyze_with_pydantic_ai(user_prompt, system_prompt)
        user_prompt = backend.call_args.args[0]
        assert "Prioritize dramatic confrontations." in user_prompt
        assert "ADDITIONAL INSTRUCTIONS" in user_prompt

    @pytest.mark.asyncio
    async def test_out_of_bounds_segment_rejected_via_word_timing(self):
        """A hallucinated far-future segment is dropped using the transcript bound (H-6)."""
        # Words establish the transcript ends at ~150s.
        words = [
            {"text": "start", "start_ms": 0, "end_ms": 1000},
            {"text": "end", "start_ms": 149000, "end_ms": 150000},
        ]
        mock_segments = [
            TranscriptSegment(start_time=300.0, end_time=320.0, text="Hallucinated future clip text.", score=0.95),
            TranscriptSegment(start_time=20.0, end_time=45.0, text="A genuinely in-range clip here.", score=0.8),
        ]

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.llm_model = ""
            mock_cfg_cls.return_value = mock_cfg

            with patch(
                "src.pipeline.analyze._analyze_with_pydantic_ai",
                new_callable=AsyncMock,
                return_value=mock_segments,
            ):
                result = await analyze_transcript(LONG_TRANSCRIPT, words=words, min_length_s=15.0, max_length_s=45.0)

        assert len(result) == 1
        assert result[0].start_time == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# _parse_timestamp — lines 107-113
# ---------------------------------------------------------------------------


class TestParseTimestamp:
    """Tests for _parse_timestamp() helper."""

    def test_mm_ss_format(self):
        """Parses MM:SS format correctly."""
        assert _parse_timestamp("02:35") == pytest.approx(155.0)

    def test_mm_ss_mmm_format(self):
        """Parses MM:SS.mmm format correctly."""
        assert _parse_timestamp("01:30.500") == pytest.approx(90.5)

    def test_zero_timestamp(self):
        """Parses 00:00 as 0.0."""
        assert _parse_timestamp("00:00") == pytest.approx(0.0)

    def test_leading_trailing_whitespace_stripped(self):
        """Whitespace around timestamp is handled."""
        assert _parse_timestamp("  01:00  ") == pytest.approx(60.0)

    def test_invalid_format_no_colon_raises(self):
        """Missing colon raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            _parse_timestamp("0135")

    def test_invalid_format_too_many_colons_raises(self):
        """Three-part timestamp raises ValueError (expected MM:SS)."""
        with pytest.raises(ValueError, match="Expected MM:SS format"):
            _parse_timestamp("01:02:03")

    def test_non_numeric_raises(self):
        """Non-numeric content raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            _parse_timestamp("ab:cd")


# ---------------------------------------------------------------------------
# _raw_segment_to_float_times — lines 128-130
# ---------------------------------------------------------------------------


class TestRawSegmentToFloatTimes:
    """Tests for _raw_segment_to_float_times()."""

    def test_valid_timestamps_returns_tuple(self):
        """Returns (start_seconds, end_seconds) for valid timestamps."""
        raw = _RawSegment(start_time="01:00", end_time="01:30", text="Hello world.")
        start, end = _raw_segment_to_float_times(raw)
        assert start == pytest.approx(60.0)
        assert end == pytest.approx(90.0)

    def test_millisecond_precision_preserved(self):
        """Millisecond precision is preserved through conversion."""
        raw = _RawSegment(start_time="00:10.250", end_time="00:40.750", text="Content.")
        start, end = _raw_segment_to_float_times(raw)
        assert start == pytest.approx(10.25)
        assert end == pytest.approx(40.75)

    def test_invalid_start_raises(self):
        """Invalid start timestamp raises ValueError."""
        raw = _RawSegment(start_time="bad", end_time="01:00", text="Content.")
        with pytest.raises(ValueError):
            _raw_segment_to_float_times(raw)

    def test_invalid_end_raises(self):
        """Invalid end timestamp raises ValueError."""
        raw = _RawSegment(start_time="00:10", end_time="bad", text="Content.")
        with pytest.raises(ValueError):
            _raw_segment_to_float_times(raw)


# ---------------------------------------------------------------------------
# _build_user_prompt — line 234
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    """Tests for _build_user_prompt()."""

    def test_contains_transcript_text(self):
        """Transcript text appears in output."""
        result = _build_user_prompt("My transcript content.", 15.0, 45.0)
        assert "My transcript content." in result

    def test_contains_min_max_lengths(self):
        """Min and max lengths appear in output."""
        result = _build_user_prompt("Transcript.", 10.0, 60.0)
        assert "10" in result
        assert "60" in result

    def test_no_custom_prompt_no_additional_instructions(self):
        """Without custom_prompt, no 'ADDITIONAL INSTRUCTIONS' appears."""
        result = _build_user_prompt("Some text.", 15.0, 45.0)
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_custom_prompt_appended(self):
        """Custom prompt text is included when provided (line 234)."""
        result = _build_user_prompt("Transcript.", 15.0, 45.0, custom_prompt="Focus on humor.")
        assert "Focus on humor." in result
        assert "ADDITIONAL INSTRUCTIONS" in result


# ---------------------------------------------------------------------------
# _raw_segments_to_transcript_segments — lines 456-475
# ---------------------------------------------------------------------------


class TestRawSegmentsToTranscriptSegments:
    """Tests for _raw_segments_to_transcript_segments()."""

    def test_valid_segments_converted(self):
        """All valid segments are converted to TranscriptSegment objects."""
        raws = [
            _RawSegment(start_time="00:10", end_time="00:40", text="Content one.", relevance_score=0.9, title="Title 1"),
            _RawSegment(start_time="01:00", end_time="01:30", text="Content two.", relevance_score=0.7, title="Title 2"),
        ]
        result = _raw_segments_to_transcript_segments(raws)
        assert len(result) == 2
        assert result[0].start_time == pytest.approx(10.0)
        assert result[0].end_time == pytest.approx(40.0)
        assert result[0].text == "Content one."
        assert result[0].score == pytest.approx(0.9)
        assert result[0].title == "Title 1"

    def test_invalid_timestamp_segment_skipped(self):
        """Segment with unparseable timestamps is skipped with a warning."""
        raws = [
            _RawSegment(start_time="bad", end_time="01:00", text="Bad start.", relevance_score=0.8),
            _RawSegment(start_time="01:00", end_time="01:30", text="Good content.", relevance_score=0.9),
        ]
        result = _raw_segments_to_transcript_segments(raws)
        assert len(result) == 1
        assert result[0].text == "Good content."

    def test_empty_input_returns_empty(self):
        """Empty input returns empty list."""
        result = _raw_segments_to_transcript_segments([])
        assert result == []

    def test_all_invalid_returns_empty(self):
        """All invalid segments results in empty list."""
        raws = [
            _RawSegment(start_time="xx:yy", end_time="zz:ww", text="Garbage."),
        ]
        result = _raw_segments_to_transcript_segments(raws)
        assert result == []


# ---------------------------------------------------------------------------
# _analyze_with_groq_structured — lines 362-406
# ---------------------------------------------------------------------------


class TestAnalyzeWithGroqStructured:
    """Tests for _analyze_with_groq_structured() with mocked AsyncGroq client."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_analysis_error(self):
        """AnalysisError raised when groq_api_key is not configured."""
        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.groq_api_key = None
            mock_cfg_cls.return_value = mock_cfg

            with pytest.raises(AnalysisError, match="GROQ_API_KEY not configured"):
                await _analyze_with_groq_structured("user prompt", "system prompt", "groq:meta-llama/llama-4-scout")

    @pytest.mark.asyncio
    async def test_successful_response_returns_segments(self):
        """Valid Groq response is parsed and returned as TranscriptSegments."""
        raw_json = """{
            "most_relevant_segments": [
                {
                    "start_time": "00:10",
                    "end_time": "00:40",
                    "text": "This is an engaging segment.",
                    "relevance_score": 0.9,
                    "reasoning": "Strong hook",
                    "title": "Great Moment"
                }
            ],
            "summary": "A video summary.",
            "key_topics": ["topic1"]
        }"""

        mock_message = MagicMock()
        mock_message.content = raw_json
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.groq_api_key = "test-key"
            mock_cfg_cls.return_value = mock_cfg

            with patch("src.pipeline.analyze.AsyncGroq", return_value=mock_client):
                result = await _analyze_with_groq_structured("user prompt", "system prompt", "groq:meta-llama/llama-4-scout")

        assert len(result) == 1
        assert result[0].start_time == pytest.approx(10.0)
        assert result[0].end_time == pytest.approx(40.0)
        assert result[0].text == "This is an engaging segment."

    @pytest.mark.asyncio
    async def test_empty_response_raises_analysis_error(self):
        """Empty content in Groq response raises AnalysisError."""
        mock_message = MagicMock()
        mock_message.content = ""
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.groq_api_key = "test-key"
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch("src.pipeline.analyze.AsyncGroq", return_value=mock_client),
                pytest.raises(AnalysisError, match="Empty response from Groq API"),
            ):
                await _analyze_with_groq_structured("user prompt", "system prompt", "groq:meta-llama/llama-4-scout")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_analysis_error(self):
        """Invalid JSON response raises AnalysisError."""
        mock_message = MagicMock()
        mock_message.content = "not valid json {{{"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.groq_api_key = "test-key"
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch("src.pipeline.analyze.AsyncGroq", return_value=mock_client),
                pytest.raises(AnalysisError, match="Invalid JSON response from Groq"),
            ):
                await _analyze_with_groq_structured("user prompt", "system prompt", "groq:meta-llama/llama-4-scout")

    @pytest.mark.asyncio
    async def test_bare_model_name_strips_groq_prefix(self):
        """The 'groq:' prefix is stripped before calling the API."""
        raw_json = """{
            "most_relevant_segments": [],
            "summary": "",
            "key_topics": []
        }"""
        mock_message = MagicMock()
        mock_message.content = raw_json
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.groq_api_key = "test-key"
            mock_cfg_cls.return_value = mock_cfg

            with patch("src.pipeline.analyze.AsyncGroq", return_value=mock_client):
                await _analyze_with_groq_structured("user prompt", "system prompt", "groq:meta-llama/llama-4-scout")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "meta-llama/llama-4-scout"


# ---------------------------------------------------------------------------
# _analyze_with_pydantic_ai — lines 425-441
# ---------------------------------------------------------------------------


class TestAnalyzeWithPydanticAI:
    """Tests for _analyze_with_pydantic_ai() with mocked Agent."""

    @pytest.mark.asyncio
    async def test_successful_response_returns_segments(self):
        """Valid Pydantic AI agent response returns TranscriptSegments."""
        raw_analysis = _RawAnalysis(
            most_relevant_segments=[
                _RawSegment(
                    start_time="00:15",
                    end_time="00:45",
                    text="This is fascinating content.",
                    relevance_score=0.88,
                    title="Key Insight",
                )
            ],
            summary="A great video.",
            key_topics=["insight"],
        )

        mock_result = MagicMock()
        mock_result.output = raw_analysis

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = False
            mock_cfg.get_llm_model.return_value = "openai:gpt-4o"
            mock_cfg_cls.return_value = mock_cfg

            with patch("src.pipeline.analyze.Agent", return_value=mock_agent):
                result = await _analyze_with_pydantic_ai("user prompt", "system prompt")

        assert len(result) == 1
        assert result[0].start_time == pytest.approx(15.0)
        assert result[0].end_time == pytest.approx(45.0)
        assert result[0].text == "This is fascinating content."

    @pytest.mark.asyncio
    async def test_empty_segments_returns_empty_list(self):
        """Agent returning no segments results in an empty list."""
        raw_analysis = _RawAnalysis(
            most_relevant_segments=[],
            summary="Empty video.",
            key_topics=[],
        )

        mock_result = MagicMock()
        mock_result.output = raw_analysis

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = False
            mock_cfg.get_llm_model.return_value = "openai:gpt-4o"
            mock_cfg_cls.return_value = mock_cfg

            with patch("src.pipeline.analyze.Agent", return_value=mock_agent):
                result = await _analyze_with_pydantic_ai("user prompt", "system prompt")

        assert result == []

    @pytest.mark.asyncio
    async def test_local_llm_constructs_openai_model_with_base_url(self):
        """When local_llm_enabled=True, Agent is constructed with an OpenAIModel."""
        raw_analysis = _RawAnalysis(
            most_relevant_segments=[],
            summary="",
            key_topics=[],
        )
        mock_result = MagicMock()
        mock_result.output = raw_analysis
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("src.pipeline.analyze.get_config") as mock_cfg_cls:
            mock_cfg = MagicMock()
            mock_cfg.local_llm_enabled = True
            mock_cfg.local_llm_model = "local-model"
            mock_cfg.local_llm_base_url = "http://localhost:6969/v1"
            mock_cfg.local_llm_api_key = "not-needed"
            mock_cfg_cls.return_value = mock_cfg

            with (
                patch("src.pipeline.analyze.OpenAIProvider") as mock_provider_cls,
                patch("src.pipeline.analyze.OpenAIModel") as mock_model_cls,
                patch("src.pipeline.analyze.Agent", return_value=mock_agent),
            ):
                mock_provider_cls.return_value = MagicMock()
                mock_model_cls.return_value = MagicMock()
                await _analyze_with_pydantic_ai("user prompt", "system prompt")

        mock_provider_cls.assert_called_once_with(
            base_url="http://localhost:6969/v1",
            api_key="not-needed",
        )
        mock_model_cls.assert_called_once_with(
            "local-model",
            provider=mock_provider_cls.return_value,
        )


# end tests/unit/test_analyze.py
