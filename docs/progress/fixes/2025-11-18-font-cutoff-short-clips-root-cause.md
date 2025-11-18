# Root Cause Analysis: Font Cutoff and Short Clips Issues
Date: 2025-11-18

## Executive Summary

Two critical issues identified from user testing:
1. **Font Cutoff Issue**: Captions are vertically cropped (text cut in half)
2. **Short Clips Issue**: AI generates 11-16 second clips despite user setting 47-58 seconds

**Status**: Both root causes identified with high confidence (90%+)

---

## Issue #1: Font Cutoff - Text Vertically Cropped

### User Report
- **Screenshot Evidence**: Captions appear with bottom portion cut off
- **Font**: "Barlow Condensed Bold" at 30px
- **Expected**: Full text visible
- **Actual**: Text appears to be cut in half vertically

### Root Cause Analysis

**Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py:906-914`

**Root Cause**: MoviePy TextClip using `method="caption"` with constrained `size` parameter

```python
# Line 906-914 in video_utils.py
text_clip = TextClip(
    text=text,
    font=font_path,
    font_size=current_font_size,
    color=font_color,
    stroke_color="black",
    stroke_width=1,
    method="caption",  # ← ROOT CAUSE: caption mode crops text
    size=(max_text_width, None),  # ← Constrains width but allows height overflow
    text_align="center",
)
```

**Why This Causes Cutoff**:
- `method="caption"` renders text within a fixed bounding box
- `size=(max_text_width, None)` constrains width but sets height to None
- When font size is large (30px) or text wraps, it exceeds the implicit height constraint
- MoviePy crops any text that overflows the bounding box
- Result: Bottom of text is cut off

**Supporting Evidence**:
1. Log shows font correctly applied: "font_family=Barlow Condensed Bold, font_size=30"
2. Screenshot shows text IS rendering but IS cut off
3. MoviePy documentation states `method="caption"` is for fixed-size text boxes with wrapping

**Confidence Level**: 95% - This is the exact pattern that causes text cropping in MoviePy

### Fix Strategy

**Option 1: Use method="label" (RECOMMENDED)**
```python
text_clip = TextClip(
    text=text,
    font=font_path,
    font_size=current_font_size,
    color=font_color,
    stroke_color="black",
    stroke_width=1,
    method="label",  # ← FIX: label mode auto-sizes to fit text
    # Remove size parameter entirely for label mode
    text_align="center",
)
```

**Option 2: Calculate proper height for caption mode**
```python
# Calculate required height before creating TextClip
estimated_height = current_font_size * 1.5 * estimated_lines
size = (max_text_width, int(estimated_height * 1.2))  # 20% padding
```

**Recommendation**: Use Option 1 (method="label") - simpler and more reliable

---

## Issue #2: Short Clips - AI Ignoring Length Parameters

### User Report
- **Screenshot Evidence**: Clip 1 duration is 06:38.680 - 06:50.040 = 11.36 seconds
- **Expected**: User likely set slider to 47-58 seconds
- **Actual**: Clips are 11-17 seconds long

### Root Cause Analysis

**Hypothesis Validated**: AI prompt has hardcoded duration constraints that override dynamic parameters

#### Evidence from Logs

**Parameters ARE being received correctly**:
```
2025-11-18 16:25:10 - src.services.video_service - INFO - 🟢 Processing video with parameters:
  font_family=Barlow Condensed Bold, font_size=30, font_color=#FFFFFF, clip_length=47s-58s

2025-11-18 16:25:12 - src.ai_structured - INFO - 🟢 Clip length settings - Min: 47s, Max: 58s
```

**But AI generates short clips anyway**:
```
2025-11-18 16:02:05 - src.ai_structured - INFO - 🟢 Groq response duration analysis:
  avg=14.39s, min=8.96s, max=16.96s

2025-11-18 16:02:05 - src.video_utils - INFO - 🟢 Segment 1 duration: 17.0s
2025-11-18 16:02:07 - src.video_utils - INFO - 🟢 Segment 2 duration: 12.6s
2025-11-18 16:02:08 - src.video_utils - INFO - 🟢 Segment 3 duration: 15.7s
2025-11-18 16:02:10 - src.video_utils - INFO - 🟢 Segment 4 duration: 15.9s
2025-11-18 16:02:11 - src.video_utils - INFO - 🟢 Segment 5 duration: 16.2s
```

**User's actual clip**:
```
clip_1_0638.680-0650.040.mp4 = 11.36 seconds (when user requested 47-58s range!)
```

#### Root Cause Location

**File**: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

**Problem**: Hardcoded SYSTEM_PROMPT overrides dynamic user parameters

**Line 56-58** (SYSTEM_PROMPT hardcoded constraints):
```python
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (DO NOT return segments shorter than 10 seconds)
- MAXIMUM DURATION: 45 seconds per segment
```

**Line 160** (User prompt with dynamic parameters):
```python
f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
```

**Why This Fails**:
1. SYSTEM_PROMPT is sent first and has stronger weight with LLMs
2. SYSTEM_PROMPT hardcodes "10 seconds minimum, 45 seconds maximum"
3. User prompt says "47-58 seconds" but comes second and conflicts
4. LLM prioritizes SYSTEM_PROMPT over conflicting user instructions
5. Result: AI generates clips in the 10-45s range, ignoring user's 47-58s preference

**Confidence Level**: 90% - Classic LLM prompt override pattern

#### Additional Evidence

**Validation is working** (lines 274-279 in ai_structured.py):
```python
if duration < 10:
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 10s required). Text: '{segment.text[:40]}...'"
    )
    continue
```

This shows validation is hardcoded to 10s minimum, NOT using min_length parameter!

### Fix Strategy

**Fix 1: Make SYSTEM_PROMPT dynamic** (RECOMMENDED)
```python
# Replace hardcoded SYSTEM_PROMPT with a function
def build_system_prompt(min_length: int, max_length: int) -> str:
    return f"""You are an expert video clip curator...

DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: {min_length} seconds per segment
- MAXIMUM DURATION: {max_length} seconds per segment
- Duration calculation: end_time - start_time MUST be >= {min_length} seconds
- If a segment is less than {min_length} seconds, DO NOT include it
...
"""
```

**Fix 2: Update validation to use min_length** (REQUIRED)
```python
# Line 274 - Change hardcoded 10 to min_length
if duration < min_length:  # ← Instead of hardcoded 10
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min {min_length}s required). Text: '{segment.text[:40]}...'"
    )
    continue
```

**Fix 3: Add max_length validation** (NEW)
```python
# Add after line 279
if duration > max_length:
    logger.warning(
        f"REJECTED: Too long - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(max {max_length}s allowed). Text: '{segment.text[:40]}...'"
    )
    continue
```

---

## Production Log Evidence

### Most Recent Run (Failed due to Groq API error)
```
2025-11-18 16:25:10 - Processing video with parameters:
  font_family=Barlow Condensed Bold, font_size=30, clip_length=47s-58s

2025-11-18 16:25:12 - Clip length settings - Min: 47s, Max: 58s

# Then Groq API failed with tool_use_failed error
```

### Successful Run with Short Clips (Evidence of Issue #2)
```
2025-11-18 16:02:03 - Clip length settings - Min: 35s, Max: 58s

2025-11-18 16:02:05 - Groq response duration analysis:
  avg=14.39s, min=8.96s, max=16.96s  ← AI IGNORED the 35-58s range!

2025-11-18 16:02:05 - Segment 1 duration: 17.0s (start: 77.44s, end: 94.399s)
2025-11-18 16:02:07 - Segment 2 duration: 12.6s
2025-11-18 16:02:08 - Segment 3 duration: 15.7s
```

---

## Impact Assessment

### Issue #1 (Font Cutoff)
- **Severity**: High - Affects ALL clips with subtitles
- **User Impact**: Captions are unreadable, defeating the purpose
- **Workaround**: None - users cannot fix this themselves
- **Affects**: 100% of generated clips

### Issue #2 (Short Clips)
- **Severity**: Critical - Users cannot control clip length
- **User Impact**: Cannot generate longer clips for platforms requiring 30-60s content
- **Workaround**: None - slider does not work
- **Affects**: Any user setting clip length > 45s (parameter flow works, AI ignores it)

---

## Dependencies and Risks

### Fix Implementation Order
1. **Issue #2 first**: Easier fix, higher impact
2. **Issue #1 second**: Requires testing with various fonts/sizes

### Regression Risks
- **Issue #1 fix**: May affect text positioning if switching from caption to label mode
- **Issue #2 fix**: Must ensure validation still rejects <10s clips (absolute minimum)

### Testing Requirements
- Test with multiple fonts (small, large, condensed, wide)
- Test with various clip lengths (10-20s, 30-45s, 50-60s)
- Verify text still positions at 75% down video
- Ensure text wrapping still works correctly

---

## Next Steps

1. **Create failing tests** that demonstrate both issues
2. **Implement Fix #2** (short clips) - simpler and higher impact
3. **Implement Fix #1** (font cutoff) - more complex, requires testing
4. **Run full test suite** to verify no regressions
5. **User validation** with actual video processing

---

## Files Requiring Changes

### Issue #1 (Font Cutoff)
- `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py:906-914`
  - Change `method="caption"` to `method="label"`
  - Remove or adjust `size` parameter

### Issue #2 (Short Clips)
- `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py:50-97`
  - Convert SYSTEM_PROMPT to function with min_length/max_length parameters
- `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py:274-279`
  - Replace hardcoded 10 with min_length parameter
  - Add max_length validation

### Additional Files to Check
- `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py:167-203`
  - TimestampParser class may also have hardcoded MIN_DURATION_SECONDS = 5
  - Verify this doesn't conflict with user's min_length setting

---

## Test Plan

### Test #1: Font Cutoff Reproduction
```python
def test_textclip_caption_mode_cuts_off_text():
    """
    Demonstrates that method='caption' with size=(width, None)
    causes text to be vertically cropped.
    """
    # Create TextClip with large font
    text = "This is a long caption that should wrap multiple lines"
    clip = TextClip(
        text=text,
        font="Barlow-Condensed-Bold.ttf",
        font_size=30,
        method="caption",
        size=(400, None),  # ← This causes cutoff
    )

    # Expected: Full text visible
    # Actual: Text will be cropped if it exceeds implicit height

    # Test will fail when checking rendered frame
    assert verify_text_fully_visible(clip)  # Should fail
```

### Test #2: Short Clips Despite Long Settings
```python
async def test_ai_ignores_clip_length_parameters():
    """
    Demonstrates that AI generates short clips (10-20s)
    even when min_length=47, max_length=58.
    """
    transcript = load_test_transcript()

    # Request 47-58 second clips
    result = await analyze_transcript_structured(
        transcript=transcript,
        min_length=47,
        max_length=58
    )

    # Calculate actual durations
    durations = [
        calculate_duration(seg.start_time, seg.end_time)
        for seg in result.most_relevant_segments
    ]

    # Expected: All clips 47-58s
    # Actual: Clips will be 10-20s (test should fail)
    for duration in durations:
        assert duration >= 47, f"Clip too short: {duration}s (expected >= 47s)"
        assert duration <= 58, f"Clip too long: {duration}s (expected <= 58s)"
```

---

## Confidence Assessment

| Finding | Confidence | Evidence |
|---------|------------|----------|
| Font cutoff caused by method="caption" | 95% | MoviePy docs, screenshot evidence, code analysis |
| Short clips caused by hardcoded SYSTEM_PROMPT | 90% | Log evidence showing AI ignoring parameters |
| Parameters flow correctly to backend | 100% | Logs show "clip_length=47s-58s" received |
| Validation uses hardcoded values | 100% | Code shows "if duration < 10" not "if duration < min_length" |

## Conclusion

Both issues have clear root causes with straightforward fixes:
1. **Font Cutoff**: Change TextClip method from "caption" to "label"
2. **Short Clips**: Make SYSTEM_PROMPT dynamic and update validation to use min_length/max_length

Fixes can be implemented independently with minimal regression risk.
