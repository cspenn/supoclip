# start tests/unit/test_transcribe.py
"""Unit tests for src/pipeline/transcribe.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.transcribe import (
    _CACHE_VERSION,
    TranscriptionError,
    format_transcript_text,
    load_cached_transcript,
    merge_bpe_tokens,
    save_transcript_cache,
    transcribe_video,
)

# ---------------------------------------------------------------------------
# merge_bpe_tokens
# ---------------------------------------------------------------------------


class TestMergeBpeTokens:
    """Tests for merge_bpe_tokens."""

    def test_empty_input_returns_empty(self) -> None:
        """Empty token list yields empty word list."""
        assert merge_bpe_tokens([]) == []

    def test_single_whole_word(self) -> None:
        """A single token with no sub-word marker is returned as-is."""
        tokens = [{"text": " Hello", "start": 0.0, "end": 0.4}]
        words = merge_bpe_tokens(tokens)
        assert len(words) == 1
        assert words[0]["text"] == "Hello"
        assert words[0]["start_ms"] == 0
        assert words[0]["end_ms"] == 400

    def test_bpe_continuation_tokens_merge(self) -> None:
        """Continuation tokens (no leading space) are concatenated to previous."""
        # "Yes" split into ["Y", "es"] — only first token has leading space context.
        # In practice the first token of an utterance may lack a leading space.
        tokens = [
            {"text": "Y", "start": 0.0, "end": 0.1},
            {"text": "es", "start": 0.1, "end": 0.3},
        ]
        words = merge_bpe_tokens(tokens)
        assert len(words) == 1
        assert words[0]["text"] == "Yes"
        assert words[0]["start_ms"] == 0
        assert words[0]["end_ms"] == 300

    def test_multiple_words_with_space_prefix(self) -> None:
        """Words separated by leading-space tokens produce separate entries."""
        tokens = [
            {"text": " Hello", "start": 0.0, "end": 0.4},
            {"text": " world", "start": 0.4, "end": 0.8},
        ]
        words = merge_bpe_tokens(tokens)
        assert len(words) == 2
        assert words[0]["text"] == "Hello"
        assert words[1]["text"] == "world"

    def test_mixed_bpe_sequence(self) -> None:
        """Realistic BPE sequence: space-delimited words with sub-word splits."""
        tokens = [
            {"text": " Yes", "start": 0.0, "end": 0.3},
            {"text": ",", "start": 0.3, "end": 0.35},
            {"text": " I", "start": 0.4, "end": 0.5},
            {"text": " think", "start": 0.5, "end": 0.8},
        ]
        words = merge_bpe_tokens(tokens)
        # "Yes" + "," merge because "," has no leading space
        assert len(words) == 3
        assert words[0]["text"] == "Yes,"
        assert words[1]["text"] == "I"
        assert words[2]["text"] == "think"

    def test_whitespace_only_tokens_are_skipped(self) -> None:
        """Tokens containing only whitespace are ignored."""
        tokens = [
            {"text": " Hello", "start": 0.0, "end": 0.4},
            {"text": "   ", "start": 0.4, "end": 0.41},
            {"text": " world", "start": 0.5, "end": 0.9},
        ]
        words = merge_bpe_tokens(tokens)
        assert len(words) == 2
        assert words[0]["text"] == "Hello"
        assert words[1]["text"] == "world"

    def test_output_timestamps_in_milliseconds(self) -> None:
        """start_ms and end_ms are integer milliseconds."""
        tokens = [{"text": " hi", "start": 1.5, "end": 2.25}]
        words = merge_bpe_tokens(tokens)
        assert words[0]["start_ms"] == 1500
        assert words[0]["end_ms"] == 2250
        assert isinstance(words[0]["start_ms"], int)
        assert isinstance(words[0]["end_ms"], int)


# ---------------------------------------------------------------------------
# load_cached_transcript
# ---------------------------------------------------------------------------


class TestLoadCachedTranscript:
    """Tests for load_cached_transcript."""

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Returns None when no cache file exists."""
        video = tmp_path / "video.mp4"
        # Do NOT create the cache file.
        result = load_cached_transcript(video)
        assert result is None

    def test_returns_none_for_wrong_version(self, tmp_path: Path) -> None:
        """Returns None when the cache has a wrong version number."""
        video = tmp_path / "video.mp4"
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION - 1,
                    "video_path": str(video),
                    "words": [{"text": "Hello", "start_ms": 0, "end_ms": 400}],
                }
            )
        )
        result = load_cached_transcript(video)
        assert result is None

    def test_returns_none_for_corrupt_json(self, tmp_path: Path) -> None:
        """Returns None when the cache file contains invalid JSON."""
        video = tmp_path / "video.mp4"
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text("not valid json {{{{")
        result = load_cached_transcript(video)
        assert result is None

    def test_returns_words_for_valid_cache(self, tmp_path: Path) -> None:
        """Returns word list for a valid, current-version cache."""
        video = tmp_path / "video.mp4"
        words = [{"text": "Hello", "start_ms": 0, "end_ms": 400}]
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION,
                    "video_path": str(video),
                    "words": words,
                }
            )
        )
        result = load_cached_transcript(video)
        assert result == words


# ---------------------------------------------------------------------------
# save_transcript_cache + load_cached_transcript round-trip
# ---------------------------------------------------------------------------


class TestCacheRoundTrip:
    """Round-trip tests for save_transcript_cache and load_cached_transcript."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Saved cache is loadable and contains the original words."""
        video = tmp_path / "myvideo.mp4"
        words = [
            {"text": "Hello", "start_ms": 0, "end_ms": 400},
            {"text": "world", "start_ms": 500, "end_ms": 900},
        ]
        save_transcript_cache(video, words)
        loaded = load_cached_transcript(video)
        assert loaded == words

    def test_cache_file_name(self, tmp_path: Path) -> None:
        """Cache file is written adjacent to the video with expected name."""
        video = tmp_path / "clip.mp4"
        save_transcript_cache(video, [])
        cache_file = tmp_path / "clip.transcript_cache.json"
        assert cache_file.exists()

    def test_cache_contains_correct_version(self, tmp_path: Path) -> None:
        """Cache file stores the current cache version."""
        video = tmp_path / "v.mp4"
        save_transcript_cache(video, [])
        data = json.loads((tmp_path / "v.transcript_cache.json").read_text())
        assert data["version"] == _CACHE_VERSION


# ---------------------------------------------------------------------------
# format_transcript_text
# ---------------------------------------------------------------------------


class TestFormatTranscriptText:
    """Tests for format_transcript_text."""

    def test_empty_words_returns_empty_string(self) -> None:
        """Empty word list yields an empty string."""
        assert format_transcript_text([]) == ""

    def test_single_word(self) -> None:
        """Single word is formatted correctly."""
        words = [{"text": "Hello", "start_ms": 0, "end_ms": 400}]
        result = format_transcript_text(words)
        assert result == "Hello [0-400]"

    def test_multiple_words(self) -> None:
        """Multiple words are space-joined with their timestamps."""
        words = [
            {"text": "Hello", "start_ms": 0, "end_ms": 400},
            {"text": "world", "start_ms": 500, "end_ms": 900},
        ]
        result = format_transcript_text(words)
        assert result == "Hello [0-400] world [500-900]"

    def test_empty_text_words_are_skipped(self) -> None:
        """Words with empty text are excluded from output."""
        words = [
            {"text": "", "start_ms": 0, "end_ms": 100},
            {"text": "Hi", "start_ms": 100, "end_ms": 300},
        ]
        result = format_transcript_text(words)
        assert result == "Hi [100-300]"


# ---------------------------------------------------------------------------
# transcribe_video — mocked parakeet
# ---------------------------------------------------------------------------


class TestTranscribeVideo:
    """Tests for transcribe_video with mocked parakeet_mlx."""

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """TranscriptionError raised when video file does not exist."""
        with pytest.raises(TranscriptionError, match="not found"):
            transcribe_video(tmp_path / "nonexistent.mp4")

    def test_returns_cached_words_without_calling_model(self, tmp_path: Path) -> None:
        """Cache hit returns stored words without invoking parakeet."""
        video = tmp_path / "test.mp4"
        video.touch()  # create empty file so path check passes
        cached_words = [{"text": "cached", "start_ms": 0, "end_ms": 200}]
        save_transcript_cache(video, cached_words)

        # Even with parakeet unavailable the cache should be returned.
        with patch("src.pipeline.transcribe.PARAKEET_AVAILABLE", False):
            result = transcribe_video(video)

        assert result == cached_words

    def test_raises_transcription_error_when_parakeet_unavailable(
        self, tmp_path: Path
    ) -> None:
        """TranscriptionError raised if parakeet is not installed and no cache."""
        video = tmp_path / "test.mp4"
        video.touch()
        with (
            patch("src.pipeline.transcribe.PARAKEET_AVAILABLE", False),
            pytest.raises(TranscriptionError, match="not installed"),
        ):
            transcribe_video(video)

    def test_calls_parakeet_and_merges_tokens(self, tmp_path: Path) -> None:
        """transcribe_video calls parakeet and returns merged words.

        We patch at the boundary points inside transcribe_video so the test
        does not depend on parakeet or mlx being importable at runtime.
        The parakeet model load and transcribe call are replaced with a mock
        that returns a pre-built AlignedResult stand-in, and ``_tokens_from_result``
        is patched to return canned raw tokens.
        """
        import sys
        import types

        video = tmp_path / "test.mp4"
        video.touch()

        expected_words = [
            {"text": "Hello", "start_ms": 0, "end_ms": 400},
            {"text": "world", "start_ms": 500, "end_ms": 900},
        ]

        # Build lightweight fake modules so the `from X import Y` inside
        # transcribe_video resolves without actually loading parakeet / mlx.
        mock_model = MagicMock()
        mock_model.transcribe.return_value = MagicMock()  # result handled via _tokens_from_result

        fake_parakeet_utils = types.ModuleType("parakeet_mlx.utils")
        fake_parakeet_utils.from_pretrained = MagicMock(return_value=mock_model)  # type: ignore[attr-defined]

        fake_mlx_core = types.ModuleType("mlx.core")
        fake_mlx_core.bfloat16 = MagicMock()  # type: ignore[attr-defined]

        with (
            patch("src.pipeline.transcribe.PARAKEET_AVAILABLE", True),
            patch.dict(
                sys.modules,
                {
                    "parakeet_mlx": types.ModuleType("parakeet_mlx"),
                    "parakeet_mlx.utils": fake_parakeet_utils,
                    "mlx": types.ModuleType("mlx"),
                    "mlx.core": fake_mlx_core,
                },
            ),
            patch(
                "src.pipeline.transcribe._tokens_from_result",
                return_value=[
                    {"text": " Hello", "start": 0.0, "end": 0.4},
                    {"text": " world", "start": 0.5, "end": 0.9},
                ],
            ),
            patch("src.pipeline.transcribe.save_transcript_cache"),
        ):
            result = transcribe_video(video)

        assert result == expected_words


# end tests/unit/test_transcribe.py
