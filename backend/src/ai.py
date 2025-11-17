"""
AI-related functions for transcript analysis with enhanced precision.
"""

from typing import List
import asyncio
import logging

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from .config import Config

logger = logging.getLogger(__name__)
config = Config()


class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing."""

    start_time: str = Field(description="Start timestamp in MM:SS format")
    end_time: str = Field(description="End timestamp in MM:SS format")
    text: str = Field(description="The transcript text for this segment")
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    reasoning: str = Field(description="Explanation for why this segment is relevant")


class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments."""

    most_relevant_segments: List[TranscriptSegment]
    summary: str = Field(description="Brief summary of the video content")
    key_topics: List[str] = Field(description="List of main topics discussed")


# Simplified system prompt that trusts AssemblyAI timing
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
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")

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


def validate_clean_start(segment_text: str) -> tuple[bool, str]:
    """
    Validate clip doesn't start with transition words/fillers.

    Returns:
        Tuple of (is_valid, reason)
    """
    forbidden_starts = [
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

    text_lower = segment_text.lower().strip()
    for forbidden in forbidden_starts:
        if text_lower.startswith(forbidden):
            return False, f"Starts with forbidden word: '{forbidden.strip()}'"

    return True, "Clean start"


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

    # Guard against empty transcripts to prevent AI hallucination
    if not transcript or len(transcript.strip()) == 0:
        logger.error("Cannot analyze empty transcript")
        raise ValueError(
            "Cannot analyze empty transcript - transcription may have failed"
        )

    # Additional safety check: transcript should have reasonable length
    if len(transcript.strip()) < 50:
        logger.error(
            f"Transcript too short ({len(transcript)} chars) - may indicate transcription failure"
        )
        raise ValueError(
            f"Transcript too short ({len(transcript)} chars) - minimum 50 characters required"
        )

    try:
        # Build the dynamic prompt
        prompt_parts = [
            "Analyze this video transcript and identify the most engaging segments for short-form content.",
            f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
        ]

        if custom_prompt:
            prompt_parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}")

        prompt_parts.append(
            "\nFind segments that would be compelling as standalone clips for social media."
        )
        prompt_parts.append(f"\nTranscript:\n{transcript}")

        analysis_prompt = "\n".join(prompt_parts)

        # Check if using Llama 4 Scout - use Groq Structured Outputs instead of tool calling
        model_str = config.llm if not config.local_llm_enabled else ""
        if "llama-4-scout" in model_str or "llama-4-maverick" in model_str:
            logger.info(
                "Using Groq Structured Outputs API for Llama 4 Scout compatibility"
            )
            from .ai_structured import analyze_transcript_structured

            return await analyze_transcript_structured(
                transcript,
                min_length=min_length,
                max_length=max_length,
                custom_prompt=custom_prompt,
            )

        # For all other models, use Pydantic AI (tool calling)
        # Lazy initialize agent on first use
        agent = _get_transcript_agent()
        result = await agent.run(analysis_prompt)

        analysis = result.data
        logger.info(
            f"AI analysis found {len(analysis.most_relevant_segments)} segments"
        )

        # Simple validation - just ensure segments have content
        validated_segments = []
        for segment in analysis.most_relevant_segments:
            # Validate text content
            if (
                not segment.text.strip() or len(segment.text.split()) < 3
            ):  # At least 3 words
                logger.warning(
                    f"Skipping segment with insufficient content: '{segment.text[:50]}...'"
                )
                continue

            # Validate clean start (no transition words/fillers)
            is_clean, reason = validate_clean_start(segment.text)
            if not is_clean:
                logger.warning(
                    f"Skipping segment with unclean start: {reason} - '{segment.text[:50]}...'"
                )
                continue

            # Validate timestamps - CRITICAL: start and end must be different
            if segment.start_time == segment.end_time:
                logger.warning(
                    f"Skipping segment with identical start/end times: {segment.start_time}"
                )
                continue

            # Parse timestamps to validate duration
            try:
                start_parts = segment.start_time.split(":")
                end_parts = segment.end_time.split(":")

                start_seconds = int(start_parts[0]) * 60 + int(start_parts[1])
                end_seconds = int(end_parts[0]) * 60 + int(end_parts[1])

                duration = end_seconds - start_seconds

                if duration <= 0:
                    logger.warning(
                        f"Skipping segment with invalid duration: {segment.start_time} to {segment.end_time} = {duration}s"
                    )
                    continue

                if duration < 5:  # Minimum 5 seconds
                    logger.warning(
                        f"Skipping segment too short: {duration}s (min 5s required)"
                    )
                    continue

                validated_segments.append(segment)
                logger.info(
                    f"Validated segment: {segment.start_time}-{segment.end_time} ({duration}s)"
                )

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Skipping segment with invalid timestamp format: {segment.start_time}-{segment.end_time}: {e}"
                )
                continue

        # Sort by relevance
        validated_segments.sort(key=lambda x: x.relevance_score, reverse=True)

        final_analysis = TranscriptAnalysis(
            most_relevant_segments=validated_segments,
            summary=analysis.summary,
            key_topics=analysis.key_topics,
        )

        logger.info(f"Selected {len(validated_segments)} segments for processing")
        if validated_segments:
            logger.info(
                f"Top segment score: {validated_segments[0].relevance_score:.2f}"
            )

        return final_analysis

    except Exception as e:
        logger.error(f"Error in transcript analysis: {e}")
        return TranscriptAnalysis(
            most_relevant_segments=[],
            summary=f"Analysis failed: {str(e)}",
            key_topics=[],
        )


def get_most_relevant_parts_sync(transcript: str) -> TranscriptAnalysis:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_most_relevant_parts_by_transcript(transcript))
