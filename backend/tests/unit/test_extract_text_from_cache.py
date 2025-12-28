# start backend/tests/unit/test_extract_text_from_cache.py
"""
Unit tests for extract_text_from_cache function.

These tests verify the critical fix for the "ghost words" bug where
transcripts showed words that weren't audible in the clip because they
started before the clip's start time.

Key Fix: Words are only included if word.start >= clip_start_ms
"""

import json
import pytest
from pathlib import Path
from src.video_utils import extract_text_from_cache


@pytest.fixture
def mock_transcript_cache(tmp_path) -> Path:
    """Create a mock video file with realistic transcript cache."""
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"fake video")

    # Realistic cache data simulating a conversation
    # Times in milliseconds
    cache_data = {
        "words": [
            {"text": "Hello", "start": 0, "end": 500, "confidence": 0.99},
            {"text": "everyone", "start": 500, "end": 1000, "confidence": 0.98},
            {"text": "welcome", "start": 1000, "end": 1500, "confidence": 0.99},
            {"text": "to", "start": 1500, "end": 1700, "confidence": 0.99},
            {"text": "the", "start": 1700, "end": 1900, "confidence": 0.99},
            {"text": "show", "start": 1900, "end": 2400, "confidence": 0.99},
            {"text": "today", "start": 2400, "end": 3000, "confidence": 0.98},
            {"text": "we're", "start": 3000, "end": 3300, "confidence": 0.97},
            {"text": "discussing", "start": 3300, "end": 4000, "confidence": 0.98},
            {"text": "AI", "start": 4000, "end": 4500, "confidence": 0.99},
        ],
        "text": "Hello everyone welcome to the show today we're discussing AI",
    }

    cache_path = tmp_path / "test_video.transcript_cache.json"
    cache_path.write_text(json.dumps(cache_data))

    return video_path


class TestExtractTextNoGhostWords:
    """Test that extract_text_from_cache never includes ghost words."""

    def test_clip_starting_at_1_second_excludes_hello_everyone(
        self, mock_transcript_cache
    ):
        """
        CRITICAL TEST: Clip starting at 1.0s should NOT include "Hello everyone"
        because those words start at 0ms and 500ms (before clip start).
        """
        # Clip from 1.0s to 3.0s
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=1.0, end_time_seconds=3.0
        )

        # Should start with "welcome" (starts at 1000ms = 1.0s)
        assert result is not None
        assert "Hello" not in result, "Ghost word detected: 'Hello' starts before clip"
        assert (
            "everyone" not in result
        ), "Ghost word detected: 'everyone' starts before clip"
        assert result.startswith(
            "welcome"
        ), f"Expected to start with 'welcome', got: {result}"
        assert "to the show today" in result

    def test_clip_starting_mid_word_excludes_partial_word(self, mock_transcript_cache):
        """
        Test that if clip starts at 1.2s, the word "welcome" (starts at 1.0s)
        is EXCLUDED, not partially included.
        """
        # Clip starts at 1.2s (mid-"welcome")
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=1.2, end_time_seconds=3.0
        )

        assert result is not None
        assert "welcome" not in result, "Word that starts before clip should be excluded"
        # First word should be "to" (starts at 1500ms = 1.5s)
        assert result.startswith("to")

    def test_exact_word_boundary_includes_word(self, mock_transcript_cache):
        """Test that word starting exactly at clip start IS included."""
        # "welcome" starts at exactly 1000ms = 1.0s
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=1.0, end_time_seconds=2.0
        )

        assert result is not None
        assert result.startswith("welcome")

    def test_word_starting_before_clip_is_excluded(self, mock_transcript_cache):
        """Test that words starting before clip start are excluded."""
        # Clip starts at 1.1s (1100ms), "welcome" starts at 1000ms
        # So "welcome" should be excluded, first word is "to" (starts at 1500ms)
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=1.1, end_time_seconds=2.0
        )

        assert result is not None
        assert "welcome" not in result
        assert result.startswith("to")


class TestExtractTextBoundaries:
    """Test boundary conditions."""

    def test_end_time_boundary_excludes_words_starting_at_end(
        self, mock_transcript_cache
    ):
        """Words starting at or after end_time should be excluded."""
        # Clip from 0s to 2.4s (exactly when "today" starts)
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=0.0, end_time_seconds=2.4
        )

        assert result is not None
        assert "today" not in result, "Word starting at end_time should be excluded"
        assert "show" in result

    def test_clip_shorter_than_word_duration(self, mock_transcript_cache):
        """Test clip that's shorter than a single word's duration."""
        # Clip from 0.0s to 0.3s (300ms), but "Hello" is 500ms long
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=0.0, end_time_seconds=0.3
        )

        # "Hello" starts at 0ms (within clip start), so should be included
        assert result is not None
        assert result == "Hello"

    def test_full_range_returns_all_words(self, mock_transcript_cache):
        """Test extracting entire transcript."""
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=0.0, end_time_seconds=5.0
        )

        assert result is not None
        assert (
            "Hello everyone welcome to the show today we're discussing AI" in result
        )


class TestExtractTextEdgeCases:
    """Test error handling and edge cases."""

    def test_missing_cache_file_returns_none(self, tmp_path):
        """Test that missing cache file returns None, not error."""
        video_path = tmp_path / "no_cache.mp4"
        video_path.write_bytes(b"fake")

        result = extract_text_from_cache(video_path, 0.0, 1.0)
        assert result is None

    def test_empty_word_list_returns_none(self, tmp_path):
        """Test cache with no words."""
        video_path = tmp_path / "empty.mp4"
        video_path.write_bytes(b"fake")

        cache_path = tmp_path / "empty.transcript_cache.json"
        cache_path.write_text(json.dumps({"words": [], "text": ""}))

        result = extract_text_from_cache(video_path, 0.0, 1.0)
        assert result is None

    def test_malformed_cache_json_returns_none(self, tmp_path):
        """Test that malformed JSON doesn't crash."""
        video_path = tmp_path / "malformed.mp4"
        video_path.write_bytes(b"fake")

        cache_path = tmp_path / "malformed.transcript_cache.json"
        cache_path.write_text("NOT VALID JSON {{{")

        result = extract_text_from_cache(video_path, 0.0, 1.0)
        assert result is None

    def test_time_range_with_no_matching_words(self, mock_transcript_cache):
        """Test time range where no words start."""
        # Gap between "AI" ending and next hypothetical word
        result = extract_text_from_cache(
            mock_transcript_cache, start_time_seconds=10.0, end_time_seconds=15.0
        )

        # Should return None (warning logged)
        assert result is None


# end backend/tests/unit/test_extract_text_from_cache.py
