# Exact Code Fixes Needed

## File 1: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

### Problem 1: System Prompt Not Producing Results

**Location:** Lines 54-67

**Current Code:**
```python
TIMING GUIDELINES:
- Segments MUST be between 10-45 seconds for optimal engagement
- CRITICAL: start_time MUST be different from end_time (minimum 10 seconds apart)
- Focus on natural content boundaries rather than arbitrary time limits
- Include enough context for the segment to be understandable

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")
```

**Issue:** The prompt is clear, but Groq is ignoring it and returning 0.5-1.3 second segments.

**What to Do:**
- [ ] Test the prompt against Groq API directly
- [ ] Check if the model (Llama 4 Scout) has limitations
- [ ] Try alternative models (Mixtral, etc.)
- [ ] Consider adding example constraints in the prompt:
  ```
  CRITICAL CONSTRAINTS:
  - Do NOT return segments less than 10 seconds
  - Reject any segment where (end_seconds - start_seconds) < 10
  - If you cannot find 10-45 second segments, return empty list
  ```

---

### Problem 2: No Error When All Segments Filtered

**Location:** Lines 223-231

**Current Code:**
```python
if duration < 5:
    logger.warning(
        f"Skipping segment too short: {duration}s (min 5s required)"
    )
    continue

validated_segments.append(segment)
logger.info(
    f"Validated segment: {segment.start_time}-{segment.end_time} ({duration}s)"
)
```

**Issue:** Logs warnings but no error condition. If all segments are filtered out, the system continues as if everything is normal.

**Fix Required:**
```python
if duration < 5:
    logger.warning(
        f"Skipping segment too short: {duration}s (min 5s required)"
    )
    continue

validated_segments.append(segment)
logger.info(
    f"Validated segment: {segment.start_time}-{segment.end_time} ({duration}s)"
)
```

After the loop (around line 241), add:

```python
# CRITICAL: Check if all segments were filtered out
if len(validated_segments) == 0:
    logger.error(
        "ALL SEGMENTS WERE FILTERED OUT - AI analysis produced invalid output"
    )
    logger.error(
        f"AI returned {len(analysis.most_relevant_segments)} segments, "
        f"but all were rejected as too short. Possible causes: "
        f"(1) Groq model not following prompt, "
        f"(2) Transcript has no 10+ second content, "
        f"(3) Prompt needs improvement"
    )
    # This should result in task error status, not success
```

---

### Problem 3: 0 Segments Treated as Success

**Location:** Line 250

**Current Code:**
```python
logger.info(f"Selected {len(validated_segments)} segments for processing")
if validated_segments:
    logger.info(
        f"Top segment score: {validated_segments[0].relevance_score:.2f}"
    )
```

**Issue:** Logs "Selected 0 segments" as INFO, then continues. Should be ERROR.

**Fix Required:**
```python
logger.info(f"Selected {len(validated_segments)} segments for processing")

if not validated_segments:
    logger.error(
        "CRITICAL: Zero valid segments found after filtering. "
        "This will result in zero clips being generated."
    )
    raise ValueError(
        "No valid segments found - all AI-identified segments were "
        "too short (<5 seconds). Check AI model output or transcript quality."
    )

if validated_segments:
    logger.info(
        f"Top segment score: {validated_segments[0].relevance_score:.2f}"
    )
```

---

## File 2: `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`

**Location:** Where AI analysis result is handled (need to find exact line)

**Issue:** When `ai_analysis.most_relevant_segments` is empty, system continues without error.

**Fix Required:**
Add validation after AI analysis:

```python
if not ai_result.most_relevant_segments or len(ai_result.most_relevant_segments) == 0:
    logger.error(
        f"Task {task_id}: AI analysis found no valid segments. "
        f"Will generate 0 clips."
    )
    # Consider: Should this be task error status? Or is 0 clips acceptable?
    # At minimum, user should see an error message, not "completed successfully"
```

---

## File 3: `/Users/cspenn/Documents/github/supoclip/backend/src/repositories/task_repository.py`

**Location:** Where task status is updated to "completed"

**Issue:** Task marked as "completed" even when 0 clips were generated.

**Fix Required:**
Add check before updating status:

```python
# When updating task status to completed
if num_clips == 0:
    # Mark as error or warning, not success
    logger.error(f"Task {task_id}: Completed with 0 clips - marking as error")
    await update_task_status(task_id, "error")
    await update_task_error_message(task_id, "No valid clips generated by AI")
else:
    await update_task_status(task_id, "completed")
```

---

## Testing: New Tests to Add

### File: `backend/tests/test_ai_segment_validation.py`

**Test 1: Verify Groq Output Quality**
```python
def test_ai_produces_valid_segment_durations():
    """
    CRITICAL: AI must produce segments with 10-45 second durations.
    This test will fail with current Groq configuration.
    """
    # Test with real Groq API or mock with realistic response
    # Verify: all segments have duration >= 10 seconds
    # Current status: FAILING (durations are 0.5-1.3 seconds)
```

**Test 2: Handling Invalid Segment Sizes**
```python
def test_zero_valid_segments_raises_error():
    """
    If all AI segments are filtered out as invalid,
    system should raise error, not complete silently.
    """
    # Mock AI response with all short segments
    # Verify: system raises ValueError or similar
    # Current status: FAILING (system completes without error)
```

**Test 3: Zero Clips Result**
```python
def test_zero_clips_generation_handled_properly():
    """
    If no valid segments exist after filtering,
    task should be marked with error status, not "completed".
    """
    # Verify: task.status == "error" or "warning"
    # Verify: task.error_message contains explanation
    # Current status: FAILING (task marked "completed")
```

---

## Summary of Required Changes

### Critical (Must Fix For Videos to Work)
1. **Diagnose Groq Output Issue** - Why returns <2s segments?
2. **Add Error on Zero Segments** - In ai_structured.py line ~250
3. **Raise Exception** - When all segments filtered out
4. **Mark Task as Error** - When 0 clips result

### High Priority (User Experience)
5. **Add Error Message** - What went wrong and why
6. **Log Error Level** - Not just warning
7. **Update Task Status** - To "error" not "completed"

### Medium Priority (Testing)
8. **Integration Test** - With real Groq API response
9. **Test Zero Segments Case** - Verify error handling
10. **End-to-End Test** - Complete workflow with valid and invalid outputs

---

## Files That Need Review/Changes

```
/Users/cspenn/Documents/github/supoclip/backend/src/
  ├── ai_structured.py              [CRITICAL - lines 54, 224, 250]
  ├── services/video_service.py      [HIGH - AI result handling]
  ├── repositories/task_repository.py [HIGH - status update]
  └── main.py                        [CHECK - task completion logic]
```

---

## Verification Checklist

After making fixes:
- [ ] Run full video processing with real YouTube URL
- [ ] Verify AI returns 10-45 second segments
- [ ] Verify if segments < 5s rejected, system shows ERROR
- [ ] Verify if 0 valid segments, task marked as error
- [ ] Verify user sees error message, not silent failure
- [ ] Run integration tests
- [ ] Check logs for error messages (not just warnings)

