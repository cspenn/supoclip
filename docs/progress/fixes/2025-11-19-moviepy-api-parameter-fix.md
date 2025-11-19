# MoviePy API Parameter Bug Fix

**Date:** 2025-11-19
**Severity:** HIGH - 100% clip generation failure
**Status:** FIXED

## Bug Summary

**Error:** `VideoClip.resized() got an unexpected keyword argument 'newsize'`

**Impact:**
- 100% clip generation failure rate
- All 4 clips failed to generate in test runs
- Task shows "completed" status but produces 0 clips
- Complete failure of video output despite successful download, transcription, and AI analysis

**Root Cause:**
MoviePy 2.2.1 API requires `new_size=` parameter (with underscore), but code was using `newsize=` (without underscore) or positional argument.

## Evidence

### Log Evidence
From `backend/logs/supoclip_2025-11-19_09-29-59.log`:

```
2025-11-19 09:32:41,747 - ❌ Error creating clip 1: VideoClip.resized() got an unexpected keyword argument 'newsize'
2025-11-19 09:32:41,747 - ❌ Error creating clip 2: VideoClip.resized() got an unexpected keyword argument 'newsize'
2025-11-19 09:32:41,748 - ❌ Error creating clip 3: VideoClip.resized() got an unexpected keyword argument 'newsize'
2025-11-19 09:32:41,748 - ❌ Error creating clip 4: VideoClip.resized() got an unexpected keyword argument 'newsize'
```

### MoviePy API Documentation
According to MoviePy 2.2.1 documentation, the correct signature is:
```python
VideoClip.resized(new_size=None, height=None, width=None, apply_to=None)
```

The parameter is `new_size` (with underscore), not `newsize`.

## Affected Files

### Primary File: `backend/src/video_utils.py`

**Two locations required fixing:**

#### Fix 1: Line 1117 - Resolution Scaling in `create_optimized_clip()`

**Before:**
```python
cropped_clip = cropped_clip.resized(newsize=(target_width, target_height))
```

**After:**
```python
cropped_clip = cropped_clip.resized(new_size=(target_width, target_height))
```

**Context:** This fix enables the new resolution selection feature (480p, 720p, 1080p) to work correctly when scaling cropped clips.

#### Fix 2: Line 1318 - Transition Resizing in `create_clips_with_transitions()`

**Before:**
```python
transition = transition.resized(clip_size)
```

**After:**
```python
transition = transition.resized(new_size=clip_size)
```

**Context:** This fix enables transition effects to be properly resized to match clip dimensions.

## Fix Implementation

### Step 1: Code Changes
- Fixed parameter name from `newsize=` to `new_size=` in line 1117
- Fixed positional argument to named parameter `new_size=` in line 1318

### Step 2: Verification
```bash
# Syntax check
python -m py_compile src/video_utils.py
# Result: No syntax errors

# Type checking
mypy src/video_utils.py --ignore-missing-imports
# Result: Success - no issues found

# Linting
ruff check src/video_utils.py
# Result: Only pre-existing unused variable warning (unrelated)
```

### Step 3: Search for Other Instances
```bash
grep -r "\.resized(" backend/src/
```

**Result:** Only 2 instances found, both fixed:
- Line 1117: `cropped_clip.resized(new_size=(target_width, target_height))`
- Line 1318: `transition.resized(new_size=clip_size)`

## Testing Verification

### Expected Outcomes After Fix
- ✅ Clips generate successfully
- ✅ Resolution scaling works (480p, 720p, 1080p)
- ✅ Logo overlay works (if user has uploaded logo)
- ✅ Transition effects work correctly
- ✅ No more `unexpected keyword argument 'newsize'` errors
- ✅ Task completes with N clips instead of 0 clips

### Test Case
YouTube URL from logs that can be used for testing:
```
https://www.youtube.com/watch?v=YsGIpbkXV8s
```

This should now produce 4 clips successfully with proper resolution scaling.

## Root Cause Analysis

### How the Bug Was Introduced
- Introduced in commit `e9ace2c` when implementing the resolution selection feature
- Developer referenced outdated or incorrect MoviePy API documentation
- Lack of immediate testing with resolution scaling enabled

### Why It Wasn't Caught Earlier
- The video processing pipeline works perfectly up to the scaling step
- Download, transcription, AI analysis, face detection, and cropping all succeeded
- Only the final scaling step failed, making it appear like a late-stage issue
- Task marked as "completed" despite clip generation failure

## Prevention Measures

### Immediate Actions
1. ✅ Fixed both incorrect API calls
2. ✅ Verified no other instances exist
3. ✅ Syntax and type checking passed
4. ⏳ Integration testing required

### Long-term Prevention
1. **API Documentation Verification:** Always verify parameter names against current library version
2. **Integration Tests:** Add test cases for resolution scaling feature
3. **Error Handling:** Improve error messages to surface clip generation failures more prominently
4. **CI/CD:** Run integration tests that exercise full video processing pipeline

## Related Issues

### Previously Fixed Issues (Unrelated)
- Logo upload database constraint issue (fixed 2025-11-19)
- Caption text trimming issue (fixed in commit e9ace2c)
- Segment duration validation (fixed in commit 0925f99)

### Cascading Impact
This bug blocked:
- Resolution selection feature testing
- Logo overlay feature testing (dependent on clip generation)
- Transition effects testing (dependent on clip generation)
- Overall user acceptance testing

## Commit Information

**Commit Message:**
```
fix(video): correct MoviePy API parameter name for resized()

Fixes critical bug causing 100% clip generation failure.

Changes:
- Line 1117: Changed newsize= to new_size= in create_optimized_clip()
- Line 1318: Changed positional arg to new_size= in create_clips_with_transitions()

MoviePy 2.2.1 requires new_size parameter (with underscore), not newsize.

Bug introduced in commit e9ace2c when implementing resolution selection.
All 4 test clips previously failed with "unexpected keyword argument 'newsize'" error.

Verified:
- Syntax check passed
- Type checking passed (mypy)
- No other instances found
- Ready for integration testing

Fixes: #resolution-scaling-failure
```

## Status

- **Bug Identified:** 2025-11-19 09:32:41
- **Fix Applied:** 2025-11-19 (current)
- **Quality Checks:** PASSED
- **Integration Testing:** PENDING
- **Deployment:** PENDING

## Next Steps

1. ⏳ Run integration test with full video processing
2. ⏳ Verify all resolution presets (480p, 720p, 1080p)
3. ⏳ Test with logo overlay enabled
4. ⏳ Test with transition effects enabled
5. ⏳ Monitor production logs after deployment
6. ⏳ Create git commit
7. ⏳ Update related documentation
