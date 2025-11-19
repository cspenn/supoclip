# Investigation Summary: Caption and Logo Issues
Date: 2025-11-19

## Overview

Systematic investigation of two reported issues with video clip generation:
1. Caption text descenders being clipped at bottom
2. Logo not appearing on generated clips

## Investigation Method

Followed strict test-driven debugging approach from CLAUDE.md guidelines:
- TASK 1: Module-by-Module Health Assessment
- TASK 2: Root Cause Hypothesis Generation
- TASK 3: Test-Driven Validation
- TASK 4: Comprehensive Repair Planning

## Key Findings

### Issue 1: Logo Not Appearing (CRITICAL - Root Cause CONFIRMED)

**Status:** ✅ ROOT CAUSE IDENTIFIED - HIGH CONFIDENCE (95%)

**Root Cause:**
Logo parameters (`logo_path` and `logo_corner_position`) are NOT passed through the video processing pipeline.

**Evidence Chain:**
1. **User uploads logo** → ✅ Works (file saved, database updated)
2. **API endpoint retrieves logo** → ✅ Works (main.py line 237, 268-269)
3. **Worker task receives logo** → ❌ BREAKS HERE (workers/tasks.py missing parameters)
4. **Task service passes logo** → ❌ Missing parameters (services/task_service.py)
5. **Video service uses logo** → ❌ Hardcodes None (services/video_service.py line 184)
6. **Logo overlay code executes** → ❌ Never reached (condition always False)

**Test Confirmation:**
Created `test_logo_pipeline.py` which demonstrates:
- ❌ process_video_task() missing logo_path parameter
- ❌ TaskService.process_task() missing logo_path parameter
- ❌ VideoService.process_video_complete() missing logo_path parameter
- ✅ Logo overlay code exists and is correct (but never executes)
- ✅ Logo file exists on filesystem
- ✅ Logo path exists in database

**Log Evidence:**
```
# Logo uploaded successfully
2025-11-19 10:27:56 - Logo uploaded for user local-user: temp/logos/local-user_logo.png

# Task completed but NO logo overlay message
2025-11-19 10:30:32 - Task completed successfully with 4 clips

# Expected but NOT found:
# "Added logo overlay at {position}"
```

**Fix Approach:** CLEAR AND STRAIGHTFORWARD
1. Add logo_path and logo_corner_position parameters to 3 function signatures
2. Pass parameters through call chain
3. Replace hardcoded None with actual parameter values
4. Test: All 7 tests in test_logo_pipeline.py should pass
5. Visual verification: Logo appears on clips

**Estimated Time:** 30-45 minutes
**Risk:** Low (isolated parameter passing changes)
**Confidence:** High (95%)

### Issue 2: Caption Descenders Clipped (HIGH PRIORITY - Requires Investigation)

**Status:** ⚠️ ROOT CAUSE UNCLEAR - INVESTIGATION REQUIRED

**Current State:**
- Margin set to 12px bottom (line 927 of video_utils.py)
- Should be adequate for most descenders (typically 5-10px)
- User screenshot shows descenders still clipped
- Recent fix (commit d62a0e6) didn't fully resolve issue

**Hypotheses:**
1. **MoviePy TextClip bounding box excludes descenders** (60% confidence)
   - TextClip may calculate bounds without including descender space
   - Margin applied to incorrect bounding box
   - Need to investigate MoviePy internals

2. **Margin applied before stroke** (40% confidence)
   - 1px stroke might extend beyond margin
   - Less likely since 12px should accommodate 1px stroke

3. **CompositeVideoClip crops TextClip edges** (30% confidence)
   - Text might be positioned such that bottom edge gets cropped
   - Would affect compositing layer, not TextClip itself

**Evidence:**
- ❓ User screenshot shows clipping
- ✅ Margin value is reasonable (12px)
- ✅ Code uses `method="label"` (changed from "caption")
- ✅ Margin applied via `.with_effects([Margin()])`
- ❓ No test yet confirms this reproduces reliably

**Existing Tests:**
- `test_caption_clipping.py` - Comprehensive visual test (EXISTS)
- Tests multiple margin values (3px, 8px, 10px, 12px, 15px)
- Tests multiple font sizes (20px, 24px, 30px, 40px)
- Includes visual inspection and pixel detection

**Next Steps:**
1. Run existing test_caption_clipping.py
2. Visual inspection of generated test images
3. Determine if margin increase needed (try 20px)
4. If still fails, investigate MoviePy TextClip behavior
5. Consider alternative approaches:
   - Dynamic margin based on font size
   - Manual positioning higher in frame
   - PIL/Pillow rendering instead of TextClip

**Estimated Time:** 1-2 hours (includes investigation)
**Risk:** Medium (may require experimentation)
**Confidence:** Medium (60%)

## Documentation Created

1. **2025-11-19-video-caption-logo-qa-eval.md**
   - Complete 8-point health assessment
   - Expected vs actual behavior analysis
   - Log evidence and priority issues

2. **2025-11-19-root-causes.md**
   - All hypotheses (5-7 per issue)
   - Top 2 hypotheses with detailed analysis
   - Supporting and contradicting evidence
   - Confidence levels

3. **2025-11-19-qa-test-audit.md**
   - Test creation and execution results
   - Hypothesis validation
   - Production log correlation
   - Success criteria

4. **2025-11-19-comprehensive-repair-plan.md**
   - 5-phase implementation plan
   - Detailed steps for each fix
   - Risk mitigation strategies
   - Success metrics and validation

5. **test_logo_pipeline.py**
   - 7 tests for logo parameter passing
   - Currently 5 failing, 2 passing (as expected)
   - Will all pass after fix

## Recommended Action Plan

### Priority 1: Fix Logo Issue (IMMEDIATE)
**Confidence: HIGH (95%)**
**Time: 30-45 minutes**

1. Create Phase 0 git checkpoint
2. Add logo parameters to 3 functions:
   - workers/tasks.py: process_video_task()
   - services/task_service.py: process_task()
   - services/video_service.py: process_video_complete()
3. Replace hardcoded None with parameters
4. Run test_logo_pipeline.py (expect 7/7 pass)
5. Integration test with real video
6. Visual verification
7. Create Phase 5 git checkpoint

### Priority 2: Investigate Caption Issue
**Confidence: MEDIUM (60%)**
**Time: 1-2 hours**

1. Run existing test_caption_clipping.py
2. Visual inspection of test images
3. If still clipping, try margin=20px
4. If 20px doesn't work, investigate MoviePy
5. Test chosen solution across resolutions
6. Visual verification

### Risk Assessment

**Logo Fix:**
- ✅ Low risk (isolated changes)
- ✅ Clear path forward
- ✅ Comprehensive test coverage
- ✅ No dependencies on other features

**Caption Fix:**
- ⚠️ Medium risk (may require experimentation)
- ⚠️ Not yet clear which approach will work
- ✅ Good test coverage (existing tests)
- ⚠️ May affect all caption rendering

## Success Metrics

### Logo Feature Working:
- [ ] test_logo_pipeline.py: 7/7 tests pass
- [ ] Log message "Added logo overlay at {position}" appears
- [ ] Logo visible on all clips
- [ ] Logo at correct corner position
- [ ] Works at 480p, 720p, 1080p

### Caption Feature Working:
- [ ] test_caption_clipping.py shows no clipping
- [ ] Text with descenders fully visible
- [ ] Works across all font sizes (20-40px)
- [ ] Works at 480p, 720p, 1080p
- [ ] No visual regression

## Files Modified (Planned)

### For Logo Fix:
- `backend/src/workers/tasks.py` (add parameters)
- `backend/src/services/task_service.py` (add parameters)
- `backend/src/services/video_service.py` (add parameters, replace None)

### For Caption Fix:
- `backend/src/video_utils.py` (adjust margin or positioning)

## Next Command

To proceed with implementation:
```bash
# Run the comprehensive repair plan
cat docs/progress/fixes/2025-11-19-comprehensive-repair-plan.md
```

## Conclusion

**Logo Issue:** Ready to fix with high confidence. Clear root cause, clear solution, good test coverage.

**Caption Issue:** Requires investigation first. Margin value seems adequate but clipping still occurs. Need to run existing tests and potentially experiment with different approaches.

**Recommendation:** Fix logo issue FIRST (30-45 min), then investigate caption issue (1-2 hours).

**Total Time Estimate:** 2-3 hours for both fixes including testing and verification.
