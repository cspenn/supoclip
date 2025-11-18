# Exact Code Changes Required

Date: 2025-11-17
Format: Copy-paste ready code for each fix

---

## FIX 1: Change Validation Threshold (Clip Duration)

### File: `backend/src/ai_structured.py`
### Line: 274

**BEFORE:**
```python
if duration < 5:
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 5s required). Text: '{segment.text[:40]}...'"
    )
    continue
```

**AFTER:**
```python
if duration < 10:
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 10s required). Text: '{segment.text[:40]}...'"
    )
    continue
```

**Exact Change:** `5` → `10` (line 274)

---

## FIX 2: Add Duration Warning Logging

### File: `backend/src/ai_structured.py`
### Line: After 236 (add new code)

**ADD THIS CODE:**
```python
                # Warning if average duration is below 10-second minimum
                if avg_duration < 10.0:
                    logger.warning(
                        f"⚠️ WARNING: Groq response has segments below minimum (avg {avg_duration:.2f}s). "
                        f"Model may not be following duration constraints. "
                        f"Expected: min=10s, max=45s."
                    )
```

**Location:** Insert after the `logger.info()` that shows duration analysis (around line 236)

---

## FIX 3: Enhance System Prompt with Duration Examples

### File: `backend/src/ai_structured.py`
### Lines: 56-62 (SYSTEM_PROMPT)

**BEFORE:**
```python
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (DO NOT return segments shorter than 10 seconds)
- MAXIMUM DURATION: 45 seconds per segment
- Duration calculation: end_time - start_time MUST be >= 10 seconds
- NEVER return ultra-short clips (0.56s, 1.36s, 2.5s are INVALID)
- If a segment is less than 10 seconds, DO NOT include it in your response
- Return COMPLETE CLIPS, not word fragments or sentence fragments
```

**AFTER:**
```python
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (HARD REQUIREMENT - NO EXCEPTIONS)
- MAXIMUM DURATION: 45 seconds per segment
- Duration calculation: end_time - start_time MUST be >= 10 seconds
- Validation will REJECT any segment shorter than 10 seconds
- If a segment is shorter than 10 seconds, it will NOT be included in output
- Do not return segments that are too short: avoid 5s, 7s, 9s durations
- Validation will REJECT segments with duration < 10 seconds
- Examples of ACCEPTABLE durations: 10.5s, 15.2s, 23.7s, 35.1s, 44.9s
- Examples of REJECTED durations: 5.8s, 7.2s, 9.9s (all too short)
- Return COMPLETE CLIPS, not sentence fragments - expand segments to meet 10s minimum
```

---

## FIX 4: Add Cache Versioning (Word Reconstruction)

### File: `backend/src/transcription_mlx.py`
### Location: After imports (around line 28)

**ADD THIS CONSTANT:**
```python
# Cache versioning for tracking transcript format changes
# Increment this when transcript format changes to invalidate old caches
TRANSCRIPT_CACHE_VERSION = "v2"
```

---

## FIX 5: Update Cache Loading with Version Check

### File: `backend/src/transcription_mlx.py`
### Lines: 69-78

**BEFORE:**
```python
    # Check cache first - avoid re-transcribing
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
            # Continue with fresh transcription
```

**AFTER:**
```python
    # Check cache first - avoid re-transcribing
    cache_path = (
        Path(video_path).parent / f"{Path(video_path).stem}.transcript_cache.json"
    )
    if cache_path.exists():
        logger.info(f"Loading cached transcript: {cache_path}")
        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check cache version - reject old caches
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
            # Continue with fresh transcription
```

---

## FIX 6: Update Cache Creation with Version and Reconstruction Flag

### File: `backend/src/transcription_mlx.py`
### Lines: 96-101

**BEFORE:**
```python
        # Format result to match AssemblyAI structure for backward compatibility
        formatted_result = {
            "text": _extract_text_from_result(result),
            "segments": _extract_segments_from_result(result),
            "words": _extract_words_from_result(result),
            "language": "en",
        }
```

**AFTER:**
```python
        # Format result to match AssemblyAI structure for backward compatibility
        formatted_result = {
            "cache_version": TRANSCRIPT_CACHE_VERSION,
            "text": _extract_text_from_result(result),
            "segments": _extract_segments_from_result(result),
            "words": _extract_words_from_result(result),
            "language": "en",
            "reconstruction_applied": False,  # Will be set to True if reconstruction runs
        }
```

---

## FIX 7: Add Reconstruction Status Logging

### File: `backend/src/transcription_mlx.py`
### Lines: 110-128 (replace entire block)

**BEFORE:**
```python
        # Reconstruct broken words from parakeet-mlx tokenization (if enabled)
        # parakeet-mlx uses BPE tokenization which returns sub-word tokens
        # Use Groq LLM to reconstruct complete words while preserving timing
        config = Config()
        words_list: List[Dict[str, Any]] = (
            list(formatted_result.get("words", []))  # type: ignore
        )
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
                # Continue with broken tokens if reconstruction fails
```

**AFTER:**
```python
        # Reconstruct broken words from parakeet-mlx tokenization (if enabled)
        # parakeet-mlx uses BPE tokenization which returns sub-word tokens
        # Use Groq LLM to reconstruct complete words while preserving timing
        config = Config()
        words_list: List[Dict[str, Any]] = (
            list(formatted_result.get("words", []))  # type: ignore
        )
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
                logger.debug(f"First 3 broken words: {[w['text'] for w in words_list[:3]]}")
        else:
            if not config.reconstruct_words_with_llm:
                logger.warning(
                    "⚠️ Word reconstruction DISABLED (RECONSTRUCT_WORDS_WITH_LLM=false). "
                    f"Captions will contain broken BPE tokens."
                )
```

---

## FIX 8: Update Environment Template

### File: `backend/.env.example`
### Add these lines (if not present)

**ADD:**
```bash
# Word reconstruction using Groq LLM
# Fixes parakeet-mlx BPE tokenization that returns sub-word tokens (e.g., "Y es" instead of "Yes")
# Set to false only if testing or if you want to disable reconstruction
RECONSTRUCT_WORDS_WITH_LLM=true

# Clip generation constraints (minimum and maximum seconds)
# Segments outside this range will be rejected by validation
CLIP_MIN_LENGTH=10
CLIP_MAX_LENGTH=45
```

---

## Summary of Changes

| File | Lines | Change | Purpose |
|------|-------|--------|---------|
| `ai_structured.py` | 274 | `5` → `10` | Fix: Duration validation threshold |
| `ai_structured.py` | ~237 | Add logging | Diagnostic: Warn if clips too short |
| `ai_structured.py` | 56-62 | Enhance prompt | Improve: Add duration examples to AI |
| `transcription_mlx.py` | ~28 | Add constant | Add: Cache version tracking |
| `transcription_mlx.py` | 69-78 | Update cache loading | Fix: Check cache version |
| `transcription_mlx.py` | 96-101 | Update cache creation | Add: Version and reconstruction flag |
| `transcription_mlx.py` | 110-128 | Update logging | Improve: Better reconstruction status |
| `.env.example` | End | Add variables | Doc: Document new configuration |

**Total Lines Changed:** ~50 lines
**Files Modified:** 3 Python files + 1 environment template
**Risk Level:** LOW to MEDIUM
**Testing Required:** Unit tests + manual video processing

---

## Verification Commands

### After implementing all changes:

```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# 1. Check changes are in place
grep -n "if duration < 10:" src/ai_structured.py
# Should show: "274:        if duration < 10:"

grep -n "TRANSCRIPT_CACHE_VERSION" src/transcription_mlx.py
# Should show: ~2 occurrences

grep -n "✅ Word reconstruction complete" src/transcription_mlx.py
# Should show: ~1 occurrence

# 2. Run tests
python -m pytest tests/ -v
# Should show: 100% passing

# 3. Run quality checks
./checkpython.sh
# Should show: 0 errors in all categories

# 4. Delete old caches
find temp -name "*.transcript_cache.json" -delete
echo "✅ Old caches deleted"

# 5. Process a test video and verify
# Check logs for:
grep "cache_version" logs/backend-*.log | tail -3
# Should show cache version checks

grep "✅ Word reconstruction complete" logs/backend-*.log | tail -3
# Should show reconstruction success

grep "ACCEPTED: Segment" logs/backend-*.log | tail -10
# Should show all durations >= 10 seconds
```

---

## Implementation Order

1. **First:** FIX 1 - Change validation threshold (1 line, lowest risk)
2. **Second:** FIX 2 - Add logging (diagnostic, safe)
3. **Third:** FIX 3 - Enhance prompt (safe, improves AI behavior)
4. **Fourth:** FIX 4-7 - Cache versioning (related changes, do together)
5. **Fifth:** FIX 8 - Update environment template (documentation)

After all changes: Delete old caches and test.

---

## Rollback Plan

If issues occur, rollback is simple:

```bash
# Reset to checkpoint before changes
git reset --hard [CHECKPOINT_HASH]

# Find checkpoint:
git log --oneline | grep "CHECKPOINT"

# Or undo specific file:
git checkout HEAD~1 -- backend/src/ai_structured.py
git checkout HEAD~1 -- backend/src/transcription_mlx.py
```

---

## Notes for Implementation

- All changes are backward compatible
- No database migrations needed
- No API changes required
- No user-facing breaking changes
- Cache deletion is the only user impact (forces re-transcription)

**The word reconstruction feature was already implemented in commit 4ab6105. These changes just:**
1. Make validation threshold match the AI prompt (Duration fix)
2. Force old caches to be invalidated so reconstruction actually runs (Caption fix)

No new features being added, just fixes to make existing features work as intended.
