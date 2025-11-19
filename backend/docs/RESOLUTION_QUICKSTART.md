# Video Resolution Feature - Quick Start Guide

## Overview

SupoClip now supports selectable output resolutions for generated video clips.

**Available Options:**
- `480p` (480x854) - SD quality, smallest file size
- `720p` (720x1280) - HD quality, balanced (DEFAULT)
- `1080p` (1080x1920) - Full HD quality, best quality

**Status:** Backend complete, frontend integration pending

## Backend API Usage

### Request Format

Add `output_resolution` parameter to your request:

```bash
POST /start
Content-Type: application/json
X-User-ID: your-user-id

{
  "source": {"url": "https://youtube.com/..."},
  "output_resolution": "1080p"
}
```

### Valid Values

- `"480p"` - SD quality
- `"720p"` - HD quality (default if omitted)
- `"1080p"` - Full HD quality

Invalid values fall back to `"720p"`.

## How It Works

1. **Face Detection** - Runs on original video quality
2. **Cropping** - Crops to 9:16 ratio centered on face
3. **Scaling** - NEW: Scales cropped video to target resolution
4. **Subtitles** - Added at target resolution
5. **Encoding** - Output at specified resolution

**Key:** Scaling happens AFTER cropping for best quality.

## Frontend Integration TODO

### 1. Add Resolution Selector (frontend/src/app/page.tsx)

```typescript
// State
const [outputResolution, setOutputResolution] = useState("720p");

// UI (add after font customization)
<Select value={outputResolution} onValueChange={setOutputResolution}>
  <SelectContent>
    <SelectItem value="480p">480p - SD</SelectItem>
    <SelectItem value="720p">720p - HD</SelectItem>
    <SelectItem value="1080p">1080p - Full HD</SelectItem>
  </SelectContent>
</Select>

// Request
{
  source: {...},
  output_resolution: outputResolution  // ADD THIS
}
```

### 2. Update Preferences Hook (frontend/src/hooks/useUserPreferences.ts)

```typescript
interface UserPreferences {
  // ... existing fields
  outputResolution: "480p" | "720p" | "1080p";
}

const DEFAULT_PREFERENCES = {
  // ... existing defaults
  outputResolution: "720p",
};
```

### 3. Add to Settings Page (frontend/src/app/settings/page.tsx)

```tsx
<Select
  value={preferences.outputResolution}
  onValueChange={(value) => updatePreference('outputResolution', value)}
>
  <SelectContent>
    <SelectItem value="480p">480p - SD</SelectItem>
    <SelectItem value="720p">720p - HD</SelectItem>
    <SelectItem value="1080p">1080p - Full HD</SelectItem>
  </SelectContent>
</Select>
```

### 4. Database Migration (when ready)

```sql
ALTER TABLE users ADD COLUMN output_resolution VARCHAR(10) DEFAULT '720p';
```

## Testing

### Test Backend API

```bash
# Test 480p
curl -X POST http://localhost:8008/start \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test-123" \
  -d '{"source": {"url": "..."}, "output_resolution": "480p"}'

# Test 1080p
curl -X POST http://localhost:8008/start \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test-123" \
  -d '{"source": {"url": "..."}, "output_resolution": "1080p"}'
```

### Verify Output

```bash
# Check video dimensions
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height \
  -of csv=s=x:p=0 temp/clips/[clip-file].mp4

# Expected: 480x854, 720x1280, or 1080x1920
```

### Check Logs

```bash
tail -f logs/application.log | grep -i "scaling\|resolution"

# Look for:
# "Creating 5 video clips at 1080p"
# "Scaling from 720x1280 to 1080x1920 (1080p)"
```

## Performance Notes

**Processing Time:**
- 480p: ~20-30% faster than 720p
- 720p: Baseline (recommended)
- 1080p: ~30-50% slower than 720p

**File Sizes (30s clip):**
- 480p: ~5-8 MB
- 720p: ~10-15 MB
- 1080p: ~20-30 MB

## Implementation Files

**Modified Files:**
- `backend/src/video_utils.py` - Resolution presets and scaling logic
- `backend/src/services/video_service.py` - Parameter passing
- `backend/src/services/video_service_legacy.py` - Legacy sync path
- `backend/src/services/video_service_async.py` - Async path
- `backend/src/services/user_preferences_service.py` - Default preference
- `backend/src/main.py` - API endpoints

**Resolution Presets Location:**
`backend/src/video_utils.py` lines 24-30

**Scaling Logic Location:**
`backend/src/video_utils.py` lines 1109-1118

## Full Documentation

See: `/Users/cspenn/Documents/github/supoclip/backend/docs/progress/fixes/2025-11-18-video-resolution-implementation.md`

## Questions?

- Resolution parameter not working? Check backend logs for "Scaling" messages
- Frontend not showing resolution? See frontend integration TODO above
- Invalid resolution? Backend automatically falls back to 720p
- Database errors? User preferences column not yet added (migration pending)
