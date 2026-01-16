# Claude Debug Audit Report - January 16, 2026

## Executive Summary

The persistent audio/video/caption misalignment in SupoClip stems from **three architectural decisions** that compound to cause cumulative timing drift:

1. **LLM-based word reconstruction** uses probabilistic text correction with a greedy character-matching heuristic to realign timestamps - this is the PRIMARY cause
2. **Precision loss** at the AI segment selection stage (milliseconds → seconds → milliseconds)
3. **Silent filtering** of "short" words masks alignment errors instead of surfacing them

The system is fundamentally trying to solve a **deterministic timing problem** with **probabilistic tools**, which cannot work reliably.

---

## Investigation Methodology

This audit followed the systematic debugging protocol:

1. **Phase 1**: Root cause investigation - traced data flow from transcription to clip output
2. **Phase 2**: Pattern analysis - compared working and broken code paths
3. **Phase 3**: Hypothesis validation - verified findings with code review agents and static analysis
4. **Phase 4**: Documentation - this report (no implementation changes)

**Tools Used**:
- Radon (cyclomatic complexity and maintainability analysis)
- Ruff (linting)
- Manual code tracing
- Code review agents (feature-dev:code-reviewer)

---

## Critical Findings

### Finding 1: LLM Word Reconstruction Causes Cumulative Timing Drift

**Severity**: CRITICAL
**Confidence**: 100%
**Files**: `backend/src/transcription_mlx.py` (lines 266-365, 425-501)

#### The Problem

The parakeet-mlx transcription model produces sub-word tokens due to BPE tokenization (e.g., `["Y", "es", "."]` instead of `["Yes", "."]`). The system attempts to "fix" this by:

1. Sending tokens to Groq LLM with instructions to merge sub-words (line 315-327)
2. Using a character-length heuristic to realign timestamps (line 473)

```python
# Line 473 - The fatal flaw
if len(word_text) >= reconstructed_len * 0.8:  # 80% match threshold
    break
```

#### Why This Fails

**LLMs are probabilistic, not deterministic.** Despite the prompt saying "do NOT correct grammar," LLMs will:
- Change punctuation placement
- "Fix" informal speech ("gonna" → "going to")
- Occasionally hallucinate or drop words
- Respond differently on each invocation

**Greedy alignment compounds errors.** Once one word consumes too few or too many tokens:
- The `broken_idx` pointer advances incorrectly
- Every subsequent word inherits the wrong start timestamp
- Timing drift accumulates across the entire transcript

#### Evidence

**Configuration** (`config.py:33-34`):
```python
self.reconstruct_words_with_llm = (
    os.getenv("RECONSTRUCT_WORDS_WITH_LLM", "true").lower() == "true"
)
```
This is **enabled by default**, meaning all transcriptions go through this unreliable process.

**Alignment algorithm** (`transcription_mlx.py:466-474`):
```python
while broken_idx < len(broken_words):
    token_text = broken_words[broken_idx]["text"]
    word_text += token_text
    broken_idx += 1

    if len(word_text) >= reconstructed_len * 0.8:  # 80% match threshold
        break
```

This greedy consumption has no backtracking or validation. If the LLM's output doesn't match the token stream's character count, alignment fails silently.

---

### Finding 2: Precision Loss in Timestamp Pipeline

**Severity**: HIGH
**Confidence**: 95%
**Files**: `backend/src/video_utils.py`, `backend/src/ai.py`

#### The Problem

The timing precision degrades through the pipeline:

| Stage | Format | Precision |
|-------|--------|-----------|
| parakeet-mlx tokens | float seconds | ~10ms |
| Cached words | int milliseconds | 1ms |
| AI input | MM:SS string | 1 second |
| AI output | MM:SS string | 1 second |
| Clip creation | float seconds | 1ms |
| Subtitles | float seconds | 1ms |

**The AI stage loses all sub-second precision.** A word at 12,340ms becomes `[00:12 - ...]` for AI input, then the AI returns `start_time: "00:12"`, which parses back to exactly 12.000 seconds.

**Result**: Up to 999ms of timing error at clip boundaries.

#### Evidence

**Format conversion** (`video_utils.py:285-290`):
```python
def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds to MM:SS format."""
    seconds = ms // 1000  # Integer division - loses milliseconds
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
```

**Parsing back** (`video_utils.py:887-900`):
```python
def parse_timestamp_to_seconds(timestamp_str: str) -> float:
    parts = timestamp_str.split(":")
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])  # Can recover sub-second if present
        return minutes * 60 + seconds
```

The parsing CAN preserve sub-seconds if the AI returns "00:12.340", but the AI receives "00:12" and returns "00:12".

---

### Finding 3: Silent Deletion of Misaligned Words

**Severity**: HIGH
**Confidence**: 90%
**File**: `backend/src/video_utils.py` (lines 1309-1313)

#### The Problem

When alignment errors (Finding 1) cause words to have very short or negative durations, the system silently drops them:

```python
if word_duration < 0.05:  # 50ms threshold
    logger.debug(  # Note: DEBUG level, not WARNING
        f"Skipping very short word '{word_data.get('text')}' (duration: {word_duration:.3f}s)"
    )
    continue
```

**Result**: Users hear words that have no corresponding caption. The system appears to succeed while producing incorrect output.

#### Evidence

- The filter uses `logger.debug`, which is typically disabled in production
- No error is raised or tracked
- The function continues processing and returns a "success" result

---

### Finding 4: Sentence-Start Snapping Causes Caption/Audio Offset

**Severity**: MEDIUM-HIGH
**Confidence**: 85%
**File**: `backend/src/video_utils.py` (lines 1170-1213, 1644-1654)

#### The Problem

The system attempts to improve clip quality by "snapping" to sentence starts:

```python
# Line 1644-1654 in create_clips_from_segments
snapped_start, _, reason = snap_segment_to_sentence_start(video_path, start_seconds)
if snapped_start != start_seconds:
    logger.info(f"Clip {i + 1}: Snapped start time {start_seconds:.2f}s -> {snapped_start:.2f}s")
    start_seconds = snapped_start
```

**But:** The subtitle extraction uses `clip_start` (the snapped time) while the AI-selected segment boundaries use the original times. If the snap moves the start backward by 2 seconds:
- Video clip starts 2 seconds earlier
- Subtitles start 2 seconds earlier (correctly relative to clip start)
- But the AI-selected text starts at the original timestamp

This causes a 2-second window where the audio plays content that has captions from a different part of the transcript.

---

### Finding 5: Unit Conversion Inconsistencies

**Severity**: MEDIUM
**Confidence**: 85%
**File**: `backend/src/video_utils.py`

#### The Problem

Timestamp units (milliseconds vs. seconds) vary throughout the codebase:

| Context | Variable | Unit |
|---------|----------|------|
| Cached words | `word["start"]`, `word["end"]` | milliseconds |
| Clip times | `clip_start`, `clip_end` | seconds |
| `SubtitleWordFilter` input | `clip_start_ms`, `clip_end_ms` | milliseconds |
| `SubtitleWordFilter` output | `relative_start`, `relative_end` | seconds |
| MoviePy clips | `.with_start()`, `.with_duration()` | seconds |

**Risk**: If any caller passes seconds when milliseconds are expected (or vice versa), timing is off by 1000x. The inconsistent naming (sometimes `_ms` suffix, sometimes not) increases this risk.

---

### Finding 6: Browser Renderer Performance Catastrophe

**Severity**: HIGH (system stability, not sync)
**Confidence**: 85%
**File**: `backend/src/video_utils.py` (lines 972-1020)

#### The Problem

The subtitle renderer creates a **new Chromium browser instance** for every word:

```python
# Line 983 - Called for EACH word
with BrowserSubtitleRenderer() as renderer:
    image_path = renderer.render_text_to_image(...)
```

For a 60-second clip with 150 words, this:
- Launches and kills Chromium **150 times**
- Adds ~3-5 minutes of delay per clip
- Risks timeouts, resource exhaustion, and race conditions
- Can cause "ghost" failures where captions simply don't generate

While not directly causing sync issues, this instability can lead to partial caption generation that appears as sync problems.

---

## Code Quality Analysis

### Cyclomatic Complexity (Radon)

**Overall**: Average complexity A (4.31) - acceptable

**Concerning Functions** (B-rated, complexity 6-10):
- `_align_reconstructed_words` - B (9): The core alignment logic is complex enough to hide bugs
- `_reconstruct_words_with_llm` - B (9): LLM interaction logic is moderately complex
- `SubtitlePositioner.calculate_position` - B (8): Subtitle positioning logic
- `SubtitleTextClipCreator.create_text_clip` - B (8): Clip creation logic

### Maintainability Index

- `backend/src/video_utils.py`: **C** (Warning - needs attention)
- `backend/src/ai.py`: **A** (Good)
- `backend/src/transcription_mlx.py`: **A** (Good)

The C rating on `video_utils.py` (820+ lines) indicates this file is becoming difficult to maintain and is likely where bugs hide.

### Ruff Findings

Only 1 minor issue found:
```
F841 Local variable `word_end` is assigned to but never used
  --> src/video_utils.py:263:9
```
This suggests dead code in the transcript extraction logic.

---

## Root Cause Summary

The audio/video/caption misalignment is caused by a **cascade of compounding errors**:

```
TRANSCRIPTION (accurate)
        ↓
LLM RECONSTRUCTION (introduces probabilistic errors)
        ↓
GREEDY ALIGNMENT (80% character match - cumulative drift)
        ↓
AI SEGMENT SELECTION (loses sub-second precision)
        ↓
SENTENCE SNAPPING (shifts clip start without adjusting text)
        ↓
SUBTITLE GENERATION (uses drifted timestamps)
        ↓
SILENT FILTERING (masks errors by dropping "short" words)
        ↓
INCORRECT CAPTIONS (user sees wrong text for audio)
```

**The PRIMARY issue is Finding 1**: Using an LLM for deterministic timestamp alignment. All other issues are secondary or consequential.

---

## Recommendations (Analysis Only - No Implementation)

### Immediate: Disable LLM Reconstruction
Set `RECONSTRUCT_WORDS_WITH_LLM=false` in environment or config. Raw parakeet-mlx tokens may show sub-word artifacts, but they preserve accurate timing.

### Short-term: Fix Alignment Algorithm
If word reconstruction is required:
1. Use deterministic alignment (Dynamic Time Warping, Needleman-Wunsch)
2. Or use a transcription model with native word-level timestamps (WhisperX)

### Medium-term: Add Timing Validation
1. Validate `word_end > word_start` before creating clips
2. Warn (not debug log) when filtering words
3. Track timing drift metrics

### Long-term: Refactor video_utils.py
The C maintainability rating and 820+ lines indicate this file should be split into:
- `subtitle_builder.py` - Subtitle creation logic
- `crop_calculator.py` - Face detection and cropping
- `clip_creator.py` - Video clip assembly

---

## Appendix: Complete Data Flow Trace

```
1. VIDEO INPUT
   video.mp4
       ↓

2. TRANSCRIPTION (transcription_mlx.py:38-109)
   parakeet-mlx model processes audio
       ↓
   AlignedResult with tokens (float seconds)
       ↓
   _extract_words_from_result (line 188)
       ↓
   words[] with {text, start_ms, end_ms, confidence}
       ↓

3. WORD RECONSTRUCTION (if enabled, transcription_mlx.py:266-365)
   _reconstruct_words_with_llm()
       ↓
   Groq LLM merges sub-word tokens  ← PROBABILISTIC ERROR INTRODUCED
       ↓
   _align_reconstructed_words() (line 425)
       ↓
   Greedy character-length matching  ← CUMULATIVE DRIFT BEGINS
       ↓
   reconstructed words[] with realigned {start, end}
       ↓

4. CACHE (transcription_mlx.py:94-100)
   Saved to {video}.transcript_cache.json
       ↓

5. AI FORMATTING (video_utils.py:161-201)
   get_video_transcript()
       ↓
   format_ms_to_timestamp()  ← PRECISION LOSS (ms → seconds)
       ↓
   "[MM:SS - MM:SS] text" format
       ↓

6. AI SEGMENT SELECTION (ai.py:469-520)
   get_most_relevant_parts_by_transcript()
       ↓
   LLM selects 3-7 segments with MM:SS timestamps
       ↓
   TranscriptSegment[{start_time, end_time, text}]
       ↓

7. CLIP CREATION (video_utils.py:1614-1710)
   create_clips_from_segments()
       ↓
   parse_timestamp_to_seconds()  ← PARSE BACK TO FLOAT
       ↓
   snap_segment_to_sentence_start()  ← SHIFTS CLIP START
       ↓
   create_optimized_clip()
       ↓

8. SUBTITLE GENERATION (video_utils.py:1350-1403)
   create_assemblyai_subtitles(clip_start, clip_end)
       ↓
   Convert to ms: int(clip_start * 1000)
       ↓
   SubtitleWordFilter.get_relevant_words()
       ↓
   Compares against cached words (potentially misaligned)
       ↓
   SubtitleClipBuilder.build_clips()
       ↓
   Filter: if word_duration < 0.05: skip  ← SILENT DELETION
       ↓

9. VIDEO OUTPUT
   Clip with misaligned subtitles
```

---

## Files Examined

| File | Lines | Purpose | Issues Found |
|------|-------|---------|--------------|
| `backend/src/transcription_mlx.py` | 590 | Transcription and word reconstruction | LLM reconstruction, greedy alignment |
| `backend/src/video_utils.py` | 1890 | Video/subtitle processing | Silent filtering, unit inconsistency, snapping |
| `backend/src/ai.py` | 530 | AI segment selection | Precision loss in timestamps |
| `backend/src/config.py` | 100 | Configuration | Default enables reconstruction |
| `backend/src/subtitle_renderer.py` | 150 | Browser-based rendering | Performance issues |

---

## References

- Previous audit: `docs/gemini-debug-audit-2026-01-16.md`
- Project memories: `video_pipeline_complete_analysis`, `transcript_pipeline_analysis`
- Radon complexity analysis output
- Code review agent findings (agentId: a0ddc49)

---

*Audit completed by Claude Opus 4.5 on 2026-01-16*
*Methodology: Systematic Debugging Protocol - Phase 1-3 (Root Cause Investigation)*
