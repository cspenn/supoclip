# Caption Failure Investigation Report
Date: 2025-11-19

## Executive Summary

**Issue:** Video clips are being generated successfully, but captions/subtitles are failing to be added.

**Root Cause:** MoviePy API incompatibility - `TextClip` objects do not have a `.margin()` method in MoviePy 2.2.1+.

**Impact:** ALL captions fail with error: `'TextClip' object has no attribute 'margin'`

**Status:** Root cause identified, fix required

---

## Investigation Details

### 1. Log Analysis

**Most Recent Log:** `backend/logs/backend-2025-11-19_09-58-02.log`

**Error Pattern Found:**
```
2025-11-19 09:58:39 - src.video_utils - WARNING - 🟡 Failed to create subtitle for 'show up unprepared.': 'TextClip' object has no attribute 'margin'
2025-11-19 09:58:39 - src.video_utils - WARNING - 🟡 Failed to create subtitle for 'None of these': 'TextClip' object has no attribute 'margin'
[... repeated for EVERY subtitle ...]
2025-11-19 09:58:39 - src.video_utils - INFO - 🟢 Created 0 subtitle elements from AssemblyAI data
```

**Key Observations:**
- Video processing succeeds (download, transcription, AI analysis, cropping, scaling)
- Face detection works (81-84 faces detected)
- Font loading succeeds
- Caption generation fails for EVERY word/phrase
- Final result: **0 subtitle elements created**

### 2. Root Cause Analysis

**Problematic Code Location:**
- **File:** `backend/src/video_utils.py`
- **Line:** 925
- **Class:** `SubtitleTextClipCreator`
- **Method:** `create_text_clip()`

**Problematic Code:**
```python
text_clip = TextClip(
    text=text,
    font=font_path,
    font_size=current_font_size,
    color=font_color,
    stroke_color="black",
    stroke_width=1,
    method="label",
    text_align="center",
)

# Add margin to prevent stroke from being cut off at edges
text_clip = text_clip.margin(bottom=3, top=3, left=2, right=2, opacity=0)  # ❌ THIS LINE FAILS
```

**Why It Fails:**
1. `TextClip` objects in MoviePy 2.2.1+ do NOT have a `.margin()` method
2. The `.margin()` syntax is from an older MoviePy API (pre-2.0)
3. MoviePy 2.x uses effects system: effects are applied via `.with_effects([Effect(...)])`

### 3. MoviePy API Investigation

**Current MoviePy Version:** `>=2.2.1` (from pyproject.toml)

**Correct API Usage for MoviePy 2.x:**
```python
from moviepy.video.fx import Margin

# OLD WAY (MoviePy 1.x) - DOESN'T WORK:
text_clip = text_clip.margin(bottom=3, top=3, left=2, right=2, opacity=0)

# NEW WAY (MoviePy 2.x) - CORRECT:
text_clip = text_clip.with_effects([Margin(bottom=3, top=3, left=2, right=2, opacity=0)])
```

**Margin Effect Signature:**
```python
Margin(
    margin_size: int = None,  # Uniform margin on all sides
    left: int = 0,
    right: int = 0,
    top: int = 0,
    bottom: int = 0,
    color: tuple = (0, 0, 0),  # RGB color
    opacity: float = 1.0,       # 0.0 = transparent, 1.0 = opaque
)
```

### 4. When Was This Bug Introduced?

**Git Commit History:**
```
e9ace2c feat(video): add selectable output resolution and fix caption text trimming
```

**Analysis:**
The `.margin()` call was introduced in commit `e9ace2c` to fix font cutoff issues. The intent was correct (add padding to prevent stroke cutoff), but the API usage was incorrect for MoviePy 2.x.

**Related Context:**
- This commit also changed from `method="caption"` to `method="label"` to prevent text cutoff
- The commit also fixed the `newsize=` vs `new_size=` parameter issue in another location
- The margin fix was well-intentioned but used the wrong API

### 5. Impact Assessment

**Severity:** CRITICAL - Complete caption failure

**Affected Functionality:**
- ALL generated video clips have NO captions
- Clips are generated successfully (download, crop, scale)
- But clips are unusable for their primary purpose (viral short clips need captions)

**User Experience:**
- Users see clips generated successfully
- No error is displayed to user (warnings only in logs)
- Clips play but have no subtitles
- Users don't understand why captions are missing

### 6. Related Issues

**No Other Caption Issues Found:**
- Font loading: ✅ Working (found system font successfully)
- Transcription: ✅ Working (word-level timing data exists)
- Text positioning: ✅ Would work if margin issue fixed
- Segment selection: ✅ Working (3 segments identified)

**Only Issue:** The `.margin()` API call

---

## Fix Recommendation

### Required Code Change

**Location:** `backend/src/video_utils.py`, line 925

**Current Code (BROKEN):**
```python
# Add margin to prevent stroke from being cut off at edges
text_clip = text_clip.margin(bottom=3, top=3, left=2, right=2, opacity=0)
```

**Fixed Code:**
```python
# Add margin to prevent stroke from being cut off at edges
from moviepy.video.fx import Margin
text_clip = text_clip.with_effects([Margin(bottom=3, top=3, left=2, right=2, opacity=0)])
```

**Note:** The `from moviepy.video.fx import Margin` import should be added at the top of the file with other MoviePy imports.

### Import Statement Update

**Current imports in video_utils.py:**
```python
from moviepy.video.VideoClip import VideoClip, ColorClip, TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
```

**Add to imports:**
```python
from moviepy.video.fx import Margin
```

### Testing Requirements

After fix is applied, verify:
1. Captions appear on generated clips
2. Caption text is not cut off at edges
3. Caption positioning is correct (75% down the video)
4. Font styling is preserved (stroke, color, size)
5. No regression in video processing pipeline

---

## Prevention Recommendations

### 1. API Version Testing
- Add integration tests that verify caption generation
- Test with actual video processing, not just unit tests
- Catch API compatibility issues before deployment

### 2. Error Handling Improvement
- Current behavior: Logs warnings, returns 0 subtitles, continues processing
- Better behavior: Fail fast when captions fail, report error to user
- Users should know immediately if captions failed

### 3. Documentation Updates
- Document MoviePy version requirements clearly
- Note API changes between MoviePy 1.x and 2.x
- Add comments explaining why specific API patterns are used

### 4. MoviePy API Usage Audit
- Review all MoviePy API usage in codebase
- Verify all methods are compatible with MoviePy 2.x
- Check for other deprecated API patterns

---

## Next Steps

1. ✅ **Investigation Complete** - Root cause identified
2. ⏳ **Fix Implementation** - Update line 925 in video_utils.py
3. ⏳ **Testing** - Verify captions work on generated clips
4. ⏳ **Git Checkpoint** - Commit fix with descriptive message
5. ⏳ **User Verification** - Process a video and confirm captions appear

---

## Technical Details

### MoviePy 2.x Effects System

**Key Concepts:**
1. **Effects are classes:** `Margin`, `Resize`, `Crop`, etc.
2. **Applied via `.with_effects()`:** Pass list of effect instances
3. **No method chaining:** Can't do `.margin().resize()`
4. **Effect composition:** Multiple effects in one list: `.with_effects([Effect1(...), Effect2(...)])`

**Example:**
```python
from moviepy.video.fx import Margin, Resize

# Apply multiple effects
clip = clip.with_effects([
    Margin(bottom=3, top=3, opacity=0),
    Resize(new_size=(720, 1280))
])
```

### Why This Matters

The MoviePy 2.x API change from method chaining to effects composition was a breaking change. Code written for MoviePy 1.x needs updates to work with 2.x. This is a common migration issue when upgrading MoviePy versions.

---

## Conclusion

The caption failure is caused by using a deprecated MoviePy 1.x API (`.margin()` method) in a MoviePy 2.x environment. The fix is straightforward: replace the method call with the proper effects syntax using `.with_effects([Margin(...)])`.

This is a single-line fix (plus import) that will restore full caption functionality.
