# Code Fix: Pydantic AI Fallback Failure
Date: 2025-11-18

## Quick Summary

**Problem:** Pydantic AI fallback fails because Llama 4 Scout tries to call tools that don't exist.

**Root Cause:** Agent has no tools registered, but model attempts tool calling.

**Solution:** Remove broken fallback + add parameter validation.

---

## Fix #1: Remove Broken Fallback in ai.py

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

**Location:** Lines 352-362

**Current Code (BROKEN):**
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

**Fixed Code:**
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

    # For all other models, use Pydantic AI (tool calling)
    # Lazy initialize agent on first use
    agent = _get_transcript_agent()
    result = await agent.run(analysis_prompt)
```

**Why:**
- Removes fallback that never worked
- Provides clear error message
- Guides user to fix (reduce clip duration)

---

## Fix #2: Add Parameter Validation in video_service.py

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`

**Location:** In `analyze_transcript` method, before calling `get_most_relevant_parts_by_transcript`

**Add this code:**
```python
    @staticmethod
    async def analyze_transcript(
        transcript: str,
        min_length: int = 10,
        max_length: int = 45,
        custom_prompt: str | None = None,
    ) -> list[dict]:
        """
        Analyze transcript with AI to identify viral segments.

        Args:
            transcript: Full video transcript
            min_length: Minimum clip duration in seconds
            max_length: Maximum clip duration in seconds
            custom_prompt: Optional custom AI prompt

        Returns:
            List of segment dictionaries with timing and metadata
        """
        logger.info("Starting AI analysis of transcript")

        # NEW: Validate and cap clip duration parameters
        original_min = min_length
        original_max = max_length

        if min_length < 10:
            logger.warning(
                f"Requested min_length {min_length}s is too short. "
                f"Setting to 10s minimum for coherent clips."
            )
            min_length = 10

        if min_length > 45:
            logger.warning(
                f"Requested min_length {min_length}s exceeds recommended maximum. "
                f"Capping at 45s for better AI performance."
            )
            min_length = 45

        if max_length > 60:
            logger.warning(
                f"Requested max_length {max_length}s exceeds recommended maximum. "
                f"Capping at 60s for optimal viral content."
            )
            max_length = 60

        if max_length < min_length:
            logger.warning(
                f"max_length {max_length}s is less than min_length {min_length}s. "
                f"Adjusting max_length to {min_length + 10}s."
            )
            max_length = min_length + 10

        if original_min != min_length or original_max != max_length:
            logger.info(
                f"Clip duration adjusted: {original_min}-{original_max}s -> {min_length}-{max_length}s"
            )

        # Continue with existing code...
        relevant_parts = await get_most_relevant_parts_by_transcript(
            transcript=transcript,
            min_length=min_length,
            max_length=max_length,
            custom_prompt=custom_prompt,
        )
```

**Why:**
- Prevents unrealistic user requests
- Caps parameters to proven working ranges
- Logs adjustments for transparency
- Reduces likelihood of AI validation failures

---

## Fix #3: Improve Error Message in ai_structured.py

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

**Location:** Lines 318-336

**Current Code:**
```python
        # CRITICAL: Raise error if no segments passed validation (Fix 1)
        # This prevents silent failures where task completes with 0 clips
        if not validated_segments:
            logger.error(
                "ERROR: All AI-identified segments were rejected during validation"
            )
            logger.error(
                f"Original segments from AI: {len(analysis.most_relevant_segments)}"
            )
            logger.error(
                "Possible causes: Groq returned ultra-short segments, "
                "invalid timestamps, or insufficient content"
            )
            raise ValueError(
                "No valid segments found. All segments were rejected as too short. "
                "This typically means the AI model is returning fragments instead of complete clips (< 5 seconds). "
                "The Groq Llama 4 Scout model may be returning ultra-short segments. "
                "Consider checking the AI system prompt or model performance."
            )
```

**Fixed Code:**
```python
        # CRITICAL: Raise error if no segments passed validation (Fix 1)
        # This prevents silent failures where task completes with 0 clips
        if not validated_segments:
            logger.error(
                "ERROR: All AI-identified segments were rejected during validation"
            )
            logger.error(
                f"Original segments from AI: {len(analysis.most_relevant_segments)}"
            )

            # Calculate average duration for diagnostic
            avg_duration = "N/A"
            if durations:
                avg_duration = f"{sum(durations)/len(durations):.1f}s"

            logger.error(
                f"Requested clip duration: {min_length}-{max_length}s. "
                f"AI returned segments averaging {avg_duration}."
            )
            logger.error(
                "Possible causes: Clip duration too high, "
                "insufficient content length, or AI model limitations"
            )

            raise ValueError(
                f"No valid segments found. All {len(analysis.most_relevant_segments)} segments were rejected. "
                f"Requested: {min_length}-{max_length}s. AI returned average: {avg_duration}. "
                f"Recommendation: Try shorter clip durations (10-45 seconds work best for viral content). "
                f"Most engaging short-form content is 15-30 seconds."
            )
```

**Why:**
- Provides specific diagnostic info (requested vs. actual durations)
- Clear recommendation for user (reduce clip duration)
- Explains why failure occurred (mismatch in expectations)

---

## Testing Commands

After applying fixes:

```bash
# 1. Apply fixes to the three files above

# 2. Run backend tests
cd /Users/cspenn/Documents/github/supoclip/backend
pytest tests/ -v

# 3. Test with realistic parameters (should succeed)
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=5lN8I4PqLkc"},
    "min_clip_length": 15,
    "max_clip_length": 30
  }'

# 4. Test with unrealistic parameters (should cap and succeed)
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=5lN8I4PqLkc"},
    "min_clip_length": 49,
    "max_clip_length": 58
  }'
# Expected: Logs show capping to 45/60, processing succeeds

# 5. Check logs for parameter adjustment warnings
tail -50 logs/backend-*.log | grep "adjusted"
```

---

## Expected Behavior After Fix

### Scenario 1: User requests 49-58s clips
**Before:** All segments rejected, fallback fails with tool error, processing fails
**After:** Parameters capped to 45-60s, warning logged, processing succeeds

### Scenario 2: User requests 10-45s clips
**Before:** Processing succeeds (no change)
**After:** Processing succeeds (no change)

### Scenario 3: Groq returns short segments with capped params
**Before:** Validation fails, fallback fails with tool error
**After:** Validation fails, clear error message guides user to reduce durations further

---

## Files Modified

1. `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py` - Remove fallback
2. `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py` - Add validation
3. `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py` - Improve errors

---

## Rollback Plan

If fixes cause issues:

```bash
git checkout HEAD -- src/ai.py src/services/video_service.py src/ai_structured.py
```

Or revert specific fix:
```bash
# Revert just the fallback removal
git show HEAD:src/ai.py > src/ai.py
```
