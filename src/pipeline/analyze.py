# start src/pipeline/analyze.py
"""Unified LLM transcript analysis for clip selection.

Merges ai.py (Pydantic AI / tool-calling) and ai_structured.py
(Groq structured JSON outputs) into a single entry point.

Routing logic:
- ``groq:`` model strings that contain ``llama`` use Groq's native
  ``json_schema`` structured-output API, which avoids tool-calling
  incompatibilities on Llama 4 Scout/Maverick.
- All other models (local, OpenAI, Anthropic, etc.) fall through to
  Pydantic AI's standard agent loop.
"""

import json
import logging
from contextlib import suppress

import stamina
from groq import AsyncGroq
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.config import get_config
from src.exceptions import AnalysisError, InsufficientSegmentsError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

_FILLER_STARTS = (
    "and ",
    "but ",
    "so ",
    "well ",
    "because ",
    "also ",
    "um ",
    "uh ",
    "you know",
    "i mean",
    "like ",
)


class TranscriptSegment(BaseModel):
    """A selected clip segment from the AI analysis."""

    model_config = ConfigDict(strict=True, extra="forbid")

    start_time: float = Field(..., description="Clip start in seconds")
    end_time: float = Field(..., description="Clip end in seconds")
    text: str = Field(..., description="Transcript text of this segment")
    score: float = Field(default=0.8, ge=0.0, le=1.0, description="Relevance score")
    title: str = Field(default="", description="Suggested clip title")


# ``AnalysisError`` and ``InsufficientSegmentsError`` are re-exported from the
# centralized hierarchy in ``src.exceptions`` so callers (and tests) can keep
# importing them from this module. They are aliases (not subclasses) on purpose:
# ``InsufficientSegmentsError`` must remain a subclass of this ``AnalysisError``
# so an un-owned ``except AnalysisError`` site (video_service) still catches it.
__all__ = [
    "AnalysisError",
    "InsufficientSegmentsError",
    "TranscriptSegment",
    "analyze_transcript",
    "build_system_prompt",
    "validate_segments",
]


# ---------------------------------------------------------------------------
# Internal response model for LLM parsing (string timestamps from LLM)
# ---------------------------------------------------------------------------


class _RawSegment(BaseModel):
    """Raw segment returned by LLM before float conversion."""

    model_config = ConfigDict(extra="ignore")

    start_time: str
    end_time: str
    text: str
    relevance_score: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str = ""
    title: str = ""


class _RawAnalysis(BaseModel):
    """Raw analysis envelope returned by LLM."""

    model_config = ConfigDict(extra="ignore")

    most_relevant_segments: list[_RawSegment]
    summary: str = ""
    key_topics: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Timestamp helpers (plain functions, no validator classes)
# ---------------------------------------------------------------------------


def _parse_timestamp(timestamp: str) -> float:
    """Parse a ``MM:SS`` or ``MM:SS.mmm`` timestamp to seconds.

    Args:
        timestamp: String in ``MM:SS`` or ``MM:SS.mmm`` format.

    Returns:
        Total seconds as a float.

    Raises:
        ValueError: If the format cannot be parsed.
    """
    try:
        parts = timestamp.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Expected MM:SS format, got: {timestamp!r}")
        return int(parts[0]) * 60 + float(parts[1])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Cannot parse timestamp {timestamp!r}: {exc}") from exc


def _raw_segment_to_float_times(raw: _RawSegment) -> tuple[float, float]:
    """Convert string timestamps to float seconds.

    Args:
        raw: A raw segment with string ``start_time`` / ``end_time`` fields.

    Returns:
        Tuple of ``(start_seconds, end_seconds)``.

    Raises:
        ValueError: If either timestamp cannot be parsed.
    """
    start = _parse_timestamp(raw.start_time)
    end = _parse_timestamp(raw.end_time)
    return start, end


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_system_prompt(
    min_length_s: float,
    max_length_s: float,
    custom_prompt: str | None = None,
) -> str:
    """Build the LLM system prompt for clip selection.

    Args:
        min_length_s: Minimum clip length in seconds.
        max_length_s: Maximum clip length in seconds.
        custom_prompt: If provided, append after the default prompt.

    Returns:
        Complete system prompt string.
    """
    prompt = f"""You are an expert at analyzing video transcripts to find the most engaging segments for short-form content creation.

CORE OBJECTIVES:
1. Identify segments that would be compelling on social media platforms.
2. Focus on complete thoughts, insights, or entertaining moments (NOT fragments).
3. Prioritize content with hooks, emotional moments, or valuable information.
4. Each segment MUST be between {min_length_s} and {max_length_s} seconds long.

SEGMENT SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines (complete sentences).
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories.
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration.
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone.
5. ENTERTAINING: Content people would want to share.

CLEAN START RULE:
- NEVER start a clip with transition words or verbal fillers.
- Forbidden starts: "And", "But", "So", "Well", "Because", "Also", "Um", "Uh", "You know", "I mean", "Like".
- Adjust the start point to the first strong word if necessary.

VERBATIM TEXT REQUIREMENT:
- The "text" field MUST contain the EXACT words from the transcript.
- Do NOT summarize, paraphrase, or rewrite the transcript text.

DURATION REQUIREMENTS — CRITICAL:
- MINIMUM: {min_length_s} seconds per segment.
- MAXIMUM: {max_length_s} seconds per segment.
- NEVER return ultra-short clips or fragments.
- CRITICAL: start_time MUST be DIFFERENT from end_time.

TIMESTAMP FORMAT:
- Use MM:SS.mmm format with millisecond precision (e.g., 02:35.450).
- start_time MUST be less than end_time.

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{{
  "most_relevant_segments": [
    {{
      "start_time": "MM:SS.mmm",
      "end_time": "MM:SS.mmm",
      "text": "verbatim segment text",
      "relevance_score": 0.85,
      "reasoning": "why this segment is compelling",
      "title": "Suggested clip title"
    }}
  ],
  "summary": "brief summary of the video",
  "key_topics": ["topic1", "topic2"]
}}

Find 3-7 compelling segments. Quality over quantity."""

    if custom_prompt:
        prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}"

    return prompt


def _build_user_prompt(
    transcript_text: str,
    min_length_s: float,
    max_length_s: float,
    custom_prompt: str | None = None,
) -> str:
    """Build the user-turn prompt for the LLM.

    Args:
        transcript_text: Full transcript formatted as text.
        min_length_s: Minimum clip duration in seconds.
        max_length_s: Maximum clip duration in seconds.
        custom_prompt: Optional additional instructions.

    Returns:
        Formatted user prompt string.
    """
    parts = [
        "Analyze this video transcript and identify the most engaging segments for short-form content.",
        f"Segments MUST be between {min_length_s}-{max_length_s} seconds for optimal engagement.",
    ]
    if custom_prompt:
        parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}")
    parts.extend(
        [
            "\nFind segments that would be compelling as standalone clips for social media.",
            f"\nTranscript:\n{transcript_text}",
        ]
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Validation helpers (plain functions, NOT validator classes)
# ---------------------------------------------------------------------------


# Tolerance (seconds) allowed when comparing a segment end against the derived
# transcript upper bound, to avoid nuking a legitimate end-of-video clip whose
# end_ms rounds slightly past the last word.
_BOUNDS_TOLERANCE_S = 1.0


def _derive_transcript_bound(words: list[dict]) -> float | None:
    """Derive an upper time bound (seconds) from word-level timing data.

    Uses the maximum ``end_ms`` across all words so segments with hallucinated
    timestamps beyond the actual media duration can be rejected.

    Args:
        words: Word-level timing data [{"text", "start_ms", "end_ms"}, ...].

    Returns:
        The maximum word end time in seconds, or None when no usable
        ``end_ms`` values are present (bounds check then skipped).
    """
    end_values = [w["end_ms"] for w in words if isinstance(w, dict) and isinstance(w.get("end_ms"), (int, float))]
    if not end_values:
        return None
    return max(end_values) / 1000.0


def _exceeds_bounds(
    seg: TranscriptSegment,
    max_time_s: float | None,
) -> bool:
    """Check whether a segment falls outside the transcript time bound.

    Args:
        seg: The candidate segment.
        max_time_s: Upper bound derived from the transcript (seconds), or None
            to skip the bounds check entirely.

    Returns:
        True if the segment starts at/after the bound or ends beyond it
        (plus a small tolerance), indicating hallucinated timestamps.
    """
    if max_time_s is None:
        return False
    if seg.start_time >= max_time_s:
        return True
    return seg.end_time > max_time_s + _BOUNDS_TOLERANCE_S


def validate_segments(
    segments: list[TranscriptSegment],
    min_length_s: float,
    max_length_s: float,
    max_time_s: float | None = None,
) -> list[TranscriptSegment]:
    """Filter and validate LLM-returned segments.

    Removes segments that:
    - Have start_time == end_time (zero duration).
    - Are shorter than min_length_s.
    - Are longer than max_length_s.
    - Start/end beyond the transcript time bound (hallucinated timestamps).
    - Start with filler words ('And', 'But', 'So', 'Um', 'Uh', 'Like', 'You know').

    Args:
        segments: Raw segments from LLM.
        min_length_s: Minimum acceptable duration.
        max_length_s: Maximum acceptable duration.
        max_time_s: Optional upper time bound derived from the transcript
            (max word end_ms / 1000). Segments whose start/end exceed this are
            rejected as hallucinations. When None, the bounds check is skipped.

    Returns:
        Filtered list of valid segments.
    """
    valid: list[TranscriptSegment] = []
    for seg in segments:
        duration = seg.end_time - seg.start_time

        if duration <= 0:
            logger.warning(
                "Skipping segment: zero or negative duration (start=%.3f end=%.3f): %.50s",
                seg.start_time,
                seg.end_time,
                seg.text,
            )
            continue

        if duration < min_length_s:
            logger.warning(
                "Skipping segment: too short (%.2fs < %.2fs): %.50s",
                duration,
                min_length_s,
                seg.text,
            )
            continue

        if duration > max_length_s:
            logger.warning(
                "Skipping segment: too long (%.2fs > %.2fs): %.50s",
                duration,
                max_length_s,
                seg.text,
            )
            continue

        if _exceeds_bounds(seg, max_time_s):
            logger.warning(
                "Skipping segment: timestamps exceed transcript bound (start=%.3f end=%.3f bound=%.3f): %.50s",
                seg.start_time,
                seg.end_time,
                max_time_s,
                seg.text,
            )
            continue

        text_lower = seg.text.lower().strip()
        filler_match = next((f for f in _FILLER_STARTS if text_lower.startswith(f)), None)
        if filler_match:
            logger.warning(
                "Skipping segment: starts with filler %r: %.50s",
                filler_match.strip(),
                seg.text,
            )
            continue

        valid.append(seg)

    return valid


# ---------------------------------------------------------------------------
# Model routing
# ---------------------------------------------------------------------------


def _should_use_structured_output(model_string: str) -> bool:
    """Check if the model supports Groq structured outputs.

    Groq structured outputs (JSON schema mode) works with Llama models.

    Args:
        model_string: The configured LLM model identifier string.

    Returns:
        True if the model is a Groq-hosted Llama model.
    """
    lower = model_string.lower()
    return "groq:" in lower and "llama" in lower


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------


@stamina.retry(on=Exception, attempts=3, wait_initial=2.0, wait_max=10.0)
async def _analyze_with_groq_structured(
    user_prompt: str,
    system_prompt: str,
    model_string: str,
) -> list[TranscriptSegment]:
    """Call Groq API with structured JSON output.

    Args:
        user_prompt: User-turn prompt text.
        system_prompt: System prompt text.
        model_string: Full model string like ``groq:meta-llama/llama-4-scout-17b-16e-instruct``.

    Returns:
        List of TranscriptSegment objects parsed from the response.

    Raises:
        AnalysisError: If the API key is missing, response is empty, or JSON is invalid.
    """
    cfg = get_config()
    if not cfg.groq_api_key:
        raise AnalysisError("GROQ_API_KEY not configured in environment")

    # Strip the "groq:" prefix to get the bare model name for the API.
    bare_model = model_string.split("groq:", 1)[-1]

    client = AsyncGroq(api_key=cfg.groq_api_key)

    try:
        logger.info("Calling Groq structured outputs API with model: %s", bare_model)

        completion = await client.chat.completions.create(
            model=bare_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "transcript_analysis",
                    "strict": True,
                    "schema": _RawAnalysis.model_json_schema(),
                },
            },
            temperature=0.7,
            max_tokens=4096,
        )

        response_content = completion.choices[0].message.content or ""
        if not response_content:
            raise AnalysisError("Empty response from Groq API")

        logger.info("Groq response received (%d chars)", len(response_content))

        raw_data = json.loads(response_content)
        raw_analysis = _RawAnalysis(**raw_data)

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Groq JSON response: %s", exc)
        raise AnalysisError(f"Invalid JSON response from Groq: {exc}") from exc

    return _raw_segments_to_transcript_segments(raw_analysis.most_relevant_segments)


@stamina.retry(on=Exception, attempts=3, wait_initial=2.0, wait_max=10.0)
async def _analyze_with_pydantic_ai(
    user_prompt: str,
    system_prompt: str,
) -> list[TranscriptSegment]:
    """Call LLM via Pydantic AI agent.

    Args:
        user_prompt: User-turn prompt text.
        system_prompt: System prompt text.

    Returns:
        List of TranscriptSegment objects from the agent response.

    Raises:
        AnalysisError: If the agent call fails or returns no data.
    """
    cfg = get_config()
    if cfg.local_llm_enabled:
        llm_model: str | OpenAIModel = OpenAIModel(
            cfg.local_llm_model,
            provider=OpenAIProvider(
                base_url=cfg.local_llm_base_url,
                api_key=cfg.local_llm_api_key,
            ),
        )
    else:
        llm_model = cfg.get_llm_model()

    agent: Agent[None, _RawAnalysis] = Agent(
        model=llm_model,
        output_type=_RawAnalysis,
        system_prompt=system_prompt,
    )

    result = await agent.run(user_prompt)
    raw_analysis: _RawAnalysis = result.output
    logger.info(
        "Pydantic AI agent found %d segments",
        len(raw_analysis.most_relevant_segments),
    )

    return _raw_segments_to_transcript_segments(raw_analysis.most_relevant_segments)


def _raw_segments_to_transcript_segments(
    raw_segments: list[_RawSegment],
) -> list[TranscriptSegment]:
    """Convert raw LLM string-timestamp segments to float-second TranscriptSegments.

    Args:
        raw_segments: List of segments with string timestamps from the LLM.

    Returns:
        List of TranscriptSegment with float start/end times in seconds.
        Segments with unparseable timestamps are skipped with a warning.
    """
    result: list[TranscriptSegment] = []
    for raw in raw_segments:
        with suppress(ValueError):
            start_s, end_s = _raw_segment_to_float_times(raw)
            result.append(
                TranscriptSegment(
                    start_time=start_s,
                    end_time=end_s,
                    text=raw.text,
                    score=raw.relevance_score,
                    title=raw.title,
                )
            )
            continue
        logger.warning(
            "Skipping segment with unparseable timestamps: %r -> %r",
            raw.start_time,
            raw.end_time,
        )
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def analyze_transcript(
    transcript_text: str,
    words: list[dict],
    min_length_s: float = 15.0,
    max_length_s: float = 45.0,
    custom_prompt: str | None = None,
) -> list[TranscriptSegment]:
    """Select the best clips from a video transcript.

    Routes to Groq structured outputs (for Llama models) or Pydantic AI
    based on the configured LLM model string.

    Args:
        transcript_text: Full transcript formatted as text.
        words: Word-level timing data [{"text", "start_ms", "end_ms"}, ...].
            Currently used for context; future versions may use it for
            sub-word alignment snapping.
        min_length_s: Minimum clip duration in seconds.
        max_length_s: Maximum clip duration in seconds.
        custom_prompt: Optional custom system prompt override.

    Returns:
        List of validated TranscriptSegment objects, 3-7 segments.

    Raises:
        AnalysisError: If LLM call fails or returns no valid segments.
    """
    if not transcript_text or not transcript_text.strip():
        raise AnalysisError("Cannot analyze empty transcript — transcription may have failed")
    if len(transcript_text.strip()) < 50:
        raise AnalysisError(f"Transcript too short ({len(transcript_text)} chars) — minimum 50 characters required")

    logger.info(
        "Starting AI analysis of transcript (%d chars), min=%.1fs max=%.1fs",
        len(transcript_text),
        min_length_s,
        max_length_s,
    )

    cfg = get_config()
    model_string = cfg.llm_model if not cfg.local_llm_enabled else ""

    max_time_s = _derive_transcript_bound(words)

    system_prompt = build_system_prompt(min_length_s, max_length_s, custom_prompt)
    user_prompt = _build_user_prompt(transcript_text, min_length_s, max_length_s, custom_prompt)

    try:
        if _should_use_structured_output(model_string):
            logger.info("Using Groq structured outputs for model: %s", model_string)
            raw_segments = await _analyze_with_groq_structured(user_prompt, system_prompt, model_string)
        else:
            logger.info("Using Pydantic AI agent for model: %s", model_string or "local")
            raw_segments = await _analyze_with_pydantic_ai(user_prompt, system_prompt)
    except AnalysisError:
        raise
    except Exception as exc:
        logger.error("LLM call failed: %s", exc, exc_info=True)
        raise AnalysisError(f"LLM call failed: {exc}") from exc

    validated = validate_segments(raw_segments, min_length_s, max_length_s, max_time_s)

    if not validated:
        raise InsufficientSegmentsError(
            f"No valid segments found after validation. "
            f"All {len(raw_segments)} segments were rejected. "
            f"Requested {min_length_s}-{max_length_s}s clips. "
            "Try shorter clip durations (10-45 seconds work best for viral content)."
        )

    # Sort by score descending.
    validated.sort(key=lambda s: s.score, reverse=True)

    logger.info("Analysis complete: %d valid segments selected", len(validated))
    return validated


# end src/pipeline/analyze.py
