# Fix Implementation Guide
**Date:** 2025-11-19
**Issue:** Test import failure after file reorganization

---

## Quick Fix (5 minutes)

### Fix 1: Update Import in test_transcription_fix.py

**File:** `/Users/cspenn/Documents/github/supoclip/backend/tests/test_transcription_fix.py`

**Line 4 - Change:**
```python
# OLD (BROKEN):
from transcription_mlx import transcribe_video_mlx  # type: ignore

# NEW (FIXED):
from src.transcription_mlx import transcribe_video_mlx
```

**Lines 8-9 - Remove (no longer needed):**
```python
# REMOVE THESE LINES:
# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
```

---

### Complete Fixed File

**File:** `/Users/cspenn/Documents/github/supoclip/backend/tests/test_transcription_fix.py`

```python
"""
Test script to verify parakeet-mlx token extraction fix.
"""
from src.transcription_mlx import transcribe_video_mlx
from pathlib import Path


# Find a test video
video_path = list(Path("temp/uploads").glob("*.mp4"))
if not video_path:
    print("❌ No video file found in temp/uploads/")
    import sys
    sys.exit(1)

video_file = video_path[0]
print(f"📹 Testing transcription on: {video_file}")

# Transcribe
result = transcribe_video_mlx(video_file)

# Verify results
print("\n" + "=" * 80)
print("VERIFICATION RESULTS:")
print("=" * 80)

success = True

# Check 1: Text is not empty
if result["text"] and len(result["text"]) > 0:
    print(f"✅ Text extracted: {len(result['text'])} characters")
    print(f"   First 100 chars: {result['text'][:100]}...")
else:
    print("❌ Text is EMPTY")
    success = False

# Check 2: Words are extracted
if result["words"] and len(result["words"]) > 0:
    print(f"✅ Words extracted: {len(result['words'])} words")
    print(f"   First word: {result['words'][0]}")
    print(f"   Last word: {result['words'][-1]}")
else:
    print("❌ Words are EMPTY")
    success = False

# Check 3: Segments are extracted
if result["segments"] and len(result["segments"]) > 0:
    print(f"✅ Segments extracted: {len(result['segments'])} segments")
    print(
        f"   First segment: start={result['segments'][0]['start']}ms, end={result['segments'][0]['end']}ms"
    )
    print(f"   First segment text: {result['segments'][0]['text'][:80]}...")
else:
    print("❌ Segments are EMPTY")
    success = False

# Check 4: Word timing is valid
if result["words"]:
    first_word = result["words"][0]
    if first_word["start"] < first_word["end"]:
        print("✅ Word timing is valid: start < end")
    else:
        print(
            f"❌ Word timing is INVALID: start={first_word['start']}, end={first_word['end']}"
        )
        success = False

# Check 5: Segment timing is valid
if result["segments"]:
    first_segment = result["segments"][0]
    if first_segment["start"] < first_segment["end"]:
        print("✅ Segment timing is valid: start < end")
    else:
        print(
            f"❌ Segment timing is INVALID: start={first_segment['start']}, end={first_segment['end']}"
        )
        success = False

print("\n" + "=" * 80)
if success:
    print("🎉 ALL CHECKS PASSED - Parakeet-MLX extraction is working correctly!")
    print("=" * 80)
    import sys
    sys.exit(0)
else:
    print("❌ SOME CHECKS FAILED - Parakeet-MLX extraction needs more fixes")
    print("=" * 80)
    import sys
    sys.exit(1)
```

---

## Verification Steps

### Step 1: Verify test collection works
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
python -m pytest --collect-only 2>&1 | grep -E "(collected|error)"
```

**Expected Output:**
```
collected 544 items
```

**If you see errors:** Check the error message and ensure all imports are correct.

---

### Step 2: Verify specific test file
```bash
python -m pytest tests/test_transcription_fix.py -v
```

**Expected:**
- Import succeeds (no `ModuleNotFoundError`)
- Test may fail if no video file exists in `temp/uploads/` - that's expected
- The important thing is the import works

---

### Step 3: Run full test suite
```bash
python -m pytest tests/ -v --tb=short
```

**Expected:**
- All tests that can run will run
- Some may fail due to missing test data (videos, etc.)
- Import errors should be eliminated

---

## Git Workflow

### Before Making Changes
```bash
# Check current status
git status

# See uncommitted changes
git diff src/api/routes/tasks.py src/video_utils.py

# Create checkpoint if desired
git add -A
git commit -m "CHECKPOINT: Before fixing test imports"
```

### After Implementing Fix
```bash
# Stage the fixed file
git add tests/test_transcription_fix.py

# Commit with descriptive message
git commit -m "fix(tests): correct import path after file reorganization

- Update import from 'transcription_mlx' to 'src.transcription_mlx'
- Remove unnecessary sys.path manipulation
- Fixes ModuleNotFoundError during test collection"
```

---

## Alternative: Just Remove the Problematic Test

If this test is not critical and you want to unblock quickly:

```bash
# Remove or comment out the test
mv tests/test_transcription_fix.py tests/test_transcription_fix.py.disabled
```

Then verify test collection works:
```bash
python -m pytest --collect-only 2>&1 | grep collected
```

**Note:** This is a temporary workaround. The proper fix is to update the import.
