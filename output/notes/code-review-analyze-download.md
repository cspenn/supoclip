# Code Review: src/pipeline/analyze.py + src/pipeline/download.py

**Auditor:** Claude Sonnet 4.6 (subagent)
**Date:** 2026-06-29
**Files reviewed:** `src/pipeline/analyze.py` (579 lines), `src/pipeline/download.py` (303 lines)
**Test files cross-referenced:** `tests/unit/test_analyze.py`, `tests/unit/test_download.py`
**Spec reference:** `docs/spec.md` — Clean Consolidation redesign

---

## Summary

Both files are the result of the "Clean Consolidation" migration from a multi-process React/FastAPI system to a single all-Python NiceGUI app. They are functionally operational and pass all 466 tests at 100% coverage. However, both share systemic violations: they use stdlib `logging` instead of the mandated `structlog`, and they instantiate `Config()` directly rather than using the cached `get_config()` singleton. `analyze.py` has a dead parameter (`words`), a subtle silent-skip bug via `suppress(ValueError)` that fails to catch Pydantic `ValidationError`, and is missing the retry logic the spec explicitly requires. `download.py` carries 6 redundant regex patterns that are dead code (pattern 0 is a superset of all others), no maximum video duration guard, and no post-download file-size check.

---

## ✅ Good — Well-Implemented

### analyze.py

**Unified LLM routing (lines 326–554)**
The single public entry point `analyze_transcript` cleanly inspects the model string and routes to either Groq's structured-output API (for `groq:*llama*` models) or Pydantic AI. This consolidates the old `ai.py` + `ai_structured.py` split documented in the spec (Appendix A). The routing logic at `_should_use_structured_output` (line 326) is simple and tested.

**Strong input guards (lines 521–529)**
Empty transcript (`""`, whitespace-only) and sub-50-character transcript are rejected before any LLM call, with clear `AnalysisError` messages.

**Filler-word validation (lines 251–318)**
`validate_segments()` enforces duration bounds and the "Clean Start Rule" (no filler opener) in a single pass. The case-insensitive lower-case check at line 304 is correct. The `_FILLER_STARTS` tuple (lines 33–45) is a module-level constant — not a magic set buried in the function.

**Pydantic model strictness (lines 48–90)**
`TranscriptSegment` uses `ConfigDict(strict=True, extra="forbid")`. The internal `_RawAnalysis` / `_RawSegment` correctly use `ConfigDict(extra="ignore")` to tolerate extra LLM fields without crashing.

**Groq prefix stripping (line 369)**
`bare_model = model_string.split("groq:", 1)[-1]` correctly strips the provider prefix before the API call. Verified in `test_bare_model_name_strips_groq_prefix`.

### download.py

**Async-safe thread offloading (lines 245, 283)**
Both `_run_ydl_download` and `_run_ydl_info` are correctly wrapped with `asyncio.to_thread`, preventing yt-dlp's blocking calls from stalling the event loop.

**stamina retry on DownloadError (lines 215, 255)**
`@stamina.retry(on=DownloadError, attempts=3, wait_initial=1.0, wait_max=4.0)` on both async functions provides exponential backoff without manual retry logic.

**yt-dlp exception translation (lines 188–189, 211–212)**
`yt_dlp.utils.DownloadError` is cleanly translated to the project's `DownloadError`, preventing yt-dlp internals from leaking into callers.

**Broad URL pattern coverage including YouTube Live (lines 36–44)**
The `live/` path was added in commit `a3af789` after a real runtime bug (FileNotFoundError). The test `test_extract_video_id_live_url` validates it.

**SSL verification NOT disabled (line 67)**
`"nocheckcertificate": False` — correct. Would be a security issue if True.

---

## ❌ Bad — Bugs, Anti-Patterns

### analyze.py

**`logging.getLogger` instead of structlog (line 27)**
```python
logger = logging.getLogger(__name__)
```
The spec (section 12.4) and `CLAUDE.md` both explicitly ban `logging` stdlib in application code and mandate `structlog`. This is a banned pattern across the entire `src/` tree. The same violation exists in `download.py` (line 18). All log calls (e.g., lines 277–282, 399, 481) need to be converted to `structlog.get_logger()` with keyword arguments.

**`Config()` instantiated 3 separate times (lines 364, 428, 538)**
```python
cfg = Config()  # in _analyze_with_groq_structured
cfg = Config()  # in _analyze_with_pydantic_ai
cfg = Config()  # in analyze_transcript
```
`src/config.py` exports `get_config()` decorated with `@lru_cache(maxsize=1)` specifically to provide a cached singleton. The direct `Config()` calls bypass this cache, re-parsing the `.env` file up to 3 times per analysis call and defeating the singleton design. Should be `from src.config import get_config; cfg = get_config()`.

**`custom_prompt` never forwarded to `_build_user_prompt` from main call path (line 542)**
```python
# analyze_transcript, line 541-542
system_prompt = build_system_prompt(min_length_s, max_length_s, custom_prompt)  # ✓ passed
user_prompt = _build_user_prompt(transcript_text, min_length_s, max_length_s)    # ✗ NOT passed
```
`_build_user_prompt` accepts `custom_prompt: str | None = None` (line 215) and has working logic to append it (lines 235–237), but `analyze_transcript` never passes `custom_prompt` to it. The user-turn prompt will never contain the custom instructions, even when a user configures them in settings. This is a silent output-correctness defect: the LLM receives the custom instruction in the system prompt but NOT in the user prompt.

### download.py

**`logging.getLogger` instead of structlog (line 18)**
Same banned pattern as in analyze.py.

**Magic number `10_485_760` not a named constant (line 74)**
```python
"http_chunk_size": 10_485_760,
```
Spec section 12.2 bans magic numbers. This 10 MB value should be a module-level named constant (e.g., `_CHUNK_SIZE_BYTES = 10 * 1024 * 1024`) or a config field.

---

## 🤫 Silent Errors — Swallowed Exceptions / Unhandled Edge Cases

### analyze.py

**`suppress(ValueError)` in `_raw_segments_to_transcript_segments` does not catch Pydantic `ValidationError` (lines 468–480)**
```python
for raw in raw_segments:
    with suppress(ValueError):
        start_s, end_s = _raw_segment_to_float_times(raw)
        result.append(
            TranscriptSegment(
                start_time=start_s,
                end_time=end_s,
                text=raw.text,
                score=raw.relevance_score,
                title=raw.title,
            )
        )
        continue
    logger.warning(...)
```
If `TranscriptSegment(...)` raises a Pydantic `ValidationError` (e.g., `score` out of `[0.0, 1.0]`, or a field coercion failure), `suppress(ValueError)` will NOT catch it. `ValidationError` is a `ValueError` subclass in Pydantic v2, so this is actually caught — but this is fragile and depends on Pydantic implementation detail. More critically, the `continue` + `suppress` pattern is genuinely non-obvious: the warning at line 481 executes only when an exception was suppressed, because on the success path `continue` exits the iteration. A future maintainer reading this will likely misread the control flow.

**No validation that timestamps are within actual video duration**
The LLM may hallucinate timestamps far beyond the source video's length. `validate_segments` only checks duration between start and end times — not whether those times fall within the video. An LLM returning `start_time=5000.0, end_time=5030.0` for a 3-minute video would pass all validation and produce a silent ffmpeg failure when clip.py attempts to trim a non-existent segment.

**Groq API errors (non-JSON failures) not caught specifically in `_analyze_with_groq_structured` (lines 374–406)**
Only `json.JSONDecodeError` is caught explicitly. Groq HTTP errors (`groq.APIError`, `groq.AuthenticationError`, `groq.RateLimitError`) propagate to the outer `except Exception` in `analyze_transcript` (line 557), which produces the generic error message `"LLM call failed: {exc}"`. This is not a silently swallowed error, but the loss of error type specificity makes debugging harder.

**`response_content = ""` initialized before try block (line 372)**
This variable is never read after the `try` block exits. The initialization is dead code and a potential source of confusion.

### download.py

**Broad `except Exception` in urlparse fallback (lines 122–123)**
```python
except Exception as exc:
    logger.warning("Error parsing YouTube URL query parameters: %s", exc)
```
The functions `urlparse()` and `parse_qs()` are pure stdlib and should not raise in practice. The broad `except Exception` is overly defensive and masks potential programming errors if the function signature changes.

**No file-size check after download (lines 247–249)**
```python
file_path = find_downloaded_file(output_path, base_stem=video_id)
if not file_path:
    raise DownloadError(...)
```
`find_downloaded_file` returns a path if the file exists, but does not check `file.stat().st_size > 0`. A failed/partial download producing a 0-byte file would be accepted here and fail silently later at transcription or ffmpeg.

---

## ❓ Missing — Gaps vs Spec/PRD

### analyze.py

**No `@stamina.retry` on LLM call (spec section 11.5)**
The spec explicitly requires:
```python
@stamina.retry(on=Exception, attempts=3, wait_initial=2.0, wait_max=10.0)
async def select_segments(...):
```
Neither `analyze_transcript`, `_analyze_with_groq_structured`, nor `_analyze_with_pydantic_ai` has any retry decorator. A transient network error on the LLM call will immediately raise `AnalysisError` to the caller with no retry. `download.py` DOES use `@stamina.retry` — the omission in `analyze.py` is inconsistent.

**`InsufficientSegmentsError` exception class not defined (spec section 12.5)**
The spec defines a custom exception hierarchy in `src/exceptions.py` with `InsufficientSegmentsError` as a distinct subclass of `AnalysisError`. The current code raises generic `AnalysisError("No valid segments found...")` (lines 563–569). This means callers cannot distinguish between "LLM API error" and "all segments rejected" without string matching the error message.

**`words` parameter exists but is never used (lines 497–509)**
```python
async def analyze_transcript(
    transcript_text: str,
    words: list[dict],   # ← accepted, never referenced in body
    ...
)
```
The docstring admits: "Currently used for context; future versions may use it for sub-word alignment snapping." This is a YAGNI dead parameter. The spec's sub-word alignment snapping is never implemented. The parameter pollutes the API surface and all call sites.

**Public entry point name and signature differ from spec (spec section 4.11)**
Spec defines: `select_segments(transcript: TranscriptData, settings: ClipSettings) -> list[ClipSegment]`
Actual: `analyze_transcript(transcript_text: str, words: list[dict], min_length_s: float, max_length_s: float, custom_prompt: str | None) -> list[TranscriptSegment]`

The spec uses a `TranscriptData` object and a `ClipSettings` object; the implementation uses primitive parameters. This makes it harder to add new settings fields (each requires a new parameter) and breaks the pattern used elsewhere in the pipeline.

### download.py

**No `MAX_VIDEO_DURATION` guard (spec section 8.3)**
The spec defines `MAX_VIDEO_DURATION=3600` (seconds) as a config field to reject overlength downloads. `download_youtube_video` does not call `get_video_info` first to check duration, nor does `_build_ydl_opts` reference `config.max_video_duration`. A user submitting a 10-hour video will trigger a full download before failure.

**`get_video_info` returns untyped `dict[str, Any]` (lines 285–298)**
The return type is undocumented structurally. Callers accessing `.get("title")` silently get `None` when the key is missing. A `TypedDict` or Pydantic model would catch missing fields at type-check time.

---

## 🗑️ Unnecessary / Tech Debt / Dead Code

### analyze.py

**`words` dead parameter — see Missing section above**

**`_build_user_prompt` `custom_prompt` parameter is unused in practice**
Since `analyze_transcript` never passes `custom_prompt` to `_build_user_prompt`, the entire `custom_prompt` branch in `_build_user_prompt` (lines 235–237) is unreachable from the main path. It is tested in `TestBuildUserPrompt.test_custom_prompt_appended` but that test calls `_build_user_prompt` directly, not via `analyze_transcript`.

### download.py

**URL patterns 1–6 are dead code — pattern 0 is a superset (lines 37–43)**
Pattern 0 (line 37):
```python
r"(?:youtube\.com/(?:.*v=|v/|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
```
This single pattern matches:
- `youtube.com/watch?v=` via the `.*v=` arm
- `youtube.com/embed/` via the `embed/` arm
- `youtube.com/v/` via the `v/` arm
- `youtube.com/shorts/` via the `shorts/` arm
- `youtube.com/live/` via the `live/` arm
- `youtu.be/` via the `youtu\.be/` arm

Because `re.search` (not `re.match`) is used (line 109) and the loop exits on first match (line 110–113), patterns 1–5 (lines 38–42) will NEVER fire if pattern 0 matches — which it will for all standard YouTube URLs. Pattern 6 (`youtube.com/live/`) is also now redundant since `live/` was added to pattern 0 in commit `a3af789`. Pattern 7 (`m.youtube.com`) has marginal value since `m.youtube.com` contains the substring `youtube.com` and is caught by pattern 0 via `re.search`.

**Remediation:** Remove patterns 1–7 and keep only pattern 0 plus the urlparse fallback.

**`_run_ydl_download` and `_run_ydl_info` exist only to translate one exception type**
These private functions (lines 175–212) are thin wrappers whose only contribution is translating `yt_dlp.utils.DownloadError` into the project's `DownloadError`. The logic could be inlined into the async functions with a `try/except`. At present they add two extra function definitions that tests must specifically cover to achieve 100% coverage.

---

## 🐷 Overengineered / Unnecessary Complexity

### analyze.py

**`suppress(ValueError)` + `continue` pattern (lines 468–480)**
The pattern of using `contextlib.suppress` to route control flow via `continue` is unnecessarily clever. The semantically identical code is:
```python
try:
    start_s, end_s = _raw_segment_to_float_times(raw)
    result.append(TranscriptSegment(...))
except ValueError:
    logger.warning(...)
```
The `suppress` approach hides the intent, makes it harder to add additional exception types, and is a footgun for future maintainers.

---

## 🔧 Runtime / Output Correctness Risks

### analyze.py (core output risk)

**`custom_prompt` silently not included in user prompt (analyze.py:542)**
This is the most impactful output-correctness issue. When a user configures a custom AI prompt in Settings (e.g., "Focus on actionable tips"), it is appended to the SYSTEM prompt but not the USER prompt. Many LLMs (particularly OpenAI, Anthropic) give stronger weight to instructions that appear in both turns. Local LLMs in particular often ignore long system prompts. Result: custom prompt instructions may be silently ignored in practice, making the Settings page's custom AI prompt feature unreliable.

**No video-duration bound check on LLM-returned timestamps**
A video of duration 2:30 (150 seconds) could receive clips with `start_time=300.0, end_time=330.0` from a hallucinating LLM. These pass duration validation (30s duration is valid) but will produce silent ffmpeg failures when clip.py tries to seek past the end of the video. ffmpeg's `-ss 300 -to 330 -i source.mp4` on a 150-second file produces a 0-byte or nearly-empty output, and the clip pipeline will either fail or produce a blank clip.

### download.py (output risk)

**0-byte file not detected after download**
If yt-dlp writes a 0-byte file (which can happen with partial failures when `ignoreerrors: False` is set but the write completes before the error propagates), `find_downloaded_file` will return the file path as valid, and downstream transcription will fail with a confusing error rather than a clear `DownloadError`.

---

## 📋 Spec Divergences Table

| Item | Spec Says | Actual |
|------|-----------|--------|
| Logging framework | structlog | stdlib logging (both files) |
| Config access | `get_config()` singleton | `Config()` per call |
| Retry on analyze | `@stamina.retry(attempts=3)` | No retry |
| Exception class | `InsufficientSegmentsError` | Generic `AnalysisError` |
| Function name | `select_segments(transcript, settings)` | `analyze_transcript(text, words, ...)` |
| Max video duration | Guard against `MAX_VIDEO_DURATION` | Not implemented |
| URL patterns | N/A (not specified) | 6 redundant patterns |
| File size check | "validate output file is non-empty" | Only existence check |

---

## Line-Level Evidence Index

| Finding | File | Lines |
|---------|------|-------|
| stdlib logging | analyze.py | 27 |
| stdlib logging | download.py | 18 |
| Config() not singleton | analyze.py | 364, 428, 538 |
| custom_prompt dropped from user prompt | analyze.py | 542 |
| words dead parameter | analyze.py | 497–498 |
| suppress(ValueError) + continue pattern | analyze.py | 468–480 |
| No retry on LLM calls | analyze.py | 494–575 (no decorator) |
| No InsufficientSegmentsError | analyze.py | 563–569 |
| Timestamp not bounds-checked vs duration | analyze.py | 561 (validate_segments) |
| Redundant URL patterns | download.py | 37–43 |
| Magic number 10_485_760 | download.py | 74 |
| No MAX_VIDEO_DURATION guard | download.py | 216–252 |
| No 0-byte file check | download.py | 247–249 |
| Broad except Exception | download.py | 122–123 |
| response_content dead init | analyze.py | 372 |
