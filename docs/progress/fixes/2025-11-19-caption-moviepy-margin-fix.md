# Caption Generation Fix - MoviePy 2.x Margin API

**Date:** 2025-11-19
**Severity:** CRITICAL
**Status:** RESOLVED

## Bug Summary

**Error:** `'TextClip' object has no attribute 'margin'`
**Impact:** 100% caption failure - 0 subtitles created on all clips
**Root Cause:** MoviePy 2.2.1 doesn't have `.margin()` method on TextClip - this is old MoviePy 1.x API

## Evidence from Logs

From `backend/logs/supoclip_2025-11-19_09-58-39.log`:

```
2025-11-19 09:59:28,629 - WARNING - Failed to create subtitle for 'show up unprepared.': 'TextClip' object has no attribute 'margin'
2025-11-19 09:59:28,629 - WARNING - Failed to create subtitle for 'If you're going to': 'TextClip' object has no attribute 'margin'
[... hundreds of similar errors ...]
2025-11-19 09:59:28,630 - INFO - Created 0 subtitle elements from AssemblyAI data
```

Result: All 4 clips generated successfully but with 0 captions.

## MoviePy API Change

MoviePy 2.x changed from method chaining to effects composition:

**Old API (MoviePy 1.x):**
```python
clip.margin(...)  # Does not work in 2.x
```

**New API (MoviePy 2.x):**
```python
from moviepy.video.fx import Margin
clip.with_effects([Margin(...)])  # Correct way
```

## The Fix

### Location
- **File:** `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py`
- **Line:** 926 (originally 925)
- **Function:** `SubtitleTextClipCreator.create_text_clip()`

### Changes Made

1. **Added Import (Line 14):**
```python
from moviepy.video.fx import Margin  # type: ignore
```

2. **Fixed Line 926:**

**Before:**
```python
text_clip = text_clip.margin(bottom=3, top=3, left=2, right=2, opacity=0)
```

**After:**
```python
text_clip = text_clip.with_effects([Margin(bottom=3, top=3, left=2, right=2, opacity=0)])
```

## Verification

- Syntax check: PASSED (`python -m py_compile src/video_utils.py`)
- Type check: PASSED (`mypy src/video_utils.py`)
- Only one instance of `.margin()` found and fixed
- Original intent preserved: prevent font stroke cutoff at edges

## Expected Outcomes

After the fix:
- Captions generate successfully on all clips
- Margin prevents stroke from being cut off at edges (original intent preserved)
- No `.margin()` AttributeError
- Subtitle count > 0 (instead of 0)
- Text appears at 75% down the video with proper margin

## Related Issues

This is the **third MoviePy API compatibility issue** fixed:
1. `newsize=` to `new_size=` (resized parameter)
2. `.resized(clip_size)` to `.resized(new_size=clip_size)` (keyword argument)
3. `.margin(...)` to `.with_effects([Margin(...)])` (method to effects) - THIS FIX

All three were caused by MoviePy 2.x API changes not being properly applied in the codebase.

## Testing Recommendations

After this fix, test with a short video to verify:
1. Clips generate successfully
2. Captions appear on clips
3. Caption text is not cut off at edges (margin working)
4. Font size and positioning look correct
5. Subtitle count > 0 in logs

## References

- Investigation report: `docs/progress/fixes/2025-11-19-caption-failure-investigation.md`
- Previous fix: commit e697bb9 (MoviePy resized parameter fix)
- Original margin addition: commit e9ace2c (font cutoff prevention)
