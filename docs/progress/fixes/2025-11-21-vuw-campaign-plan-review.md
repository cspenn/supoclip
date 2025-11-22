# VUW Campaign Plan Review Report
**Date:** 2025-11-21
**Reviewer:** Claude Code (Automated Analysis)
**Plan Under Review:** `/docs/progress/fixes/2025-11-21-vuw-campaign-plan.md`

---

## Executive Summary

The VUW Campaign Plan contains several **critical accuracy issues** that will cause the proposed fixes to fail or be ineffective. The most significant finding is that **Campaign 1 (Caption-Video Sync)** is based on an incorrect root cause analysis - the transcript IS already formatted with millisecond precision for AI, but the AI models (TranscriptSegment) are documented as expecting MM:SS format. Additionally, several line numbers are incorrect, and some fixes have already been partially implemented in previous commits.

**Overall Assessment:** REQUIRES REVISION before execution.

---

## 1. REGRESSION ANALYSIS

### 1.1 Previous Fix Attempts Found

| Date | Fix | Outcome | Relevance |
|------|-----|---------|-----------|
| 2025-11-19 | Caption margin fix (3px -> 12px) | SUPERSEDED | Commit `3fcf8a7` increased to 12px, then `c8a093b` changed to dynamic 35% |
| 2025-11-19 | Logo pipeline parameter threading | PARTIAL | Commits `9c41b3f` fixed parameter passing, but path resolution issue persists |
| 2025-11-18 | Segment expansion for short clips | IMPLEMENTED | `ai_structured.py` already has `expand_segment_to_duration()` function |
| 2025-11-17 | Caption word reconstruction | IMPLEMENTED | Cache version 2 with LLM reconstruction enabled by default |

### 1.2 Patterns of Unsuccessful Fixes

1. **Caption Margin Issue:** Fixed multiple times with different approaches:
   - Original: 3px margin
   - First fix: 12px fixed margin
   - Current: `max(5, int(current_font_size * 0.35))` (35% dynamic)
   - **Pattern:** Each fix was incrementally better but the 35% multiplier may still be insufficient for deep descenders.

2. **Logo Path Issue:** The 2025-11-19 fix addressed authentication header mismatch (`user_id` vs `user-id`), but the **path resolution** issue identified in the VUW plan is a SEPARATE unresolved issue.

3. **Timestamp Precision:** No previous explicit fix attempts found - this appears to be a newly identified issue, but the root cause analysis is **incorrect**.

---

## 2. ACCURACY CHECK - LINE NUMBER VERIFICATION

### 2.1 Campaign 1: ai.py TranscriptSegment

**Plan Claims:** Lines 21-22
**Actual Code:**
```python
# Lines 21-22 in ai.py:
start_time: str = Field(description="Start timestamp in MM:SS format")
end_time: str = Field(description="End timestamp in MM:SS format")
```
**Verdict:** CORRECT - Line numbers are accurate.

### 2.2 Campaign 1: ai_structured.py TranscriptSegment

**Plan Claims:** Lines 90-99
**Actual Code:**
```python
# Lines 90-99 in ai_structured.py:
class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing."""

    start_time: str = Field(description="Start timestamp in MM:SS format")
    end_time: str = Field(description="End timestamp in MM:SS format")
    text: str = Field(description="The transcript text for this segment")
    ...
```
**Verdict:** CORRECT - Line numbers are accurate.

### 2.3 Campaign 1: parse_timestamp_to_seconds

**Plan Claims:** Line 826
**Actual Code:** Function starts at line 826
**Verdict:** CORRECT - Line number is accurate.

### 2.4 Campaign 2: Logo Upload Endpoint

**Plan Claims:** Line 480 for `/upload-logo`, line 553 for logo_path
**Actual Code:**
- `/upload-logo` starts at line 480 - CORRECT
- `logo_path = str(logo_path)` at line 553 - INCORRECT (actual is line 553 `logo_path`: str(logo_path), but this stores relative path which IS the issue)
**Verdict:** MOSTLY CORRECT

### 2.5 Campaign 2: user_preferences_service.py get_logo_path

**Plan Claims:** Line 168
**Actual Code:** `get_logo_path` method starts at line 168
**Verdict:** CORRECT - Line number is accurate.

### 2.6 Campaign 3: Caption Margin

**Plan Claims:** Lines 926-932 with 35% margin calculation
**Actual Code:**
```python
# Lines 926-932 (actual lines 925-931):
# Add margin to prevent stroke and descenders from being cut off at edges
# Dynamic bottom margin based on font size: 35% of font size accounts for descenders (20-25%)
# plus stroke (1px) and buffer. This ensures no clipping at any font size (16-40px).
# Examples: 16px->5px, 20px->7px, 24px->8px, 30px->10px, 40px->14px
bottom_margin = max(5, int(current_font_size * 0.35))
text_clip = text_clip.with_effects(
    [Margin(bottom=bottom_margin, top=5, left=3, right=3, opacity=0)]
)
```
**Verdict:** CORRECT - Current code already has dynamic margin with 35% multiplier.

---

## 3. COMPLETENESS CHECK - CRITICAL GAPS

### 3.1 CRITICAL: Transcript Already Has Millisecond Precision

**Discovery:** The `format_transcript_for_ai()` function ALREADY formats timestamps with millisecond precision.

**Evidence from video_utils.py lines 380-381:**
```python
start_time = format_ms_to_timestamp_precise(self.current_start)
end_time = format_ms_to_timestamp_precise(self.current_line[-1][2])
```

**`format_ms_to_timestamp_precise()` output:** `MM:SS.mmm` format (e.g., "02:35.450")

**Impact on Plan:** The root cause analysis for Campaign 1 is **PARTIALLY INCORRECT**. The transcript DOES include milliseconds. The real issue is:
1. The AI models (TranscriptSegment) DESCRIBE the format as "MM:SS" not "MM:SS.mmm"
2. LLMs may ignore milliseconds even when provided if not explicitly instructed
3. The system prompt says "keep MM:SS structure" which contradicts millisecond precision

### 3.2 Missing VUWs for Complete Fix

1. **Missing:** Update `simplified_system_prompt` to NOT say "keep MM:SS structure"
2. **Missing:** Verify LLM actually outputs milliseconds after prompt changes
3. **Missing:** Add validation that AI-returned timestamps include milliseconds
4. **Missing:** Update frontend to handle/display millisecond timestamps

### 3.3 Database Schema Considerations

**No schema changes needed** for timestamps - timestamps are stored as strings in clips table.

**Logo path:** Currently stored as relative path (e.g., `temp/logos/user_logo.png`). Plan correctly addresses this.

### 3.4 Frontend Implications

**Not addressed in plan:**
- Frontend displays clip times - would need to handle MM:SS.mmm format
- Logo upload verification feedback in UI

---

## 4. EFFECTIVENESS ANALYSIS

### 4.1 Campaign 1: Caption-Video Sync - MEDIUM EFFECTIVENESS

**Will the fix work?**
- **Partial:** Updating Field descriptions and prompts MAY encourage LLMs to output milliseconds
- **Uncertain:** LLMs (especially Llama 4 Scout) may still round to seconds
- **Risk:** No validation added to ensure AI actually outputs milliseconds

**Recommended enhancements:**
1. Add regex validation in `TranscriptSegmentValidator` to check for millisecond pattern
2. Add fallback to expand timestamps that lack milliseconds
3. Test with actual LLM outputs before deploying

### 4.2 Campaign 2: Logo Rendering - HIGH EFFECTIVENESS

**Will the fix work?**
- **Yes:** Converting to absolute paths with `.resolve()` will fix the path resolution issue
- **Yes:** Logging additions will aid debugging
- **Risk:** Existing database records have relative paths - needs migration

**Recommended enhancements:**
1. Add data migration script for existing relative paths in database
2. Handle case where logo file was deleted but path remains in DB

### 4.3 Campaign 3: Caption Rendering - MEDIUM EFFECTIVENESS

**Will the fix work?**
- **Maybe:** Increasing from 35% to 50% will help, but 50% may be excessive
- **Good:** Adding stroke width to calculation is mathematically sound
- **Risk:** May create too much whitespace below text

**Recommended enhancements:**
1. Test with specific fonts being used (TikTokSans-Regular)
2. Consider 40-45% instead of 50% to avoid excessive margin

### 4.4 Campaign 4: Transcript Display - LOW EFFECTIVENESS

**Will the fix work?**
- **Unlikely:** LLMs fundamentally summarize/paraphrase - adding "verbatim" instruction rarely works
- **Risk:** AI may still produce slightly different text
- **Root cause misidentified:** The real solution is to reconstruct text from cached word data using timestamps

**Recommended alternative:**
Add post-processing step that:
1. Takes AI segment timestamps
2. Looks up exact words from `.transcript_cache.json` for that time range
3. Replaces AI text with actual cached words

---

## 5. SAFETY CONCERNS

### 5.1 Backward Compatibility

| Change | Risk | Mitigation Needed |
|--------|------|-------------------|
| MM:SS.mmm timestamps | LOW | `parse_timestamp_to_seconds()` already handles both formats |
| Absolute logo paths | MEDIUM | Need migration for existing relative paths |
| Caption margins | LOW | Visual change only, no data migration |
| Verbatim text | LOW | Display-only change |

### 5.2 Breaking Changes to API Contracts

**None identified** - All changes are internal processing improvements.

### 5.3 Test Coverage Gaps

**Identified gaps:**
1. No unit test for `parse_timestamp_to_seconds()` with MM:SS.mmm format
2. No integration test for logo path resolution across working directories
3. No visual regression test for caption margins
4. No test that verifies AI output format matches expected MM:SS.mmm

---

## 6. RISK ASSESSMENT BY CAMPAIGN

### Campaign 1: Caption-Video Sync
| Risk Factor | Level | Description |
|------------|-------|-------------|
| Technical Risk | HIGH | LLM behavior is unpredictable - may not output milliseconds |
| Regression Risk | LOW | Existing parsing handles both formats |
| Completeness | MEDIUM | Missing validation for AI output format |
| **Overall** | **MEDIUM-HIGH** | Needs more robust implementation |

### Campaign 2: Logo Rendering
| Risk Factor | Level | Description |
|------------|-------|-------------|
| Technical Risk | LOW | Path resolution is deterministic |
| Regression Risk | MEDIUM | Existing DB records need migration |
| Completeness | HIGH | Well-specified fixes |
| **Overall** | **LOW** | Likely to succeed with minor additions |

### Campaign 3: Caption Rendering
| Risk Factor | Level | Description |
|------------|-------|-------------|
| Technical Risk | LOW | Simple math change |
| Regression Risk | LOW | Only affects new clips |
| Completeness | MEDIUM | May need fine-tuning |
| **Overall** | **LOW** | Likely effective |

### Campaign 4: Transcript Display
| Risk Factor | Level | Description |
|------------|-------|-------------|
| Technical Risk | HIGH | LLM instructions often ignored |
| Regression Risk | LOW | Display-only change |
| Completeness | LOW | Wrong approach - needs post-processing |
| **Overall** | **HIGH** | Unlikely to work as designed |

---

## 7. RECOMMENDED CORRECTIONS

### 7.1 Campaign 1 Corrections

**VUW_SYNC-002:** The simplified_system_prompt correction is WRONG. The plan says to change:
```diff
-- Never modify timestamp format (keep MM:SS structure)
+- Timestamp format MUST be MM:SS.mmm
```

But the actual current text at line 71-72 is:
```python
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
```

The transcript already provides MM:SS.mmm format, so the instruction "keep MM:SS structure" should be "keep MM:SS.mmm structure" (preserve what's already there).

**Suggested Fix:**
```diff
- Never modify timestamp format (keep MM:SS structure)
+ Never modify timestamp format (keep MM:SS.mmm structure including milliseconds)
```

### 7.2 Campaign 2 Additions

**Add VUW_LOGO-004:** Migration script for existing relative paths
```python
# Update existing relative paths to absolute
async def migrate_logo_paths():
    # Query all users with relative logo paths
    # Convert each to absolute using base_path / relative_path
    # Update database records
```

### 7.3 Campaign 3 Adjustments

**VUW_CAPTION-001:** Consider reducing multiplier:
- Plan proposes: 50%
- Recommendation: 40-45% (test to confirm)

The plan's proposed change of `max(8, descender_margin + stroke_buffer)` where `descender_margin = int(current_font_size * 0.50)` may create excessive margins.

### 7.4 Campaign 4 Rewrite

**VUW_TEXT-001 through VUW_TEXT-003:** Should be replaced with:

**VUW_TEXT-001_REVISED:** Add transcript text reconstruction function
```python
def reconstruct_text_from_cache(
    cache_path: Path,
    start_time: float,
    end_time: float
) -> str:
    """Reconstruct exact transcript text from cached word data."""
    cache_data = load_cached_transcript_data(cache_path)
    words = cache_data.get("words", [])

    start_ms = int(start_time * 1000)
    end_ms = int(end_time * 1000)

    relevant_words = [
        w["text"] for w in words
        if w["start"] >= start_ms and w["end"] <= end_ms
    ]
    return " ".join(relevant_words)
```

**VUW_TEXT-002_REVISED:** Apply reconstruction to AI segments
```python
# In video processing pipeline, after AI returns segments:
for segment in ai_segments:
    segment.text = reconstruct_text_from_cache(
        video_path.with_suffix(".transcript_cache.json"),
        parse_timestamp_to_seconds(segment.start_time),
        parse_timestamp_to_seconds(segment.end_time)
    )
```

---

## 8. MISSING VUWs TO ADD

### VUW_VALIDATION-001: Add timestamp format validation

**Objective:** Ensure AI returns timestamps with millisecond precision

**Files to Modify:** `backend/src/ai.py`, `backend/src/ai_structured.py`

**Implementation:**
```python
import re

TIMESTAMP_PATTERN = re.compile(r"^\d{2}:\d{2}\.\d{3}$")

def validate_timestamp_format(timestamp: str) -> bool:
    """Validate timestamp has MM:SS.mmm format."""
    return bool(TIMESTAMP_PATTERN.match(timestamp))

# In validation:
if not validate_timestamp_format(segment.start_time):
    logger.warning(f"Timestamp missing milliseconds: {segment.start_time}")
    # Optionally: append ".000" if only MM:SS
```

### VUW_LOGO-004: Database migration for existing paths

**Objective:** Convert existing relative logo paths to absolute

**Files to Create:** `backend/scripts/migrate_logo_paths.py`

### VUW_TEST-001: Add timestamp format tests

**Objective:** Verify timestamp parsing handles all formats

**Files to Create:** `backend/tests/unit/test_timestamp_parsing.py`

---

## 9. EXECUTION ORDER REVISION

### Recommended New Order:

1. **Campaign 2 (Logo)** - Most likely to succeed, lower risk
2. **Campaign 3 (Captions)** - Simple math fix, test visually
3. **Campaign 1 (Sync)** - After adding validation VUW
4. **Campaign 4 (Text)** - Only after complete rewrite

### Pre-Campaign Tasks:
- VUW_VALIDATION-001: Add timestamp validation (required for Campaign 1)
- VUW_LOGO-004: Database migration (required for Campaign 2)

---

## 10. FINAL RECOMMENDATIONS

### DO PROCEED WITH (after corrections):
1. Campaign 2 (Logo) - Add migration VUW
2. Campaign 3 (Captions) - Adjust multiplier value

### REVISE BEFORE PROCEEDING:
1. Campaign 1 (Sync) - Add validation, fix prompt text

### REWRITE COMPLETELY:
1. Campaign 4 (Text) - Replace with cache-based reconstruction

### TESTING RECOMMENDATIONS:
1. Create test video with known word timings
2. Process through full pipeline
3. Compare AI segment boundaries to actual word timings
4. Visually verify caption margins with descender-heavy text
5. Verify logo appears after processing with uploaded logo

---

## Appendix: Source Evidence

### A. Transcript Format Proof (video_utils.py:380-381)
```python
start_time = format_ms_to_timestamp_precise(self.current_start)
end_time = format_ms_to_timestamp_precise(self.current_line[-1][2])
```

### B. Current Caption Margin (video_utils.py:929)
```python
bottom_margin = max(5, int(current_font_size * 0.35))
```

### C. Logo Path Storage (main.py:553)
```python
"logo_path": str(logo_path),  # Relative path stored
```

### D. AI Field Descriptions (ai.py:21-22)
```python
start_time: str = Field(description="Start timestamp in MM:SS format")
end_time: str = Field(description="End timestamp in MM:SS format")
```

---

**Report Generated:** 2025-11-21
**Confidence Level:** HIGH (based on source code verification)
**Recommendation:** REVISE PLAN before execution
