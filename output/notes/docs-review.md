# Documentation Review — SupoClip (Source of Truth for "What Was Promised")

**Author:** Docs-review audit agent
**Date:** 2026-06-29
**Scope:** Authoritative summary of every documented promise, requirement, module spec, and
development standard, plus all doc-vs-doc and doc-vs-tree contradictions. Downstream
PRD-validation and code-audit agents should treat this file as the canonical "promised" baseline.

**Documents reviewed (full reads unless noted):**
- `docs/prd.md` (97 lines) — Product Requirements
- `docs/spec.md` (1235 lines) — Technical Specification, "Clean Consolidation" Redesign v1.0
- `docs/rules-python.md` (490 lines) — Python coding standards
- `docs/orientation.md` (17 lines) — folder conventions
- `docs/progress/fixes/MASTER-QA-REPORT-2026-02-15.md` (skimmed) — historical pre-redesign audit
- `CLAUDE.md` (459 lines, root) — project instructions
- `AGENTS.md` (74 lines, root) — repository guidelines (STALE — see §5)
- `README.md` (root), `recipe.md` (root), `qa.md` (root)

---

## 1. PROJECT SCOPE & VISION

SupoClip is an open-source, self-hosted alternative to OpusClip. It transforms long-form video
(podcasts, interviews, tutorials) into 3–7 viral 9:16 short clips with AI-selected segments and
word-level burned-in subtitles. Differentiators: zero subscription fees, no watermarks, unlimited
usage, fully local/privacy-preserving processing.

**Target users:** independent creators, podcasters, marketing teams repurposing webinars,
privacy-conscious creators wanting local processing (`docs/prd.md:11-16`).

**Core architectural mandate (the redesign thesis):** SupoClip is a **single all-Python
application**. NiceGUI (built on FastAPI) serves UI + API from one process, one event loop. There
is explicitly **no React, no TypeScript, no Node.js, no npm** (`CLAUDE.md:13`, `docs/spec.md:88-92`).

**The "Clean Consolidation" redesign** (`docs/spec.md:35-46`) replaced the prior two-process
split (Python/FastAPI backend + React/Next.js frontend) and removed:
- Playwright/Chromium subtitle rendering → pysubs2 + ffmpeg ASS filter
- MoviePy video layer → direct ffmpeg subprocess calls
- Duplicate AI paths (`ai.py` + `ai_structured.py`) → unified `analyze.py`
- Over-abstracted backend (repositories/services/workers/utils) → flat `src/`
- Better Auth + Prisma authentication → no auth (single-user local)
- Waitlist / hosted SaaS landing page → deleted from scope

**Out of scope** (`docs/prd.md:90-97`): multi-user SaaS, cloud processing, mobile native apps,
real-time collaboration, billing/payments, hosted/waitlist version.

**Non-functional requirements** (`docs/prd.md:58-72`): self-hosted single machine, single Python
process, SQLite (no external DB), local asyncio job queue (no Redis), `uv` package manager only,
NiceGUI 3.0+ frontend, no authentication, `python -m src.main` start command, ffmpeg system dep.

---

## 2. PRD PROMISED FEATURES (every requirement)

Source: `docs/prd.md:18-57`. Each is a promise downstream PRD-validation must verify against code.

| # | Feature | Promise detail | Source |
|---|---------|----------------|--------|
| F1 | YouTube download | Paste URL; yt-dlp downloads video | prd.md:20-21 |
| F2 | File upload | Upload local video files via web UI | prd.md:22 |
| F3 | AI Transcription | parakeet-mlx, offline, on-device, word-level timestamps; full transcript + per-word timing; all local, no data leaves machine | prd.md:24-27 |
| F4 | Intelligent clip selection | Pydantic AI + configurable LLM (local or cloud); criteria = strong hooks, valuable content, emotional moments, complete standalone thoughts; **3-7 segments, each 10-45s**; validation start_time != end_time, min 5-10s duration | prd.md:29-33 |
| F5 | Video generation — format | 9:16 vertical | prd.md:36 |
| F6 | Smart cropping | "Face-centered using MediaPipe (primary), **OpenCV DNN (fallback), Haar cascade (last resort)**" ⚠️ CONTRADICTS spec — see §5 C7 | prd.md:37 |
| F7 | Subtitles | Word-level synchronized via pysubs2 + ffmpeg ASS filter; customizable font/size/color/stroke/shadow/position | prd.md:38 |
| F8 | Transitions | Optional intro/outro effects from MP4 templates | prd.md:39 |
| F9 | Encoding | H.264 via ffmpeg, even dimensions enforced | prd.md:40 |
| F10 | Real-time progress | Live display during transcription, analysis, clip generation; task-based tracking with persistent history | prd.md:42-44 |
| F11 | Font/style customization | Custom TTF fonts (incl. Google Fonts) in `fonts/`; configurable family/size/color/stroke/shadow/position per request; system font discovery | prd.md:46-49 |
| F12 | Settings persistence | User prefs (fonts, clip lengths, AI prompt, logo, resolution) persisted across sessions | prd.md:51-52 |
| F13 | Task history & clip management | View past jobs and clips; download or delete individual clips | prd.md:54-56 |

**README adds** (consistent with PRD): transitions applied "round-robin" across clips
(`README.md:24`, `CLAUDE.md` workflows section). Note: round-robin is a README/CLAUDE detail not
in the PRD or spec.

---

## 3. SPEC MODULE SPECIFICATIONS (what each module MUST do)

Source: `docs/spec.md` §4 (lines 160-454). Target structure is flat `src/` (no backend/ prefix).

- **`src/main.py`** (§4.1, 162-183): entry point only, no business logic. Configures structlog,
  calls `database.init_db()`, registers `@ui.page` functions, configures static serving for
  `fonts/` + clip output dir, starts uvicorn via `ui.run()`, registers lifespan hooks.
- **`src/config.py`** (§4.2): `Config(BaseSettings)` with `SettingsConfigDict(extra="ignore")`.
  Single source of truth. Full field list in §8 (see §4 below).
- **`src/database.py`** (§4.3, 196-211): exports `Base` (DeclarativeBase), `AsyncSessionLocal`
  (async_sessionmaker), `init_db()`, `get_session()` async context manager.
- **`src/models.py`** (§4.4): the 3 ORM tables (full schema §7 of spec — see below).
- **`src/pages/home.py`** (§4.5 / §6.1): `/` — URL input or upload; creates `Task` row status
  `pending`; navigates to `/task/{id}`. Components incl. font selector, size slider (12-72,
  default 24), color picker (#FFFFFF), clip length range (default 10-45), target count (default 5,
  range 1-10), resolution select (720p/1080p, default 720p).
- **`src/pages/task.py`** (§4.6 / §6.2): `/task/{task_id}` — status badge, linear progress
  (0.0-1.0) via WebSocket, progress message, clip grid after `done`, per-clip video player +
  download, error alert if `failed` (reads `task.settings_json["error"]`).
- **`src/pages/history.py`** (§4.7 / §6.3): `/history` — table (title, status, clip count, created
  date, newest-first), row click → task page, delete button (soft-delete), empty state.
- **`src/pages/settings.py`** (§4.8 / §6.4): `/settings` — edits/persists `UserPreferences`
  singleton (font family/size/color, min/target/max clip length, custom AI prompt, logo upload +
  corner, output resolution).
- **`src/pipeline/download.py`** (§4.9, 255-274): `async download_video(url, output_dir) -> Path`.
  yt-dlp via `asyncio.to_thread`, best video+audio up to 1080p, validates non-empty output, strips
  query params from filename, raises `DownloadError`.
- **`src/pipeline/transcribe.py`** (§4.10, 277-305): `async transcribe(video_path) -> TranscriptData`,
  `load_cache`, `save_cache`. `TranscriptData` = `dataclass(slots=True)` with `words:
  list[WordTiming]` (text, start_ms, end_ms, confidence), `full_text`, `duration_s`. Cache at
  `{video_path}.transcript_cache.json` (JSON, Pydantic-deserialised). Optional LLM word
  reconstruction if `config.reconstruct_words_with_llm`.
- **`src/pipeline/analyze.py`** (§4.11 / §11): `async select_segments(transcript, settings) ->
  list[ClipSegment]` sorted by descending score. Merges old `ai.py` + `ai_structured.py` into one
  ~250-line module, one system prompt, one validation pipeline. `ClipSegment`:
  start_ms/end_ms/title/transcript_text/score/reasoning (NOTE: §11.3 shows the dataclass with
  `start_time`/`end_time` as `MM:SS.mmm` str fields and `text` — minor internal field-name
  inconsistency between §4.11 and §11.3). Routing: Groq structured outputs vs Pydantic AI by model
  string prefix. `@stamina.retry(attempts=3, wait_initial=2.0, wait_max=10.0)`. Raises
  `InsufficientSegmentsError` if <1 valid segment.
- **`src/pipeline/clip.py`** (§4.12 / §10): `async build_clip(source_video, segment,
  subtitle_file, output_path, settings) -> Path`. Single ffmpeg subprocess (trim + 9:16 crop +
  scale + burn ASS + optional logo overlay + H.264). Never `shell=True`. Raises `RenderError` /
  `FfmpegError` on non-zero exit.
- **`src/pipeline/subtitles.py`** (§4.13 / §9): `build_ass_file(words, clip_start_ms, clip_end_ms,
  output_path, style) -> Path` via pysubs2. Word-level events; context-line dimming of surrounding
  words; `hex_to_ass_color(#RRGGBB) -> &HAABBGGRR`. `SubtitleStyle` fields in §9.3 (font_family
  default `TikTokSans-Regular`, font_size 24, primary `&H00FFFFFF`, secondary `&H80FFFFFF`,
  outline_width 2.0, shadow_depth 1.0, vertical_margin 25% of height, bold False).
- **`src/pipeline/face_detect.py`** (§4.14, 390-416): `async get_crop_rect(video_path, start_s,
  end_s, target_width, target_height) -> CropRect`. Sample up to 10 evenly spaced frames, run
  MediaPipe, aggregate bounding boxes (median x-centre). **MediaPipe ONLY** — center crop if no
  face, "no further fallback". Even w/h. Synchronous calls in `asyncio.to_thread`.
- **`src/services/video_service.py`** (§4.15, 419-454): `async process_video(task_id, source_path,
  settings, progress_callback) -> list[GeneratedClip]`. Orchestrates full pipeline. Progress
  checkpoints: download 5-20%, transcribe 20-50%, analyse 50-60%, render 60-95%, save 95-100%.
  Clip rendering parallel via `asyncio.TaskGroup` up to `config.max_workers`. On any exception:
  status `failed`, error stored in `Task.settings_json["error"]`, callback `(0, "Error: …")`,
  exception re-raised for structlog traceback (§5.3, 505-507).

### Data model (spec §7, 608-674) — 3 tables, UUID v4 VARCHAR(36) PKs, UTC datetimes
- **`tasks`**: id, source_url, source_type (`youtube`/`upload`/`url`), status
  (`pending`/`processing`/`done`/`failed`), progress (0-100), progress_message, settings_json
  (also holds `error`), created_at, updated_at. CHECK constraints on status & source_type.
- **`generated_clips`**: id, task_id (FK CASCADE), filename, start_time/end_time (`MM:SS.mmm`),
  title, transcript_text, score (FLOAT 0-1), reasoning, clip_order, timestamps.
- **`user_preferences`**: singleton (id always 1). font_family default `TikTokSans-Regular`,
  font_size 24, font_color #FFFFFF, clip_min_s 10, clip_target_s 30, clip_max_s 45,
  target_clip_count 5, custom_ai_prompt, logo_path, logo_position (`top-right` default),
  output_resolution (`720p` default). CHECK constraints on logo_position & output_resolution.

### Configuration env vars (spec §8, 677-724)
LLM: `LOCAL_LLM_ENABLED` (true), `LOCAL_LLM_BASE_URL` (http://localhost:6969/v1),
`LOCAL_LLM_MODEL` (local-model), `LOCAL_LLM_API_KEY` (not-needed), `LLM_MODEL` (""),
`GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`. Priority: local →
cloud → raise `ValueError`. Transcription: `PARAKEET_MODEL`
(mlx-community/parakeet-tdt-0.6b-v2), `RECONSTRUCT_WORDS_WITH_LLM` (true). Video: `TEMP_DIR`
(temp), `MAX_VIDEO_DURATION` (3600), `MAX_CLIPS` (10), `FFMPEG_PRESET` (fast), `FFMPEG_CRF`
(23). App: `DATABASE_URL` (sqlite+aiosqlite:///./supoclip.db), `HOST` (0.0.0.0), `PORT`
(8008), `MAX_WORKERS` (2), `LOG_LEVEL` (INFO), `LOG_DIR` (logs).

### ffmpeg pipeline (spec §10) & subtitle system (spec §9)
Single subprocess per clip; input-seek `-ss/-to` before `-i`; filter
`crop={w}:{h}:{x}:{y},scale={out_w}:{out_h},ass={subtitle_path}:fontsdir={fonts_dir}`; logo via
`-filter_complex overlay` scaled to 10% width; H.264 libx264 + aac 128k + `+faststart`.
Resolutions: 720p = 1080×1920, 1080p = 2160×3840 (NOTE odd labeling — "720p" output is actually
1080px wide; see §5 C8). ASS colours `&HAABBGGRR`. Fonts discovered at startup via fonttools name
table; `fontsdir=fonts/` makes them available to libass without system install.

---

## 4. DOCUMENTED DEVELOPMENT STANDARDS & QUALITY GATE

### First Principles (rules-python.md:11-24, also in recipe.md & CLAUDE.md VUW section)
P1 Fix Over Create · P2 Reusable Testing (utilities in `src/scripts/`, tests in `tests/`) · P3
Docs Location (all docs in `docs/`; sole root exception = `CLAUDE.md`) · P4 Never Defer · P5 Use
Agents · P6 Anti-Elision (no stubs/`...`/`pass`/`# TODO`) · P7 Contextual Strictness · P8 Explicit
Failure Propagation (no swallowing; None = absence not failure) · P9 Idempotent Mutation · P10
Simplicity · P11 Test Coverage (100% or FAILURE) · P12 Never Reinvent the Wheel.

### Language/standards (rules-python.md §2-3, spec §12)
Python **3.12 preferred / 3.11 minimum** (rules + spec) — but PRD/README/pyproject demand **3.12**
(see §5 C2). Builtin generics only (`list`/`dict`/`X | None`); absolute imports; file markers
`# start …` / `# end …`. Banned: `print()`, stdlib `logging`, `shell=True` with user input,
moviepy/playwright/tqdm/tenacity/requests/poetry, `assert` for runtime, mutable defaults, bare
`except`, `# TODO`/`pass`/`...`, magic numbers. Complexity caps: ≤50 statements, CC ≤10, ≤5 params,
≤6 returns, ≤12 branches, ≤4 nesting. Custom exception hierarchy in **`src/exceptions.py`**:
`SupoClipError` base + `DownloadError`, `TranscriptionError`, `AnalysisError`, `RenderError`,
`InsufficientSegmentsError` (spec §12.5). Pydantic strict mode `ConfigDict(strict=True,
extra="forbid")`. structlog for all logging. stamina for retries.

### Quality gate (THREE different tool lists exist — drift, see §5 C3)
- **spec §13.5** (`checkpython.sh`): ruff check + ruff format --check + mypy + pytest
  `--cov-fail-under=100` + deptry + xenon `--max-absolute B` + bandit.
- **CLAUDE.md** quality-gate section: Ruff, mypy, **pyright**, Bandit, radon/xenon, **grimp**,
  pytest.
- **rules-python.md §4 Tier 1**: ruff check, ruff format, mypy, pytest `--cov-fail-under=80`,
  deptry (Tiers 2-3 add radon, bandit, interrogate, pylint, dodgy, cohesion, refurb, vulture,
  xenon, semgrep, pip-audit, pyright, jscpd).

### Testing strategy (spec §13.2, rules §3.9)
100% coverage + 100% passing unit + 100% passing E2E mandatory (`<100% = FAILURE`). Spec mandates
`tests/unit/` (per-module test files) + `tests/integration/` (`test_pipeline_end_to_end.py` using
a <30s real fixture probed with ffprobe; `test_nicegui_pages.py` using `nicegui.testing.User`).

### VUW debugging methodology (CLAUDE.md, rules §6)
Verifiable Units of Work: one file/error per unit, mandatory pre/post git checkpoints, mandatory
verification = `./checkpython.sh` clean + 100% tests. Campaign order: stability → mypy → ruff.

---

## 5. CONTRADICTIONS & DOC-VS-DOC / DOC-VS-TREE DRIFT

These are the high-value findings for downstream agents. Each cites evidence.

**C1 — `checkpython.sh` is a PHANTOM quality gate (CRITICAL).** It is named as the MANDATORY
pre-commit gate by `docs/spec.md:1099,1190-1201`, `CLAUDE.md` (multiple places + VUW checklist),
`AGENTS.md:40`, `qa.md`, and `rules-python.md` VUW. **It does not exist in the working tree**
(`ls checkpython.sh` → No such file) nor in git history (per orchestrator ground truth).
`rules-python.md:126` even lists it under "Required files … (never modify)". Every "run
`./checkpython.sh` before commit" instruction is unexecutable. The actual gate must be reconstructed
from the tool lists in C3.

**C2 — Python version contradiction (3.11 vs 3.12).** `docs/prd.md:67` NFR table = "Python version
| 3.12"; `README.md:31` = "Python 3.12+"; `pyproject.toml:5` = `requires-python = ">=3.12"`;
`pyproject.toml:59` mypy `python_version = "3.12"`. BUT `CLAUDE.md` Prerequisites = "Python 3.11+",
and both `docs/spec.md:154` and `docs/rules-python.md:1,3` = "3.12 preferred, 3.11 minimum". The
hard build constraint (`>=3.12`) makes the "3.11 minimum" language in CLAUDE.md/spec/rules false.

**C3 — Quality-gate tool list disagreement.** Three docs list different tool sets (see §4 above):
`grimp` appears only in CLAUDE.md; `pyright` in CLAUDE.md + rules but NOT spec §13.5; `deptry` in
spec + rules but NOT CLAUDE.md. No single authoritative gate definition exists, compounded by C1.

**C4 — Coverage threshold contradiction WITHIN rules-python.md.** Prose at `rules-python.md:300-302`
says "100% test coverage mandatory. <100% = FAILURE", but the example command at
`rules-python.md:306` and the Tier-1 table at `rules-python.md:344` both use
`--cov-fail-under=80`. Spec §13.1 (`docs/spec.md:1099`) says `--cov-fail-under=100`. (Ground truth:
the actual pytest config enforces 100%, so spec is correct and rules-python.md's 80 is stale/wrong.)

**C5 — `AGENTS.md` is WHOLESALE STALE / describes the DELETED architecture (HIGH).** `AGENTS.md`
(root) still documents the pre-redesign monorepo: "three apps: `backend/`, `frontend/` (Next.js
15), `waitlist/`" (`AGENTS.md:5-9`), `./start.sh` boot (`AGENTS.md:17`), `npm install && npm run
dev` (`AGENTS.md:33-34`), Jest frontend tests (`AGENTS.md:52`), Python **3.11** backend
(`AGENTS.md:7`), `python -m src.main` "auto-selects a free port" (`AGENTS.md:27`), and references
`docs/standards.md` for conventions (`AGENTS.md:45`). Verified: `docs/standards.md` does NOT exist;
`start.sh` does NOT exist. This directly contradicts the entire "Clean Consolidation" redesign in
spec/PRD/CLAUDE.md/README (single Python process, no Node, no waitlist, port 8008).

**C6 — `frontend/` directory STILL EXISTS in the tree (HIGH, doc-vs-tree).** Spec §2.0
(`docs/spec.md:90`) states "The `frontend/` and `waitlist/` directories are deleted," and Appendix A
(`docs/spec.md:1208-1209`) lists `frontend/` (~3,900 lines) and `waitlist/` as deleted/replaced.
Ground truth + verification: `frontend/` exists (37MB, **123 git-tracked files**, incl. stale
Prisma generated client, next-env.d.ts, coverage HTML). The "deletion" promise is unfulfilled. This
also pollutes the graphify graph with non-live nodes.

**C7 — Face-detection fallback contradiction (PRD vs everything else).** `docs/prd.md:37` promises
"Face-centered using MediaPipe (primary), **OpenCV DNN (fallback), Haar cascade (last resort)**".
Every other doc mandates **MediaPipe ONLY** with a plain center-crop fallback and NO OpenCV: spec
§4.14 (`docs/spec.md:413` "no further fallback"), spec Removed-Dependencies (`docs/spec.md:140`
opencv-python removed), `CLAUDE.md` Face Detection section ("MediaPipe only … no OpenCV DNN or Haar
cascade fallbacks"), `README.md:20`. The PRD line is obsolete and must not be treated as a live
requirement.

**C8 — Confusing resolution labeling (LOW, internal spec oddity, not a true contradiction).** Spec
§6.4 (`docs/spec.md:603`) and §10.1 (`docs/spec.md:823-826`) define `720p` = 1080×1920 and `1080p`
= 2160×3840. The "720p" preset actually outputs a 1080-px-wide / 1920-tall frame; the labels refer
to loose tiers, not literal heights. Internally consistent but a likely source of confusion.

**C9 — `analyze.py` ClipSegment field-name inconsistency within the spec (LOW).** §4.11
(`docs/spec.md:327`) lists fields `start_ms:int, end_ms:int, … transcript_text`. §11.3
(`docs/spec.md:952-960`) defines the dataclass with `start_time:str (MM:SS.mmm), end_time:str, …
text`. Two different field names/types for the same model in one spec.

**C10 — rules-python.md generic config/CLI standards contradict the project's actual design
(MEDIUM).** `rules-python.md:130-144` mandates "No env vars; `config.yml` → settings;
`credentials.yml` → secrets" and "**Typer** for all CLI". The entire project instead uses `.env` +
`pydantic-settings` + env vars (PRD NFR, spec §8, CLAUDE.md, README, and a real `.env.example`
exists while `config.yml`/`credentials.yml` do NOT). rules-python.md is a generic house-style doc
whose §3.2/§3.3 do not apply to this project; downstream should defer to spec §8 for config.

**C11 — `src/exceptions.py` mandated but absent (MEDIUM, doc-vs-tree — flag for code-audit).** Spec
§12.5 (`docs/spec.md:1051`) requires the exception hierarchy in `src/exceptions.py`. Verified: no
`src/exceptions.py` exists; exception classes are instead defined inline across pipeline modules
(`src/pipeline/{analyze,clip,transcribe,download}.py`). Centralization promise unmet (code-audit to
confirm the hierarchy is otherwise complete).

**C12 — `src/scripts/` mandated by P2 but absent (LOW).** `rules-python.md:14` / P2 requires the
"single quality utility in `src/scripts/`". Verified: `src/scripts/` does not exist. Tied to the
missing `checkpython.sh` (C1).

**C13 — Transitions feature promised but unspecified (MEDIUM, PRD-gap to validate).** Transitions
are a PRD feature (F8, `prd.md:39`), README, and CLAUDE.md ("round-robin"), and a `transitions/`
dir is in the structure. BUT spec §4 defines NO transitions pipeline module and the spec flow §5
never mentions transitions. `rg` finds "transition" references in `src/config.py`,
`src/pipeline/analyze.py`, `src/pipeline/clip.py` but there is no dedicated module. Downstream
PRD-validation should determine whether transitions are actually implemented or a phantom feature.

**C14 — Root-level doc sprawl vs P3 (LOW principle note).** P3 (`rules-python.md:15`) says all docs
live in `docs/` with `CLAUDE.md` the sole root exception. Root currently also holds `AGENTS.md`,
`qa.md`, `recipe.md`, `README.md`. (README at root is conventional; the others are stale planning
artifacts — `recipe.md:14` even says "docs/spec.md (does not exist)", which is itself now obsolete
since spec.md exists.)

### Items that are CONSISTENT across docs (no drift — stated explicitly)
- Port 8008, start command `python -m src.main`, NiceGUI single-process, SQLite 3-table schema,
  `uv` package manager, ffmpeg-only video, pysubs2 ASS subtitles, parakeet-mlx transcription model
  default, local-LLM-default config — all agree across spec/CLAUDE/README/PRD.
- Subtitle vertical position: CLAUDE.md "75% down" == spec `vertical_margin=25` (% from bottom,
  BOTTOM_CENTER) — consistent.

---

## 6. HISTORICAL CONTEXT (for root-cause framing)
`docs/progress/fixes/MASTER-QA-REPORT-2026-02-15.md` is the PRE-redesign audit (28 issues:
1 blocker, 5 critical, 13 high, 9 medium) against the OLD `backend/` monorepo (e.g.,
`video_utils.py` 1933-line grade-C monolith, 25 files with legacy typing imports, non-Pydantic
Config). The "Clean Consolidation" redesign (spec.md) is the response to that report. Downstream
agents should NOT treat MASTER-QA findings as live — they describe deleted code — but the
recurring theme (over-engineering, output/formatting breakage) matches the orchestrator's note that
recent fix commits were runtime-rendering bugs (clipped subtitles, HTML sanitization, LLM base_url,
YouTube Live URLs), i.e., the "plagued with output issues" complaint is about runtime behavior, not
static code health (which is currently clean: 466 tests pass, 100% coverage, ruff/mypy clean).

---

## 7. GUIDANCE FOR DOWNSTREAM AGENTS
- Treat **spec.md as the authoritative "promised" baseline** for modules, schema, config, and
  pipeline behavior. Where PRD contradicts spec (C7 face-detection), spec wins.
- Treat **PRD §2 feature table (this doc)** as the checklist for PRD-validation, applying the C7
  correction.
- The quality gate to actually run is the union of tool lists (C3); `checkpython.sh` itself is
  absent (C1) — do not rely on it; use the orchestrator's already-measured ground truth.
- Open verification items for code-audit: C11 (`src/exceptions.py`), C13 (transitions module),
  C6 (frontend/ removal), and whether `RECONSTRUCT_WORDS_WITH_LLM` word-reconstruction (spec §4.10)
  is implemented.
- No input file was inaccessible; no fabrication. All claims above cite file:line or a verified
  shell check.
