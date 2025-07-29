"""
AI-related functions.
"""

from pathlib import Path
from typing import List, Dict, Any
import asyncio
import logging

from pydantic_ai import Agent
from pydantic import BaseModel

from .config import Config

logger = logging.getLogger(__name__)

config = Config()

class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript."""
    start_time: str
    end_time: str
    text: str
    relevance_score: float
    reasoning: str

class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments."""
    most_relevant_segments: List[TranscriptSegment]
    summary: str
    key_topics: List[str]

# Create the agent with proper system prompt
transcript_agent = Agent(
    model=config.llm,
    result_type=TranscriptAnalysis,
    system_prompt="""You are an expert at analyzing video transcripts to find the most engaging and relevant segments for creating short clips.

Your task is to:
1. Identify the most interesting, engaging, or valuable segments from the transcript
2. Focus on segments with strong hooks, valuable insights, surprising information, or emotional moments
3. Consider segments that would work well as standalone short-form content
4. Provide timestamps and reasoning for each selection
5. Rate each segment's relevance (0.0-1.0 scale)

Return segments that would make compelling short clips for social media or highlights."""
)

async def get_most_relevant_parts_by_transcript(transcript: str) -> TranscriptAnalysis:
    """Get the most relevant parts of a transcript for creating clips."""
    logger.info(f"🤖 Starting AI analysis of transcript (length: {len(transcript)} chars)")
    logger.info(f"📝 First 200 chars of transcript: {transcript[:200]}...")

    try:
        logger.info("🔮 Calling AI agent for transcript analysis")
        result = await transcript_agent.run(
            f"Analyze this transcript and find the most relevant segments for creating engaging short clips:\n\n{transcript}"
        )
        logger.info(f"✅ AI analysis successful - result type: {type(result.data)}")
        logger.info(f"📊 Found {len(result.data.most_relevant_segments)} segments")

        if result.data.most_relevant_segments:
            logger.info(f"🎯 Top segment score: {result.data.most_relevant_segments[0].relevance_score}")
            logger.info(f"📝 Top segment text: {result.data.most_relevant_segments[0].text[:100]}...")
        else:
            logger.warning("⚠️ No relevant segments found by AI")

        return result.data
    except Exception as e:
        logger.error(f"❌ Error in AI analysis: {str(e)}")
        logger.error(f"📊 Exception type: {type(e)}")
        # Fallback response in case of error
        return TranscriptAnalysis(
            most_relevant_segments=[],
            summary=f"Error analyzing transcript: {str(e)}",
            key_topics=[]
        )

def get_most_relevant_parts_sync(transcript: str) -> TranscriptAnalysis:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_most_relevant_parts_by_transcript(transcript))
