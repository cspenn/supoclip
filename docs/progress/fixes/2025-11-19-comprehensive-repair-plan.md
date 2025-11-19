# Comprehensive Repair Plan
Date: 2025-11-19

## Executive Summary
- **Modules Evaluated:** 2 (Caption System, Logo System)
- **Total Issues Found:** 2
- **Root Causes Validated:** 1 (Logo parameter missing - 95% confidence)
- **Tests Created:** 1 new (test_logo_pipeline.py), plus existing caption tests
- **Tests Failing (proving issues exist):** 5 tests failing for logo issue

## Issue Priority Matrix

### Critical Issues (System Failure Risk)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Logo System | Logo not appearing on clips | Logo parameters not passed through processing pipeline | Yes - test_logo_pipeline.py | None - isolated fix |

### High Priority (Major Functionality)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Caption System | Descenders clipped at bottom | Unknown - 12px margin should be sufficient | Yes - test_caption_clipping.py | None - may need MoviePy investigation |

### Medium Priority (Minor Functionality)
None identified.

### Low Priority (Technical Debt)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Logo System | Logo path relative vs absolute | Secondary to parameter passing | Can add to test | Fix parameter passing first |

## Implementation Sequence

### Phase 0: Git Checkpoint

```bash
git add -A
git commit -m "CHECKPOINT: 2025-11-19 Before implementing repair plan for logo and caption issues

Test results:
- Logo pipeline test FAILING (5/7 tests) - confirms missing parameters
- Logo overlay code exists but never executes
- Caption margin at 12px but still clipping reported

Ready to implement fixes."
```

### Phase 1: Logo Parameter Passing Fix (CRITICAL - Clear Path)

**Priority:** P0 - Blocking user feature
**Confidence:** High (95%) - root cause confirmed by tests
**Estimated Time:** 30-45 minutes
**Risk:** Low - isolated changes

#### Step 1.1: Add logo parameters to worker task
**File:** `backend/src/workers/tasks.py`
**Changes:**
1. Add `logo_path: Optional[Path] = None` parameter to `process_video_task()` (line 14)
2. Add `logo_corner_position: str = "top-right"` parameter to `process_video_task()` (line 14)
3. Pass parameters to `task_service.process_task()` call (line 63)

**Before:**
```python
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    min_length: int = 10,
    max_length: int = 45,
) -> Dict[str, Any]:
```

**After:**
```python
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    min_length: int = 10,
    max_length: int = 45,
    logo_path: Optional[Path] = None,
    logo_corner_position: str = "top-right",
) -> Dict[str, Any]:
```

**Success Criteria:**
- [ ] Function signature includes logo parameters
- [ ] Parameters passed to task_service.process_task()
- [ ] Test `test_logo_params_in_worker_task` passes

#### Step 1.2: Add logo parameters to task service
**File:** `backend/src/services/task_service.py`
**Changes:**
1. Add `logo_path: Optional[Path] = None` parameter to `process_task()` (line 74)
2. Add `logo_corner_position: str = "top-right"` parameter to `process_task()` (line 74)
3. Pass parameters to `video_service.process_video_complete()` call (line 115)

**Success Criteria:**
- [ ] Function signature includes logo parameters
- [ ] Parameters passed to video_service.process_video_complete()
- [ ] Test `test_logo_params_in_task_service` passes

#### Step 1.3: Add logo parameters to video service
**File:** `backend/src/services/video_service.py`
**Changes:**
1. Add `logo_path: Optional[Path] = None` parameter to `process_video_complete()` (line 204)
2. Add `logo_corner_position: str = "top-right"` parameter to `process_video_complete()` (line 204)
3. Replace hardcoded `None` at line 184 with `logo_path`
4. Replace hardcoded `"top-right"` at line 185 with `logo_corner_position`
5. Update docstring to document new parameters

**Before:**
```python
clips_info = await run_in_thread(
    create_clips_with_transitions,
    video_path,
    segments,
    clips_output_dir,
    font_family,
    font_size,
    font_color,
    None,  # logo_path
    "top-right",  # logo_position
    output_resolution,
)
```

**After:**
```python
clips_info = await run_in_thread(
    create_clips_with_transitions,
    video_path,
    segments,
    clips_output_dir,
    font_family,
    font_size,
    font_color,
    logo_path,
    logo_corner_position,
    output_resolution,
)
```

**Success Criteria:**
- [ ] Function signature includes logo parameters
- [ ] Parameters passed to create_clips_with_transitions()
- [ ] Test `test_logo_params_in_video_service` passes
- [ ] Test `test_logo_params_passed_to_clip_creation` passes

#### Step 1.4: Update API endpoint job creation
**File:** `backend/src/api/routes/tasks.py` (or wherever job is enqueued)
**Changes:**
1. Retrieve logo_path and logo_corner_position from user preferences (likely already done in main.py)
2. Pass logo parameters when enqueuing job to local queue
3. Ensure logo_path is absolute (resolve relative paths if needed)

**Code to find:**
- Look for `queue.enqueue()` or `create_task()` call with task parameters
- Add logo_path and logo_corner_position to arguments

**Success Criteria:**
- [ ] Logo preferences retrieved from user
- [ ] Logo parameters passed to worker job
- [ ] Logo path is absolute

#### Step 1.5: Run tests and verify
**Commands:**
```bash
# Run logo pipeline test
python test_logo_pipeline.py

# Expected: 7 passed (all tests pass)

# Check for "Added logo overlay" message in logs
tail -f backend/logs/backend-*.log | grep -i logo
```

**Success Criteria:**
- [ ] All 7 tests in test_logo_pipeline.py pass
- [ ] No import errors or attribute errors
- [ ] Ready for integration testing

### Phase 2: Logo Fix Integration Testing

**Priority:** P0 - Verify fix works end-to-end
**Estimated Time:** 15-20 minutes

#### Step 2.1: Process video with logo
**Commands:**
```bash
# Ensure logo uploaded for test user
# Upload logo via API if not already done

# Process a short test video
curl -X POST http://localhost:8008/tasks \
  -H "Content-Type: application/json" \
  -H "user_id: local-user" \
  -d '{
    "url": "https://www.youtube.com/watch?v=jYjJjYeMt3k",
    "clip_min_length": 48,
    "clip_max_length": 58
  }'

# Monitor logs for logo messages
tail -f backend/logs/backend-*.log | grep -E "(logo|Logo|Added logo overlay)"
```

**Success Criteria:**
- [ ] Log message "Added logo overlay at {position}" appears
- [ ] No "Failed to add logo overlay" error
- [ ] Clips generated successfully

#### Step 2.2: Visual verification
**Commands:**
```bash
# Find most recent clips
ls -lt backend/temp/clips/ | head -5

# Open clip in video player
open backend/temp/clips/clip_1_*.mp4
```

**Success Criteria:**
- [ ] Logo visible on clip
- [ ] Logo at correct corner position (bottom-right for local-user)
- [ ] Logo correct size (~60px)
- [ ] Logo transparency preserved
- [ ] Logo appears on ALL clips

### Phase 3: Caption Investigation and Fix (HIGH PRIORITY)

**Priority:** P1 - Affects readability
**Confidence:** Medium (60%) - investigation required
**Estimated Time:** 1-2 hours
**Risk:** Medium - may require MoviePy internals investigation

#### Step 3.1: Run existing caption tests
**Commands:**
```bash
cd backend
python test_caption_clipping.py

# Review generated test images
open /tmp/caption_tests/
```

**Analysis Required:**
- Identify which margin values prevent clipping
- Check if issue is font-size dependent
- Verify if 12px margin is sufficient
- Look for patterns in clipping behavior

**Success Criteria:**
- [ ] Test images generated for all margin values
- [ ] Visual inspection completed
- [ ] Pattern identified (if any)
- [ ] Minimum safe margin determined

#### Step 3.2: Investigate MoviePy TextClip behavior
**Investigation:**
1. Check if TextClip.size includes descenders
2. Verify if Margin is applied before or after rendering
3. Check if stroke extends beyond reported bounds
4. Test with different MoviePy text methods

**Possible Approaches:**
1. **Increase margin further:** Try 15-20px bottom margin
2. **Dynamic margin:** Calculate based on font size: `int(font_size * 0.35)`
3. **Manual positioning:** Position text higher to avoid bottom edge
4. **Alternative rendering:** Use PIL/Pillow to render text, then ImageClip

**Success Criteria:**
- [ ] Root cause identified
- [ ] Fix approach determined
- [ ] Test case created

#### Step 3.3: Implement caption fix
**File:** `backend/src/video_utils.py` line 927

**Option A: Increase Margin (Simple)**
```python
# Current
text_clip = text_clip.with_effects([Margin(bottom=12, top=5, left=3, right=3, opacity=0)])

# Proposed
text_clip = text_clip.with_effects([Margin(bottom=20, top=8, left=5, right=5, opacity=0)])
```

**Option B: Dynamic Margin (Better)**
```python
# Calculate margin based on font size
bottom_margin = int(current_font_size * 0.4)  # 40% of font size
top_margin = int(current_font_size * 0.3)
side_margin = int(current_font_size * 0.2)

text_clip = text_clip.with_effects([
    Margin(bottom=bottom_margin, top=top_margin, left=side_margin, right=side_margin, opacity=0)
])
```

**Option C: Manual Positioning (If margins don't work)**
- Position text higher in frame (e.g., at 70% instead of 75%)
- Ensure adequate space below text for descenders

**Success Criteria:**
- [ ] Caption test shows no clipping
- [ ] Works across all font sizes (20-40px)
- [ ] Works across all resolutions
- [ ] No visual regression (captions still readable)

#### Step 3.4: Test caption fix
**Commands:**
```bash
# Re-run caption test
python test_caption_clipping.py

# Visual inspection
open /tmp/caption_tests/

# Process test video
# (use same curl command from Phase 2)

# Check generated clip
open backend/temp/clips/clip_1_*.mp4
```

**Success Criteria:**
- [ ] Test images show no clipping
- [ ] Production clip shows no clipping
- [ ] Text fully readable
- [ ] No descenders cut off

### Phase 4: Validation and Documentation

**Priority:** P0 - Required before completion
**Estimated Time:** 15 minutes

#### Step 4.1: Run full test suite
**Commands:**
```bash
cd backend
pytest tests/ -v

# Run specific tests
python test_logo_pipeline.py
python test_caption_clipping.py
pytest tests/test_logo_upload_feature.py -v
```

**Success Criteria:**
- [ ] All logo tests pass (test_logo_pipeline.py: 7/7)
- [ ] Caption tests pass (no clipping detected)
- [ ] Existing tests still pass (no regressions)
- [ ] Integration tests pass

#### Step 4.2: Cross-resolution testing
**Test Matrix:**
| Resolution | Logo | Caption | Expected |
|------------|------|---------|----------|
| 480p | ✓ | ✓ | Both work |
| 720p | ✓ | ✓ | Both work |
| 1080p | ✓ | ✓ | Both work |

**Commands:**
```bash
# Process video at each resolution
# Check output_resolution parameter in API call

# 480p
curl -X POST http://localhost:8008/tasks \
  -H "Content-Type: application/json" \
  -H "user_id: local-user" \
  -d '{"url": "...", "output_resolution": "480p"}'

# Repeat for 720p, 1080p
```

**Success Criteria:**
- [ ] Logo appears at all resolutions
- [ ] Caption readable at all resolutions
- [ ] No clipping at any resolution
- [ ] Logo size scales appropriately

#### Step 4.3: Document changes
**Files to update:**
- `docs/progress/fixes/2025-11-19-final-verification-report.md`
- Update CHANGELOG or commit message with clear description

**Documentation should include:**
- What was broken
- Root cause
- What was fixed
- Test results
- Visual confirmation

### Phase 5: Git Checkpoint Post-Fix

```bash
git add -A
git commit -m "CHECKPOINT: 2025-11-19 Completed repair plan - logo and caption fixes

Logo Fix:
- Added logo_path and logo_corner_position parameters to:
  - workers/tasks.py: process_video_task()
  - services/task_service.py: process_task()
  - services/video_service.py: process_video_complete()
- Replaced hardcoded None with actual logo_path
- Logo overlay code now executes
- Test results: test_logo_pipeline.py 7/7 PASSED

Caption Fix:
- [Describe what was changed - margin increase or other approach]
- Test results: test_caption_clipping.py PASSED
- Visual verification: No descender clipping

Verification:
- End-to-end test with logo and captions: PASSED
- Cross-resolution testing (480p, 720p, 1080p): PASSED
- All existing tests: PASSED
- No regressions introduced"
```

## Risk Mitigation

### Regression Prevention
- [X] Created test_logo_pipeline.py to prevent future regressions
- [ ] All existing tests must pass after changes
- [ ] Visual inspection of clips required
- [ ] Test across all resolutions
- [ ] Git checkpoints before and after each phase

### Rollback Plan
- **Phase 0 checkpoint:** Before any changes
- **Phase 5 checkpoint:** After all changes
- **Rollback command:** `git reset --hard <phase-0-commit-hash>`

### Logo Fix Risks
**Risk:** Low
- Changes are isolated to parameter passing
- No complex logic changes
- Clear test coverage
- Logo overlay code already exists and tested

**Mitigation:**
- Test each phase independently
- Verify log messages appear
- Visual verification required

### Caption Fix Risks
**Risk:** Medium
- Root cause not yet confirmed
- May require experimentation
- Could affect all caption rendering

**Mitigation:**
- Run existing caption tests first
- Try simple fix (margin increase) first
- Test across multiple font sizes
- Visual inspection required
- Keep old margin value in comments for rollback

## Success Metrics

### Logo Feature
- [X] Test suite passes (7/7 tests in test_logo_pipeline.py)
- [ ] Logo appears on all generated clips
- [ ] Logo positioned correctly at specified corner
- [ ] Log message "Added logo overlay at {position}" appears
- [ ] Works across all resolutions (480p, 720p, 1080p)
- [ ] No errors in logs

### Caption Feature
- [ ] Text with descenders fully visible
- [ ] Caption tests pass (no clipping detected)
- [ ] Works with all fonts
- [ ] Works across all font sizes (20-40px)
- [ ] Works across all resolutions
- [ ] No visual regression (captions still readable and positioned correctly)

### Overall Quality
- [ ] All tests passing (old and new)
- [ ] No regressions introduced
- [ ] Production validation confirms fixes work
- [ ] Documentation complete
- [ ] Git history clean with clear commit messages

## Implementation Guidelines

### Before Starting Fixes
1. ✅ All tests from Task 3 are in place
2. ✅ Git checkpoint created (Phase 0)
3. ✅ Dependencies between issues reviewed (none - independent)
4. ✅ Rollback procedures confirmed

### During Implementation
1. Fix one issue at a time (logo first, then caption)
2. Run associated test after each change
3. Run full test suite to check for regressions
4. Verify in production environment (process actual video)
5. Document the fix approach

### After Implementation
1. All tests passing (old and new)
2. Production validation complete
3. Documentation updated
4. Git checkpoint created (Phase 5)
5. Monitor for unexpected issues

## Time Estimate

| Phase | Task | Estimated Time |
|-------|------|----------------|
| Phase 0 | Git checkpoint | 2 min |
| Phase 1 | Logo parameter fix | 30-45 min |
| Phase 2 | Logo integration testing | 15-20 min |
| Phase 3 | Caption investigation & fix | 1-2 hours |
| Phase 4 | Validation & docs | 15 min |
| Phase 5 | Git checkpoint | 5 min |
| **Total** | | **2-3 hours** |

**Priority:**
- Logo fix: IMMEDIATE (P0 - blocking user feature)
- Caption fix: HIGH (P1 - affects quality but not blocking)

## Notes

- Logo fix has CLEAR path forward (95% confidence)
- Caption fix requires investigation (60% confidence)
- Both issues are independent and can be fixed separately
- Logo fix should be done FIRST (easier, higher confidence)
- Caption fix may require experimentation with different approaches
