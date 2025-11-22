# Complete Video Processing Pipeline Analysis - THOROUGH EXPLORATION

## Executive Summary

The SupoClip video processing pipeline has a **well-architected multi-stage flow**, but the current reported issues (captions cut off, audio mismatch, caption misalignment) indicate **potential timing synchronization problems across multiple stages**. This document maps every function involved in transcription, timing handling, AI selection, and caption rendering.

---

## PHASE 1: COMPLETE TRANSCRIPTION PIPELINE

### Stage 1.1: Video Input Entry Points

**Files**: `backend/src/main.py`, `backend/src/services/video_service.py`

Entry points that initiate transcription:
1. `/start` endpoint (sync processing)
2. `/start-with-progress` endpoint (async processing with SSE)
3. Background job queue via `process_video_task()`

All three eventually call:
```
VideoService.process_video_complete() 
  → VideoService.generate_transcript(video_path)
    → get_video_transcript(video_path)
```

### Stage 1.2: Raw Transcription - parakeet-mlx

**File**: `backend/src/transcription_mlx.py` (lines 36-168)

**Function**: `transcribe_video_mlx(video_path, model_id="mlx-community/parakeet-tdt-0.6b-v2")`

**Key Implementation Details**:
- Line 108-112: Calls `model.transcribe(video_path, chunk_duration=120.0, overlap_duration=15.0)`
- Returns dict with 4 keys:
  - `text`: Full transcript string
  - `segments`: List of segment dicts (from parakeet sentences)
  - `words`: List of word-level timestamps (from parakeet tokens)
  - `language`: "en" (hardcoded)
  - `_cache_version`: 2 (for cache invalidation)

**CRITICAL TIMING FORMAT** (lines 250-252):
```python
start_ms = int(token.start * 1000)  # Convert float seconds to milliseconds
end_ms = int(token.end * 1000)      # Same conversion
```

**Word Reconstruction Feature** (lines 129-147):
- **Enabled by**: `config.reconstruct_words_with_llm` (default: true)
- **When**: If `RECONSTRUCT_WORDS_WITH_LLM=true` env var
- **What**: parakeet-mlx uses BPE tokenization → returns sub-word tokens
  - Example: word "hello" might become "hel", "lo" as separate tokens
  - Groq LLM reconstructs to complete "hello" while preserving timing
- **Function**: `_reconstruct_words_with_llm()` (lines 304-400)
- **Timing Re-alignment**: `_align_reconstructed_words()` (lines 404-486)
  - Maps reconstructed words to original token start/end times
  - Preserves millisecond precision from original tokens

**Caching Strategy** (lines 74-95):
- Cache path: `{video_stem}.transcript_cache.json` (same directory as video)
- Cache version check (line 86): If cached version ≠ TRANSCRIPT_CACHE_VERSION (2), re-transcribe
- Cache invalidation triggers re-transcription to apply word reconstruction

### Stage 1.3: Transcript Formatting for AI

**File**: `backend/src/video_utils.py` (lines 156-236)

**Function**: `get_video_transcript(video_path: Path) -> str`

**Process** (lines 156-236):
1. Calls `transcribe_video_mlx(video_path)` → returns dict with `words` array
2. Groups words into segments (~8 words per segment, max ~3-4 seconds)
3. Formats as: `[MM:SS - MM:SS] text content`
4. Returns newline-separated string for AI

**Timestamp Conversion Functions**:
- `format_ms_to_timestamp(ms: int) -> str` (lines 230-236)
  - Input: milliseconds (int)
  - Output: "MM:SS" format
  - Precision lost: milliseconds → seconds (1-second resolution)
- `format_ms_to_timestamp_precise(ms: int) -> str` (lines 238-244)
  - Input: milliseconds (int)
  - Output: "MM:SS.mmm" format (3 decimal precision)
  - Note: NOT used in current pipeline (appears to be legacy)

**CRITICAL TIMING POINT**: Word grouping at lines 173-179
```python
segment_text = " ".join(word["text"] for word in word_group)
segment_start = word_group[0]["start"]  # First word's start in ms
segment_end = word_group[-1]["end"]      # Last word's end in ms
```
Then converted via `format_ms_to_timestamp()` → loses millisecond precision.

**Example Output**:
```
[00:01 - 00:05] Welcome to the video today we're going to talk about something
[00:05 - 00:10] really important that will help you understand the basics
[00:10 - 00:14] of this technology and how it works in practice
```

---

## PHASE 2: AI SEGMENT SELECTION PIPELINE

### Stage 2.1: AI Analysis with Pydantic AI

**File**: `backend/src/ai.py` (lines 274-400)

**Function**: `async get_most_relevant_parts_by_transcript(transcript: str, min_length: int = 10, max_length: int = 45) -> TranscriptAnalysis`

**Input Format**:
- Formatted transcript string with `[MM:SS - MM:SS] text` format
- Min/max clip length in seconds

**AI Processing** (lines 302-365):
1. Builds dynamic prompt with clip length constraints
2. Sends to LLM (local or cloud) with `simplified_system_prompt` 
3. LLM returns JSON with `TranscriptSegment` list

**Returned TranscriptSegment Format** (lines 18-27):
```python
class TranscriptSegment(BaseModel):
    start_time: str        # MM:SS format (1-second precision)
    end_time: str          # MM:SS format (1-second precision)
    text: str              # Segment text
    relevance_score: float # 0.0-1.0
    reasoning: str         # Why relevant
```

**CRITICAL VALIDATION** (lines 371-385):
- `TranscriptSegmentValidator.validate_segment()` checks:
  1. start_time ≠ end_time (line 226)
  2. Duration ≥ 5 seconds minimum (line 198)
  3. Text has ≥ 3 words (line 216)
  4. Clean start (no filler words) (line 255)

**System Prompt Note** (lines 38-79):
- Line 73: "MINIMUM segment duration: 10 seconds"
- Line 76: "NEVER use the same timestamp for both start_time and end_time"
- "Use EXACT timestamps as they appear in the transcript"

### Stage 2.2: Timestamp Precision in AI

**PRECISION LOSS POINT**:
- Transcript input: `[00:01 - 00:05]` → 1-second precision
- AI processes MM:SS → returns MM:SS
- No millisecond information available to AI
- Result: AI clips are quantized to 1-second boundaries

**Example**:
- Actual word timing: "hello" starts at 1234ms, "world" ends at 5789ms
- Formatted for AI: [00:01 - 00:05]
- AI returns: start_time="00:01", end_time="00:05"
- Millisecond precision discarded

---

## PHASE 3: CAPTION RENDERING PIPELINE

### Stage 3.1: Subtitle Word Extraction

**File**: `backend/src/video_utils.py` (lines 858-887)

**Class**: `SubtitleWordFilter`

**Function**: `get_relevant_words(transcript_data, clip_start_ms, clip_end_ms) -> List[Dict]`

**Critical Process** (lines 862-887):
```python
# Convert clip float seconds to milliseconds
clip_start_ms = int(clip_start * 1000)  # Line 1036
clip_end_ms = int(clip_end * 1000)       # Line 1037

# Extract words overlapping clip timerange
for word_data in transcript_data.get("words", []):
    word_start = word_data["start"]  # milliseconds from cache
    word_end = word_data["end"]      # milliseconds from cache
    
    # Check overlap: word_start < clip_end_ms and word_end > clip_start_ms
    if word_start < clip_end_ms and word_end > clip_start_ms:
        # CRITICAL: Convert to relative times (offset from clip start)
        relative_start = max(0, (word_start - clip_start_ms) / 1000.0)  # Line 872
        relative_end = min(
            (clip_end_ms - clip_start_ms) / 1000.0,
            (word_end - clip_start_ms) / 1000.0,
        )
```

**Output Format** (lines 880-885):
```python
{
    "text": word_text,
    "start": relative_start,  # Float seconds from clip start
    "end": relative_end,      # Float seconds from clip start
    "confidence": confidence
}
```

**CRITICAL TIMING CONVERSION**:
- Word timings from cache: milliseconds (absolute from video start)
- Clip boundaries: float seconds (absolute from video start)
- OUTPUT: float seconds (relative from clip start = 0)

**Example**:
- Video word: "hello" at 12340ms-12890ms (absolute)
- Clip range: 10s-20s (10000ms-20000ms absolute)
- Relative timing: (12340-10000)/1000 = 2.34s start, (12890-10000)/1000 = 2.89s end

### Stage 3.2: Word Grouping and Timing

**File**: `backend/src/video_utils.py` (lines 961-1010)

**Class**: `SubtitleClipBuilder`

**Function**: `build_clips(relevant_words, font_path, font_size, font_color, video_width, video_height, words_per_subtitle=3)`

**Process** (lines 975-1010):
```python
for i in range(0, len(relevant_words), words_per_subtitle):  # Group by 3
    word_group = relevant_words[i : i + words_per_subtitle]
    
    # Calculate timing from first and last word
    segment_start = word_group[0]["start"]  # Relative float seconds
    segment_end = word_group[-1]["end"]     # Relative float seconds
    segment_duration = segment_end - segment_start
    
    # Create text clip with timing
    text_clip = text_clip.with_duration(segment_duration).with_start(segment_start)
```

**CRITICAL**: All timings at this point are relative to clip start (0.0 = clip start).

### Stage 3.3: Text Rendering with Margin

**File**: `backend/src/video_utils.py` (lines 890-948)

**Class**: `SubtitleTextClipCreator`

**Function**: `create_text_clip(text, font_path, font_size, font_color, video_width)`

**Margin Calculation** (lines 926-932):
```python
# Dynamic margin based on font size
# Formula: accounts for descenders (20-25%), stroke (1px), buffer
bottom_margin = max(5, int(current_font_size * 0.35))

text_clip = text_clip.with_effects(
    [Margin(bottom=bottom_margin, top=5, left=3, right=3, opacity=0)]
)
```

**Margin Examples**:
- 16px font → 5px margin
- 20px font → 7px margin
- 24px font → 8px margin
- 30px font → 10px margin
- 40px font → 14px margin

**Recent Fix** (commit c8a093b, 2025-11-19):
- Changed from fixed 12px to dynamic calculation
- Prevents descender clipping on g, p, y, j, q

### Stage 3.4: Positioning and Composition

**File**: `backend/src/video_utils.py` (lines 951-1003)

**Positioning** (lines 951-958):
```python
class SubtitlePositioner:
    @staticmethod
    def calculate_position(video_height: int, text_height: int) -> Tuple[str, int]:
        vertical_position = int(video_height * 0.75 - text_height // 2)  # 75% down
        return ("center", vertical_position)
```

**Composition** (lines 1051-1058 in `create_assemblyai_subtitles`):
```python
subtitle_clips = SubtitleClipBuilder.build_clips(
    relevant_words,
    processor.font_path,
    calculated_font_size,
    font_color,
    video_width,
    video_height,
)
```

Then in `create_optimized_clip` (lines 1135-1146):
```python
if add_subtitles:
    subtitle_clips = create_assemblyai_subtitles(
        video_path,
        start_time,      # Float seconds, absolute from video
        end_time,        # Float seconds, absolute from video
        new_width,
        new_height,
        ...
    )
    final_clips.extend(subtitle_clips)

final_clip = CompositeVideoClip(final_clips) if len(final_clips) > 1 else cropped_clip
```

---

## PHASE 4: COMPLETE TIMING DATA FLOW

### Complete Flow Diagram

```
1. VIDEO TRANSCRIPTION
   Video file (.mp4)
        ↓
   parakeet-mlx model
        ↓
   parakeet result with tokens
   - token.start (float seconds)
   - token.end (float seconds)
   - token.text (string)
        ↓
   _extract_words_from_result()
   - Convert seconds to milliseconds: int(seconds * 1000)
   - Output: {text, start_ms, end_ms, confidence}
        ↓
   [OPTIONAL] Word reconstruction via Groq
   - Reconstruct sub-word tokens to complete words
   - Re-align timing while preserving ms precision
        ↓
   Cache: {video}.transcript_cache.json
   └─ Contains words[] with millisecond timing


2. FORMATTING FOR AI
   Cached words[] (milliseconds, absolute)
        ↓
   get_video_transcript()
   - Groups words into segments (~8 words)
   - Extracts first word start, last word end
        ↓
   format_ms_to_timestamp() 
   - Convert: milliseconds → MM:SS (1-second precision loss)
        ↓
   Formatted transcript string
   └─ Example: "[00:01 - 00:05] Welcome to the video..."


3. AI ANALYSIS
   Formatted transcript (MM:SS precision)
        ↓
   get_most_relevant_parts_by_transcript()
   - AI processes MM:SS timestamps
   - AI returns segments with MM:SS format
        ↓
   TranscriptSegment[]
   └─ {start_time: "MM:SS", end_time: "MM:SS", text, score, reasoning}


4. CLIP CREATION
   TranscriptSegment[] (MM:SS format)
        ↓
   create_clips_from_segments()
   - parse_timestamp_to_seconds("MM:SS") → float seconds
   - Example: "01:23" → 83.0 seconds
        ↓
   create_optimized_clip(video_path, start_seconds, end_seconds)
   - Subclips video: video.subclipped(start, end)
   - Crops to 9:16 aspect ratio
   - Scales to target resolution
        ↓
   [For each clip] create_assemblyai_subtitles()
   - Receives: start_time (float seconds, absolute), end_time (float seconds, absolute)
   - Loads: {video}.transcript_cache.json → words[] (milliseconds, absolute)


5. SUBTITLE EXTRACTION & POSITIONING
   Cached words[] + clip boundaries
        ↓
   SubtitleWordFilter.get_relevant_words()
   - Convert clip times: float seconds → milliseconds
     clip_start_ms = int(start_time * 1000)
     clip_end_ms = int(end_time * 1000)
   - Find words overlapping [clip_start_ms, clip_end_ms]
   - Convert to relative timing:
     relative_start = (word_start_ms - clip_start_ms) / 1000.0
     relative_end = (word_end_ms - clip_start_ms) / 1000.0
        ↓
   relevant_words[] (float seconds, relative to clip start)
   └─ [{text, start: 1.23, end: 1.89}, ...]


6. SUBTITLE GROUPING & COMPOSITION
   relevant_words[] (relative timing)
        ↓
   SubtitleClipBuilder.build_clips(words_per_subtitle=3)
   - Group every 3 words
   - Set duration: segment_end - segment_start
   - Set start: segment_start (relative)
        ↓
   TextClip[] with timing
   └─ Each clip: start=relative_ms, duration=seconds_between_words


7. VIDEO COMPOSITION
   Video clip + TextClip[] (all in relative time)
        ↓
   CompositeVideoClip([video] + subtitle_clips + logo_clips)
        ↓
   write_videofile() → output .mp4
        ↓
   Generated clip
```

---

## CRITICAL TIMING POINTS & PRECISION ANALYSIS

| Stage | Input Format | Output Format | Precision | Conversion Function | Time Base | Relative/Absolute |
|-------|------|------|-----------|--------|----------|------|
| parakeet-mlx | float seconds | milliseconds (int) | 1ms | `int(s * 1000)` | Absolute | Absolute |
| Word cache | milliseconds (int) | milliseconds (int) | 1ms | None | Absolute | Absolute |
| AI formatting | milliseconds (int) | MM:SS string | 1 second | `format_ms_to_timestamp()` | Absolute | Absolute |
| AI analysis | MM:SS string | MM:SS string | 1 second | None (AI decides) | Absolute | Absolute |
| Clip extraction | MM:SS string | float seconds | Millisecond | `parse_timestamp_to_seconds()` | Absolute | Absolute |
| Subtitle filtering | Absolute ms + float s | Relative float s | Millisecond | `(ms - clip_start_ms) / 1000.0` | Absolute → Relative | Relative |
| MoviePy composition | Relative float s | MoviePy internal | Internal | None (passed directly) | Relative | Relative |

---

## IDENTIFIED ISSUES & HYPOTHESES

### HYPOTHESIS 1: Floating-Point Precision Loss in Timestamp Conversion

**Evidence**:
1. `format_ms_to_timestamp()` line 236: Takes int milliseconds, outputs MM:SS (truncates to seconds)
2. AI receives MM:SS with 1-second quantization
3. `parse_timestamp_to_seconds()` line 836: Takes MM:SS, parses back to float seconds
4. Example: 1234ms → "00:01" → 1.0s (233ms of precision lost)

**Impact**:
- Clip start/end times could be off by up to 1 second
- If clip boundary falls in middle of a word, subtitle timing errors occur
- 1-second error over a 10-45 second clip = 2-10% timing drift

**Probability**: MEDIUM-HIGH (precision loss is intentional but could cause off-by-one issues)

---

### HYPOTHESIS 2: Millisecond-to-Second Conversion Bug in Subtitle Filtering

**Evidence**:
1. Line 1036-1037: `clip_start_ms = int(clip_start * 1000)` where `clip_start` is float seconds
2. Line 872: `relative_start = max(0, (word_start - clip_start_ms) / 1000.0)` 
3. If `clip_start = 10.5` seconds (from AI rounding "10.5" back to float):
   - `clip_start_ms = int(10.5 * 1000) = 10500`
   - Correct value should be 10500ms
   - But if there was rounding earlier, timing could be off

**Impact**:
- Words at clip boundaries might be incorrectly filtered
- Word timing relative to clip could be inverted or negative
- Subtitles could start too early or too late

**Probability**: MEDIUM (depends on how `parse_timestamp_to_seconds()` handles edge cases)

---

### HYPOTHESIS 3: Cache Staleness from Word Reconstruction

**Evidence**:
1. `TRANSCRIPT_CACHE_VERSION = 2` (line 33 in transcription_mlx.py)
2. Word reconstruction enabled by default (line 129-135)
3. Old caches (v1) have different word timings than v2
4. If cache wasn't invalidated on deployment, old timings are used

**Impact**:
- Subtitle words have incorrect absolute millisecond timings
- All relative timings calculated from cache would be wrong
- Audio/caption mismatch across all clips for users with old caches

**Probability**: LOW-MEDIUM (cache version check is in place, but user-specific caches might exist)

---

### HYPOTHESIS 4: Word Grouping Logic Breaking Synchronization

**Evidence**:
1. Line 976: `for i in range(0, len(relevant_words), words_per_subtitle)` with `words_per_subtitle=3`
2. Line 981-982: `segment_start = word_group[0]["start"]` and `segment_end = word_group[-1]["end"]`
3. If a word's relative timing is calculated incorrectly (Hypothesis 2), grouping uses wrong times
4. Line 985-986: Skips groups with `segment_duration < 0.1` seconds

**Impact**:
- Subtitle groups might skip words or group wrong words together
- Timing gaps between groups could cause subtitles to disappear
- If relative_end < relative_start, segment is skipped entirely

**Probability**: MEDIUM (depends on subtitle filtering being correct)

---

### HYPOTHESIS 5: Clip Start Time Offset Not Applied to All Words

**Evidence**:
1. Line 1036-1039: Converts clip times to ms and calls `SubtitleWordFilter.get_relevant_words()`
2. Line 872: Correctly calculates `relative_start = (word_start - clip_start_ms) / 1000.0`
3. But what if `word_start` comes from cache that's in absolute time, while clip is in relative time?

**Impact**:
- If there's any mismatch in absolute vs. relative time interpretation
- Subtitles could be offset by the clip start time
- Audio at 00:25-00:45 → captions showing 00:00-00:20 content

**Probability**: MEDIUM-HIGH (requires careful tracking through multiple conversions)

---

### HYPOTHESIS 6: MoviePy Timing Issues with Relative vs. Absolute

**Evidence**:
1. Line 1104: `clip = video.subclipped(start_time, end_time)` - creates new clip with relative=0
2. Line 996-997: `text_clip.with_duration(...).with_start(segment_start)` - segment_start is relative
3. Line 1189: `CompositeVideoClip([cropped_clip] + subtitle_clips)` - mixing clips
4. MoviePy 2.x may have different time handling than v1

**Impact**:
- Subtitle timing relative to cropped clip might not align with subclipped video
- Captions could be offset if MoviePy interprets times differently
- Logo and captions might use different time bases

**Probability**: MEDIUM (MoviePy version changes could affect this)

---

### HYPOTHESIS 7: Audio Processing Not Synced with Video

**Evidence**:
1. Line 1197-1200: `write_videofile()` with `temp_audiofile="temp-audio.m4a"`
2. No evidence of audio extraction or reprocessing between transcription and rendering
3. Original video audio used as-is
4. If audio stretch/compression happens during cropping, captions wouldn't match

**Impact**:
- Captions match original full video timestamps
- But audio might be resampled or compressed
- Results in audio-caption mismatch

**Probability**: LOW (audio should be passed through unchanged)

---

## KEY CODE LOCATIONS FOR INVESTIGATION

### For Timing Issues:
1. `backend/src/video_utils.py:826-850` - `parse_timestamp_to_seconds()` function
2. `backend/src/video_utils.py:862-887` - `SubtitleWordFilter.get_relevant_words()`
3. `backend/src/video_utils.py:972-1010` - `SubtitleClipBuilder.build_clips()`
4. `backend/src/transcription_mlx.py:250-252` - Word timing extraction

### For Word Reconstruction:
5. `backend/src/transcription_mlx.py:304-400` - `_reconstruct_words_with_llm()`
6. `backend/src/transcription_mlx.py:404-486` - `_align_reconstructed_words()`
7. `backend/src/config.py:30-31` - `RECONSTRUCT_WORDS_WITH_LLM` config

### For Cache Issues:
8. `backend/src/transcription_mlx.py:73-95` - Cache loading logic
9. `backend/src/transcription_mlx.py:149-159` - Cache saving logic

### For AI Timing:
10. `backend/src/ai.py:38-79` - System prompt with timing requirements
11. `backend/src/ai.py:164-204` - `TimestampParser` class

### For Clip Creation:
12. `backend/src/video_utils.py:1216-1292` - `create_clips_from_segments()`
13. `backend/src/video_utils.py:1064-1209` - `create_optimized_clip()`

---

## TESTING RECOMMENDATIONS

1. **Word Timing Precision Test**:
   - Transcribe test video
   - Log all word timings (ms) from cache
   - Log clip boundaries (float seconds)
   - Log relative word timings after conversion
   - Verify: no timing inversions, no gaps, all words within clip bounds

2. **Cache Version Test**:
   - Delete all `.transcript_cache.json` files
   - Re-transcribe with word reconstruction
   - Compare v1 vs v2 word timings
   - Verify: v2 has complete words, not sub-word tokens

3. **Subtitle Sync Test**:
   - Create test video with distinctive audio markers
   - Generate clips
   - Play back and verify: captions start/end match audio
   - Check: no captions lag/lead audio by >200ms

4. **Boundary Condition Test**:
   - Test clips that start/end at sub-second boundaries
   - Test with AI-selected times that round to .5 seconds
   - Verify: no off-by-one second errors

---

## SUMMARY OF PIPELINE ARCHITECTURE

**Timing Precision by Stage**:
- Transcription: 1ms (parakeet provides per-token timing)
- Cache: 1ms (stored as int milliseconds)
- AI Input: 1 second (formatted as MM:SS)
- AI Output: 1 second (returned as MM:SS)
- Clip Creation: 1 millisecond (float seconds support sub-second precision)
- Subtitle Rendering: 1 millisecond (MoviePy supports float seconds)

**Precision Loss Points**:
1. `format_ms_to_timestamp()` - intentional (for AI readability)
2. `parse_timestamp_to_seconds()` - could compound rounding errors if called multiple times

**No Data Format Mismatches Detected** - all conversions appear correctly implemented, but edge cases around floating-point rounding could cause issues.

---

## CONFIGURATION FACTORS

From `backend/src/config.py`:
- `RECONSTRUCT_WORDS_WITH_LLM=true` (default) - enables word reconstruction
- `LOCAL_LLM_ENABLED=true` (default) - uses local LLM for segment selection
- `PARAKEET_MODEL=mlx-community/parakeet-tdt-0.6b-v2` (default)
- `TEMP_DIR=temp` - where transcription cache is stored

---

## NEXT INVESTIGATION STEPS

1. Collect user-reported clip files with misaligned captions
2. Examine corresponding `.transcript_cache.json` files
3. Trace through timing calculations with real data
4. Compare word timings in cache vs. captions in generated clip
5. Check if issue is systematic (all clips) or clip-specific
6. Verify `RECONSTRUCT_WORDS_WITH_LLM` setting matches deployment

