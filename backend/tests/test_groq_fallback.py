"""
Test Groq API fallback mechanism.

This test verifies that when Groq API fails, the system falls back to
Pydantic AI with the configured LLM (local or cloud).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ai import get_most_relevant_parts_by_transcript


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Fallback from Groq to Pydantic AI not yet implemented - test documents intended behavior")
async def test_groq_failure_falls_back_to_pydantic_ai():
    """
    Test that when Groq API returns 500 error, system falls back to Pydantic AI.

    NOTE: This test is marked as xfail because the fallback logic is not yet implemented.
    Currently, the code re-raises Groq exceptions instead of falling back.

    Intended behavior when implemented:
    - Primary path: Groq Structured Outputs (fails with InternalServerError)
    - Fallback path: Pydantic AI with configured LLM (succeeds)
    - Result: Video processing continues despite Groq being unavailable
    """

    # Sample transcript for testing
    test_transcript = """
    [00:00 - 00:05] Welcome to the amazing content about technology innovation
    [00:05 - 00:10] Today we're going to explore the latest developments
    [00:10 - 00:20] This breakthrough technology is changing everything we know
    [00:20 - 00:30] Let me show you how this works in practice with real examples
    [00:30 - 00:40] You can see the dramatic difference in performance and capability
    [00:40 - 00:50] This is absolutely revolutionary for the entire industry
    [00:50 - 01:00] We predict this will transform how people work and innovate
    """

    # Mock the Groq API to fail (simulating service down)
    with patch('src.ai_structured.AsyncGroq') as mock_groq_class:
        mock_groq_instance = AsyncMock()
        mock_groq_class.return_value = mock_groq_instance

        # Make the Groq call fail with generic exception (simulates any Groq API error)
        mock_groq_instance.chat.completions.create.side_effect = Exception(
            "500 Internal Server Error from Groq API"
        )

        # Mock Pydantic AI agent to succeed
        with patch('src.ai._get_transcript_agent') as mock_get_agent:
            from src.ai import TranscriptSegment, TranscriptAnalysis

            mock_agent = AsyncMock()
            mock_result = MagicMock()

            # Create real TranscriptSegment objects that pass validation
            segment1 = TranscriptSegment(
                start_time="00:10",
                end_time="00:25",
                text="This breakthrough technology is changing everything we know about how we work and innovate",
                relevance_score=0.95,
                reasoning="Strong hook with valuable content"
            )

            segment2 = TranscriptSegment(
                start_time="00:40",
                end_time="00:55",
                text="This is absolutely revolutionary for the entire industry and will transform everything we do",
                relevance_score=0.85,
                reasoning="Emotional impact with high engagement potential"
            )

            analysis = TranscriptAnalysis(
                most_relevant_segments=[segment1, segment2],
                summary="Revolutionary technology breakthrough",
                key_topics=["Technology", "Innovation", "Breakthrough"]
            )

            mock_result.data = analysis
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_get_agent.return_value = mock_agent

            # Ensure the config indicates we're using Groq
            with patch('src.ai.config') as mock_config:
                mock_config.local_llm_enabled = False
                mock_config.llm = "groq:meta-llama/llama-4-scout-17b-16e-instruct"

                # Call the function - it should fall back to Pydantic AI and succeed
                result = await get_most_relevant_parts_by_transcript(test_transcript)

                # Verify result
                assert result is not None
                assert len(result.most_relevant_segments) == 2
                assert result.most_relevant_segments[0].relevance_score == 0.95
                assert "revolutionary" in result.summary.lower()

                # Verify fallback was used
                mock_agent.run.assert_called_once()
                print("✅ Groq fallback test passed: System fell back to Pydantic AI successfully")


@pytest.mark.asyncio
async def test_groq_success_uses_structured_outputs():
    """
    Test that Groq API success path works when service is available.

    This ensures we don't break the normal Groq flow when it's working.
    """
    import json

    test_transcript = """
    [00:00 - 00:10] Introduction to amazing new feature
    [00:10 - 00:25] Detailed explanation with examples
    [00:25 - 00:40] Real world impact and benefits
    """

    with patch('src.ai_structured.AsyncGroq') as mock_groq_class:
        mock_groq_instance = AsyncMock()
        mock_groq_class.return_value = mock_groq_instance

        # Create a successful Groq response
        response_data = {
            "most_relevant_segments": [
                {
                    "start_time": "00:00",
                    "end_time": "00:15",
                    "text": "Introduction to amazing new feature that changes everything",
                    "relevance_score": 0.9,
                    "reasoning": "Strong opening hook"
                },
                {
                    "start_time": "00:20",
                    "end_time": "00:40",
                    "text": "Real world impact and benefits demonstrated clearly",
                    "relevance_score": 0.85,
                    "reasoning": "Valuable content demonstration"
                }
            ],
            "summary": "Amazing new feature overview",
            "key_topics": ["Feature", "Benefits", "Innovation"]
        }

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps(response_data)
        mock_groq_instance.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch('src.ai.config') as mock_config:
            mock_config.local_llm_enabled = False
            mock_config.llm = "groq:meta-llama/llama-4-scout-17b-16e-instruct"

            # Call the function - should use Groq directly
            result = await get_most_relevant_parts_by_transcript(test_transcript)

            # Verify Groq was called
            mock_groq_instance.chat.completions.create.assert_called_once()

            # Verify result
            assert result is not None
            assert len(result.most_relevant_segments) == 2
            assert "amazing" in result.summary.lower()
            print("✅ Groq success test passed: Structured Outputs API works correctly")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])
