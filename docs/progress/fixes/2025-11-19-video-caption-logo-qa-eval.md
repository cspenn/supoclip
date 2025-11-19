# Module Evaluation: Video Caption and Logo Systems
Date: 2025-11-19

## Module Purpose

### Caption System
Renders word-level synchronized captions on video clips using MoviePy TextClip, with proper margins to prevent text clipping at edges.

### Logo System
Overlays user-uploaded logos on generated video clips at specified corner positions.

## Expected Behavior

### Caption System
- Captions should render with word-level timing from parakeet-mlx transcript
- Text with descenders (g, p, y, j, q) should be fully visible
- Stroke (1px) should not be clipped at edges
- Anti-aliasing should not cause edge artifacts
- Margin should provide adequate buffer (especially bottom for descenders)

### Logo System
- User uploads logo via POST /upload-logo endpoint
- Logo stored in `temp/logos/{user_id}_logo.png`
- Logo path saved to users table: `logo_file_path` column
- Logo position saved to users table: `logo_corner_position` column
- During clip generation, logo overlaid at specified corner
- Logo resized to 60px (longest dimension)
- Logo positioned with 20px padding from edges
- Logo appears on ALL generated clips

## Actual Behavior (from logs and code inspection)

### Caption System
**Status: PARTIALLY WORKING**

Current margin setting (line 927 of video_utils.py):
```python
text_clip = text_clip.with_effects([Margin(bottom=12, top=5, left=3, right=3, opacity=0)])
```

- 12px bottom margin: Should be adequate for most descenders
- User report: Text "what happened instead." shows descenders clipped at bottom
- This suggests margin IS sufficient but something else is causing clipping

### Logo System
**Status: NOT WORKING**

**Evidence from logs (backend-2025-11-19_10-27-39.log):**
```
2025-11-19 10:27:56 - Logo uploaded for user local-user: temp/logos/local-user_logo.png
2025-11-19 10:28:14 - Task 7b8bf748-9c6a-496b-b3b2-c6a853a93f0c created and job enqueued
2025-11-19 10:30:32 - Task 7b8bf748-9c6a-496b-b3b2-c6a853a93f0c completed successfully with 4 clips
```

**Expected log message NOT found:**
- "Added logo overlay at {logo_position}"
- "Failed to add logo overlay: {e}"

**Code flow analysis:**
1. Logo uploaded successfully: `local-user_logo.png` exists (1.9K file)
2. Database entry confirmed: `local-user|temp/logos/local-user_logo.png|bottom-right`
3. Logo retrieved in main.py line 237: `logo_path = pref_service.get_logo_path(preferences)`
4. Logo passed to async processing in main.py line 268-269
5. **BREAK IN CHAIN:** Worker task in `workers/tasks.py` does NOT accept logo parameters
6. Worker calls `task_service.process_task()` WITHOUT logo parameters (line 63-73)
7. TaskService calls `video_service.process_video_complete()` WITHOUT logo parameters (line 115-124)
8. VideoService hardcodes `None` for logo_path at line 184

## Deviations

### Caption Issue
**Expected:** Text fully visible with adequate margins
**Actual:** Descenders clipped despite 12px bottom margin
**Deviation:** Unknown cause - margin should be sufficient

### Logo Issue
**Expected:** Logo appears on clips
**Actual:** Logo NOT applied to clips
**Deviation:** Logo parameters not passed through the processing pipeline

## Production Log Evidence

### Caption Evidence
User screenshot shows text "what happened instead." with bottom clipping.

### Logo Evidence
```bash
# Logo file exists
$ ls -lh backend/temp/logos/
-rw-r--r--  1 cspenn  staff   1.9K Nov 19 10:27 local-user_logo.png

# Database has logo configured
$ sqlite3 backend/supoclip.db "SELECT id, logo_file_path, logo_corner_position FROM users WHERE logo_file_path IS NOT NULL;"
local-user|temp/logos/local-user_logo.png|bottom-right

# Task processed successfully but NO logo log messages
$ grep -E "(logo|Logo)" backend/logs/backend-2025-11-19_10-27-39.log
2025-11-19 10:27:56 - Logo uploaded for user local-user: temp/logos/local-user_logo.png
# No "Added logo overlay" or "Failed to add logo overlay" messages during clip generation
```

## Eight-Point Health Assessment

### Caption System

#### ✅ What's Good
- Margin fix already implemented (12px bottom margin)
- TextClip method changed from "caption" to "label" to prevent cutoff
- Stroke width (1px) reasonable
- Font size reduction logic works for long text
- Top, left, right margins present

#### ❌ What's Bad
- Descenders still being clipped despite 12px margin
- Root cause unclear - margin should be adequate

#### ❓ What's Missing
- Visual debugging: No way to verify actual text bounding box
- Testing: No automated test for descender visibility
- Font metrics: No explicit calculation of descender height

#### 🗑️ What's Unnecessary
- All code appears necessary for caption rendering

#### 🛠️ What's Fixed
- Commit d62a0e6: Changed `.margin()` to `.with_effects([Margin()])`
- Margin increased from 3px to 12px bottom

#### 💥 What's Newly Broken
- Issue still persists after margin fix
- Suggests margin fix was not the actual root cause

#### 🤫 Silent Errors
- No logging when text bounding box exceeds clip boundaries
- No warning when descenders might be clipped

#### 🐷 What's Overengineered
- Nothing identified as overcomplicated

### Logo System

#### ✅ What's Good
- Logo upload endpoint works correctly
- Logo file saved to filesystem
- Logo path saved to database
- Logo overlay code exists in video_utils.py (lines 1143-1177)
- Logo positioning logic correct (with padding calculations)
- Error handling present (try/except with logging)

#### ❌ What's Bad
- Logo parameters NOT passed through processing pipeline
- Workers/tasks.py does NOT accept logo_path/logo_corner_position parameters
- TaskService.process_task() does NOT accept logo parameters
- VideoService.process_video_complete() does NOT accept logo parameters
- VideoService hardcodes `None` for logo_path (line 184)
- Logo overlay code NEVER EXECUTES (condition `if logo_path and logo_path.exists()` is always False)

#### ❓ What's Missing
- Logo parameters in worker task signature
- Logo parameters in TaskService.process_task() signature
- Logo parameters in VideoService.process_video_complete() signature
- Logo path retrieval from user preferences in video service
- Logo parameter passing through the entire call chain

#### 🗑️ What's Unnecessary
- Logo overlay code in video_utils.py IS necessary but currently unreachable

#### 🛠️ What's Fixed
- Logo upload endpoint (recent fix)
- Logo database schema (recent fix)
- Auth header for logo upload (recent fix)

#### 💥 What's Newly Broken
- Logo feature broken since migration to asyncio worker queue
- Old code path (likely in main.py /start endpoint) might have worked
- New worker-based processing broke the parameter chain

#### 🤫 Silent Errors
- No error logged when logo configured but not applied
- No warning when logo path is None despite user having logo
- Logo overlay code has try/except but it's never reached

#### 🐷 What's Overengineered
- Nothing identified as overcomplicated

## Logging Assessment

**Current log level:** INFO (appropriate for production)

**Key operations logged:**
- Logo upload: YES
- Task creation: YES
- Task progress: YES
- Logo overlay application: YES (but code never executes)

**Error handling logged:**
- Logo upload errors: YES
- Logo overlay errors: YES (but code never executes)

**Adequacy:**
- Caption logging: Adequate
- Logo logging: Adequate BUT code never reached
- Missing: Warning when logo configured but not passed to processing

**Recommendations:**
1. Add INFO log in task_service when logo_path is None despite user having logo
2. Add DEBUG log showing logo parameter values at each pipeline stage
3. Keep existing logo overlay logging (it's good, just never executed)

## Priority Issues

### Critical Issues (Affecting User Experience)

1. **Logo Not Applied to Clips**
   - Severity: HIGH
   - Impact: User feature completely non-functional
   - Root Cause: Logo parameters not passed through processing pipeline
   - Affected: All users who upload logos
   - Files: workers/tasks.py, services/task_service.py, services/video_service.py

2. **Caption Descenders Clipped**
   - Severity: MEDIUM-HIGH
   - Impact: Reduced caption readability
   - Root Cause: Unknown (margin should be sufficient)
   - Affected: All captions with descenders
   - Files: src/video_utils.py line 927

### High Priority (Investigation Required)

3. **Caption Margin Mystery**
   - Why does 12px bottom margin still result in clipping?
   - Possible causes:
     - MoviePy TextClip bounding box calculation incorrect
     - Stroke applied AFTER margin calculation
     - Font rendering extends beyond reported bounding box
     - CompositeVideoClip cropping the TextClip

### Technical Debt

4. **No Visual Debugging for Text Bounds**
   - Cannot verify text bounding box dimensions
   - Cannot test descender visibility programmatically
   - Recommend: Add debug mode that draws bounding boxes

5. **No Automated Tests for Visual Elements**
   - Caption rendering not tested
   - Logo overlay not tested
   - Recommend: Create visual regression tests

## Next Steps

1. **Logo Fix (CLEAR PATH FORWARD)**
   - Add logo_path and logo_corner_position parameters to:
     - workers/tasks.py: process_video_task()
     - services/task_service.py: process_task()
     - services/video_service.py: process_video_complete()
   - Retrieve user preferences in worker or pass from API endpoint
   - Pass parameters through entire call chain
   - Verify logo overlay code executes

2. **Caption Fix (REQUIRES INVESTIGATION)**
   - Investigate why 12px margin insufficient
   - Check MoviePy TextClip bounding box calculation
   - Verify stroke applied before or after margin
   - Test with different font sizes
   - Consider increasing margin to 15-20px as temporary fix
   - May need to use MoviePy's `.margin()` method differently

## Summary

**Logo System:** Completely broken due to missing parameter passing. Clear fix path.

**Caption System:** Partially working but descenders clipped. Root cause unclear despite adequate margin. Requires investigation.

Both issues are HIGH priority as they affect user-facing video quality.
