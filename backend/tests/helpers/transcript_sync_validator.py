# start backend/tests/helpers/transcript_sync_validator.py
"""
Reusable validation helpers for transcript/audio synchronization testing.

These utilities can be imported into E2E tests to verify that generated
clips have accurate transcripts that match the audio.
"""

from pathlib import Path
from typing import dict
from src.video_utils import load_cached_transcript_data, parse_timestamp_to_seconds


def assert_no_ghost_words(
    video_path: Path,
    segment_start_seconds: float,
    segment_end_seconds: float,
    segment_text: str,
) -> None:
    """
    Assert that segment_text contains NO words from before segment_start_seconds.

    Args:
        video_path: Path to source video (must have .transcript_cache.json)
        segment_start_seconds: Clip start time in seconds
        segment_end_seconds: Clip end time in seconds
        segment_text: The transcript text to validate

    Raises:
        AssertionError: If ghost words are detected
        ValueError: If cache is missing
    """
    cache_data = load_cached_transcript_data(video_path)
    if not cache_data or "words" not in cache_data:
        raise ValueError(f"No transcript cache found for {video_path}")

    start_ms = int(segment_start_seconds * 1000)
    ghost_words = []

    # Find words in segment_text that start BEFORE segment start
    for word in cache_data["words"]:
        word_text = word.get("text", "")
        word_start = word.get("start", 0)

        # If this word is in the segment text but starts before clip...
        if word_text in segment_text and word_start < start_ms:
            ghost_words.append(
                {
                    "word": word_text,
                    "start_ms": word_start,
                    "clip_start_ms": start_ms,
                    "delta_ms": start_ms - word_start,
                }
            )

    if ghost_words:
        details = "\n".join(
            [
                f"  - '{w['word']}' starts at {w['start_ms']}ms "
                f"(clip starts at {w['clip_start_ms']}ms, "
                f"{w['delta_ms']}ms gap)"
                for w in ghost_words
            ]
        )
        raise AssertionError(
            f"Ghost words detected (words in transcript that start before clip):\n{details}"
        )


def validate_transcript_sync(video_path: Path, segments: list[dict]) -> list[str]:
    """
    Validate all segments for transcript/audio sync issues.

    Args:
        video_path: Path to source video
        segments: List of segment dicts with keys: start_time, end_time, text

    Returns:
        List of issue descriptions (empty if all valid)
    """
    issues = []

    cache_data = load_cached_transcript_data(video_path)
    if not cache_data or "words" not in cache_data:
        return ["Missing transcript cache - cannot validate"]

    for i, segment in enumerate(segments):
        try:
            start_seconds = parse_timestamp_to_seconds(segment.get("start_time", "0"))
            text = segment.get("text", "")

            # Check for ghost words
            start_ms = int(start_seconds * 1000)
            for word in cache_data["words"]:
                word_text = word.get("text", "")
                word_start = word.get("start", 0)

                if word_text in text and word_start < start_ms:
                    issues.append(
                        f"Segment {i} ({segment.get('start_time')}): "
                        f"Ghost word '{word_text}' starts at {word_start}ms "
                        f"but clip starts at {start_ms}ms"
                    )

        except Exception as e:
            issues.append(f"Segment {i}: Validation error - {e}")

    return issues


# end backend/tests/helpers/transcript_sync_validator.py
