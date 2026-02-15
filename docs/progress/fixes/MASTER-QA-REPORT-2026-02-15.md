# Master QA Report — SupoClip

**Generated:** 2026-02-15
**Source Reports:** Codex, Gemini, Claude Opus QA audits
**Validation Method:** All claims factchecked against actual codebase; only VERIFIED findings included
**False Positives Excluded:** 750-line file limit (fabricated), broken test suite (false), DATABASE_URL poisoning (false), asyncpg usage (false), /api/v1/tasks/ mount path (false)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| BLOCKER | 1 |
| CRITICAL | 5 |
| HIGH | 13 |
| MEDIUM | 9 |
| **Total** | **28** |

---

## BLOCKER

### BLK-001: Task Completion Without Postcondition
- **Description:** Tasks are marked "completed" even when all clips are invalid/skipped, creating silent false-positive success states
- **Evidence:** `video_service_async.py:374-376` — `await self._update_task_status(task_id, "completed")` executes unconditionally after clip loop, with no check on whether `clip_ids` is non-empty
- **Files:** `backend/src/services/video_service_async.py`
- **Confirmed by:** Codex, Claude Opus
- **Impact:** Users see "completed" tasks with zero usable output

---

## CRITICAL

### CRIT-001: video_utils.py Monolith (1933 lines, Radon Grade C)
- **Description:** Single file handles font resolution, face detection (3 methods), subtitle creation, clip compositing, transcript parsing, resolution management, and backward-compat wrappers. Radon reports `create_optimized_clip` at grade C (complexity 14).
- **Evidence:** `wc -l` = 1933 exactly. Radon grade C confirmed by Gemini factcheck (ran tool). Contains `import sqlite3`, MediaPipe, OpenCV DNN, Haar cascade, subtitle rendering, and clip assembly all in one file.
- **Files:** `backend/src/video_utils.py`
- **Standard violated:** `rules-python.md:48` — "No file exceeds radon cc grade B; C/D/E MUST be refactored"
- **Confirmed by:** All 3 reports

### CRIT-002: Legacy Typing Imports (25 Files)
- **Description:** 25 source files use deprecated `from typing import List, Dict, Optional, Union` instead of Python 3.11+ builtins (`list`, `dict`, `X | None`, `X | Y`)
- **Evidence:** `grep 'from typing import' backend/src/` returns 25 files. Example: `video_utils.py:8` has `from typing import List, Dict, Tuple, Optional, Any, Union`
- **Files:** All 25 files listed in Claude factcheck report (video_utils.py, ai.py, models.py, config.py, transcription_mlx.py, youtube_utils.py, font_service.py, video_service.py, video_service_async.py, ai_structured.py, ai_models.py, and 14 more)
- **Standard violated:** `rules-python.md:195-199,319` — "Use `list[str]`, `dict[str, int]`, `X | Y`, `X | None`. Avoid deprecated `typing.List`, `typing.Dict`, `typing.Union`, `typing.Optional`"
- **Confirmed by:** Codex, Claude Opus (Gemini incorrectly marked PASS)

### CRIT-003: Config Class Not Using Pydantic BaseSettings
- **Description:** Config is a plain Python class with 26 `os.getenv()` calls. No type validation, no default enforcement, no startup error on invalid values.
- **Evidence:** `backend/src/config.py:10` — `class Config:` with `__init__` calling `os.getenv()` 26 times. `grep 'BaseSettings' backend/src/` returns zero.
- **Files:** `backend/src/config.py`
- **Standard violated:** `rules-python.md:57` and `CLAUDE.md:287` (documented deviation but still not Pydantic-validated)
- **Confirmed by:** All 3 reports

### CRIT-004: Missing Required Documentation
- **Description:** 4 required documentation files do not exist
- **Evidence:** Glob search returns no results for any of these paths
- **Missing files:**
  - `docs/prd.md` (Product Requirements Document)
  - `docs/workplan.md` (Development Plan)
  - `docs/polish.md` (Refinement Checklist)
  - `docs/standards.md` (referenced in `AGENTS.md:45`)
- **Standard violated:** `CLAUDE.md:280-285` — Required Project Files, `rules-python.md:49`
- **Confirmed by:** All 3 reports

### CRIT-005: Missing .pre-commit-config.yaml
- **Description:** Pre-commit framework configuration file does not exist at project root
- **Evidence:** Glob search returns no results
- **Files:** `.pre-commit-config.yaml` (should exist at repo root)
- **Standard violated:** `CLAUDE.md:283` — Required Project Files
- **Confirmed by:** All 3 reports

---

## HIGH

### HIGH-001: Duplicate API Endpoints
- **Description:** Task detail and clip endpoints exist in both `main.py` and `api/routes/tasks.py`, creating direct path collisions at `/tasks/{task_id}` and `/tasks/{task_id}/clips`
- **Evidence:** `main.py:180` GET clips, `main.py:233` GET task detail; `tasks.py:152` GET task detail, `tasks.py:171` GET clips. Router uses `prefix="/tasks"` (NOT `/api/v1/tasks/` as some reports claimed).
- **Files:** `backend/src/main.py`, `backend/src/api/routes/tasks.py`
- **Confirmed by:** All 3 reports

### HIGH-002: Raw SQL in main.py Bypassing Repository Pattern
- **Description:** Multiple endpoints use `text("SELECT ...")` raw SQL instead of calling repository methods, despite repository files existing
- **Evidence:** `main.py` lines 186, 193, 238, 254, 256 all use `text("SELECT * FROM ...")`. Repository files exist at `backend/src/repositories/` (task_repository.py, clip_repository.py, source_repository.py)
- **Files:** `backend/src/main.py`
- **Confirmed by:** All 3 reports

### HIGH-003: Raw sqlite3 in video_utils.py
- **Description:** Direct `sqlite3.connect()` call for font lookup instead of using SQLAlchemy
- **Evidence:** `video_utils.py:82` — `import sqlite3`; lines 88-92 show `sqlite3.connect()` and `cursor.execute()` for system_fonts table
- **Files:** `backend/src/video_utils.py`
- **Confirmed by:** Gemini

### HIGH-004: os.getenv() Scattered Outside Config
- **Description:** Configuration access bypasses the Config class in 3 files
- **Evidence:**
  - `database.py:16` — `DATABASE_URL = os.getenv(...)`
  - `transcription_mlx.py:333` — `groq_api_key = os.getenv("GROQ_API_KEY", "")`
  - `ai_structured.py:360` — `api_key = os.getenv("GROQ_API_KEY")`
- **Files:** `backend/src/database.py`, `backend/src/transcription_mlx.py`, `backend/src/ai_structured.py`
- **Confirmed by:** Claude Opus

### HIGH-005: clip_target_length Dead Parameter
- **Description:** Parameter accepted in API and function signature but never used for scoring or segment selection
- **Evidence:** `video_service_async.py:207` declares `clip_target_length: int = 30`. Function body (lines 236-382) never references it. AI call at lines 272-277 only passes `clip_min_length` and `clip_max_length`.
- **Files:** `backend/src/services/video_service_async.py`
- **Confirmed by:** Codex, Claude Opus

### HIGH-006: Dead Backward-Compat Wrapper Functions (No Callers)
- **Description:** 3 wrapper functions exist with zero in-repo callers
- **Evidence:**
  - `video_utils.py:1914` — `get_video_transcript_with_assemblyai()` (wraps `get_video_transcript()`)
  - `video_utils.py:1923` — `create_9_16_clip()` (wraps `create_optimized_clip()`)
  - `youtube_utils.py:346` — `extract_video_id()` (wraps `get_youtube_video_id()`)
- **Files:** `backend/src/video_utils.py`, `backend/src/youtube_utils.py`
- **Confirmed by:** Codex, Claude Opus

### HIGH-007: Dead Private Functions (No Callers)
- **Description:** 2 private functions with zero call sites
- **Evidence:**
  - `transcription_mlx.py:271` — `_get_token_start_time()` (no callers in backend/src/)
  - `transcription_mlx.py:287` — `_get_token_end_time()` (no callers in backend/src/)
- **Files:** `backend/src/transcription_mlx.py`
- **Confirmed by:** Codex, Claude Opus

### HIGH-008: Dead Parameters in Functions
- **Description:** 2 parameters accepted but never referenced in function bodies
- **Evidence:**
  - `video_utils.py:979` — `is_single_word` in `_create_clip_candidate()`: parameter declared but body (lines 988-1025) never references it. Computed at line 1049, passed at line 1058.
  - `video_utils.py:1290` — `words_per_subtitle` in `SubtitleClipBuilder.build_clips()`: parameter declared but body never references it. Always called with hardcoded value `1` at line 1412.
- **Files:** `backend/src/video_utils.py`
- **Confirmed by:** Codex, Claude Opus

### HIGH-009: File Path Markers Missing (24 of 34 Files)
- **Description:** Only 10 of 34 non-init Python source files have the required `# start path/to/file.py` markers
- **Evidence:** `grep '# start' backend/src/` returns 10 matches. Files WITH markers: dependencies.py, video_service_async.py, user_preferences_service.py, font_service.py, job_queue.py, tasks.py (workers), fonts.py (api), lifecycle.py, logging_config.py, font_options.py. All other 24 files (including main.py, video_utils.py, config.py, models.py, database.py, ai.py) lack markers.
- **Standard violated:** `rules-python.md:42-43` — "All source files must start and end with a file path comment"
- **Files:** 24 files in `backend/src/`
- **Confirmed by:** All 3 reports

### HIGH-010: .gitignore Incomplete + Tracked Artifacts
- **Description:** `.gitignore` missing entries for `.coverage`, `*.db`, and generated reports. `backend/supoclip.db` and `backend/.coverage` are tracked in git.
- **Evidence:** `.gitignore` contains only: `.env.local`, `.DS_Store`, `__pycache__`, `*.egg-info`, `logs/`, `temp/`, `.env`, `*.m4a`. Git status shows `backend/supoclip.db` as modified.
- **Files:** `.gitignore`, `backend/supoclip.db`, `backend/.coverage`
- **Confirmed by:** Codex, Claude Opus

### HIGH-011: Archive Debugging Scripts in tests/
- **Description:** 5 one-off debugging scripts exist in archive directory, violating "no one-off diagnostic scripts" principle
- **Evidence:** `tests/archive/debugging/` contains: `investigate_parakeet.py`, `manual_check_critical_fixes.py`, `reproduce_issue.py`, `reproduce_logo_issue.py`, `validate_logo_fix.py`
- **Files:** `backend/tests/archive/debugging/` (5 files)
- **Standard violated:** `rules-python.md` — "Build single static quality utility, no one-off diagnostic scripts"
- **Confirmed by:** Claude Opus

### HIGH-012: No CI/CD Pipeline
- **Description:** No continuous integration or deployment configuration exists
- **Evidence:** No `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, or `.circleci/` found
- **Files:** Repository root
- **Confirmed by:** Gemini

### HIGH-013: except Exception: Without Binding
- **Description:** Bare `except Exception:` clauses silently drop errors
- **Evidence:**
  - `font_service.py:57` — `except Exception:` with no variable binding
  - `utility_complexity_heatmap.py:61`, `utility_dependency_graph.py:31`, `utility_xray.py:44`, `utility_grimp_analysis.py:84`
- **Files:** `backend/src/services/font_service.py`, 4 utility scripts
- **Confirmed by:** Claude Opus

---

## MEDIUM

### MED-001: Duration Policy Overrides User Constraints
- **Description:** Segments shorter than user-specified `clip_min_length` but >= 5.0 seconds are accepted with a warning, silently overriding user constraints
- **Evidence:** `ai_structured.py:272-286` — segments with `duration >= 5.0` accepted as "UNDERLENGTH" even when below `min_length`
- **Files:** `backend/src/ai_structured.py`
- **Confirmed by:** Codex, Claude Opus

### MED-002: parse_timestamp_to_seconds Returns 0.0 on Failure
- **Description:** Parse failures silently return 0.0 instead of raising an error, which can cause clips to start from the beginning of a video
- **Evidence:** `video_utils.py:920` — `return 0.0` in `except (ValueError, IndexError)` block
- **Files:** `backend/src/video_utils.py`
- **Confirmed by:** All 3 reports

### MED-003: No Frontend Tests
- **Description:** Zero test files in frontend despite Jest configuration in package.json
- **Evidence:** No `.test.*` or `.spec.*` files in `frontend/src/`
- **Files:** `frontend/`
- **Confirmed by:** All 3 reports

### MED-004: No Waitlist Tests
- **Description:** No testing infrastructure or test files in waitlist app
- **Evidence:** No test files, no jest/vitest config in `waitlist/`
- **Files:** `waitlist/`
- **Confirmed by:** Gemini

### MED-005: Stale .serena Memory Files
- **Description:** Auto-generated memory files reference technologies not in use (Redis, arq, PostgreSQL, Docker Compose, main_refactored.py)
- **Evidence:** `.serena/memories/project_overview.md:23` — "Redis-based arq job queue"; `.serena/memories/tech_stack.md` lines 15,17,20-21 reference PostgreSQL, asyncpg, Redis
- **Files:** `.serena/memories/project_overview.md`, `.serena/memories/tech_stack.md`
- **Confirmed by:** Gemini

### MED-006: Stale AssemblyAI References in Code
- **Description:** Function names and docstrings reference AssemblyAI despite migration to parakeet-mlx
- **Evidence:** `video_utils.py:3` docstring says "AssemblyAI integration"; line 1514 says "Create optimized 9:16 clip with AssemblyAI subtitles"; function `create_assemblyai_subtitles` called on line 1587
- **Files:** `backend/src/video_utils.py`
- **Confirmed by:** Gemini

### MED-007: Sync video_service.py Coexists with Async Version
- **Description:** Both `video_service.py` (413 lines) and `video_service_async.py` (411 lines) exist, creating duplication risk
- **Evidence:** Both files present in `backend/src/services/`
- **Files:** `backend/src/services/video_service.py`, `backend/src/services/video_service_async.py`
- **Confirmed by:** Codex

### MED-008: Incomplete Google-Style Docstrings
- **Description:** Most functions lack complete Google-style docstrings with Args/Returns/Raises sections
- **Evidence:** `main.py` has 0 Google-style docstring sections. `video_utils.py` has partial coverage (~63% of documented functions)
- **Standard violated:** `rules-python.md` — "Google Python Style for docstrings (PEP 257)"
- **Files:** Most backend source files
- **Confirmed by:** Gemini

### MED-009: Test File Tests Old TextClip Rendering Path
- **Description:** `test_font_cutoff_and_short_clips.py` tests old `TextClip(method="caption")` path while production uses `BrowserSubtitleRenderer`
- **Evidence:** File contains 11 references to `TextClip` from moviepy; production path uses browser rendering
- **Files:** `backend/tests/test_font_cutoff_and_short_clips.py`
- **Confirmed by:** Claude Opus

---

## False Positives Excluded From This Report

The following claims appeared in one or more QA reports but were **disproven** during factchecking:

| Claim | Why False | Reports Affected |
|-------|-----------|------------------|
| "750-line file maximum" exists in standards | Neither CLAUDE.md nor rules-python.md mentions any line limit. Actual standard is radon grade B max. | Codex, Gemini |
| Test suite is "un-runnable" due to DATABASE_URL | pytest collects 574 tests, passes 562 in 25.78s. Backend loads correct .env. | Gemini |
| Root .env "silently poisons" backend | backend's load_dotenv() loads backend/.env (correct URL), not root .env | Gemini |
| SQLAlchemy crashes during startup/testing | No crash occurs; all tests pass | Gemini |
| Type hints "PASS" | 25 files use deprecated typing imports, violating rules-python.md | Gemini |
| Uses asyncpg for performance | Uses aiosqlite, not asyncpg (SQLite, not PostgreSQL) | Gemini |
| Router mounted at /api/v1/tasks/ | Actual prefix is /tasks/ | Claude Opus |
| Layered architecture "working well" | main.py bypasses repositories with raw SQL | Gemini |
| MLX imports crash at import time | Imports wrapped in try/except ImportError with graceful fallback | Codex |
| Standards contradiction (env vars) | CLAUDE.md:287 explicitly documents this as intentional deviation | Codex |

---

## Audit Methodology

- **3 independent QA reports** factchecked against actual codebase
- **155 total claims examined** (42 Codex + 35 Gemini + 78 Claude)
- **110 verified** (71%), **28 false positives** (18%), **4 outdated** (3%), **13 cannot verify** (8%)
- **Deduplication** reduced 110 verified claims to 28 unique findings
- Tools used: file reads, grep, wc -l, glob, git log, radon (by Gemini agent), pytest (by Gemini agent)

*This master report was produced by consolidating 3 factcheck audits run on 2026-02-15.*
