# VUW Campaign Plan: Video Processing Bug Fixes
**Date:** 2025-11-21
**Status:** Planning
**Last Updated:** 2025-11-21 (Context-Fetcher Review)

## Campaign Overview

This document contains a comprehensive VUW (Verifiable Units of Work) campaign plan to fix four persistent video processing issues in SupoClip. The issues are organized into 4 campaigns, prioritized by severity:

| Campaign | Priority | Issue | Impact |
|----------|----------|-------|--------|
| 1 | CRITICAL | Caption-Video Sync | Clips start at wrong moment due to AI returning MM:SS instead of MM:SS.mmm |
| 2 | HIGH | Logo Not Appearing | User-uploaded logos never render on clips (path resolution + migration) |
| 3 | MEDIUM | Descender Clipping | Letters like g, p, y, q appear cut off at bottom |
| 4 | MEDIUM | Transcript Display | UI shows AI summary instead of verbatim transcript |

**Total VUWs:** 18 (updated from 12)
**Estimated Time:** 6-8 hours

---

## IMPORTANT: Root Cause Corrections (2025-11-21 Review)

### Campaign 1 Root Cause - CORRECTED

**INCORRECT Previous Analysis:**
> "The AI output format uses MM:SS (1-second precision), but transcription from parakeet-mlx provides millisecond-level timing. When the AI selects segments, it loses the millisecond precision..."

**CORRECT Analysis:**
The transcript IS formatted with millisecond precision (`format_ms_to_timestamp_precise()` outputs `MM:SS.mmm` format at `video_utils.py:238-244`). The formatted transcript sent to AI contains timestamps like `[02:35.450 - 02:45.820]`.

**The REAL Issue is Two-Fold:**
1. **Prompt Issue**: The AI prompts explicitly instruct "keep MM:SS structure" and show examples like `start_time: "02:25"` without milliseconds (`ai.py:72`, `ai_structured.py:149`)
2. **Parsing Issue**: The `TimestampParser.parse_timestamp()` in `ai.py:170-184` uses `int(parts[1])` which truncates any decimal, but `parse_timestamp_to_seconds()` in `video_utils.py:836` correctly uses `float(parts[1])`

**Consequence:** Even if we update prompts to request MM:SS.mmm, LLMs may not reliably preserve milliseconds. We need:
1. Update prompts (necessary but not sufficient)
2. Add output validation with regex
3. Add fallback to snap to nearest word boundary from transcript cache

### Campaign 2 Root Cause - ADDITION NEEDED

**Missing Migration:** The existing fix only handles NEW uploads. Database records with relative paths need migration.

### Campaign 4 Root Cause - APPROACH CHANGE

**INCORRECT Previous Approach:**
Prompt-only changes to request "verbatim text" are unreliable. LLMs fundamentally summarize.

**CORRECT Approach:**
Post-processing that reconstructs exact words from `.transcript_cache.json` based on AI-returned timestamps. This is deterministic and guaranteed accurate.

---

## Campaign 1: Caption-Video Sync (CRITICAL)
**Goal:** Fix timestamp precision loss causing caption/video mismatch

### Corrected Root Cause Analysis

**Problem Chain:**
1. `format_transcript_for_ai()` outputs `[02:35.450 - 02:45.820] word text` (correct, milliseconds present)
2. AI prompts say "keep MM:SS structure" and show examples without milliseconds (wrong instruction)
3. LLM returns `start_time: "02:35"` (milliseconds lost)
4. `TimestampParser.parse_timestamp()` uses `int(parts[1])` which would lose any decimals anyway
5. Clip starts at wrong time (up to 0.999s off)

**Evidence:**
- `backend/src/video_utils.py:238-244`: `format_ms_to_timestamp_precise()` outputs `MM:SS.mmm` correctly
- `backend/src/video_utils.py:380-381`: Uses `format_ms_to_timestamp_precise()` in transcript formatting
- `backend/src/ai.py:71-77`: Prompt says "keep MM:SS structure" - WRONG
- `backend/src/ai.py:170-184`: `int(parts[1])` truncates milliseconds - BUG
- `backend/src/video_utils.py:836`: `float(parts[1])` preserves milliseconds - CORRECT

**Multi-Layered Solution:**
1. Update prompts to request MM:SS.mmm format
2. Fix `TimestampParser.parse_timestamp()` to handle decimals
3. Add validation regex to enforce MM:SS.mmm format
4. Add fallback to snap timestamps to nearest word boundaries from cache

---

### VUW_SYNC-001: Update TranscriptSegment model in ai.py
**Objective:** Change timestamp field descriptions to require millisecond precision (MM:SS.mmm format)

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-001 - TranscriptSegment timestamp precision"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate lines 21-22 containing the TranscriptSegment model fields
3. Replace the timestamp field descriptions with millisecond precision format

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -18,8 +18,8 @@ config = Config()
 class TranscriptSegment(BaseModel):
     """Represents a relevant segment of transcript with precise timing."""

-    start_time: str = Field(description="Start timestamp in MM:SS format")
-    end_time: str = Field(description="End timestamp in MM:SS format")
+    start_time: str = Field(description="Start timestamp in MM:SS.mmm format (e.g., 02:35.450)")
+    end_time: str = Field(description="End timestamp in MM:SS.mmm format (e.g., 02:45.820)")
     text: str = Field(description="The transcript text for this segment")
     relevance_score: float = Field(
         description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-001: Update TranscriptSegment timestamp format to MM:SS.mmm"
```

---

### VUW_SYNC-002: Update simplified_system_prompt timestamp requirements
**Objective:** Update AI prompt to request millisecond-precision timestamps

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-002 - system prompt timestamp format"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate the `simplified_system_prompt` string (around line 38)
3. Update the TIMESTAMP REQUIREMENTS section to specify MM:SS.mmm format

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -69,11 +69,13 @@ CLEAN START RULE - CRITICAL FOR VIRAL CLIPS:
 - Example: X "So the main thing you need..." -> OK "The main thing you need..." (reasoning: "Original start: 'So the' -> Clean start: 'The main'")

 TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
-- Use EXACT timestamps as they appear in the transcript
-- Never modify timestamp format (keep MM:SS structure)
+- Use EXACT timestamps as they appear in the transcript WITH MILLISECOND PRECISION
+- Timestamp format MUST be MM:SS.mmm (e.g., 02:35.450, NOT 02:35)
+- Extract milliseconds from transcript timing like [02:35.450 - 02:45.820]
 - start_time MUST be LESS THAN end_time (start_time < end_time)
 - MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
-- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
+- Look at transcript ranges like [02:25.120 - 02:35.890] and preserve the milliseconds
 - NEVER use the same timestamp for both start_time and end_time
-- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")
+- Example CORRECT: start_time: "02:25.120", end_time: "02:35.890"
+- Example INCORRECT: start_time: "02:25", end_time: "02:35" (missing milliseconds)

 Find 3-7 compelling segments that would work well as standalone clips. Quality over quantity - choose segments that would genuinely engage viewers and have proper time ranges."""
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-002: Update system prompt to require MM:SS.mmm timestamp format"
```

---

### VUW_SYNC-003: Update TranscriptSegment model in ai_structured.py
**Objective:** Update Groq structured output model to use millisecond precision timestamps

**Files to Modify:**
- `backend/src/ai_structured.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-003 - ai_structured.py timestamp format"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai_structured.py`
2. Locate lines 90-99 containing the TranscriptSegment model
3. Update the field descriptions to require MM:SS.mmm format

**Git Diff:**
```diff
--- a/backend/src/ai_structured.py
+++ b/backend/src/ai_structured.py
@@ -90,8 +90,8 @@ def expand_segment_to_duration(
 class TranscriptSegment(BaseModel):
     """Represents a relevant segment of transcript with precise timing."""

-    start_time: str = Field(description="Start timestamp in MM:SS format")
-    end_time: str = Field(description="End timestamp in MM:SS format")
+    start_time: str = Field(description="Start timestamp in MM:SS.mmm format (e.g., 02:35.450)")
+    end_time: str = Field(description="End timestamp in MM:SS.mmm format (e.g., 02:45.820)")
     text: str = Field(description="The transcript text for this segment")
     relevance_score: float = Field(
         description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-003: Update ai_structured.py TranscriptSegment to MM:SS.mmm format"
```

---

### VUW_SYNC-004: Update build_system_prompt in ai_structured.py
**Objective:** Update Groq system prompt to require millisecond precision timestamps

**Files to Modify:**
- `backend/src/ai_structured.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-004 - ai_structured.py system prompt"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai_structured.py`
2. Locate the `build_system_prompt` function (around line 110)
3. Update the TIMESTAMP REQUIREMENTS section to specify MM:SS.mmm format

**Git Diff:**
```diff
--- a/backend/src/ai_structured.py
+++ b/backend/src/ai_structured.py
@@ -145,13 +145,15 @@ def build_system_prompt(min_length: int = 10, max_length: int = 45) -> str:
 - If a segment is more than {max_length} seconds, DO NOT include it in your response
 - Return COMPLETE CLIPS, not word fragments or sentence fragments

-TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
-- Use EXACT timestamps as they appear in the transcript
-- Never modify timestamp format (keep MM:SS structure)
+TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT (MILLISECOND PRECISION REQUIRED):
+- Use EXACT timestamps as they appear in the transcript WITH MILLISECOND PRECISION
+- Timestamp format MUST be MM:SS.mmm (e.g., 02:35.450, NOT 02:35)
+- Extract milliseconds from transcript timing like [02:35.450 - 02:45.820]
 - start_time MUST be LESS THAN end_time (start_time < end_time)
 - MINIMUM segment duration: {min_length} seconds (end_time - start_time >= {min_length} seconds)
 - MAXIMUM segment duration: {max_length} seconds (end_time - start_time <= {max_length} seconds)
-- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
+- Look at transcript ranges like [02:25.120 - 02:35.890] and PRESERVE the milliseconds
 - NEVER use the same timestamp for both start_time and end_time
 - VERIFY DURATION BEFORE RETURNING: Calculate (end_time - start_time) and ensure it's between {min_length} and {max_length} seconds
-- Example CORRECT (if min={min_length}, max={max_length}): start_time: "02:25", end_time: "02:35" (10 second duration)
-- Example INCORRECT: start_time: "02:25", end_time: "02:26" (1 second - TOO SHORT)
-- Example INCORRECT: start_time: "02:25", end_time: "02:25" (0 seconds - INVALID)
+- Example CORRECT: start_time: "02:25.120", end_time: "02:35.890" (10.77 second duration)
+- Example INCORRECT: start_time: "02:25", end_time: "02:35" (missing milliseconds - PRECISION LOST)
+- Example INCORRECT: start_time: "02:25.000", end_time: "02:25.000" (0 seconds - INVALID)
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-004: Update ai_structured.py build_system_prompt for MM:SS.mmm"
```

---

### VUW_SYNC-005: Fix TimestampParser.parse_timestamp to handle milliseconds
**Objective:** Fix the integer truncation bug in ai.py's timestamp parser

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-005 - TimestampParser millisecond fix"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate the `TimestampParser.parse_timestamp` method (around line 170)
3. Change `int(parts[1])` to `float(parts[1])` and return float instead of int

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -164,19 +164,19 @@ class TimestampParser:
     """Parses and validates transcript timestamps."""

     MIN_DURATION_SECONDS = 5

     @staticmethod
-    def parse_timestamp(timestamp: str) -> int:
+    def parse_timestamp(timestamp: str) -> float:
         """
-        Parse MM:SS timestamp to seconds.
+        Parse MM:SS or MM:SS.mmm timestamp to seconds with millisecond precision.

         Raises:
             ValueError: If timestamp format is invalid
         """
         try:
             parts = timestamp.split(":")
             if len(parts) != 2:
                 raise ValueError(f"Invalid format: {timestamp}")
-            minutes, seconds = int(parts[0]), int(parts[1])
+            minutes, seconds = int(parts[0]), float(parts[1])
             return minutes * 60 + seconds
         except (ValueError, IndexError) as e:
             raise ValueError(f"Cannot parse timestamp '{timestamp}': {e}")

     @staticmethod
-    def calculate_duration(start_time: str, end_time: str) -> int:
+    def calculate_duration(start_time: str, end_time: str) -> float:
         """Calculate duration between two timestamps in seconds."""
         start_seconds = TimestampParser.parse_timestamp(start_time)
         end_seconds = TimestampParser.parse_timestamp(end_time)
         return end_seconds - start_seconds

     @staticmethod
-    def validate_duration(duration: int) -> tuple[bool, str]:
+    def validate_duration(duration: float) -> tuple[bool, str]:
         """Validate duration meets minimum requirement."""
         if duration <= 0:
-            return False, f"Invalid duration: {duration}s (must be positive)"
+            return False, f"Invalid duration: {duration:.3f}s (must be positive)"
         if duration < TimestampParser.MIN_DURATION_SECONDS:
             return (
                 False,
-                f"Too short: {duration}s (min {TimestampParser.MIN_DURATION_SECONDS}s required)",
+                f"Too short: {duration:.3f}s (min {TimestampParser.MIN_DURATION_SECONDS}s required)",
             )
-        return True, f"Valid: {duration}s"
+        return True, f"Valid: {duration:.3f}s"
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-005: Fix TimestampParser to handle millisecond precision"
```

---

### VUW_SYNC-006: Add regex validation for MM:SS.mmm format in AI output parsing (NEW)
**Objective:** Add validation to ensure AI output contains millisecond precision, with fallback

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-006 - timestamp format validation"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Add a new `TimestampFormatValidator` class after `TimestampParser`
3. Add validation in the segment validation flow

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -6,6 +6,7 @@
 from typing import List
 import asyncio
 import logging
+import re

 from pydantic_ai import Agent
 from pydantic import BaseModel, Field
@@ -203,6 +204,42 @@ class TimestampParser:
         return True, f"Valid: {duration:.3f}s"


+class TimestampFormatValidator:
+    """Validates timestamp format includes millisecond precision."""
+
+    # Regex for MM:SS.mmm format (milliseconds required)
+    PRECISE_FORMAT = re.compile(r"^\d{1,2}:\d{2}\.\d{1,3}$")
+    # Regex for MM:SS format (milliseconds missing)
+    IMPRECISE_FORMAT = re.compile(r"^\d{1,2}:\d{2}$")
+
+    @staticmethod
+    def validate(timestamp: str) -> tuple[bool, str]:
+        """
+        Validate timestamp has millisecond precision.
+
+        Returns:
+            Tuple of (has_milliseconds, warning_message)
+        """
+        timestamp = timestamp.strip()
+        if TimestampFormatValidator.PRECISE_FORMAT.match(timestamp):
+            return True, "Format OK (MM:SS.mmm)"
+        if TimestampFormatValidator.IMPRECISE_FORMAT.match(timestamp):
+            return False, f"Missing milliseconds in '{timestamp}' - precision may be reduced"
+        return False, f"Invalid timestamp format: '{timestamp}'"
+
+    @staticmethod
+    def add_default_milliseconds(timestamp: str) -> str:
+        """
+        Add .000 to timestamps missing milliseconds.
+
+        This is a fallback when AI returns MM:SS format despite instructions.
+        """
+        timestamp = timestamp.strip()
+        if TimestampFormatValidator.IMPRECISE_FORMAT.match(timestamp):
+            return f"{timestamp}.000"
+        return timestamp
+
+
 class TranscriptSegmentValidator:
     """Validates transcript segments for clip generation."""
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-006: Add TimestampFormatValidator for MM:SS.mmm validation"
```

---

### VUW_SYNC-007: Integrate format validation into segment validation flow (NEW)
**Objective:** Use TimestampFormatValidator in the validation pipeline with logging

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_SYNC-007 - integrate format validation"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate the `TranscriptSegmentValidator.validate_timestamps` method
3. Add format validation with warning logging

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -223,6 +223,18 @@ class TranscriptSegmentValidator:
     def validate_timestamps(segment: TranscriptSegment) -> tuple[bool, str]:
         """Validate segment timestamps."""
+        # Check format precision and log warnings
+        start_has_ms, start_msg = TimestampFormatValidator.validate(segment.start_time)
+        end_has_ms, end_msg = TimestampFormatValidator.validate(segment.end_time)
+
+        if not start_has_ms:
+            logger.warning(f"Timestamp precision warning: {start_msg}")
+            # Apply fallback: add .000 if missing
+            segment.start_time = TimestampFormatValidator.add_default_milliseconds(segment.start_time)
+        if not end_has_ms:
+            logger.warning(f"Timestamp precision warning: {end_msg}")
+            segment.end_time = TimestampFormatValidator.add_default_milliseconds(segment.end_time)
+
         if segment.start_time == segment.end_time:
             return False, "Start and end times are identical"
         try:
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_SYNC-007: Integrate TimestampFormatValidator into validation flow"
```

---

## Campaign 2: Logo Rendering (HIGH)
**Goal:** Fix logo path resolution so uploaded logos appear on videos

### Root Cause Analysis

**Problem:** Logo path is stored as a relative path in the database, but `Path.exists()` fails when the working directory changes during video processing.

**Evidence:**
- `backend/src/main.py:553`: `logo_path = str(logo_path)` stores relative path
- `backend/src/video_utils.py:1172-1173`: `logo_path_obj = Path(logo_path)` then `if logo_path_obj.exists()` - fails with relative path
- `backend/src/services/user_preferences_service.py:178`: Returns `Path(logo_file_path)` without making it absolute

**Solution:**
1. Convert logo path to absolute path at upload time (handles NEW uploads)
2. Convert logo path to absolute in service layer (handles existing relative paths at runtime)
3. Add logging for debugging
4. **NEW:** Migrate existing database records with relative paths

---

### VUW_LOGO-001: Store absolute logo path in upload endpoint
**Objective:** Ensure logo path is stored as absolute path in database

**Files to Modify:**
- `backend/src/main.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_LOGO-001 - absolute logo path storage"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/main.py`
2. Locate the `/upload-logo` endpoint (around line 480)
3. Change `str(logo_path)` to `str(logo_path.resolve())` to store absolute path

**Git Diff:**
```diff
--- a/backend/src/main.py
+++ b/backend/src/main.py
@@ -538,7 +538,8 @@ async def upload_logo(request: Request, user_id: str = Depends(get_current_user)

             # Save resized logo
             logo_filename = f"{user_id}_logo.png"
             logo_path = logos_dir / logo_filename
+            logo_path = logo_path.resolve()  # Convert to absolute path
             resized.save(logo_path, "PNG")

         # Delete temp file
@@ -548,7 +549,7 @@ async def upload_logo(request: Request, user_id: str = Depends(get_current_user)
         async with AsyncSessionLocal() as db:
             await db.execute(
                 text(
-                    "UPDATE users SET logo_file_path = :logo_path, logo_corner_position = :position WHERE id = :user_id"
+                    "UPDATE users SET logo_file_path = :logo_path, logo_corner_position = :position, updatedAt = CURRENT_TIMESTAMP WHERE id = :user_id"
                 ),
                 {
                     "logo_path": str(logo_path),
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_LOGO-001: Store absolute logo path in upload endpoint"
```

---

### VUW_LOGO-002: Convert logo path to absolute in user_preferences_service
**Objective:** Ensure logo path is always returned as absolute path

**Files to Modify:**
- `backend/src/services/user_preferences_service.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_LOGO-002 - absolute logo path in service"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/services/user_preferences_service.py`
2. Locate the `get_logo_path` method (around line 168)
3. Add `.resolve()` call and existence validation

**Git Diff:**
```diff
--- a/backend/src/services/user_preferences_service.py
+++ b/backend/src/services/user_preferences_service.py
@@ -165,9 +165,25 @@ class UserPreferencesService:

     def get_logo_path(self, preferences: dict[str, Any]) -> Optional[Path]:
         """Extract logo path from preferences.
+
+        Converts relative paths to absolute and validates existence.

         Args:
             preferences: Merged preferences dictionary

         Returns:
-            Path object if logo configured, None otherwise
+            Absolute Path object if logo exists, None otherwise
         """
         logo_file_path = preferences.get("logo_file_path")
-        return Path(logo_file_path) if logo_file_path else None
+        if not logo_file_path:
+            return None
+
+        logo_path = Path(logo_file_path)
+
+        # Convert to absolute path if relative
+        if not logo_path.is_absolute():
+            logo_path = logo_path.resolve()
+
+        # Validate existence
+        if not logo_path.exists():
+            logger.warning(f"Logo file not found at path: {logo_path}")
+            return None
+
+        return logo_path
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_LOGO-002: Add absolute path conversion and validation in get_logo_path"
```

---

### VUW_LOGO-003: Add logo path validation logging in video_utils.py
**Objective:** Add explicit logging for logo path resolution to aid debugging

**Files to Modify:**
- `backend/src/video_utils.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_LOGO-003 - logo path validation logging"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/video_utils.py`
2. Locate the logo overlay section in `create_optimized_clip` (around line 1170)
3. Add explicit logging for logo path resolution

**Git Diff:**
```diff
--- a/backend/src/video_utils.py
+++ b/backend/src/video_utils.py
@@ -1167,9 +1167,17 @@ def create_optimized_clip(

         # Add logo overlay if provided
         if logo_path:
+            logger.info(f"Logo path provided: {logo_path}")
             # Convert string to Path if needed
             logo_path_obj = Path(logo_path) if isinstance(logo_path, str) else logo_path
+
+            # Ensure absolute path
+            if not logo_path_obj.is_absolute():
+                logo_path_obj = logo_path_obj.resolve()
+                logger.info(f"Converted to absolute path: {logo_path_obj}")
+
             if logo_path_obj.exists():
+                logger.info(f"Logo file found, adding overlay from: {logo_path_obj}")
                 try:
                     from moviepy import ImageClip

@@ -1202,6 +1210,8 @@ def create_optimized_clip(

                 except Exception as e:
                     logger.warning(f"Failed to add logo overlay: {e}")
+            else:
+                logger.warning(f"Logo file NOT found at: {logo_path_obj}")

         # Compose and encode
         final_clip = (
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_LOGO-003: Add logo path validation and logging in create_optimized_clip"
```

---

### VUW_LOGO-004: Database migration script for existing relative logo paths (NEW)
**Objective:** Migrate existing database records with relative logo paths to absolute paths

**Files to Modify:**
- `backend/scripts/migrate_logo_paths.py` (NEW FILE)

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_LOGO-004 - logo path migration script"
```

**Step-by-Step Instructions:**

1. Create the directory `backend/scripts/` if it doesn't exist
2. Create a new file `backend/scripts/migrate_logo_paths.py`
3. Write a migration script that:
   - Queries all users with logo_file_path set
   - For each relative path, converts to absolute
   - Updates the database record

**New File Content:**
```python
#!/usr/bin/env python3
"""
Migration script to convert relative logo paths to absolute paths.

Run this once after deploying VUW_LOGO-001 to fix existing records.

Usage:
    cd backend
    python -m scripts.migrate_logo_paths
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import text

from src.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_logo_paths() -> None:
    """Migrate relative logo paths to absolute paths in database."""
    logger.info("Starting logo path migration...")

    async with AsyncSessionLocal() as db:
        # Query all users with logo paths
        result = await db.execute(
            text("SELECT id, logo_file_path FROM users WHERE logo_file_path IS NOT NULL")
        )
        rows = result.fetchall()

        if not rows:
            logger.info("No users with logo paths found. Nothing to migrate.")
            return

        logger.info(f"Found {len(rows)} users with logo paths to check.")

        migrated_count = 0
        for user_id, logo_path in rows:
            if not logo_path:
                continue

            path_obj = Path(logo_path)

            # Skip if already absolute
            if path_obj.is_absolute():
                logger.debug(f"User {user_id}: Already absolute: {logo_path}")
                continue

            # Convert to absolute
            absolute_path = path_obj.resolve()

            # Verify file exists at absolute path
            if not absolute_path.exists():
                logger.warning(
                    f"User {user_id}: File not found at resolved path: {absolute_path}"
                )
                continue

            # Update database
            await db.execute(
                text(
                    "UPDATE users SET logo_file_path = :new_path, updatedAt = CURRENT_TIMESTAMP WHERE id = :user_id"
                ),
                {"new_path": str(absolute_path), "user_id": user_id},
            )
            logger.info(f"User {user_id}: Migrated '{logo_path}' -> '{absolute_path}'")
            migrated_count += 1

        await db.commit()
        logger.info(f"Migration complete. Updated {migrated_count} records.")


if __name__ == "__main__":
    asyncio.run(migrate_logo_paths())
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**
- [ ] Verify script runs without errors: `cd backend && python -m scripts.migrate_logo_paths`

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_LOGO-004: Add migration script for existing relative logo paths"
```

---

## Campaign 3: Caption Rendering (MEDIUM)
**Goal:** Fix descender clipping in caption text

### Root Cause Analysis

**Problem:** The dynamic margin calculation (35% of font size) is insufficient for fonts with deep descenders (like g, p, y, q) when combined with stroke effects.

**Evidence:**
- `backend/src/video_utils.py:929`: Current margin is `max(5, int(current_font_size * 0.35))`
- For 24px font: margin = 8px, but descenders + 1px stroke need ~10-12px
- For fonts with deep descenders, this causes visible clipping

**Solution:** Increase margin multiplier from 0.35 to 0.45 (45% of font size - more conservative than 50%) and add stroke width to calculation.

**Note:** Context-fetcher recommended testing 40-45% before going to 50%. Using 45% as a balanced starting point.

---

### VUW_CAPTION-001: Increase descender margin calculation
**Objective:** Fix descender clipping by increasing margin to 45% of font size plus stroke

**Files to Modify:**
- `backend/src/video_utils.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_CAPTION-001 - descender margin fix"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/video_utils.py`
2. Locate the `SubtitleTextClipCreator.create_text_clip` method (around line 898)
3. Update the bottom margin calculation to use 45% of font size plus stroke width

**Git Diff:**
```diff
--- a/backend/src/video_utils.py
+++ b/backend/src/video_utils.py
@@ -893,6 +893,7 @@ class SubtitleTextClipCreator:
     MAX_SUBTITLE_LINES = 2
     HORIZONTAL_PADDING = 0.1
     MIN_FONT_SIZE = 16
+    STROKE_WIDTH = 1  # Stroke width in pixels
     FONT_SIZE_REDUCTION = 0.85

     @staticmethod
@@ -922,11 +923,17 @@ class SubtitleTextClipCreator:
             )

             # Add margin to prevent stroke and descenders from being cut off at edges
-            # Dynamic bottom margin based on font size: 35% of font size accounts for descenders (20-25%)
-            # plus stroke (1px) and buffer. This ensures no clipping at any font size (16-40px).
-            # Examples: 16px->5px, 20px->7px, 24px->8px, 30px->10px, 40px->14px
-            bottom_margin = max(5, int(current_font_size * 0.35))
+            # Dynamic bottom margin based on font size: 45% of font size accounts for:
+            # - Deep descenders (25-30% for fonts like g, p, y, q, j)
+            # - Stroke width (typically 1-2px)
+            # - Safety buffer for edge anti-aliasing
+            # This ensures no clipping at any font size (16-40px).
+            # Examples: 16px->7px, 20px->9px, 24px->11px, 30px->14px, 40px->18px
+            stroke_buffer = SubtitleTextClipCreator.STROKE_WIDTH * 2
+            descender_margin = int(current_font_size * 0.45)
+            bottom_margin = max(7, descender_margin + stroke_buffer)
             text_clip = text_clip.with_effects(
-                [Margin(bottom=bottom_margin, top=5, left=3, right=3, opacity=0)]
+                [Margin(bottom=bottom_margin, top=6, left=4, right=4, opacity=0)]
             )
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_CAPTION-001: Fix descender clipping with 45% font size margin plus stroke buffer"
```

---

### VUW_CAPTION-002: Add configurable stroke width parameter
**Objective:** Make stroke width configurable to allow margin calculation to adapt

**Files to Modify:**
- `backend/src/video_utils.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_CAPTION-002 - configurable stroke width"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/video_utils.py`
2. Locate the TextClip creation in `create_text_clip` (around line 914)
3. Use the class constant for stroke_width instead of hardcoded value

**Git Diff:**
```diff
--- a/backend/src/video_utils.py
+++ b/backend/src/video_utils.py
@@ -914,7 +914,7 @@ class SubtitleTextClipCreator:
                 font_size=current_font_size,
                 color=font_color,
                 stroke_color="black",
-                stroke_width=1,
+                stroke_width=SubtitleTextClipCreator.STROKE_WIDTH,
                 method="label",  # Changed from "caption" to prevent text cutoff
                 text_align="center",
             )
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_CAPTION-002: Use configurable STROKE_WIDTH constant in TextClip creation"
```

---

## Campaign 4: Transcript Display (MEDIUM)
**Goal:** Show actual transcript words in UI instead of AI summary

### Corrected Root Cause Analysis

**Problem:** The AI's `text` field contains a summary/paraphrase of the segment, not the verbatim transcript. This causes the UI to display different text than what's actually spoken in the video.

**INCORRECT Previous Approach:**
Prompt-only changes to request "verbatim text" are unreliable. LLMs fundamentally summarize content.

**CORRECT Approach:**
1. Update prompts (necessary but not sufficient) - VUW_TEXT-001 through VUW_TEXT-003
2. **NEW:** Add post-processing to reconstruct exact words from `.transcript_cache.json` - VUW_TEXT-004

The cache-based approach is deterministic and guaranteed accurate because it extracts actual transcribed words based on timestamps.

---

### VUW_TEXT-001: Update text field description to require verbatim transcript
**Objective:** Instruct AI to use exact transcript words, not summaries

**Files to Modify:**
- `backend/src/ai.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEXT-001 - verbatim transcript text"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate the TranscriptSegment model text field (line 23)
3. Update the field description to require verbatim text

**Git Diff:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -20,7 +20,7 @@ class TranscriptSegment(BaseModel):

     start_time: str = Field(description="Start timestamp in MM:SS.mmm format (e.g., 02:35.450)")
     end_time: str = Field(description="End timestamp in MM:SS.mmm format (e.g., 02:45.820)")
-    text: str = Field(description="The transcript text for this segment")
+    text: str = Field(description="The EXACT verbatim transcript text for this segment - copy directly from transcript, do not summarize or paraphrase")
     relevance_score: float = Field(
         description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
     )
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEXT-001: Update text field to require verbatim transcript"
```

---

### VUW_TEXT-002: Update ai_structured.py text field description
**Objective:** Instruct Groq model to use exact transcript words

**Files to Modify:**
- `backend/src/ai_structured.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEXT-002 - ai_structured verbatim text"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai_structured.py`
2. Locate the TranscriptSegment model text field (line 95)
3. Update the field description to require verbatim text

**Git Diff:**
```diff
--- a/backend/src/ai_structured.py
+++ b/backend/src/ai_structured.py
@@ -92,7 +92,7 @@ class TranscriptSegment(BaseModel):

     start_time: str = Field(description="Start timestamp in MM:SS.mmm format (e.g., 02:35.450)")
     end_time: str = Field(description="End timestamp in MM:SS.mmm format (e.g., 02:45.820)")
-    text: str = Field(description="The transcript text for this segment")
+    text: str = Field(description="The EXACT verbatim transcript text for this segment - copy directly from transcript, do not summarize or paraphrase")
     relevance_score: float = Field(
         description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
     )
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEXT-002: Update ai_structured.py text field to require verbatim transcript"
```

---

### VUW_TEXT-003: Update system prompts to explicitly require verbatim text
**Objective:** Add explicit instruction in system prompts to copy transcript verbatim

**Files to Modify:**
- `backend/src/ai.py`
- `backend/src/ai_structured.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEXT-003 - system prompt verbatim text instruction"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/ai.py`
2. Locate the `simplified_system_prompt` string
3. Add explicit instruction about verbatim text

4. Open the file `backend/src/ai_structured.py`
5. Locate the `build_system_prompt` function
6. Add the same explicit instruction

**Git Diff for ai.py:**
```diff
--- a/backend/src/ai.py
+++ b/backend/src/ai.py
@@ -52,6 +52,11 @@ SEGMENT SELECTION CRITERIA:
 4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone
 5. ENTERTAINING: Content people would want to share

+TEXT CONTENT REQUIREMENT - CRITICAL:
+- The 'text' field MUST contain the EXACT words from the transcript
+- DO NOT summarize, paraphrase, or rewrite the transcript
+- COPY the exact text that appears between your chosen timestamps
+
 TIMING GUIDELINES:
 - Segments MUST respect the configured duration range for optimal engagement
```

**Git Diff for ai_structured.py:**
```diff
--- a/backend/src/ai_structured.py
+++ b/backend/src/ai_structured.py
@@ -135,6 +135,11 @@ def build_system_prompt(min_length: int = 10, max_length: int = 45) -> str:
 4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone (NOT partial)
 5. ENTERTAINING: Content people would want to watch (FULL CLIPS, NOT FRAGMENTS)

+TEXT CONTENT REQUIREMENT - CRITICAL:
+- The 'text' field MUST contain the EXACT words from the transcript
+- DO NOT summarize, paraphrase, or rewrite the transcript
+- COPY the exact text that appears between your chosen timestamps
+
 DURATION REQUIREMENTS - ABSOLUTELY CRITICAL:
 - MINIMUM DURATION: {min_length} seconds per segment (DO NOT return segments shorter than {min_length} seconds)
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEXT-003: Add explicit verbatim text requirement to system prompts"
```

---

### VUW_TEXT-004: Implement cache-based text reconstruction (NEW)
**Objective:** Add post-processing to extract exact words from transcript cache based on timestamps

**Files to Modify:**
- `backend/src/video_utils.py`

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEXT-004 - cache-based text reconstruction"
```

**Step-by-Step Instructions:**

1. Open the file `backend/src/video_utils.py`
2. Add a new function `extract_text_from_cache` that reads word-level data from transcript cache
3. This function will be called during clip generation to get exact text for timestamps

**New Function to Add (after `format_transcript_for_ai`):**
```python
def extract_text_from_cache(
    transcript_data: Dict[str, Any],
    start_seconds: float,
    end_seconds: float,
) -> str:
    """
    Extract exact verbatim text from transcript cache based on timestamps.

    This provides accurate text extraction based on word-level timing data,
    independent of what the AI returned in its 'text' field.

    Args:
        transcript_data: Dictionary with 'words' array containing word objects
        start_seconds: Start time in seconds (can include milliseconds)
        end_seconds: End time in seconds (can include milliseconds)

    Returns:
        Exact transcript text for the given time range
    """
    if not transcript_data or "words" not in transcript_data:
        logger.warning("No transcript data available for text extraction")
        return ""

    words = transcript_data["words"]
    if not words:
        return ""

    # Convert to milliseconds for comparison with word data
    start_ms = start_seconds * 1000
    end_ms = end_seconds * 1000

    extracted_words = []
    for word_data in words:
        word_start = word_data.get("start", 0)
        word_end = word_data.get("end", 0)
        word_text = word_data.get("text", "")

        # Include word if it overlaps with the requested time range
        # Word is included if it starts before end_ms and ends after start_ms
        if word_start < end_ms and word_end > start_ms:
            extracted_words.append(word_text)

    result = " ".join(extracted_words)
    logger.debug(
        f"Extracted {len(extracted_words)} words from {start_seconds:.3f}s to {end_seconds:.3f}s"
    )
    return result
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEXT-004: Add extract_text_from_cache for verbatim text reconstruction"
```

---

## Campaign 5: Test Coverage (NEW)
**Goal:** Add unit tests to verify fixes and prevent regressions

---

### VUW_TEST-001: Add unit tests for timestamp parsing with MM:SS and MM:SS.mmm formats (NEW)
**Objective:** Ensure timestamp parsers correctly handle both formats

**Files to Modify:**
- `backend/tests/unit/test_timestamp_parsing.py` (NEW FILE)

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEST-001 - timestamp parsing tests"
```

**Step-by-Step Instructions:**

1. Create a new test file `backend/tests/unit/test_timestamp_parsing.py`
2. Add tests for both `TimestampParser` (ai.py) and `parse_timestamp_to_seconds` (video_utils.py)

**New File Content:**
```python
"""Unit tests for timestamp parsing functions."""

import pytest

from src.ai import TimestampParser, TimestampFormatValidator
from src.video_utils import parse_timestamp_to_seconds


class TestTimestampParser:
    """Tests for ai.py TimestampParser."""

    def test_parse_mm_ss_format(self):
        """Test parsing MM:SS format."""
        result = TimestampParser.parse_timestamp("02:35")
        assert result == 155.0

    def test_parse_mm_ss_mmm_format(self):
        """Test parsing MM:SS.mmm format with milliseconds."""
        result = TimestampParser.parse_timestamp("02:35.450")
        assert abs(result - 155.450) < 0.001

    def test_parse_single_digit_minutes(self):
        """Test parsing single digit minutes."""
        result = TimestampParser.parse_timestamp("1:30")
        assert result == 90.0

    def test_calculate_duration_with_milliseconds(self):
        """Test duration calculation preserves milliseconds."""
        duration = TimestampParser.calculate_duration("02:25.120", "02:35.890")
        assert abs(duration - 10.77) < 0.001

    def test_validate_duration_positive(self):
        """Test duration validation for positive duration."""
        is_valid, msg = TimestampParser.validate_duration(10.5)
        assert is_valid is True

    def test_validate_duration_too_short(self):
        """Test duration validation rejects short durations."""
        is_valid, msg = TimestampParser.validate_duration(2.0)
        assert is_valid is False
        assert "Too short" in msg


class TestTimestampFormatValidator:
    """Tests for ai.py TimestampFormatValidator."""

    def test_validate_precise_format(self):
        """Test validation of MM:SS.mmm format."""
        has_ms, msg = TimestampFormatValidator.validate("02:35.450")
        assert has_ms is True

    def test_validate_imprecise_format(self):
        """Test validation of MM:SS format (missing milliseconds)."""
        has_ms, msg = TimestampFormatValidator.validate("02:35")
        assert has_ms is False
        assert "Missing milliseconds" in msg

    def test_add_default_milliseconds(self):
        """Test adding .000 to imprecise timestamps."""
        result = TimestampFormatValidator.add_default_milliseconds("02:35")
        assert result == "02:35.000"

    def test_add_default_milliseconds_preserves_precise(self):
        """Test that precise timestamps are not modified."""
        result = TimestampFormatValidator.add_default_milliseconds("02:35.450")
        assert result == "02:35.450"


class TestVideoUtilsTimestampParsing:
    """Tests for video_utils.py parse_timestamp_to_seconds."""

    def test_parse_mm_ss_format(self):
        """Test parsing MM:SS format."""
        result = parse_timestamp_to_seconds("02:35")
        assert result == 155.0

    def test_parse_mm_ss_mmm_format(self):
        """Test parsing MM:SS.mmm format with milliseconds."""
        result = parse_timestamp_to_seconds("02:35.450")
        assert abs(result - 155.450) < 0.001

    def test_parse_hh_mm_ss_format(self):
        """Test parsing HH:MM:SS format."""
        result = parse_timestamp_to_seconds("01:02:35")
        assert result == 3755.0

    def test_parse_hh_mm_ss_mmm_format(self):
        """Test parsing HH:MM:SS.mmm format."""
        result = parse_timestamp_to_seconds("01:02:35.500")
        assert abs(result - 3755.5) < 0.001

    def test_parse_pure_seconds(self):
        """Test parsing pure seconds format."""
        result = parse_timestamp_to_seconds("155.450")
        assert abs(result - 155.450) < 0.001
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEST-001: Add unit tests for timestamp parsing"
```

---

### VUW_TEST-002: Add unit tests for logo path resolution (NEW)
**Objective:** Ensure logo paths are correctly resolved to absolute paths

**Files to Modify:**
- `backend/tests/unit/test_logo_path.py` (NEW FILE)

**Mandatory Pre-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CHECKPOINT: Before VUW_TEST-002 - logo path tests"
```

**Step-by-Step Instructions:**

1. Create a new test file `backend/tests/unit/test_logo_path.py`
2. Add tests for logo path resolution in user_preferences_service

**New File Content:**
```python
"""Unit tests for logo path resolution."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.services.user_preferences_service import UserPreferencesService


class TestLogoPathResolution:
    """Tests for logo path resolution in UserPreferencesService."""

    def test_get_logo_path_none_when_not_set(self):
        """Test returns None when no logo path configured."""
        service = UserPreferencesService()
        result = service.get_logo_path({})
        assert result is None

    def test_get_logo_path_none_when_empty(self):
        """Test returns None when logo path is empty string."""
        service = UserPreferencesService()
        result = service.get_logo_path({"logo_file_path": ""})
        assert result is None

    def test_get_logo_path_returns_absolute(self):
        """Test returns absolute path when file exists."""
        service = UserPreferencesService()
        # Use a file we know exists
        test_path = Path(__file__).resolve()
        result = service.get_logo_path({"logo_file_path": str(test_path)})
        assert result is not None
        assert result.is_absolute()

    def test_get_logo_path_converts_relative(self):
        """Test converts relative path to absolute."""
        service = UserPreferencesService()
        # Create a temporary test to verify behavior
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_absolute", return_value=False):
                result = service.get_logo_path({"logo_file_path": "logos/test.png"})
                # With mocking, we're testing the logic, not the actual file
                # The function should attempt resolution

    def test_get_logo_path_none_when_file_missing(self):
        """Test returns None when file doesn't exist."""
        service = UserPreferencesService()
        result = service.get_logo_path({"logo_file_path": "/nonexistent/path/logo.png"})
        assert result is None
```

**Mandatory Verification Checklist:**
- [ ] Run `./checkpython.sh`: Must report **zero errors** with **100% passing tests**

**Self-Attestation:**
- [ ] I attest that checkpython.sh passed and tests succeeded

**Mandatory Post-Work Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "VUW_TEST-002: Add unit tests for logo path resolution"
```

---

## Execution Order Summary

Execute VUWs in this exact order:

### Campaign 1: Caption-Video Sync (CRITICAL) - 7 VUWs
1. VUW_SYNC-001: Update TranscriptSegment model in ai.py
2. VUW_SYNC-002: Update simplified_system_prompt timestamp requirements
3. VUW_SYNC-003: Update TranscriptSegment model in ai_structured.py
4. VUW_SYNC-004: Update build_system_prompt in ai_structured.py
5. VUW_SYNC-005: Fix TimestampParser.parse_timestamp to handle milliseconds
6. **VUW_SYNC-006: Add regex validation for MM:SS.mmm format (NEW)**
7. **VUW_SYNC-007: Integrate format validation into segment validation flow (NEW)**

### Campaign 2: Logo Rendering (HIGH) - 4 VUWs
8. VUW_LOGO-001: Store absolute logo path in upload endpoint
9. VUW_LOGO-002: Convert logo path to absolute in user_preferences_service
10. VUW_LOGO-003: Add logo path validation logging in video_utils.py
11. **VUW_LOGO-004: Database migration script for existing relative logo paths (NEW)**

### Campaign 3: Caption Rendering (MEDIUM) - 2 VUWs
12. VUW_CAPTION-001: Increase descender margin calculation (45% instead of 50%)
13. VUW_CAPTION-002: Add configurable stroke width parameter

### Campaign 4: Transcript Display (MEDIUM) - 4 VUWs
14. VUW_TEXT-001: Update text field description to require verbatim transcript
15. VUW_TEXT-002: Update ai_structured.py text field description
16. VUW_TEXT-003: Update system prompts to explicitly require verbatim text
17. **VUW_TEXT-004: Implement cache-based text reconstruction (NEW)**

### Campaign 5: Test Coverage (NEW) - 2 VUWs
18. **VUW_TEST-001: Add unit tests for timestamp parsing (NEW)**
19. **VUW_TEST-002: Add unit tests for logo path resolution (NEW)**

---

## Post-Campaign Verification

After completing all VUWs, run comprehensive verification:

```bash
cd /Users/cspenn/Documents/github/supoclip/backend

# Run full test suite
./checkpython.sh

# Run migration script for existing logo paths
python -m scripts.migrate_logo_paths

# Manual verification tests (optional)
# 1. Upload a logo and verify it appears on generated clips
# 2. Process a video and verify timestamps have millisecond precision
# 3. Check that caption text matches spoken words
# 4. Verify descenders (g, p, y, q) are not clipped in captions
```

**Final Checkpoint:**
```bash
cd /Users/cspenn/Documents/github/supoclip && git add -A && git commit -m "CAMPAIGN COMPLETE: All video processing bug fixes implemented and verified"
```

---

## Risk Assessment (Updated)

### Campaign 1 Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM ignores millisecond precision despite prompts | HIGH | MEDIUM | VUW_SYNC-006/007 adds validation and fallback |
| Timestamp parsing breaks backward compatibility | LOW | HIGH | Parser handles both MM:SS and MM:SS.mmm |
| Tests fail after parser changes | MEDIUM | LOW | VUW_TEST-001 validates both formats |

### Campaign 2 Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration script fails on some records | LOW | MEDIUM | Script has validation and logging |
| Existing relative paths not found | MEDIUM | LOW | Service layer adds existence check |

### Campaign 3 Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 45% margin still clips some fonts | LOW | LOW | Can be increased later if needed |
| Margin increase pushes text off-screen | LOW | MEDIUM | Top margin also increased |

### Campaign 4 Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM still returns summaries | HIGH | LOW | VUW_TEXT-004 provides deterministic fallback |
| Cache not available | LOW | MEDIUM | Graceful fallback to AI text |

---

## Rollback Plan

Each VUW has a pre-work checkpoint. To rollback any VUW:
```bash
git log --oneline -20  # Find the CHECKPOINT commit
git reset --hard <checkpoint-commit-hash>
```

### Backward Compatibility
- Timestamp parser handles both MM:SS and MM:SS.mmm formats
- Logo path changes are additive (resolve() handles both relative and absolute)
- Caption margin changes are purely visual improvements
- Text extraction is additive, doesn't remove AI text

### Testing Strategy
- Each VUW must pass `./checkpython.sh` before proceeding
- Changes are incremental and isolated
- No database schema changes required (migration is data-only)
- New tests validate all fixes
