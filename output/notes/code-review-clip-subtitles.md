# Code Review: src/pipeline/clip.py + src/pipeline/subtitles.py

**Reviewer:** automated audit agent  
**Date:** 2026-06-29  
**Scope:** src/pipeline/clip.py, src/pipeline/subtitles.py  
**Ground truth:** 466 tests pass, 100% coverage, ruff clean, mypy clean, radon C on process_video in video_service (not in scope here).

---

## ✅ Good — Well-implemented features, clean code, good patterns

### clip.py

- **`filter_words_for_segment` (lines 108–158):** Correct midpoint-based inclusion logic avoids boundary ambiguity. Offsets timestamps to be relative to segment start without mutating caller's input (uses `dict(word)` copy). Docstring has a concrete worked example.
- **`build_ffmpeg_command` uses list-form subprocess correctly (lines 219–233):** No `shell=True`. All arguments are str-typed. `-ss` before `-i` for fast keyframe seek is correct. `-y` for non-interactive overwrite is correct. `-movflags +faststart` for streaming compatibility is correct.
- **`asyncio.to_thread(_run_ffmpeg, cmd)` (line 339):** Blocking subprocess offloaded off the asyncio event loop. `_run_ffmpeg` captures stdout+stderr with `capture_output=True`.
- **`generate_clip` error propagation (lines 341–346):** Raises `ClipGenerationError` with the decoded ffmpeg stderr, making failures diagnosable.
- **`_get_video_dimensions` try/finally (lines 398–410):** `cap.release()` is in `finally`, guaranteed even on exception. Handles ImportError, zero-dimension, and exception cases with appropriate fallbacks and warnings.
- **`out.parent.mkdir(parents=True, exist_ok=True)` (line 278):** Defensive pre-creation of output directory.
- **`@dataclass(slots=True)` on both `TranscriptSegment` and `ClipOptions` (lines 61, 80):** Memory-efficient, prevents typo-based dynamic attribute creation.

### subtitles.py

- **`hex_to_bgr_color` (lines 51–79):** Correctly converts #RRGGBB to pysubs2 Color. Validates length, raises `ValueError` on invalid input. Comments explain the confusing ASS BGR internal storage vs constructor argument order.
- **`calculate_margin_v` (lines 82–101):** Correct math: pysubs2 MarginV is pixels from bottom, so `(100 - position_y_pct) / 100 * video_height` is right. Docstring with example (`75% → 480px` on 1920px).
- **`_MIN_WORD_DURATION_MS = 50` filter (lines 163–170):** Prevents zero- or near-zero-duration ASS events, which can confuse libass and produce flicker.
- **`pysubs2.Alignment.BOTTOM_CENTER` (line 120):** Correct alignment constant for social media vertical video.
- **`write_ass_file` creates parent dirs (line 214):** Defensive, consistent with `generate_clip`.

---

## ❌ Bad — Bugs, poor implementations, anti-patterns

### clip.py

**[CRITICAL] ffmpeg filter-graph injection via unescaped paths (clip.py:212–215)**  
`build_ffmpeg_command` directly interpolates `ass_path` and `fonts_dir` into the `-vf` filter string:
```python
ass_filter = f"ass={ass_path}"
if fonts_dir is not None:
    ass_filter += f":fontsdir={fonts_dir}"
```
The ffmpeg filter-graph parser uses `:` and `,` as delimiters and `\` for escaping. If `TEMP_DIR` or the project root path contains a space, colon, or comma (e.g., `My Projects/supoclip/temp/`), ffmpeg will misparse the filter chain and fail silently or with a cryptic error. The spec (Section 10.4) explicitly requires this escaping: *"Paths containing colons or spaces must be escaped with backslash for the ffmpeg filter graph parser."* This is unimplemented. Unit tests use `/tmp/subs.ass` which has no special characters, so this bug is never exercised.

**[HIGH] Resolution label mismatch vs spec (clip.py:44–48)**  
```python
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "480p": (480, 854),
    "720p": (720, 1280),
    "1080p": (1080, 1920),
}
```
The spec (Section 10.1, 6.4) defines `720p` = 1080×1920 and `1080p` = 2160×3840. The code defines `720p` = 720×1280 and `1080p` = 1080×1920. If `UserPreferences.output_resolution` defaults to `"720p"`, users get 720×1280 output instead of the TikTok/Reels standard 1080×1920. The code labels are conventional (720 lines), but the spec uses non-standard labels where "720p" means full 1080px-wide vertical. The mismatch means users are silently getting lower-resolution output than expected.

### subtitles.py

**[HIGH] Misleading docstring header for `hex_to_bgr_color` (subtitles.py:58)**  
The docstring says *"pysubs2's Color constructor takes (Blue, Green, Red, Alpha)"* but the code immediately below calls `pysubs2.Color(r, g, b, 0)` in RGB order. The clarifying comment (line 78) says the constructor takes RGB, contradicting the header. This is a maintenance hazard for anyone who reads only the function signature.

**[HIGH] Missing dict key validation on word data (subtitles.py:159–180)**  
`start_ms`, `end_ms`, and `text` are accessed directly via `word_data["start_ms"]` etc. without `.get()` or try/except. If the upstream transcription pipeline produces word dicts missing any of these keys (e.g. parakeet-mlx returns a different key name, or a word entry is malformed), the entire `generate_ass_subtitles` call raises `KeyError` with no useful context about which word or which key was missing.

---

## ❓ Missing — Incomplete features, gaps vs spec/PRD

### clip.py

**[HIGH] Logo overlay completely unimplemented (clip.py:94–95, 330–336)**  
`ClipOptions` declares `logo_path`, `add_transitions`, and `transitions_dir`. `generate_clip` passes `ass_path` and `fonts_dir` to `build_ffmpeg_command` but the logo is never passed. `build_ffmpeg_command` has no parameter for logo. The spec (Section 10.5) describes a complete `-filter_complex` logo overlay filter chain with position mapping (`top-left`, `top-right`, etc.). `UserPreferences.logo_path` and `logo_position` are persisted but never applied. Users who configure a logo see no effect.

**[MEDIUM] Transitions unimplemented (clip.py:95–96)**  
`ClipOptions.add_transitions` and `transitions_dir` are unused. The PRD (Section 4) and CLAUDE.md both describe transitions as supported. The `transitions/` directory exists at the project root. The pipeline never applies them.

**[MEDIUM] No ffmpeg timeout (clip.py:339)**  
```python
result = await asyncio.to_thread(_run_ffmpeg, cmd)
```
There is no `asyncio.wait_for` or subprocess `timeout=` parameter. A hung ffmpeg (corrupt source, disk full, impossible filter) will stall the pipeline indefinitely. The CLAUDE.md rules specify "explicit timeouts" as an asyncio best practice.

**[LOW] Custom exception hierarchy missing (clip.py:99)**  
The spec (Section 12.5) requires `src/exceptions.py` with `SupoClipError` as base and `RenderError` as a subclass. The module defines its own `ClipGenerationError(Exception)` instead of inheriting from `RenderError`. The shared exception hierarchy from `src/exceptions.py` does not exist.

### subtitles.py

**[CRITICAL] Context-line / karaoke subtitle approach not implemented (subtitles.py:125–188)**  
The spec (Section 9.2) describes the core subtitle UX: *"a 'context line' approach is used: the active word is shown in the primary colour (e.g., white), and the surrounding words from the current phrase (up to 6 words) are shown in a dimmed secondary colour. This is implemented using ASS inline override tags (`{\c&HBBGGRR&}`) within a single event that groups the phrase."*  
The actual implementation creates one bare `SSAEvent` per word with no phrase grouping, no active/dimmed color distinction, and no ASS inline color tags. The result is isolated single-word flashes with no context. This is a fundamental product-differentiating feature that is entirely absent.

**[HIGH] `SubtitleStyle` missing spec-required fields (subtitles.py:25–48)**  
Spec Section 9.3 defines these fields; actual implementation differences:
- `secondary_color: str` — MISSING (needed for dimmed context words)
- `shadow_color: str` — MISSING (spec: `&H80000000` semi-transparent shadow)
- `bold: bool` — MISSING
- Field naming diverges: spec uses `primary_color`, impl uses `font_color`; spec uses `vertical_margin: int` (25 = bottom %) while impl uses `position_y_pct: int` + `video_height: int`

**[HIGH] `_build_style` does not set `shadowcolor` (subtitles.py:104–122)**  
`ssa_style.shadow = style.shadow_depth` sets depth (line 119) but pysubs2's `SSAStyle` also has a `shadowcolor` attribute that controls the shadow color. This is never set, so the shadow uses the pysubs2 default (opaque black). The spec intends a semi-transparent `&H80000000` shadow. This cannot be configured by users.

**[MEDIUM] `_build_style` does not set `bold` (subtitles.py:104–122)**  
`pysubs2.SSAStyle` has a `bold` attribute. It is never set, so bold text is not achievable regardless of user intent.

---

## 🗑️ Unnecessary — Redundant, unused, or over-engineered code

### clip.py

**[MEDIUM] Three dead `ClipOptions` fields (clip.py:94–96)**  
`logo_path`, `add_transitions`, and `transitions_dir` are declared in the `ClipOptions` dataclass, passed around, logged, and never consumed. They add noise to the public API and tests mock them. If they cannot be implemented soon, they should be removed and re-added when implemented.

**[LOW] `_find_fonts_dir` filesystem walk (clip.py:413–429)**  
Walks up 6 directory levels from `clip.py`'s file location at call time to locate `fonts/`. This is unnecessary filesystem I/O that should be replaced by a configured path from `Config`. Every clip generation call triggers a fresh filesystem stat loop.

---

## 🤫 Silent errors — Swallowed exceptions, unhandled edge cases, silent failures

### clip.py

**[HIGH] cv2 ImportError silently causes wrong crop box for non-landscape video (clip.py:392–396, face_detect.py:170–174)**  
`_get_video_dimensions` returns `(1920, 1080)` (landscape) when cv2 is unavailable. If the user uploads a portrait video (e.g., a phone recording at 1080×1920) and cv2 is not installed, `calculate_crop_box` receives `(1920, 1080)` as frame dimensions. The crop calculation treats the source as landscape, producing a wildly incorrect crop box. The warning `"cv2_unavailable_for_dimensions"` is logged but the caller in `generate_clip` does not surface this to the user, and the ffmpeg crop filter will execute with wrong coordinates. The spec said cv2 was a removed dependency, making this doubly problematic.

**[MEDIUM] `segment_words` empty but no subtitle warning (clip.py:311–320)**  
When `filter_words_for_segment` returns an empty list, `write_ass_file` is not called (correct), but the absence of subtitles is only logged at `info` level. The user will receive a clip with no subtitles and no explanation. If this was unintentional (e.g., timestamps in milliseconds/seconds confusion), it will be hard to debug.

### subtitles.py

**[MEDIUM] All words below minimum duration → silent empty subtitle file (subtitles.py:157–188)**  
If all words have `end_ms - start_ms < 50`, `generate_ass_subtitles` returns a valid ASS string with 0 events. `write_ass_file` then writes this file to disk. The ffmpeg `ass=` filter burns no subtitles. The only log output is a `DEBUG`-level message per skipped word plus an `INFO` with `events=0`. No user-visible warning and no `ClipGenerationError`.

**[LOW] `generate_ass_subtitles` silently ignores style mismatch when no events generated (subtitles.py:157–188)**  
The function logs `"generated ass subtitles"` with `events=0` at INFO without mentioning that no subtitles will appear in the output video. The distinction between "0 events because all words were too short" vs "0 events because empty word list was passed" is not surfaced.

---

## 🐷 Overengineered — Unnecessary complexity

### clip.py

**[LOW] `_find_fonts_dir` upward traversal (clip.py:413–429)**  
Walking up to 6 parent directories from `__file__` to find a `fonts/` folder is overly clever. It will break if run from an installed wheel or a non-standard project layout. Should be a single configured path from `Config`.

---

## 🚮 Tech debt / dead code

### clip.py

**[MEDIUM] `ClipOptions.logo_path`, `add_transitions`, `transitions_dir` (clip.py:87–96)**  
Three public API fields with no implementation. Docstrings say "not yet implemented" and "reserved for future." These are stubs that inflate the API surface and mislead callers.

**[LOW] `# type: ignore[type-arg]` on `subprocess.CompletedProcess` (clip.py:362)**  
`_run_ffmpeg` signature has `subprocess.CompletedProcess  # type: ignore[type-arg]`. This should be `subprocess.CompletedProcess[bytes]` since `capture_output=True` returns `bytes`. The type ignore suppresses a fixable typing gap.

---

## 🛠️ Runtime / output-correctness risks (not caught by unit tests)

These are gaps that 100% unit-test coverage does NOT protect against because tests mock subprocess or use controlled inputs.

1. **ffmpeg filter path escaping (clip.py:212–215):** Any path with a colon, comma, or space will break the `-vf` filter graph at runtime. Tests use clean `/tmp/` paths. Production `TEMP_DIR` is user-configurable.

2. **Wrong crop box when cv2 absent (clip.py:294–300):** If the cv2 optional dependency is not installed (the spec says it was removed), every video will be cropped as if it were 1920×1080 landscape regardless of actual dimensions. This produces vertically-stretched or incorrectly-cropped vertical output.

3. **No karaoke subtitle context (subtitles.py:125–188):** The subtitle output is one bare word per event. Platform algorithms (TikTok, Instagram, YouTube Shorts) reward aesthetic subtitle presentation. The lack of the context-line grouping described in the spec degrades product quality in a way that is invisible in unit tests.

4. **Resolution label misalignment (clip.py:44–48 vs spec 10.1):** If any UI or service layer passes `"720p"` expecting 1080×1920 (as the spec documents), they get 720×1280 instead. The settings page default is `"720p"` per the spec. This means the default quality delivered to users is smaller than intended.

5. **Hung ffmpeg with no timeout (clip.py:339):** In production, a corrupted source video or disk I/O failure can cause ffmpeg to hang indefinitely. The asyncio event loop will be blocked via `to_thread`, but the thread itself runs forever.

---

## Summary table

| ID | File | Severity | Category | Location |
|----|------|----------|----------|----------|
| C1 | clip.py | critical | bad | clip.py:212–215 |
| C2 | clip.py | high | bad | clip.py:44–48 |
| C3 | clip.py | high | missing | clip.py:94–95 |
| C4 | clip.py | high | silent-error | clip.py:392–396 |
| C5 | clip.py | medium | missing | clip.py:339 |
| C6 | clip.py | medium | tech-debt | clip.py:87–96 |
| C7 | clip.py | low | missing | clip.py:99 |
| S1 | subtitles.py | critical | missing | subtitles.py:125–188 |
| S2 | subtitles.py | high | missing | subtitles.py:25–48 |
| S3 | subtitles.py | high | bad | subtitles.py:104–122 |
| S4 | subtitles.py | high | bad | subtitles.py:58 |
| S5 | subtitles.py | high | silent-error | subtitles.py:159–180 |
| S6 | subtitles.py | medium | silent-error | subtitles.py:157–188 |
