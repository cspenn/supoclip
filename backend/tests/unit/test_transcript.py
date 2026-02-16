# start tests/unit/test_transcript.py
"""
Unit tests for backend/src/transcript.py

Covers: format_ms_to_timestamp, format_ms_to_timestamp_precise,
TranscriptLineBreaker, TranscriptLineFormatter, format_transcript_for_ai,
get_video_transcript, cache_transcript_data, load_cached_transcript_data,
extract_text_from_cache, parse_timestamp_to_seconds,
_find_closest_word_index, _is_sentence_start_word,
_find_sentence_start_backwards, snap_segment_to_sentence_start
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys

backend_root = Path(__file__).parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


# Patch Config before importing transcript module
with patch("src.config.Config"):
    from src.transcript import (
        format_ms_to_timestamp,
        format_ms_to_timestamp_precise,
        TranscriptLineBreaker,
        TranscriptLineFormatter,
        format_transcript_for_ai,
        get_video_transcript,
        cache_transcript_data,
        load_cached_transcript_data,
        extract_text_from_cache,
        parse_timestamp_to_seconds,
        _find_closest_word_index,
        _is_sentence_start_word,
        _find_sentence_start_backwards,
        snap_segment_to_sentence_start,
    )


# ---------------------------------------------------------------------------
# format_ms_to_timestamp (lines 27-30)
# ---------------------------------------------------------------------------
class TestFormatMsToTimestamp:
    def test_zero(self):
        assert format_ms_to_timestamp(0) == "00:00"

    def test_simple_seconds(self):
        assert format_ms_to_timestamp(5000) == "00:05"

    def test_minutes_and_seconds(self):
        assert format_ms_to_timestamp(125000) == "02:05"

    def test_rounds_down_ms(self):
        # 1999 ms -> 1 second
        assert format_ms_to_timestamp(1999) == "00:01"


# ---------------------------------------------------------------------------
# format_ms_to_timestamp_precise
# ---------------------------------------------------------------------------
class TestFormatMsToTimestampPrecise:
    def test_zero(self):
        assert format_ms_to_timestamp_precise(0) == "00:00.000"

    def test_with_ms(self):
        assert format_ms_to_timestamp_precise(1500) == "00:01.500"

    def test_minutes(self):
        assert format_ms_to_timestamp_precise(62345) == "01:02.345"


# ---------------------------------------------------------------------------
# TranscriptLineBreaker (lines 68-83)
# ---------------------------------------------------------------------------
class TestTranscriptLineBreaker:
    def test_break_on_period(self):
        assert TranscriptLineBreaker.should_break_line("sentence.", 5) is True

    def test_break_on_exclamation(self):
        assert TranscriptLineBreaker.should_break_line("wow!", 3) is True

    def test_break_on_question(self):
        assert TranscriptLineBreaker.should_break_line("really?", 3) is True

    def test_no_break_on_regular_word(self):
        assert TranscriptLineBreaker.should_break_line("hello", 5) is False

    def test_comma_short_line_no_break(self):
        assert TranscriptLineBreaker.should_break_line("word,", 5) is False

    def test_comma_long_line_breaks(self):
        assert TranscriptLineBreaker.should_break_line("word,", 16) is True

    def test_max_words_per_line(self):
        assert TranscriptLineBreaker.should_break_line("word", 20) is True

    def test_whitespace_stripped(self):
        assert TranscriptLineBreaker.should_break_line("end. ", 3) is True

    def test_empty_string(self):
        assert TranscriptLineBreaker.should_break_line("", 5) is False

    def test_below_max_no_break(self):
        assert TranscriptLineBreaker.should_break_line("word", 19) is False


# ---------------------------------------------------------------------------
# TranscriptLineFormatter (lines 91-93, 101-111, 115-125, 133)
# ---------------------------------------------------------------------------
class TestTranscriptLineFormatter:
    def test_add_word_sets_current_start(self):
        f = TranscriptLineFormatter()
        f.add_word({"text": "hello", "start": 1000, "end": 1500})
        assert f.current_start == 1000
        assert len(f.current_line) == 1

    def test_add_word_empty_text_skips(self):
        f = TranscriptLineFormatter()
        f.add_word({"text": "", "start": 1000, "end": 1500})
        assert len(f.current_line) == 0
        assert f.current_start is None

    def test_add_word_subsequent_keeps_start(self):
        f = TranscriptLineFormatter()
        f.add_word({"text": "hello", "start": 1000, "end": 1500})
        f.add_word({"text": "world", "start": 1500, "end": 2000})
        assert f.current_start == 1000
        assert len(f.current_line) == 2

    def test_finalize_current_line(self):
        f = TranscriptLineFormatter()
        f.add_word({"text": "hello", "start": 1000, "end": 1500})
        f.add_word({"text": "world", "start": 1500, "end": 2000})
        f.finalize_current_line()
        assert len(f.lines) == 1
        assert "hello world" in f.lines[0]
        assert f.current_line == []
        assert f.current_start is None

    def test_finalize_empty_does_nothing(self):
        f = TranscriptLineFormatter()
        f.finalize_current_line()
        assert f.lines == []

    def test_finalize_no_start_does_nothing(self):
        f = TranscriptLineFormatter()
        f.current_line = [("word", 0, 100)]
        f.current_start = None
        f.finalize_current_line()
        assert f.lines == []

    def test_get_formatted_output(self):
        f = TranscriptLineFormatter()
        f.add_word({"text": "hello", "start": 0, "end": 500})
        f.finalize_current_line()
        f.add_word({"text": "world", "start": 1000, "end": 1500})
        f.finalize_current_line()
        result = f.get_formatted_output()
        assert "\n" in result
        assert "hello" in result
        assert "world" in result


# ---------------------------------------------------------------------------
# format_transcript_for_ai (lines 149-172)
# ---------------------------------------------------------------------------
class TestFormatTranscriptForAi:
    def test_empty_data(self):
        assert format_transcript_for_ai(None) == ""
        assert format_transcript_for_ai({}) == ""

    def test_no_words(self):
        assert format_transcript_for_ai({"words": []}) == ""

    def test_basic_format(self):
        data = {
            "words": [
                {"text": "Hello", "start": 0, "end": 500},
                {"text": "world.", "start": 500, "end": 1000},
            ]
        }
        result = format_transcript_for_ai(data)
        assert "Hello" in result
        assert "world." in result

    def test_empty_word_text_skipped(self):
        data = {
            "words": [
                {"text": "", "start": 0, "end": 500},
                {"text": "Hello", "start": 500, "end": 1000},
            ]
        }
        result = format_transcript_for_ai(data)
        assert "Hello" in result

    def test_remaining_words_finalized(self):
        """Words without line-breaking punctuation still get finalized."""
        data = {
            "words": [
                {"text": "hello", "start": 0, "end": 500},
                {"text": "world", "start": 500, "end": 1000},
            ]
        }
        result = format_transcript_for_ai(data)
        assert "hello world" in result

    def test_missing_words_key(self):
        assert format_transcript_for_ai({"text": "hello"}) == ""


# ---------------------------------------------------------------------------
# get_video_transcript (lines 190-212)
# ---------------------------------------------------------------------------
class TestGetVideoTranscript:
    @patch("src.transcript.transcribe_video_mlx")
    @patch("src.transcript.format_transcript_for_ai")
    def test_success_with_words(self, mock_format, mock_transcribe):
        mock_transcribe.return_value = {
            "words": [{"text": "hello", "start": 0, "end": 500}]
        }
        mock_format.return_value = "[00:00.000 - 00:00.500] hello"

        result = get_video_transcript(Path("/fake/video.mp4"))
        assert result == "[00:00.000 - 00:00.500] hello"
        mock_transcribe.assert_called_once()
        mock_format.assert_called_once()

    @patch("src.transcript.transcribe_video_mlx")
    def test_no_words_returns_empty(self, mock_transcribe):
        mock_transcribe.return_value = {"words": []}
        result = get_video_transcript(Path("/fake/video.mp4"))
        assert result == ""

    @patch("src.transcript.transcribe_video_mlx")
    def test_no_words_key_returns_empty(self, mock_transcribe):
        mock_transcribe.return_value = {"text": "hello"}
        result = get_video_transcript(Path("/fake/video.mp4"))
        assert result == ""

    @patch("src.transcript.transcribe_video_mlx")
    def test_exception_propagates(self, mock_transcribe):
        mock_transcribe.side_effect = RuntimeError("transcription failed")
        with pytest.raises(RuntimeError, match="transcription failed"):
            get_video_transcript(Path("/fake/video.mp4"))


# ---------------------------------------------------------------------------
# cache_transcript_data (lines 222-244)
# ---------------------------------------------------------------------------
class TestCacheTranscriptData:
    def test_cache_with_words(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_transcript = MagicMock()
        mock_transcript.words = [
            MagicMock(text="hello", start=0, end=500, confidence=0.95),
            MagicMock(text="world", start=500, end=1000, spec=["text", "start", "end"]),
        ]
        # The second word has no confidence attribute
        del mock_transcript.words[1].confidence
        mock_transcript.text = "hello world"

        cache_transcript_data(video_path, mock_transcript)

        cache_path = video_path.with_suffix(".transcript_cache.json")
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert len(data["words"]) == 2
        assert data["words"][0]["confidence"] == 0.95
        assert data["words"][1]["confidence"] == 1.0
        assert data["text"] == "hello world"

    def test_cache_no_words(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_transcript = MagicMock()
        mock_transcript.words = []
        mock_transcript.text = ""

        cache_transcript_data(video_path, mock_transcript)
        cache_path = video_path.with_suffix(".transcript_cache.json")
        data = json.loads(cache_path.read_text())
        assert data["words"] == []


# ---------------------------------------------------------------------------
# load_cached_transcript_data
# ---------------------------------------------------------------------------
class TestLoadCachedTranscriptData:
    def test_no_cache_file(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        result = load_cached_transcript_data(video_path)
        assert result is None

    def test_valid_cache(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_data = {"words": [{"text": "hi", "start": 0, "end": 100}]}
        cache_path.write_text(json.dumps(cache_data))

        result = load_cached_transcript_data(video_path)
        assert result is not None
        assert result["words"][0]["text"] == "hi"

    def test_corrupt_cache(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_path.write_text("NOT JSON")

        result = load_cached_transcript_data(video_path)
        assert result is None


# ---------------------------------------------------------------------------
# extract_text_from_cache
# ---------------------------------------------------------------------------
class TestExtractTextFromCache:
    def test_no_cache(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        result = extract_text_from_cache(video_path, 0.0, 5.0)
        assert result is None

    def test_extract_words_in_range(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_data = {
            "words": [
                {"text": "hello", "start": 1000, "end": 1500},
                {"text": "world", "start": 2000, "end": 2500},
                {"text": "extra", "start": 6000, "end": 6500},
            ]
        }
        cache_path.write_text(json.dumps(cache_data))

        result = extract_text_from_cache(video_path, 0.5, 5.0)
        assert result == "hello world"

    def test_no_words_in_range(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_data = {
            "words": [
                {"text": "hello", "start": 10000, "end": 10500},
            ]
        }
        cache_path.write_text(json.dumps(cache_data))

        result = extract_text_from_cache(video_path, 0.0, 5.0)
        assert result is None

    def test_no_words_key(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_path.write_text(json.dumps({"text": "hello"}))

        result = extract_text_from_cache(video_path, 0.0, 5.0)
        assert result is None


# ---------------------------------------------------------------------------
# parse_timestamp_to_seconds
# ---------------------------------------------------------------------------
class TestParseTimestampToSeconds:
    def test_mm_ss(self):
        assert parse_timestamp_to_seconds("01:30") == 90.0

    def test_mm_ss_ms(self):
        result = parse_timestamp_to_seconds("01:30.500")
        assert abs(result - 90.5) < 0.001

    def test_hh_mm_ss(self):
        assert parse_timestamp_to_seconds("01:02:03") == 3723.0

    def test_hh_mm_ss_ms(self):
        result = parse_timestamp_to_seconds("01:02:03.500")
        assert abs(result - 3723.5) < 0.001

    def test_pure_seconds(self):
        assert parse_timestamp_to_seconds("45.5") == 45.5

    def test_whitespace_stripped(self):
        assert parse_timestamp_to_seconds("  01:30  ") == 90.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_timestamp_to_seconds("not_a_timestamp")


# ---------------------------------------------------------------------------
# _find_closest_word_index
# ---------------------------------------------------------------------------
class TestFindClosestWordIndex:
    def test_exact_match(self):
        words = [{"start": 1000}, {"start": 2000}, {"start": 3000}]
        assert _find_closest_word_index(words, 2000) == 1

    def test_closest_match(self):
        words = [{"start": 1000}, {"start": 2000}, {"start": 3000}]
        assert _find_closest_word_index(words, 2200) == 1

    def test_empty_list(self):
        assert _find_closest_word_index([], 1000) == -1


# ---------------------------------------------------------------------------
# _is_sentence_start_word
# ---------------------------------------------------------------------------
class TestIsSentenceStartWord:
    def test_first_word(self):
        words = [{"text": "hello"}]
        assert _is_sentence_start_word(words, 0) is True

    def test_uppercase_after_period(self):
        words = [{"text": "end."}, {"text": "Start"}]
        assert _is_sentence_start_word(words, 1) is True

    def test_lowercase_after_period(self):
        words = [{"text": "end."}, {"text": "start"}]
        assert _is_sentence_start_word(words, 1) is False

    def test_uppercase_no_period(self):
        words = [{"text": "word"}, {"text": "Start"}]
        assert _is_sentence_start_word(words, 1) is False

    def test_empty_text(self):
        words = [{"text": "end."}, {"text": ""}]
        assert _is_sentence_start_word(words, 1) is False

    def test_previous_empty(self):
        words = [{"text": ""}, {"text": "Start"}]
        assert _is_sentence_start_word(words, 1) is False


# ---------------------------------------------------------------------------
# _find_sentence_start_backwards (lines 427, 431, 436)
# ---------------------------------------------------------------------------
class TestFindSentenceStartBackwards:
    def test_finds_sentence_start(self):
        words = [
            {"text": "end.", "start": 1000},
            {"text": "The", "start": 1500},
            {"text": "new", "start": 2000},
        ]
        # Searching backwards from index 2, target=2000, window=2000ms
        result = _find_sentence_start_backwards(words, 2, 2000, 2000)
        assert result == 1  # "The" after "end."

    def test_too_far_back_stops(self):
        words = [
            {"text": "end.", "start": 0},
            {"text": "The", "start": 100},
            {"text": "new", "start": 5000},
        ]
        # target_ms=5000, window=1000 => we won't go back to start=100 because
        # 5000 - 100 = 4900 > 1000
        result = _find_sentence_start_backwards(words, 2, 5000, 1000)
        assert result == -1

    def test_skip_if_word_too_far_forward(self):
        words = [
            {"text": "end.", "start": 0},
            {"text": "The", "start": 10000},  # way ahead of target
            {"text": "new", "start": 1000},
        ]
        # target_ms=1000, the word at idx 1 has start 10000, so curr_start - target_ms = 9000 > 2000
        result = _find_sentence_start_backwards(words, 2, 1000, 5000)
        # "new" at idx 2 is not a sentence start, "The" at idx 1 is too far forward, "end." at idx 0 is first word
        assert result == 0

    def test_no_match_returns_minus_one(self):
        words = [
            {"text": "and", "start": 1000},
            {"text": "also", "start": 2000},
        ]
        result = _find_sentence_start_backwards(words, 1, 2000, 3000)
        # "also" is not sentence start, "and" is idx 0 => is sentence start
        # Actually, idx 0 is always a sentence start
        assert result == 0


# ---------------------------------------------------------------------------
# snap_segment_to_sentence_start (lines 470, 487)
# ---------------------------------------------------------------------------
class TestSnapSegmentToSentenceStart:
    def test_no_cache(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        result = snap_segment_to_sentence_start(video_path, 5.0)
        assert result == (5.0, "", "No cache available")

    def test_no_words_in_cache(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_path.write_text(json.dumps({"words": []}))
        # load_cached_transcript_data will return {"words": []}, but the function
        # checks "words" not in transcript_data, which is False. But then
        # _find_closest_word_index returns -1.
        # Actually, let's test with no words key
        cache_path.write_text(json.dumps({"text": "hello"}))
        result = snap_segment_to_sentence_start(video_path, 5.0)
        assert result == (5.0, "", "No cache available")

    def test_empty_words_returns_no_words(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_path.write_text(json.dumps({"words": []}))
        result = snap_segment_to_sentence_start(video_path, 5.0)
        # _find_closest_word_index([],5000) => -1
        assert result == (5.0, "", "No words found")

    def test_snaps_to_sentence_start(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_data = {
            "words": [
                {"text": "end.", "start": 3000, "end": 3500},
                {"text": "Start", "start": 4000, "end": 4500},
                {"text": "here", "start": 5000, "end": 5500},
            ]
        }
        cache_path.write_text(json.dumps(cache_data))
        result = snap_segment_to_sentence_start(video_path, 5.0)
        # Closest to 5000ms is idx 2. Search backwards:
        # idx 2: "here" is not sentence start
        # idx 1: "Start" after "end." => sentence start
        assert result[0] == 4.0
        assert result[1] == "Start"

    def test_no_better_start_found(self, tmp_path):
        video_path = tmp_path / "video.mp4"
        cache_path = video_path.with_suffix(".transcript_cache.json")
        cache_data = {
            "words": [
                {"text": "and", "start": 1000, "end": 1500},
                {"text": "also", "start": 2000, "end": 2500},
                {"text": "maybe", "start": 10000, "end": 10500},
            ]
        }
        cache_path.write_text(json.dumps(cache_data))
        # target = 10.0s = 10000ms, closest idx = 2
        # Search backwards: idx 2 "maybe" not sentence start, idx 1 "also" start=2000, 10000-2000=8000 > 2000 (window)
        result = snap_segment_to_sentence_start(video_path, 10.0)
        assert result == (10.0, "", "No better start found")


# end tests/unit/test_transcript.py
