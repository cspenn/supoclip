"""
AI analysis using Groq's Structured Outputs API (for Llama 4 Scout compatibility).

This bypasses Pydantic AI's tool calling mechanism which has compatibility issues
with Llama 4 Scout, and instead uses Groq's native Structured Outputs feature.
"""

import logging
import json
import os
from typing import List
from groq import AsyncGroq
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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

DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: {min_length} seconds per segment (DO NOT return segments shorter than {min_length} seconds)
- MAXIMUM DURATION: {max_length} seconds per segment (DO NOT return segments longer than {max_length} seconds)
- Duration calculation: end_time - start_time MUST be >= {min_length} seconds AND <= {max_length} seconds
- NEVER return ultra-short clips (0.56s, 1.36s, 2.5s are INVALID)
- If a segment is less than {min_length} seconds, DO NOT include it in your response
- If a segment is more than {max_length} seconds, DO NOT include it in your response
- Return COMPLETE CLIPS, not word fragments or sentence fragments

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: {min_length} seconds (end_time - start_time >= {min_length} seconds)
- MAXIMUM segment duration: {max_length} seconds (end_time - start_time <= {max_length} seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- VERIFY DURATION BEFORE RETURNING: Calculate (end_time - start_time) and ensure it's between {min_length} and {max_length} seconds
- Example CORRECT (if min={min_length}, max={max_length}): start_time: "02:25", end_time: "02:35" (10 second duration)
- Example INCORRECT: start_time: "02:25", end_time: "02:26" (1 second - TOO SHORT)
- Example INCORRECT: start_time: "02:25", end_time: "02:25" (0 seconds - INVALID)

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{{
  "most_relevant_segments": [
    {{
      "start_time": "MM:SS",
      "end_time": "MM:SS",
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
    # Guard against empty transcripts
    if not transcript or len(transcript.strip()) == 0:
        logger.error("Cannot analyze empty transcript")
        raise ValueError(
            "Cannot analyze empty transcript - transcription may have failed"
        )

    if len(transcript.strip()) < 50:
        logger.error(f"Transcript too short ({len(transcript)} chars)")
        raise ValueError(
            f"Transcript too short ({len(transcript)} chars) - minimum 50 characters required"
        )

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
        if custom_prompt:
            logger.info(f"Using custom AI prompt: {custom_prompt[:100]}...")

        # Build the dynamic user prompt
        user_prompt_parts = [
            "Analyze this video transcript and identify the most engaging segments for short-form content.",
            f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
        ]

        if custom_prompt:
            user_prompt_parts.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}")

        user_prompt_parts.append(
            "\nFind segments that would be compelling as standalone clips for social media."
        )
        user_prompt_parts.append(f"\nTranscript:\n{transcript}")

        user_prompt = "\n".join(user_prompt_parts)

        # Build dynamic system prompt with user's clip length parameters
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

        # Extract and parse the response
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

        # Fix 5: Add Groq response validation for duration warnings
        # Check if segments are statistically too short (diagnostic for Groq issues)
        if analysis.most_relevant_segments:
            durations = []
            for segment in analysis.most_relevant_segments:
                try:
                    start_parts = segment.start_time.split(":")
                    end_parts = segment.end_time.split(":")
                    start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                    end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])
                    duration = end_seconds - start_seconds
                    if duration > 0:
                        durations.append(duration)
                except (ValueError, IndexError):
                    pass

            if durations:
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                logger.info(
                    f"Groq response duration analysis: "
                    f"avg={avg_duration:.2f}s, min={min_duration:.2f}s, max={max_duration:.2f}s"
                )

                # Warning if average is suspiciously short (< 5 seconds)
                if avg_duration < 5.0:
                    logger.warning(
                        f"WARNING: Groq response has very short segments (avg {avg_duration:.2f}s). "
                        f"Model may be returning fragments instead of complete clips."
                    )

        # Validate segments
        validated_segments = []
        for segment in analysis.most_relevant_segments:
            # Validate text content (Fix 2: Enhanced diagnostic logging)
            if not segment.text.strip() or len(segment.text.split()) < 3:
                logger.warning(
                    f"REJECTED: Insufficient text content - '{segment.text[:50]}...' "
                    f"({len(segment.text.split())} words, min 3 required)"
                )
                continue

            # Validate timestamps (using user-configured min_length)
            if segment.start_time == segment.end_time:
                logger.warning(
                    f"REJECTED: Identical start/end times - {segment.start_time} "
                    f"(duration 0s, min {min_length}s required)"
                )
                continue

            # Parse timestamps to validate duration (Fix 2: Enhanced diagnostic logging)
            try:
                start_parts = segment.start_time.split(":")
                end_parts = segment.end_time.split(":")

                start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])

                duration = end_seconds - start_seconds

                if duration <= 0:
                    logger.warning(
                        f"REJECTED: Invalid duration - {segment.start_time} to {segment.end_time} = {duration}s "
                        f"(min {min_length}s required)"
                    )
                    continue

                if duration < min_length:
                    logger.warning(
                        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
                        f"(min {min_length}s required). Text: '{segment.text[:40]}...'"
                    )
                    continue

                if duration > max_length:
                    logger.warning(
                        f"REJECTED: Too long - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
                        f"(max {max_length}s allowed). Text: '{segment.text[:40]}...'"
                    )
                    continue

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

        # Sort by relevance
        validated_segments.sort(key=lambda x: x.relevance_score, reverse=True)

        # CRITICAL: Raise error if no segments passed validation (Fix 1)
        # This prevents silent failures where task completes with 0 clips
        if not validated_segments:
            # Calculate average duration for diagnostics
            avg_duration_str = "N/A"
            if durations:
                avg_duration_str = f"{sum(durations)/len(durations):.1f}s"

            logger.error(
                "ERROR: All AI-identified segments were rejected during validation"
            )
            logger.error(
                f"Original segments from AI: {len(analysis.most_relevant_segments)}"
            )
            logger.error(
                "Possible causes: Groq returned ultra-short segments, "
                "invalid timestamps, or insufficient content"
            )
            raise ValueError(
                f"No valid segments found. All {len(analysis.most_relevant_segments)} segments rejected. "
                f"Requested: {min_length}-{max_length}s. AI returned average: {avg_duration_str}. "
                f"Recommendation: Try shorter clip durations (10-45 seconds work best for viral content)."
            )

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

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response content: {response_content[:500]}...")
        raise Exception(f"Invalid JSON response from Groq: {e}")
    except Exception as e:
        logger.error(f"Error in Groq structured analysis: {e}")
        raise
