# SupoClip FOSS Research: ClipsAI Techniques

**Date:** 2026-06-29  
**Repository:** https://github.com/ClipsAI/clipsai  
**Focus Areas:** Clip selection algorithm, video cropping/reframing, subtitle handling, transcription approach, quality optimization

---

## Executive Summary

ClipsAI (Python, 91% Python codebase) is an open-source alternative to OpusClip designed specifically for **audio-centric, narrative-based content** (podcasts, interviews, speeches, sermons). It uses a **TextTiling + BERT embeddings** approach for clip selection, **Pyannote-based speaker diarization** for dynamic reframing, and **WhisperX** for transcription. Key borrowable techniques include semantic topic segmentation, multi-frame speaker tracking, and diarization-based cropping strategies.

---

## 1. Clip Selection Algorithm: TextTiling + BERT Embeddings

### How ClipsAI Does It

ClipsAI uses a **topic-segmentation approach** rather than semantic scoring:

- **Algorithm:** TextTiling with BERT embeddings (improvement over original TextTiling formulation)
- **Input:** Transcript from WhisperX (word-level timing)
- **Process:** Analyzes "word usage and distribution patterns" to detect topic shifts at sentence granularity
- **Output:** Segments with natural topic boundaries, varying lengths optimized for short/long-form content
- **Key Advantage:** Identifies structural "complete thoughts" without requiring LLM inference for every clip

**Technical Details:**
- TextTiling is a classic NLP algorithm by Marti A. Hearst (1990s) that segments text into topic-coherent chunks
- BERT embeddings enhance this by using modern transformer-based semantic similarity
- No tunable parameters exposed in public API; detection is deterministic and lightweight
- Operates at sentence level, produces clips of varying lengths

### SupoClip's Current Approach

SupoClip uses **LLM-based clip selection** (`src/pipeline/analyze.py`):
- Routes to Groq structured outputs (Llama models) or Pydantic AI agents
- Relies on LLM prompt engineering to define "good clip" criteria
- Manual validation filters: minimum/maximum duration (default 15–45s), filler-word detection, zero-duration rejection
- Produces 3–7 clips per video with relevance scores (0.0–1.0)

**Code Reference:** `src/pipeline/analyze.py:140-212` (system prompt), `src/pipeline/analyze.py:251-318` (validation)

### Borrowable Technique: Hybrid Segmentation + LLM Scoring

**Recommendation:** Add TextTiling + BERT as an **optional first-pass segmentation** layer before LLM scoring:

1. **Stage 1 (Lightweight Segmentation):** Use TextTiling/BERT to pre-segment the transcript into topic-coherent chunks
   - Identifies natural topic boundaries without LLM inference cost
   - Reduces hallucination risk (clip boundaries are derived from text structure, not LLM creativity)
   - Candidates become smaller, more focused regions for LLM scoring

2. **Stage 2 (LLM Scoring):** Pass TextTiling segments to the LLM as candidates; LLM ranks/merges/adjusts based on virality/engagement criteria
   - LLM focuses on *ranking* (not blind generation) — faster, cheaper, more reliable
   - Maintains SupoClip's flexibility for custom prompts and heuristics

**Implementation Path:**
- Add optional dependency: `pip install texttiling` or use Hugging Face Transformers BERT model for embeddings
- Create new module: `src/pipeline/segmentation.py` with `texttile_segments()` function
- Modify `src/services/video_service.py` orchestration to optionally pre-segment before clip analysis
- Update `analyze_transcript()` signature to accept optional pre-segmented regions

**Benefits:**
- Deterministic, predictable clip boundaries (vs. LLM randomness)
- Reduced LLM token usage (smaller, pre-filtered candidate set)
- Better handling of long videos (10+ hours) where LLM context windows struggle
- Inherently captures "complete thoughts" — natural narrative breaks

**Category:** `borrow-from-foss`

---

## 2. Dynamic Video Cropping with Speaker Diarization

### How ClipsAI Does It

ClipsAI's `resize()` function uses a **three-component system** for speaker-aware cropping:

- **Speaker Diarization:** Pyannote (requires free HuggingFace token) assigns unique speaker IDs across the video
- **Face Detection:** MTCNN + MediaPipe detect facial position in each segment
- **Scene Detection:** PySceneDetect identifies shot boundaries (where to start/stop tracking)
- **Output:** Crops object with segment-wise x,y coordinates defining 9:16 crop box to follow the current speaker
- **Tunable Parameters:**
  - Speaker segment duration (min duration to consider a diarized speaker segment)
  - Face detection sampling rate per segment (how often to re-detect face)
  - Scene detection threshold (minimum shot duration)
  - Minimum scene duration (0.25s default)
  - Merge threshold for speaker/scene transitions (0.25s default)

**Technical Workflow:**
1. Run Pyannote on entire video → assigns speaker labels to time ranges
2. For each speaker segment: sample frames at configurable interval
3. Detect faces in sampled frames (MTCNN/MediaPipe)
4. Compute crop box centered on detected face, clamped to frame bounds
5. Merge adjacent speaker segments with PySceneDetect for shot-aware transitions

### SupoClip's Current Approach

SupoClip uses **single-frame MediaPipe face detection** (`src/pipeline/face_detect.py`):
- Samples a single frame at clip start (default 1.0s)
- Detects highest-confidence face in that frame
- Falls back to center crop if no face detected
- Applies simple 10% upward bias for better framing
- All output dimensions rounded to even integers for H.264 encoding

**Code Reference:** `src/pipeline/face_detect.py:35-94` (detection), `src/pipeline/face_detect.py:97-151` (crop calculation)

### Borrowable Technique: Multi-Frame Speaker Tracking

**Recommendation:** Enhance cropping with **frame-level speaker tracking** (without full diarization overhead):

**Simple Approach (No Diarization):**
- Sample multiple frames across the clip duration (e.g., every 1s or at 25% intervals)
- Detect faces in each frame
- Smooth detected face centers using moving average or Kalman filter
- Compute a single "representative" crop box that covers the trajectory

**Benefits Over Current:**
- Handles clips with speaker movement (standing/pacing)
- Reduces jitter from single-frame outliers
- Better framing for multi-speaker segments
- No external dependencies (Pyannote token not needed)

**Full Diarization Approach (Optional, Future):**
- Add optional Pyannote integration in `src/pipeline/face_detect.py` for speaker-aware tracking
- Use speaker ID to prioritize face detection only in regions where that speaker is active
- Requires `.env` config: `PYANNOTE_HF_TOKEN=hf_...`
- Fallback to frame-level tracking if diarization unavailable

**Implementation Path:**
1. Modify `src/pipeline/face_detect.py:detect_face_center()` to accept a list of frames (not just one)
2. Add function `detect_face_trajectory()` that:
   - Takes list of sampled frames across clip duration
   - Detects face center in each frame
   - Filters outliers (faces that move >X pixels between frames)
   - Smooths trajectory (moving average)
   - Returns representative face center for the clip
3. Update clip generation in `src/pipeline/clip.py` to sample frames and pass to `detect_face_trajectory()`

**Code Changes:**
- `src/pipeline/face_detect.py`: Add `detect_face_trajectory(frames: list[np.ndarray]) -> tuple[int, int]`
- `src/pipeline/clip.py`: Sample frames from clip, pass to face detection

**Category:** `borrow-from-foss`

---

## 3. Speaker Diarization for Reframing (Optional Integration)

### How ClipsAI Does It

Uses **Pyannote** for speaker identification across the entire video:
- Assigns unique speaker IDs to time ranges
- Enables "follow the current speaker" cropping strategy
- Requires free HuggingFace token (security consideration: token in `.env`)
- Allows filtering to specific speakers (e.g., "only crop to speaker A, not background voices")

### SupoClip's Opportunity

**Current State:** No speaker diarization; crops to any detected face

**Borrowable Enhancement:**
- Make Pyannote optional (env var `ENABLE_DIARIZATION=true`, `PYANNOTE_HF_TOKEN=...`)
- If available: prioritize cropping to the main speaker (first speaker by total duration)
- If unavailable: fallback to multi-frame face tracking (see section 2)
- UI control: Settings page could show "Follow speaker: [auto/speaker1/speaker2/best]"

**Implementation:**
- Add to `src/config.py`:
  ```python
  @property
  def enable_diarization(self) -> bool:
      return os.getenv("ENABLE_DIARIZATION", "false").lower() == "true"
  
  @property
  def pyannote_hf_token(self) -> str:
      return os.getenv("PYANNOTE_HF_TOKEN", "")
  ```
- Create `src/pipeline/diarization.py` with optional Pyannote wrapper
- Update `src/services/video_service.py` to optionally diarize before face detection

**Category:** `borrow-from-foss` (optional dependency)

---

## 4. Transcription: WhisperX vs. Parakeet-MLX

### How ClipsAI Does It

Uses **WhisperX** (open-source wrapper on OpenAI Whisper):
- Provides word-level timestamps via forced alignment
- Detects start/stop times for each word (not just sentence-level)
- Supports auto language detection
- Batch size tunable for GPU memory (default 16)
- Output: Transcription object with word, sentence, character-level granularity

**Technical Details:**
- WhisperX = Whisper + alignment model (Wave2Vec2 or CTC-based phoneme model)
- Alignment model force-aligns transcription to audio, producing sub-100ms word timing
- Enables practical downstream tasks: SRT/VTT subtitle generation, clip boundary snapping to word edges

### SupoClip's Current Approach

Uses **parakeet-mlx** (MLX-community optimized for Apple Silicon):
- Local, on-device transcription (no cloud API calls)
- Word-level timestamps via parakeet's native alignment
- BPE token merging (space-prefix heuristic) for whole-word reconstruction
- Transcript caching (`.transcript_cache.json` alongside video)
- Model: `mlx-community/parakeet-tdt-0.6b-v2`

**Code Reference:** `src/pipeline/transcribe.py:43-111` (BPE merging), `src/pipeline/transcribe.py:246-299` (main function)

### Comparison & Assessment

| Aspect | WhisperX | Parakeet-MLX |
|--------|----------|--------------|
| **License** | MIT | Hugging Face model license |
| **Offline** | No (uses OpenAI API or requires local Whisper) | Yes (local MLX) |
| **Speed** | Fast (cloud or GPU-optimized) | Very fast (Apple Silicon optimized) |
| **Word Timing** | High precision (forced alignment) | Good precision (native alignment) |
| **Language Support** | 99 languages (Whisper) | Multilingual (parakeet) |
| **Hardware** | Any GPU/CPU | Best on Apple Silicon (MLX) |
| **Deployment** | Cloud or local | Local only |

**Conclusion:** SupoClip's parakeet-mlx choice is **sound for local, cross-platform use**. WhisperX is better for cloud deployments or when absolute precision is critical (YouTube captions).

**Optional Borrowable Idea:**
- Support WhisperX as an **optional alternative** transcriber if user sets `TRANSCRIBER=whisperx` in `.env`
- Keep parakeet-mlx as default (faster, offline, Apple Silicon optimized)
- Create `src/pipeline/transcribe_whisperx.py` alongside existing `transcribe.py`
- Update `src/services/video_service.py` to route based on config

**Category:** `borrow-from-foss` (optional, not critical)

---

## 5. Subtitle Generation: ASS Format + Per-Word Timing

### How ClipsAI Does It

Uses **pysubs2** to generate ASS (Advanced SubStation Alpha) subtitles:
- Per-word timing (each word gets start/end timestamps)
- Full styling support: font family, size, colors, outlines, shadows
- Burned into video via ffmpeg: `-vf "ass=file.ass:fontsdir=fonts/"`
- Synchronization: word-level precision enables frame-accurate captions

### SupoClip's Current Approach

SupoClip **already uses this exact technique!**

**Code Reference:** `src/pipeline/subtitles.py:125-188` (ASS generation), `src/pipeline/subtitles.py:51-79` (color conversion)

**Implementation Details:**
- Per-word timing: each word gets its own SSAEvent with start_ms/end_ms
- Styling: font family (custom TTF support), size, color, outline, shadow
- Position: 75% down from top (lower-middle, not bottom) via MarginV calculation
- Custom fonts: TTF files in `fonts/` directory, matched to internal font family name

**Minor Enhancement (Borrowable Idea):**
- ClipsAI's resize documentation mentions tunable parameters for scene detection thresholds
- SupoClip could add **dynamic font sizing** based on clip duration:
  - Shorter clips (10-20s): larger font (28-32pt)
  - Longer clips (30-45s): smaller font (20-24pt)
  - Prevents text overshadowing speaker for long-form content

**Category:** Already implemented; no urgent borrowing needed

---

## 6. Video Processing Pipeline Architecture

### How ClipsAI Does It

ClipsAI is a **pure-Python library** (no frontend) with modular pipeline:
- `Transcriber` class: handles WhisperX transcription
- `ClipFinder` class: identifies clip segments
- `resize()` function: applies diarization + face detection + cropping
- `MediaEditor` class: handles video trimming/composition
- Library-first design: developers integrate into custom workflows

### SupoClip's Current Approach

SupoClip is a **full-stack application** (NiceGUI UI + FastAPI + Pipeline):
- UI pages in `src/pages/`
- Pipeline orchestration in `src/services/video_service.py`
- Modular pipeline stages in `src/pipeline/`
- Single-process app (NiceGUI IS FastAPI, same event loop)

**Architecture Comparison:**

| Aspect | ClipsAI | SupoClip |
|--------|---------|---------|
| **Scope** | Library only | Full application |
| **UI** | None (developer-facing) | NiceGUI web UI |
| **Orchestration** | Manual (caller chains stages) | Service-based (video_service.py) |
| **Extensibility** | High (library model) | High (plugin architecture possible) |

**Borrowable Ideas:**

1. **Expose SupoClip as a library:**
   - Extract pipeline from FastAPI
   - Create `src/api/` module exposing Python API
   - Allow programmatic use: `from supoclip.pipeline import transcribe_video, find_clips, generate_clip`

2. **Progressive Processing:**
   - Add optional caching at each pipeline stage (not just transcription)
   - Cache intermediate results: `clip_analysis_cache.json`, `face_detection_cache.json`
   - Enable resume-on-failure for large videos

3. **Modular Dependencies:**
   - Make parakeet-mlx optional (allow "transcription-free" mode for pre-transcribed content)
   - Make MediaPipe optional (graceful center-crop fallback)
   - Similar to ClipsAI's modular Transcriber

**Category:** `borrow-from-foss` (architectural pattern, not critical)

---

## 7. Configuration & Parameter Tuning

### How ClipsAI Does It

**ClipFinder:**
- Single parameter: `find_clips(transcription)` — no tunable parameters exposed
- All heuristics are deterministic and baked into TextTiling algorithm

**Resize:**
- Tunable parameters:
  - `speaker_segment_duration`: min duration to consider a speaker segment
  - `face_detection_sampling_rate`: how often per segment to re-detect faces
  - `scene_detection_threshold`: minimum shot duration
  - Defaults: 0.25s for minimum segment, 0.25s for merge threshold

### SupoClip's Current Approach

**Analyze (Clip Selection):**
- Tunable parameters:
  - `min_length_s`: minimum clip duration (default 15.0)
  - `max_length_s`: maximum clip duration (default 45.0)
  - `custom_prompt`: optional system prompt override
- Hardcoded filler words: `_FILLER_STARTS` in `analyze.py:33-45`
- Default: 3-7 segments per video

**Subtitle Generation:**
- Tunable style parameters:
  - Font family, size, colors, outline width, shadow depth
  - Position (75% down default)
  - Uppercase toggle
- Minimum word duration: 50ms filter (skip very short/noise words)

### Borrowable Enhancement: User-Configurable Clip Criteria

**Recommendation:** Expose clip selection parameters as **user settings** in UI:

1. **Add to Settings page** (`src/pages/settings.py`):
   - Clip duration range slider (10-60s)
   - Max clips to generate (1-15)
   - Toggle for filler-word filtering
   - Optional: custom exclusion words (user-defined)

2. **Persist to database:**
   - Store in `UserPreferences` model (`src/models.py`)
   - Load in `video_service.py` before analysis

3. **Example UI:**
   ```
   [Clip Selection Settings]
   Min Duration: [===========]  15s
   Max Duration: [===========]  45s
   Segments to Find: [====]  5
   [x] Skip clips starting with common words
   ```

**Code Changes:**
- `src/pages/settings.py`: Add clip preference UI
- `src/models.py`: Add fields to `UserPreferences` (clip_min_s, clip_max_s, max_segments)
- `src/services/video_service.py`: Load prefs and pass to `analyze_transcript()`

**Category:** `borrow-from-foss` (user experience improvement)

---

## 8. Quality Metrics & Evaluation

### How ClipsAI Does It

ClipsAI does **not expose** explicit quality metrics. The TextTiling algorithm produces segments deterministically; quality is implicit in topic coherence.

### SupoClip's Current Approach

No explicit quality metrics. Relies on:
- LLM relevance score (0.0-1.0)
- Duration validation (min/max bounds)
- Filler-word filtering
- Manual user review/selection via web UI

### Borrowable Opportunity: Engagement Scoring

**Recommendation:** Add optional post-LLM scoring heuristics:

1. **Hook Detection:** Scan first N words for engagement triggers
   - "Did you know?", "Wait until you see...", "Here's the thing...", "Actually, ..."
   - Boost relevance score if detected

2. **Structural Completeness:** Check if segment contains:
   - Clear opening (hook or setup)
   - Body (explanation or story)
   - Closing (punchline, insight, or call-to-action)
   - Deduct if missing any (likely fragment)

3. **Uniqueness:** Ensure selected segments don't overlap >30% in content
   - Prevent duplicate topics

**Implementation:**
- Create `src/pipeline/scoring.py` with optional quality heuristics
- Apply in `analyze.py:571-574` after LLM validation but before final sort
- Optional config: `ENABLE_ENGAGEMENT_SCORING=true`

**Category:** `borrow-from-foss` (enhancement, not core feature)

---

## 9. Scene Detection for Shot-Aware Cropping

### How ClipsAI Does It

**PySceneDetect** component:
- Detects shot/scene boundaries in video
- Used to reset crop tracking when scene changes (reduces jitter at cuts)
- Parameters: scene threshold, minimum duration
- Integrates with speaker diarization: when scene changes, recalculate crop box

### SupoClip's Current Approach

No scene detection. Crops entire clip uniformly based on representative frame face detection.

### Borrowable Enhancement: Shot-Aware Crop Transitions

**Recommendation:** Add optional scene detection for smoother crop box transitions:

1. **Lightweight Approach:** Use `scenedetect` library (pure Python, no native deps)
   - Detect scene boundaries within clip timeframe
   - When scene changes: sample new representative frame for face detection
   - Smooth crop box interpolation between scenes

2. **Integration:**
   - New module: `src/pipeline/scene_detect.py`
   - Modify `src/pipeline/clip.py` to apply per-scene cropping
   - Optional: store scene boundaries in clip metadata for debugging

**Benefits:**
- Eliminates jarring crop jumps at cuts
- Better handling of interview/multi-shot videos
- Minimal performance overhead

**Category:** `borrow-from-foss` (enhancement)

---

## 10. Key Differences: SupoClip vs. ClipsAI

| Dimension | ClipsAI | SupoClip |
|-----------|---------|---------|
| **Target Content** | Podcasts, interviews, speeches (narrative-driven) | General video (YouTube, long-form, any topic) |
| **Clip Selection** | TextTiling + BERT (topic segmentation) | LLM-based (semantic relevance scoring) |
| **Scope** | Library (developer-facing) | Full app (end-user facing) |
| **Transcription** | WhisperX (cloud or local) | Parakeet-MLX (local, Apple Silicon optimized) |
| **Cropping** | Pyannote diarization + MTCNN + MediaPipe + scene detection | MediaPipe face detection + center-crop fallback |
| **Complexity** | Lower (deterministic algorithms) | Higher (LLM-based, more config) |

---

## 11. Prioritized Borrowing Roadmap

### **High Priority (1-2 weeks, high impact)**

1. **TextTiling + BERT for pre-segmentation** (Section 1)
   - Reduces LLM token usage
   - Improves clip boundary accuracy
   - Low implementation risk (external library)

2. **Multi-frame speaker tracking** (Section 2)
   - Handles speaker movement
   - Reduces single-frame noise
   - Medium implementation effort

### **Medium Priority (2-4 weeks, nice-to-have)**

3. **Optional Pyannote diarization** (Section 3)
   - Better speaker prioritization
   - Optional dependency (no blocker)
   - Requires HF token setup

4. **User-configurable clip criteria in UI** (Section 7)
   - Improves UX
   - Enables experimentation
   - Low implementation risk

### **Low Priority (future, polish)**

5. **Scene detection** (Section 9)
   - Smooth crop transitions
   - Nice-to-have, not critical
   - Medium implementation effort

6. **Engagement scoring heuristics** (Section 8)
   - Post-processing refinement
   - Optional feature
   - Low implementation risk

7. **WhisperX as alternative transcriber** (Section 4)
   - Not critical (parakeet-mlx is solid)
   - Only if cloud transcription demanded
   - Medium effort

---

## 12. Sources & References

**ClipsAI Repository & Documentation:**
- [ClipsAI GitHub Repository](https://github.com/ClipsAI/clipsai)
- [ClipsAI Documentation: Clip Finding](https://www.clipsai.com/references/clip)
- [ClipsAI Documentation: Resizing](https://www.clipsai.com/references/resize)
- [ClipsAI Documentation: Transcription](https://www.clipsai.com/references/transcribe)
- [ClipsAI Main Site](https://www.clipsai.com/)

**Related Technologies:**
- [TextTiling Algorithm (Marti Hearst, 1997)](https://dl.acm.org/doi/10.1145/278190.278222)
- [WhisperX: Word-level Timestamps](https://github.com/m-bain/whisperx)
- [Pyannote Speaker Diarization](https://github.com/pyannote/pyannote-audio)
- [pysubs2 ASS Subtitle Library](https://github.com/asottile/pysubs2)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)

**SupoClip Code References:**
- `src/pipeline/analyze.py` — LLM-based clip selection
- `src/pipeline/face_detect.py` — MediaPipe face detection
- `src/pipeline/transcribe.py` — parakeet-mlx transcription
- `src/pipeline/subtitles.py` — ASS subtitle generation
- `src/services/video_service.py` — Pipeline orchestration

---

## Conclusion

ClipsAI demonstrates several **production-grade techniques** that SupoClip can selectively borrow:

1. **TextTiling + BERT** for deterministic, lightweight topic segmentation (as a pre-pass before LLM scoring)
2. **Multi-frame face tracking** to handle speaker movement and reduce jitter
3. **Pyannote diarization** (optional) for speaker-prioritized cropping
4. **Scene detection** for smooth crop transitions at shot boundaries

All borrowings are **compatible with SupoClip's all-Python, single-process architecture**. The highest-impact borrowing is TextTiling for clip pre-segmentation, which reduces LLM dependency and cost while improving reliability.

---

**End of research document.**
