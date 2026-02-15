# SupoClip Full Code Review Audit

**Generated:** 2026-02-15 22:30:00 (local)
**Auditor:** Claude Opus 4.6
**Scope:** Full codebase review — backend (Python/FastAPI), frontend (Next.js 15), waitlist, test infrastructure
**Evaluated Against:** CLAUDE.md, AGENTS.md, docs/rules-python.md, docs/orientation.md
**Note:** `docs/prd.md` is missing; PRD-level acceptance criteria cannot be verified.

---

## Executive Summary

The codebase shows evidence of disciplined incremental work (VUW-style commits with checkpoints, targeted QA campaigns). However, **systemic structural issues** undermine the quality foundation: a 1933-line monolith module, legacy typing imports across 25 files, a Config class that bypasses Pydantic validation, duplicate API endpoints, and a test suite that can't reliably run due to native MLX crashes. The strongest risk is not any single defect — it is the inability to produce trustworthy verification signals from the quality gate.

**Overall Health Score: 5.5 / 10**

---

## 8-Dimension QA Matrix

### ✅ What's Good

1. **VUW commit discipline is real.** The last 20 commits follow the VUW pattern with pre/post checkpoints (SYNC-001 through QA-005). Each commit is small, focused, and verifiable. This is the strongest process indicator in the repo.

2. **No bare `except:` clauses anywhere in production code.** Every exception handler catches a specific type. Zero violations found across all 42 source files.

3. **No mutable default arguments.** Not a single `def func(x=[])` or `def func(x={})` found. Clean.

4. **No hardcoded secrets.** All API keys, tokens, and credentials are externalized via `os.getenv()` in `config.py`. No leaked credentials in source.

5. **Type hints are comprehensive.** All public functions and methods across `main.py`, `ai.py`, `youtube_utils.py`, `database.py`, `config.py`, and service files have return type annotations and parameter types.

6. **Docstring coverage is strong (88.9%).** `interrogate` reports above the 80% minimum threshold. Google-style docstrings are used consistently in key modules.

7. **Resource cleanup improvements landed (QA-003, QA-004).** Clip resources are now cleaned up in exception handlers. Overlay/subtitle/logo clips get proper `close()` calls. `contextlib.suppress` replaces bare try/except for cleanup.

8. **Clip validation before DB insert (CLIPS-002).** Invalid/tiny clip files are now skipped before writing to the database — prevents ghost records.

9. **Named constant extraction (QA-005).** `MIN_CLIP_FILE_SIZE_BYTES = 1000` replaces a magic number at `video_service_async.py:36`.

10. **Repository pattern for data access.** `repositories/task_repository.py`, `clip_repository.py`, and `source_repository.py` provide clean data access abstractions.

---

### ❌ What's Bad

#### CRITICAL-001: `video_utils.py` is 1933 lines (2.58x the 750-line limit)

- **File:** `backend/src/video_utils.py`
- **Standard violated:** CLAUDE.md line 276 ("Maximum radon/xenon grade of A or B"), rules-python.md ("max 750 lines, no file grade C+")
- **Measured:** `wc -l` = 1933 lines; radon reports `create_optimized_clip` at complexity grade C
- **Content:** Mixed responsibilities — transcript parsing, face detection, smart cropping, subtitle rendering orchestration, clip compositing, transition effects, format conversion, compatibility wrappers, resolution presets. This is 6-8 distinct modules compressed into one file.
- **Root cause:** Accretive development without refactoring gates. No CI check enforces the line limit or complexity threshold.
- **Impact:** Highest defect density risk in the codebase. Any change to this file risks unintended side effects across unrelated functionality. Grade C function violates the "A or B only" standard.

#### CRITICAL-002: MLX import chain causes native SIGABRT in non-Apple-Silicon environments

- **File:** `backend/src/transcription_mlx.py:15-20` → imported by `backend/src/video_utils.py:24-26`
- **Current mitigation:** `try/except ImportError` wraps the MLX import
- **Why it fails:** `mlx.core` triggers an `NSRangeException` (Objective-C runtime crash) — exit code 134 (SIGABRT). This is a **native crash below the Python exception handler**. The `try/except ImportError` cannot catch it.
- **Impact:** `pytest` exits with code 134 on any machine without Apple Silicon MLX support. The entire test suite is unrunnable. This means **the quality gate (Tier 1: pytest) is broken** — no verification signals are possible.
- **Root cause:** Heavy runtime dependencies initialized at import time, not lazily at call time.

#### CRITICAL-003: Task completion without postcondition check

- **File:** `backend/src/services/video_service_async.py:374-376`
- **Code:** `await self._update_task_status(task_id, "completed")` runs unconditionally after the clip loop
- **Problem:** If every clip in the loop is skipped (file doesn't exist or too small at lines 336-347), `clip_ids` is empty. The task is still marked `completed`.
- **Impact:** Users see a "completed" task with zero clips and no error. Silent false-positive.
- **Root cause:** Missing postcondition — should check `len(clip_ids) > 0` before marking complete, or mark as `completed_with_warnings` / `failed`.

#### CRITICAL-004: 25 source files use legacy `typing` imports

- **Files affected:** Every major source file
- **Standard violated:** rules-python.md ("NEVER import from typing: List, Dict, Tuple, Optional, Union — use Python 3.11+ built-ins")
- **Examples:**
  - `video_utils.py:8` — `from typing import List, Dict, Tuple, Optional, Any, Union`
  - `ai_types/ai_models.py:7` — `from typing import List`
  - `services/font_service.py:8` — `from typing import Optional, List, Dict, Any`
  - `services/video_service.py:6` — `from typing import List, Dict, Any, Optional, Callable`
  - `youtube_utils.py:9` — `from typing import Optional, Dict, Any`
  - `transcription_mlx.py:12` — `from typing import Dict, List, Any, Optional`
  - `models.py:2` — `from typing import List, Optional`
  - All 25 files listed in grep results
- **Correct Python 3.11+ equivalents:** `list[str]`, `dict[str, Any]`, `X | None`, `X | Y`
- **Root cause:** Standards document was written after the code, and no migration was done.

#### HIGH-001: Config class is not Pydantic BaseSettings

- **File:** `backend/src/config.py:10-93`
- **Standard violated:** CLAUDE.md ("Configuration should be validated with Pydantic at application startup"), rules-python.md ("Pydantic validation")
- **Current implementation:** Plain Python class with `__init__` calling `os.getenv()` 30+ times. No type validation, no field constraints, no env file parsing.
- **Example failure mode:** `self.max_clips = int(os.getenv("MAX_CLIPS", "10"))` — if someone sets `MAX_CLIPS=abc`, this crashes with an unhandled `ValueError` at startup with no useful error message.
- **Root cause:** Config was written before Pydantic standards were adopted.

#### HIGH-002: `os.getenv()` used outside Config module

- **Locations:**
  - `backend/src/database.py:16` — `DATABASE_URL = os.getenv(...)`
  - `backend/src/transcription_mlx.py:333` — `groq_api_key = os.getenv("GROQ_API_KEY", "")`
  - `backend/src/ai_structured.py:360` — `api_key = os.getenv("GROQ_API_KEY")`
- **Standard violated:** CLAUDE.md ("Configuration loading should use Pydantic models"), rules-python.md ("centralize configuration")
- **Impact:** Configuration scattered across modules. No single point of truth for what env vars the system reads. Impossible to audit configuration surface in one place.

#### HIGH-003: Duplicate API endpoints between main.py and router

- **`main.py` endpoints:**
  - `GET /tasks/{task_id}/clips` (line 180)
  - `GET /tasks/{task_id}` (line 233)
- **`api/routes/tasks.py` endpoints:**
  - `GET /{task_id}` (line 152, mounted at `/api/v1/tasks/`)
  - `GET /{task_id}/clips` (line 171, mounted at `/api/v1/tasks/`)
- **Impact:** Two code paths serve the same logical function. Business logic drifts between them. Debugging becomes ambiguous (which endpoint was hit?).
- **Root cause:** Router was introduced alongside existing main.py endpoints, but the old endpoints were never removed.

#### HIGH-004: Raw SQL queries in main.py bypass repository pattern

- **File:** `backend/src/main.py:185-227`, `main.py:238-286`
- **Problem:** `get_task_clips()` and `get_task_details()` contain inline `text("SELECT * FROM ...")` queries while repository modules exist specifically for this purpose.
- **Impact:** SPOT violation — task/clip data access logic exists in two places (main.py + repositories). Changes to one don't propagate to the other.

#### HIGH-005: Duration policy contradicts user constraints

- **File:** `backend/src/ai_structured.py:272-286`
- **Problem:** When `duration < min_length` but `duration >= 5.0`, the segment is ACCEPTED with a warning: "Keeping original to preserve hook integrity." This silently overrides the user's explicitly configured `clip_min_length`.
- **Impact:** Users set a minimum clip length via the API. The system acknowledges it in the prompt but then ignores it in post-processing validation. Silent contract violation.

#### HIGH-006: `clip_target_length` is accepted but never used

- **File:** `backend/src/services/video_service_async.py:207-229`
- **Problem:** `clip_target_length` is accepted as a parameter, documented, and plumbed through the service layer. But no code anywhere uses it for scoring, ranking, or selecting segments.
- **Impact:** UI exposes a setting that does nothing. Users have a false sense of control.

---

### ❓ What's Missing

1. **`docs/prd.md`** — Product Requirements Document. CLAUDE.md line 280 lists this as REQUIRED. Without it, there is no acceptance baseline. **This is the single most important missing artifact.**

2. **`docs/workplan.md`** — Development plan. Required by CLAUDE.md.

3. **`docs/polish.md`** — Refinement checklist. Required by CLAUDE.md.

4. **`docs/standards.md`** — Coding standards. Referenced by AGENTS.md line 45. The rules-python.md partially fills this role but the reference is broken.

5. **`.pre-commit-config.yaml`** — Pre-commit framework configuration. Required by CLAUDE.md line 284. Without this, quality gates are **voluntary** — nothing prevents broken code from being committed.

6. **File path markers on 30/42 source files.** Only 12 files have the required `# start backend/src/...` / `# end backend/src/...` markers. Missing from all core files: `main.py`, `ai.py`, `video_utils.py`, `youtube_utils.py`, `config.py`, `database.py`, `models.py`, `subtitle_renderer.py`, `ai_structured.py`, and 21 others.

7. **Frontend tests.** Jest is configured in `frontend/package.json` (v30.2.0, @testing-library/react 16.3.0) but **zero test files exist** in the frontend. No component tests, no hook tests, no integration tests.

8. **Regression tests for QA fixes.** CLIPS-001 through QA-005 added defensive code but no tests verify the new behavior (e.g., "what happens when all clips are invalid?", "does cleanup actually close resources?").

9. **Authentication/authorization tests.** No tests for `user_id` header validation, unauthorized access, or Better Auth integration.

10. **SSE progress endpoint tests.** `GET /tasks/{task_id}/progress` is untested.

---

### 🗑️ What's Unnecessary

1. **Backward compatibility wrappers with no callers:**
   - `backend/src/video_utils.py` line ~1914: `get_video_transcript_with_assemblyai()` — AssemblyAI was replaced by parakeet-mlx. No in-repo call sites.
   - `backend/src/video_utils.py` line ~1923: `create_9_16_clip()` — wrapper around `create_optimized_clip()`. No in-repo call sites.
   - `backend/src/youtube_utils.py:343-348`: `extract_video_id()` — wrapper around `get_youtube_video_id()`.

2. **Dead parameters in production code:**
   - `backend/src/video_utils.py:979,1049,1058`: `is_single_word` — passed but never read
   - `backend/src/video_utils.py:1290`: `words_per_subtitle` — declared but unused
   - `backend/src/transcription_mlx.py:271`: `_get_token_start_time()` — no in-repo callers
   - `backend/src/transcription_mlx.py:287`: `_get_token_end_time()` — no in-repo callers

3. **Archive debugging scripts in test directory:**
   - `backend/tests/archive/debugging/investigate_parakeet.py`
   - `backend/tests/archive/debugging/manual_check_critical_fixes.py`
   - `backend/tests/archive/debugging/reproduce_issue.py`
   - `backend/tests/archive/debugging/reproduce_logo_issue.py`
   - `backend/tests/archive/debugging/validate_logo_fix.py`
   - These are one-off debugging scripts, not tests. Should be removed or moved out of the test tree.

4. **Tracked artifacts that should be gitignored:**
   - `backend/supoclip.db` — database file (modified in git status)
   - `backend/.coverage` — test coverage data
   - `backend/docs/reports/*` — generated analysis reports (20+ files being deleted in current status)

---

### 🛠️ What's Fixed (Recent QA Campaign)

| VUW ID | Fix | File | Status |
|--------|-----|------|--------|
| QA-001 | Removed unused `word_end` variable | video_utils.py | ✅ Landed |
| QA-002 | Removed unnecessary `float()` cast | video_utils.py | ✅ Landed |
| QA-003 | Use `tuple` and `contextlib.suppress` in cleanup | video_utils.py | ✅ Landed |
| QA-004 | Add subtitle and logo clip cleanup | video_utils.py | ✅ Landed |
| QA-005 | Extract magic number to `MIN_CLIP_FILE_SIZE_BYTES` | video_service_async.py | ✅ Landed |
| CLIPS-001 | Add resource cleanup in exception handler | video_utils.py | ✅ Landed |
| CLIPS-002 | Add file validation before database storage | video_service_async.py | ✅ Landed |
| CLIPS-003 | Add diagnostic logging for clip loop | video_utils.py | ✅ Landed |
| SYNC-003 | Unify word boundary rules (STRICT) | transcription_mlx.py | ✅ Landed |
| SYNC-004 | Add diagnostic logging for caption sync | subtitle_renderer.py | ✅ Landed |

**Assessment:** All 10 fixes are directionally correct and well-scoped. The VUW discipline is working as designed. However, none of the fixes include regression tests to verify the behavior change.

---

### 💥 What's Newly Broken

**No new runtime regressions introduced by the QA campaign.** The recent commits (QA-001 through QA-005, CLIPS-001 through CLIPS-003, SYNC-003 through SYNC-004) are all defensive additions — they add validation, cleanup, and logging without altering core logic.

**However, existing critical gaps were NOT closed:**
- Task completion semantics (CRITICAL-003) remain unfixed
- MLX import crash (CRITICAL-002) remains unfixed
- Duration policy contradiction (HIGH-005) remains unfixed

---

### 🤫 Silent Errors Lurking

1. **False success on task completion** (CRITICAL-003). A task with zero valid clips is marked `completed` at `video_service_async.py:374-376`. No error, no warning to the user. The frontend shows a "completed" badge with an empty clip list.

2. **`clip_target_length` silently ignored** (HIGH-006). The API accepts this parameter, the frontend exposes a slider for it, the service layer passes it through — but nothing uses it. Users adjust a slider that changes nothing.

3. **`except Exception:` discards error context** in 5 locations:
   - `services/font_service.py:57` — catches `Exception` without binding to variable. The actual error is silently dropped.
   - `scripts/utility_complexity_heatmap.py:61`, `utility_dependency_graph.py:31`, `utility_xray.py:44`, `utility_grimp_analysis.py:84` — same pattern.

4. **Config startup crash on invalid env vars.** `config.py` does `int(os.getenv("MAX_CLIPS", "10"))` — if the env var contains a non-numeric string, the entire application crashes with an unhelpful `ValueError` traceback instead of a clear validation error.

5. **Invalid timestamp parsing returns 0.0.** In certain ai_structured.py parsing pathways, unparseable timestamps silently become `0.0` rather than raising an error. A clip starting at time 0.0 is almost certainly wrong but will be processed as if valid.

6. **MLX-dependent tests silently skip.** `backend/tests/test_video_processing.py:23-45` — import tests catch `ImportError` and call `pytest.skip()`. This means the entire video processing test class reports as "skipped" (green in CI), not "failed." The test suite gives false confidence.

---

### 🐷 What's Overengineered / Overcomplicated

1. **`video_utils.py` as a 1933-line monolith.** This file handles transcript parsing, face detection (3 cascading approaches: MediaPipe -> OpenCV DNN -> Haar), subtitle formatting, clip compositing with transitions, resolution management, browser-based subtitle rendering orchestration, compatibility wrappers, and utility functions. This is an entire application compressed into one file. The `create_optimized_clip` function alone has cyclomatic complexity grade C (radon).

2. **Dual sync/async video service.** `video_service.py` (413 lines) and `video_service_async.py` (411 lines) contain duplicated business logic with slight differences. Both evolve independently, creating drift risk. The sync version (`/start`) is already deprecated (returns 410) but the full code remains.

3. **Three-tier face detection cascade.** MediaPipe -> OpenCV DNN -> Haar cascade is robust but complex. Each fallback adds ~100 lines of code and different coordinate systems. No telemetry tracks which fallback fires in production, so it's unknown whether the cascades are needed.

---

### 🚮 Technical Debt / Dead Code

| Item | Location | Type | Impact |
|------|----------|------|--------|
| Legacy typing imports (25 files) | All `from typing import List, Dict...` | Standards debt | Blocks Python 3.11+ compliance |
| `get_video_transcript_with_assemblyai()` | `video_utils.py:~1914` | Dead code | AssemblyAI replaced by parakeet-mlx |
| `create_9_16_clip()` | `video_utils.py:~1923` | Dead code | Wrapper with no callers |
| `extract_video_id()` | `youtube_utils.py:343-348` | Dead code | Compat wrapper with no callers |
| `is_single_word` parameter | `video_utils.py:979,1049,1058` | Dead parameter | Passed but never read |
| `words_per_subtitle` parameter | `video_utils.py:1290` | Dead parameter | Declared but unused |
| `_get_token_start_time()` | `transcription_mlx.py:271` | Dead code | No callers |
| `_get_token_end_time()` | `transcription_mlx.py:287` | Dead code | No callers |
| Sync video service | `services/video_service.py` (413 lines) | Dead code path | `/start` returns 410, full service still exists |
| Duplicate endpoints in main.py | `main.py:180,233` vs `api/routes/tasks.py:152,171` | Architecture debt | Two code paths for same functionality |
| File markers missing (30 files) | All core source files | Standards debt | Convention not enforced |
| Config without Pydantic | `config.py` entire file | Architecture debt | No startup validation |
| Debugging scripts in tests | `tests/archive/debugging/` (5 files) | Dead code | Not maintained, not run |
| Stale subtitle tests | `tests/test_font_cutoff_and_short_clips.py` | Test debt | Tests old TextClip path, not current browser renderer |

---

## Tool Results Summary

### Tier 1 — Gate Checks

| Tool | Command | Result | Details |
|------|---------|--------|---------|
| ruff | `ruff check src/` | ✅ PASS | Zero lint errors |
| mypy | `mypy src/` | ⚠️ 3 errors | All in `src/scripts/` — untyped `radon` imports |
| pytest | `pytest tests/` | ❌ CRASH | Exit code 134 (SIGABRT) — MLX native crash |
| deptry | `deptry src/` | ✅ PASS | No dependency issues |

### Tier 2 — Quality Analysis

| Tool | Command | Result | Details |
|------|---------|--------|---------|
| radon | `radon cc src/ -a -nb` | ⚠️ Grade C | `create_optimized_clip` in video_utils.py |
| bandit | `bandit -r src/` | ⚠️ 4 medium | Bind-all-interfaces, SQL expression warnings, `/tmp` usage |
| interrogate | `interrogate src/` | ✅ 88.9% | Above 80% threshold |
| pylint | `pylint src/` | ⚠️ 7.65/10 | Unused args, duplicate code, broad exceptions, oversized module |

### Tier 3 — Advanced

| Tool | Command | Result | Details |
|------|---------|--------|---------|
| xenon | `xenon src/ --max-absolute C` | ✅ PASS | No grade D+ functions |
| semgrep | `semgrep --config auto src/` | ❌ BLOCKED | Local CA/cert trust failure |
| sqlfluff | `sqlfluff lint` | ⚠️ Issues | Migration SQL style problems |
| pip-audit | `pip-audit` | ❌ BLOCKED | Network/DNS constraints |

---

## Systemic Root Causes

### 1. Quality gates are documented but not mechanized

The standards in CLAUDE.md and rules-python.md are comprehensive and well-written. But **nothing enforces them automatically**:
- No `.pre-commit-config.yaml` means no pre-commit hooks
- No CI pipeline checks file length, typing imports, or file markers
- `checkpython.sh` exists but is manual
- The quality gate (pytest) is broken by MLX crashes

**Result:** Standards become aspirational, not operational. Compliance depends entirely on developer discipline, which degrades over time.

### 2. Import-time side effects from heavy native dependencies

`video_utils.py` imports `transcription_mlx` at module level, which imports `mlx.core`. On non-Apple-Silicon machines, this triggers a C-level crash that Python cannot catch. This single import chain makes the entire test suite, linter, and type checker unreliable in CI or cross-platform environments.

### 3. Contradictory standards documents

- **CLAUDE.md** says: use `.env` files for configuration, `os.getenv()` for loading
- **rules-python.md** says: "NEVER use environment variables" and mandates YAML config + Pydantic
- This inconsistency means developers can always claim compliance with one document while violating the other.

### 4. Architecture evolution without cleanup

The project has evolved through several phases (AssemblyAI -> parakeet-mlx, sync -> async, monolith -> router), but prior-phase artifacts remain:
- Old compatibility wrappers with no callers
- Duplicate endpoints (main.py + router)
- Sync video service for a deprecated endpoint
- Stale tests validating old rendering paths

---

## File-by-File Compliance Summary

| File | Lines | Limit | Markers | Typing | Docstrings |
|------|-------|-------|---------|--------|------------|
| video_utils.py | 1933 | ❌ 750 | ❌ | ❌ Legacy | ✅ |
| main.py | 509 | ✅ | ❌ | ✅ | ✅ |
| ai.py | 504 | ✅ | ❌ | ✅ | ✅ |
| transcription_mlx.py | 621 | ✅ | ⚠️ end only | ❌ Legacy | ✅ |
| youtube_utils.py | 348 | ✅ | ❌ | ❌ Legacy | ✅ |
| config.py | 161 | ✅ | ❌ | ✅ | ✅ |
| database.py | 142 | ✅ | ❌ | ✅ | ✅ |
| models.py | ~200 | ✅ | ❌ | ❌ Legacy | ✅ |
| video_service_async.py | 411 | ✅ | ✅ | ❌ Legacy | ✅ |
| video_service.py | 413 | ✅ | ❌ | ❌ Legacy | ✅ |
| services/font_service.py | 531 | ✅ | ✅ | ❌ Legacy | ✅ |
| dependencies.py | 113 | ✅ | ✅ | ❌ Legacy | ✅ |
| lifecycle.py | 84 | ✅ | ✅ | ✅ | ✅ |
| logging_config.py | 144 | ✅ | ✅ | ✅ | ✅ |

---

## Recommended Priority Sequence

### Campaign 1: Unblock Quality Gate (Blockers)
1. **Lazy-load MLX imports** — Move `mlx.core` import inside function body, not module level. Unblocks pytest.
2. **Add `.pre-commit-config.yaml`** — Mechanize ruff, mypy, pytest as pre-commit hooks.
3. **Add postcondition to task completion** — Don't mark completed if `clip_ids` is empty.

### Campaign 2: Standards Compliance
4. **Migrate 25 files from legacy typing** — `List` -> `list`, `Optional[X]` -> `X | None`, etc.
5. **Convert Config to Pydantic BaseSettings** — Centralize and validate all configuration.
6. **Remove os.getenv outside Config** — All env access through Config class.
7. **Add file path markers to 30 missing files**.

### Campaign 3: Architecture Cleanup
8. **Split video_utils.py** into 4-6 focused modules (cropping, subtitle formatting, compositing, transcript parsing, compatibility).
9. **Remove duplicate endpoints from main.py** — Keep router-based endpoints only.
10. **Remove sync video_service.py** — `/start` already returns 410.
11. **Remove dead code** — compatibility wrappers, unused parameters, dead helper functions.
12. **Remove archive debugging scripts** from test directory.

### Campaign 4: Test Coverage
13. **Add regression tests for QA/CLIPS fixes**.
14. **Add frontend component tests**.
15. **Replace import-only video tests** with meaningful unit tests.
16. **Add auth/authorization tests**.

---

*End of audit report.*
