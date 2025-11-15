"""
Video transcription using parakeet-mlx (offline, Apple Silicon optimized).
Replaces AssemblyAI cloud API for local, privacy-preserving transcription.

Module: backend/src/transcription_mlx.py
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

try:
    from parakeet_mlx.utils import from_pretrained
    from mlx.core import bfloat16
except ImportError:
    from_pretrained = None
    bfloat16 = None

logger = logging.getLogger(__name__)


def transcribe_video_mlx(
    video_path: Path,
    model_id: str = "mlx-community/parakeet-tdt-0.6b-v2"
) -> Dict[str, Any]:
    """
    Transcribe video using parakeet-mlx (offline, Apple Silicon optimized).

    This replaces the AssemblyAI API call with local processing.
    Provides word-level timestamps compatible with existing clip generation.

    Args:
        video_path: Path to video file
        model_id: Model identifier from MLX Community
                 (default: "mlx-community/parakeet-tdt-0.6b-v2")

    Returns:
        Dict with transcription data:
            - text: Full transcript text
            - segments: List of segments with timing
            - words: List of word-level timestamps (AssemblyAI-compatible format)
            - language: Detected/specified language code

    Raises:
        ImportError: If parakeet-mlx not installed
        FileNotFoundError: If video file not found
        Exception: If transcription fails
    """
    if from_pretrained is None:
        raise ImportError(
            "parakeet-mlx not installed. Install with: uv pip install parakeet-mlx"
        )

    logger.info(f"🚀 Transcribing video with parakeet-mlx: {video_path}")

    # Check if file exists
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Check cache first - avoid re-transcribing
    cache_path = Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
    if cache_path.exists():
        logger.info(f"📝 Loading cached transcript: {cache_path}")
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")
            # Continue with fresh transcription

    try:
        # Load parakeet-mlx model
        logger.info(f"📝 Loading parakeet-mlx model: {model_id}...")
        model = from_pretrained(model_id, dtype=bfloat16)
        logger.info(f"✅ Model loaded. Starting transcription...")

        # Transcribe with word-level timing via streaming
        logger.info(f"📝 Starting parakeet transcription...")
        result = model.transcribe(
            str(video_path),
            chunk_duration=120.0,
            overlap_duration=15.0,
        )

        # Format result to match AssemblyAI structure for backward compatibility
        formatted_result = {
            "text": _extract_text_from_result(result),
            "segments": _extract_segments_from_result(result),
            "words": _extract_words_from_result(result),
            "language": "en",
        }

        # Cache for future use - avoid re-transcribing same video
        try:
            with open(cache_path, 'w') as f:
                json.dump(formatted_result, f, indent=2)
            logger.info(f"✅ Cached transcript: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache transcript: {e}")

        logger.info(f"✅ Transcription complete. Word count: {len(formatted_result['words'])}")
        return formatted_result

    except Exception as e:
        logger.error(f"❌ parakeet-mlx transcription failed: {e}", exc_info=True)
        raise


def _extract_text_from_result(result: Any) -> str:
    """
    Extract full transcript text from parakeet result.

    Args:
        result: AlignedResult from parakeet_mlx

    Returns:
        Full transcript text
    """
    if hasattr(result, 'sentences'):
        # parakeet returns sentences with tokens
        text_parts: List[str] = []
        for sentence in result.sentences:
            sentence_text = ""
            for token in sentence.tokens:
                if hasattr(token, 'word'):
                    sentence_text += token.word
            if sentence_text:
                text_parts.append(sentence_text)
        return " ".join(text_parts)
    return ""


def _extract_segments_from_result(result: Any) -> List[Dict[str, Any]]:
    """
    Extract segments from parakeet result.

    Converts parakeet output format to AssemblyAI-compatible format.

    Args:
        result: AlignedResult from parakeet_mlx

    Returns:
        List of segment dicts with timing information
    """
    segments: List[Dict[str, Any]] = []

    if hasattr(result, 'sentences'):
        for idx, sentence in enumerate(result.sentences):
            if sentence.tokens:
                # Get timing from first and last tokens
                start_time = _get_token_start_time(sentence.tokens[0])
                end_time = _get_token_end_time(sentence.tokens[-1])

                # Build segment text
                segment_text = ""
                for token in sentence.tokens:
                    if hasattr(token, 'word'):
                        segment_text += token.word

                segments.append({
                    "id": idx,
                    "seek": 0,
                    "start": start_time,
                    "end": end_time,
                    "text": segment_text.strip(),
                    "tokens": [t.id for t in sentence.tokens if hasattr(t, 'id')],
                    "temperature": 0.0,
                    "avg_logprob": 0.0,
                    "compression_ratio": 0.0,
                    "no_speech_prob": 0.0,
                })

    return segments


def _extract_words_from_result(result: Any) -> List[Dict[str, Any]]:
    """
    Extract word-level timestamps from parakeet result.

    Converts parakeet output format to AssemblyAI-compatible format
    for seamless integration with existing clip generation code.

    Args:
        result: AlignedResult from parakeet_mlx

    Returns:
        List of word dicts with:
            - text: Word text
            - start: Start time in milliseconds
            - end: End time in milliseconds
            - confidence: Confidence score (0-1)
    """
    words: List[Dict[str, Any]] = []

    if hasattr(result, 'sentences'):
        for sentence in result.sentences:
            for token in sentence.tokens:
                if hasattr(token, 'word') and token.word.strip():
                    start_ms = _get_token_start_time(token)
                    end_ms = _get_token_end_time(token)

                    # Skip if timing is invalid
                    if start_ms >= end_ms:
                        continue

                    words.append({
                        "text": token.word.strip(),
                        "start": start_ms,
                        "end": end_ms,
                        "confidence": 1.0,
                    })

    return words


def _get_token_start_time(token: Any) -> int:
    """
    Get start time in milliseconds from parakeet token.

    Args:
        token: AlignedToken from parakeet_mlx

    Returns:
        Start time in milliseconds
    """
    if hasattr(token, 'start_ts'):
        # start_ts is in seconds (float), convert to milliseconds
        return int(token.start_ts * 1000)
    elif hasattr(token, 'stime'):
        # Alternative attribute name
        return int(token.stime * 1000)
    return 0


def _get_token_end_time(token: Any) -> int:
    """
    Get end time in milliseconds from parakeet token.

    Args:
        token: AlignedToken from parakeet_mlx

    Returns:
        End time in milliseconds
    """
    if hasattr(token, 'end_ts'):
        # end_ts is in seconds (float), convert to milliseconds
        return int(token.end_ts * 1000)
    elif hasattr(token, 'etime'):
        # Alternative attribute name
        return int(token.etime * 1000)
    return 0


def get_video_transcript_mlx(video_path: Path) -> str:
    """
    Get full transcript text from video.

    Convenience wrapper that returns just the text string.

    Args:
        video_path: Path to video file

    Returns:
        Full transcript text
    """
    result = transcribe_video_mlx(video_path)
    return result.get("text", "")


def load_cached_transcript_mlx(video_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load cached transcript if available without re-transcribing.

    Args:
        video_path: Path to video file

    Returns:
        Cached transcript dict, or None if not cached
    """
    cache_path = Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"

    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")

    return None


# end backend/src/transcription_mlx.py
