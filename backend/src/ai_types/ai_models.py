"""Shared AI model definitions for transcript analysis.

These models are used by both ai.py (Pydantic AI/Tool Calling) and
ai_structured.py (Groq Structured Outputs) to ensure consistency.
"""

from typing import List

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing."""

    model_config = {"extra": "forbid"}

    start_time: str = Field(
        description="Start timestamp in MM:SS.mmm format (e.g., 02:35.450)"
    )
    end_time: str = Field(
        description="End timestamp in MM:SS.mmm format (e.g., 02:45.820)"
    )
    text: str = Field(
        description="VERBATIM transcript text for this segment - copy exactly from transcript, do not summarize"
    )
    relevance_score: float = Field(
        description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    reasoning: str = Field(description="Explanation for why this segment is relevant")


class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments."""

    model_config = {"extra": "forbid"}

    most_relevant_segments: List[TranscriptSegment]
    summary: str = Field(description="Brief summary of the video content")
    key_topics: List[str] = Field(description="List of main topics discussed")
