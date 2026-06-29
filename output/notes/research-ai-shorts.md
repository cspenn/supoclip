# Research: Borrowable Techniques from ai-youtube-shorts-generator

**Date:** June 29, 2026  
**Target Repo:** https://github.com/samuraigpt/ai-youtube-shorts-generator  
**SupoClip Repo:** https://github.com/cspenn/supoclip (all-Python, parakeet-mlx, MediaPipe, ffmpeg)

---

## Executive Summary

The FOSS repo (ai-youtube-shorts-generator) implements a dual-mode (API + local) pipeline for short-form clip generation. While it uses incompatible stacks in some areas (Whisper instead of parakeet-mlx, OpenCV Haar instead of MediaPipe), it offers several high-impact techniques that SupoClip can adopt **within its architectural constraints**: long-video chunking with deduplication, two-stage LLM clip selection, frame-by-frame face tracking, JSON retry logic, and virality scoring as a separate dimension from content relevance.

---

## 1. Clip Selection & LLM Analysis

### What They Do

**Source Files:** `shorts_generator/highlights.py`, `shorts_generator/local/llm.py`

The FOSS repo uses a **two-stage LLM approach**:

1. **Content Classification:** First pass analyzes a transcript sample to determine content type (podcast, interview, tutorial, etc.) and estimate segment density (low/medium/high).
2. **Highlight Identification:** Second pass uses detailed virality criteria ranked by impact, explicitly looking for:
   - **HOOK MOMENTS** — statements creating immediate curiosity (first 3 seconds critical)
   - **EMOTIONAL PEAKS** — genuine surprise, laughter, anger, vulnerability
   - **COMPLETE SEGMENTS** — self-contained ideas without overlap

**Virality Scoring:** Each clip receives a 0–100 score. The system also implements **JSON retry logic** (up to 3 attempts) with progressive clarification prompts if the LLM returns malformed JSON.

**Duration Sweet Spot:** 45–90 seconds preferred, but system enforces configurable min/max.

**Long-Video Handling:** Videos longer than 30 minutes are chunked into 20-minute segments with 60-second overlap. Results are deduplicated by dropping clips with >50% overlap with higher-scoring alternatives.

### How SupoClip Currently Works

**Source:** `src/pipeline/analyze.py`

SupoClip uses a **single unified LLM call** via Pydantic AI or Groq structured outputs. Current implementation (src/pipeline/analyze.py:140-211):
- System prompt focuses on 5 selection criteria (hooks, valuable content, emotional moments, complete thoughts, entertaining)
- Clip duration enforced at 15–45 seconds by default (src/pipeline/analyze.py:155–161)
- Filler-word filtering removes clips starting with "And", "But", "Like", etc. (src/pipeline/analyze.py:251–318)
- Validation checks for zero-duration clips and minimum 5–10s segments
- Single-pass LLM call; no JSON retry logic

### Borrowable Techniques

**RECOMMENDATION 1: Implement Two-Stage LLM Analysis** (CATEGORY: good/enhancement)
- Add a classification step before highlight detection
- First LLM call: classify content type and segment density
- Second call: use content type context to refine clip selection
- **How to Map to SupoClip:** Extend `src/pipeline/analyze.py`:
  - Add a new function `classify_content(transcript_text: str) -> ContentClass`
  - Modify `analyze_transcript()` to call classification first, then pass result to the highlight analyzer
  - Keep Groq+Pydantic routing logic unchanged

**RECOMMENDATION 2: Add Long-Video Chunking & Deduplication** (CATEGORY: good/enhancement)
- For videos >30 minutes, chunk transcript into 20-minute segments with 60-second overlap
- Analyze each chunk independently
- Deduplicate results: if two clips overlap by >50%, keep the higher-scoring one
- **How to Map to SupoClip:** Add to `src/pipeline/analyze.py`:
  - Helper function `chunk_transcript(transcript: str, words: list[dict], chunk_size_s=1200, overlap_s=60) -> list[TranscriptChunk]`
  - Modify `analyze_transcript()` to detect long videos and apply chunking before LLM call
  - Add deduplication in post-processing: `deduplicate_segments(segments: list[TranscriptSegment], overlap_threshold=0.5) -> list[TranscriptSegment]`

**RECOMMENDATION 3: Implement JSON Retry Logic with Progressive Clarification** (CATEGORY: good/enhancement)
- Catch malformed JSON responses and retry up to 3 times
- On first retry, resend with clarification: "Previous response was invalid JSON. Please respond with **only** valid JSON."
- On second retry, provide an example of the expected format
- **How to Map to SupoClip:** Modify `src/pipeline/analyze.py:346–408` (`_analyze_with_groq_structured`) and `411–452` (`_analyze_with_pydantic_ai`):
  - Wrap LLM call in retry loop with exponential backoff
  - Add clarification prompts on retry
  - Raise `AnalysisError` only after 3 failed attempts

**RECOMMENDATION 4: Separate Virality Scoring from Content Relevance** (CATEGORY: good/enhancement)
- FOSS repo treats virality as a distinct 0–100 dimension separate from content relevance
- SupoClip's current `relevance_score` (0–1) conflates multiple dimensions
- **How to Map to SupoClip:** Extend `TranscriptSegment` model (src/pipeline/analyze.py:48–57):
  - Add new field: `virality_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Estimated viral potential")`
  - Modify system prompt to explicitly rate virality separately
  - Use virality score for sorting/ranking in UI (separate from relevance)

---

## 2. Transcription

### What They Do

**Source Files:** `shorts_generator/local/transcriber.py`

The FOSS repo uses **faster-whisper** (OpenAI's Whisper, optimized):
- Segment-level timestamps only (start/end of each transcript segment)
- No word-level timing extraction
- SRT cache format for transcript reuse
- Cache validation via file modification times

### How SupoClip Currently Works

**Source:** `src/pipeline/transcribe.py`

SupoClip uses **parakeet-mlx**:
- Word-level timing via BPE token merging (src/pipeline/transcribe.py:43–100)
- JSON cache format
- Word-level precision enables per-word subtitle timing (critical for TikTok/Reels)

### Borrowable Techniques

**RECOMMENDATION 5: Enhance Caching Strategy** (CATEGORY: good/enhancement)
- SupoClip already has word-level caching (better than FOSS)
- Add segment-level caching as a fallback/optimization
- Store segment boundaries alongside words for faster transcript reconstruction
- **How to Map to SupoClip:** Extend `src/pipeline/transcribe.py`:
  - Add segment boundary detection to cache (e.g., detect paragraph breaks, topic shifts)
  - Store both word-level and segment-level indices in cache JSON
  - Use segment index for fast seeking during clip selection

---

## 3. Face Detection & Active-Speaker Cropping

### What They Do

**Source Files:** `shorts_generator/local/clipper.py`

The FOSS repo implements **frame-by-frame horizontal face tracking**:
- Uses OpenCV Haar Cascade classifier for face detection
- Processes every frame to detect the largest face (assumed speaker)
- Applies smoothing factor of **0.15** to prevent jerky crop position changes
- Crops to 9:16 by moving a vertical window horizontally to follow the face

### How SupoClip Currently Works

**Source:** `src/pipeline/face_detect.py`

SupoClip uses **MediaPipe face detection**:
- Static single-frame analysis (extracts frame at `start_s + 1.0 seconds`)
- Detects face center and calculates crop box once (src/pipeline/face_detect.py:154–191)
- Falls back to frame center if no face detected (src/pipeline/face_detect.py:135–151)
- No frame-by-frame tracking or smoothing

### Borrowable Techniques

**IMPORTANT ARCHITECTURAL NOTE:** SupoClip's CLAUDE.md explicitly forbids OpenCV DNN/Haar fallbacks. All face detection must use MediaPipe only. Do NOT adopt FOSS's Haar Cascade approach.

**RECOMMENDATION 6: Implement Frame-by-Frame MediaPipe Face Tracking** (CATEGORY: good/enhancement)
- Replace static single-frame detection with multi-frame analysis
- Sample 5–10 frames evenly distributed across the segment
- Apply smoothing (factor 0.15) to interpolate face center across frames
- Generates smoother, more stable crops without jerky position jumps
- **How to Map to SupoClip:** Extend `src/pipeline/face_detect.py`:
  - Rename `detect_face_center()` to `detect_face_center_static()` (keep as fallback)
  - Add new function: `detect_face_track(video_path: Path, segment_start_s: float, segment_end_s: float, num_frames: int = 5) -> list[tuple[int, int] | None]`
  - Compute smoothed trajectory: `smooth_face_trajectory(positions: list[tuple[int, int] | None], factor=0.15) -> list[tuple[int, int] | None]`
  - Modify `generate_clip()` to compute an average/smoothed position from the trajectory
  - Store frame-by-frame positions for potential future use in ffmpeg filtergraph

**RECOMMENDATION 7: Detect Active Speaker via Mouth Movement** (CATEGORY: good/enhancement)
- MediaPipe provides face landmarks including mouth corners and lip vertices
- Mouth motion magnitude (distance between frames) correlates with speech activity
- Use mouth motion to prioritize faces and refine speaker detection
- **How to Map to SupoClip:** Extend `src/pipeline/face_detect.py`:
  - Modify `detect_face_center()` to extract face landmarks (line 58: `mp.solutions.face_detection` → `mp.solutions.face_mesh`)
  - Calculate mouth motion: `compute_mouth_motion(landmarks_frame1, landmarks_frame2) -> float`
  - Score faces by (confidence * mouth_motion_score) instead of confidence alone
  - Choose face with highest combined score across frames

---

## 4. Vertical Reframing (9:16 Cropping)

### What They Do

**Source:** `shorts_generator/local/clipper.py`

Two-stage ffmpeg + OpenCV approach:
1. ffmpeg cuts the video and preserves audio
2. OpenCV frame-by-frame processing: detects face, calculates crop box, applies smoothing

Uses OpenCV for video reading and frame processing; ffmpeg for re-encoding.

### How SupoClip Currently Works

**Source:** `src/pipeline/clip.py`

Single-stage ffmpeg approach:
- Face detection on a single representative frame (src/pipeline/clip.py:286–288)
- Calculate crop box once (src/pipeline/clip.py:294–300)
- ffmpeg handles trimming, cropping, scaling, subtitle burn-in, and H.264 encoding in one pass (src/pipeline/clip.py:326–336)
- No frame-by-frame processing

### Borrowable Techniques

**RECOMMENDATION 8: Enhance Crop Box Calculation with Multi-Frame Analysis** (CATEGORY: good/enhancement)
- Current implementation detects face at `start_s + 1.0 seconds` only
- Use multiple frame samples (e.g., 5 frames at 0%, 25%, 50%, 75%, 100% of segment)
- Compute average/median face position across samples
- Reduces chance of picking an unrepresentative frame (e.g., face turned away, blink)
- **How to Map to SupoClip:** Modify `src/pipeline/clip.py:241–354`:
  - Change `generate_clip()` to sample multiple frames during segment duration
  - Call enhanced `detect_face_track()` from Recommendation 6
  - Compute smoothed/averaged crop box from the trajectory

---

## 5. Subtitle Burn-In

### What They Do

**Source:** `shorts_generator/local/clipper.py`

The FOSS repo **does not implement subtitle burn-in**. It focuses only on face-centered vertical cropping.

### How SupoClip Currently Works

**Source:** `src/pipeline/subtitles.py`, `src/pipeline/clip.py:308–320`

SupoClip generates **.ass files** with per-word timing:
- pysubs2 creates SSAFile with one event per word (src/pipeline/subtitles.py:125–188)
- Custom font support via fontsdir parameter (src/pipeline/subtitles.py:24–48)
- Position at 75% down video (lower-middle, not bottom) for TikTok/Reels convention (src/pipeline/subtitles.py:46)
- ffmpeg burns subtitles via `-vf "ass=file.ass:fontsdir=fonts/"` (src/pipeline/clip.py:211–215)

### Borrowable Techniques

**REVERSE BORROW: SupoClip's subtitle system is superior and should not be modified.**

However, FOSS repo could benefit from SupoClip's approach. This is an area where SupoClip leads.

---

## 6. Pipeline Structure & Orchestration

### What They Do

**Source Files:** `shorts_generator/pipeline.py`, `main.py`

Sequential workflow: Download → Transcribe → Highlight Detection → Ranking → Cropping
- Supports two modes: API mode (MuAPI) and local mode (yt-dlp + local tools)
- Minimal status feedback (single print statement)
- Returns structured dict with all intermediate results
- Exception-based error handling

### How SupoClip Currently Works

**Source:** `src/services/video_service.py`, `src/main.py`

Sequential workflow: Download → Transcribe → Analyze → Generate Clips
- Single local mode (NiceGUI + FastAPI)
- WebSocket progress reporting for real-time UI updates (src/services/video_service.py:41–42)
- Database persistence of tasks and clips (src/services/video_service.py:97–157)
- Structured data models (ProcessingRequest, ProcessingResult)
- Exception handling with task status persistence

### Borrowable Techniques

**RECOMMENDATION 9: Add Content-Type Classification Step** (CATEGORY: good/enhancement)
- Align with Recommendation 1 (two-stage LLM)
- Add classification step before clip analysis in the pipeline
- **How to Map to SupoClip:** Modify `src/services/video_service.py`:
  - Add pipeline stage after transcription: call `classify_content()` before `analyze_transcript()`
  - Store content type in Task database (src/models.py)
  - Pass content type to second-stage LLM call for context

**RECOMMENDATION 10: Implement Clip Deduplication in Pipeline** (CATEGORY: good/enhancement)
- Add post-processing deduplication after `analyze_transcript()` returns results
- Align with Recommendation 2
- **How to Map to SupoClip:** Modify `src/services/video_service.py`:
  - After `analyze_transcript()` returns segments, call `deduplicate_segments()`
  - Filter out low-scoring clips that overlap >50% with higher-scoring ones
  - Log deduplication events for debugging

**RECOMMENDATION 11: Improve Status Message Granularity** (CATEGORY: good/enhancement)
- SupoClip already has WebSocket progress, but messages could be more specific
- FOSS prints "cropping X of Y candidates" — SupoClip could do similar for each stage
- **How to Map to SupoClip:** Enhance `src/services/video_service.py:97–132`:
  - Add detailed progress messages for each pipeline stage:
    - "Classifying content..."
    - "Analyzing for highlights..."
    - "Generating 7 clips (3 of 7 complete)"
    - "Deduplicating results..."

---

## 7. LLM Provider Integration

### What They Do

**Source Files:** `shorts_generator/local/llm.py`

Provider selection pattern:
- Routes to OpenAI or Gemini based on `LLM_PROVIDER` env var
- Runtime dependency validation (raises error if library not installed)
- Gemini explicitly sets JSON output format: `"response_mime_type": "application/json"`
- OpenAI lacks explicit JSON mode, relies on prompt instruction

### How SupoClip Currently Works

**Source:** `src/pipeline/analyze.py:325–452`

Sophisticated provider routing:
- Groq structured outputs (JSON schema mode) for Llama models (src/pipeline/analyze.py:326–338, 346–408)
- Pydantic AI agent for all other models (OpenAI, Anthropic, local) (src/pipeline/analyze.py:411–452)
- Local LLM support via OpenAI-compatible endpoint (src/pipeline/analyze.py:428–435)
- Supports multiple LLM providers: Groq, OpenAI, Anthropic, local (src/config.py)

### Borrowable Techniques

**RECOMMENDATION 12: Add Provider-Specific JSON Enforcement** (CATEGORY: good/enhancement)
- SupoClip supports Groq structured outputs (excellent)
- Could add explicit JSON mode for other providers (OpenAI supports `response_format={"type": "json_object"}`)
- Anthropic also supports structured output (available in Claude 3.5+)
- **How to Map to SupoClip:** Extend `src/pipeline/analyze.py`:
  - Add provider detection in `_analyze_with_pydantic_ai()` (around line 411)
  - For OpenAI models: enable JSON mode explicitly
  - For Anthropic models: use native structured output API
  - Keep Pydantic AI as fallback for unknown providers

---

## 8. Video Download

### What They Do

**Source Files:** `shorts_generator/local/downloader.py`

Uses yt-dlp for YouTube downloads. Supports resolution selection, format preferences.

### How SupoClip Currently Works

**Source:** `src/pipeline/download.py`

Uses yt-dlp, supports YouTube URLs and local file uploads. Validates YouTube URLs before processing.

### Borrowable Techniques

**No significant differences.** Both use yt-dlp appropriately.

---

## Summary Table: Borrowable Techniques

| Recommendation | Impact | Effort | SupoClip File | FOSS File | Priority |
|---|---|---|---|---|---|
| 1. Two-stage LLM analysis | High | Medium | `src/pipeline/analyze.py` | `highlights.py` | 1 |
| 2. Long-video chunking + deduplication | Medium | Medium | `src/pipeline/analyze.py` | `highlights.py` | 2 |
| 3. JSON retry logic | Medium | Low | `src/pipeline/analyze.py` | `highlights.py` | 3 |
| 4. Virality scoring | Medium | Low | `src/pipeline/analyze.py` | `highlights.py` | 4 |
| 5. Enhanced caching | Low | Low | `src/pipeline/transcribe.py` | `transcriber.py` | 5 |
| 6. Frame-by-frame face tracking | High | High | `src/pipeline/face_detect.py` | `clipper.py` | 1 |
| 7. Active speaker detection | Medium | Medium | `src/pipeline/face_detect.py` | `clipper.py` | 2 |
| 8. Multi-frame crop optimization | Medium | Medium | `src/pipeline/clip.py` | `clipper.py` | 3 |
| 9. Content classification step | Medium | Medium | `src/services/video_service.py` | `highlights.py` | 2 |
| 10. Clip deduplication in pipeline | Medium | Low | `src/services/video_service.py` | `highlights.py` | 3 |
| 11. Improved status messages | Low | Low | `src/services/video_service.py` | `pipeline.py` | 4 |
| 12. Provider-specific JSON enforcement | Low | Low | `src/pipeline/analyze.py` | `llm.py` | 5 |

---

## Architectural Constraints Respected

All recommendations respect SupoClip's hard rules:
- ✅ **Parakeet-mlx (not Whisper):** Transcription already uses parakeet; recommendation maintains this
- ✅ **MediaPipe only (not OpenCV/Haar):** All face detection recommendations use MediaPipe, explicitly forbid Haar Cascade
- ✅ **ffmpeg subprocess (not MoviePy):** Clipping already uses ffmpeg; no change recommended
- ✅ **Pure Python:** All recommendations are Python-only
- ✅ **No JavaScript/Node.js:** No TypeScript or build steps required

---

## Implementation Strategy

**Phase 1 (High Impact, Quick):**
- Recommendation 3: JSON retry logic (low effort, improves robustness)
- Recommendation 4: Virality scoring (low effort, improves ranking)

**Phase 2 (High Impact, Medium Effort):**
- Recommendation 1: Two-stage LLM analysis (requires prompt engineering)
- Recommendation 6: Frame-by-frame face tracking (requires multi-frame sampling)
- Recommendation 9: Content classification (requires new LLM prompt)

**Phase 3 (Medium-High Impact, Higher Effort):**
- Recommendation 2: Long-video chunking (complex logic, needs testing)
- Recommendation 7: Active speaker detection (requires landmark extraction)

**Future:**
- Recommendations 5, 8, 10, 11, 12 (lower priority, incremental improvements)

---

## References

**FOSS Repo:** https://github.com/samuraigpt/ai-youtube-shorts-generator
- Key files: `shorts_generator/highlights.py`, `shorts_generator/local/clipper.py`, `shorts_generator/local/transcriber.py`, `shorts_generator/pipeline.py`

**SupoClip Repo:** https://github.com/cspenn/supoclip
- Key files: `src/pipeline/analyze.py`, `src/pipeline/face_detect.py`, `src/pipeline/clip.py`, `src/pipeline/subtitles.py`, `src/pipeline/transcribe.py`, `src/services/video_service.py`

---

**Analysis completed:** June 29, 2026
