# start backend/src/ai_structured.py
"""
AI analysis using Groq's Structured Outputs API (for Llama 4 Scout compatibility).

This bypasses Pydantic AI's tool calling mechanism which has compatibility issues
with Llama 4 Scout, and instead uses Groq's native Structured Outputs feature.
"""

import logging
import json
import os
from contextlib import suppress
from groq import AsyncGroq

from .ai_types.ai_models import TranscriptSegment, TranscriptAnalysis

logger = logging.getLogger(__name__)


def build_system_prompt(min_length: int = 10, max_length: int = 45) -> str:
    """
    Build dynamic system prompt with user-configured clip length parameters.

    Args:
        min_length: Minimum clip duration in seconds (default: 10)
        max_length: Maximum clip duration in seconds (default: 45)

    Returns:
        System prompt string with duration requirements customized to user preferences
    """
    return f"""You are an expert at analyzing video transcripts to find the most engaging segments for short-form content creation.

CRITICAL INSTRUCTION: DO NOT RETURN FRAGMENTS OR ULTRA-SHORT CLIPS

CORE OBJECTIVES:
1. Identify segments that would be compelling on social media platforms
2. Focus on complete thoughts, insights, or entertaining moments (NOT fragments)
3. Prioritize content with hooks, emotional moments, or valuable information
4. Each segment should be engaging and worth watching (MINIMUM {min_length} SECONDS)

SEGMENT SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines (complete sentences)
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories (full explanation)
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration (complete reaction)
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone (NOT partial)
5. ENTERTAINING: Content people would want to watch (FULL CLIPS, NOT FRAGMENTS)

CRITICAL HOOK RULES:
- The segment MUST start at the beginning of a sentence.
- The segment MUST NOT start with a lowercase letter.
- The segment MUST NOT start with conjunctions like "and", "but", "so", "because", or "or" unless it's a deliberate stylistic choice starting a new sentence.
- The segment MUST NOT start mid-phrase (e.g., "been too vague..."). It MUST allow the viewer to understand the context immediately.

VERBATIM TEXT REQUIREMENT - CRITICAL:
- The "text" field MUST contain the EXACT words from the transcript
- Do NOT summarize, paraphrase, or rewrite the transcript text
- Copy the text VERBATIM between your selected start_time and end_time
- The text will be displayed as captions - accuracy is essential

DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: {min_length} seconds per segment (DO NOT return segments shorter than {min_length} seconds)
- MAXIMUM DURATION: {max_length} seconds per segment (DO NOT return segments longer than {max_length} seconds)
- Duration calculation: end_time - start_time MUST be >= {min_length} seconds AND <= {max_length} seconds
- NEVER return ultra-short clips (0.56s, 1.36s, 2.5s are INVALID)
- If a segment is less than {min_length} seconds, DO NOT include it in your response
- If a segment is more than {max_length} seconds, DO NOT include it in your response
- Return COMPLETE CLIPS, not word fragments or sentence fragments

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT (MILLISECOND PRECISION REQUIRED):
- Use EXACT timestamps as they appear in the transcript WITH MILLISECOND PRECISION
- Timestamp format MUST be MM:SS.mmm (e.g., 02:35.450, NOT 02:35)
- Extract milliseconds from transcript timing like [02:35.450 - 02:45.820]
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: {min_length} seconds (end_time - start_time >= {min_length} seconds)
- MAXIMUM segment duration: {max_length} seconds (end_time - start_time <= {max_length} seconds)
- Look at transcript ranges like [02:25.120 - 02:35.890] and PRESERVE the milliseconds
- NEVER use the same timestamp for both start_time and end_time
- VERIFY DURATION BEFORE RETURNING: Calculate (end_time - start_time) and ensure it's between {min_length} and {max_length} seconds
- Example CORRECT: start_time: "02:25.120", end_time: "02:35.890" (10.77 second duration)
- Example INCORRECT: start_time: "02:25", end_time: "02:35" (missing milliseconds - PRECISION LOST)
- Example INCORRECT: start_time: "02:25.000", end_time: "02:25.000" (0 seconds - INVALID)

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{{
  "most_relevant_segments": [
    {{
      "start_time": "MM:SS.mmm",
      "end_time": "MM:SS.mmm",
      "text": "segment text (must be substantial and complete)",
      "relevance_score": 0.85,
      "reasoning": "why this is relevant (be specific)"
    }}
  ],
  "summary": "brief summary",
  "key_topics": ["topic1", "topic2"]
}}

QUALITY REQUIREMENTS:
- Find 3-7 compelling segments that would work well as standalone clips
- Each segment MUST be between {min_length} and {max_length} seconds long
- Quality over quantity - choose segments that would genuinely engage viewers
- Include enough text and context that the segment makes sense without external info
- Only return segments that are COMPLETE THOUGHTS or COMPLETE SCENES, never fragments"""


def build_user_prompt(
    transcript: str, min_length: int, max_length: int, custom_prompt: str | None = None
) -> str:
    """Build the user prompt for the AI."""
    user_prompt_parts = [
        "Analyze this video transcript and identify the most engaging segments for short-form content.",
        f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
    ]

    if custom_prompt:
        user_prompt_parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}")

    user_prompt_parts.extend(
        (
            "\nFind segments that would be compelling as standalone clips for social media.",
            f"\nTranscript:\n{transcript}",
        )
    )

    return "\n".join(user_prompt_parts)


def _get_duration(segment: TranscriptSegment) -> float:
    """Calculate duration of a segment in seconds."""
    start_parts = segment.start_time.split(":")
    end_parts = segment.end_time.split(":")
    start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
    end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
    return end_seconds - start_seconds


def _analyze_response_durations(segments: list[TranscriptSegment]) -> list[float]:
    """Analyze and log statistics about response durations."""
    durations = []
    for segment in segments:
        with suppress(ValueError, IndexError):
            duration = _get_duration(segment)
            if duration > 0:
                durations.append(duration)

    if durations:
        avg_duration = sum(durations) / len(durations)
        logger.info(
            f"Groq response duration analysis: "
            f"avg={avg_duration:.2f}s, min={min(durations):.2f}s, max={max(durations):.2f}s"
        )

        if avg_duration < 5.0:
            logger.warning(
                f"WARNING: Groq response has very short segments (avg {avg_duration:.2f}s). "
                f"Model may be returning fragments instead of complete clips."
            )
    return durations


def _validate_transcript_input(transcript: str) -> None:
    """Validate transcript input before analysis.

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
        logger.error(f"Transcript too short ({len(transcript)} chars)")
        raise ValueError(
            f"Transcript too short ({len(transcript)} chars) - minimum 50 characters required"
        )


def _build_final_analysis(
    analysis: TranscriptAnalysis,
    validated_segments: list[TranscriptSegment],
    durations: list[float],
    min_length: int,
    max_length: int,
) -> TranscriptAnalysis:
    """Build the final analysis result from validated segments.

    Args:
        analysis: Original analysis from API
        validated_segments: Validated segment list
        durations: List of segment durations for error reporting
        min_length: Minimum clip length
        max_length: Maximum clip length

    Returns:
        Final TranscriptAnalysis

    Raises:
        ValueError: If no valid segments found
    """
    # Sort by relevance
    validated_segments.sort(key=lambda x: x.relevance_score, reverse=True)

    if not validated_segments:
        avg_duration_str = (
            f"{sum(durations) / len(durations):.1f}s" if durations else "N/A"
        )
        logger.error(
            "ERROR: All AI-identified segments were rejected during validation"
        )
        logger.error(
            f"Original segments from AI: {len(analysis.most_relevant_segments)}"
        )
        raise ValueError(
            f"No valid segments found. All {len(analysis.most_relevant_segments)} segments rejected "
            f"(too short or AI model fragments). Requested: {min_length}-{max_length}s. "
            f"AI returned average: {avg_duration_str}. "
            f"Recommendation: Try shorter clip durations (10-45 seconds work best for viral content)."
        )

    final_analysis = TranscriptAnalysis(
        most_relevant_segments=validated_segments,
        summary=analysis.summary,
        key_topics=analysis.key_topics,
    )

    logger.info(f"Selected {len(validated_segments)} segments for processing")
    if validated_segments:
        logger.info(f"Top segment score: {validated_segments[0].relevance_score:.2f}")

    return final_analysis


def _validate_and_adjust_segments(
    segments: list[TranscriptSegment], min_length: int, max_length: int
) -> list[TranscriptSegment]:
    """Validate, expand, or trim segments to meet constraints."""
    validated_segments = []

    for segment in segments:
        # Validate text content
        if not segment.text.strip() or len(segment.text.split()) < 3:
            logger.warning(
                f"REJECTED: Insufficient text content - '{segment.text[:50]}...' "
                f"({len(segment.text.split())} words, min 3 required)"
            )
            continue

        # Validate timestamps
        if segment.start_time == segment.end_time:
            logger.warning(
                f"REJECTED: Identical start/end times - {segment.start_time} "
                f"(duration 0s, min {min_length}s required)"
            )
            continue

        try:
            duration = _get_duration(segment)

            if duration <= 0:
                logger.warning(
                    f"REJECTED: Invalid duration - {segment.start_time} to {segment.end_time} = {duration}s "
                    f"(min {min_length}s required)"
                )
                continue
            # Handle too short
            if duration < min_length:
                # CRITICAL: Do NOT auto-expand. Auto-expansion blindly adds time to start/end,
                # which ruins hooks by picking up mid-sentence fragments from previous lines.
                # Better to have a short good clip than a long broken one.
                if duration < 5.0:
                    logger.warning(
                        f"REJECTED: Segment too short ({duration:.2f}s) and < 5.0s hard limit."
                    )
                    continue

                logger.warning(
                    f"ACCEPTED (UNDERLENGTH): Segment {segment.start_time}-{segment.end_time} "
                    f"({duration:.2f}s) is shorter than min {min_length}s. "
                    f"Keeping original to preserve hook integrity."
                )

            # Handle too long
            if duration > max_length:
                logger.warning(
                    f"Target segment too long: {segment.start_time} to {segment.end_time} = {duration:.2f}s "
                    f"(max {max_length}s allowed). Trimming to limits."
                )

                # Calculate new end time
                start_parts = segment.start_time.split(":")
                start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                new_end_seconds = start_seconds + max_length
                new_end_time = (
                    f"{int(new_end_seconds // 60):02d}:{new_end_seconds % 60:05.2f}"
                )

                logger.info(
                    f"TRIMMED: {segment.start_time}-{segment.end_time} ({duration:.2f}s) → "
                    f"{segment.start_time}-{new_end_time} ({max_length:.2f}s)"
                )

                segment.end_time = new_end_time
                segment.reasoning = (
                    f"{segment.reasoning} [Auto-trimmed from longer segment]"
                )
                duration = max_length

            validated_segments.append(segment)
            logger.info(
                f"ACCEPTED: Segment {segment.start_time}-{segment.end_time} ({duration:.2f}s, "
                f"score {segment.relevance_score:.2f}). Text: '{segment.text[:50]}...'"
            )

        except (ValueError, IndexError) as e:
            logger.warning(
                f"Skipping segment with invalid timestamp format: {segment.start_time}-{segment.end_time}: {e}"
            )
            continue

    return validated_segments


async def analyze_transcript_structured(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45,
    custom_prompt: str | None = None,
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> TranscriptAnalysis:
    """
    Analyze transcript using Groq's Structured Outputs API.

    This function uses Groq's native structured outputs feature instead of
    Pydantic AI's tool calling, which has compatibility issues with Llama 4 Scout.

    Args:
        transcript: The video transcript to analyze
        min_length: Minimum clip length in seconds
        max_length: Maximum clip length in seconds
        custom_prompt: Custom instructions for AI analysis
        model: Groq model to use (default: Llama 4 Scout)

    Returns:
        TranscriptAnalysis with validated segments

    Raises:
        ValueError: If transcript is empty or too short
        Exception: If API call fails
    """
    # Validate input
    _validate_transcript_input(transcript)

    # Initialize Groq client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")

    client = AsyncGroq(api_key=api_key)
    response_content: str = ""

    try:
        logger.info(
            f"Analyzing transcript with Groq Structured Outputs ({len(transcript)} chars)"
        )
        logger.info(f"Using model: {model}")
        logger.info(f"Clip length settings - Min: {min_length}s, Max: {max_length}s")

        user_prompt = build_user_prompt(
            transcript, min_length, max_length, custom_prompt
        )
        system_prompt = build_system_prompt(min_length, max_length)

        # Create the completion with structured outputs
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "transcript_analysis",
                    "strict": True,
                    "schema": TranscriptAnalysis.model_json_schema(),
                },
            },
            temperature=0.7,
            max_tokens=4096,
        )

        response_content = completion.choices[0].message.content or ""
        if not response_content:
            raise ValueError("Empty response from Groq API")
        logger.info(f"Received response from Groq ({len(response_content)} chars)")

        # Parse JSON response
        analysis_data = json.loads(response_content)
        analysis = TranscriptAnalysis(**analysis_data)

        logger.info(
            f"AI analysis found {len(analysis.most_relevant_segments)} segments"
        )

        # Analyze durations (diagnostic)
        durations = _analyze_response_durations(analysis.most_relevant_segments)

        # Validate and adjust segments
        validated_segments = _validate_and_adjust_segments(
            analysis.most_relevant_segments, min_length, max_length
        )

        # Build and return final analysis
        return _build_final_analysis(
            analysis, validated_segments, durations, min_length, max_length
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response content: {response_content[:500]}...")
        raise Exception(f"Invalid JSON response from Groq: {e}")
    except Exception as e:
        logger.error(f"Error in Groq structured analysis: {e}")
        raise

# end backend/src/ai_structured.py
