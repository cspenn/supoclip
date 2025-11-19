# Root Cause Analysis: Caption Clipping and Logo Missing
Date: 2025-11-19

## Issues Under Investigation

### Issue 1: Caption Text Descenders Clipped at Bottom
- User screenshot shows "what happened instead." with descenders cut off
- Current margin: 12px bottom (should be adequate)
- Previous fix (commit d62a0e6) did not resolve

### Issue 2: Logo Not Appearing on Clips
- Logo uploaded successfully
- Logo saved to database
- Logo overlay code exists but never executes
- No log messages about logo application

## Log Evidence

### Logo Issue Evidence
```bash
# Logo file exists
$ ls -lh backend/temp/logos/
-rw-r--r--  1 cspenn  staff   1.9K Nov 19 10:27 local-user_logo.png

# Database has logo configured
$ sqlite3 backend/supoclip.db "SELECT id, logo_file_path, logo_corner_position FROM users WHERE logo_file_path IS NOT NULL;"
local-user|temp/logos/local-user_logo.png|bottom-right

# Task processed but NO logo overlay messages
$ grep -E "Added logo overlay|Failed to add logo" backend/logs/backend-2025-11-19_10-27-39.log
# (no results - code never executed)
```

### Caption Issue Evidence
- User screenshot showing descender clipping
- Margin set to 12px at line 927 of video_utils.py
- No error logs related to caption rendering

## All Hypotheses

### Logo Issue Hypotheses

1. **Logo parameters not passed through processing pipeline (CONFIRMED)**
2. Logo file path incorrect or relative vs absolute
3. Logo overlay code has bug preventing execution
4. Logo added but z-order wrong (behind video)
5. Logo opacity zero or size zero

### Caption Issue Hypotheses

1. **Margin applied before stroke calculation**
2. **MoviePy TextClip bounding box excludes descenders**
3. **CompositeVideoClip crops TextClip edges**
4. Font rendering extends beyond reported bounds
5. Resolution scaling affects margin calculations
6. Method "label" has different bounding box than "caption"
7. Text positioning calculation incorrect

## Top 2 Hypotheses - Detailed Analysis

## LOGO ISSUE

### Most Likely Root Cause: Logo Parameters Not Passed Through Pipeline

**Hypothesis:** Logo path and position are retrieved in main.py but NOT passed through the worker/service call chain, resulting in hardcoded `None` value.

**Why this is #1:**
1. Code inspection confirms logo_path/logo_corner_position parameters MISSING from:
   - `workers/tasks.py`: `process_video_task()` signature (lines 14-24)
   - `services/task_service.py`: `process_task()` signature (lines 74-85)
   - `services/video_service.py`: `process_video_complete()` signature (lines 204-214)

2. VideoService hardcodes `None` for logo at line 184:
   ```python
   clips_info = await run_in_thread(
       create_clips_with_transitions,
       video_path,
       segments,
       clips_output_dir,
       font_family,
       font_size,
       font_color,
       None,  # logo_path <-- HARDCODED
       "top-right",  # logo_position <-- HARDCODED
       output_resolution,
   )
   ```

3. Logo overlay code in video_utils.py lines 1143-1177 checks:
   ```python
   if logo_path and logo_path.exists():
       # overlay code
   ```
   This condition is ALWAYS False because logo_path is always None

**Supporting Evidence:**
- **Code trace:** main.py line 237 retrieves logo → line 268 passes to async task → workers/tasks.py line 63 DROPS parameters → video_service.py line 184 uses None
- **Log evidence:** No "Added logo overlay" or "Failed to add logo overlay" messages (code never reached)
- **Database evidence:** Logo exists in database: `local-user|temp/logos/local-user_logo.png|bottom-right`
- **Filesystem evidence:** Logo file exists: `local-user_logo.png` (1.9K)
- **Recent changes:** Migration to asyncio worker queue likely broke parameter passing

**Contradicting Evidence:**
- None - all evidence supports this hypothesis

**Confidence Level:** High (95-100%)

This is a classic "broken telephone" problem - the message (logo parameters) gets lost between the sender (main.py) and receiver (video_utils.py).

### Second Most Likely Root Cause: Logo Path Format Issue

**Hypothesis:** Logo path is relative but needs to be absolute, or path separator issues.

**Why this is #2:**
1. Database stores relative path: `temp/logos/local-user_logo.png`
2. Video processing might run from different working directory
3. Path object creation might fail silently

**Supporting Evidence:**
- Database value is relative: `temp/logos/local-user_logo.png` (no leading /)
- If video processing runs from different directory, relative path would fail
- Logo overlay code checks `logo_path.exists()` - would be False if path wrong

**Contradicting Evidence:**
- This is SECONDARY issue - even if path were absolute, it's currently None
- Logo path is passed as Path object, which should handle relative paths
- Other temp files (clips, downloads) use relative paths successfully
- Logo upload uses `temp/logos/` directory, same as other temp files

**Confidence Level:** Low (15-25%)

This MIGHT be an issue but is secondary to the parameter passing problem.

---

## CAPTION ISSUE

### Most Likely Root Cause: MoviePy TextClip Bounding Box Excludes Descenders

**Hypothesis:** MoviePy's TextClip calculates text bounds based on typical characters, not accounting for descenders that extend below the baseline.

**Why this is #1:**
1. Margin of 12px should be adequate for typical descenders (5-10px)
2. Issue persists despite increased margin (was 3px, now 12px)
3. MoviePy may calculate text height from baseline to ascender top, ignoring descenders
4. When margin is applied, it's applied to the reported bounding box
5. Actual rendered text extends below the bounding box
6. CompositeVideoClip then crops to the bounding box, clipping descenders

**Supporting Evidence:**
- User screenshot clearly shows descenders clipped: "what happened instead."
- 12px margin should be more than sufficient for typical descenders
- Previous fix increased margin but didn't solve issue
- MoviePy TextClip documentation doesn't mention descender handling
- Common issue with text rendering libraries

**Contradicting Evidence:**
- If this were true, ALL text with descenders would be clipped
- May depend on specific font metrics
- Some fonts have smaller descenders than others

**Confidence Level:** Medium-High (60-75%)

This is likely but needs testing to confirm. The solution might be to:
1. Increase margin even more (20-25px)
2. Manually adjust text positioning to account for descenders
3. Use different MoviePy text rendering method

### Second Most Likely Root Cause: Margin Applied Before Stroke

**Hypothesis:** The 1px stroke is applied AFTER margin calculation, causing the stroke to extend beyond the margin and get clipped.

**Why this is #2:**
1. Code applies margin to text_clip AFTER creating it with stroke:
   ```python
   text_clip = TextClip(
       text,
       font=font_path,
       font_size=current_font_size,
       color=font_color,
       stroke_color="black",
       stroke_width=1,  # <-- Stroke applied here
       method="label",
       text_align="center",
   )
   # Then margin applied
   text_clip = text_clip.with_effects([Margin(bottom=12, ...)])
   ```

2. If stroke is rendered AFTER bounding box is calculated, it would extend beyond bounds
3. Margin might not account for stroke width

**Supporting Evidence:**
- Stroke is 1px, which could explain small amount of clipping
- Order of operations: create text → add stroke → add margin
- MoviePy might calculate bounds before stroke is applied

**Contradicting Evidence:**
- 12px margin should account for 1px stroke plus descenders
- If stroke were the only issue, 3-4px margin would suffice
- User screenshot shows significant clipping, more than 1px

**Confidence Level:** Medium (40-50%)

This might be a contributing factor but probably not the primary cause.

## Testing Strategy

### Logo Issue Testing
1. Add logging at each stage of call chain to track logo_path value
2. Add logo parameters to each function signature
3. Pass parameters through pipeline
4. Verify logo overlay code executes (check for log message)
5. Verify logo appears on generated clip

### Caption Issue Testing
1. Create test clip with text containing descenders: "python, joyful, query"
2. Generate clip at different font sizes (20, 24, 36)
3. Try different margin values (12, 15, 20, 25)
4. Check if issue is font-specific
5. Try different MoviePy text methods
6. Manually inspect text bounding box vs rendered bounds

## Fix Approach

### Logo Fix (Clear Path)
**Steps:**
1. Add logo_path and logo_corner_position parameters to process_video_task()
2. Retrieve user preferences in worker before calling task_service
3. Add parameters to TaskService.process_task()
4. Add parameters to VideoService.process_video_complete()
5. Pass logo_path to create_clips_with_transitions()
6. Ensure logo_path is absolute (resolve relative paths)
7. Test with user who has logo uploaded

### Caption Fix (Investigation Required)
**Steps:**
1. Create test script that generates single clip with descenders
2. Try increasing margin to 20-25px
3. If still fails, investigate MoviePy TextClip source code
4. Consider alternative approaches:
   - Use PIL/Pillow to render text, then create ImageClip
   - Manually calculate text bounds including descenders
   - Position text higher in frame to avoid bottom clipping
5. Test across different font sizes and resolutions

## Validation Criteria

### Logo Fix Success
- [ ] Logo appears on all generated clips
- [ ] Logo positioned correctly at specified corner
- [ ] Logo size correct (60px longest dimension)
- [ ] Log message "Added logo overlay at {position}" appears
- [ ] Works across all resolutions (480p, 720p, 1080p)

### Caption Fix Success
- [ ] Text with descenders fully visible
- [ ] No clipping at bottom of text
- [ ] Works with all fonts (TikTokSans, Arial, etc.)
- [ ] Works across all font sizes (20-36px)
- [ ] Works across all resolutions
