# SupoClip QA Audit Report

Generated: 2026-02-15 17:30:17 (local)
Scope: `backend` implementation review vs `CLAUDE.md`, `AGENTS.md`, and available repo requirements artifacts.
Constraint noted: `docs/prd.md` is missing, so PRD-level completion cannot be fully verified.

## Severity-Ranked Findings

### Critical

1. Missing PRD and required governance artifacts make full requirements validation impossible.
- Evidence:
  - `CLAUDE.md:280`-`CLAUDE.md:285` requires `docs/prd.md`, `docs/workplan.md`, `docs/polish.md`, `.pre-commit-config.yaml`, `checkpython.sh`.
  - `AGENTS.md:45` points to `docs/standards.md`, which is also missing.
  - Repo check confirms missing files at root: `docs/prd.md`, `docs/workplan.md`, `docs/polish.md`, `docs/standards.md`, `.pre-commit-config.yaml`.
- Impact: No objective acceptance baseline; “done/not done” can only be partially inferred.
- Root cause: Requirements governance and repo hygiene are not enforced by CI/pre-commit.

2. QA gate is non-functional on this host because importing the core video module hard-crashes Python.
- Evidence:
  - `backend/src/video_utils.py:24` imports `transcribe_video_mlx` at module import time.
  - `backend/src/transcription_mlx.py:16`-`backend/src/transcription_mlx.py:17` imports MLX (`mlx.core`) at module import time.
  - Running `pytest` exits with `134`; direct import of `tests.unit.test_video_utils_timestamps` triggers `NSRangeException` from `libmlx` before tests execute.
- Impact: Unit tests for touched code cannot run reliably in non-MLX-capable environments; regressions can ship undetected.
- Root cause: Heavy runtime dependencies initialized during import instead of lazy/runtime feature-gated execution.

### High

3. Async job can be marked `completed` even when all generated clips are invalid/skipped.
- Evidence:
  - Invalid clip files are skipped with `continue` in `backend/src/services/video_service_async.py:335`-`backend/src/services/video_service_async.py:347`.
  - Task is still unconditionally set to completed at `backend/src/services/video_service_async.py:374`-`backend/src/services/video_service_async.py:376`.
- Impact: Silent false-positive success state (`completed` with zero usable clips).
- Root cause: Missing postcondition/acceptance check before status transition.

4. Configured minimum clip length is not strictly enforced despite prompt claims.
- Evidence:
  - Underlength segments are accepted when `duration >= 5.0` at `backend/src/ai_structured.py:272`-`backend/src/ai_structured.py:286`.
  - This conflicts with strict prompt constraints generated in `backend/src/ai_structured.py:61`-`backend/src/ai_structured.py:66`.
- Impact: User-requested duration constraints can still be violated.
- Root cause: Intentional “hook integrity” policy embedded in validation without matching product/spec update.

5. `clip_target_length` is plumbed through API/service but never used in selection logic.
- Evidence:
  - Parameter exists in `backend/src/services/video_service_async.py:207` and is documented at `backend/src/services/video_service_async.py:229`.
  - No downstream usage in scoring/segment selection.
- Impact: User preference appears accepted but has no behavioral effect.
- Root cause: Incomplete parameter implementation (interface-first, logic not finished).

### Medium

6. Core video module violates stated maintainability constraints.
- Evidence:
  - `backend/src/video_utils.py` is 1933 lines (repo measurement), exceeding the 750-line limit from `CLAUDE.md:276`.
  - Radon reports `create_optimized_clip` complexity `C` at `backend/src/video_utils.py:1498`, conflicting with “no grade C+” rules in `docs/rules-python.md:48`.
- Impact: Higher defect density risk; difficult regression isolation.
- Root cause: Accretive edits in a monolithic module without structural refactor.

7. File marker convention is inconsistently applied.
- Evidence:
  - Required marker convention documented at `CLAUDE.md:274` and `docs/rules-python.md:45`.
  - `backend/src/services/video_service_async.py` follows markers (`# start`/`# end`), but `backend/src/video_utils.py` does not.
- Impact: Standards drift and inconsistent maintainability.
- Root cause: No automated lint/check for repository-specific conventions.

8. Repository hygiene around generated/stateful artifacts is weak.
- Evidence:
  - Recent commits include `backend/.coverage`, `backend/supoclip.db`, and report artifacts under `backend/docs/reports/`.
  - Root `.gitignore` (`.gitignore:1`-`.gitignore:8`) does not exclude common stateful artifacts like `.coverage`, `*.db`, or generated reports.
- Impact: Noisy diffs, accidental state coupling, difficult review signal.
- Root cause: Incomplete ignore policy and lack of pre-commit guardrails.

### Low

9. Some tests are stale/misaligned with current subtitle implementation.
- Evidence:
  - `backend/tests/test_font_cutoff_and_short_clips.py` assumes `TextClip(method="caption")` path (`backend/tests/test_font_cutoff_and_short_clips.py:44`-`backend/tests/test_font_cutoff_and_short_clips.py:53`).
  - Current production path uses browser-rendered subtitles (`backend/src/video_utils.py:973`-`backend/src/video_utils.py:1004`).
- Impact: Tests can no longer verify real behavior and may create false confidence/confusion.
- Root cause: Test suite not maintained alongside architecture changes.

## Done vs Not Done

### Done
- Added defensive cleanup of clip resources in `create_optimized_clip` (`backend/src/video_utils.py:1639`-`backend/src/video_utils.py:1651`).
- Added explicit overlay clip cleanup (`backend/src/video_utils.py:1640`-`backend/src/video_utils.py:1645`).
- Added clip file existence/size validation before DB insert (`backend/src/services/video_service_async.py:335`-`backend/src/services/video_service_async.py:347`).
- Replaced magic number with named constant (`backend/src/services/video_service_async.py:36`).
- Added clip-loop diagnostics (`backend/src/video_utils.py:1675`, `backend/src/video_utils.py:1718`, `backend/src/video_utils.py:1743`).

### Not Done
- PRD-traceable acceptance verification is not possible because PRD file is missing.
- Strict min/max duration enforcement remains logically inconsistent with prompt contract.
- `clip_target_length` is not implemented behaviorally.
- No targeted regression tests were added for CLIPS/QA fixes (resource cleanup, invalid clip handling, status semantics).
- “Completed with zero clips” condition is not prevented.

## 8-Dimension QA Matrix

### ✅ What’s good
- Resource cleanup work is directionally correct and reduces leak risk in normal clip path.
- Invalid clip file validation prevents obvious bad records from entering DB.
- Diagnostic logging additions improve observability of clip-loop progression.
- Lint/type checks on touched files are clean (`ruff`, `mypy` passed on reviewed files).

### ❌ What’s bad
- Full review against PRD is blocked by missing `docs/prd.md`.
- Test execution is brittle/non-portable due import-time MLX initialization crash.
- Async status semantics can misreport failed outcomes as completed.
- Duration policy contradicts user constraints and prompt contract.

### ❓ What’s missing
- Missing required docs and pre-commit config listed in `CLAUDE.md`.
- Missing enforceable CI checks for repo-specific conventions (file markers, artifact hygiene, complexity threshold).
- Missing behavioral tests for new CLIPS/QA changes.

### 🗑️ What’s unnecessary
- Tracking generated/stateful artifacts (`.coverage`, DB snapshots, generated report files) in normal development commits.
- Stale tests built around superseded subtitle rendering internals.

### 🛠️ What’s fixed
- Clip resource cleanup path improved.
- Overlay clip cleanup added.
- DB write validation for missing/tiny clips added.
- Magic number extraction performed.

### 💥 What’s newly broken
- No clear evidence that these specific QA commits introduced a new runtime regression in reviewed code paths.
- However, they did not close existing high-risk gaps (completion semantics, duration contract mismatch, test portability).

### 🤫 Silent errors likely lurking
- False success: tasks can end `completed` with zero valid clips.
- User settings silently ignored: `clip_target_length` accepted but unused.
- Invalid timestamp parsing returns `0.0` in parser pathways, which can quietly alter downstream behavior rather than fail fast.

### 🐷 Overengineered / overcomplicated
- `backend/src/video_utils.py` remains a monolith with mixed responsibilities (transcription IO, face detection, subtitle rendering, compositing, transitions, parsing).
- Complexity concentration in `create_optimized_clip` (grade C) indicates overdue decomposition.

### 🚮 Technical debt / dead code
- `clip_target_length` is interface debt: accepted/documented but unused in processing logic (`backend/src/services/video_service_async.py:207`, `backend/src/services/video_service_async.py:229`).
- Confirmed dead parameters in production code:
  - `is_single_word` is passed but unused (`backend/src/video_utils.py:979`, `backend/src/video_utils.py:1049`, `backend/src/video_utils.py:1058`).
  - `words_per_subtitle` is unused (`backend/src/video_utils.py:1290`).
- Likely dead compatibility wrappers with no in-repo call sites:
  - `backend/src/video_utils.py:1914` (`get_video_transcript_with_assemblyai`)
  - `backend/src/video_utils.py:1923` (`create_9_16_clip`)
- Unused helper functions in transcription module with no in-repo call sites:
  - `backend/src/transcription_mlx.py:271` (`_get_token_start_time`)
  - `backend/src/transcription_mlx.py:287` (`_get_token_end_time`)
- API surface duplication debt: task detail/clip endpoints are defined in both main app and router:
  - `backend/src/main.py:180`, `backend/src/main.py:233`
  - `backend/src/api/routes/tasks.py:152`, `backend/src/api/routes/tasks.py:171`
- Duplicated business logic across sync/async services (also flagged by `pylint` duplicate-code), increasing drift risk between `backend/src/services/video_service.py` and `backend/src/services/video_service_async.py`.

## Systemic Root Causes

1. Requirements governance failure.
- Missing required docs and no enforced traceability workflow.

2. Environment-dependent side effects at import time.
- Core modules initialize optional heavy dependencies too early.

3. Quality gate misalignment.
- Standards are documented but not mechanized (marker checks, artifact controls, complexity thresholds).

4. Contradictory standards documents.
- `CLAUDE.md` says env vars are expected (`CLAUDE.md:292`-`CLAUDE.md:293`), while `docs/rules-python.md:57` says “NEVER use environment variables.”
- This inconsistency makes compliance ambiguous and encourages ad-hoc decisions.

## Verification Notes

- `checkpython.sh` was intentionally not used per request.
- Commands run included static analysis (`ruff`, `mypy`, `radon`) and targeted pytest attempts.
- Pytest results were not reliable due process abort (`exit 134`) triggered during import-time MLX initialization.

## Rules-Python Quality Check Results

Executed against `backend` per `docs/rules-python.md` toolchain:

- Tier 1:
  - `ruff check src/`: pass.
  - `mypy src/`: fail (3 errors in `src/scripts/*` due untyped `radon` imports).
  - `pytest tests/`: fail to run (process abort `134` due MLX initialization crash path).
  - `deptry src/`: pass (no dependency issues).
- Tier 2:
  - `radon cc src/ -a -nb`: fail threshold intent (grade `C` present, e.g., `create_optimized_clip`).
  - `bandit -r src/`: 4 medium findings (bind-all-interfaces, SQL-expression warning, `/tmp` usage warning).
  - `interrogate src/`: pass (88.9% docstring coverage vs 80% minimum).
  - `pylint src/`: heavy findings, score `7.65/10`, including unused args, duplicate code, broad exceptions, oversized module.
- Tier 3:
  - `xenon src/ --max-absolute C`: pass.
  - `semgrep --config auto src/`: blocked by local CA/cert trust-anchor failure.
  - `sqlfluff lint --dialect sqlite`: fail (multiple migration SQL style/parse issues, plus dialect mismatch on procedural SQL).
  - `pip-audit --cache-dir /tmp/pip-audit-cache`: blocked by network/DNS constraints to `pypi.org` in this environment.

## Overall Assessment

Implementation shows incremental tactical fixes, but QA maturity is below “full confidence” due missing requirement artifacts, brittle testability, and unresolved behavioral contract gaps. The strongest risk is not a single line defect; it is the current system’s inability to provide trustworthy verification signals.
