# Fix: Double URL Construction in Clip Playback

**Date:** 2025-11-15
**Status:** FIXED
**Commit:** f2fc2d5

## Problem

Clip video playback and downloads were failing with invalid URLs like:
```
localhost:8008http://localhost:8008/clips/clip_1_0840-0853.mp4
```

Safari error message:
```
Safari can't open the page "localhost:8008http://localhost:8008/clips/clip_1_0840-0853.mp4"
because the page's address isn't valid.
```

## Root Cause

Double URL construction in frontend:

1. **Backend behavior (CORRECT):**
   - `backend/src/repositories/clip_repository.py` line 121 constructs full URLs:
   - Returns: `{backend_url}/clips/{filename}` = `http://localhost:8008/clips/clip_1_0840-0853.mp4`

2. **Frontend behavior (INCORRECT):**
   - `frontend/src/app/tasks/[id]/page.tsx` was prepending `apiUrl` to already-full URLs:
   - Line 596: `src={`${apiUrl}${clip.video_url}`}`
   - Line 638: `href={`${apiUrl}${clip.video_url}`}`
   - This created: `http://localhost:8008` + `http://localhost:8008/clips/...`
   - Result: Invalid double URL

## Configuration

**Backend:**
- `backend/.env`: `BACKEND_URL=http://localhost:8008`
- `backend/src/config.py` line 75: Default `backend_url = "http://localhost:8008"`
- Clip repository uses this to construct full URLs

**Frontend:**
- `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8008`
- `frontend/src/app/tasks/[id]/page.tsx` line 74: `const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`
- Note: Fallback to port 8000 is incorrect but not used since .env.local sets correct value

## Solution

**Changed in `frontend/src/app/tasks/[id]/page.tsx`:**

1. **Line 596 - Video player:**
   ```tsx
   // BEFORE (INCORRECT)
   src={`${apiUrl}${clip.video_url}`}

   // AFTER (CORRECT)
   src={clip.video_url}
   ```

2. **Line 638 - Download link:**
   ```tsx
   // BEFORE (INCORRECT)
   <a href={`${apiUrl}${clip.video_url}`} download={clip.filename}>

   // AFTER (CORRECT)
   <a href={clip.video_url} download={clip.filename}>
   ```

**Rationale:**
Since the backend already returns complete URLs via `clip_repository.py`, the frontend should use them directly without modification.

## Verification

**Backend URL construction:**
```python
# backend/src/repositories/clip_repository.py line 121
"video_url": f"{backend_url}/clips/{row.filename}"
```

**Backend config:**
```python
# backend/src/config.py line 75
self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8008")
```

**Example clip.video_url value:**
```
http://localhost:8008/clips/clip_1_0840-0853.mp4
```

**Frontend now uses this directly:**
- Video playback: `<DynamicVideoPlayer src={clip.video_url} />`
- Download: `<a href={clip.video_url} download={clip.filename}>`

## Impact

- Fixes clip video playback in browser
- Fixes clip download functionality
- No backend changes required
- No configuration changes required
- Simple, surgical frontend fix

## Testing

To verify the fix:
1. Start backend: `uvicorn src.main:app --host 0.0.0.0 --port 8008`
2. Start frontend: `npm run dev`
3. Process a video to generate clips
4. Navigate to task detail page
5. Verify video player loads and plays clips
6. Verify download button works correctly

Expected behavior:
- Video URLs should be: `http://localhost:8008/clips/clip_*.mp4`
- Browser should successfully fetch and play videos
- Download should work without errors
