"""
Video transcription using MLX Whisper (offline, Apple Silicon optimized).
Replaces AssemblyAI cloud API for local, privacy-preserving transcription.

Module: backend/src/transcription_mlx.py
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

try:
    import mlx_whisper
except ImportError:
    mlx_whisper = None

logger = logging.getLogger(__name__)


def transcribe_video_mlx(
    video_path: Path,
    model_size: str = "medium"
) -> Dict[str, Any]:
    """
    Transcribe video using MLX Whisper (offline, Apple Silicon optimized).

    This replaces the AssemblyAI API call with local processing.
    Provides word-level timestamps compatible with existing clip generation.

    Args:
        video_path: Path to video file
        model_size: Model size - tiny, base, small, medium, large
                   (medium recommended for speed/accuracy balance)

    Returns:
        Dict with transcription data:
            - text: Full transcript text
            - segments: List of segments with timing
            - words: List of word-level timestamps (AssemblyAI-compatible format)
            - language: Detected/specified language code

    Raises:
        ImportError: If mlx_whisper not installed
        FileNotFoundError: If video file not found
        Exception: If transcription fails
    """
    if mlx_whisper is None:
        raise ImportError(
            "mlx-whisper not installed. Install with: uv pip install mlx-whisper"
        )

    logger.info(f"🚀 Transcribing video with MLX Whisper ({model_size}): {video_path}")

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
        # MLX Whisper transcription with word-level timing
        logger.info(f"📝 Starting MLX transcription (model: {model_size})...")
        result = mlx_whisper.transcribe(
            str(video_path),
            path_or_hf_repo=f"mlx-community/whisper-{model_size}",
            word_level_timings=True,  # Enable word-level timestamps
            language="en",
            fp16=False,
        )

        # Format result to match AssemblyAI structure for backward compatibility
        formatted_result = {
            "text": result.get("text", ""),
            "segments": result.get("segments", []),
            "words": _extract_words_from_segments(result.get("segments", [])),
            "language": result.get("language", "en"),
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
        logger.error(f"❌ MLX transcription failed: {e}", exc_info=True)
        raise


def _extract_words_from_segments(segments: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract word-level timestamps from Whisper segments.

    Converts Whisper output format to AssemblyAI-compatible format
    for seamless integration with existing clip generation code.

    Args:
        segments: List of segment dicts from Whisper result

    Returns:
        List of word dicts with:
            - text: Word text
            - start: Start time in milliseconds
            - end: End time in milliseconds
            - confidence: Confidence score (0-1)
    """
    words: List[Dict[str, Any]] = []

    for segment in segments:
        # Handle segments with word-level data
        if "words" in segment:
            for word_data in segment["words"]:
                words.append({
                    "text": word_data.get("word", "").strip(),
                    "start": int(word_data.get("start", 0) * 1000),  # seconds to ms
                    "end": int(word_data.get("end", 0) * 1000),
                    "confidence": word_data.get("probability", 1.0),
                })
        # Fallback: if no word-level data, create one entry per segment
        elif "text" in segment:
            words.append({
                "text": segment.get("text", "").strip(),
                "start": int(segment.get("start", 0) * 1000),
                "end": int(segment.get("end", 0) * 1000),
                "confidence": 1.0,
            })

    return words


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
