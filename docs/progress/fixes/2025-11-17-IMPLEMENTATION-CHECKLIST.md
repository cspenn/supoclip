# Implementation Checklist

Date: 2025-11-17
Status: Ready for execution

---

## PRE-IMPLEMENTATION CHECKLIST

Before starting any code changes:

- [ ] Read CLAUDE.md to understand project structure
- [ ] Read 2025-11-17-SUMMARY.md to understand the issues
- [ ] Read 2025-11-17-EXACT-CODE-CHANGES.md to see what needs changing
- [ ] Verify you're on `feature/mlx-no-docker-migration` branch
- [ ] Verify working directory is clean: `git status` shows no uncommitted changes
- [ ] Backup current state: `git stash` (just in case)

**Checklist Complete:** [ ]

---

## PHASE 0: PREPARATION

### Step 0.1: Delete Old Caches
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
find temp -name "*.transcript_cache.json" -delete
echo "✅ Old caches deleted"
```

**Verification:**
```bash
find temp -name "*.transcript_cache.json" | wc -l
# Should output: 0
```

- [ ] Command executed
- [ ] Verification shows 0 caches

### Step 0.2: Create Git Checkpoint
```bash
cd /Users/cspenn/Documents/github/supoclip
git add -A
git commit -m "CHECKPOINT: Before implementing critical fixes for clip duration and caption rendering"
```

**Verification:**
```bash
git log --oneline -1
# Should show: CHECKPOINT: Before implementing critical fixes...
```

- [ ] Commit created
- [ ] Commit message correct

---

## PHASE 1: CLIP DURATION FIX

### Step 1.1: Modify Validation Threshold

**File:** `backend/src/ai_structured.py`
**Line:** 274

1. Open file in editor
2. Find line: `if duration < 5:`
3. Change to: `if duration < 10:`
4. Also change log message from "5s" to "10s"
5. Save file

**Verification:**
```bash
grep -n "if duration < 10:" backend/src/ai_structured.py
# Should show: 274:        if duration < 10:
```

- [ ] File opened
- [ ] Line 274 changed from `< 5` to `< 10`
- [ ] Log message updated
- [ ] File saved
- [ ] Verification passed

### Step 1.2: Add Duration Warning Logging

**File:** `backend/src/ai_structured.py`
**Location:** After line 236 (after existing duration analysis logging)

1. Find the block that prints `avg_duration`, `min_duration`, `max_duration`
2. After that `logger.info()`, add new warning code
3. See EXACT-CODE-CHANGES.md for the exact code

**Verification:**
```bash
grep -n "avg_duration < 10.0:" backend/src/ai_structured.py
# Should find the new warning
```

- [ ] Code added after duration analysis
- [ ] Warning triggers when avg < 10s
- [ ] File saved
- [ ] Verification passed

### Step 1.3: Enhance System Prompt

**File:** `backend/src/ai_structured.py`
**Lines:** 56-62 (SYSTEM_PROMPT)

1. Find the DURATION REQUIREMENTS section
2. Replace with enhanced version from EXACT-CODE-CHANGES.md
3. Add examples of acceptable vs rejected durations
4. Save file

**Verification:**
```bash
grep -n "Examples of ACCEPTABLE durations" backend/src/ai_structured.py
# Should find the new examples
```

- [ ] System prompt enhanced
- [ ] Examples added
- [ ] File saved
- [ ] Verification passed

### Phase 1 Git Checkpoint
```bash
git add backend/src/ai_structured.py
git commit -m "FIX: Update clip duration validation from 5s to 10s minimum"
```

- [ ] Changes committed
- [ ] Commit message clear

---

## PHASE 2: CAPTION RENDERING FIX

### Step 2.1: Add Cache Version Constant

**File:** `backend/src/transcription_mlx.py`
**Location:** After imports (around line 28)

1. Open file in editor
2. Find the end of imports section
3. Add constant: `TRANSCRIPT_CACHE_VERSION = "v2"`
4. Add comment explaining version is for format tracking
5. Save file

**Verification:**
```bash
grep -n "TRANSCRIPT_CACHE_VERSION" backend/src/transcription_mlx.py
# Should show: ~28: TRANSCRIPT_CACHE_VERSION = "v2"
```

- [ ] File opened
- [ ] Constant added after imports
- [ ] Comment included
- [ ] File saved
- [ ] Verification passed

### Step 2.2: Update Cache Loading with Version Check

**File:** `backend/src/transcription_mlx.py`
**Lines:** 69-78

1. Find the cache loading section
2. Replace the old `if cache_path.exists():` block
3. Use exact code from EXACT-CODE-CHANGES.md
4. This code checks version and rejects old caches
5. Save file

**Verification:**
```bash
grep -n "cache_version" backend/src/transcription_mlx.py
# Should find version check in cache loading
```

- [ ] Cache loading section replaced
- [ ] Version check added
- [ ] Old caches will be rejected
- [ ] File saved
- [ ] Verification passed

### Step 2.3: Update Cache Creation with Version Field

**File:** `backend/src/transcription_mlx.py`
**Lines:** 96-101 (formatted_result dictionary)

1. Find the `formatted_result` dictionary creation
2. Add `"cache_version": TRANSCRIPT_CACHE_VERSION,` as first field
3. Add `"reconstruction_applied": False,` as last field
4. Save file

**Verification:**
```bash
grep -n "cache_version.*TRANSCRIPT_CACHE_VERSION" backend/src/transcription_mlx.py
# Should find version in formatted_result
```

- [ ] Cache creation updated
- [ ] Version field added
- [ ] Reconstruction flag added
- [ ] File saved
- [ ] Verification passed

### Step 2.4: Enhance Reconstruction Status Logging

**File:** `backend/src/transcription_mlx.py`
**Lines:** 110-128 (word reconstruction block)

1. Find the word reconstruction section
2. Replace the entire try/except block
3. Use exact code from EXACT-CODE-CHANGES.md
4. This adds better success/failure logging with examples
5. Save file

**Verification:**
```bash
grep -n "✅ Word reconstruction complete" backend/src/transcription_mlx.py
# Should find the new success message
grep -n "❌ Word reconstruction FAILED" backend/src/transcription_mlx.py
# Should find the new error message
```

- [ ] Reconstruction logging enhanced
- [ ] Success message with sample words
- [ ] Error message with debugging info
- [ ] File saved
- [ ] Verification passed

### Phase 2 Git Checkpoint
```bash
git add backend/src/transcription_mlx.py
git commit -m "FIX: Implement cache versioning to invalidate old caches and force word reconstruction"
```

- [ ] Changes committed
- [ ] Commit message clear

---

## PHASE 3: ENVIRONMENT DOCUMENTATION

### Step 3.1: Update Environment Template

**File:** `backend/.env.example`

1. Open file in editor
2. Add the new configuration variables at the end
3. Include the comments explaining each variable
4. From EXACT-CODE-CHANGES.md, add:
   - RECONSTRUCT_WORDS_WITH_LLM=true
   - CLIP_MIN_LENGTH=10
   - CLIP_MAX_LENGTH=45
5. Save file

**Verification:**
```bash
grep "RECONSTRUCT_WORDS_WITH_LLM" backend/.env.example
# Should show the variable
grep "CLIP_MIN_LENGTH" backend/.env.example
# Should show the variable
```

- [ ] File opened
- [ ] Variables added
- [ ] Comments clear and helpful
- [ ] File saved
- [ ] Verification passed

### Phase 3 Git Checkpoint
```bash
git add backend/.env.example
git commit -m "DOCS: Update environment template with caption and clip duration settings"
```

- [ ] Changes committed
- [ ] Commit message clear

---

## TESTING PHASE

### Step 4.1: Run Code Quality Checks

```bash
cd /Users/cspenn/Documents/github/supoclip
./checkpython.sh
```

**Expected Output:**
```
✅ Ruff: 0 errors
✅ MyPy: 0 errors
✅ Bandit: 0 errors
✅ Tests: 100% passing
```

- [ ] Command executed
- [ ] Ruff check passed (0 errors)
- [ ] MyPy check passed (0 errors)
- [ ] Bandit check passed (0 errors)
- [ ] Tests passing (100%)

### Step 4.2: Run Specific Tests

```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run tests related to captions
python -m pytest tests/test_caption_reconstruction.py -v

# Should show all tests passing from commit 4ab6105
```

**Expected:** All caption reconstruction tests pass

- [ ] Caption tests running
- [ ] All tests passing
- [ ] No new failures

### Step 4.3: Manual Testing - Duration Fix

```bash
# Process a test video using the API or direct function call
# Monitor logs for:

tail -100 backend/logs/backend-*.log | grep "ACCEPTED: Segment"
# All segments should show duration >= 10 seconds
# Example: "ACCEPTED: Segment 00:15.000-00:30.000 (15.00s, score 0.90)"

# Also check for rejection messages:
tail -100 backend/logs/backend-*.log | grep "REJECTED: Too short"
# Should NOT see this message if all segments are >= 10s
```

- [ ] Test video processed
- [ ] All clips shown as 10+ seconds
- [ ] No sub-10s segments accepted
- [ ] Logs show correct behavior

### Step 4.4: Manual Testing - Caption Rendering

```bash
# Process the same test video (or a new one)
# Monitor logs for:

tail -100 backend/logs/backend-*.log | grep "✅ Word reconstruction complete"
# Should see this message

tail -100 backend/logs/backend-*.log | grep "cache_version"
# Should show version check

# Check the generated cache file:
python3 -c "import json; d=json.load(open('backend/temp/uploads/[ID].transcript_cache.json')); print('Cache version:', d.get('cache_version')); print('First 3 words:', [w['text'] for w in d['words'][:3]])"
# Should show:
# Cache version: v2
# First 3 words: ['Word1', 'Word2', 'Word3'] (complete words, not broken tokens)
```

- [ ] Video processed
- [ ] Log shows cache version check
- [ ] Log shows "Word reconstruction complete"
- [ ] Cache contains complete words (not "Y", "es")
- [ ] Generated clip has readable captions

### Step 4.5: Final Integration Test

Process 2-3 diverse videos to verify both fixes work:

For each video:
- [ ] Check clip durations are 10-45 seconds
- [ ] Check captions show complete words
- [ ] Check no errors in logs
- [ ] Check "Word reconstruction complete" in logs

---

## FINAL VERIFICATION

### Check List Before Finishing

- [ ] All code changes implemented
- [ ] All tests passing
- [ ] Quality checks passing (checkpython.sh)
- [ ] Manual testing successful
- [ ] Old caches deleted (find temp -name "*.transcript_cache.json" | wc -l = 0)
- [ ] Git commits clear and descriptive
- [ ] Documentation updated (.env.example)

### Run Final Checks

```bash
cd /Users/cspenn/Documents/github/supoclip

# Check commit history
git log --oneline -5
# Should show your 3 new commits

# Check no uncommitted changes
git status
# Should show: "nothing to commit, working tree clean"

# Verify all files modified
git diff HEAD~3..HEAD --name-only
# Should show: backend/src/ai_structured.py, backend/src/transcription_mlx.py, backend/.env.example

# Final code quality check
./checkpython.sh
# All checks should pass
```

- [ ] Commit history clean
- [ ] No uncommitted changes
- [ ] Correct files modified
- [ ] All quality checks pass

---

## SUCCESS CRITERIA

### Duration Fix Working When:
- [ ] System logs show all clips >= 10 seconds
- [ ] Validation threshold changed from 5 to 10
- [ ] System prompt enhanced with duration examples
- [ ] Tests pass without regression

### Caption Fix Working When:
- [ ] Generated captions show complete words
- [ ] Log shows "✅ Word reconstruction complete"
- [ ] Cache has cache_version: v2
- [ ] Old caches are rejected and re-transcribed

### Overall Success When:
- [ ] All quality checks pass
- [ ] All tests pass (100%)
- [ ] Manual testing confirms both fixes work
- [ ] No regressions in existing functionality
- [ ] Git history is clean

---

## TROUBLESHOOTING

### If Tests Fail

```bash
# Check what failed
python -m pytest tests/ -v 2>&1 | head -50

# Re-run specific test with more detail
python -m pytest tests/test_caption_reconstruction.py::test_name -vv

# If import errors, check Python path
python -c "import sys; print(sys.path)"
```

**Common Issues:**
- Import errors: Make sure you're in `backend/` directory
- MyPy errors: Check type hints in modified lines
- Ruff errors: Check formatting and import order

### If Captions Still Broken

```bash
# Check that old caches are gone
find backend/temp -name "*.transcript_cache.json" | wc -l
# Should be 0

# Check that reconstruction actually ran
grep -i "reconstruction" backend/logs/backend-*.log | tail -5
# Should show successful reconstruction

# Check cache content
python3 -c "import json; d=json.load(open('path/to/cache.json')); print(d.keys()); print('First word:', d['words'][0])"
# Should have cache_version key
# First word should be complete (not partial token)
```

### If Clips Still Short

```bash
# Check validation threshold was updated
grep -n "if duration < " backend/src/ai_structured.py
# Should show: if duration < 10:

# Check system prompt was enhanced
grep "Examples of" backend/src/ai_structured.py
# Should find the duration examples

# Check logs for rejection messages
grep "REJECTED" backend/logs/backend-*.log | tail -5
# Should see any segments < 10s being rejected
```

---

## Cleanup After Success

Once everything is working and verified:

```bash
# Remove any temporary test files
rm -f backend/temp/test_*.mp4

# Create final release tag (optional, if deploying)
git tag -a v1.0-critical-fixes -m "Critical fixes for clip duration and caption rendering"

# View summary of changes
git log --oneline v1.0-critical-fixes~3..v1.0-critical-fixes
```

- [ ] Temporary files cleaned up
- [ ] Release tagged (if applicable)
- [ ] Summary reviewed

---

## Post-Implementation

### Monitor Production (Next 24 Hours)

- [ ] Check logs for any "Word reconstruction FAILED" errors
- [ ] Monitor for "cache_version mismatch" messages
- [ ] Verify users report better caption and clip quality
- [ ] Check if re-transcription time is acceptable (~20-30s)

### Document Results

Update relevant documentation with:
- Implementation date: 2025-11-17
- Changes deployed: Both fixes applied
- Testing results: All tests passing
- Production status: Monitoring

---

## Completion

All steps complete when:
- [x] Pre-implementation checklist done
- [x] Phase 0 (Preparation) done
- [x] Phase 1 (Duration Fix) done
- [x] Phase 2 (Caption Fix) done
- [x] Phase 3 (Documentation) done
- [x] Testing phase done
- [x] Final verification done
- [x] Cleanup done

**Status:** READY FOR IMPLEMENTATION

**Estimated Time:** 2.5-3.5 hours total

**Next Step:** Begin Phase 0 (Delete caches and create checkpoint)
