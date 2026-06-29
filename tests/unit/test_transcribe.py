# start tests/unit/test_transcribe.py
"""Unit tests for src/pipeline/transcribe.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.exceptions
from src.pipeline.transcribe import (
    _CACHE_VERSION,
    TranscriptionError,
    _tokens_from_result,
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

    def test_all_whitespace_tokens_yield_no_words(self) -> None:
        """Tokens that are all blank are dropped, so nothing is flushed at the end."""
        tokens = [
            {"text": "  ", "start": 0.0, "end": 0.2},
            {"text": "", "start": 0.2, "end": 0.4},
        ]
        assert merge_bpe_tokens(tokens) == []

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
# TranscriptionError inheritance
# ---------------------------------------------------------------------------


class TestTranscriptionErrorInheritance:
    """Tests for the centralized exception inheritance of TranscriptionError."""

    def test_inherits_from_central_transcription_error(self) -> None:
        """transcribe.TranscriptionError subclasses the centralized one."""
        assert issubclass(TranscriptionError, src.exceptions.TranscriptionError)
        assert issubclass(TranscriptionError, src.exceptions.SupoClipError)

    def test_central_except_site_catches_local_error(self) -> None:
        """An ``except src.exceptions.TranscriptionError`` catches the local subclass."""
        with pytest.raises(src.exceptions.TranscriptionError):
            raise TranscriptionError("boom")


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

    def test_raises_transcription_error_when_parakeet_unavailable(self, tmp_path: Path) -> None:
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

    def test_raises_transcription_error_on_parakeet_exception(self, tmp_path: Path) -> None:
        """TranscriptionError is raised when parakeet raises during transcription.

        Covers lines 289-290: the ``except Exception`` handler inside
        transcribe_video that wraps parakeet errors.
        """
        import sys
        import types

        video = tmp_path / "test.mp4"
        video.touch()

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("GPU OOM")

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
            pytest.raises(TranscriptionError, match="parakeet-mlx transcription failed"),
        ):
            transcribe_video(video)


# ---------------------------------------------------------------------------
# load_cached_transcript — words-not-a-list branch
# ---------------------------------------------------------------------------


class TestLoadCachedTranscriptWordsNotList:
    """Additional tests for load_cached_transcript edge cases."""

    def test_returns_none_when_words_is_not_a_list(self, tmp_path: Path) -> None:
        """Returns None when cache 'words' value is not a list (line 159).

        This covers the ``if not isinstance(words, list): return None`` guard.
        """
        video = tmp_path / "video.mp4"
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION,
                    "video_path": str(video),
                    "words": "not-a-list",
                }
            )
        )
        result = load_cached_transcript(video)
        assert result is None

    def test_returns_none_when_words_key_missing(self, tmp_path: Path) -> None:
        """Returns None when 'words' key is absent (also hits line 159)."""
        video = tmp_path / "video.mp4"
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION,
                    "video_path": str(video),
                }
            )
        )
        result = load_cached_transcript(video)
        assert result is None


# ---------------------------------------------------------------------------
# save_transcript_cache — exception handling
# ---------------------------------------------------------------------------


class TestSaveTranscriptCacheException:
    """Tests for save_transcript_cache exception path (lines 186-187)."""

    def test_logs_warning_on_write_failure(self, tmp_path: Path) -> None:
        """save_transcript_cache silently logs a warning when the write fails.

        Covers lines 186-187: the ``except Exception`` handler that catches
        IOError and similar failures without re-raising.
        """
        video = tmp_path / "video.mp4"
        words = [{"text": "Hi", "start_ms": 0, "end_ms": 200}]

        # Patch json.dump to raise so the exception handler (lines 186-187) runs.
        with patch("src.pipeline.transcribe.json.dump", side_effect=OSError("disk full")):
            # Should NOT raise — the exception is caught and logged.
            save_transcript_cache(video, words)


# ---------------------------------------------------------------------------
# _tokens_from_result
# ---------------------------------------------------------------------------


class TestTokensFromResult:
    """Tests for _tokens_from_result (lines 207-238)."""

    def _make_token(self, text: str, start: float, end: float) -> MagicMock:
        """Build a mock token object with text/start/end attributes."""
        token = MagicMock()
        token.text = text
        token.start = start
        token.end = end
        return token

    def _make_sentence(self, tokens: list) -> MagicMock:
        """Build a mock sentence object with a tokens attribute."""
        sentence = MagicMock()
        sentence.tokens = tokens
        return sentence

    def test_returns_empty_for_result_with_no_sentences_no_tokens(self) -> None:
        """Returns empty list when result has no sentences and no tokens."""
        result = MagicMock()
        result.sentences = None
        result.tokens = None
        assert _tokens_from_result(result) == []

    def test_extracts_tokens_from_sentences(self) -> None:
        """Sentence-level tokens are preferred and extracted correctly."""
        token_a = self._make_token(" Hello", 0.0, 0.4)
        token_b = self._make_token(" world", 0.5, 0.9)
        sentence = self._make_sentence([token_a, token_b])

        result = MagicMock()
        result.sentences = [sentence]

        raw = _tokens_from_result(result)
        assert len(raw) == 2
        assert raw[0] == {"text": " Hello", "start": 0.0, "end": 0.4}
        assert raw[1] == {"text": " world", "start": 0.5, "end": 0.9}

    def test_skips_sentence_tokens_with_zero_duration(self) -> None:
        """Tokens where start >= end are dropped (lines 220-221)."""
        good = self._make_token(" Hi", 0.0, 0.3)
        bad = self._make_token(" glitch", 1.0, 1.0)  # start == end
        sentence = self._make_sentence([good, bad])

        result = MagicMock()
        result.sentences = [sentence]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " Hi"

    def test_skips_sentence_tokens_with_empty_text(self) -> None:
        """Tokens with empty or whitespace-only text are dropped."""
        empty = self._make_token("   ", 0.0, 0.5)
        good = self._make_token(" ok", 0.5, 0.9)
        sentence = self._make_sentence([empty, good])

        result = MagicMock()
        result.sentences = [sentence]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " ok"

    def test_falls_back_to_top_level_tokens_when_sentences_empty(self) -> None:
        """Falls back to result.tokens when sentences list is empty/falsy.

        Covers lines 226-236 — the fallback BPE token extraction path.
        """
        token_a = self._make_token(" foo", 0.1, 0.4)
        token_b = self._make_token("bar", 0.4, 0.7)

        result = MagicMock()
        result.sentences = []  # falsy — triggers fallback
        result.tokens = [token_a, token_b]

        raw = _tokens_from_result(result)
        assert len(raw) == 2
        assert raw[0]["text"] == " foo"
        assert raw[1]["text"] == "bar"

    def test_falls_back_to_top_level_tokens_when_sentences_none(self) -> None:
        """Falls back to result.tokens when sentences is None."""
        token = self._make_token(" only", 0.0, 0.5)

        result = MagicMock()
        result.sentences = None
        result.tokens = [token]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " only"

    def test_falls_back_skips_zero_duration_top_level_tokens(self) -> None:
        """Zero-duration tokens in the fallback path are also dropped (lines 233-234)."""
        good = self._make_token(" good", 0.0, 0.3)
        bad = self._make_token(" bad", 0.5, 0.5)  # start == end

        result = MagicMock()
        result.sentences = []
        result.tokens = [good, bad]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " good"

    def test_falls_back_skips_whitespace_only_top_level_tokens(self) -> None:
        """Whitespace-only tokens in the fallback path are dropped (line 231)."""
        whitespace = self._make_token("   ", 0.0, 0.3)  # whitespace-only
        good = self._make_token(" real", 0.5, 0.9)

        result = MagicMock()
        result.sentences = []  # force fallback path
        result.tokens = [whitespace, good]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " real"

    def test_sentences_yield_no_tokens_falls_back_to_top_level(self) -> None:
        """When sentences exist but all tokens are filtered, falls back to top-level.

        Covers the ``if raw: return raw`` guard (line 223-224) NOT being hit
        when all sentence tokens are invalid, then the fallback path executes.
        """
        bad_token = self._make_token("", 0.0, 0.0)  # empty text + zero duration
        sentence = self._make_sentence([bad_token])

        top_token = self._make_token(" fallback", 0.1, 0.5)

        result = MagicMock()
        result.sentences = [sentence]
        result.tokens = [top_token]

        raw = _tokens_from_result(result)
        assert len(raw) == 1
        assert raw[0]["text"] == " fallback"


# ---------------------------------------------------------------------------
# PARAKEET_AVAILABLE = False branch (module-level import guard, lines 30-31)
# ---------------------------------------------------------------------------


class TestParakeetAvailableFlag:
    """Tests for the PARAKEET_AVAILABLE module-level flag."""

    def test_parakeet_available_is_bool(self) -> None:
        """PARAKEET_AVAILABLE is always a bool regardless of whether parakeet is installed."""
        import src.pipeline.transcribe as transcribe_mod

        assert isinstance(transcribe_mod.PARAKEET_AVAILABLE, bool)

    def test_parakeet_unavailable_set_to_false_on_import_error(self) -> None:
        """Simulates the ImportError branch by reloading with parakeet blocked.

        This test reimports the module after removing parakeet_mlx from
        sys.modules and replacing it with a stub that raises ImportError,
        verifying that PARAKEET_AVAILABLE becomes False (lines 30-31).
        """
        import importlib
        import sys

        # Remove the already-imported module so we get a fresh import.
        mod_key = "src.pipeline.transcribe"
        original = sys.modules.pop(mod_key, None)
        # Also remove parakeet_mlx so the try-block actually runs the except.
        original_parakeet = sys.modules.pop("parakeet_mlx", None)

        try:
            # Insert a stub that raises ImportError on access.
            import types

            types.ModuleType("parakeet_mlx")

            class _FailImport:
                def __getattr__(self, name: str) -> object:
                    raise ImportError("parakeet_mlx not installed")

            # Make the import itself fail by using a finder that raises.
            import builtins

            real_import = builtins.__import__

            def mock_import(name: str, *args: object, **kwargs: object) -> object:
                if name == "parakeet_mlx":
                    raise ImportError("parakeet_mlx not installed")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = mock_import  # type: ignore[assignment]
            try:
                fresh_mod = importlib.import_module(mod_key)
                assert fresh_mod.PARAKEET_AVAILABLE is False  # type: ignore[attr-defined]
            finally:
                builtins.__import__ = real_import  # type: ignore[assignment]
        finally:
            # Restore original module state.
            if original is not None:
                sys.modules[mod_key] = original
            else:
                sys.modules.pop(mod_key, None)
            if original_parakeet is not None:
                sys.modules["parakeet_mlx"] = original_parakeet


# end tests/unit/test_transcribe.py
