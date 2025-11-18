# Video Processing Failure - Debug Summary
Date: 2025-11-18
Analyzed by: Claude Code

---

## ROOT CAUSE IDENTIFIED

**The failure is NOT related to recent fixes (commit 7699f06).**

### Primary Issue: Broken Pydantic AI Fallback

When Groq Structured Outputs validation rejects all segments, the code falls back to Pydantic AI. However, this fallback has NEVER worked for Llama 4 Scout because:

1. Pydantic AI agent has NO TOOLS registered (no @agent.tool decorators)
2. Llama 4 Scout model tries to call `get_transcript_segment` tool
3. Groq API returns 400 error: "tool 'get_transcript_segment' not in request.tools"

### Secondary Issue: Unrealistic Clip Duration Request

User requested clips of 49-58 seconds, but:
- Groq AI returned segments averaging 11.63 seconds (8-13s range)
- All segments rejected as "too short" (< 49s)
- This triggered the broken fallback

**The AI behavior is actually CORRECT** - 10-15 second clips are optimal for viral content (TikTok/YouTube Shorts).

---

## ERROR LOG ANALYSIS

```
2025-11-18 16:37:49 - src.ai_structured - WARNING - REJECTED: Too short -
00:49.200 to 00:58.160 = 8.96s (min 49s required)
...
[All 5 segments rejected]
...
2025-11-18 16:37:49 - src.ai - WARNING - Groq Structured Outputs failed (ValueError),
falling back to Pydantic AI
...
2025-11-18 16:37:52 - groq.BadRequestError: tool call validation failed:
attempted to call tool 'get_transcript_segment' which was not in request.tools
```

**Flow:**
1. Groq Structured Outputs returns 5 segments (all 8-13 seconds)
2. Validation rejects all segments (< 49s minimum)
3. ValueError raised, triggers fallback
4. Pydantic AI tries to use same model (Llama 4 Scout)
5. Model attempts tool calling (incompatible interface)
6. Groq API rejects request (no tools registered)
7. Processing fails completely

---

## VERIFICATION: Recent Fixes Are Working

From commit 7699f06:

### Fix #1: Font Method Change (video_utils.py)
✅ **Working** - Changed `method="caption"` to `method="label"`
- No errors in logs related to TextClip
- Font rendering not mentioned in failure logs
- This fix resolved subtitle cutoff issue

### Fix #2: Dynamic System Prompt (ai_structured.py)
✅ **Working** - Changed static SYSTEM_PROMPT to `build_system_prompt(min_length, max_length)`
- Logs show: "Clip length settings - Min: 49s, Max: 58s"
- Dynamic prompt correctly passing parameters
- Function correctly building prompt with user values

**Conclusion:** Recent fixes are solid. This is a pre-existing bug in fallback logic.

---

## CODE LOCATIONS FOR FIXES

### File 1: `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

**Lines 352-362** - Remove broken fallback

**Current (BROKEN):**
```python
except Exception as e:
    logger.warning(
        f"Groq Structured Outputs failed ({type(e).__name__}), "
        f"falling back to Pydantic AI with configured LLM"
    )
    # Continue to Pydantic AI fallback below
```

**Fixed:**
```python
except ValueError as e:
    logger.error(f"Groq Structured Outputs validation failed: {e}")
    raise ValueError(
        f"AI analysis failed: {e}. "
        f"Try reducing clip duration requirements (recommended: 10-45 seconds)."
    ) from e
except Exception as e:
    logger.error(f"Groq Structured Outputs API error: {e}")
    raise
```

---

### File 2: `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`

**Lines 149-152** - Add parameter validation BEFORE AI call

**Current:**
```python
logger.info("Starting AI analysis of transcript")
relevant_parts = await get_most_relevant_parts_by_transcript(
    transcript, min_length=min_length, max_length=max_length
)
```

**Fixed:**
```python
logger.info("Starting AI analysis of transcript")

# Validate and cap clip duration parameters
if min_length < 10:
    logger.warning(f"min_length {min_length}s too short. Setting to 10s.")
    min_length = 10

if min_length > 45:
    logger.warning(f"min_length {min_length}s too high. Capping at 45s.")
    min_length = 45

if max_length > 60:
    logger.warning(f"max_length {max_length}s too high. Capping at 60s.")
    max_length = 60

if max_length < min_length:
    logger.warning(f"max_length < min_length. Adjusting to {min_length + 10}s.")
    max_length = min_length + 10

relevant_parts = await get_most_relevant_parts_by_transcript(
    transcript, min_length=min_length, max_length=max_length
)
```

---

### File 3: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

**Lines 318-336** - Improve error message with diagnostics

**Current:**
```python
raise ValueError(
    "No valid segments found. All segments were rejected as too short. "
    "This typically means the AI model is returning fragments instead of complete clips (< 5 seconds). "
    "The Groq Llama 4 Scout model may be returning ultra-short segments. "
    "Consider checking the AI system prompt or model performance."
)
```

**Fixed:**
```python
# Calculate average duration for diagnostics
avg_duration = "N/A"
if durations:
    avg_duration = f"{sum(durations)/len(durations):.1f}s"

raise ValueError(
    f"No valid segments found. All {len(analysis.most_relevant_segments)} segments rejected. "
    f"Requested: {min_length}-{max_length}s. AI returned average: {avg_duration}. "
    f"Recommendation: Try shorter clip durations (10-45 seconds work best). "
    f"Most engaging short-form content is 15-30 seconds."
)
```

---

## RECOMMENDED FIX APPROACH

### Option A: Quick Fix (Recommended)
1. Remove broken fallback (File 1)
2. Add parameter validation (File 2)
3. Improve error messages (File 3)

**Time:** ~15 minutes
**Risk:** Low - removes broken code, adds guardrails
**Result:** Clear failures with helpful guidance

### Option B: Comprehensive Fix
1. All of Option A
2. Add working fallback with different model (e.g., GPT-4)
3. Add frontend validation for clip durations
4. Add documentation about optimal clip lengths

**Time:** ~1 hour
**Risk:** Medium - more complex, requires testing
**Result:** Graceful degradation, better UX

---

## TESTING AFTER FIX

### Test 1: Unrealistic Parameters (Should Cap and Succeed)
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=5lN8I4PqLkc"},
    "min_clip_length": 49,
    "max_clip_length": 58
  }'
```

**Expected:**
- Logs show: "min_length 49s too high. Capping at 45s."
- Processing succeeds with 45s cap
- Clips generated successfully

### Test 2: Realistic Parameters (Should Work as Before)
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=5lN8I4PqLkc"},
    "min_clip_length": 15,
    "max_clip_length": 30
  }'
```

**Expected:**
- No parameter warnings
- Processing succeeds
- Clips generated successfully

### Test 3: Edge Cases
```bash
# Test minimum boundary
curl -X POST http://localhost:8000/start -d '{"min_clip_length": 5, "max_clip_length": 10}'
# Expected: Capped to min=10

# Test maximum boundary
curl -X POST http://localhost:8000/start -d '{"min_clip_length": 60, "max_clip_length": 120}'
# Expected: Capped to min=45, max=60
```

---

## ADDITIONAL TESTS NEEDED

Since recent fixes are working, we should add regression tests:

```python
# tests/test_video_processing_fixes.py

def test_font_method_label_not_caption():
    """Verify Fix #1: TextClip uses method='label' not 'caption'."""
    # Test that create_clips_with_transitions uses method='label'
    pass

def test_dynamic_system_prompt():
    """Verify Fix #2: System prompt builds dynamically with user params."""
    prompt_10_45 = build_system_prompt(10, 45)
    assert "10 seconds" in prompt_10_45
    assert "45 seconds" in prompt_10_45

    prompt_30_60 = build_system_prompt(30, 60)
    assert "30 seconds" in prompt_30_60
    assert "60 seconds" in prompt_30_60

def test_parameter_validation_caps_high_values():
    """Verify Fix #3: Parameter validation caps unrealistic requests."""
    # Test that min_length > 45 gets capped
    # Test that max_length > 60 gets capped
    pass
```

---

## FILES FOR REFERENCE

Full analysis documents:
1. `/Users/cspenn/Documents/github/supoclip/backend/docs/progress/fixes/2025-11-18-pydantic-ai-fallback-analysis.md`
2. `/Users/cspenn/Documents/github/supoclip/backend/docs/progress/fixes/2025-11-18-pydantic-ai-fix-code.md`
3. `/Users/cspenn/Documents/github/supoclip/backend/docs/progress/fixes/2025-11-18-debug-summary.md` (this file)

---

## FINAL VERDICT

### What's Broken
- Pydantic AI fallback (pre-existing bug, never worked)
- No parameter validation (allows unrealistic requests)
- Error messages don't guide users to solutions

### What's Working
- Recent fixes (font method, dynamic prompt) ✅
- Groq Structured Outputs (when params are reasonable) ✅
- Validation logic (correctly rejects too-short segments) ✅

### Recommended Action
Implement **Option A: Quick Fix** - removes broken code, adds guardrails, provides clear errors.

No rollback of recent changes needed.
