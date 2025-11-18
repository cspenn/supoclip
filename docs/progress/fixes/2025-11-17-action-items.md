# Action Items: Critical Issues Fix Plan

Date: 2025-11-17
Status: Ready for Implementation

---

## Executive Summary

Two critical issues identified and analyzed:
1. **Clip Duration:** AI returns 7-8s clips instead of 10-45s (validation-prompt mismatch)
2. **Caption Rendering:** Subtitles show broken tokens (cache bypass prevents reconstruction)

Both issues have clear root causes and are actionable. Expected resolution time: 4-6 hours total.

---

## PRIORITY 0: Immediate Actions (Next 30 minutes)

### Action 0.1: Delete Old Caches (Cache Bypass Immediate Fix)

**Why:** Existing caches contain broken tokens and prevent word reconstruction

**Command:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
find temp -name "*.transcript_cache.json" -delete
echo "✅ All transcript caches deleted"
```

**Verification:**
```bash
find temp -name "*.transcript_cache.json" | wc -l
# Should output: 0
```

**Impact:** Next video processing will attempt word reconstruction instead of using old broken cache

---

### Action 0.2: Git Checkpoint Before Changes

**Command:**
```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "CHECKPOINT: Before implementing critical fixes - cache deleted and test files created"
```

**Verification:**
```bash
git log --oneline -1
# Should show: "CHECKPOINT: Before implementing critical fixes..."
```

---

## PRIORITY 1: Critical Fix (Caption Rendering) - 1-2 hours

### Action 1.1: Implement Cache Versioning

**File:** `backend/src/transcription_mlx.py`

**Location:** Line 69-78 (cache loading) and Line 96-101 (cache creation)

**Change 1.1a: Add version constant (line ~30)**
```python
# Add after imports
TRANSCRIPT_CACHE_VERSION = "v2"  # Increment when format changes
```

**Change 1.1b: Update cache loading (lines 69-78)**
```python
# OLD CODE:
cache_path = (
    Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
)
if cache_path.exists():
    logger.info(f"Loading cached transcript: {cache_path}")
    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cached transcript: {e}")

# NEW CODE:
cache_path = (
    Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
)
if cache_path.exists():
    logger.info(f"Loading cached transcript: {cache_path}")
    try:
        with open(cache_path, "r") as f:
            cached_data = json.load(f)

        # Check cache version
        if cached_data.get("cache_version") != TRANSCRIPT_CACHE_VERSION:
            logger.warning(
                f"Cache version mismatch (expected {TRANSCRIPT_CACHE_VERSION}, "
                f"got {cached_data.get('cache_version')}). Re-transcribing..."
            )
            # Fall through to fresh transcription
        else:
            return cached_data
    except Exception as e:
        logger.warning(f"Failed to load cached transcript: {e}")
        # Fall through to fresh transcription
```

**Change 1.1c: Update cache creation (lines ~96-101)**
```python
# OLD CODE:
formatted_result = {
    "text": _extract_text_from_result(result),
    "segments": _extract_segments_from_result(result),
    "words": _extract_words_from_result(result),
    "language": "en",
}

# NEW CODE:
formatted_result = {
    "cache_version": TRANSCRIPT_CACHE_VERSION,
    "text": _extract_text_from_result(result),
    "segments": _extract_segments_from_result(result),
    "words": _extract_words_from_result(result),
    "language": "en",
    "reconstruction_applied": False,  # Will be set to True if reconstruction runs
}
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "TRANSCRIPT_CACHE_VERSION" src/transcription_mlx.py
# Should find version constant
grep -n "cache_version" src/transcription_mlx.py
# Should find 3+ occurrences in loading and creation
```

---

### Action 1.2: Add Reconstruction Status Flag

**File:** `backend/src/transcription_mlx.py`

**Location:** Line 110-128 (word reconstruction block)

**Change:**
```python
# OLD CODE:
if words_list and config.reconstruct_words_with_llm:
    logger.info("Reconstructing broken sub-word tokens with Groq LLM...")
    try:
        reconstructed_words = asyncio.run(
            _reconstruct_words_with_llm(words_list)
        )
        formatted_result["words"] = reconstructed_words
        # Update text with reconstructed words
        formatted_result["text"] = " ".join(
            w["text"] for w in reconstructed_words
        )
        logger.info(
            f"Word reconstruction complete: {len(formatted_result['words'])} words"
        )
    except Exception as e:
        logger.warning(
            f"Word reconstruction failed, using original tokens: {e}"
        )

# NEW CODE:
if words_list and config.reconstruct_words_with_llm:
    logger.info("Reconstructing broken sub-word tokens with Groq LLM...")
    try:
        reconstructed_words = asyncio.run(
            _reconstruct_words_with_llm(words_list)
        )
        formatted_result["words"] = reconstructed_words
        formatted_result["reconstruction_applied"] = True
        # Update text with reconstructed words
        formatted_result["text"] = " ".join(
            w["text"] for w in reconstructed_words
        )
        sample_words = " ".join(w["text"] for w in reconstructed_words[:5])
        logger.info(
            f"✅ Word reconstruction complete: {len(formatted_result['words'])} words. "
            f"Sample: {sample_words}"
        )
    except Exception as e:
        logger.error(
            f"❌ Word reconstruction FAILED: {e}. "
            f"Captions will use broken BPE tokens."
        )
        # Log more detail to help debugging
        logger.debug(f"First 3 broken words: {[w['text'] for w in words_list[:3]]}")
else:
    if not config.reconstruct_words_with_llm:
        logger.warning(
            "⚠️ Word reconstruction DISABLED (RECONSTRUCT_WORDS_WITH_LLM=false). "
            f"Captions will contain broken BPE tokens."
        )
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "reconstruction_applied" src/transcription_mlx.py
# Should find 2 occurrences (setting True and checking in logging)
grep -n "✅ Word reconstruction complete" src/transcription_mlx.py
# Should find new success log message
```

---

### Action 1.3: Update Environment Template

**File:** `backend/.env.example`

**Add these lines (if not already present):**
```bash
# Word reconstruction using Groq LLM
# Fixes parakeet-mlx BPE tokenization that returns sub-word tokens (e.g., "Y es" instead of "Yes")
# Set to false only if testing or if you want to disable reconstruction
RECONSTRUCT_WORDS_WITH_LLM=true

# Clip generation constraints (minimum and maximum seconds)
CLIP_MIN_LENGTH=10
CLIP_MAX_LENGTH=45
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep "RECONSTRUCT_WORDS_WITH_LLM" .env.example
# Should show the variable and comment
```

---

### Action 1.4: Test Cache Versioning

**Command:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run tests for caption reconstruction
python -m pytest tests/test_caption_reconstruction.py -v
```

**Expected Result:**
```
test_caption_reconstruction.py::... PASSED
# All 6 tests from commit 4ab6105 should still pass
```

**Verification of Fix:**
```bash
# Process a new video through the API
# Check the generated cache file for cache_version field
python3 -c "import json; d=json.load(open('temp/uploads/[VIDEO_ID].transcript_cache.json')); print('Cache version:', d.get('cache_version')); print('Reconstruction applied:', d.get('reconstruction_applied'))"

# Expected output:
# Cache version: v2
# Reconstruction applied: True or False
```

---

## PRIORITY 2: High Priority Fix (Clip Duration) - 1-2 hours

### Action 2.1: Update Validation Threshold

**File:** `backend/src/ai_structured.py`

**Location:** Line 274-279

**Change:**
```python
# OLD CODE (line 274):
if duration < 5:
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 5s required). Text: '{segment.text[:40]}...'"
    )
    continue

# NEW CODE:
if duration < 10:  # Match system prompt requirement (min 10 seconds)
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 10s required). Text: '{segment.text[:40]}...'"
    )
    continue
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "if duration < 10:" src/ai_structured.py
# Should find the line number showing the change
```

---

### Action 2.2: Add Duration Validation Logging

**File:** `backend/src/ai_structured.py`

**Location:** Line 206-236 (add after duration analysis)

**Add after line 236:**
```python
# Add warning if average duration is below 10-second minimum
if avg_duration < 10.0:
    logger.warning(
        f"⚠️ WARNING: Groq response has segments below minimum (avg {avg_duration:.2f}s). "
        f"Model may not be following duration constraints. "
        f"Expected: min=10s, max=45s. "
        f"Consider adjusting system prompt or trying with different model."
    )
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "avg_duration < 10.0:" src/ai_structured.py
# Should find the new warning
```

---

### Action 2.3: Enhance System Prompt

**File:** `backend/src/ai_structured.py`

**Location:** Line 56-62 (SYSTEM_PROMPT)

**Change:**
```python
# OLD CODE:
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (DO NOT return segments shorter than 10 seconds)
- MAXIMUM DURATION: 45 seconds per segment
- Duration calculation: end_time - start_time MUST be >= 10 seconds
- NEVER return ultra-short clips (0.56s, 1.36s, 2.5s are INVALID)
- If a segment is less than 10 seconds, DO NOT include it in your response
- Return COMPLETE CLIPS, not word fragments or sentence fragments

# NEW CODE:
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (HARD REQUIREMENT - NO EXCEPTIONS)
- MAXIMUM DURATION: 45 seconds per segment
- Duration calculation: end_time - start_time MUST be >= 10 seconds
- If a segment is shorter than 10 seconds, it will be REJECTED by validation
- Do not return segments that are too short for engagement: avoid 5s, 7s, 9s durations
- Validation will reject any segment with duration < 10 seconds
- Examples of ACCEPTABLE durations: 10.5s, 15.2s, 23.7s, 35.1s, 44.9s
- Examples of REJECTED durations: 5.8s, 7.2s, 9.9s (all too short)
- Return COMPLETE CLIPS, not sentence fragments - expand segments to meet 10s minimum
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "Examples of ACCEPTABLE durations" src/ai_structured.py
# Should find the enhanced prompt
```

---

### Action 2.4: Test Duration Validation

**Command:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run tests for clip duration
python -m pytest tests/ -k duration -v
```

**Expected Result:**
```
test_clip_duration_after_validation_fix.py::... PASSED
# Duration validation tests should pass
```

---

## PRIORITY 3: Hardening (Configuration) - 1-2 hours

### Action 3.1: Update Config Class

**File:** `backend/src/config.py`

**Location:** Add new fields in `__init__` (around line 56-57)

**Add:**
```python
# Clip duration constraints (used by AI for segment selection)
self.clip_min_length = int(os.getenv("CLIP_MIN_LENGTH", "10"))
self.clip_max_length = int(os.getenv("CLIP_MAX_LENGTH", "45"))

# Validate that min < max
if self.clip_min_length >= self.clip_max_length:
    raise ValueError(
        f"Invalid clip duration settings: min ({self.clip_min_length}) "
        f"must be less than max ({self.clip_max_length})"
    )

logger.info(
    f"Clip duration constraints: {self.clip_min_length}s - {self.clip_max_length}s"
)
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "clip_min_length" src/config.py
# Should find the new configuration
```

---

### Action 3.2: Use Config Values in AI Functions

**File:** `backend/src/ai.py`

**Location:** Line 274-279 (function signature)

**Change:**
```python
# OLD CODE:
async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int = 10,
    max_length: int = 45,
    custom_prompt: str | None = None,
) -> TranscriptAnalysis:

# NEW CODE:
async def get_most_relevant_parts_by_transcript(
    transcript: str,
    min_length: int | None = None,
    max_length: int | None = None,
    custom_prompt: str | None = None,
) -> TranscriptAnalysis:
    # Use config defaults if not provided
    if min_length is None:
        min_length = config.clip_min_length
    if max_length is None:
        max_length = config.clip_max_length
```

**Verification:**
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
grep -n "min_length = config.clip_min_length" src/ai.py
# Should find the configuration usage
```

---

## Test & Verification Plan

### Step 1: Run Existing Tests
```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run all tests
python -m pytest tests/ -v

# Expected: All tests pass
# ✅ tests/test_caption_reconstruction.py - 6 tests PASSED
# ✅ tests/test_ai*.py - All tests PASSED
```

### Step 2: Run Quality Checks
```bash
cd /Users/cspenn/Documents/github/supoclip

# Run full code quality checks
./checkpython.sh

# Expected:
# ✅ Ruff: 0 errors
# ✅ MyPy: 0 errors
# ✅ Bandit: 0 errors
# ✅ Tests: 100% passing
```

### Step 3: Manual Testing with Video

```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Process a test video (5+ minutes recommended)
# Use API: POST /start or /start-with-progress
# Or directly call processing function

# Check logs for:
# 1. Cache version check
grep "cache_version" logs/backend-*.log | tail -5
# Expected: "Cache version: v2"

# 2. Word reconstruction
grep "Word reconstruction" logs/backend-*.log | tail -5
# Expected: "✅ Word reconstruction complete"

# 3. Clip duration
grep "ACCEPTED.*Segment" logs/backend-*.log | tail -10
# Expected: All durations >= 10 seconds
# Example: "ACCEPTED: Segment 00:10.000-00:25.500 (15.50s, score 0.90)"

# Check generated clips:
ls -lh temp/clips/ | head -5
# Check that clip files were created

# Visual check (most important):
# - Open a generated clip in video player
# - Verify captions show complete words (not "Y es" or "U h")
# - Verify clip is 10+ seconds long
```

### Step 4: Verification Checklist

- [ ] Cache deleted: `find temp -name "*.transcript_cache.json" | wc -l` = 0
- [ ] Code changes committed: `git log --oneline -5` shows changes
- [ ] Tests passing: `pytest tests/ -v` shows 100% pass
- [ ] Quality checks passing: `./checkpython.sh` shows 0 errors
- [ ] Cache versioning working: New cache has `cache_version: v2`
- [ ] Word reconstruction running: Log shows "✅ Word reconstruction complete"
- [ ] Captions clean: Video shows complete words (not BPE tokens)
- [ ] Clip duration correct: All clips 10-45 seconds (checked via logs)
- [ ] No regressions: All existing functionality still works

---

## Git Workflow

### Checkpoint 1: Before Changes
```bash
git add -A
git commit -m "CHECKPOINT: Before critical fixes - cache deleted and analysis complete"
```

### Checkpoint 2: After Priority 1 (Caption Fix)
```bash
git add -A
git commit -m "FIX: Implement cache versioning and word reconstruction status logging (Issue #2)"
```

### Checkpoint 3: After Priority 2 (Duration Fix)
```bash
git add -A
git commit -m "FIX: Update clip duration validation from 5s to 10s minimum (Issue #1)"
```

### Checkpoint 4: After Priority 3 (Config Hardening)
```bash
git add -A
git commit -m "HARDENING: Move clip duration settings to Config class and environment"
```

### Final: Create Release Tag
```bash
git tag -a v1.0-critical-fixes -m "Critical fixes for caption rendering and clip duration"
git log --oneline -5
```

---

## Rollback Plan (If Needed)

### Quick Rollback
```bash
# If issues occur after implementing fixes:
git reset --hard [CHECKPOINT_COMMIT_HASH]

# Identify checkpoint commits:
git log --oneline | grep CHECKPOINT
```

### Cache Restoration (If Needed)
```bash
# If you need to restore old caches (not recommended):
# They are deleted, but if you saved them:
cp backup/*.transcript_cache.json temp/uploads/
```

---

## Success Criteria

### Clip Duration Issue (RESOLVED when)
- [x] Root cause identified: Validation-prompt mismatch (5s vs 10s)
- [ ] Fix implemented: Validation threshold changed to 10s
- [ ] Tests passing: All duration validation tests pass
- [ ] Production verified: Process video shows all clips 10-45s
- [ ] Logs clear: No segments rejected as too short that are >= 10s

### Caption Rendering Issue (RESOLVED when)
- [x] Root cause identified: Cache bypass prevents word reconstruction
- [ ] Fix implemented: Cache versioning + status logging
- [ ] Caches deleted: All old broken caches removed
- [ ] Tests passing: Reconstruction tests pass
- [ ] Production verified: Generated captions show complete words (not "Y es")
- [ ] Logs clear: Log shows "✅ Word reconstruction complete"

---

## Time Estimate

| Action | Time | Priority |
|--------|------|----------|
| Delete caches + checkpoint | 5 min | 0 |
| Cache versioning | 20 min | 1 |
| Reconstruction logging | 15 min | 1 |
| Duration validation | 15 min | 2 |
| Config hardening | 30 min | 3 |
| Testing & verification | 60 min | All |
| Documentation updates | 30 min | All |
| **Total** | **~3.5 hours** | - |

**Critical path:**
1. Delete caches (5m) → 2. Cache versioning (20m) → 3. Duration fix (15m) → 4. Testing (60m) = ~100 minutes

Can be done in parallel after cache deletion.

---

## Questions to Answer Before Starting

1. **Do we want to keep old caches for reference?**
   - Recommendation: No, delete them. They prevent reconstruction from running.

2. **Should we notify users about re-transcription?**
   - Recommendation: Yes, add status message to API response if cache is being invalidated.

3. **Do we need to handle migration for existing tasks?**
   - Recommendation: No, new caches will be created with correct version. Old tasks will get new caches.

---

## Next Steps

1. **Immediate (now):** Review this action plan
2. **Next:** Confirm you're ready to proceed with fixes
3. **Then:** Execute Priority 0 actions (cache deletion)
4. **Then:** Execute Priorities 1-3 in sequence
5. **Finally:** Run verification and testing

Once you confirm you're ready, I can provide detailed code for each action item or implement them directly if you prefer.
