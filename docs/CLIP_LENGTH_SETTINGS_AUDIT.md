# Clip Length Settings Flow Audit

**Date:** 2025-11-18
**Issue:** Clip length settings from frontend UI are not being applied to video processing

## Executive Summary

The clip length settings (min_length, target_length, max_length) are configured by users in the Settings page and stored in the database, but they are **NOT being sent from the frontend to the backend** when a video processing task is initiated. Additionally, the backend endpoints don't retrieve these stored preferences when processing videos.

This creates a complete disconnect where:
1. User configures clip lengths (35s, 48s, 58s)
2. Frontend saves to `/api/preferences`
3. Frontend does NOT send these values in the video processing request
4. Backend does NOT load these values from user preferences
5. Backend uses hardcoded defaults (10s-45s) for all users

## Data Flow Analysis

### 1. Frontend Settings Page (`frontend/src/app/settings/page.tsx`)

**Working Correctly:**
- Clip length sliders capture user input (minLength, targetLength, maxLength)
- Validation logic exists (lines 42-57)
- Values are saved to `/api/preferences` via PATCH request (lines 87-125)
- On load, preferences are fetched and loaded into state (lines 76-85)

**State Variables:**
- `clipMinLength` - stored
- `clipTargetLength` - stored
- `clipMaxLength` - stored

### 2. Frontend Video Processing Form (`frontend/src/app/page.tsx`)

**Problem Found:**
- When submitting video for processing (handleSubmit, lines 97-182)
- Line 136: Creates task with POST to `/tasks/`
- Lines 142-152: Request body includes:
  ```json
  {
    "source": { "url": "...", "title": null },
    "font_options": { "font_family": "...", "font_size": 24, "font_color": "#FFFFFF" }
  }
  ```
- **MISSING:** No clip_min_length, clip_max_length, clip_target_length in request

**Root Cause:** The main form doesn't have clip length settings at all. Users set them in Settings, but the form on the home page (where videos are processed) never reads or sends them.

### 3. Backend Task Creation Endpoint (`backend/src/api/routes/tasks.py`)

**Current Implementation (lines 49-119):**
```python
@router.post("/")
async def create_task(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    font_options = data.get("font_options", {})
    # Extracts font options only
    # NO extraction of clip_min_length or clip_max_length

    task_id = await task_service.create_task_with_source(
        user_id=user_id,
        url=raw_source["url"],
        title=raw_source.get("title"),
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        # NO clip length parameters passed
    )
```

**Problems:**
1. Does not extract clip_min_length, clip_max_length from request
2. Does not load user preferences from database
3. Does not pass clip length parameters to task_service.create_task_with_source()
4. Does not enqueue clip length parameters with the job

### 4. Backend Task Service (`backend/src/services/task_service.py`)

**create_task_with_source() method (lines 28-72):**
```python
async def create_task_with_source(
    self,
    user_id: str,
    url: str,
    title: Optional[str] = None,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # MISSING: clip_min_length, clip_max_length parameters
) -> str:
```

**Problems:**
1. Method signature does not accept clip_min_length/clip_max_length
2. Cannot pass these values to task creation
3. No retrieval of user preferences

**process_task() method (lines 74-177):**
```python
async def process_task(
    self,
    task_id: str,
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # MISSING: clip_min_length, clip_max_length parameters
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    ...
    result = await self.video_service.process_video_complete(
        url=url,
        source_type=source_type,
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        # NOT passing clip length parameters
        progress_callback=update_progress,
    )
```

**Problems:**
1. Does not accept clip_min_length/clip_max_length parameters
2. Does not pass them to video_service.process_video_complete()

### 5. Backend Video Service (`backend/src/services/video_service.py`)

**process_video_complete() method (lines 191-254):**
```python
async def process_video_complete(
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # MISSING: clip_min_length, clip_max_length parameters
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    ...
    relevant_parts = await VideoService.analyze_transcript(transcript)
    # NOT passing clip length parameters to analysis
```

**analyze_transcript() method (lines 137-147):**
```python
async def analyze_transcript(transcript: str) -> Any:
    logger.info("Starting AI analysis of transcript")
    relevant_parts = await get_most_relevant_parts_by_transcript(transcript)
    # NOT passing min_length/max_length to AI analysis
    return relevant_parts
```

**Problem:** AI analysis is called without clip length constraints

### 6. Backend Worker Task (`backend/src/workers/tasks.py`)

**process_video_task() function (lines 14-76):**
```python
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    # MISSING: clip_min_length, clip_max_length parameters
) -> Dict[str, Any]:
    ...
    result = await task_service.process_task(
        task_id=task_id,
        url=url,
        source_type=source_type,
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        # NOT passing clip length parameters
        progress_callback=update_progress,
    )
```

**Problems:**
1. Does not accept clip_min_length/clip_max_length parameters
2. Does not pass them to task_service.process_task()

### 7. AI Analysis Functions

**backend/src/ai.py - get_most_relevant_parts_by_transcript() (line 276):**
```python
async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45,
    ...
) -> Any:
```

**Status:** This function DOES accept min_length/max_length parameters with defaults (10s, 45s)
- When called without parameters, it uses hardcoded defaults
- Currently being called without parameters, so defaults are always used

### 8. User Preferences Service

**backend/src/services/user_preferences_service.py**

**Available for loading user preferences:**
- `DEFAULT_PREFERENCES` dict with clip_min_length: 10, clip_max_length: 45
- `get_user_preferences()` method to load from database
- `merge_preferences()` method to merge request options with user preferences

**Status:** Service exists but is NOT being used in the video processing pipeline

## Hardcoded Defaults

All clip length constraints that reach the AI analysis use hardcoded values:

| Component | Min | Target | Max | Source |
|-----------|-----|--------|-----|--------|
| AI analysis | 10s | (none) | 45s | ai.py line 276-277 |
| User default | 10s | 30s | 45s | user_preferences_service.py line 31-33 |
| UI sliders | 5s | 10s | 15s to 60s | settings/page.tsx |

## Missing Data Preservation

The following data is lost at transition points:

1. **Frontend → Backend (Task Creation)**
   - User preferences stored in database but not sent in request
   - Not loaded by endpoint

2. **Endpoint → Worker Queue**
   - Even if endpoint had clip lengths, they're not passed to JobQueue.enqueue_job()
   - Only: task_id, url, source_type, user_id, font_family, font_size, font_color

3. **Worker → Task Service**
   - Worker doesn't pass clip length parameters to task_service.process_task()

4. **Task Service → Video Service**
   - video_service.process_video_complete() doesn't accept clip length parameters

5. **Video Service → AI Analysis**
   - get_most_relevant_parts_by_transcript() called without parameters

## Files Requiring Changes

To fix this issue completely:

1. **frontend/src/app/page.tsx**
   - Import clip length preferences
   - Send clip_min_length, clip_target_length, clip_max_length in POST /tasks/ request

2. **backend/src/api/routes/tasks.py**
   - Extract clip lengths from request OR load user preferences
   - Pass to task_service.create_task_with_source()
   - Pass to JobQueue.enqueue_job()

3. **backend/src/services/task_service.py**
   - Add clip_min_length, clip_max_length to create_task_with_source() signature
   - Add clip_min_length, clip_max_length to process_task() signature
   - Pass to video_service.process_video_complete()

4. **backend/src/services/video_service.py**
   - Add clip_min_length, clip_max_length to process_video_complete() signature
   - Pass to analyze_transcript()

5. **backend/src/workers/tasks.py**
   - Add clip_min_length, clip_max_length to process_video_task() signature
   - Pass to task_service.process_task()

6. **backend/src/ai.py**
   - Already accepts parameters, ensure they're always passed through

## Current Behavior

1. User sets clip lengths to 35s-48s-58s in Settings
2. Settings saved to database successfully
3. User goes to home page and submits video
4. Request sent to /tasks/ WITHOUT clip lengths
5. Backend endpoint ignores user preferences
6. Worker processes with hardcoded defaults (10s-45s)
7. AI selects segments between 10-45 seconds
8. Generated clips are 10-45 seconds long, ignoring user settings

## Expected Behavior

1. User sets clip lengths to 35s-48s-58s in Settings
2. Settings saved to database
3. User submits video on home page
4. Frontend sends clip length settings to backend (from user preferences)
5. Backend endpoint loads user preferences if not in request
6. Worker receives clip length parameters
7. Task service passes to video service
8. Video service passes to AI analysis
9. AI selects segments between 35-58 seconds
10. Generated clips are 35-58 seconds long
