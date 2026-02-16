# start backend/src/transcript.py
"""
Transcript handling: transcription, caching, formatting, and timestamp parsing.
"""

from pathlib import Path
from typing import Any
import logging
import json

from .config import Config
from .transcription_mlx import transcribe_video_mlx

logger = logging.getLogger(__name__)
config = Config()


def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds to MM:SS format.

    Args:
        ms: Time in milliseconds

    Returns:
        Formatted string in MM:SS format
    """
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def format_ms_to_timestamp_precise(ms: int) -> str:
    """Format milliseconds to MM:SS.mmm format with millisecond precision.

    Args:
        ms: Time in milliseconds

    Returns:
        Formatted string in MM:SS.mmm format
    """
    total_seconds = ms / 1000.0
    minutes = int(total_seconds) // 60
    seconds = int(total_seconds) % 60
    milliseconds = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class TranscriptLineBreaker:
    """Determine when to break lines in transcripts."""

    MAX_WORDS_PER_LINE = 20
    BREAK_PUNCTUATION = {".", "!", "?"}

    @staticmethod
    def should_break_line(word_text: str, word_count: int) -> bool:
        """Determine if line should break at this word.

        Args:
            word_text: Text of current word
            word_count: Number of words in current line

        Returns:
            True if line should break, False otherwise
        """
        # Always break on strong punctuation (sentence boundaries)
        # Fix: strip whitespace to handle tokens like "word. "
        clean_text = word_text.strip()
        if clean_text and any(
            clean_text.endswith(punct)
            for punct in TranscriptLineBreaker.BREAK_PUNCTUATION
        ):
            return True

        # Break on commas only if line is getting long to avoid chopping phrases
        if clean_text and clean_text.endswith(",") and word_count > 15:
            return True

        # Hard limit to preventing extremely long lines
        if word_count >= TranscriptLineBreaker.MAX_WORDS_PER_LINE:
            return True

        return False


class TranscriptLineFormatter:
    """Format transcript lines with timing information."""

    def __init__(self):
        """Initialize formatter with empty state."""
        self.lines: list[str] = []
        self.current_line: list[tuple[str, int, int]] = []
        self.current_start: int | None = None

    def add_word(self, word_data: dict[str, Any]) -> None:
        """Add word to current line.

        Args:
            word_data: Dictionary with 'text', 'start', 'end' keys
        """
        word_text = word_data.get("text", "")
        start_ms = word_data.get("start", 0)
        end_ms = word_data.get("end", 0)

        if not word_text:
            return

        if self.current_start is None:
            self.current_start = start_ms

        self.current_line.append((word_text, start_ms, end_ms))

    def finalize_current_line(self) -> None:
        """Format and append current line to output."""
        if not self.current_line or self.current_start is None:
            return

        start_time = format_ms_to_timestamp_precise(self.current_start)
        end_time = format_ms_to_timestamp_precise(self.current_line[-1][2])
        line_text = " ".join(word[0] for word in self.current_line)
        formatted = f"[{start_time} - {end_time}] {line_text}"
        self.lines.append(formatted)

        self.current_line = []
        self.current_start = None

    def get_formatted_output(self) -> str:
        """Return all formatted lines joined by newlines.

        Returns:
            Formatted transcript string
        """
        return "\n".join(self.lines)


def format_transcript_for_ai(transcript_data: dict[str, Any]) -> str:
    """Format transcript with SRT-style precise timing for AI analysis.

    Each line shows exact word timing for AI to select precise clip boundaries.
    Format: [MM:SS.mmm - MM:SS.mmm] word

    Args:
        transcript_data: Dictionary with 'words' array containing word objects
            with 'text', 'start', 'end' keys

    Returns:
        Formatted string with word-level timestamps for AI analysis
    """
    if not transcript_data or "words" not in transcript_data:
        return ""

    words = transcript_data["words"]
    if not words:
        return ""

    formatter = TranscriptLineFormatter()
    breaker = TranscriptLineBreaker()

    for word_data in words:
        word_text = word_data.get("text", "")
        if not word_text:
            continue

        formatter.add_word(word_data)

        if breaker.should_break_line(word_text, len(formatter.current_line)):
            formatter.finalize_current_line()

    # Handle remaining words
    formatter.finalize_current_line()

    return formatter.get_formatted_output()


def get_video_transcript(video_path: Path) -> str:
    """Get transcript using parakeet-mlx (offline, Apple Silicon optimized).

    Uses parakeet-mlx for local, offline transcription.
    Formats transcript with precise word-level timestamps (SRT-style) for AI analysis.

    Args:
        video_path: Path to the video file

    Returns:
        Formatted transcript string with word-level timestamps

    Raises:
        Exception: If transcription fails
    """
    logger.info(f"Getting transcript for: {video_path}")

    try:
        # Use parakeet-mlx for local transcription
        logger.info("Starting parakeet-mlx transcription (offline)")
        result = transcribe_video_mlx(video_path, model_id=config.parakeet_model)

        # Format transcript with precise word-level timing for AI analysis
        if result.get("words"):
            words = result["words"]
            logger.info(f"Processing {len(words)} words with precise timing")

            # Use SRT-style format with millisecond precision for AI analysis
            result_text = format_transcript_for_ai(result)
            logger.info(f"Transcript formatted with SRT: {len(result_text)} chars")
            return result_text
        else:
            logger.error("No words found in transcription result")
            return ""

    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        raise


def cache_transcript_data(video_path: Path, transcript) -> None:
    """Cache transcript data for subtitle generation.

    Args:
        video_path: Path to the video file (cache stored alongside)
        transcript: Transcript object with 'words' and 'text' attributes
    """
    cache_path = video_path.with_suffix(".transcript_cache.json")

    # Store word-level data
    words_data = []
    if transcript.words:
        for word in transcript.words:
            words_data.append(
                {
                    "text": word.text,
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.confidence
                    if hasattr(word, "confidence")
                    else 1.0,
                }
            )

    cache_data = {"words": words_data, "text": transcript.text}

    with cache_path.open("w") as f:
        json.dump(cache_data, f)

    logger.info(f"Cached {len(words_data)} words to {cache_path}")


def load_cached_transcript_data(video_path: Path) -> dict | None:
    """Load cached transcript data.

    Args:
        video_path: Path to the video file

    Returns:
        Cached transcript data dict, or None if not available
    """
    cache_path = video_path.with_suffix(".transcript_cache.json")

    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load transcript cache: {e}")
        return None


def extract_text_from_cache(
    video_path: Path, start_time_seconds: float, end_time_seconds: float
) -> str | None:
    """Extract verbatim text from transcript cache for a given time range.

    This ensures captions display the exact words spoken in the video,
    not the AI's summary or paraphrase.

    Args:
        video_path: Path to the video file (cache file shares the same stem)
        start_time_seconds: Start time in seconds
        end_time_seconds: End time in seconds

    Returns:
        Verbatim text from transcript, or None if cache unavailable
    """
    transcript_data = load_cached_transcript_data(video_path)
    if not transcript_data or "words" not in transcript_data:
        logger.warning(f"No transcript cache available for {video_path}")
        return None

    start_ms = int(start_time_seconds * 1000)
    end_ms = int(end_time_seconds * 1000)

    words_in_range = []
    for word in transcript_data["words"]:
        word_start = word.get("start", 0)
        word_text = word.get("text", "")

        # Include word ONLY if it STARTS at or after clip start time
        # This prevents "ghost words" where the transcript shows words
        # that the viewer doesn't hear (because they start before the clip)
        if word_start >= start_ms and word_start < end_ms:
            words_in_range.append(word_text)

    if words_in_range:
        extracted_text = " ".join(words_in_range)
        logger.info(
            f"Extracted {len(words_in_range)} words from cache for {start_time_seconds:.2f}s-{end_time_seconds:.2f}s"
        )
        return extracted_text

    logger.warning(
        f"No words found in cache for time range {start_time_seconds:.2f}s-{end_time_seconds:.2f}s"
    )
    return None


def parse_timestamp_to_seconds(timestamp_str: str) -> float:
    """Parse timestamp string to seconds.

    Supports formats: MM:SS, MM:SS.mmm, HH:MM:SS, HH:MM:SS.mmm, or plain seconds.

    Args:
        timestamp_str: Timestamp string to parse

    Returns:
        Time in seconds as float

    Raises:
        ValueError: If timestamp cannot be parsed
    """
    try:
        timestamp_str = timestamp_str.strip()
        logger.info(f"Parsing timestamp: '{timestamp_str}'")  # Debug logging

        if ":" in timestamp_str:
            parts = timestamp_str.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = float(parts[1])
                result = minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result
            elif len(parts) == 3:  # HH:MM:SS format
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                result = hours * 3600 + minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result

        # Try parsing as pure seconds
        result = float(timestamp_str)
        logger.info(f"Parsed '{timestamp_str}' as seconds -> {result}s")
        return result

    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse timestamp '{timestamp_str}': {e}") from e


def _find_closest_word_index(words: list[dict], target_ms: int) -> int:
    """Find the index of the word closest to the target timestamp.

    Args:
        words: List of word dictionaries with 'start' timestamps
        target_ms: Target timestamp in milliseconds

    Returns:
        Index of closest word, or -1 if no words found
    """
    closest_idx = -1
    min_diff = float("inf")

    for i, word in enumerate(words):
        word_start = word.get("start", 0)
        diff = abs(word_start - target_ms)
        if diff < min_diff:
            min_diff = diff
            closest_idx = i

    return closest_idx


def _is_sentence_start_word(words: list[dict], index: int) -> bool:
    """Check if the word at the given index is a valid sentence start.

    A word is a sentence start if:
    1. It's the first word (index 0), OR
    2. It starts with an uppercase letter AND the previous word ends with [.!?]

    Args:
        words: List of word dictionaries
        index: Index of the word to check

    Returns:
        True if the word is a valid sentence start
    """
    if index == 0:
        return True

    word_text = words[index].get("text", "").strip()
    if not word_text or not word_text[0].isupper():
        return False

    prev_text = words[index - 1].get("text", "").strip()
    return bool(prev_text and prev_text[-1] in (".", "!", "?"))


def _find_sentence_start_backwards(
    words: list[dict], start_idx: int, target_ms: int, window_ms: int
) -> int:
    """Search backwards from start_idx to find a sentence start within the window.

    Args:
        words: List of word dictionaries
        start_idx: Index to start searching from
        target_ms: Original target timestamp in milliseconds
        window_ms: Maximum window to search backwards in milliseconds

    Returns:
        Index of the sentence start word, or -1 if none found
    """
    for i in range(start_idx, -1, -1):
        curr_start = words[i].get("start", 0)

        # Stop if we've gone too far back from the target start time
        if (target_ms - curr_start) > window_ms:
            break

        # Skip if we've gone forward significantly (edge case)
        if (curr_start - target_ms) > 2000:
            continue

        if _is_sentence_start_word(words, i):
            return i

    return -1


def snap_segment_to_sentence_start(
    video_path: Path, start_time_seconds: float, search_window_seconds: float = 2.0
) -> tuple[float, str, str]:
    """Find the nearest valid sentence start to the given timestamp.

    Strategies:
    1. Find the word corresponding to the start time.
    2. Search backwards (up to search_window_seconds) for a 'Sentence Starter'.
       - A word that starts with an Uppercase letter AND matches strict criteria.
       - Criteria: Previous word ends with [.!?] OR it's the very first word.

    Args:
        video_path: Path to the video file
        start_time_seconds: Start time in seconds
        search_window_seconds: Maximum backward search window in seconds

    Returns:
        Tuple of (new_start_seconds, matched_word_text, conversion_reason).
        If no better start found, returns original start time.
    """
    transcript_data = load_cached_transcript_data(video_path)
    if not transcript_data or "words" not in transcript_data:
        return start_time_seconds, "", "No cache available"

    words = transcript_data["words"]
    start_ms = int(start_time_seconds * 1000)
    window_ms = int(search_window_seconds * 1000)

    # Find the word index closest to start_time
    closest_idx = _find_closest_word_index(words, start_ms)
    if closest_idx == -1:
        return start_time_seconds, "", "No words found"

    # Search backwards for sentence start within the window
    best_start_idx = _find_sentence_start_backwards(
        words, closest_idx, start_ms, window_ms
    )

    if best_start_idx != -1:
        new_word = words[best_start_idx]
        new_start_ms = new_word.get("start", 0)
        new_start_seconds = new_start_ms / 1000.0
        return (
            new_start_seconds,
            new_word.get("text", ""),
            f"Snapped to '{new_word.get('text', '')}'",
        )

    return start_time_seconds, "", "No better start found"


# end backend/src/transcript.py
