# start backend/tests/integration/test_transcript_sync_integration.py
"""
Integration tests for transcript/audio synchronization in the video processing pipeline.

Tests the complete flow:
1. AI generates segments with approximate timestamps
2. snap_segment_to_sentence_start() adjusts timestamps
3. extract_text_from_cache() replaces AI text with verbatim text
4. Generated clips have accurate captions

This validates the fixes in video_service.py lines 310-370.
"""

import json
import pytest
from pathlib import Path
from src.video_utils import (
    extract_text_from_cache,
    snap_segment_to_sentence_start,
    parse_timestamp_to_seconds,
    format_ms_to_timestamp_precise,
)


@pytest.fixture
def realistic_transcript_cache(tmp_path) -> tuple[Path, dict]:
    """
    Create a realistic transcript cache simulating a podcast intro.
    Returns (video_path, cache_data_dict)
    """
    video_path = tmp_path / "podcast.mp4"
    video_path.write_bytes(b"fake video data")

    # Simulate a 30-second podcast intro
    cache_data = {
        "words": [
            # Sentence 1: "What's up everyone, welcome back to the show."
            {"text": "What's", "start": 0, "end": 400, "confidence": 0.99},
            {"text": "up", "start": 400, "end": 600, "confidence": 0.99},
            {"text": "everyone", "start": 600, "end": 1100, "confidence": 0.98},
            {"text": ",", "start": 1100, "end": 1150, "confidence": 0.95},
            {"text": "welcome", "start": 1150, "end": 1600, "confidence": 0.99},
            {"text": "back", "start": 1600, "end": 1900, "confidence": 0.99},
            {"text": "to", "start": 1900, "end": 2000, "confidence": 0.99},
            {"text": "the", "start": 2000, "end": 2100, "confidence": 0.99},
            {"text": "show", "start": 2100, "end": 2500, "confidence": 0.99},
            {"text": ".", "start": 2500, "end": 2550, "confidence": 0.90},
            # Sentence 2: "Today we're talking about AI."
            {"text": "Today", "start": 3000, "end": 3400, "confidence": 0.99},
            {"text": "we're", "start": 3400, "end": 3700, "confidence": 0.97},
            {"text": "talking", "start": 3700, "end": 4200, "confidence": 0.98},
            {"text": "about", "start": 4200, "end": 4500, "confidence": 0.99},
            {"text": "AI", "start": 4500, "end": 5000, "confidence": 0.99},
            {"text": ".", "start": 5000, "end": 5050, "confidence": 0.90},
            # Sentence 3: "This technology is changing everything."
            {"text": "This", "start": 5500, "end": 5800, "confidence": 0.99},
            {"text": "technology", "start": 5800, "end": 6500, "confidence": 0.98},
            {"text": "is", "start": 6500, "end": 6700, "confidence": 0.99},
            {"text": "changing", "start": 6700, "end": 7200, "confidence": 0.99},
            {"text": "everything", "start": 7200, "end": 7900, "confidence": 0.98},
            {"text": ".", "start": 7900, "end": 7950, "confidence": 0.90},
        ],
        "text": (
            "What's up everyone, welcome back to the show. "
            "Today we're talking about AI. "
            "This technology is changing everything."
        ),
    }

    cache_path = tmp_path / "podcast.transcript_cache.json"
    cache_path.write_text(json.dumps(cache_data))

    return video_path, cache_data


class TestTranscriptSyncPipeline:
    """Test end-to-end transcript synchronization."""

    def test_verbatim_text_replaces_ai_summary(self, realistic_transcript_cache):
        """
        Test that AI-generated summary text is replaced with verbatim transcript.

        This is the core fix: video_service.py line 349-356
        """
        video_path, cache_data = realistic_transcript_cache

        # Simulate AI-generated segment (paraphrased)
        ai_segment = {
            "start_time": "00:00.000",
            "end_time": "00:03.000",
            "text": "Host greets audience and introduces the show",  # AI summary
        }

        # Extract verbatim text
        verbatim_text = extract_text_from_cache(
            video_path,
            parse_timestamp_to_seconds(ai_segment["start_time"]),
            parse_timestamp_to_seconds(ai_segment["end_time"]),
        )

        assert verbatim_text is not None
        # Should be verbatim, not AI summary
        assert "What's up everyone" in verbatim_text
        assert "welcome back to the show" in verbatim_text
        assert "Host greets" not in verbatim_text

    def test_snap_segment_prevents_mid_sentence_start(self, realistic_transcript_cache):
        """
        Test snap_segment_to_sentence_start() prevents clips starting mid-sentence.

        This tests video_service.py lines 324-346 (snapping logic)
        """
        video_path, cache_data = realistic_transcript_cache

        # AI picks a start time in the middle of sentence 1 (at "welcome")
        ai_start_time = 1.15  # "welcome" starts here

        # Snap to sentence start
        snapped_start, word, reason = snap_segment_to_sentence_start(
            video_path, ai_start_time, search_window_seconds=2.0
        )

        # Should snap back to "What's" (sentence start at 0.0s)
        assert snapped_start == pytest.approx(0.0, abs=0.01)
        assert word == "What's"
        # Reason can vary but should indicate snapping occurred
        assert reason != ""

    def test_snap_segment_respects_2_second_window(self, realistic_transcript_cache):
        """
        Test that snapping only looks back 2 seconds (not forever).

        This prevents snapping to sentence starts that are too far back.
        """
        video_path, cache_data = realistic_transcript_cache

        # AI picks start time at "changing" (6.7s)
        # Previous sentence "This" starts at 5.5s (1.2s back - within window)
        # But "Today" starts at 3.0s (3.7s back - outside window)
        ai_start_time = 6.7

        snapped_start, word, reason = snap_segment_to_sentence_start(
            video_path, ai_start_time, search_window_seconds=2.0
        )

        # Should snap to "This" (5.5s), NOT "Today" (3.0s)
        assert snapped_start == pytest.approx(5.5, abs=0.01)
        assert word == "This"

    def test_full_pipeline_integration_with_simulated_ai(
        self, realistic_transcript_cache
    ):
        """
        Test complete pipeline with simulated AI to verify segment text replacement.

        This simulates the flow in video_service.py process_video_complete()
        """
        video_path, cache_data = realistic_transcript_cache

        # Mock AI response with approximate timestamps and summaries
        mock_ai_segments = [
            {
                "start_time": "00:01.200",  # Mid-sentence (should snap to 00:00.000)
                "end_time": "00:03.000",
                "text": "Welcome message to audience",  # AI summary
                "hook": "Engaging greeting",
                "reasoning": "Strong intro",
            }
        ]

        # Simulate the verbatim text replacement logic
        # (Same logic as video_service.py lines 316-369)
        for segment in mock_ai_segments:
            # Snap to sentence start
            original_start = parse_timestamp_to_seconds(segment["start_time"])
            new_start, word, reason = snap_segment_to_sentence_start(
                video_path, original_start, search_window_seconds=2.0
            )

            # Update segment if snapped
            if abs(new_start - original_start) > 0.01:
                segment["start_time"] = format_ms_to_timestamp_precise(
                    int(new_start * 1000)
                )

            # Extract verbatim text
            verbatim_text = extract_text_from_cache(
                video_path,
                parse_timestamp_to_seconds(segment["start_time"]),
                parse_timestamp_to_seconds(segment["end_time"]),
            )

            if verbatim_text:
                segment["text"] = verbatim_text

        # Assertions
        final_segment = mock_ai_segments[0]

        # Timestamp should be snapped to sentence start
        assert final_segment["start_time"] == "00:00.000"

        # Text should be verbatim, not AI summary
        assert "What's up everyone" in final_segment["text"]
        assert "Welcome message" not in final_segment["text"]

        # Original metadata should be preserved
        assert final_segment["hook"] == "Engaging greeting"
        assert final_segment["reasoning"] == "Strong intro"


class TestTranscriptSyncErrorHandling:
    """Test error cases in transcript sync pipeline."""

    def test_missing_cache_preserves_none_result(self, tmp_path):
        """If cache is missing, extract returns None (graceful degradation)."""
        video_path = tmp_path / "no_cache.mp4"
        video_path.write_bytes(b"fake")

        # Try to extract verbatim text
        verbatim_text = extract_text_from_cache(video_path, 0.0, 5.0)

        # Should return None (allowing pipeline to keep AI text)
        assert verbatim_text is None

    def test_snap_with_no_cache_returns_original_time(self, tmp_path):
        """snap_segment_to_sentence_start without cache returns original time."""
        video_path = tmp_path / "no_cache.mp4"
        video_path.write_bytes(b"fake")

        original_time = 5.5
        snapped_time, word, reason = snap_segment_to_sentence_start(
            video_path, original_time
        )

        # Should return original time unchanged
        assert snapped_time == original_time
        assert "no cache" in reason.lower() or "not available" in reason.lower()


class TestGhostWordPrevention:
    """
    Regression tests specifically for the ghost words bug.

    Ghost words: Words that appear in transcript but start BEFORE
    the clip's start time, so viewers don't actually hear them.
    """

    def test_no_ghost_words_when_clip_starts_mid_conversation(
        self, realistic_transcript_cache
    ):
        """
        Critical regression test: Starting clip at 3.0s should NOT include
        any words from sentences 1 (which ends around 2.5s).
        """
        video_path, cache_data = realistic_transcript_cache

        # Clip starting at sentence 2
        result = extract_text_from_cache(
            video_path, start_time_seconds=3.0, end_time_seconds=5.5
        )

        assert result is not None

        # Should NOT have any words from sentence 1
        assert "What's" not in result
        assert "up" not in result
        assert "everyone" not in result
        assert "welcome" not in result
        assert "back" not in result
        assert "show" not in result

        # Should have words from sentence 2
        assert "Today" in result
        assert "talking" in result
        assert "AI" in result

    def test_extracted_text_matches_only_audible_content(
        self, realistic_transcript_cache
    ):
        """
        The extracted text should contain ONLY words that are audible
        in the specified time range.
        """
        video_path, cache_data = realistic_transcript_cache

        # Extract segment from 1.5s to 3.5s
        result = extract_text_from_cache(
            video_path, start_time_seconds=1.5, end_time_seconds=3.5
        )

        assert result is not None

        # Words starting at 1.5s onwards in the fixture:
        # "back" (1600ms), "to" (1900ms), "the" (2000ms), "show" (2100ms),
        # "." (2500ms), "Today" (3000ms), "we're" (3400ms)
        words_in_result = result.split()

        # First word should be "back" (starts at 1600ms, first word >= 1500ms)
        assert words_in_result[0] == "back"

        # Should NOT include "welcome" (starts at 1150ms = 1.15s)
        assert "welcome" not in result


# end backend/tests/integration/test_transcript_sync_integration.py
