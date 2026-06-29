# Code Review: src/pipeline/transcribe.py and src/pipeline/face_detect.py

**Auditor:** Code Review Agent  
**Date:** 2026-06-29  
**Files audited:**
- `src/pipeline/transcribe.py` (331 lines)
- `src/pipeline/face_detect.py` (193 lines)

All findings are grounded in file evidence with line citations. Ground-truth test/lint numbers from orchestrator used as-is.

---

## src/pipeline/transcribe.py

### ✅ Good — well-implemented features, clean code, good patterns

**G1. BPE token merging logic** (`merge_bpe_tokens`, lines 43–111)  
The leading-space heuristic for parakeet-mlx's BPE output is correctly implemented and well-documented. The flush-on-new-word state machine avoids off-by-one errors. Timestamps are correctly converted to integer milliseconds. Tests cover: empty input, single whole word, continuation tokens, multiple words, mixed BPE sequences, whitespace-only tokens, and millisecond precision.

**G2. Cache version system** (lines 19–22, 148–155)  
`_CACHE_VERSION = 3` with version mismatch detection prevents silent stale-cache issues. Old caches are rejected cleanly with an info log rather than silently corrupting output. This is the correct defensive pattern.

**G3. Proper exception chaining** (line 290)  
`raise TranscriptionError(...) from exc` preserves the original traceback. This is correct Python practice for wrapping third-party exceptions.

**G4. PARAKEET_AVAILABLE flag** (lines 27–31)  
Graceful import guard at module level allows the rest of the codebase to work without parakeet installed. The flag is always a `bool` regardless of import outcome.

**G5. Structured logging** (throughout)  
`structlog.get_logger(__name__)` used consistently. Log fields use snake_case keys with structured context. No print statements or emoji-based logging.

**G6. format_transcript_text** (lines 307–328)  
Clean and correct. Produces `"word [start_ms-end_ms] ..."` format for LLM consumption, skips empty words, and is appropriately simple.

---

### ❌ Bad — bugs, poor implementations, anti-patterns

**B1. Magic numbers in transcription call** (lines 284–288)  
`chunk_duration=120.0` and `overlap_duration=15.0` are hardcoded in `transcribe_video`. CLAUDE.md explicitly prohibits "hardcoded ... magic numbers in source code." Neither constant is in `config.py` nor exposed as an env var. Changing chunking behavior for long videos requires a code edit.

```python
result = model.transcribe(
    str(p),
    chunk_duration=120.0,   # magic number — not in config
    overlap_duration=15.0,  # magic number — not in config
)
```

**B2. `_DEFAULT_MODEL_ID` is not configurable** (line 25)  
`_DEFAULT_MODEL_ID = "mlx-community/parakeet-tdt-0.6b-v2"` is a module-level constant not wired to any config. `docs/spec.md:701` explicitly specifies a `PARAKEET_MODEL` env var: `| PARAKEET_MODEL | str | mlx-community/parakeet-tdt-0.6b-v2 | HuggingFace model ID for parakeet-mlx |`. This env var does not exist in `src/config.py`. The transcription model cannot be overridden without modifying source code.

---

### ❓ Missing — gaps vs spec/PRD

**M1. `TranscriptData` typed dataclass not implemented**  
`docs/spec.md:294–296` requires:
```python
TranscriptData  # dataclass(slots=True)
  words: list[WordTiming]   # each word has text, start_ms, end_ms, confidence
  full_text: str
  duration_s: float
```
The implementation returns raw `list[dict]` throughout. The pipeline (`video_service.py:345`) receives `list[dict]` and passes it as `words: list[dict]`. This means the entire pipeline operates on untyped dicts. mypy cannot catch field name typos or missing keys in word dicts.

**M2. `WordTiming` typed model not implemented**  
Spec requires per-word `confidence` field in `WordTiming`. This is never captured by `merge_bpe_tokens` or `_tokens_from_result`. The analyzer and subtitle generator never receive confidence data.

**M3. `PARAKEET_MODEL` env var not in config.py**  
Spec.md:701 specifies this should be configurable. `src/config.py` has no such field. See B2 above.

**M4. Cache deserialised via Pydantic not raw dict**  
Spec.md:303: "Cache file is JSON; deserialised via Pydantic model, not raw dict access." The implementation does `data: dict = json.load(fh)` then `data.get("words")` directly. No Pydantic model validates the cache structure beyond the isinstance check at line 158.

**M5. `reconstruct_words_with_llm` option removed without replacement**  
Spec.md:304 describes a `config.reconstruct_words_with_llm` path to fix sub-word tokens via LLM. The module docstring (line 6) says "The Groq LLM word reconstruction path has been removed." This is an intentional removal, but it is not reflected in config.py (no deprecated flag) and the spec still shows it as a feature. This is a PRD gap that should be formally closed.

---

### 🤫 Silent errors — swallowed exceptions, unhandled edge cases

**SE1. Cache load failure is invisible to callers** (lines 141–146)  
```python
except Exception as exc:  # noqa: BLE001
    logger.warning("transcript_cache.load_failed", ...)
    return None
```
A disk read error, permission error, or corrupted file all return `None` — the same as "no cache exists." The caller (`transcribe_video`, line 264) cannot distinguish between "cache not found" and "cache unreadable." The effect is silent re-transcription, which is expensive (minutes on real hardware). The `noqa: BLE001` suppression acknowledges the broad catch but not the ambiguity.

**SE2. Cache save failure is invisible to callers** (lines 183–187)  
```python
except Exception as exc:  # noqa: BLE001
    logger.warning("transcript_cache.save_failed", ...)
```
Disk-full, permission, or serialization errors are swallowed. The transcript is returned correctly but caching silently fails. The user will re-transcribe on every run with no indication of why. The warning is logged but only to structlog — not surfaced to the UI.

**SE3. Missing keys in `merge_bpe_tokens` default silently to 0** (lines 76–77)  
```python
start_ms = int(token.get("start", 0) * 1000)
end_ms = int(token.get("end", 0) * 1000)
```
If a parakeet token is missing `start` or `end` keys (malformed output), both timestamps become 0 ms. This produces a word at timestamp 0 with zero duration, which looks like `{"text": "hello", "start_ms": 0, "end_ms": 0}`. It passes through the merger, enters the cache, and reaches the subtitle generator where it could produce a subtitle event at the very start of the clip with incorrect timing. No warning is logged.

---

### 🐷 Overengineered / 🚮 Tech debt

**TD1. `_tokens_from_result` complexity grade C** (line 195)  
Radon CC reports this function at grade C. The function has two nested loops with per-token filtering and conditional early returns. The spec's "Extreme Granularity" VUW approach calls for functions at grade A or B. Remediation: extract per-token filtering and the sentence-loop body into named helpers to reduce nesting depth.

---

## src/pipeline/face_detect.py

### ✅ Good — well-implemented features, clean code, good patterns

**G1. Dual threshold filtering in `detect_face_center`** (lines 83–88)  
Rejects faces smaller than 30px (absolute) AND outside the `[0.005, 0.3]` relative area range. This two-layer heuristic is appropriate for rejecting both noise detections (tiny faces) and framing errors.

**G2. `try/finally` resource release in `get_representative_frame`** (lines 188–190)  
`cap.release()` in a `finally` block ensures the VideoCapture handle is always released even if `cap.read()` or `cap.set()` raises. This is correct resource management.

**G3. `round_to_even` utility** (lines 23–32)  
Clean, correctly documents the H.264 even-dimension requirement. Well-tested.

**G4. Crop clamping logic** (lines 148–149)  
`x = max(0, min(x, frame_width - crop_width))` correctly prevents the crop box from exceeding frame bounds when a face is near the edge. The upward bias (line 139: `10%` of crop height) is a sensible framing heuristic.

**G5. Structured logging with contextual fields**  
`log.warning("cv2_unavailable", reason="...")` provides machine-parseable log context.

---

### ❌ Bad — bugs, poor implementations, anti-patterns

**B1. BGR vs RGB color space mismatch — runtime face detection bug** (lines 35–94)  
`get_representative_frame` returns a **BGR** numpy array (cv2 default). `detect_face_center` receives this array and passes it directly to `mediapipe.FaceDetection.process(frame)`. MediaPipe FaceDetection expects **RGB** images. There is no `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` conversion anywhere in the code.

Evidence from the file's own docstrings:
- `get_representative_frame` docstring, line 168: "Returns: BGR numpy array"
- `detect_face_center` parameter docstring, line 43: "frame: BGR numpy array from a video frame"
- `detector.process(frame)` at line 62: no conversion applied

Impact: Face detection operates on the wrong channel ordering. In RGB space, the R channel is red; in BGR it is blue. For most faces this causes detection degradation rather than total failure (face features remain detectable), but confidence scores are incorrect and detection boundary accuracy degrades. Combined with the `min_detection_confidence=0.5` threshold (line 59), some faces that would have been detected in RGB may be missed, silently falling back to center crop. Tests mock MediaPipe entirely so this is invisible in the test suite.

**B2. cv2 relied on as an undeclared transitive dependency, and its use violates the ffmpeg-only mandate** (lines 170–191)  
`pyproject.toml` does not list `opencv-python` or `opencv-contrib-python` as a direct dependency. However, `uv.lock` confirms that `mediapipe>=0.10.0` pins `opencv-contrib-python` as a transitive dependency (opencv-contrib-python 4.13.0.92), so `import cv2` does succeed on a clean `uv sync`. The cv2 availability is therefore an undeclared reliance on a transitive pin that could break if mediapipe ever removes this dependency.

More significantly, using `cv2.VideoCapture` for frame extraction violates the project's explicit architectural rule. CLAUDE.md: "ffmpeg is the video engine. Every video operation ... is expressed as a single ffmpeg subprocess call. No Python video library sits between the application and ffmpeg." Spec.md:410 mandates using the ffmpeg `select` filter for frame extraction, not cv2. CLAUDE.md also states "mediapipe (face detection only; no OpenCV DNN fallbacks)" — yet cv2 is used here for a core video operation (frame extraction), not just detection. The conditional ImportError guard (which makes cv2 appear "optional") gives false confidence: if cv2 becomes unavailable (e.g., mediapipe changes its transitive deps), the fallback to center crop is silent and complete.

**B3. Single-frame sampling instead of spec-required multi-frame aggregation** (combined with clip.py:53)  
The spec at `docs/spec.md:410–412` requires:
> "Samples up to 10 evenly spaced frames within the segment using ffmpeg `select` filter"  
> "Aggregates face bounding boxes across frames; takes the median x-centre"

The implementation samples exactly 1 frame at `segment.start_s + 1.0s` (hardcoded constant `_FACE_DETECT_OFFSET_S = 1.0` in `clip.py:53`). For talking-head videos where the subject is stationary this may be sufficient, but for videos with camera movement, zooms, or cut-to-cut edits within a segment, a single early frame can produce systematically off-center crops for the remainder of the clip. The median-across-frames approach in the spec directly addresses this instability.

**B4. ffmpeg-only mandate violated for frame extraction**  
`CLAUDE.md` states: "ffmpeg is the video engine. Every video operation — trim, crop, scale, subtitle burn, logo overlay, encode — is expressed as a single ffmpeg subprocess call. No Python video library sits between the application and ffmpeg."

`get_representative_frame` uses `cv2.VideoCapture` — a Python video library — for frame extraction instead of ffmpeg's `select` filter as specified in `docs/spec.md:410`. This contradicts both the architectural mandate and the spec.

---

### ❓ Missing — gaps vs spec/PRD

**M1. `get_crop_rect()` function not implemented**  
The spec defines the public API surface as:
```python
async def get_crop_rect(
    video_path: Path,
    start_s: float,
    end_s: float,
    target_width: int,
    target_height: int,
) -> CropRect:
```
The implementation replaces this with three separate synchronous functions called directly from `clip.py`. This is a reasonable architectural choice (separation of concerns) but it means callers must orchestrate the 3-step chain themselves (and clip.py does this at lines 286–300).

**M2. `CropRect` named return type not implemented**  
The spec defines `CropRect(x=int, y=int, w=int, h=int)` as the return type. The implementation returns a bare `tuple[int, int, int, int]` from `calculate_crop_box`. No named dataclass is used, making the tuple positional-only with no IDE or mypy field-name safety.

**M3. Multi-frame aggregation with median x-centre entirely absent**  
See B3. The spec test requirements at `docs/spec.md:1161` say "Test aggregation logic with multiple frames and varying face positions." No such test exists in `tests/unit/test_face_detect.py` because the feature itself is not implemented.

**M4. PRD says 3-tier fallback chain was retained**  
`docs/prd.md:37`: "Smart cropping: Face-centered using MediaPipe (primary), OpenCV DNN (fallback), Haar cascade (last resort)". The spec supersedes this (MediaPipe only), but the PRD still describes the 3-tier chain. The spec says "The 3-tier fallback chain ... is replaced with MediaPipe only." This is a PRD/spec inconsistency that should be formally noted.

---

### 🤫 Silent errors — swallowed exceptions, unhandled edge cases

**SE1. `results.detections` accessed outside try/except block** (lines 62–67) — speculative / defensive  
```python
try:
    detector = mp.solutions.face_detection.FaceDetection(...)
    with detector:
        results = detector.process(frame)
except Exception as exc:
    log.warning("mediapipe_detection_failed", error=str(exc))
    return None

if not results.detections:   # <-- outside try/except
    return None
```
The MediaPipe solutions API normally returns a namedtuple with `.detections = None` or `.detections = []` when no face is found — so `results` itself being `None` is not the common case. However, with malformed frames or certain MediaPipe versions, `results` could theoretically be `None`, causing an unhandled `AttributeError` at line 67 that propagates through `detect_face_center` → `generate_clip`. This is a low-probability defensive gap. Fix: `if results is None or not results.detections:`.

**SE2. `_MAX_RELATIVE_AREA = 0.3` silently rejects close-up faces** (lines 18–19, 87–88)  
A face occupying more than 30% of the frame area is silently filtered as a "framing error." For selfie-style or close-up interview content (common on YouTube Shorts and TikTok), the subject's face routinely occupies 30–60% of the frame. These clips will silently fall back to center crop even though MediaPipe successfully detected a face. No warning is logged when this filter triggers. The threshold is not configurable.

**SE3. Zero-dimension source frames** (line 126)  
```python
if frame_width / frame_height > target_ratio:
```
If `frame_width == 0` or `frame_height == 0` (e.g., `_get_video_dimensions` fallback returns `(0, 0)`), this raises `ZeroDivisionError`. No input validation. The caller in clip.py (line 293) calls `_get_video_dimensions` which has its own fallback, but the behavior under `frame_height=0` is untested.

---

### 🐷 Overengineered — None found.

The module is appropriately sized for its responsibility.

---

### 🚮 Tech debt / dead code

**TD1. Module docstring mentions removed fallback chain** (lines 5–8)  
The docstring says "The 3-tier fallback chain (MediaPipe → OpenCV DNN → Haar cascade) is replaced with MediaPipe only" — but then `get_representative_frame` uses cv2 anyway (for frame extraction, not detection). The framing is correct for detection but misleading for frame extraction. This will confuse future contributors.

---

## Runtime / Output Correctness Risk Summary

These are issues that pass unit tests (which mock all external dependencies) but affect real output:

| Risk | Severity | File | Notes |
|------|----------|------|-------|
| BGR passed to RGB-expecting MediaPipe | High | face_detect.py:62 | Face detection runs but on wrong color channels; confidence scores and bbox positions degrade; some faces missed silently → center crop fallback |
| cv2 used as undeclared transitive dep, violates ffmpeg-only mandate | Medium | face_detect.py:171 | Currently works (mediapipe pins opencv-contrib-python); silently falls back to center crop if transitive dep ever removed; should be explicit dep or replaced with ffmpeg frame extraction |
| Single-frame sampling | Medium | face_detect.py + clip.py:53 | Camera motion or cuts within segment produce poor centering |
| chunk_duration/overlap_duration hardcoded | Medium | transcribe.py:284-288 | Cannot tune for very long videos without code change |
| `results.detections` AttributeError | Medium | face_detect.py:67 | Could crash clip generation on edge-case MediaPipe return |
| Cache save failure invisible | Low | transcribe.py:186 | Re-transcribes on every run without warning |
| Missing PARAKEET_MODEL config | Low | transcribe.py:25 | Cannot switch models without code change |

---

## Remediation Priority

1. **Critical — fix before any production use:**
   - Add `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` conversion before `detector.process()` in `detect_face_center` (face_detect.py:62). This is a runtime bug that degrades face detection on every clip.
   - Add `if results is None or not results.detections:` guard (face_detect.py:67) as defensive hardening.

2. **High — architectural debt, affects output quality:**
   - Implement multi-frame sampling and median aggregation per spec.md:410-412; replaces the 1-frame approach in `get_representative_frame` + clip.py:53
   - Add `PARAKEET_MODEL` to config.py and wire to `transcribe.py:25`
   - Move `chunk_duration=120.0` and `overlap_duration=15.0` from transcribe.py:284-288 to config.py
   - Replace cv2 frame extraction with ffmpeg `select` filter (or explicitly declare `opencv-contrib-python` as a direct dependency with explanation of why the ffmpeg mandate is relaxed here)

3. **Medium — type safety and spec compliance:**
   - Implement `TranscriptData` and `WordTiming` typed dataclasses per spec.md:294-296
   - Refactor `_tokens_from_result` to reduce complexity (radon grade C → A/B)

4. **Low — polish:**
   - Log warning when `_MAX_RELATIVE_AREA` filter (0.3) rejects a valid detection (face_detect.py:87)
   - Add zero-dimension guard to `calculate_crop_box` (face_detect.py:126)
   - Formally close the PRD/spec gap on 3-tier vs 1-tier face detection (prd.md:37 vs spec.md:413)
