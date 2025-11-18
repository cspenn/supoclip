# Clip Length Settings Issue - Complete Documentation Index

**Investigation Date:** November 18, 2025
**Status:** Root cause identified and documented
**Documents Created:** 5 comprehensive audit documents
**Files Requiring Changes:** 6 (1 frontend, 5 backend)

---

## Quick Start

If you want to understand and fix the clip length issue, read these documents in order:

1. **START HERE:** `CLIP_LENGTH_INVESTIGATION_SUMMARY.md`
   - **Read time:** 5 minutes
   - **What you'll learn:** What's broken, why it's broken, what needs to be fixed
   - **Best for:** Quick understanding of the issue

2. **THEN READ:** `CLIP_LENGTH_VISUAL_FLOW.md`
   - **Read time:** 5 minutes
   - **What you'll learn:** Visual diagrams of current vs. fixed data flow
   - **Best for:** Understanding the data flow at a glance

3. **IMPLEMENTATION:** `CLIP_LENGTH_FIX_GUIDE.md`
   - **Read time:** 20 minutes
   - **What you'll learn:** Step-by-step fix instructions with code examples
   - **Best for:** Implementing the actual fixes

4. **REFERENCE:** `CLIP_LENGTH_CODE_REFERENCES.md`
   - **Read time:** 10 minutes
   - **What you'll learn:** Exact file paths, line numbers, code snippets
   - **Best for:** Quick lookup during implementation

5. **DETAILED ANALYSIS:** `CLIP_LENGTH_SETTINGS_AUDIT.md`
   - **Read time:** 15 minutes
   - **What you'll learn:** Complete technical breakdown of each component
   - **Best for:** Deep understanding of the system architecture

---

## Document Descriptions

### 1. CLIP_LENGTH_INVESTIGATION_SUMMARY.md

**Purpose:** Executive summary of the issue

**Contains:**
- Quick problem summary
- What's working vs. broken
- Problem breakdown by location
- Data loss points
- Why this happened
- Implementation priority
- Key insights

**Length:** ~300 lines
**Audience:** Developers, Project Managers
**Key Takeaway:** "Settings are saved but never used in video processing"

---

### 2. CLIP_LENGTH_VISUAL_FLOW.md

**Purpose:** Visual representation of data flow

**Contains:**
- ASCII diagram of current (broken) flow
- ASCII diagram of fixed (working) flow
- Side-by-side comparison table
- Component status matrix
- User experience before/after

**Length:** ~400 lines
**Audience:** Visual learners, Architects
**Key Takeaway:** "Data gets lost at 12 of 13 handoff points"

---

### 3. CLIP_LENGTH_FIX_GUIDE.md

**Purpose:** Step-by-step implementation instructions

**Contains:**
- Fix strategy overview
- 6 detailed fixes (one per file)
- For each fix:
  - Current code
  - Required changes
  - Code snippets
- Testing instructions
- Expected outcomes
- Implementation order
- Backward compatibility notes

**Length:** ~450 lines
**Audience:** Developers implementing the fix
**Key Takeaway:** "Follow these 6 steps to fix it"

---

### 4. CLIP_LENGTH_CODE_REFERENCES.md

**Purpose:** Exact code locations and references

**Contains:**
- File paths and exact line numbers
- Current code snippets (marked ✅ working or ❌ broken)
- What needs to be added
- Data flow diagram
- Summary table with all changes needed

**Length:** ~500 lines
**Audience:** Developers during implementation
**Key Takeaway:** "Here's exactly where to change what"

---

### 5. CLIP_LENGTH_SETTINGS_AUDIT.md

**Purpose:** Comprehensive technical audit

**Contains:**
- Detailed analysis of each component:
  - Frontend settings page
  - Frontend video form
  - Backend endpoint
  - Task service
  - Video service
  - Worker task
  - AI functions
  - User preferences service
- Hardcoded defaults list
- Missing data preservation analysis
- Files requiring changes
- Current vs. expected behavior

**Length:** ~500 lines
**Audience:** Technical architects, QA engineers
**Key Takeaway:** "Every component in the chain is broken at the connection point"

---

## The Issue at a Glance

```
User Sets Clip Lengths
        ↓
    Database (Stored ✅)
        ↓
Frontend Form (Lost ❌)
        ↓
Backend Endpoint (Lost ❌)
        ↓
Worker (Lost ❌)
        ↓
Task Service (Lost ❌)
        ↓
Video Service (Lost ❌)
        ↓
AI Analysis (Uses hardcoded defaults ❌)
        ↓
Generated Clips are 10-45s (Expected: 35-58s)
```

---

## Files That Need Changes

### Frontend (1 file)
- **`frontend/src/app/page.tsx`**
  - **Issue:** Doesn't send clip length settings
  - **Fix:** Load from preferences, include in request
  - **Lines:** ~150
  - **Changes:** 2 main changes

### Backend (5 files)

1. **`backend/src/api/routes/tasks.py`**
   - **Issue:** Doesn't extract or load clip lengths
   - **Fix:** Extract from request, load from preferences
   - **Lines:** 49-119
   - **Changes:** 3 code blocks

2. **`backend/src/services/task_service.py`**
   - **Issue:** Methods don't accept clip length parameters
   - **Fix:** Add parameters to method signatures, pass through
   - **Lines:** 28-36, 74-82, 113-120
   - **Changes:** 3 method signature updates

3. **`backend/src/services/video_service.py`**
   - **Issue:** Methods don't accept/pass clip length parameters
   - **Fix:** Add parameters to method signatures, pass through
   - **Lines:** 137-147, 191-198, 227
   - **Changes:** 3 method signature updates

4. **`backend/src/workers/tasks.py`**
   - **Issue:** Function doesn't accept clip length parameters
   - **Fix:** Add parameters to function signature, pass through
   - **Lines:** 14-22, 59-67
   - **Changes:** 2 function signature updates

5. **`backend/src/workers/job_queue.py`**
   - **Issue:** enqueue_job doesn't accept clip length parameters
   - **Fix:** Update signature to accept and pass through parameters
   - **Lines:** TBD (search for enqueue_job method)
   - **Changes:** 1 method signature update

---

## Key Code Locations

### Settings Saved (Works)
- `frontend/src/app/settings/page.tsx` - Lines 99-110
- Saves to `/api/preferences` endpoint

### Settings Lost (Broken Chain)
1. `frontend/src/app/page.tsx` - Line 142-152 - Doesn't send in POST /tasks/
2. `backend/src/api/routes/tasks.py` - Line 62-88 - Doesn't extract or load
3. `backend/src/api/routes/tasks.py` - Line 96-105 - Doesn't pass to worker
4. `backend/src/workers/tasks.py` - Line 59-67 - Doesn't receive or pass
5. `backend/src/services/task_service.py` - Line 113-120 - Doesn't receive or pass
6. `backend/src/services/video_service.py` - Line 227 - Doesn't pass to AI
7. `backend/src/ai.py` - Line 143 - Uses hardcoded defaults

---

## Implementation Checklist

- [ ] Read `CLIP_LENGTH_INVESTIGATION_SUMMARY.md`
- [ ] Review `CLIP_LENGTH_VISUAL_FLOW.md`
- [ ] Create feature branch: `feature/fix-clip-length-settings`
- [ ] Implement changes from `CLIP_LENGTH_FIX_GUIDE.md` in order:
  - [ ] `backend/src/workers/job_queue.py` - Update enqueue_job
  - [ ] `backend/src/workers/tasks.py` - Add parameters
  - [ ] `backend/src/services/video_service.py` - Add parameters
  - [ ] `backend/src/services/task_service.py` - Add parameters
  - [ ] `backend/src/api/routes/tasks.py` - Extract/load and pass
  - [ ] `frontend/src/app/page.tsx` - Load and send
- [ ] Test after each file change
- [ ] Verify with `CLIP_LENGTH_CODE_REFERENCES.md`
- [ ] Create comprehensive test cases
- [ ] Test backward compatibility
- [ ] Document changes in commit message
- [ ] Submit for code review

---

## Testing Strategy

### Manual Test Cases

**Test 1: Default Behavior**
1. Don't change any settings
2. Submit a video
3. Verify clips are in default range (10-45s)
4. ✅ Should pass

**Test 2: Custom Settings - Long Clips**
1. Set Min=45s, Target=55s, Max=60s
2. Submit a video
3. Verify clips are in 45-60s range
4. ✅ Should pass

**Test 3: Custom Settings - Short Clips**
1. Set Min=5s, Target=10s, Max=15s
2. Submit a video
3. Verify clips are in 5-15s range
4. ✅ Should pass

**Test 4: Settings Persistence**
1. Set custom clip lengths
2. Refresh page
3. Verify settings are still there
4. ✅ Should pass

**Test 5: Cross-User Settings**
1. User A sets Min=30s, Max=50s
2. User B sets Min=10s, Max=20s
3. Both submit videos
4. User A gets 30-50s clips
5. User B gets 10-20s clips
6. ✅ Should pass (different results per user)

### Backend Verification

**Log Check During Processing**
```
Look for: "Starting AI analysis of transcript (min_length=35s, max_length=58s)"
Current:  "Starting AI analysis of transcript"  ❌
Expected: "Starting AI analysis of transcript (min_length=35s, max_length=58s)"  ✅
```

**Network Request Check**
```
POST /tasks/
Request body should include:
  "clip_min_length": 35,
  "clip_target_length": 48,
  "clip_max_length": 58
```

---

## Estimated Effort

| Component | Estimated Time | Difficulty |
|-----------|-----------------|------------|
| Frontend change | 15 minutes | Easy |
| Backend job_queue.py | 10 minutes | Easy |
| Backend tasks.py (worker) | 10 minutes | Easy |
| Backend video_service.py | 15 minutes | Easy |
| Backend task_service.py | 15 minutes | Easy |
| Backend tasks.py (endpoint) | 20 minutes | Medium |
| Testing | 30 minutes | Medium |
| Code Review & Polish | 20 minutes | Easy |
| **TOTAL** | **~2 hours** | **Medium** |

---

## Risk Assessment

### Risks
- **Low Risk:** All changes use default parameters, no breaking changes
- **Database:** No schema changes needed
- **Backward Compatibility:** Old requests without clip lengths still work

### Mitigation
- Implement in small, testable chunks
- Test after each file change
- Verify backward compatibility
- Review with team before merge

---

## Success Criteria

### Before Fix
- ❌ Users set clip lengths: 35s-58s
- ❌ Generated clips: 10-45s (hardcoded)
- ❌ Settings appear to be ignored

### After Fix
- ✅ Users set clip lengths: 35s-58s
- ✅ Generated clips: 35-58s (user-configured)
- ✅ Settings are applied correctly
- ✅ Logs show correct values
- ✅ Different users have different results
- ✅ Backward compatible (defaults still work)

---

## Quick Reference Links

**Document Locations:**
```
/Users/cspenn/Documents/github/supoclip/
├── CLIP_LENGTH_INVESTIGATION_SUMMARY.md ← START HERE
├── CLIP_LENGTH_VISUAL_FLOW.md ← Visual diagrams
├── CLIP_LENGTH_FIX_GUIDE.md ← Implementation steps
├── CLIP_LENGTH_CODE_REFERENCES.md ← Code locations
├── CLIP_LENGTH_SETTINGS_AUDIT.md ← Technical deep dive
└── CLIP_LENGTH_ISSUE_INDEX.md ← This file
```

**Key Files to Modify:**
```
frontend/src/app/page.tsx
backend/src/api/routes/tasks.py
backend/src/services/task_service.py
backend/src/services/video_service.py
backend/src/workers/tasks.py
backend/src/workers/job_queue.py
```

---

## FAQ

**Q: Why weren't these settings working?**
A: The components exist but are never connected. Settings are saved but the video processing pipeline never loads or uses them.

**Q: Will this break existing functionality?**
A: No. All changes use default parameters. Old requests without clip lengths will still work with defaults (10-45s).

**Q: How many files need to change?**
A: 6 files total (1 frontend, 5 backend).

**Q: How long will it take to implement?**
A: About 2 hours including testing, maybe 1.5 hours if you're experienced with the codebase.

**Q: Do I need to change the database?**
A: No. User preferences table already has the columns.

**Q: Will users need to re-save their settings?**
A: No. Existing settings are already in the database. After the fix, they'll just work.

**Q: How do I know if it's working?**
A:
1. Set custom clip lengths in Settings
2. Submit a video
3. Check browser Network tab - request should include clip lengths
4. Check backend logs - should show "Starting AI analysis (min_length=XXs, max_length=XXs)"
5. Verify generated clips are in the configured range

---

## Next Steps

1. **Understand the Issue:** Read `CLIP_LENGTH_INVESTIGATION_SUMMARY.md`
2. **Visualize the Flow:** Review `CLIP_LENGTH_VISUAL_FLOW.md`
3. **Plan Implementation:** Review `CLIP_LENGTH_FIX_GUIDE.md` outline
4. **Start Implementation:** Follow the steps in `CLIP_LENGTH_FIX_GUIDE.md`
5. **Reference as Needed:** Use `CLIP_LENGTH_CODE_REFERENCES.md`
6. **Test Thoroughly:** Use testing strategy from this document
7. **Get Code Review:** Share with team before merging

---

## Contact / Questions

These documents were created based on:
- Frontend code analysis (settings page, video form)
- Backend code analysis (endpoints, services, workers)
- Database schema review (user preferences)
- Configuration review (defaults)

All findings are documented with exact file paths and line numbers for easy verification.

---

**Status:** All investigation complete. Ready for implementation.
**Created:** November 18, 2025
**Last Updated:** November 18, 2025
