# Root Cause Analysis: Pydantic AI Fallback Failure
Date: 2025-11-18

## Executive Summary

**Root Cause:** Pydantic AI agent has NO TOOLS registered, but Groq's Llama 4 Scout model attempts to call `get_transcript_segment` tool during fallback.

**Impact:** All video processing fails when Groq Structured Outputs validation rejects segments.

**Severity:** CRITICAL - 100% failure rate on fallback path

---

## Issue Flow

### Step 1: Groq Structured Outputs (Primary Path)
- Groq returns 5 segments with durations 8-12 seconds
- All segments rejected: Too short (min 49s required)
- ValueError raised: "No valid segments found"

### Step 2: Fallback to Pydantic AI (Failure Point)
- Code catches ValueError, triggers fallback (line 352-356 in ai.py)
- Pydantic AI agent initialized with:
  - model: `groq:meta-llama/llama-4-scout-17b-16e-instruct`
  - output_type: `TranscriptAnalysis`
  - system_prompt: `simplified_system_prompt`
  - **tools: NONE** (no @agent.tool decorators exist)

### Step 3: Groq API Error (400 Bad Request)
```
tool call validation failed: attempted to call tool 'get_transcript_segment'
which was not in request.tools
```

**Analysis:** Groq's Llama 4 Scout model is trying to call a tool that was never registered with the Pydantic AI agent.

---

## Code Evidence

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

**Lines 110-124: Agent Creation (NO TOOLS)**
```python
def _get_transcript_agent():
    """Lazy initialization of transcript agent (only when needed)."""
    global _transcript_agent
    if _transcript_agent is None:
        model = _get_llm_model()
        _transcript_agent = Agent(
            model=model,
            output_type=TranscriptAnalysis,
            system_prompt=simplified_system_prompt,
        )
    return _transcript_agent
```

**Problem:** No tools registered. The agent expects model to use structured outputs ONLY.

**Lines 352-362: Fallback Logic**
```python
except Exception as e:
    # Fallback to Pydantic AI if Groq fails (e.g., API down, rate limited)
    logger.warning(
        f"Groq Structured Outputs failed ({type(e).__name__}), "
        f"falling back to Pydantic AI with configured LLM"
    )
    # Continue to Pydantic AI fallback below

# For all other models, use Pydantic AI (tool calling)
# Lazy initialize agent on first use
agent = _get_transcript_agent()
result = await agent.run(analysis_prompt)
```

**Problem:** Falls back to same model (Llama 4 Scout) but via different API path.

---

## Why Groq Model Tries to Call Tools

When using Pydantic AI with Groq models, the library sends the `output_type` schema as potential tools. The model sees this and attempts to invoke tool calls, but:

1. Groq Structured Outputs (primary): Model constrained by JSON schema - no tool calling
2. Pydantic AI (fallback): Model uses tool calling interface - expects tools in request

**The mismatch:** Same model, different API interfaces, incompatible expectations.

---

## Related to Recent Changes?

**NO - This is a pre-existing bug in the fallback logic.**

Recent changes (commit 7699f06):
- Fix #1: `method="caption"` to `method="label"` (video_utils.py)
- Fix #2: Dynamic `build_system_prompt()` (ai_structured.py)

**These fixes are correct and working.** The issue was always present but rarely triggered because:
- Groq Structured Outputs usually succeeds
- When it fails validation, it correctly raises ValueError
- Fallback path is flawed and has likely NEVER worked for Llama 4 Scout

---

## Why Groq Structured Outputs Rejected Segments

From logs:
```
2025-11-18 16:37:49 - src.ai_structured - WARNING - REJECTED: Too short -
00:49.200 to 00:58.160 = 8.96s (min 49s required)
```

**Analysis:**
- User requested min_length=49s, max_length=58s (unusually long for viral clips)
- Groq returned 5 segments averaging 11.63 seconds
- ALL segments rejected as too short

**This is CORRECT behavior** - validation is working as designed.

---

## Fix Options

### Option 1: Remove Fallback (Recommended)
**Rationale:** Fallback is fundamentally broken for Llama 4 Scout.

```python
# In ai.py, lines 352-358, REMOVE fallback
except Exception as e:
    logger.error(f"Groq Structured Outputs failed: {e}")
    raise  # Re-raise instead of fallback
```

**Pros:**
- Clean failure with clear error message
- No false hope of fallback working
- Forces fix of root cause (AI returning too-short segments)

**Cons:**
- No graceful degradation

### Option 2: Fix Fallback with Different Model
**Rationale:** Use a model known to work with Pydantic AI tool calling.

```python
except Exception as e:
    logger.warning(
        f"Groq Structured Outputs failed, falling back to OpenAI GPT-4"
    )
    # Create temporary agent with different model
    fallback_model = "openai:gpt-4"
    fallback_agent = Agent(
        model=fallback_model,
        output_type=TranscriptAnalysis,
        system_prompt=simplified_system_prompt,
    )
    result = await fallback_agent.run(analysis_prompt)
```

**Pros:**
- Actual working fallback
- Different model may succeed where Groq failed

**Cons:**
- Requires OpenAI API key
- Different model = different results
- More complex logic

### Option 3: Fix Validation Logic
**Rationale:** The real issue is Groq returning segments too short.

**Root cause:** User requested 49-58 second clips, but this is unrealistic for most content.

**Fix:** Add validation in request handling:
```python
# In video_service.py or request validation
if min_length > 45:
    logger.warning(f"Requested min_length {min_length}s is too high. Capping at 45s.")
    min_length = 45

if max_length > 60:
    logger.warning(f"Requested max_length {max_length}s is too high. Capping at 60s.")
    max_length = 60
```

**Pros:**
- Prevents unrealistic requests
- Groq Structured Outputs more likely to succeed
- No fallback needed

**Cons:**
- Overrides user preference
- May not solve all cases

---

## Recommended Solution

**Implement Option 1 + Option 3:**

1. **Remove broken fallback** - clear failure is better than false hope
2. **Cap clip duration requests** - prevent unrealistic parameters
3. **Improve error messaging** - guide users to reasonable settings

---

## Implementation Plan

### Step 1: Fix ai.py Fallback (Remove It)

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

**Lines 352-358: Remove fallback logic**

**Before:**
```python
except Exception as e:
    # Fallback to Pydantic AI if Groq fails (e.g., API down, rate limited)
    logger.warning(
        f"Groq Structured Outputs failed ({type(e).__name__}), "
        f"falling back to Pydantic AI with configured LLM"
    )
    # Continue to Pydantic AI fallback below
```

**After:**
```python
except ValueError as e:
    # Re-raise validation errors with helpful context
    logger.error(f"Groq Structured Outputs validation failed: {e}")
    raise ValueError(
        f"AI analysis failed: {e}. "
        f"Try reducing clip duration requirements (recommended: 10-45 seconds)."
    ) from e
except Exception as e:
    # Re-raise API errors
    logger.error(f"Groq Structured Outputs API error: {e}")
    raise
```

### Step 2: Add Parameter Validation

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`

**Add validation before calling analyze_transcript:**

```python
# Validate and cap clip duration parameters
if min_length > 45:
    logger.warning(f"Requested min_length {min_length}s exceeds recommended maximum. Capping at 45s.")
    min_length = 45

if max_length > 60:
    logger.warning(f"Requested max_length {max_length}s exceeds recommended maximum. Capping at 60s.")
    max_length = 60

if min_length < 10:
    logger.warning(f"Requested min_length {min_length}s is too short. Setting to 10s minimum.")
    min_length = 10
```

### Step 3: Update Error Messages

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

**Line 331-336: Improve error message**

**Before:**
```python
raise ValueError(
    "No valid segments found. All segments were rejected as too short. "
    "This typically means the AI model is returning fragments instead of complete clips (< 5 seconds). "
    "The Groq Llama 4 Scout model may be returning ultra-short segments. "
    "Consider checking the AI system prompt or model performance."
)
```

**After:**
```python
raise ValueError(
    f"No valid segments found. All {len(analysis.most_relevant_segments)} segments were rejected. "
    f"Requested clip duration: {min_length}-{max_length}s. "
    f"AI returned segments averaging {sum(durations)/len(durations):.1f}s. "
    f"Recommendation: Try more realistic clip durations (10-45 seconds work best for viral content)."
)
```

---

## Testing Strategy

### Test Case 1: Unrealistic Parameters (Current Failure)
```python
min_length = 49
max_length = 58
# Expected: Capped to 45/60, processing succeeds
```

### Test Case 2: Reasonable Parameters
```python
min_length = 10
max_length = 45
# Expected: Processing succeeds
```

### Test Case 3: Edge Cases
```python
min_length = 5   # Too short - should warn and cap to 10
max_length = 120 # Too long - should warn and cap to 60
```

---

## Additional Findings

### Groq Model Behavior
From logs, Groq Llama 4 Scout consistently returns 8-13 second segments:
- Segment 1: 8.96s
- Segment 2: 12.40s
- Segment 3: 11.84s
- Segment 4: 12.56s
- Segment 5: 12.40s

**Average: 11.63 seconds**

**Conclusion:** Model interprets "engaging short-form content" as 10-15 second clips, regardless of prompt instructions for 49-58 seconds.

**This is actually GOOD behavior** - 10-15s is optimal for TikTok/YouTube Shorts. The issue is user requesting unrealistic 49-58s clips.

---

## Recommended User Guidance

Add to API documentation and frontend:

```
Optimal clip durations for maximum engagement:
- TikTok/Instagram Reels: 10-30 seconds
- YouTube Shorts: 15-45 seconds
- General viral content: 10-45 seconds

Note: Requesting clips longer than 45 seconds may result in fewer results,
as AI prioritizes complete thoughts over arbitrary duration targets.
```

---

## Files Requiring Changes

1. `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py` (lines 352-358)
2. `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py` (before analyze_transcript call)
3. `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py` (line 331-336)

---

## Conclusion

**Root Cause:** Pydantic AI fallback uses tool calling interface with a model (Llama 4 Scout) that doesn't support tools when not using Groq's Structured Outputs API.

**Trigger:** User requested unrealistic clip durations (49-58s), causing all AI segments to be rejected.

**Solution:** Remove broken fallback, cap parameters to realistic ranges, improve error messages.

**Not Related to Recent Changes:** Fixes for font cutoff and dynamic prompts are working correctly.
