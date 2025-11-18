# Investigation Summary: Font Cutoff and Short Clips
Date: 2025-11-18
Investigator: Claude Code
Duration: Comprehensive analysis completed

## Quick Reference

**Issue #1: Font Cutoff**
- **Root Cause**: `method="caption"` in TextClip (video_utils.py:913)
- **Fix**: Change to `method="label"` and remove `size` parameter
- **Files**: 1 file, 2 lines
- **Time**: 5 minutes

**Issue #2: Short Clips**
- **Root Cause**: Hardcoded "10-45s" in SYSTEM_PROMPT (ai_structured.py:56-58)
- **Fix**: Make SYSTEM_PROMPT dynamic with min_length/max_length params
- **Files**: 1 file, ~60 lines
- **Time**: 20 minutes

## Documentation Deliverables

All documents created in `/Users/cspenn/Documents/github/supoclip/docs/progress/fixes/`:

1. **Root Cause Analysis** (`2025-11-18-font-cutoff-short-clips-root-cause.md`)
   - Comprehensive analysis with log evidence
   - Confidence levels: Font (95%), Clips (90%)
   - Production log correlation
   - Impact assessment

2. **Failing Tests** (`/Users/cspenn/Documents/github/supoclip/backend/tests/test_font_cutoff_and_short_clips.py`)
   - 8 test cases demonstrating both issues
   - Tests SHOULD FAIL before fixes applied
   - Integration test reproducing exact user scenario
   - Ready to run: `pytest tests/test_font_cutoff_and_short_clips.py -v`

3. **Fix Implementation Plan** (`2025-11-18-fix-implementation-plan.md`)
   - Exact line numbers for all changes
   - Before/after code snippets
   - Testing procedures
   - Rollback plan
   - Git commit strategy

## Evidence Summary

### Font Cutoff Evidence
- **Screenshot**: User shows text cut in half vertically
- **Log**: `font_family=Barlow Condensed Bold, font_size=30` ✓ (parameter flow works)
- **Code**: `method="caption"` with `size=(max_text_width, None)` causes cropping
- **MoviePy Docs**: Caption mode is for fixed-size boxes, label mode auto-sizes

### Short Clips Evidence
- **Screenshot**: Clip duration 06:38.680 - 06:50.040 = 11.36 seconds
- **Log**: `clip_length=47s-58s` ✓ (parameters received correctly)
- **Log**: `Clip length settings - Min: 47s, Max: 58s` ✓ (passed to AI)
- **Log**: `Groq response duration analysis: avg=14.39s` ✗ (AI ignored parameters!)
- **Code**: SYSTEM_PROMPT hardcodes "10 seconds minimum, 45 seconds maximum"
- **Code**: Validation hardcodes `if duration < 10` instead of `if duration < min_length`

## Key Findings

### What's Working
- ✅ Frontend sends correct parameters (font, size, color, clip_length)
- ✅ Backend receives parameters correctly
- ✅ Parameters flow to AI analysis function
- ✅ Logging shows parameter values at each step
- ✅ Font selection works (correct font applied)
- ✅ Validation logic runs (rejects segments correctly)

### What's Broken
- ❌ TextClip crops text vertically (wrong method parameter)
- ❌ AI ignores min_length/max_length (hardcoded SYSTEM_PROMPT)
- ❌ Validation ignores min_length (hardcoded 10s minimum)
- ❌ No max_length validation at all

### What's Missing
- ❓ Max length validation in ai_structured.py
- ❓ Absolute minimum enforcement (should be >= 5s always)
- ❓ User feedback when AI can't find segments in requested range

## Root Cause Categories

| Issue | Category | Root Cause Type |
|-------|----------|-----------------|
| Font Cutoff | Implementation Bug | Wrong parameter value |
| Short Clips (AI) | Configuration Bug | Hardcoded instead of dynamic |
| Short Clips (Validation) | Implementation Bug | Wrong variable used |

## Fix Complexity

### Font Cutoff Fix
- **Complexity**: Low
- **Risk**: Low
- **Testing**: Easy (visual verification)
- **Files**: 1
- **Lines**: 2

### Short Clips Fix
- **Complexity**: Medium
- **Risk**: Medium
- **Testing**: Requires API key
- **Files**: 1
- **Lines**: ~60

## Next Steps for User

### Option 1: Apply Fixes Yourself
1. Review fix implementation plan
2. Apply changes to 2 files as specified
3. Run tests to verify
4. Process test video to confirm

### Option 2: Request Implementation
1. Review root cause analysis
2. Approve fix strategy
3. Request implementation by developer
4. Test fixed version

### Option 3: Investigate Further
1. Review failing tests to understand issues
2. Add additional test cases
3. Explore alternative solutions
4. Consider edge cases

## Time Estimates

| Task | Time |
|------|------|
| Apply Font Fix | 5 min |
| Test Font Fix | 5 min |
| Apply Clips Fix | 20 min |
| Test Clips Fix | 10 min |
| Integration Test | 10 min |
| **Total** | **50 min** |

## Success Metrics

After fixes applied:

1. **Font Cutoff**:
   - Captions fully visible (no vertical cropping)
   - Text wraps correctly
   - Positioning still at 75% down video

2. **Short Clips**:
   - User sets 47-58s → Gets 47-58s clips
   - User sets 20-30s → Gets 20-30s clips
   - Logs show AI response matches requested range
   - Validation rejects clips outside range

## Files Requiring Changes

```
backend/src/video_utils.py          (2 lines modified)
backend/src/ai_structured.py        (~60 lines modified)
```

## Related Issues

### Potential Related Problems
- Font size calculation (line 970 video_utils.py) - May need adjustment
- Validation minimum (5s in ai.py:167) - Consider making configurable
- Custom prompts - User prompts might override duration settings

### Future Improvements
- Add clip length presets (Short/Medium/Long)
- Show predicted clip count before generation
- Add "regenerate with different settings" button
- Validate fonts exist before processing

## Confidence Levels

- **Font Cutoff Root Cause**: 95% confident
- **Short Clips Root Cause**: 90% confident
- **Fix Strategies**: 95% confident will work
- **No Regressions**: 85% confident (need testing)

## References

- Root Cause Analysis: `2025-11-18-font-cutoff-short-clips-root-cause.md`
- Failing Tests: `backend/tests/test_font_cutoff_and_short_clips.py`
- Fix Implementation: `2025-11-18-fix-implementation-plan.md`
- Logs: `backend/logs/backend-2025-11-18_*.log`

---

**Status**: Investigation complete. Ready for fix implementation.
**Priority**: High (both issues affect 100% of clips)
**Blocker**: No - workarounds exist but fixes are recommended
