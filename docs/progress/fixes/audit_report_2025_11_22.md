# Audit Report: Video Generation Issues
**Date:** November 22, 2025
**Status:** Completed
**Auditor:** Antigravity

## Executive Summary
This audit investigated four persistent issues with the video generation pipeline:
1.  Uploaded logo not appearing on video.
2.  Video captions remaining cut off.
3.  Video content not matching captions.
4.  Video content not matching transcript excerpts.

**Key Finding:** The backend code for passing logo parameters appears **correct** and fully implemented, contradicting previous reports. The failure likely lies in runtime configuration, frontend data transmission, or file system access, rather than missing parameter passing logic in the backend.

## Detailed Findings

### 1. Logo Not on Video
**Status:** Code Implementation Verified (Backend)
**Previous Diagnosis:** "Worker task ... does NOT accept logo parameters."
**Current Audit Finding:**
-   **Backend Chain is Intact:** The parameter `logo_path` is correctly passed through the entire chain:
    -   `api/routes/tasks.py` (Endpoint) -> `JobQueue`
    -   `workers/tasks.py` (Worker) -> `TaskService`
    -   `services/task_service.py` -> `VideoService`
    -   `services/video_service.py` -> `video_utils.py`
    -   `video_utils.py` (`create_optimized_clip`) -> `ImageClip` overlay.
-   **Potential Root Causes:**
    -   **Frontend:** The frontend might not be sending the `logo_path` or `logo_corner_position` correctly in the request.
    -   **User Preferences:** The `UserPreferencesService` might return `None` for `logo_path` if the user hasn't explicitly saved it or if the session lookup fails.
    -   **File System:** The worker process might not have read permissions for the logo file path, or the path might be relative/invalid in the worker's context.
    -   **Deployment:** The running worker instance might be using an older version of the code (cache/deployment issue).

### 2. Video Captions Cut Off
**Status:** Issue Identified (Rendering Logic)
**Root Cause:**
-   The `TextClip` generation uses `method="label"` which generally fits text to a box, but descenders (g, j, p, q, y) combined with a thick `stroke_width` can still extend beyond the calculated bounding box.
-   The `Margin` effect adds padding *around* the generated clip but does not change the internal rendering canvas of the `TextClip` itself. If ImageMagick clips the text during generation, the `Margin` effect comes too late.
**Proposed Fix:**
-   **Increase Bottom Margin:** Increase the dynamic bottom margin calculation in `SubtitleTextClipCreator` to be more aggressive (e.g., `0.6 * font_size`).
-   **Padding in TextClip:** Investigate if `TextClip` accepts a `size` argument slightly larger than the font size to allow for drawing outside the glyph bounds.

### 3. Video Content vs. Captions Mismatch
**Status:** Issue Identified (Synchronization)
**Root Cause:**
-   **Tokenization:** `parakeet-mlx` produces sub-word tokens. The reconstruction logic (`_reconstruct_words_with_llm`) attempts to merge them, but if the LLM hallucinates or alters the text, the captions will drift from the audio.
-   **Timing:** Even with accurate words, if the `TextClip` duration doesn't perfectly match the audio duration of the spoken word, visual drift occurs.
**Proposed Fix:**
-   **Strict Reconstruction:** Enforce stricter constraints on the LLM to *only* merge tokens and never alter/add/remove words.
-   **Visual Debugging:** Generate a debug video with the raw transcript timestamps overlaid to verify `parakeet-mlx` accuracy.

### 4. Video Content vs. Transcript Excerpt Mismatch
**Status:** Issue Identified (Cutting Precision)
**Root Cause:**
-   **Audio Bleed:** The AI selects a text segment, but the corresponding audio might start slightly before or end slightly after the precise timestamps provided by the transcriber (due to breath, co-articulation).
-   **FFmpeg Cutting:** `subclipped` cuts at exact timestamps, which might be too tight.
**Proposed Fix:**
-   **Buffer:** Add a configurable "audio buffer" (e.g., 0.1s - 0.2s) to the start and end of each clip to ensure the complete audio phrase is captured.

## Fix Plan

### Phase 1: Logo Verification (Immediate)
1.  **Verify Frontend Payload:** Check browser network logs to ensure `POST /tasks` includes `logo_path` (or that the backend correctly retrieves it from prefs).
2.  **Add Logging:** Add explicit logs in `workers/tasks.py` and `video_utils.py` to print the received `logo_path` and the result of `os.path.exists(logo_path)`.
3.  **Test with Hardcoded Path:** Temporarily hardcode a known valid logo path in `video_utils.py` to verify the overlay logic works in isolation.

### Phase 2: Caption & Content Fixes
1.  **Adjust Margins:** Update `backend/src/video_utils.py` to increase the bottom margin factor for `TextClip`.
2.  **Add Buffer:** Update `create_optimized_clip` to add `0.15s` padding to `start_time` and `end_time` (clamped to video duration).
3.  **LLM Constraints:** Review and tighten the system prompt for `_reconstruct_words_with_llm` in `transcription_mlx.py`.

## Conclusion
The backend code is structurally sound regarding the logo parameter passing. The focus should shift to runtime verification and frontend/configuration debugging. The caption and content mismatch issues require tuning of rendering parameters and timing buffers.
