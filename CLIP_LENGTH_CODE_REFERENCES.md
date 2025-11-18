# Clip Length Settings - Exact Code References

This document provides the exact file locations, line numbers, and code snippets for the clip length settings issue.

---

## Issue Summary

**Problem:** Clip length settings UI sliders (min/target/max) are not applied to generated clips
**Evidence:** Generated clips are 7-8 seconds (or hardcoded 10-45s range) regardless of user settings
**Root Cause:** Settings are not being passed from frontend → backend → worker → AI analysis

---

## File 1: Frontend Settings (Working)

**File:** `/Users/cspenn/Documents/github/supoclip/frontend/src/app/settings/page.tsx`

**Status:** ✅ WORKING - Settings are saved correctly

**Lines 25-27: State variables defined**
```typescript
const [clipMinLength, setClipMinLength] = useState(10);
const [clipTargetLength, setClipTargetLength] = useState(30);
const [clipMaxLength, setClipMaxLength] = useState(45);
```

**Lines 76-85: Preferences loaded on mount**
```typescript
useEffect(() => {
  if (preferences) {
    setClipMinLength(preferences.clipMinLength);
    setClipTargetLength(preferences.clipTargetLength);
    setClipMaxLength(preferences.clipMaxLength);
```

**Lines 99-110: Preferences saved to backend**
```typescript
const response = await fetch('/api/preferences', {
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    clipMinLength,
    clipTargetLength,
    clipMaxLength,
    customAiPrompt: useCustomPrompt ? customAiPrompt : null,
  }),
});
```

---

## File 2: Frontend Video Processing (BROKEN)

**File:** `/Users/cspenn/Documents/github/supoclip/frontend/src/app/page.tsx`

**Status:** ❌ BROKEN - Does NOT send clip length settings

**Lines 97-182: handleSubmit function**
- **Line 136:** `const startResponse = await fetch(`${apiUrl}/tasks/`, {`
- **Lines 142-152:** Request body sent to backend

**Current request body (MISSING clip lengths):**
```typescript
body: JSON.stringify({
  source: {
    url: videoUrl,
    title: null
  },
  font_options: {
    font_family: fontOptions.family,
    font_size: fontOptions.size,
    font_color: fontOptions.color
  }
  // MISSING: clip_min_length, clip_target_length, clip_max_length
}),
```

**What's missing:**
- No import of `useUserPreferences` hook
- No state variable for preferences
- No clip length parameters in request body

---

## File 3: Backend Task Endpoint (BROKEN)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/api/routes/tasks.py`

**Status:** ❌ BROKEN - Does NOT extract or load clip lengths

**Lines 49-119: create_task endpoint**

**Current implementation:**
```python
@router.post("/")
async def create_task(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    headers = request.headers

    raw_source = data.get("source")
    user_id = headers.get("user_id")

    # Get font options
    font_options = data.get("font_options", {})
    font_family = font_options.get("font_family", "TikTokSans-Regular")
    font_size = font_options.get("font_size", 24)
    font_color = font_options.get("font_color", "#FFFFFF")
    # ❌ NO EXTRACTION OF CLIP LENGTHS

    # Line 81: create_task_with_source called WITHOUT clip lengths
    task_id = await task_service.create_task_with_source(
        user_id=user_id,
        url=raw_source["url"],
        title=raw_source.get("title"),
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        # ❌ NO CLIP LENGTH PARAMETERS
    )

    # Line 96: JobQueue.enqueue_job called WITHOUT clip lengths
    job_id = await JobQueue.enqueue_job(
        process_video_task,
        task_id,
        raw_source["url"],
        source_type,
        user_id,
        font_family,
        font_size,
        font_color,
        # ❌ NO CLIP LENGTH PARAMETERS
    )
```

**What needs to be added:**
1. Extract clip lengths from request (after line 65)
2. Load user preferences if not provided
3. Pass to create_task_with_source()
4. Pass to JobQueue.enqueue_job()

---

## File 4: Backend Task Service (BROKEN)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/services/task_service.py`

**Status:** ❌ BROKEN - Methods don't accept clip lengths

**Lines 28-72: create_task_with_source method**

**Current signature (line 28-36):**
```python
async def create_task_with_source(
    self,
    user_id: str,
    url: str,
    title: Optional[str] = None,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # ❌ NO CLIP LENGTH PARAMETERS
) -> str:
```

**Lines 74-177: process_task method**

**Current signature (lines 74-82):**
```python
async def process_task(
    self,
    task_id: str,
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    progress_callback: Optional[Callable] = None,
    # ❌ NO CLIP LENGTH PARAMETERS
) -> Dict[str, Any]:
```

**Line 113-120: Call to video_service.process_video_complete**
```python
result = await self.video_service.process_video_complete(
    url=url,
    source_type=source_type,
    font_family=font_family,
    font_size=font_size,
    font_color=font_color,
    # ❌ NO CLIP LENGTH PARAMETERS
    progress_callback=update_progress,
)
```

---

## File 5: Backend Video Service (BROKEN)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`

**Status:** ❌ BROKEN - Methods don't accept clip lengths

**Lines 137-147: analyze_transcript method**

**Current implementation:**
```python
@staticmethod
async def analyze_transcript(transcript: str) -> Any:
    logger.info("Starting AI analysis of transcript")
    # ❌ NOT PASSING min_length/max_length
    relevant_parts = await get_most_relevant_parts_by_transcript(transcript)
    logger.info(
        f"AI analysis complete: {len(relevant_parts.most_relevant_segments)} segments found"
    )
    return relevant_parts
```

**Lines 191-254: process_video_complete method**

**Current signature (lines 191-198):**
```python
async def process_video_complete(
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    progress_callback: Optional[Callable] = None,
    # ❌ NO CLIP LENGTH PARAMETERS
) -> Dict[str, Any]:
```

**Line 227: Call to analyze_transcript**
```python
# ❌ NOT PASSING clip length constraints
relevant_parts = await VideoService.analyze_transcript(transcript)
```

---

## File 6: Backend Worker Task (BROKEN)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/workers/tasks.py`

**Status:** ❌ BROKEN - Function doesn't accept clip lengths

**Lines 14-76: process_video_task function**

**Current signature (lines 14-22):**
```python
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # ❌ NO CLIP LENGTH PARAMETERS
) -> Dict[str, Any]:
```

**Lines 59-67: Call to task_service.process_task**
```python
result = await task_service.process_task(
    task_id=task_id,
    url=url,
    source_type=source_type,
    font_family=font_family,
    font_size=font_size,
    font_color=font_color,
    # ❌ NO CLIP LENGTH PARAMETERS
    progress_callback=update_progress,
)
```

---

## File 7: Backend AI Analysis (PARTIALLY WORKING)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

**Status:** ✅ ACCEPTS parameters, but NOT CALLED WITH THEM

**Lines 275-331: get_most_relevant_parts_by_transcript function**

**Correct signature with parameters:**
```python
async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int = 10,  # ✅ HAS PARAMETER
    max_length: int = 45,  # ✅ HAS PARAMETER
    ...
) -> Any:
    logger.info(f"Clip length settings - Min: {min_length}s, Max: {max_length}s")
```

**Line 330-331: Correctly uses parameters**
```python
await get_analysis_structured(
    # ...
    min_length=min_length,  # ✅ PASSED CORRECTLY
    max_length=max_length,  # ✅ PASSED CORRECTLY
)
```

**Problem:** This function IS CALLED WITHOUT these parameters (from video_service.py line 227)

---

## File 8: Backend AI Structured (PARTIALLY WORKING)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

**Status:** ✅ ACCEPTS parameters, but NOT CALLED WITH THEM

**Lines 100-200+: analyze_transcript_structured function**

**Correct signature:**
```python
async def analyze_transcript_structured(
    transcript: str,
    min_length: int = 10,  # ✅ HAS PARAMETER
    max_length: int = 45,  # ✅ HAS PARAMETER
    ...
) -> TranscriptAnalysis:
    logger.info(f"Clip length settings - Min: {min_length}s, Max: {max_length}s")
```

**Problem:** This function accepts parameters but is called without them from upstream

---

## File 9: User Preferences Service (AVAILABLE)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/services/user_preferences_service.py`

**Status:** ✅ EXISTS but NOT USED in video processing endpoint

**Lines 19-37: DEFAULT_PREFERENCES**
```python
DEFAULT_PREFERENCES = {
    "font_family": "TikTokSans-Regular",
    "font_size": 24,
    "font_color": "#FFFFFF",
    "clip_min_length": 10,           # ✅ AVAILABLE
    "clip_target_length": 30,        # ✅ AVAILABLE
    "clip_max_length": 45,           # ✅ AVAILABLE
    "custom_ai_prompt": None,
    "logo_file_path": None,
    "logo_corner_position": "top-right",
}
```

**Lines 77-90+: get_user_preferences method**
```python
async def get_user_preferences(self, user_id: str) -> dict[str, Any]:
    """Load user preferences from database.

    Merges user-stored preferences with system defaults.
    Priority: User prefs > System defaults
    """
    # ✅ CAN BE USED to load clip length settings
```

---

## Data Flow Diagram

```
CURRENT (BROKEN):
================

Frontend Settings Page
  ↓ (saves OK)
  Database: user preferences (clip lengths stored)
  ↓ (NOT loaded)
Frontend Home Page (handleSubmit)
  ↓ (does NOT send clip lengths)
POST /tasks/ body {source, font_options}
  ↓ (does NOT extract clip lengths)
Backend endpoint (create_task)
  ↓ (does NOT load user prefs)
  ↓ (does NOT pass to enqueue)
JobQueue.enqueue_job(process_video_task, ..., NO CLIP LENGTHS)
  ↓
Worker (process_video_task, NO CLIP LENGTH PARAMETERS)
  ↓
TaskService.process_task(..., NO CLIP LENGTHS)
  ↓
VideoService.process_video_complete(..., NO CLIP LENGTHS)
  ↓
VideoService.analyze_transcript(..., NO PARAMETERS)
  ↓
get_most_relevant_parts_by_transcript(transcript)  ← Uses defaults (10s-45s)
  ↓
AI returns segments with hardcoded 10-45s constraints
  ↓
Generated clips are always 10-45 seconds regardless of user settings


REQUIRED (FIXED):
=================

Frontend Settings Page
  ↓ (saves OK)
  Database: user preferences (clip lengths stored)
  ↓ (LOAD HERE)
Frontend Home Page (handleSubmit)
  ↓ (SEND clip lengths)
POST /tasks/ body {source, font_options, clip_min_length, clip_max_length, ...}
  ↓ (EXTRACT clip lengths)
Backend endpoint (create_task)
  ↓ (or LOAD user prefs if not in request)
  ↓ (PASS to enqueue)
JobQueue.enqueue_job(process_video_task, ..., clip_min_length, clip_max_length, ...)
  ↓
Worker (process_video_task, clip_min_length, clip_max_length, ...)
  ↓
TaskService.process_task(..., clip_min_length, clip_max_length, ...)
  ↓
VideoService.process_video_complete(..., clip_min_length, clip_max_length, ...)
  ↓
VideoService.analyze_transcript(..., min_length, max_length)
  ↓
get_most_relevant_parts_by_transcript(transcript, min_length, max_length)  ← Uses user values
  ↓
AI returns segments with user-configured constraints
  ↓
Generated clips match user-configured lengths
```

---

## Summary of Changes Needed

| File | Lines | Change | Status |
|------|-------|--------|--------|
| `frontend/src/app/page.tsx` | ~35 | Import hook | NEEDED |
| `frontend/src/app/page.tsx` | ~150 | Add clip lengths to request | NEEDED |
| `backend/src/api/routes/tasks.py` | 49-119 | Extract/load and pass clip lengths | NEEDED |
| `backend/src/services/task_service.py` | 28-36 | Add params to create_task_with_source | NEEDED |
| `backend/src/services/task_service.py` | 74-82 | Add params to process_task | NEEDED |
| `backend/src/services/task_service.py` | 113-120 | Pass params to video_service call | NEEDED |
| `backend/src/services/video_service.py` | 137-147 | Add params to analyze_transcript | NEEDED |
| `backend/src/services/video_service.py` | 191-198 | Add params to process_video_complete | NEEDED |
| `backend/src/services/video_service.py` | 227 | Pass params to analyze_transcript | NEEDED |
| `backend/src/workers/tasks.py` | 14-22 | Add params to process_video_task | NEEDED |
| `backend/src/workers/tasks.py` | 59-67 | Pass params to process_task | NEEDED |
| `backend/src/workers/job_queue.py` | TBD | Update enqueue_job signature | NEEDED |
| `backend/src/ai.py` | 276-277 | Already has params ✅ | OK |
| `backend/src/ai_structured.py` | 100-103 | Already has params ✅ | OK |

---

## Priority

**CRITICAL:** All 11 changes are needed for the complete flow to work.

**Order of implementation:**
1. job_queue.py - Foundation
2. tasks.py (worker) - Accept params
3. video_service.py - Accept params
4. task_service.py - Accept params, pass through
5. tasks.py (endpoint) - Load and pass params
6. page.tsx - Send from frontend

Test after each change to verify data flows correctly.
