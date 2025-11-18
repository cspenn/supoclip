# Fix Implementation Plan: Font Cutoff and Short Clips
Date: 2025-11-18

## Overview

This document provides exact implementation steps with line numbers for fixing:
1. **Font Cutoff Issue**: Text vertically cropped in captions
2. **Short Clips Issue**: AI ignoring user's min/max clip length settings

## Pre-Implementation Checklist

- [ ] Create git checkpoint: `git add -A && git commit -m "CHECKPOINT: Before fixing font cutoff and short clips issues"`
- [ ] Run baseline tests: `cd backend && pytest tests/test_font_cutoff_and_short_clips.py -v`
- [ ] Verify tests FAIL (proving bugs exist)
- [ ] Review root cause analysis document

---

## Fix #1: Font Cutoff Issue

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py`

### Change 1.1: TextClip method parameter (Line 913)

**Current Code (Line 906-920):**
```python
text_clip = TextClip(
    text=text,
    font=font_path,
    font_size=current_font_size,
    color=font_color,
    stroke_color="black",
    stroke_width=1,
    method="caption",  # ← LINE 913: CHANGE THIS
    size=(max_text_width, None),  # ← LINE 914: REMOVE THIS
    text_align="center",
)
```

**Fixed Code:**
```python
text_clip = TextClip(
    text=text,
    font=font_path,
    font_size=current_font_size,
    color=font_color,
    stroke_color="black",
    stroke_width=1,
    method="label",  # ← CHANGED from "caption"
    # size parameter removed - not needed for label mode
    text_align="center",
)
```

### Exact Changes:
1. **Line 913**: Change `method="caption"` to `method="label"`
2. **Line 914**: Remove or comment out `size=(max_text_width, None),`

### Why This Fixes It:
- `method="caption"` renders text in a fixed bounding box and crops overflow
- `method="label"` auto-sizes the text clip to fit all content
- Removing `size` parameter lets MoviePy calculate proper dimensions

### Testing:
```bash
cd backend
pytest tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue -v
```
Expected: Tests should PASS after fix

---

## Fix #2: Short Clips Issue (Part A - Dynamic System Prompt)

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

### Change 2.1: Convert SYSTEM_PROMPT to function (Lines 50-97)

**Current Code (Line 50):**
```python
SYSTEM_PROMPT = """You are an expert video clip curator...
DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: 10 seconds per segment (DO NOT return segments shorter than 10 seconds)
- MAXIMUM DURATION: 45 seconds per segment
..."""
```

**Fixed Code:**
```python
def build_system_prompt(min_length: int = 10, max_length: int = 45) -> str:
    """
    Build dynamic system prompt with configurable duration constraints.

    Args:
        min_length: Minimum clip duration in seconds
        max_length: Maximum clip duration in seconds

    Returns:
        System prompt string with duration requirements
    """
    return f"""You are an expert video clip curator for creating engaging short-form content.
Your task is to analyze video transcripts and identify the most compelling segments.

CRITICAL SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines (complete sentences)
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories (full explanation)
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration (complete reaction)
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone (NOT partial)
5. ENTERTAINING: Content people would want to watch (FULL CLIPS, NOT FRAGMENTS)

DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
- MINIMUM DURATION: {min_length} seconds per segment (DO NOT return segments shorter than {min_length} seconds)
- MAXIMUM DURATION: {max_length} seconds per segment (DO NOT return segments longer than {max_length} seconds)
- Duration calculation: end_time - start_time MUST be >= {min_length} seconds
- NEVER return ultra-short clips (clips shorter than {min_length} seconds are INVALID)
- If a segment is less than {min_length} seconds, DO NOT include it in your response
- If a segment is more than {max_length} seconds, DO NOT include it in your response
- Return COMPLETE CLIPS, not word fragments or sentence fragments

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: {min_length} seconds (end_time - start_time >= {min_length} seconds)
- MAXIMUM segment duration: {max_length} seconds (end_time - start_time <= {max_length} seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- VERIFY DURATION BEFORE RETURNING: Calculate (end_time - start_time) and ensure it's >= {min_length} and <= {max_length}
- Example CORRECT (for {min_length}s min): start_time: "02:25", end_time: "02:35" (10 second duration)
- Example INCORRECT: start_time: "02:25", end_time: "02:26" (1 second - TOO SHORT)
- Example INCORRECT: start_time: "02:25", end_time: "02:25" (0 seconds - INVALID)

OUTPUT FORMAT:
Return a JSON object with this exact structure:
{{
  "most_relevant_segments": [
    {{
      "start_time": "MM:SS",
      "end_time": "MM:SS",
      "text": "segment text (must be substantial and complete)",
      "relevance_score": 0.85,
      "reasoning": "why this is relevant (be specific)"
    }}
  ],
  "summary": "brief summary",
  "key_topics": ["topic1", "topic2"]
}}

QUALITY REQUIREMENTS:
- Find 3-7 compelling segments that would work well as standalone clips
- Each segment MUST be at least {min_length} seconds long
- Each segment MUST NOT exceed {max_length} seconds
- Quality over quantity - choose segments that would genuinely engage viewers
- Include enough text and context that the segment makes sense without external info
- Only return segments that are COMPLETE THOUGHTS or COMPLETE SCENES, never fragments"""
```

### Change 2.2: Update function call (Line 177)

**Current Code (Line 174-178):**
```python
completion = await client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},  # ← LINE 177: CHANGE THIS
        {"role": "user", "content": user_prompt},
    ],
```

**Fixed Code:**
```python
completion = await client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": build_system_prompt(min_length, max_length)},  # ← CHANGED
        {"role": "user", "content": user_prompt},
    ],
```

### Exact Changes:
1. **Lines 50-97**: Replace `SYSTEM_PROMPT = """..."""` with `def build_system_prompt(min_length: int = 10, max_length: int = 45) -> str:`
2. **Line 177**: Change `SYSTEM_PROMPT` to `build_system_prompt(min_length, max_length)`

---

## Fix #2: Short Clips Issue (Part B - Validation)

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

### Change 2.3: Dynamic minimum validation (Line 274)

**Current Code (Lines 274-279):**
```python
if duration < 10:  # ← LINE 274: HARDCODED 10
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min 10s required). Text: '{segment.text[:40]}...'"  # ← LINE 277: HARDCODED
    )
    continue
```

**Fixed Code:**
```python
if duration < min_length:  # ← CHANGED from hardcoded 10
    logger.warning(
        f"REJECTED: Too short - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(min {min_length}s required). Text: '{segment.text[:40]}...'"  # ← CHANGED
    )
    continue
```

### Change 2.4: Add maximum validation (NEW - After Line 279)

**Add After Line 279:**
```python
# Validate maximum duration
if duration > max_length:
    logger.warning(
        f"REJECTED: Too long - {segment.start_time} to {segment.end_time} = {duration:.2f}s "
        f"(max {max_length}s allowed). Text: '{segment.text[:40]}...'"
    )
    continue
```

### Exact Changes:
1. **Line 274**: Change `if duration < 10:` to `if duration < min_length:`
2. **Line 277**: Change `"(min 10s required)"` to `f"(min {min_length}s required)"`
3. **After Line 279**: Add max_length validation (6 lines of code)

---

## Fix #2: Short Clips Issue (Part C - Update User Prompt)

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py`

### Change 2.5: Enhance user prompt (Line 160)

**Current Code (Line 158-161):**
```python
user_prompt_parts = [
    "Analyze this video transcript and identify the most engaging segments for short-form content.",
    f"Segments MUST be between {min_length}-{max_length} seconds for optimal engagement.",
]
```

**Fixed Code:**
```python
user_prompt_parts = [
    "Analyze this video transcript and identify the most engaging segments for short-form content.",
    f"CRITICAL REQUIREMENT: Segments MUST be between {min_length}-{max_length} seconds.",
    f"DO NOT return segments shorter than {min_length} seconds or longer than {max_length} seconds.",
    f"Verify each segment duration: (end_time - start_time) should be >= {min_length}s and <= {max_length}s.",
]
```

### Exact Changes:
1. **Lines 159-161**: Expand to 4 lines with stronger emphasis on duration requirements

---

## Fix #3: Additional Validation in ai.py (Optional but Recommended)

### File: `/Users/cspenn/Documents/github/supoclip/backend/src/ai.py`

### Change 3.1: Make MIN_DURATION_SECONDS configurable (Line 167)

**Current Code (Line 164-168):**
```python
class TimestampParser:
    """Parses and validates transcript timestamps."""

    MIN_DURATION_SECONDS = 5  # ← HARDCODED
```

**Consideration:**
- This is an absolute minimum (5s) to prevent fragments
- User's min_length should be >= 5s
- Could make this configurable or add assertion: `assert min_length >= 5`

**Recommended: Add assertion in analyze_transcript_structured:**
```python
# At start of analyze_transcript_structured function (after line 126)
if min_length < 5:
    logger.warning(
        f"min_length={min_length}s is below absolute minimum (5s). "
        f"Adjusting to 5s to prevent fragment clips."
    )
    min_length = 5
```

---

## Testing Plan

### Step 1: Run failing tests (before fixes)
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
pytest tests/test_font_cutoff_and_short_clips.py -v

# Expected: All tests FAIL (proving bugs exist)
```

### Step 2: Apply Fix #1 (Font Cutoff)
```bash
# Edit video_utils.py lines 913-914 as specified above
```

### Step 3: Test Fix #1
```bash
pytest tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue -v

# Expected: Font cutoff tests now PASS
```

### Step 4: Apply Fix #2 (Short Clips)
```bash
# Edit ai_structured.py as specified above:
# - Lines 50-97: Convert SYSTEM_PROMPT to function
# - Line 177: Update function call
# - Lines 274-279: Update validation
# - Lines 158-161: Enhance user prompt
```

### Step 5: Test Fix #2
```bash
# Note: Requires GROQ_API_KEY environment variable
export GROQ_API_KEY="your-key-here"

pytest tests/test_font_cutoff_and_short_clips.py::TestShortClipsIssue -v

# Expected: Short clips tests now PASS
```

### Step 6: Integration test
```bash
pytest tests/test_font_cutoff_and_short_clips.py::TestActualUserScenario -v

# Expected: Full user scenario test PASSES
```

### Step 7: Run full test suite
```bash
cd backend
./checkpython.sh

# Expected: All tests pass, no regressions
```

---

## Verification Checklist

### Manual Testing
- [ ] Process a video with font "Barlow Condensed Bold" at 30px
- [ ] Verify captions are NOT cut off (full text visible)
- [ ] Set clip length to 47-58 seconds via frontend sliders
- [ ] Verify generated clips are 47-58 seconds (not 10-20s)
- [ ] Test with various fonts (Arial, TikTok Sans, Impact)
- [ ] Test with various clip lengths (10-20s, 30-40s, 50-60s)

### Code Quality
- [ ] No hardcoded duration values in SYSTEM_PROMPT
- [ ] No hardcoded duration values in validation code
- [ ] All parameters flow through correctly
- [ ] Logging shows actual min_length/max_length used
- [ ] No type errors (mypy passes)
- [ ] No lint errors (ruff passes)

---

## Implementation Order

1. **Fix #1 first** (Font Cutoff) - Simpler, isolated change
   - Estimated time: 5 minutes
   - Risk: Low (only affects TextClip rendering)

2. **Fix #2 second** (Short Clips) - More complex, affects AI
   - Estimated time: 20 minutes
   - Risk: Medium (changes prompt structure)

3. **Test both fixes together** - Ensure no interactions
   - Estimated time: 15 minutes

4. **User validation** - Real video processing test
   - Estimated time: 10 minutes

**Total estimated time: 50 minutes**

---

## Rollback Plan

If fixes cause regressions:

```bash
# Rollback to checkpoint
git reset --hard HEAD~1

# Or rollback specific file
git checkout HEAD~1 -- backend/src/video_utils.py
git checkout HEAD~1 -- backend/src/ai_structured.py
```

---

## Success Criteria

### Fix #1 Success:
- [ ] TextClip uses `method="label"`
- [ ] No `size` parameter constraining height
- [ ] Captions fully visible in generated clips
- [ ] Text positioning still correct (75% down video)

### Fix #2 Success:
- [ ] SYSTEM_PROMPT is a function accepting min_length/max_length
- [ ] Validation uses dynamic min_length/max_length (not hardcoded)
- [ ] AI generates clips within requested duration range
- [ ] Logs show: "Clip length settings - Min: 47s, Max: 58s"
- [ ] Logs show: "Groq response duration analysis: avg=52s, min=47s, max=58s"
- [ ] Generated clips match requested duration (±5s tolerance)

---

## Known Edge Cases

### Font Cutoff:
- Very long words might still overflow horizontally (separate issue)
- Emoji fonts may render differently (test separately)
- Font files must exist in backend/fonts/ directory

### Short Clips:
- If transcript doesn't have segments >= min_length, task will fail (expected)
- Groq API rate limits may cause test failures (use skip/retry)
- Custom prompts might still affect duration selection (user responsibility)

---

## Post-Implementation Tasks

1. Update documentation:
   - Document `build_system_prompt()` function
   - Update API docs with clip length parameter behavior

2. Monitor production:
   - Watch logs for "REJECTED: Too short" warnings
   - Check average clip durations in database
   - Gather user feedback on clip lengths

3. Future improvements:
   - Add clip length presets (Short: 10-20s, Medium: 30-45s, Long: 50-60s)
   - Show AI-selected duration in frontend before generation
   - Add "regenerate with different length" option

---

## File Change Summary

| File | Lines Changed | Type of Change |
|------|--------------|----------------|
| `backend/src/video_utils.py` | 913-914 | Modify (2 lines) |
| `backend/src/ai_structured.py` | 50-97 | Replace with function (47 lines) |
| `backend/src/ai_structured.py` | 177 | Modify (1 line) |
| `backend/src/ai_structured.py` | 274-279 | Modify (3 lines) |
| `backend/src/ai_structured.py` | After 279 | Add (6 lines) |
| `backend/src/ai_structured.py` | 158-161 | Modify (4 lines) |
| **Total** | **~63 lines changed** | **2 files modified** |

---

## Git Commit Strategy

### Commit 1: Font cutoff fix
```bash
git add backend/src/video_utils.py
git commit -m "Fix font cutoff: Change TextClip method from caption to label

- Change method='caption' to method='label' in video_utils.py line 913
- Remove size parameter that was constraining text height
- Fixes issue where captions were vertically cropped
- Tests: pytest tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue

Resolves: Font cutoff issue (text cut in half)"
```

### Commit 2: Short clips fix
```bash
git add backend/src/ai_structured.py backend/tests/test_font_cutoff_and_short_clips.py
git commit -m "Fix short clips: Make AI duration constraints dynamic

- Convert SYSTEM_PROMPT to build_system_prompt() function with min/max params
- Update validation to use dynamic min_length instead of hardcoded 10
- Add max_length validation that was missing
- Enhance user prompt to emphasize duration requirements
- Tests: pytest tests/test_font_cutoff_and_short_clips.py::TestShortClipsIssue

Resolves: AI ignoring user's clip length settings (47-58s → 11s clips)

Before: AI used hardcoded 10-45s durations regardless of user settings
After: AI respects user's min_length and max_length parameters"
```

### Commit 3: Post-fix verification
```bash
git add -A
git commit -m "Verify fixes: All tests passing, user scenario validated

- Font cutoff tests: PASS
- Short clips tests: PASS
- Integration tests: PASS
- Manual testing: Verified with actual video processing
- checkpython.sh: Zero errors

Both issues resolved successfully."
```

---

## Contact/Escalation

If fixes don't work as expected:
1. Check logs for parameter flow: `grep "Clip length settings" backend/logs/*.log`
2. Verify Groq API key is set: `echo $GROQ_API_KEY`
3. Test with different LLM model (fallback to Pydantic AI)
4. Review root cause analysis document for alternative hypotheses
