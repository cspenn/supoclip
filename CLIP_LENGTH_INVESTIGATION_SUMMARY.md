# Clip Length Settings Issue - Investigation Summary

**Date:** November 18, 2025
**Status:** Root cause identified, fix plan created

---

## Quick Summary

**Issue:** Video clips are being generated at hardcoded lengths (10-45 seconds) instead of using user-configured clip length settings.

**Root Cause:** The clip length settings flow is completely broken from frontend to backend. User settings are stored in the database but never sent to the video processing pipeline.

**Evidence:**
- Frontend Settings page has sliders for min/target/max clip lengths ✅
- Settings are saved to backend API ✅
- But when processing videos, settings are NOT sent with the request ❌
- Backend doesn't load user preferences ❌
- AI analysis uses hardcoded defaults ❌

---

## Complete Audit Documents Created

Three comprehensive documents have been created in the project root:

### 1. CLIP_LENGTH_SETTINGS_AUDIT.md
**Detailed breakdown of the entire flow**
- Maps where settings exist vs where they're needed
- Shows each transition point where data is lost
- Lists all hardcoded defaults
- Compares current vs expected behavior

### 2. CLIP_LENGTH_FIX_GUIDE.md
**Step-by-step implementation guide**
- 6 files that need changes
- For each file: exact line numbers, current code, required changes
- Testing instructions
- Expected outcomes before/after fix

### 3. CLIP_LENGTH_CODE_REFERENCES.md
**Quick reference with exact code snippets**
- All file paths and line numbers
- Exact code to change
- Data flow diagrams
- Status of each component (working vs broken)

---

## The Problem Explained Simply

```
User Sets: Min=35s, Target=48s, Max=58s
    ↓
Settings saved to database ✅
    ↓
User submits video
    ↓
Frontend does NOT send clip lengths to API ❌
    ↓
Backend receives request without clip lengths ❌
    ↓
Backend does NOT load user preferences ❌
    ↓
AI analysis runs with hardcoded defaults (10s-45s) ❌
    ↓
Result: Generated clips are 10-45 seconds
```

---

## What's Working

✅ **Frontend Settings Page** (`frontend/src/app/settings/page.tsx`)
- Captures user input via sliders
- Saves to `/api/preferences` API endpoint
- Loads preferences on page load

✅ **Backend Preferences Storage**
- User preferences are correctly stored in database
- UserPreferencesService can load them

✅ **AI Analysis Functions** (`backend/src/ai.py`, `backend/src/ai_structured.py`)
- Already accept min_length and max_length parameters
- Already use them correctly in segment validation
- Just not being called with these values

---

## What's Broken

❌ **Frontend → Backend Gap**
- Video processing form doesn't have clip length inputs
- Clip lengths not sent in POST /tasks/ request
- Settings from Settings page are never accessed

❌ **Backend Request Handling**
- Endpoint doesn't extract clip lengths from request
- Endpoint doesn't load user preferences
- Endpoint doesn't pass values to worker

❌ **Backend Service Chain**
- TaskService doesn't accept clip lengths
- VideoService doesn't accept clip lengths
- Worker doesn't receive clip lengths
- Information is lost at each handoff

---

## Files That Need Changes

**Frontend (1 file):**
1. `frontend/src/app/page.tsx` - Load and send clip lengths

**Backend (5 files):**
2. `backend/src/api/routes/tasks.py` - Extract/load and pass clip lengths
3. `backend/src/services/task_service.py` - Add parameters to methods
4. `backend/src/services/video_service.py` - Add parameters to methods
5. `backend/src/workers/tasks.py` - Add parameters to worker function
6. `backend/src/workers/job_queue.py` - Update enqueue_job signature

---

## Detailed Problem Breakdown

### Problem 1: Frontend Doesn't Send Settings

**Location:** `frontend/src/app/page.tsx`, lines 142-152

**Current request body:**
```json
{
  "source": { "url": "...", "title": null },
  "font_options": { ... }
}
```

**Should include:**
```json
{
  "source": { "url": "...", "title": null },
  "font_options": { ... },
  "clip_min_length": 35,
  "clip_target_length": 48,
  "clip_max_length": 58
}
```

**Why:** Frontend can access user preferences but doesn't

---

### Problem 2: Backend Endpoint Doesn't Load Settings

**Location:** `backend/src/api/routes/tasks.py`, lines 49-119

**Current code:**
```python
# Gets font options
font_options = data.get("font_options", {})

# Does NOT get or load clip lengths
# Does NOT call UserPreferencesService
# Does NOT pass to create_task_with_source
```

**Should:**
1. Extract clip lengths from request: `data.get("clip_min_length")`
2. If not in request, load from user preferences: `UserPreferencesService(db).get_user_preferences(user_id)`
3. Pass all values to `task_service.create_task_with_source(..., clip_min_length=..., clip_max_length=...)`
4. Pass all values to `JobQueue.enqueue_job(..., clip_min_length=..., clip_max_length=...)`

---

### Problem 3: Service Chain Doesn't Accept Parameters

**Task Service** (`backend/src/services/task_service.py`):
- `create_task_with_source()` has NO clip length parameters
- `process_task()` has NO clip length parameters

**Video Service** (`backend/src/services/video_service.py`):
- `process_video_complete()` has NO clip length parameters
- `analyze_transcript()` has NO clip length parameters

**Worker** (`backend/src/workers/tasks.py`):
- `process_video_task()` has NO clip length parameters

**Job Queue** (`backend/src/workers/job_queue.py`):
- `enqueue_job()` probably doesn't accept/pass clip length parameters

---

### Problem 4: AI Analysis Never Gets Parameters

**Location:** `backend/src/services/video_service.py`, line 227

**Current code:**
```python
relevant_parts = await VideoService.analyze_transcript(transcript)
```

**Should be:**
```python
relevant_parts = await VideoService.analyze_transcript(
    transcript,
    min_length=clip_min_length,
    max_length=clip_max_length
)
```

**Result:**
- `get_most_relevant_parts_by_transcript()` is called with defaults (10s-45s)
- User preferences (35s-58s) never reach the AI

---

## Data Loss at Each Step

```
Frontend Form:
  - Has access to: preferences (none), user settings (not loaded), request params (not sent)
  ↓ SENDS: Only source and font_options
  ↓ LOSES: clip_min_length, clip_target_length, clip_max_length

Backend Endpoint:
  - Receives: source, font_options (no clip lengths)
  - Has access to: UserPreferencesService (not used)
  ↓ SENDS: Only source, font_options to task_service and job queue
  ↓ LOSES: clip_min_length, clip_target_length, clip_max_length

Job Queue Worker:
  - Receives: source, font_options (no clip lengths)
  - Has access to: None
  ↓ SENDS: Only source, font_options to task_service
  ↓ LOSES: clip_min_length, clip_target_length, clip_max_length

Task Service:
  - Receives: source, font_options (no clip lengths)
  - Has access to: None
  ↓ SENDS: Only source, font_options to video_service
  ↓ LOSES: clip_min_length, clip_target_length, clip_max_length

Video Service:
  - Receives: source, font_options (no clip lengths)
  - Has access to: None
  ↓ SENDS: No parameters to analyze_transcript
  ↓ LOSES: clip_min_length, clip_target_length, clip_max_length

AI Analysis:
  - Receives: transcript (no clip lengths)
  - Uses: Hardcoded defaults (10s-45s)
  ↓ RESULT: Clips generated in 10-45s range
```

---

## Why This Happened

The system was designed with two separate concerns:
1. **User Preferences Service** - Stores clip length settings ✅
2. **Video Processing Service** - Generates clips ✅

But they were never connected. The video processing service was hardcoded to always use 10s-45s, and no one added code to:
1. Load user preferences in the endpoint
2. Pass them through the service chain
3. Use them in AI analysis

---

## Fix Complexity

**Low** - All code components already exist:
- AI functions accept the parameters ✅
- UserPreferencesService can load them ✅
- No database changes needed ✅
- No new dependencies ✅

Just need to:
1. Load preferences in endpoint (1 location)
2. Pass parameters through service chain (5 locations)
3. Load preferences in frontend (1 location)

Total: 6 small changes across 6 files

---

## Testing Strategy

### Pre-Fix Verification
1. Set clip lengths to 35s-58s in Settings
2. Submit a video
3. Check generated clips: Should be 10-45s (broken)

### Post-Fix Verification
1. Set clip lengths to 35s-58s in Settings
2. Submit a video
3. Check browser Network tab: Request should include `"clip_min_length": 35, "clip_max_length": 58`
4. Check backend logs: Should show `"Starting AI analysis (min_length=35s, max_length=58s)"`
5. Check generated clips: Should be 35-58s (fixed)

### Regression Testing
1. Test without custom settings (should use defaults)
2. Test with different settings (15s-25s-35s)
3. Verify other features still work (font options, etc.)

---

## Implementation Priority

**HIGH** - Users expect settings to work

This is a visible bug that affects core functionality. The workaround (hardcoded to 10-45s) makes the Settings page appear broken.

---

## Backward Compatibility

All changes use default parameters, so:
- Old requests without clip lengths still work ✅
- Default to system defaults (10-45s) ✅
- No API breaking changes ✅
- No database migration needed ✅

---

## Key Insight

The issue is **architectural, not technical**. The code to handle clip length parameters already exists in the AI functions:

```python
async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45,
    ...
) -> Any:
```

It just needs to be **called with the right parameters** instead of using defaults.

---

## Next Steps

1. **Review:** Confirm this analysis with the project maintainers
2. **Implement:** Apply changes from `CLIP_LENGTH_FIX_GUIDE.md` in order
3. **Test:** Use verification steps after each change
4. **Commit:** Create a feature branch and commit the fixes
5. **Deploy:** Merge to main and deploy

All guidance is in the three audit documents created.
