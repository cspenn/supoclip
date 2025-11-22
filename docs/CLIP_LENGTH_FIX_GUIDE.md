# Clip Length Settings Fix Guide

**Issue:** User-configured clip length settings are not being applied during video processing.

**Root Cause:** Clip length settings flow is broken at multiple points:
1. Frontend doesn't send them in video processing request
2. Backend endpoint doesn't load them from user preferences
3. Backend services don't accept/pass them through the pipeline
4. Worker doesn't receive them
5. AI analysis is called without clip length constraints

---

## Fix Strategy

The fix requires changes across 6 files to complete the data flow:

### Frontend Changes (1 file)
- `frontend/src/app/page.tsx` - Load and send clip length settings with video processing request

### Backend Changes (5 files)
- `backend/src/api/routes/tasks.py` - Extract/load clip lengths and pass to enqueue
- `backend/src/services/task_service.py` - Add clip length parameters to method signatures
- `backend/src/services/video_service.py` - Add clip length parameters to method signatures
- `backend/src/workers/tasks.py` - Add clip length parameters to worker signature
- `backend/src/workers/job_queue.py` - Update enqueue_job to accept clip length parameters

---

## Detailed Fix Instructions

### Fix 1: Frontend - Load and Send Clip Lengths

**File:** `frontend/src/app/page.tsx`

**Current Code (around line 97):**
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  // ... validation ...

  const startResponse = await fetch(`${apiUrl}/tasks/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'user_id': session.user.id,
    },
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
    }),
  });
```

**Required Changes:**

1. Import the hook (add to imports at top):
```typescript
import { useUserPreferences } from "@/hooks/useUserPreferences";
```

2. Add state hook in component (add after other hooks around line ~40):
```typescript
const { preferences } = useUserPreferences();
```

3. Update the fetch request body to include clip lengths:
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
  },
  clip_min_length: preferences?.clipMinLength || 10,
  clip_target_length: preferences?.clipTargetLength || 30,
  clip_max_length: preferences?.clipMaxLength || 45
}),
```

---

### Fix 2: Backend Endpoint - Extract and Pass Clip Lengths

**File:** `backend/src/api/routes/tasks.py`

**Current Code (lines 49-119):**
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
```

**Required Changes:**

1. Add import at top:
```python
from ...services.user_preferences_service import UserPreferencesService
```

2. After font options extraction, add clip length extraction:
```python
    # Get font options
    font_options = data.get("font_options", {})
    font_family = font_options.get("font_family", "TikTokSans-Regular")
    font_size = font_options.get("font_size", 24)
    font_color = font_options.get("font_color", "#FFFFFF")

    # Get clip length settings - from request or user preferences
    clip_min_length = data.get("clip_min_length")
    clip_target_length = data.get("clip_target_length")
    clip_max_length = data.get("clip_max_length")

    # If not in request, load from user preferences
    if not (clip_min_length and clip_max_length):
        pref_service = UserPreferencesService(db)
        user_prefs = await pref_service.get_user_preferences(user_id)
        clip_min_length = clip_min_length or user_prefs.get("clip_min_length", 10)
        clip_target_length = clip_target_length or user_prefs.get("clip_target_length", 30)
        clip_max_length = clip_max_length or user_prefs.get("clip_max_length", 45)
```

3. Pass to create_task_with_source (update the call around line 81-88):
```python
    task_id = await task_service.create_task_with_source(
        user_id=user_id,
        url=raw_source["url"],
        title=raw_source.get("title"),
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        clip_min_length=clip_min_length,
        clip_target_length=clip_target_length,
        clip_max_length=clip_max_length,
    )
```

4. Pass to JobQueue.enqueue_job (update the call around line 96-105):
```python
    job_id = await JobQueue.enqueue_job(
        process_video_task,
        task_id,
        raw_source["url"],
        source_type,
        user_id,
        font_family,
        font_size,
        font_color,
        clip_min_length,
        clip_target_length,
        clip_max_length,
    )
```

---

### Fix 3: Task Service - Accept and Pass Clip Lengths

**File:** `backend/src/services/task_service.py`

**Part A: Update create_task_with_source() signature (lines 28-36):**

```python
# FROM:
async def create_task_with_source(
    self,
    user_id: str,
    url: str,
    title: Optional[str] = None,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
) -> str:

# TO:
async def create_task_with_source(
    self,
    user_id: str,
    url: str,
    title: Optional[str] = None,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    clip_min_length: int = 10,
    clip_target_length: int = 30,
    clip_max_length: int = 45,
) -> str:
```

**Part B: Update process_task() signature (lines 74-83):**

```python
# FROM:
async def process_task(
    self,
    task_id: str,
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:

# TO:
async def process_task(
    self,
    task_id: str,
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    clip_min_length: int = 10,
    clip_target_length: int = 30,
    clip_max_length: int = 45,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
```

**Part C: Update video_service call in process_task() (around line 113-120):**

```python
# FROM:
result = await self.video_service.process_video_complete(
    url=url,
    source_type=source_type,
    font_family=font_family,
    font_size=font_size,
    font_color=font_color,
    progress_callback=update_progress,
)

# TO:
result = await self.video_service.process_video_complete(
    url=url,
    source_type=source_type,
    font_family=font_family,
    font_size=font_size,
    font_color=font_color,
    clip_min_length=clip_min_length,
    clip_target_length=clip_target_length,
    clip_max_length=clip_max_length,
    progress_callback=update_progress,
)
```

---

### Fix 4: Video Service - Accept and Pass Clip Lengths

**File:** `backend/src/services/video_service.py`

**Part A: Update process_video_complete() signature (lines 191-198):**

```python
# FROM:
async def process_video_complete(
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:

# TO:
async def process_video_complete(
    url: str,
    source_type: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    clip_min_length: int = 10,
    clip_target_length: int = 30,
    clip_max_length: int = 45,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
```

**Part B: Update analyze_transcript call (around line 227):**

```python
# FROM:
relevant_parts = await VideoService.analyze_transcript(transcript)

# TO:
relevant_parts = await VideoService.analyze_transcript(
    transcript,
    min_length=clip_min_length,
    max_length=clip_max_length
)
```

**Part C: Update analyze_transcript() method signature (lines 137-143):**

```python
# FROM:
@staticmethod
async def analyze_transcript(transcript: str) -> Any:
    logger.info("Starting AI analysis of transcript")
    relevant_parts = await get_most_relevant_parts_by_transcript(transcript)

# TO:
@staticmethod
async def analyze_transcript(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45
) -> Any:
    logger.info(f"Starting AI analysis of transcript (min_length={min_length}s, max_length={max_length}s)")
    relevant_parts = await get_most_relevant_parts_by_transcript(
        transcript,
        min_length=min_length,
        max_length=max_length
    )
```

---

### Fix 5: Worker Task - Accept and Pass Clip Lengths

**File:** `backend/src/workers/tasks.py`

**Update process_video_task() signature and call (lines 14-66):**

```python
# FROM:
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
) -> Dict[str, Any]:
    ...
    result = await task_service.process_task(
        task_id=task_id,
        url=url,
        source_type=source_type,
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        progress_callback=update_progress,
    )

# TO:
async def process_video_task(
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    clip_min_length: int = 10,
    clip_target_length: int = 30,
    clip_max_length: int = 45,
) -> Dict[str, Any]:
    ...
    result = await task_service.process_task(
        task_id=task_id,
        url=url,
        source_type=source_type,
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        clip_min_length=clip_min_length,
        clip_target_length=clip_target_length,
        clip_max_length=clip_max_length,
        progress_callback=update_progress,
    )
```

---

### Fix 6: Job Queue - Accept Clip Length Parameters

**File:** `backend/src/workers/job_queue.py`

Find the `enqueue_job` method and update it to accept the new parameters.

**Update enqueue_job() call signature:**

The method needs to accept and store the additional parameters:
- clip_min_length
- clip_target_length
- clip_max_length

These should be passed through to the task function when it's executed.

---

## Testing the Fix

### Manual Testing

1. **Set clip length preferences:**
   - Go to Settings page
   - Set: Min=35s, Target=48s, Max=58s
   - Click Save Preferences

2. **Process a video:**
   - Go to home page
   - Submit a video for processing
   - Observe the "Creating video clips..." step

3. **Verify results:**
   - Check generated clips
   - Verify they're in the 35-58 second range (not 10-45s)

### Browser Console Check

1. Open browser DevTools (F12)
2. Go to Network tab
3. Submit video
4. Look for POST to `/tasks/`
5. In the request body, verify:
   ```json
   {
     "clip_min_length": 35,
     "clip_target_length": 48,
     "clip_max_length": 58
   }
   ```

### Backend Log Check

1. Watch backend logs while processing video
2. Look for line showing: `"Starting AI analysis of transcript (min_length=35s, max_length=58s)"`
3. Verify it matches your configured values

---

## Expected Outcomes

### Before Fix
- All videos use hardcoded 10-45 second clips
- User settings are ignored
- Logs show: "Starting AI analysis of transcript"

### After Fix
- Videos use user-configured clip lengths
- Different users can have different clip length settings
- Logs show: "Starting AI analysis of transcript (min_length=35s, max_length=58s)"

---

## Implementation Order

1. **Start with backend:** Fix files in this order:
   - job_queue.py (update enqueue_job signature)
   - tasks.py (worker - add parameters)
   - video_service.py (accept parameters)
   - task_service.py (accept parameters, pass through)
   - tasks.py (endpoint - load and pass parameters)

2. **Then frontend:**
   - page.tsx (import hook, send clip lengths)

3. **Test** as you go to catch issues early

---

## Backward Compatibility

All changes use default parameters, so:
- Existing API calls without clip lengths will still work
- Will use system defaults (10-45) if not provided
- No database migrations needed
- No breaking changes to existing functionality
