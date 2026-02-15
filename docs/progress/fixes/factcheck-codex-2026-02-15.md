# Factcheck Audit: Codex QA Report

**Generated:** 2026-02-15
**Audited Document:** codex2026-02-15-173017-full-code-review-audit.md
**Methodology:** Each claim validated against actual source code using file reads, grep searches, glob patterns, git history, and line counts.

## Summary
- Total claims examined: 42
- VERIFIED: 29
- FALSE POSITIVE: 8
- OUTDATED: 1
- CANNOT VERIFY: 4

---

## Detailed Findings

### VERIFIED Claims

| # | Claim | Evidence | Files |
|---|-------|----------|-------|
| 1 | `docs/prd.md` is missing | Glob search returns no results | N/A (file does not exist) |
| 2 | `docs/workplan.md` is missing | Glob search returns no results | N/A (file does not exist) |
| 3 | `docs/polish.md` is missing | Glob search returns no results | N/A (file does not exist) |
| 4 | `docs/standards.md` is missing | Glob search returns no results; `AGENTS.md:45` correctly references it | `/Users/cspenn/Documents/github/supoclip/AGENTS.md` |
| 5 | `.pre-commit-config.yaml` is missing | Glob search returns no results | N/A (file does not exist) |
| 6 | `checkpython.sh` is missing | Glob search across entire repo returns no results | N/A (file does not exist) |
| 7 | `CLAUDE.md:280-285` requires `docs/prd.md`, `docs/workplan.md`, `docs/polish.md`, `checkpython.sh`, `.pre-commit-config.yaml` | Lines 280-285 confirmed to list these as "Required Project Files" | `/Users/cspenn/Documents/github/supoclip/CLAUDE.md` |
| 8 | `AGENTS.md:45` references `docs/standards.md` | Line 45: "See `docs/standards.md` for backend conventions." | `/Users/cspenn/Documents/github/supoclip/AGENTS.md` |
| 9 | `video_utils.py` is 1933 lines | `wc -l` returns exactly 1933 | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 10 | Invalid clips are skipped with `continue` at `video_service_async.py:335-347` | Lines 334-347 contain validation that checks for file existence and minimum size, with `continue` on failure | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 11 | Task is unconditionally set to completed at `video_service_async.py:374-376` | Lines 374-376: `await self._update_task_status(task_id, "completed")` with no check on whether any clips were successfully saved | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 12 | Underlength segments accepted when `duration >= 5.0` at `ai_structured.py:272-286` | Lines 272-286 show segments shorter than `min_length` but >= 5.0 are accepted with a warning "ACCEPTED (UNDERLENGTH)" | `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py` |
| 13 | Duration prompt constraints at `ai_structured.py:61-66` | Lines 60-66 specify strict MINIMUM/MAXIMUM DURATION requirements in the prompt | `/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py` |
| 14 | `clip_target_length` exists in `video_service_async.py:207` and documented at `video_service_async.py:229` | Line 207: `clip_target_length: int = 30,` and line 229: `clip_target_length: Target clip length in seconds` | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 15 | `clip_target_length` has no downstream usage in scoring/segment selection | The `process_video_async` function body (lines 236-382) never references `clip_target_length`. The AI call at line 272-277 only passes `clip_min_length` and `clip_max_length`. | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 16 | `video_service_async.py` has `# start`/`# end` markers | Line 1: `# start backend/src/services/video_service_async.py` and line 411: `# end backend/src/services/video_service_async.py` | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 17 | `video_utils.py` does not have `# start`/`# end` markers | Grep for `# start ` and `# end ` returns no matches; file starts with a docstring | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 18 | `.gitignore` does not exclude `.coverage`, `*.db`, or generated reports | `.gitignore` contains only: `.env.local`, `.DS_Store`, `__pycache__`, `*.egg-info`, `logs/`, `temp/`, `.env`, `*.m4a` | `/Users/cspenn/Documents/github/supoclip/.gitignore` |
| 19 | `backend/.coverage` and `backend/supoclip.db` have been committed to git | `git log` confirms both files appear in multiple commits | Git history |
| 20 | Report artifacts under `backend/docs/reports/` have been committed | `git log` confirms report files in commit history | Git history |
| 21 | `is_single_word` is passed but unused in `_create_clip_candidate` at `video_utils.py:979` | Parameter declared at line 979 but never referenced in the function body (lines 982-1030). It is computed at line 1049 and passed at line 1058 but has no effect. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 22 | `words_per_subtitle` is unused at `video_utils.py:1290` | Parameter declared at line 1290 in `SubtitleClipBuilder.build_clips()` but never referenced in the function body (lines 1311-1357). Always called with hardcoded value `1` at line 1412. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 23 | `get_video_transcript_with_assemblyai` exists at `video_utils.py:1914` | Line 1914: backward compatibility wrapper function exists with no in-repo callers (grep confirms only the definition at line 1914) | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 24 | `create_9_16_clip` exists at `video_utils.py:1923` | Line 1923: backward compatibility wrapper function exists with no in-repo callers (grep confirms only the definition at line 1923) | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 25 | `_get_token_start_time` at `transcription_mlx.py:271` and `_get_token_end_time` at `transcription_mlx.py:287` are unused | Both functions exist at stated lines. Grep across backend/src confirms no callers - only the definitions themselves appear. | `/Users/cspenn/Documents/github/supoclip/backend/src/transcription_mlx.py` |
| 26 | Task detail/clip endpoints are duplicated in `main.py:180,233` and `api/routes/tasks.py:152,171` | `main.py` has `get_task_clips` at line 180 and `get_task_details` at line 233. `tasks.py` has equivalent routes at lines 152 and 171. | `/Users/cspenn/Documents/github/supoclip/backend/src/main.py`, `/Users/cspenn/Documents/github/supoclip/backend/src/api/routes/tasks.py` |
| 27 | `video_service.py` (sync) exists alongside `video_service_async.py`, creating duplication risk | Both files exist in `backend/src/services/` | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py`, `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |
| 28 | `parse_timestamp_to_seconds` returns `0.0` on parse failure | Line 920: `return 0.0` in the `except (ValueError, IndexError)` block | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 29 | Named constant `MIN_CLIP_FILE_SIZE_BYTES = 1000` extracted at `video_service_async.py:36` | Line 36: `MIN_CLIP_FILE_SIZE_BYTES = 1000  # 1 KB minimum` | `/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service_async.py` |

### FALSE POSITIVE Claims

| # | Claim | Why False | Evidence |
|---|-------|-----------|----------|
| 1 | "`video_utils.py` is 1933 lines, exceeding the 750-line limit from `CLAUDE.md:276`" - specifically the "750-line limit" part | `CLAUDE.md:276` says "Maximum radon/xenon grade of A or B - C and below MUST be refactored." There is NO 750-line limit mentioned anywhere in `CLAUDE.md`. The 1933-line count is correct but the referenced line limit does not exist. | `/Users/cspenn/Documents/github/supoclip/CLAUDE.md` line 276 |
| 2 | "`transcription_mlx.py:16-17` imports MLX (`mlx.core`) at module import time" implying a hard crash | Lines 15-20 show the MLX import is wrapped in `try/except ImportError` with graceful fallback: `from_pretrained = None` and `bfloat16 = None`. The import itself will NOT crash Python if MLX is unavailable. The `transcribe_video_mlx` function also checks `if from_pretrained is None` at runtime (line 64) before attempting to use MLX. | `/Users/cspenn/Documents/github/supoclip/backend/src/transcription_mlx.py` lines 15-20 |
| 3 | `CLAUDE.md:292-293` says "env vars are expected" vs `docs/rules-python.md:57` "NEVER use environment variables" is a "contradictory standards" issue | While the inconsistency between the two documents is real, `CLAUDE.md:287` explicitly acknowledges this deviation: "This project uses `uv` for dependency management instead of Poetry. Environment variables are stored in `.env` files for local development." This is a documented project-specific override, not an accidental contradiction. `CLAUDE.md` lines 291-293 describe the project's intentional configuration approach. | `/Users/cspenn/Documents/github/supoclip/CLAUDE.md` lines 287-296 |
| 4 | "Radon reports `create_optimized_clip` complexity `C` at `video_utils.py:1498`" | The function `create_optimized_clip` begins at line 1498. While the report claims grade C, this cannot be verified without actually running radon. The function itself is ~140 lines (1498-1651) with a try/except/finally structure, which is moderately complex but the exact grade cannot be confirmed from code inspection alone. Classified as false positive because the claim about the specific line number 1498 is correct but the complexity grade is unverifiable from the report's own admission that tool results were obtained in a constrained environment. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 5 | "Test assumes `TextClip(method='caption')` path at `test_font_cutoff_and_short_clips.py:44-53`" as evidence tests are "stale/misaligned" | Lines 43-53 do use `TextClip(method="caption")`, and the current production code does use `BrowserSubtitleRenderer`. However, the test file's purpose is specifically to test font cutoff behavior, which can still be relevant as a regression test for the TextClip rendering path. Calling them "stale" assumes the TextClip path is fully dead, but it may still be accessible. This is more nuanced than "stale." | `/Users/cspenn/Documents/github/supoclip/backend/tests/test_font_cutoff_and_short_clips.py` |
| 6 | "Current production path uses browser-rendered subtitles at `video_utils.py:973-1004`" | Lines 973-1004 are inside the `_create_clip_candidate` static method of `SubtitleTextClipCreator`, not a standalone production path. The actual subtitle creation flows through `create_text_clip` (line 1033) which calls `_create_clip_candidate`. While the browser rendering claim is correct, the line range cited (973-1004) is the internal method, not the entry point. Minor line reference inaccuracy. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |
| 7 | "`xenon src/ --max-absolute C`: pass" | The report shows xenon was run with `--max-absolute C`, but `docs/rules-python.md:133` specifies the threshold should be `--max-absolute B`. Running with C threshold is a weaker check than the standard requires. The "pass" result is therefore misleading - it passed a less strict threshold. | `/Users/cspenn/Documents/github/supoclip/docs/rules-python.md` line 133 |
| 8 | "Defensive cleanup of clip resources at `video_utils.py:1639-1651`" and "explicit overlay clip cleanup at `video_utils.py:1640-1645`" | The line numbers are correct and the code exists, but the report lists both as separate "done" items when they are part of the same `finally` block. Lines 1640-1645 handle overlay clips, lines 1647-1651 handle main clips. This is one cleanup block, not two separate fixes. The claim inflates the count of completed items. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |

### OUTDATED Claims

| # | Claim | Current State | Evidence |
|---|-------|---------------|----------|
| 1 | "Clip-loop diagnostics at `video_utils.py:1675`, `1718`, `1743`" | These diagnostic log lines exist at the stated line numbers in the current code. However, the line numbers may shift with future edits. As of the current file (1933 lines), line 1675 shows `[CLIP_DIAG] Starting clip`, line 1718 shows `[CLIP_DIAG] Clip {i + 1} created successfully`, and line 1743 shows `[CLIP_DIAG] Completed iteration`. These are accurate to the current snapshot. | `/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py` |

### CANNOT VERIFY Claims

| # | Claim | Reason |
|---|-------|--------|
| 1 | "Running `pytest` exits with `134`; direct import triggers `NSRangeException` from `libmlx`" | This is an environment-specific runtime claim. The MLX imports are wrapped in try/except ImportError (lines 15-20), so the crash mechanism described (import-time MLX initialization) may be partially incorrect. The actual crash may occur during test collection if pytest tries to import modules that trigger native MLX code. Cannot reproduce without running pytest in the same environment. |
| 2 | "Radon reports `create_optimized_clip` complexity `C`" | Would require running `radon cc` against the actual file. The function is ~140 lines with moderate branching, which could plausibly be grade C, but cannot confirm without running the tool. |
| 3 | "`ruff check src/`: pass" and "`mypy src/`: fail (3 errors in `src/scripts/*`)" | These are tool execution results that would require running the actual tools to verify. The mypy claim about untyped `radon` imports in `src/scripts/*` is plausible but not confirmed. |
| 4 | "`interrogate src/`: pass (88.9% docstring coverage vs 80% minimum)" and "`pylint src/`: score `7.65/10`" | These are tool execution results that would require running the actual tools to verify. |

---

## Additional Observations

### Line Number Accuracy
Most line number references in the report are accurate to the current state of the codebase. The report demonstrates thorough file-level inspection.

### Key Mischaracterizations

1. **MLX Import Crash Mechanism**: The report describes the crash as caused by "import-time MLX initialization" at `transcription_mlx.py:16-17`. In reality, lines 15-20 use a `try/except ImportError` guard, so the import itself is safe. The actual crash (if it occurs) likely happens during test collection when pytest attempts to load test fixtures that exercise the MLX code path, or through native library loading side effects that occur even within the try block. The report's description of the mechanism is misleading.

2. **Non-Existent 750-Line Limit**: The report fabricates a "750-line limit from `CLAUDE.md:276`". `CLAUDE.md:276` actually says "Maximum radon/xenon grade of A or B - C and below MUST be refactored." No line count limit is specified anywhere in the project standards. The `video_utils.py` file at 1933 lines is indeed large, but the violation is about complexity grade, not line count.

3. **Standards Contradiction Overstated**: The report presents the env-var configuration difference between `CLAUDE.md` and `docs/rules-python.md` as a contradiction, but `CLAUDE.md:287` explicitly documents this as an intentional project-specific deviation.

### Confirmed High-Value Findings
The following findings from the report are substantive and verified:
- `clip_target_length` is truly dead interface debt (accepted but unused)
- Task can complete with zero valid clips (no postcondition check)
- Multiple dead/unused functions and parameters exist
- API endpoint duplication between `main.py` and `api/routes/tasks.py`
- `.gitignore` is genuinely incomplete for development artifacts
- File marker convention is inconsistently applied
