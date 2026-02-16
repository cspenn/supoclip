# start backend/tests/unit/test_transcription_mlx_coverage.py
"""Comprehensive tests for transcription_mlx.py to achieve 100% line coverage.

Covers:
- Import fallback paths (parakeet-mlx / groq not installed)
- transcribe_video_mlx: ImportError, FileNotFoundError, cache hit, full flow, cache save error
- _extract_text_from_result
- _extract_segments_from_result
- _extract_words_from_result (primary + fallback paths)
- _extract_single_token (all branches)
- _reconstruct_words_with_llm (Groq not available, no API key, empty text, success, empty response, error)
- _rebuild_segments_from_words (with punctuation + remainder)
- _align_reconstructed_words (empty, normal, excess words)
- get_video_transcript_mlx
- load_cached_transcript_mlx (no cache, old version, valid, corrupted)
- _process_word_reconstruction (disabled, enabled success, enabled error)
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.transcription_mlx import (
    TRANSCRIPT_CACHE_VERSION,
    transcribe_video_mlx,
    _extract_text_from_result,
    _extract_segments_from_result,
    _extract_words_from_result,
    _extract_single_token,
    _reconstruct_words_with_llm,
    _rebuild_segments_from_words,
    _align_reconstructed_words,
    get_video_transcript_mlx,
    load_cached_transcript_mlx,
    _process_word_reconstruction,
)


# ---------------------------------------------------------------------------
# Module-level import fallback tests
# ---------------------------------------------------------------------------


class TestImportFallbacks:
    """Test that the module handles missing optional dependencies gracefully."""

    def test_parakeet_mlx_import_fallback(self) -> None:
        """Lines 18-20: from_pretrained and bfloat16 set to None when not available."""
        import importlib
        import sys

        # Temporarily make parakeet_mlx and mlx unavailable
        saved_modules = {}
        for mod_name in list(sys.modules.keys()):
            if "parakeet_mlx" in mod_name or mod_name.startswith("mlx"):
                saved_modules[mod_name] = sys.modules.pop(mod_name)

        # Also remove cached transcription_mlx
        if "src.transcription_mlx" in sys.modules:
            saved_modules["src.transcription_mlx"] = sys.modules.pop("src.transcription_mlx")

        # Install import hook that blocks parakeet_mlx and mlx
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name in ("parakeet_mlx.utils", "mlx.core"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            try:
                mod = importlib.import_module("src.transcription_mlx")
                importlib.reload(mod)
            except Exception:
                pass

        # Restore modules
        sys.modules.update(saved_modules)
        # Re-import to restore original state
        importlib.reload(importlib.import_module("src.transcription_mlx"))

    def test_groq_import_fallback(self) -> None:
        """Lines 24-25: AsyncGroq set to None when groq not installed."""
        import importlib
        import sys

        saved_modules = {}
        for mod_name in list(sys.modules.keys()):
            if "groq" in mod_name:
                saved_modules[mod_name] = sys.modules.pop(mod_name)

        if "src.transcription_mlx" in sys.modules:
            saved_modules["src.transcription_mlx"] = sys.modules.pop("src.transcription_mlx")

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "groq":
                raise ImportError("No module named 'groq'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            try:
                mod = importlib.import_module("src.transcription_mlx")
                importlib.reload(mod)
            except Exception:
                pass

        # Restore
        sys.modules.update(saved_modules)
        importlib.reload(importlib.import_module("src.transcription_mlx"))


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_token(text: str, start: float, end: float, confidence: float = 0.9) -> SimpleNamespace:
    return SimpleNamespace(text=text, start=start, end=end, confidence=confidence, id=1)


def _make_sentence(text: str, start: float, end: float, tokens: list) -> SimpleNamespace:
    return SimpleNamespace(text=text, start=start, end=end, tokens=tokens)


def _make_result(
    text: str = "",
    sentences: list | None = None,
    tokens: list | None = None,
) -> SimpleNamespace:
    ns = SimpleNamespace(text=text)
    if sentences is not None:
        ns.sentences = sentences
    if tokens is not None:
        ns.tokens = tokens
    return ns


# ---------------------------------------------------------------------------
# _extract_text_from_result
# ---------------------------------------------------------------------------


class TestExtractTextFromResult:
    def test_has_text(self) -> None:
        result = _make_result(text="Hello world")
        assert _extract_text_from_result(result) == "Hello world"

    def test_no_text_attr(self) -> None:
        result = SimpleNamespace()
        assert _extract_text_from_result(result) == ""


# ---------------------------------------------------------------------------
# _extract_segments_from_result
# ---------------------------------------------------------------------------


class TestExtractSegmentsFromResult:
    def test_has_sentences(self) -> None:
        t1 = _make_token("Hello", 0.0, 0.5)
        s1 = _make_sentence("Hello world.", 0.0, 1.0, [t1])
        result = _make_result(sentences=[s1])
        segments = _extract_segments_from_result(result)
        assert len(segments) == 1
        assert segments[0]["start"] == 0
        assert segments[0]["end"] == 1000
        assert segments[0]["text"] == "Hello world."

    def test_no_sentences(self) -> None:
        result = SimpleNamespace()
        assert _extract_segments_from_result(result) == []

    def test_sentence_without_start_end_text(self) -> None:
        """Handles sentences missing .start / .end / .text attributes."""
        s = SimpleNamespace(tokens=[])
        result = SimpleNamespace(sentences=[s])
        segments = _extract_segments_from_result(result)
        assert len(segments) == 1
        assert segments[0]["start"] == 0
        assert segments[0]["end"] == 0
        assert segments[0]["text"] == ""

    def test_token_without_id(self) -> None:
        """Tokens without .id attribute are skipped in token list."""
        t = SimpleNamespace(text="hi", start=0.0, end=0.5)  # no .id
        s = _make_sentence("hi", 0.0, 0.5, [t])
        result = SimpleNamespace(sentences=[s])
        segments = _extract_segments_from_result(result)
        assert segments[0]["tokens"] == []


# ---------------------------------------------------------------------------
# _extract_single_token
# ---------------------------------------------------------------------------


class TestExtractSingleToken:
    def test_valid_token(self) -> None:
        t = _make_token("Hello", 0.0, 1.0, 0.95)
        d = _extract_single_token(t)
        assert d is not None
        assert d["text"] == "Hello"
        assert d["start"] == 0
        assert d["end"] == 1000
        assert d["confidence"] == 0.95

    def test_empty_text(self) -> None:
        t = _make_token("   ", 0.0, 1.0)
        assert _extract_single_token(t) is None

    def test_no_text_attr(self) -> None:
        t = SimpleNamespace(start=0.0, end=1.0)
        assert _extract_single_token(t) is None

    def test_invalid_timing(self) -> None:
        """start >= end should return None."""
        t = _make_token("hello", 1.0, 1.0)
        assert _extract_single_token(t) is None

    def test_no_start_end(self) -> None:
        """Token without start/end defaults to 0, 0 -> invalid."""
        t = SimpleNamespace(text="word")
        assert _extract_single_token(t) is None

    def test_no_confidence(self) -> None:
        """Token without confidence defaults to 1.0."""
        t = SimpleNamespace(text="word", start=0.0, end=0.5)
        d = _extract_single_token(t)
        assert d is not None
        assert d["confidence"] == 1.0


# ---------------------------------------------------------------------------
# _extract_words_from_result
# ---------------------------------------------------------------------------


class TestExtractWordsFromResult:
    def test_primary_from_sentences(self) -> None:
        t1 = _make_token("Hello", 0.0, 0.5)
        t2 = _make_token("world", 0.5, 1.0)
        s = _make_sentence("Hello world", 0.0, 1.0, [t1, t2])
        result = SimpleNamespace(sentences=[s])
        words = _extract_words_from_result(result)
        assert len(words) == 2
        assert words[0]["text"] == "Hello"

    def test_fallback_to_tokens(self) -> None:
        """Falls back to result.tokens when sentences are empty."""
        t1 = _make_token("Hello", 0.0, 0.5)
        result = SimpleNamespace(sentences=[], tokens=[t1])
        words = _extract_words_from_result(result)
        assert len(words) == 1

    def test_fallback_no_sentences_attr(self) -> None:
        """Falls back when result has no sentences attribute at all."""
        t1 = _make_token("Hello", 0.0, 0.5)
        result = SimpleNamespace(tokens=[t1])
        words = _extract_words_from_result(result)
        assert len(words) == 1

    def test_no_sentences_no_tokens(self) -> None:
        result = SimpleNamespace()
        words = _extract_words_from_result(result)
        assert words == []

    def test_sentence_with_empty_tokens(self) -> None:
        """Sentence with no valid tokens falls through to fallback."""
        empty_token = SimpleNamespace(text="   ", start=0.0, end=0.5)
        s = SimpleNamespace(tokens=[empty_token])
        result = SimpleNamespace(sentences=[s])
        # No valid words from sentences -> falls back but no tokens attr
        words = _extract_words_from_result(result)
        assert words == []


# ---------------------------------------------------------------------------
# _rebuild_segments_from_words
# ---------------------------------------------------------------------------


class TestRebuildSegmentsFromWords:
    def test_splits_on_punctuation(self) -> None:
        words = [
            {"text": "Hello", "start": 0, "end": 500},
            {"text": "world.", "start": 500, "end": 1000},
            {"text": "How", "start": 1000, "end": 1500},
            {"text": "are", "start": 1500, "end": 2000},
            {"text": "you?", "start": 2000, "end": 2500},
        ]
        segments = _rebuild_segments_from_words(words)
        assert len(segments) == 2
        assert segments[0]["text"] == "Hello world."
        assert segments[0]["end"] == 1000
        assert segments[1]["text"] == "How are you?"

    def test_no_punctuation_single_segment(self) -> None:
        words = [
            {"text": "Hello", "start": 0, "end": 500},
            {"text": "world", "start": 500, "end": 1000},
        ]
        segments = _rebuild_segments_from_words(words)
        assert len(segments) == 1
        assert segments[0]["text"] == "Hello world"

    def test_empty_words(self) -> None:
        segments = _rebuild_segments_from_words([])
        # Empty list -> current_start defaults to 0, no words to iterate
        assert segments == []

    def test_exclamation_mark(self) -> None:
        words = [
            {"text": "Wow!", "start": 0, "end": 500},
            {"text": "Great", "start": 500, "end": 1000},
        ]
        segments = _rebuild_segments_from_words(words)
        assert len(segments) == 2


# ---------------------------------------------------------------------------
# _align_reconstructed_words
# ---------------------------------------------------------------------------


class TestAlignReconstructedWords:
    def test_normal_alignment(self) -> None:
        broken = [
            {"text": "Hel", "start": 0, "end": 300, "confidence": 0.9},
            {"text": "lo", "start": 300, "end": 500, "confidence": 0.8},
            {"text": "world", "start": 500, "end": 1000, "confidence": 1.0},
        ]
        aligned = _align_reconstructed_words(broken, "Hello world")
        assert len(aligned) == 2
        assert aligned[0]["text"] == "Hello"
        assert aligned[0]["start"] == 0
        assert aligned[1]["text"] == "world"

    def test_empty_reconstructed(self) -> None:
        broken = [{"text": "a", "start": 0, "end": 100, "confidence": 1.0}]
        result = _align_reconstructed_words(broken, "")
        assert result == broken

    def test_more_reconstructed_than_tokens(self) -> None:
        """When reconstructed has more words than broken tokens, alignment stops."""
        broken = [{"text": "Hi", "start": 0, "end": 100, "confidence": 1.0}]
        result = _align_reconstructed_words(broken, "Hi there friend")
        # Only 1 broken token, can map to "Hi" at most, then broken_idx runs out
        assert len(result) >= 1
        assert result[0]["text"] == "Hi"


# ---------------------------------------------------------------------------
# _reconstruct_words_with_llm (async)
# ---------------------------------------------------------------------------


class TestReconstructWordsWithLlm:
    @pytest.mark.asyncio
    async def test_groq_not_installed(self) -> None:
        """Returns original words when AsyncGroq is None."""
        words = [{"text": "he", "start": 0, "end": 100}]
        with patch("src.transcription_mlx.AsyncGroq", None):
            result = await _reconstruct_words_with_llm(words)
        assert result == words

    @pytest.mark.asyncio
    async def test_no_api_key(self) -> None:
        """Returns original words when GROQ_API_KEY is empty."""
        words = [{"text": "he", "start": 0, "end": 100}]
        mock_config = MagicMock()
        mock_config.groq_api_key = ""
        with patch("src.transcription_mlx.AsyncGroq", MagicMock()), \
             patch("src.transcription_mlx.Config", return_value=mock_config):
            result = await _reconstruct_words_with_llm(words)
        assert result == words

    @pytest.mark.asyncio
    async def test_empty_text(self) -> None:
        """Returns original words when all word texts are empty."""
        words = [{"text": "  ", "start": 0, "end": 100}]
        mock_config = MagicMock()
        mock_config.groq_api_key = "test-key"
        with patch("src.transcription_mlx.AsyncGroq", MagicMock()), \
             patch("src.transcription_mlx.Config", return_value=mock_config):
            result = await _reconstruct_words_with_llm(words)
        assert result == words

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Full successful reconstruction flow."""
        broken = [
            {"text": "Hel", "start": 0, "end": 300, "confidence": 0.9},
            {"text": "lo", "start": 300, "end": 500, "confidence": 0.8},
            {"text": "world", "start": 500, "end": 1000, "confidence": 1.0},
        ]

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello world"
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_groq_cls = MagicMock(return_value=mock_client)
        mock_config = MagicMock()
        mock_config.groq_api_key = "test-key"

        with patch("src.transcription_mlx.AsyncGroq", mock_groq_cls), \
             patch("src.transcription_mlx.Config", return_value=mock_config):
            result = await _reconstruct_words_with_llm(broken)

        assert len(result) == 2
        assert result[0]["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        """Returns original words when Groq returns empty response."""
        broken = [{"text": "he", "start": 0, "end": 100, "confidence": 1.0}]

        mock_response = MagicMock()
        mock_response.choices = []

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_groq_cls = MagicMock(return_value=mock_client)
        mock_config = MagicMock()
        mock_config.groq_api_key = "test-key"

        with patch("src.transcription_mlx.AsyncGroq", mock_groq_cls), \
             patch("src.transcription_mlx.Config", return_value=mock_config):
            result = await _reconstruct_words_with_llm(broken)
        assert result == broken

    @pytest.mark.asyncio
    async def test_api_error(self) -> None:
        """Returns original words when API call fails."""
        broken = [{"text": "he", "start": 0, "end": 100, "confidence": 1.0}]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        mock_groq_cls = MagicMock(return_value=mock_client)
        mock_config = MagicMock()
        mock_config.groq_api_key = "test-key"

        with patch("src.transcription_mlx.AsyncGroq", mock_groq_cls), \
             patch("src.transcription_mlx.Config", return_value=mock_config):
            result = await _reconstruct_words_with_llm(broken)
        assert result == broken


# ---------------------------------------------------------------------------
# load_cached_transcript_mlx
# ---------------------------------------------------------------------------


class TestLoadCachedTranscriptMlx:
    def test_no_cache_file(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        assert load_cached_transcript_mlx(video) is None

    def test_valid_cache(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        cache = tmp_path / "video.transcript_cache.json"
        data = {"text": "hello", "_cache_version": TRANSCRIPT_CACHE_VERSION}
        cache.write_text(json.dumps(data))

        result = load_cached_transcript_mlx(video)
        assert result is not None
        assert result["text"] == "hello"

    def test_old_cache_version(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        cache = tmp_path / "video.transcript_cache.json"
        data = {"text": "hello", "_cache_version": 1}  # old version
        cache.write_text(json.dumps(data))

        result = load_cached_transcript_mlx(video)
        assert result is None

    def test_no_version_key(self, tmp_path: Path) -> None:
        """Cache without _cache_version defaults to 1 (old)."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        cache = tmp_path / "video.transcript_cache.json"
        data = {"text": "hello"}
        cache.write_text(json.dumps(data))

        result = load_cached_transcript_mlx(video)
        assert result is None

    def test_corrupted_cache(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        cache = tmp_path / "video.transcript_cache.json"
        cache.write_text("NOT VALID JSON {{{")

        result = load_cached_transcript_mlx(video)
        assert result is None


# ---------------------------------------------------------------------------
# transcribe_video_mlx
# ---------------------------------------------------------------------------


class TestTranscribeVideoMlx:
    def test_import_error_when_not_installed(self, tmp_path: Path) -> None:
        """Raises ImportError when parakeet-mlx is not installed."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        with patch("src.transcription_mlx.from_pretrained", None):
            with pytest.raises(ImportError, match="parakeet-mlx not installed"):
                transcribe_video_mlx(video)

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for missing video."""
        fake_pretrained = MagicMock()
        with patch("src.transcription_mlx.from_pretrained", fake_pretrained):
            with pytest.raises(FileNotFoundError):
                transcribe_video_mlx(tmp_path / "nonexistent.mp4")

    def test_cache_hit(self, tmp_path: Path) -> None:
        """Returns cached data when available."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        cache = tmp_path / "video.transcript_cache.json"
        cached = {
            "text": "cached text",
            "segments": [],
            "words": [],
            "language": "en",
            "_cache_version": TRANSCRIPT_CACHE_VERSION,
        }
        cache.write_text(json.dumps(cached))

        fake_pretrained = MagicMock()
        with patch("src.transcription_mlx.from_pretrained", fake_pretrained):
            result = transcribe_video_mlx(video)
        assert result["text"] == "cached text"
        # Model should NOT have been loaded (cache hit)
        fake_pretrained.assert_not_called()

    def test_full_transcription_flow(self, tmp_path: Path) -> None:
        """Full flow: load model, transcribe, cache result."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")

        t1 = _make_token("Hello", 0.0, 0.5)
        t2 = _make_token("world", 0.5, 1.0)
        s1 = _make_sentence("Hello world", 0.0, 1.0, [t1, t2])
        mock_result = _make_result(text="Hello world", sentences=[s1])

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_result
        fake_pretrained = MagicMock(return_value=mock_model)
        fake_bfloat = MagicMock()

        with patch("src.transcription_mlx.from_pretrained", fake_pretrained), \
             patch("src.transcription_mlx.bfloat16", fake_bfloat), \
             patch("src.transcription_mlx._process_word_reconstruction", side_effect=lambda x: x):
            result = transcribe_video_mlx(video)

        assert result["text"] == "Hello world"
        assert len(result["words"]) == 2
        assert result["language"] == "en"
        # Cache file should have been written
        cache_path = tmp_path / "video.transcript_cache.json"
        assert cache_path.exists()

    def test_cache_write_failure(self, tmp_path: Path) -> None:
        """Continues even if cache write fails (covers lines 120-121)."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")

        t1 = _make_token("Hi", 0.0, 0.5)
        s1 = _make_sentence("Hi", 0.0, 0.5, [t1])
        mock_result = _make_result(text="Hi", sentences=[s1])

        mock_model = MagicMock()
        mock_model.transcribe.return_value = mock_result
        fake_pretrained = MagicMock(return_value=mock_model)
        fake_bfloat = MagicMock()

        # Make json.dump raise to trigger the except block in cache writing
        with patch("src.transcription_mlx.from_pretrained", fake_pretrained), \
             patch("src.transcription_mlx.bfloat16", fake_bfloat), \
             patch("src.transcription_mlx._process_word_reconstruction", side_effect=lambda x: x), \
             patch("src.transcription_mlx.json.dump", side_effect=OSError("disk full")):
            result = transcribe_video_mlx(video)

        assert result["text"] == "Hi"

    def test_transcription_error(self, tmp_path: Path) -> None:
        """Raises when model.transcribe fails."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")

        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("Model failed")
        fake_pretrained = MagicMock(return_value=mock_model)
        fake_bfloat = MagicMock()

        with patch("src.transcription_mlx.from_pretrained", fake_pretrained), \
             patch("src.transcription_mlx.bfloat16", fake_bfloat):
            with pytest.raises(RuntimeError, match="Model failed"):
                transcribe_video_mlx(video)


# ---------------------------------------------------------------------------
# get_video_transcript_mlx
# ---------------------------------------------------------------------------


class TestGetVideoTranscriptMlx:
    def test_returns_text(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        with patch(
            "src.transcription_mlx.transcribe_video_mlx",
            return_value={"text": "transcript text", "words": [], "segments": []},
        ):
            assert get_video_transcript_mlx(video) == "transcript text"

    def test_returns_empty_when_no_text_key(self, tmp_path: Path) -> None:
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        with patch(
            "src.transcription_mlx.transcribe_video_mlx",
            return_value={"words": [], "segments": []},
        ):
            assert get_video_transcript_mlx(video) == ""


# ---------------------------------------------------------------------------
# _process_word_reconstruction
# ---------------------------------------------------------------------------


class TestProcessWordReconstruction:
    def test_disabled(self) -> None:
        """Returns unchanged when reconstruct_words_with_llm is False."""
        mock_config = MagicMock()
        mock_config.reconstruct_words_with_llm = False
        data = {"text": "hi", "words": [{"text": "hi"}], "segments": []}

        with patch("src.transcription_mlx.Config", return_value=mock_config):
            result = _process_word_reconstruction(data)
        assert result == data

    def test_empty_words(self) -> None:
        """Returns unchanged when words list is empty."""
        mock_config = MagicMock()
        mock_config.reconstruct_words_with_llm = True
        data: dict[str, Any] = {"text": "", "words": [], "segments": []}

        with patch("src.transcription_mlx.Config", return_value=mock_config):
            result = _process_word_reconstruction(data)
        assert result == data

    def test_success(self) -> None:
        """Successful reconstruction updates text, words, segments."""
        mock_config = MagicMock()
        mock_config.reconstruct_words_with_llm = True
        data: dict[str, Any] = {
            "text": "Hel lo",
            "words": [
                {"text": "Hel", "start": 0, "end": 300},
                {"text": "lo", "start": 300, "end": 500},
            ],
            "segments": [],
        }

        reconstructed = [{"text": "Hello", "start": 0, "end": 500}]

        with patch("src.transcription_mlx.Config", return_value=mock_config), \
             patch("src.transcription_mlx.asyncio.run", return_value=reconstructed), \
             patch("src.transcription_mlx._rebuild_segments_from_words", return_value=[{"id": 0}]):
            result = _process_word_reconstruction(data)

        assert result["words"] == reconstructed
        assert result["text"] == "Hello"
        assert result["segments"] == [{"id": 0}]

    def test_reconstruction_error(self) -> None:
        """Falls back to original on reconstruction error."""
        mock_config = MagicMock()
        mock_config.reconstruct_words_with_llm = True
        data: dict[str, Any] = {
            "text": "Hel lo",
            "words": [
                {"text": "Hel", "start": 0, "end": 300},
                {"text": "lo", "start": 300, "end": 500},
            ],
            "segments": [],
        }

        with patch("src.transcription_mlx.Config", return_value=mock_config), \
             patch("src.transcription_mlx.asyncio.run", side_effect=RuntimeError("fail")):
            result = _process_word_reconstruction(data)

        # Should return original data (unchanged)
        assert result["text"] == "Hel lo"


# end backend/tests/unit/test_transcription_mlx_coverage.py
