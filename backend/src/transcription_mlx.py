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
    video_path: Path, model_id: str = "mlx-community/parakeet-tdt-0.6b-v2"
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

    logger.info(f"Transcribing video with parakeet-mlx: {video_path}")

    # Check if file exists
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Check cache first - avoid re-transcribing
    cache_path = (
        Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
    )
    if cache_path.exists():
        logger.info(f"Loading cached transcript: {cache_path}")
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")
            # Continue with fresh transcription

    try:
        # Load parakeet-mlx model
        logger.info(f"Loading parakeet-mlx model: {model_id}...")
        model = from_pretrained(model_id, dtype=bfloat16)
        logger.info("Model loaded. Starting transcription...")

        # Transcribe with word-level timing via streaming
        logger.info("Starting parakeet transcription...")
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
            with open(cache_path, "w") as f:
                json.dump(formatted_result, f, indent=2)
            logger.info(f"Cached transcript: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache transcript: {e}")

        logger.info(
            f"Transcription complete. Word count: {len(formatted_result['words'])}"
        )
        return formatted_result

    except Exception as e:
        logger.error(f"parakeet-mlx transcription failed: {e}", exc_info=True)
        raise


def _extract_text_from_result(result: Any) -> str:
    """
    Extract full transcript text from parakeet result.

    Args:
        result: AlignedResult from parakeet_mlx

    Returns:
        Full transcript text
    """
    # parakeet-mlx AlignedResult already has .text attribute
    if hasattr(result, "text"):
        return result.text
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

    if hasattr(result, "sentences"):
        for idx, sentence in enumerate(result.sentences):
            # AlignedSentence has .text, .start, .end attributes directly
            # .start and .end are in seconds (float), convert to milliseconds
            start_ms = int(sentence.start * 1000) if hasattr(sentence, "start") else 0
            end_ms = int(sentence.end * 1000) if hasattr(sentence, "end") else 0

            segments.append(
                {
                    "id": idx,
                    "seek": 0,
                    "start": start_ms,
                    "end": end_ms,
                    "text": sentence.text if hasattr(sentence, "text") else "",
                    "tokens": [t.id for t in sentence.tokens if hasattr(t, "id")],
                    "temperature": 0.0,
                    "avg_logprob": 0.0,
                    "compression_ratio": 0.0,
                    "no_speech_prob": 0.0,
                }
            )

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

    # AlignedResult has .tokens attribute - a flattened list of all AlignedToken objects
    if hasattr(result, "tokens"):
        for token in result.tokens:
            # AlignedToken has .text, .start, .end, .confidence attributes
            if hasattr(token, "text") and token.text.strip():
                # .start and .end are in seconds (float), convert to milliseconds
                start_ms = int(token.start * 1000) if hasattr(token, "start") else 0
                end_ms = int(token.end * 1000) if hasattr(token, "end") else 0

                # Skip if timing is invalid
                if start_ms >= end_ms:
                    continue

                words.append(
                    {
                        "text": token.text.strip(),
                        "start": start_ms,
                        "end": end_ms,
                        "confidence": token.confidence
                        if hasattr(token, "confidence")
                        else 1.0,
                    }
                )

    return words


def _get_token_start_time(token: Any) -> int:
    """
    Get start time in milliseconds from parakeet token.

    Args:
        token: AlignedToken from parakeet_mlx

    Returns:
        Start time in milliseconds
    """
    # AlignedToken has .start attribute in seconds (float)
    if hasattr(token, "start"):
        return int(token.start * 1000)
    return 0


def _get_token_end_time(token: Any) -> int:
    """
    Get end time in milliseconds from parakeet token.

    Args:
        token: AlignedToken from parakeet_mlx

    Returns:
        End time in milliseconds
    """
    # AlignedToken has .end attribute in seconds (float)
    if hasattr(token, "end"):
        return int(token.end * 1000)
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
    cache_path = (
        Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
    )

    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")

    return None


# end backend/src/transcription_mlx.py
