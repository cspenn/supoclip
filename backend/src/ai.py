# start backend/src/ai.py
"""
AI-related functions for transcript analysis with enhanced precision.
"""

import logging
import re

from pydantic_ai import Agent

from .config import Config
from .ai_types.ai_models import TranscriptSegment, TranscriptAnalysis

logger = logging.getLogger(__name__)
config = Config()


# Simplified system prompt that trusts transcript timing
simplified_system_prompt = """You are an expert at analyzing video transcripts to find the most engaging segments for short-form content creation.

CORE OBJECTIVES:
1. Identify segments that would be compelling on social media platforms
2. Focus on complete thoughts, insights, or entertaining moments
3. Prioritize content with hooks, emotional moments, or valuable information
4. Each segment should be engaging and worth watching

SEGMENT SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone
5. ENTERTAINING: Content people would want to share

VERBATIM TEXT REQUIREMENT - CRITICAL:
- The "text" field MUST contain the EXACT words from the transcript
- Do NOT summarize, paraphrase, or rewrite the transcript text
- Copy the text VERBATIM between your selected start_time and end_time
- The text will be displayed as captions - accuracy is essential

TIMING GUIDELINES:
- Segments MUST respect the configured duration range for optimal engagement
- CRITICAL: start_time MUST be different from end_time (minimum duration requirement enforced)
- Focus on natural content boundaries rather than arbitrary time limits
- Include enough context for the segment to be understandable
- Note: Exact duration constraints will be specified in the analysis prompt based on user preferences

CLEAN START RULE - CRITICAL FOR VIRAL CLIPS:
- NEVER start clips with transition words, fillers, or verbal disfluencies
- Forbidden starts: "And...", "But...", "So...", "Well...", "Because...", "Also...", "Um...", "Uh...", "You know...", "I mean...", "Like..."
- If original segment starts with a forbidden word, MUST adjust start point to first strong word
- Strong opening words: nouns, verbs, action words, attention-grabbing phrases
- IN YOUR REASONING FIELD, MUST state: "Original start: '[weak phrase]' → Clean start: '[strong phrase]'"
- First word of final clip MUST be powerful, commanding attention, not transitional
- Example: ❌ "So the main thing you need..." → ✅ "The main thing you need..." (reasoning: "Original start: 'So the' → Clean start: 'The main'")

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript WITH MILLISECOND PRECISION
- Timestamp format MUST be MM:SS.mmm (e.g., 02:35.450, NOT 02:35)
- Extract milliseconds from transcript timing like [02:35.450 - 02:45.820]
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
- Look at transcript ranges like [02:25.120 - 02:35.890] and preserve the milliseconds
- NEVER use the same timestamp for both start_time and end_time
- Example CORRECT: start_time: "02:25.120", end_time: "02:35.890"
- Example INCORRECT: start_time: "02:25", end_time: "02:35" (missing milliseconds)

Find 3-7 compelling segments that would work well as standalone clips. Quality over quantity - choose segments that would genuinely engage viewers and have proper time ranges."""

# Module-level caches for lazy initialization
_llm_model = None
_transcript_agent = None


def _get_llm_model():
    """Lazy initialization of LLM model (only when needed).

    This allows the backend to start even if:
    - Local LLM (KoboldCPP) is not running
    - Cloud API keys are not configured

    The error only occurs when actually processing videos.
    """
    global _llm_model
    if _llm_model is None:
        try:
            _llm_model = config.get_llm_model()
            # Log which LLM mode is active
            if config.local_llm_enabled:
                logger.info(f"Using local LLM: {config.local_llm_base_url}")
            else:
                logger.info(f"Using cloud LLM: {config.llm}")
        except ValueError as e:
            logger.error(f"LLM configuration error: {e}")
            raise
    return _llm_model


def _get_transcript_agent():
    """Lazy initialization of transcript agent (only when needed).

    Creates the Pydantic AI agent with the configured LLM model.
    This is deferred until the agent is actually used for analysis.
    """
    global _transcript_agent
    if _transcript_agent is None:
        model = _get_llm_model()
        _transcript_agent = Agent(
            model=model,
            output_type=TranscriptAnalysis,
            system_prompt=simplified_system_prompt,
        )
    return _transcript_agent


class CleanStartValidator:
    """Validates clip doesn't start with transition words/fillers."""

    FORBIDDEN_STARTS = [
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
    ]

    @staticmethod
    def validate(segment_text: str) -> tuple[bool, str]:
        """
        Validate clip doesn't start with transition words/fillers.

        Returns:
            Tuple of (is_valid, reason)
        """
        text_lower = segment_text.lower().strip()
        for forbidden in CleanStartValidator.FORBIDDEN_STARTS:
            if text_lower.startswith(forbidden):
                return False, f"Starts with forbidden word: '{forbidden.strip()}'"
        return True, "Clean start"


def validate_clean_start(segment_text: str) -> tuple[bool, str]:
    """Legacy wrapper for backward compatibility."""
    return CleanStartValidator.validate(segment_text)


class TimestampParser:
    """Parses and validates transcript timestamps."""

    MIN_DURATION_SECONDS = 5

    @staticmethod
    def parse_timestamp(timestamp: str) -> float:
        """
        Parse MM:SS or MM:SS.mmm timestamp to seconds with millisecond precision.

        Raises:
            ValueError: If timestamp format is invalid
        """
        try:
            parts = timestamp.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid format: {timestamp}")
            minutes, seconds = int(parts[0]), float(parts[1])
            return minutes * 60 + seconds
        except (ValueError, IndexError) as e:
            raise ValueError(f"Cannot parse timestamp '{timestamp}': {e}")

    @staticmethod
    def calculate_duration(start_time: str, end_time: str) -> float:
        """Calculate duration between two timestamps in seconds."""
        start_seconds = TimestampParser.parse_timestamp(start_time)
        end_seconds = TimestampParser.parse_timestamp(end_time)
        return end_seconds - start_seconds

    @staticmethod
    def validate_duration(duration: float) -> tuple[bool, str]:
        """Validate duration meets minimum requirement."""
        if duration <= 0:
            return False, f"Invalid duration: {duration:.3f}s (must be positive)"
        if duration < TimestampParser.MIN_DURATION_SECONDS:
            return (
                False,
                f"Too short: {duration:.3f}s (min {TimestampParser.MIN_DURATION_SECONDS}s required)",
            )
        return True, f"Valid: {duration:.3f}s"


class TimestampFormatValidator:
    """Validates timestamp format includes millisecond precision."""

    # Regex for MM:SS.mmm format (milliseconds required)
    PRECISE_FORMAT = re.compile(r"^\d{1,2}:\d{2}\.\d{1,3}$")
    # Regex for MM:SS format (milliseconds missing)
    IMPRECISE_FORMAT = re.compile(r"^\d{1,2}:\d{2}$")

    @staticmethod
    def validate(timestamp: str) -> tuple[bool, str]:
        """
        Validate timestamp has millisecond precision.

        Returns:
            Tuple of (has_milliseconds, warning_message)
        """
        timestamp = timestamp.strip()
        if TimestampFormatValidator.PRECISE_FORMAT.match(timestamp):
            return True, "Format OK (MM:SS.mmm)"
        if TimestampFormatValidator.IMPRECISE_FORMAT.match(timestamp):
            return (
                False,
                f"Missing milliseconds in '{timestamp}' - precision may be reduced",
            )
        return False, f"Invalid timestamp format: '{timestamp}'"

    @staticmethod
    def add_default_milliseconds(timestamp: str) -> str:
        """
        Add .000 to timestamps missing milliseconds.

        This is a fallback when AI returns MM:SS format despite instructions.
        """
        timestamp = timestamp.strip()
        if TimestampFormatValidator.IMPRECISE_FORMAT.match(timestamp):
            return f"{timestamp}.000"
        return timestamp


class TranscriptSegmentValidator:
    """Validates transcript segments for clip generation."""

    MIN_WORD_COUNT = 3

    @staticmethod
    def validate_text_content(text: str) -> tuple[bool, str]:
        """Validate segment has sufficient text content."""
        if not text.strip():
            return False, "Empty text"
        if len(text.split()) < TranscriptSegmentValidator.MIN_WORD_COUNT:
            return (
                False,
                f"Too few words: {len(text.split())} (min {TranscriptSegmentValidator.MIN_WORD_COUNT} required)",
            )
        return True, "Valid content"

    @staticmethod
    def validate_timestamps(segment: TranscriptSegment) -> tuple[bool, str]:
        """Validate segment timestamps."""
        # Check format precision and log warnings
        start_has_ms, start_msg = TimestampFormatValidator.validate(segment.start_time)
        end_has_ms, end_msg = TimestampFormatValidator.validate(segment.end_time)

        if not start_has_ms:
            logger.warning(f"Timestamp precision warning: {start_msg}")
            # Apply fallback: add .000 if missing
            segment.start_time = TimestampFormatValidator.add_default_milliseconds(
                segment.start_time
            )
        if not end_has_ms:
            logger.warning(f"Timestamp precision warning: {end_msg}")
            segment.end_time = TimestampFormatValidator.add_default_milliseconds(
                segment.end_time
            )

        if segment.start_time == segment.end_time:
            return False, "Start and end times are identical"
        try:
            duration = TimestampParser.calculate_duration(
                segment.start_time, segment.end_time
            )
            is_valid, reason = TimestampParser.validate_duration(duration)
            if is_valid:
                return True, f"Valid ({duration:.3f}s)"
            return False, reason
        except ValueError as e:
            return False, f"Invalid timestamp format: {e}"

    @staticmethod
    def validate_segment(segment: TranscriptSegment) -> tuple[bool, str, float]:
        """
        Validate entire segment for clip generation.

        Returns:
            Tuple of (is_valid, reason, duration_seconds)
        """
        # Check text content
        is_valid, reason = TranscriptSegmentValidator.validate_text_content(
            segment.text
        )
        if not is_valid:
            return False, f"Text validation: {reason}", 0.0

        # Check clean start
        is_clean, reason = CleanStartValidator.validate(segment.text)
        if not is_clean:
            return False, f"Clean start validation: {reason}", 0.0

        # Check timestamps
        is_valid, reason = TranscriptSegmentValidator.validate_timestamps(segment)
        if not is_valid:
            return False, f"Timestamp validation: {reason}", 0.0

        # Calculate final duration for logging
        try:
            duration = TimestampParser.calculate_duration(
                segment.start_time, segment.end_time
            )
            return True, "Valid segment", duration
        except ValueError:
            return False, "Duration calculation failed", 0.0


async def _analyze_with_structured_model(
    transcript: str,
    min_length: int,
    max_length: int,
    custom_prompt: str | None,
) -> TranscriptAnalysis:
    """Analyze using Groq Structured Outputs API (Llama 4 Scout)."""
    logger.info("Using Groq Structured Outputs API for Llama 4 Scout compatibility")
    from .ai_structured import analyze_transcript_structured

    try:
        structured_result = await analyze_transcript_structured(
            transcript,
            min_length=min_length,
            max_length=max_length,
            custom_prompt=custom_prompt,
        )
        # Convert from ai_structured.TranscriptAnalysis to ai.TranscriptAnalysis
        converted_segments = [
            TranscriptSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                relevance_score=seg.relevance_score,
                reasoning=seg.reasoning,
            )
            for seg in structured_result.most_relevant_segments
        ]
        return TranscriptAnalysis(
            most_relevant_segments=converted_segments,
            summary=structured_result.summary,
            key_topics=structured_result.key_topics,
        )
    except ValueError as e:
        logger.error(f"Groq Structured Outputs validation failed: {e}")
        raise ValueError(
            f"AI analysis failed: {e}. "
            f"Try reducing clip duration requirements (recommended: 10-45 seconds)."
        ) from e
    except Exception as e:
        logger.error(f"Groq Structured Outputs API error: {e}")
        raise


async def _analyze_with_standard_model(
    analysis_prompt: str,
) -> TranscriptAnalysis:
    """Analyze using standard Pydantic AI agent (Tool Calling)."""
    # Lazy initialize agent on first use
    agent = _get_transcript_agent()
    result = await agent.run(analysis_prompt)

    analysis = result.data
    logger.info(f"AI analysis found {len(analysis.most_relevant_segments)} segments")

    # Validate and filter segments
    validated_segments = []
    for segment in analysis.most_relevant_segments:
        is_valid, reason, duration = TranscriptSegmentValidator.validate_segment(
            segment
        )

        if not is_valid:
            logger.warning(f"Skipping segment: {reason} - '{segment.text[:50]}...'")
            continue

        validated_segments.append(segment)
        logger.info(
            f"Validated segment: {segment.start_time}-{segment.end_time} ({duration}s)"
        )

    # Sort by relevance
    validated_segments.sort(key=lambda x: x.relevance_score, reverse=True)

    final_analysis = TranscriptAnalysis(
        most_relevant_segments=validated_segments,
        summary=analysis.summary,
        key_topics=analysis.key_topics,
    )

    logger.info(f"Selected {len(validated_segments)} segments for processing")
    if validated_segments:
        logger.info(f"Top segment score: {validated_segments[0].relevance_score:.2f}")

    return final_analysis


def _validate_transcript(transcript: str) -> None:
    """Validate transcript input.

    Args:
        transcript: The transcript to validate

    Raises:
        ValueError: If transcript is empty or too short
    """
    if not transcript or not transcript.strip():
        logger.error("Cannot analyze empty transcript")
        raise ValueError(
            "Cannot analyze empty transcript - transcription may have failed"
        )

    if len(transcript.strip()) < 50:
        logger.error(
            f"Transcript too short ({len(transcript)} chars) - may indicate transcription failure"
        )
        raise ValueError(
            f"Transcript too short ({len(transcript)} chars) - minimum 50 characters required"
        )


def _build_analysis_prompt(
    transcript: str, min_length: int, max_length: int, custom_prompt: str | None
) -> str:
    """Build the analysis prompt for the AI.

    Args:
        transcript: The transcript to analyze
        min_length: Minimum clip length
        max_length: Maximum clip length
        custom_prompt: Optional custom instructions

    Returns:
        Formatted analysis prompt
    """
    prompt_parts = [
        "Analyze this video transcript and identify the most engaging segments for short-form content.",
        f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
    ]

    if custom_prompt:
        prompt_parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}")

    prompt_parts.extend(
        (
            "\nFind segments that would be compelling as standalone clips for social media.",
            f"\nTranscript:\n{transcript}",
        )
    )

    return "\n".join(prompt_parts)


def _should_use_structured_model() -> bool:
    """Check if we should use Groq Structured Outputs API.

    Returns:
        True if using Llama 4 Scout/Maverick models
    """
    model_str = config.llm if not config.local_llm_enabled else ""
    return "llama-4-scout" in model_str or "llama-4-maverick" in model_str


async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45,
    custom_prompt: str | None = None,
) -> TranscriptAnalysis:
    """Get the most relevant parts of a transcript for creating clips - simplified version."""
    logger.info(f"Starting AI analysis of transcript ({len(transcript)} chars)")
    logger.info(f"Clip length settings - Min: {min_length}s, Max: {max_length}s")
    if custom_prompt:
        logger.info(f"Using custom AI prompt: {custom_prompt[:100]}...")

    # Validate transcript input
    _validate_transcript(transcript)

    try:
        # Route to appropriate model
        if _should_use_structured_model():
            return await _analyze_with_structured_model(
                transcript, min_length, max_length, custom_prompt
            )

        # For all other models, use Pydantic AI (tool calling)
        analysis_prompt = _build_analysis_prompt(
            transcript, min_length, max_length, custom_prompt
        )
        return await _analyze_with_standard_model(analysis_prompt)

    except ValueError as e:
        # Re-raise validation errors so tasks correctly mark as failed
        logger.error(f"Validation error in transcript analysis: {e}")
        raise
    except Exception as e:
        # Re-raise other exceptions so tasks correctly mark as failed
        logger.error(f"Error in transcript analysis: {e}", exc_info=True)
        raise

# end backend/src/ai.py
