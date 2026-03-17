# start src/pipeline/transcribe.py
"""Transcription using parakeet-mlx with word-level timestamps and transcript caching.

Merges the functionality of the old backend/src/transcription_mlx.py and
backend/src/transcript.py into a single, focused module. The Groq LLM word
reconstruction path has been removed; BPE sub-word tokens are merged locally
using a simple space-prefix heuristic instead.

Module: src/pipeline/transcribe.py
"""

import json
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Cache version — increment when the word dict format changes.
# v3 matches the version used in the old transcription_mlx.py so existing
# caches on disk remain valid.
_CACHE_VERSION: int = 3

# Default parakeet-mlx model hosted on MLX Community.
_DEFAULT_MODEL_ID: str = "mlx-community/parakeet-tdt-0.6b-v2"

try:
    import parakeet_mlx  # type: ignore[import-untyped]  # noqa: F401
    PARAKEET_AVAILABLE: bool = True
except ImportError:
    PARAKEET_AVAILABLE = False


class TranscriptionError(Exception):
    """Raised when video transcription fails."""


# ---------------------------------------------------------------------------
# BPE token merging
# ---------------------------------------------------------------------------


def merge_bpe_tokens(tokens: list[dict]) -> list[dict]:
    """Merge BPE sub-word tokens into whole words.

    parakeet-mlx outputs sub-word tokens where continuation tokens start with
    a space.  Tokens WITHOUT a leading space are continuations of the previous
    token and should be concatenated to it.

    The output timestamps are in milliseconds (int) with keys ``start_ms`` and
    ``end_ms``, matching the word data structure expected by the analyzer and
    subtitle generator.

    Args:
        tokens: Raw token dicts with ``text``, ``start``, ``end`` (seconds,
            floats).  Extra keys are ignored.

    Returns:
        Merged word dicts with ``text``, ``start_ms``, ``end_ms``
        (milliseconds, ints).  Empty or whitespace-only tokens are dropped
        before merging.
    """
    if not tokens:
        return []

    words: list[dict] = []
    current_text: str = ""
    current_start_ms: int = 0
    current_end_ms: int = 0

    for token in tokens:
        text: str = token.get("text", "")
        if not text or not text.strip():
            continue

        start_ms = int(token.get("start", 0) * 1000)
        end_ms = int(token.get("end", 0) * 1000)

        # A token that starts with a space begins a new word.
        # (parakeet uses leading-space convention for word boundaries.)
        is_new_word = text.startswith(" ") or not current_text

        if is_new_word and current_text:
            # Flush the accumulated word before starting the new one.
            words.append(
                {
                    "text": current_text.strip(),
                    "start_ms": current_start_ms,
                    "end_ms": current_end_ms,
                }
            )
            current_text = ""

        if not current_text:
            # First token of a new word — record its start time.
            current_start_ms = start_ms

        current_text += text
        current_end_ms = end_ms

    # Flush the final accumulated word.
    if current_text.strip():
        words.append(
            {
                "text": current_text.strip(),
                "start_ms": current_start_ms,
                "end_ms": current_end_ms,
            }
        )

    return words


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_path_for(video_path: str | Path) -> Path:
    """Return the .transcript_cache.json path adjacent to *video_path*."""
    p = Path(video_path)
    return p.parent / f"{p.stem}.transcript_cache.json"


def load_cached_transcript(video_path: str | Path) -> list[dict] | None:
    """Load cached transcript from ``.transcript_cache.json``.

    Returns ``None`` if no cache exists or cache is invalid / outdated.
    The cache file is stored alongside the video file.

    Args:
        video_path: Path to the video file.

    Returns:
        Cached word list, or ``None`` if not found or invalid.
    """
    cache_path = _cache_path_for(video_path)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r") as fh:
            data: dict = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("transcript_cache.load_failed", path=str(cache_path), error=str(exc))
        return None

    if data.get("version") != _CACHE_VERSION:
        logger.info(
            "transcript_cache.version_mismatch",
            path=str(cache_path),
            found=data.get("version"),
            expected=_CACHE_VERSION,
        )
        return None

    words = data.get("words")
    if not isinstance(words, list):
        return None

    return words


def save_transcript_cache(video_path: str | Path, words: list[dict]) -> None:
    """Save transcript to ``.transcript_cache.json`` alongside the video.

    Args:
        video_path: Path to the video file.
        words: Word list to cache.
    """
    cache_path = _cache_path_for(video_path)
    data = {
        "version": _CACHE_VERSION,
        "video_path": str(Path(video_path).resolve()),
        "words": words,
    }
    try:
        with cache_path.open("w") as fh:
            json.dump(data, fh, indent=2)
        logger.info(
            "transcript_cache.saved",
            path=str(cache_path),
            word_count=len(words),
            version=_CACHE_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("transcript_cache.save_failed", path=str(cache_path), error=str(exc))


# ---------------------------------------------------------------------------
# parakeet-mlx extraction helpers
# ---------------------------------------------------------------------------


def _tokens_from_result(result: object) -> list[dict]:
    """Extract raw token dicts from a parakeet-mlx AlignedResult.

    Prefers sentence-level tokens (word-level) over the flattened BPE token
    list.  Returns an empty list if neither source is available.

    Args:
        result: ``AlignedResult`` object returned by ``model.transcribe()``.

    Returns:
        List of raw token dicts with ``text``, ``start``, and ``end`` keys.
    """
    raw: list[dict] = []

    # Prefer sentence-level tokens — these are already word-level in parakeet.
    sentences = getattr(result, "sentences", None)
    if sentences:
        for sentence in sentences:
            tokens = getattr(sentence, "tokens", None) or []
            for token in tokens:
                text = getattr(token, "text", "")
                if not text or not text.strip():
                    continue
                start = getattr(token, "start", 0.0)
                end = getattr(token, "end", 0.0)
                if start >= end:
                    continue
                raw.append({"text": text, "start": start, "end": end})
        if raw:
            return raw

    # Fall back to top-level flattened tokens (BPE sub-words).
    top_tokens = getattr(result, "tokens", None) or []
    for token in top_tokens:
        text = getattr(token, "text", "")
        if not text or not text.strip():
            continue
        start = getattr(token, "start", 0.0)
        end = getattr(token, "end", 0.0)
        if start >= end:
            continue
        raw.append({"text": text, "start": start, "end": end})

    return raw


# ---------------------------------------------------------------------------
# Main transcription function
# ---------------------------------------------------------------------------


def transcribe_video(video_path: str | Path) -> list[dict]:
    """Transcribe a video file using parakeet-mlx.

    Returns word-level timestamps.  Uses cached results if available.

    Args:
        video_path: Path to the video file.

    Returns:
        List of word dicts: ``[{"text": str, "start_ms": int, "end_ms": int}, ...]``

    Raises:
        TranscriptionError: If transcription fails.
    """
    p = Path(video_path)
    if not p.exists():
        raise TranscriptionError(f"Video file not found: {p}")

    cached = load_cached_transcript(p)
    if cached is not None:
        logger.info("transcribe.cache_hit", path=str(p), word_count=len(cached))
        return cached

    if not PARAKEET_AVAILABLE:
        raise TranscriptionError(
            "parakeet-mlx is not installed. "
            "Install with: uv pip install parakeet-mlx"
        )

    logger.info("transcribe.start", path=str(p), model=_DEFAULT_MODEL_ID)

    try:
        from mlx.core import bfloat16  # type: ignore[import-untyped]
        from parakeet_mlx.utils import from_pretrained  # type: ignore[import-untyped]

        model = from_pretrained(_DEFAULT_MODEL_ID, dtype=bfloat16)
        logger.info("transcribe.model_loaded", model=_DEFAULT_MODEL_ID)

        result = model.transcribe(
            str(p),
            chunk_duration=120.0,
            overlap_duration=15.0,
        )
    except Exception as exc:
        raise TranscriptionError(f"parakeet-mlx transcription failed: {exc}") from exc

    raw_tokens = _tokens_from_result(result)
    logger.info("transcribe.raw_tokens", count=len(raw_tokens))

    words = merge_bpe_tokens(raw_tokens)
    logger.info("transcribe.words_merged", count=len(words))

    save_transcript_cache(p, words)
    return words


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_transcript_text(words: list[dict]) -> str:
    """Format word list into a plain text string for the AI analyzer.

    Each word is emitted with its timestamp range so the AI can select
    precise clip boundaries.

    Args:
        words: Word list with ``text``, ``start_ms``, ``end_ms`` keys.

    Returns:
        Formatted text suitable for LLM analysis.
        Format: ``"word [start_ms-end_ms] ..."``
    """
    parts: list[str] = []
    for word in words:
        text = word.get("text", "").strip()
        if not text:
            continue
        start_ms = word.get("start_ms", 0)
        end_ms = word.get("end_ms", 0)
        parts.append(f"{text} [{start_ms}-{end_ms}]")
    return " ".join(parts)


# end src/pipeline/transcribe.py
