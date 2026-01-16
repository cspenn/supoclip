# Gemini Debug Audit Report - January 16, 2026

## Executive Summary

The persistent misalignment between audio, video, and text captions in the SupoClip application is caused by a **flawed architectural decision** in the transcription pipeline. The system attempts to use a Large Language Model (LLM) to "fix" sub-word tokens from the transcription engine and then deterministically map old timestamps to the new text using an unreliable character-length heuristic. This process is inherently unstable and leads to cumulative drift.

Additionally, extreme performance inefficiencies in the subtitle rendering engine and aggressive filtering of "short" words contribute to missing captions and system instability.

## Critical Issues

### 1. The "Reconstruction" Trap (Primary Cause of Alignment Drift)

**Location:** `backend/src/transcription_mlx.py`
**Functions:** `_reconstruct_words_with_llm`, `_align_reconstructed_words`
**Severity:** Critical

**The Logic:**
The system takes raw, time-stamped tokens from the MLX transcription model (which are often sub-word fragments like "go", "ing") and sends them to an LLM with the instruction to "merge sub-word tokens" into whole words. It then attempts to assign the original timestamps to these new words based on **character length**.

**The Flaw:**
LLMs are probabilistic, not deterministic string manipulators.
1.  **Hallucination/Correction:** If the LLM "corrects" grammar (e.g., changing "gonna" to "going to") or changes punctuation, the character count changes.
2.  **Greedy Alignment:** The `_align_reconstructed_words` function iterates through the original tokens and consumes them until the length matches the LLM's word. If the LLM output doesn't perfectly match the token stream's implied length, the alignment logic desynchronizes.
3.  **Cumulative Drift:** Once one word is misaligned, *every subsequent word* uses the wrong starting token index, causing the text to drift further and further away from the audio.

**Evidence:**
- `config.py`: `self.reconstruct_words_with_llm` defaults to `True`.
- `transcription_mlx.py`: The code explicitly relies on `len(word_text) >= reconstructed_len * 0.8` to decide when a word ends. This is a heuristic, not a robust alignment algorithm.

### 2. Silent Deletion of Captions

**Location:** `backend/src/video_utils.py`
**Function:** `SubtitleClipBuilder.build_clips`
**Severity:** High

**The Logic:**
```python
if word_duration < 0.05:
    logger.debug(f"Skipping very short word...")
    continue
```

**The Flaw:**
When the alignment logic (Issue #1) fails, it often incorrectly calculates the duration of a word, sometimes squeezing it into a tiny time window (e.g., < 50ms). This filter silently deletes these words from the video. The user hears the word, but the caption never appears.

### 3. Catastrophic Performance in Rendering

**Location:** `backend/src/video_utils.py`, `backend/src/subtitle_renderer.py`
**Function:** `SubtitleTextClipCreator.create_text_clip`
**Severity:** High

**The Logic:**
```python
with BrowserSubtitleRenderer() as renderer:
    # ... render text
```

**The Flaw:**
The `BrowserSubtitleRenderer` launches a headless Chromium instance (via Playwright) in its `__init__` or `start` method. Because `create_text_clip` is called inside a loop for *every single word* (to determine line breaks and generate clips), the system launches and kills hundreds or thousands of browser instances per video.

**Impact:**
-   **Extreme Latency:** Generating clips takes significantly longer than necessary.
-   **Instability:** Rapidly spawning browser processes can lead to resource exhaustion, timeouts, and "ghost" failures where captions simply don't generate.

### 4. Complexity Hotspots

Static analysis tools (`radon`) identified several functions with high cyclomatic complexity (CC > 9), making them prone to bugs and difficult to maintain:
-   `backend/src/transcription_mlx.py`: `_extract_words_from_result` (CC 9), `_reconstruct_words_with_llm` (CC 9).
-   `backend/src/video_utils.py`: `resolve_font_path` (CC 10), `detect_faces_in_clip` (CC 5+ but calls complex chains).
-   `backend/src/ai_structured.py`: `_validate_and_adjust_segments` (CC 10).

## Recommendations

1.  **Disable LLM Reconstruction:** Immediately set `RECONSTRUCT_WORDS_WITH_LLM=false` in the environment or change the default in `config.py`. The raw tokens from `parakeet-mlx` might be imperfectly spaced, but they are **time-accurate**.
2.  **Rewrite Alignment Logic:** If word reconstruction is necessary, use a deterministic algorithm (like Dynamic Time Warping or Needleman-Wunsch) to align the original tokens with the clean text, rather than a greedy character-length heuristic. Or, better yet, use a transcription model that outputs word-level timestamps directly (like WhisperX).
3.  **Singleton Browser Instance:** Refactor `SubtitleTextClipCreator` to accept an existing `BrowserSubtitleRenderer` instance rather than creating a new one. The renderer should be started once per job, used for all words, and then closed.
4.  **Remove Arbitrary Filters:** Remove the `< 0.05s` duration filter. If a word is short, it should still be shown (perhaps with a minimum display time enforced by extending into the next word's time, not by deleting it).

## Tooling Output Summary

-   **Radon (Complexity):** Confirmed high complexity in transcription and video processing logic.
-   **Mypy (Type Checking):** Failed due to dependency syntax errors (`mlx`), indicating a fragile development environment.
-   **Manual Inspection:** Confirmed the existence of non-deterministic logic in critical synchronization paths.

---
*Audit completed by Gemini Agent on 2026-01-16.*
