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


# System prompt for Groq API
SYSTEM_PROMPT = """You are an expert at analyzing video transcripts to find the most engaging segments for short-form content creation.

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
- Segments MUST be between 10-45 seconds for optimal engagement
- CRITICAL: start_time MUST be different from end_time (minimum 10 seconds apart)
- Focus on natural content boundaries rather than arbitrary time limits
- Include enough context for the segment to be understandable

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{
  "most_relevant_segments": [
    {
      "start_time": "MM:SS",
      "end_time": "MM:SS",
      "text": "segment text",
      "relevance_score": 0.85,
      "reasoning": "why this is relevant"
    }
  ],
  "summary": "brief summary",
  "key_topics": ["topic1", "topic2"]
}

Find 3-7 compelling segments that would work well as standalone clips. Quality over quantity - choose segments that would genuinely engage viewers and have proper time ranges."""


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

        # Create the completion with structured outputs
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
        response_content = completion.choices[0].message.content
        logger.info(f"Received response from Groq ({len(response_content)} chars)")

        # Parse JSON response
        analysis_data = json.loads(response_content)
        analysis = TranscriptAnalysis(**analysis_data)

        logger.info(
            f"AI analysis found {len(analysis.most_relevant_segments)} segments"
        )

        # Validate segments
        validated_segments = []
        for segment in analysis.most_relevant_segments:
            # Validate text content
            if not segment.text.strip() or len(segment.text.split()) < 3:
                logger.warning(
                    f"Skipping segment with insufficient content: '{segment.text[:50]}...'"
                )
                continue

            # Validate timestamps
            if segment.start_time == segment.end_time:
                logger.warning(
                    f"Skipping segment with identical start/end times: {segment.start_time}"
                )
                continue

            # Parse timestamps to validate duration
            try:
                start_parts = segment.start_time.split(":")
                end_parts = segment.end_time.split(":")

                start_seconds = int(start_parts[0]) * 60 + float(start_parts[1])
                end_seconds = int(end_parts[0]) * 60 + float(end_parts[1])

                duration = end_seconds - start_seconds

                if duration <= 0:
                    logger.warning(
                        f"Skipping segment with invalid duration: {segment.start_time} to {segment.end_time} = {duration}s"
                    )
                    continue

                if duration < 5:
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

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response content: {response_content[:500]}...")
        raise Exception(f"Invalid JSON response from Groq: {e}")
    except Exception as e:
        logger.error(f"Error in Groq structured analysis: {e}")
        raise
