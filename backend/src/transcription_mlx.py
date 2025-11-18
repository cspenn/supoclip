"""
Video transcription using parakeet-mlx (offline, Apple Silicon optimized).
Replaces AssemblyAI cloud API for local, privacy-preserving transcription.

Module: backend/src/transcription_mlx.py
"""
import logging
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

try:
    from parakeet_mlx.utils import from_pretrained  # type: ignore
    from mlx.core import bfloat16  # type: ignore
except ImportError:
    from_pretrained = None  # type: ignore
    bfloat16 = None  # type: ignore

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None  # type: ignore

from .config import Config

logger = logging.getLogger(__name__)

# Cache version for transcript cache files
# Increment this when cache format changes or when new processing is added (e.g., word reconstruction)
# This ensures old caches are invalidated and re-transcription occurs with new features
TRANSCRIPT_CACHE_VERSION = 2  # v2: Added word reconstruction via Groq LLM (2025-11-17)


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
                cached_data = json.load(f)

            # Check cache version for forward compatibility
            cached_version = cached_data.get("_cache_version", 1)  # Default to v1 for old caches
            if cached_version != TRANSCRIPT_CACHE_VERSION:
                logger.info(
                    f"Cache version mismatch (cached: v{cached_version}, current: v{TRANSCRIPT_CACHE_VERSION}). "
                    f"Re-transcribing to ensure word reconstruction is applied..."
                )
                # Delete old cache to force re-transcription
                cache_path.unlink()
            else:
                # Cache version matches, use it
                return cached_data
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
        formatted_result: Dict[str, Any] = {
            "text": _extract_text_from_result(result),
            "segments": _extract_segments_from_result(result),
            "words": _extract_words_from_result(result),
            "language": "en",
        }

        # Reconstruct broken words from parakeet-mlx tokenization (if enabled)
        # parakeet-mlx uses BPE tokenization which returns sub-word tokens
        # Use Groq LLM to reconstruct complete words while preserving timing
        config = Config()
        words_list: List[Dict[str, Any]] = (
            list(formatted_result.get("words", []))  # type: ignore
        )
        if words_list and config.reconstruct_words_with_llm:
            logger.info("Reconstructing broken sub-word tokens with Groq LLM...")
            try:
                reconstructed_words = asyncio.run(
                    _reconstruct_words_with_llm(words_list)
                )
                formatted_result["words"] = reconstructed_words
                # Update text with reconstructed words
                formatted_result["text"] = " ".join(
                    w["text"] for w in reconstructed_words
                )
                logger.info(
                    f"Word reconstruction complete: {len(formatted_result['words'])} words"
                )
            except Exception as e:
                logger.warning(
                    f"Word reconstruction failed, using original tokens: {e}"
                )
                # Continue with broken tokens if reconstruction fails

        # Cache for future use - avoid re-transcribing same video
        # Include cache version to invalidate old caches when format changes
        formatted_result["_cache_version"] = TRANSCRIPT_CACHE_VERSION
        try:
            with open(cache_path, "w") as f:
                json.dump(formatted_result, f, indent=2)
            logger.info(f"Cached transcript (v{TRANSCRIPT_CACHE_VERSION}): {cache_path}")
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


async def _reconstruct_words_with_llm(
    broken_words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Reconstruct complete words from sub-word tokens using Groq LLM.

    parakeet-mlx returns sub-word tokens (e.g., ["Y", "es", "."]) instead of
    complete words (["Yes", "."]) due to BPE tokenization. This function uses
    Groq's LLM to reconstruct complete words while preserving timing information.

    Args:
        broken_words: List of word dicts with sub-word text and timing
                     Format: [{"text": "Y", "start": 0, "end": 100}, ...]

    Returns:
        List of word dicts with reconstructed complete words and re-aligned timing
        Format: [{"text": "Yes", "start": 0, "end": 200}, ...]

    Raises:
        ValueError: If Groq API key not configured
        Exception: If API call fails
    """
    # Check if Groq is available and configured
    if AsyncGroq is None:
        logger.warning(
            "Groq not available, skipping word reconstruction. "
            "Install with: uv pip install groq"
        )
        return broken_words

    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        logger.warning(
            "GROQ_API_KEY not configured, skipping word reconstruction. "
            "Captions may contain broken words."
        )
        return broken_words

    # Extract broken text
    broken_text = " ".join(word["text"] for word in broken_words)
    if not broken_text.strip():
        return broken_words

    logger.info(f"Reconstructing {len(broken_words)} broken tokens with Groq LLM...")

    try:
        client = AsyncGroq(api_key=groq_api_key)

        # Create prompt for word reconstruction
        reconstruction_prompt = f"""Fix this broken transcription by combining sub-word tokens into complete words.
The input has been tokenized at sub-word level (character fragments, BPE tokens).
Reconstruct it into proper complete words with correct spacing and punctuation.

Rules:
1. Only reconstruct - do NOT add explanations or extra text
2. Preserve all punctuation
3. Return ONLY the corrected text, nothing else
4. Keep original meaning - fix only the broken word boundaries

Input: {broken_text}
Output:"""

        response = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": reconstruction_prompt}],
            temperature=0.1,  # Low temperature for deterministic output
            max_tokens=2000,
        )

        reconstructed_text = ""
        if response.choices and response.choices[0].message.content:
            reconstructed_text = response.choices[0].message.content.strip()

        if not reconstructed_text:
            logger.warning("Groq returned empty response, using original tokens")
            return broken_words

        logger.info(
            f"Reconstruction complete. Original: '{broken_text[:50]}...' "
            f"→ Reconstructed: '{reconstructed_text[:50]}...'"
        )

        # Re-align timing: map reconstructed words to original token timings
        reconstructed_words = _align_reconstructed_words(
            broken_words, reconstructed_text
        )

        logger.info(
            f"Timing re-aligned: {len(broken_words)} broken tokens "
            f"→ {len(reconstructed_words)} reconstructed words"
        )

        return reconstructed_words

    except Exception as e:
        logger.error(f"Word reconstruction failed: {e}")
        logger.warning("Falling back to broken tokens")
        return broken_words


def _align_reconstructed_words(
    broken_words: List[Dict[str, Any]], reconstructed_text: str
) -> List[Dict[str, Any]]:
    """
    Re-align timing information from broken tokens to reconstructed words.

    Algorithm:
    1. Split reconstructed text into words
    2. For each reconstructed word, find matching broken tokens
    3. Assign timing from first to last matching broken token

    Args:
        broken_words: Original broken tokens with timing
        reconstructed_text: Reconstructed text from LLM

    Returns:
        List of word dicts with reconstructed text and aligned timing
    """
    # Split reconstructed text into words (preserve punctuation attached to words)
    reconstructed_words_list = reconstructed_text.split()

    if not reconstructed_words_list:
        return broken_words

    aligned_words: List[Dict[str, Any]] = []
    broken_idx = 0

    for reconstructed_word in reconstructed_words_list:
        if broken_idx >= len(broken_words):
            # No more broken tokens, stop alignment
            break

        # Find how many broken tokens make up this reconstructed word
        # by matching character count approximately
        reconstructed_len = len(reconstructed_word)

        # Collect tokens that form this word
        word_start_ms = broken_words[broken_idx]["start"]
        word_text = ""
        token_count = 0

        while broken_idx < len(broken_words):
            token_text = broken_words[broken_idx]["text"]
            word_text += token_text
            broken_idx += 1
            token_count += 1

            # Check if we've matched the reconstructed word
            if len(word_text) >= reconstructed_len * 0.8:  # 80% match threshold
                break

        # Use end time of last matched token
        word_end_ms = (
            broken_words[broken_idx - 1]["end"] if token_count > 0 else word_start_ms
        )

        # Average confidence from matched tokens
        confidence = (
            sum(
                broken_words[i].get("confidence", 1.0)
                for i in range(max(0, broken_idx - token_count), broken_idx)
            )
            / token_count
            if token_count > 0
            else 1.0
        )

        aligned_words.append(
            {
                "text": reconstructed_word,
                "start": word_start_ms,
                "end": word_end_ms,
                "confidence": confidence,
            }
        )

    return aligned_words


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
