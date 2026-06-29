# SupoClip Audit Synthesis — Systemic Themes & Root Causes

**Author:** Synthesis (QA-lead) agent
**Date:** 2026-06-29
**Inputs:** all 13 audit notes in `output/notes/` + 4 `_ground_truth_*.txt` files
**Method:** dedup + root-cause grouping across docs-review, prd-validation, principles-validation,
testing-audit, deadcode-frontend, 6 code-review files, 2 FOSS-research files.

Static health is GREEN (466 tests pass, 100% line coverage, ruff/mypy clean). The findings
below are all things that GREEN CI does not see. That gap is itself the headline.

---

## THE META ROOT CAUSE (read first)

**The "Clean Consolidation" redesign was specified and documented as DONE, but was executed
only at the module-skeleton level. Every pipeline stage exists and is individually unit-tested
to 100% line coverage with mocks — but the WIRING between stages was never completed or
integration-tested, and nothing enforced end-to-end correctness because the mandated quality
gate (`checkpython.sh`) is a phantom that does not exist.**

Three consequences cascade from this single cause:

1. **Modules work in isolation, the app does not work as a whole.** The four most damaging bugs
   are all *wiring gaps* between correctly-built parts: Settings→clip (subtitles never applied),
   main→static-mount (clips 404), home→UserPreferences (settings ignored), callback→UI (progress
   is DB-polled not pushed). Each individual module passes its tests; the seams are untested.

2. **The redesign was a "paper migration."** `docs/spec.md` says `frontend/` and `waitlist/`
   were "deleted" — but `git rm` was never run. 37 MB / 123 files remain. `AGENTS.md`,
   `.pre-commit-config.yaml`, and `tests/verify_subtitle_renderer.py` still describe/import the
   deleted `backend/` + React + Playwright architecture.

3. **No enforced gate → unbounded drift.** `checkpython.sh` is cited as MANDATORY by spec.md,
   CLAUDE.md, AGENTS.md, qa.md, rules-python.md — and exists nowhere (not in tree, not in git
   history). With nothing actually run, doc-vs-code and doc-vs-doc drift accumulated unchecked:
   9 of 14 spec config vars are absent, status is `completed` vs spec `done`, 3 doc files list
   3 different quality-gate tool sets, Python 3.11-vs-3.12 disagreement, etc.

---

## THEME 1 — OUTPUT-CORRECTNESS: why 100% green tests still ship broken output

**Root cause:** The test suite mocks every I/O boundary (ffmpeg `subprocess`, MediaPipe, the LLM,
`asyncio.to_thread`, NiceGUI widgets). It validates Python control flow, never a real artifact.
Coverage is **line**, not **branch** (`pyproject.toml:54` — `--cov-branch` absent), so the 100%
number is achievable with half the conditional arms never exercised. No test ever produces or
inspects a real `.mp4`, `.ass`, or rendered HTML page. `tests/fixtures/sample_video.mp4` (a real
5441-byte MP4) sits committed and referenced by ZERO tests. The four recent fix commits
(a3af789, 92dfc0f, 529be05, 4a751dc) were all found at runtime, not by tests.

**Worse — unit tests CODIFY the broken behavior as correct:** `test_clip.py:342` asserts
"write_ass_file is NOT called when subtitle_style is None", `test_video_service.py:138-140`
asserts `subtitle_style is None` is the correct default. The tests pin the dead wiring in place.

The output bugs this hides (the user's "plagued with formatting/output issues" complaint):

| # | Bug | Location | Effect |
|---|-----|----------|--------|
| O1 | **Subtitles + ALL font/style customization never applied to clips.** `home.py` builds `ProcessingRequest` with `subtitle_style=None`; `clip.py:310` guards all subtitle generation behind `if opts.subtitle_style is not None`. Settings page is dead end-to-end. | `home.py:91-97`, `video_service.py:384-392`, `clip.py:310` | Every UI-produced clip has NO burned-in captions. The entire headline feature is dead. |
| O2 | **Clip playback + download return HTTP 404.** `main.py` never calls `app.add_media_files('/clips/', ...)`. Task page renders `/clips/{filename}`. | `main.py` (missing), `task.py:79,106` | Users can never view or download any clip. |
| O3 | **ffmpeg filter-path injection / no escaping.** `ass={ass_path}:fontsdir={fonts_dir}` interpolated raw into `-vf`. Any space/colon/comma in `TEMP_DIR` breaks the filtergraph. Spec 10.4 requires escaping. Tests use clean `/tmp/`. | `clip.py:212-215` | Silent ffmpeg failure on real project paths. |
| O4 | **BGR frame passed to RGB-expecting MediaPipe.** No `cv2.cvtColor(...BGR2RGB)` before `detector.process()`. | `face_detect.py:62` | Degraded detection → faces missed → silent center-crop. |
| O5 | **cv2-absent fallback returns hardcoded (1920,1080).** A portrait source gets cropped as landscape. cv2 is an undeclared transitive dep (via mediapipe). | `clip.py:392-396`, `face_detect.py:170-174` | Wildly wrong crop box, no user-visible error. |
| O6 | **Karaoke/context-line subtitle UX not implemented.** Spec 9.2 core differentiator: active word primary + dimmed context words via ASS inline tags. Code emits one bare word per event. | `subtitles.py:125-188` | Isolated single-word flashes; product-quality regression invisible to tests. |
| O7 | **`custom_prompt` dropped from the LLM *user* prompt** (only in system prompt). | `analyze.py:542` | Custom AI instructions silently weakened/ignored, esp. on local LLMs. |
| O8 | **LLM timestamps never bounds-checked vs video duration.** Hallucinated `start=300` on a 150s video passes validation. | `analyze.py` `validate_segments` | Blank/0-byte clips from ffmpeg seek past EOF. |
| O9 | **`error_message` column never written** (code writes `progress_message` instead). | `video_service.py:123-124` vs `models.py:72` | Error banner always shows generic "unknown error"; reloaded failed task shows no error at all. |
| O10 | **Resolution labels disagree with spec** (`720p`=720×1280 in code vs 1080×1920 in spec). | `clip.py:44-48` | Default output smaller than the spec'd default. |
| O11 | **Uploads written to hardcoded `/tmp`**, not `temp/uploads/`; violates explicit project rule; risks FileNotFoundError mid-pipeline. | `home.py:150` | Upload path may vanish between stages. |
| O12 | **Non-YouTube URL input broken** — stored `source_type='upload'`, treated as local path → FileNotFoundError. | `home.py:219`, `video_service.py:330-334` | Direct/Vimeo/.mp4 URLs unusable. |
| O13 | **No ffmpeg / transcription timeout** — a hung subprocess stalls the pipeline forever. | `clip.py:339`, `video_service.py:343` | Indefinite hang on corrupt input. |

**Why it matters for remediation:** Fixing O1–O13 individually is necessary but insufficient.
The durable fix is a real integration test that runs the actual home→service→clip path with
`sample_video.mp4`, calls real ffmpeg, and `ffprobe`-asserts dimensions/codec/non-zero bytes,
plus a browser smoke test of the served `/clips/` route and the phone-frame preview. Without
that, the same class of bug recurs.

---

## THEME 2 — DEAD CODE & DEBT: the paper migration

**Root cause:** redesign documented complete, never physically executed.

| Item | Size / scope | Evidence | Action |
|------|--------------|----------|--------|
| `frontend/` React/Next.js + Prisma | 37 MB, 123 git-tracked files, **32% (667/2056) of graphify nodes** | spec.md:90 says "deleted"; still present | `git rm -r frontend/`, add to `.gitignore`, regen graphify |
| `checkpython.sh` phantom gate | does not exist in tree OR git history | cited mandatory in 5 docs | create it (union of tool lists) |
| `.pre-commit-config.yaml` | every hook scoped `^backend/` (nonexistent dir) → all no-ops | file content | rescope to `^(src\|tests)/` |
| `tests/verify_subtitle_renderer.py` | imports `src.subtitle_renderer.BrowserSubtitleRenderer` (deleted) + `backend/` path | file:7,9 | `git rm` |
| `tests/output/logo_test.mp4` | stray tracked binary artifact | git ls-files | `git rm` |
| `supoclip.db` | 24 KB dev DB tracked despite `*.db` ignore | git ls-files | `git rm --cached` |
| `.serena/memories/` | 12 tracked session-context files | git ls-files | `git rm -r --cached`, ignore |
| `graphify-out/` | 13 MB generated, untracked but not ignored | git status | add to `.gitignore` |
| `AGENTS.md` | wholesale stale: documents `backend/`, `frontend/` Next.js, `waitlist/`, `npm`, Jest, `./start.sh`, `docs/standards.md` (none exist) | AGENTS.md:5-52 | rewrite for single-Python app |
| Stub fields / dead exports | `logo_path`, `add_transitions`, `transitions_dir` (clip), `clip_order` (never persisted), `words` param (analyze), `Task.title`, `Task.settings_json`, `get_video_info()`, `DEFAULT_BACKEND_PORT`, `app_port` | per code-reviews | remove or implement |
| Redundant URL regex 1-7 | pattern 0 is a superset; unreachable | download.py:37-43 | collapse to pattern 0 + urlparse fallback |

**Perverse coverage incentive:** the 100% rule forces tests for dead exports (`get_video_info`
is tested but called nowhere in `src/`), making dead code look alive.

---

## THEME 3 — DOC-VS-REALITY DRIFT: no single source of truth

**Root cause:** aspirational spec + unenforced gate. Five docs (PRD, spec, CLAUDE.md, rules-python,
AGENTS.md) disagree with each other and with the tree.

- **Phantom gate** (`checkpython.sh`) — Theme 2.
- **Quality-gate tool lists disagree 3 ways:** `grimp` only in CLAUDE.md; `pyright` in
  CLAUDE.md+rules not spec; `deptry` in spec+rules not CLAUDE.md.
- **Python version:** PRD/README/pyproject demand `>=3.12`; CLAUDE.md/spec/rules say "3.11
  minimum" — false given the hard build constraint.
- **Coverage threshold:** rules-python.md says both "100% = mandatory" (prose) and
  `--cov-fail-under=80` (its example + table); actual config enforces 100%.
- **Face detection:** PRD promises 3-tier MediaPipe→OpenCV DNN→Haar; spec/CLAUDE/code = MediaPipe
  only. PRD line is obsolete.
- **Config drift:** 9 of 14 spec env vars absent in `config.py` (`PARAKEET_MODEL`,
  `RECONSTRUCT_WORDS_WITH_LLM`, `MAX_VIDEO_DURATION`, `MAX_CLIPS`, `FFMPEG_PRESET`, `FFMPEG_CRF`,
  `HOST`, `MAX_WORKERS`, `LOG_DIR`); `PORT` aliased as `BACKEND_PORT` and ignored (main.py
  hardcodes 8008).
- **Schema/status drift:** status `completed` vs spec `done`; `GeneratedClip` missing
  `reasoning`/`clip_order`/`updated_at`; `UserPreferences` missing `logo_position`/target count;
  `MM:SS.mmm` vs float seconds; field renames (`ai_prompt` vs `custom_ai_prompt`).
- **Spec WebSocket-push vs actual 1s DB polling** (task.py:262); callback path implemented but
  unwired.
- **Missing `src/exceptions.py`** hierarchy (spec 12.5) — exceptions defined ad hoc per module,
  no common `SupoClipError` base.
- **Stale root docs** (`qa.md`, `recipe.md`) vs P3 "docs in docs/".

**Resolution rule for downstream:** treat `spec.md` as authoritative for modules/schema/config;
where PRD contradicts spec, spec wins; reconcile docs to the GREEN code reality and delete
phantoms.

---

## THEME 4 — TEST QUALITY vs QUANTITY: coverage-as-metric over coverage-as-confidence

466 tests / 100% line coverage is quantity. Quality gaps:
- **No branch coverage** (`--cov-branch` absent).
- **Fully-mocked "E2E"** — `_generate_clips_concurrently` (the ffmpeg caller) replaced by
  AsyncMock; no real subprocess. (`test_pipeline_e2e.py:70-98`)
- **NiceGUI tests are smoke-only** — every widget is a chaining MagicMock; `render()` then
  `assert True`. Cannot catch the phone-frame/HTML preview class of bugs.
- **ASS special-char escaping untested** — `{`, `}`, `\N` words would be parsed as style tags.
- **Settings→clip style pipeline never exercised whole** — `ClipOptions` mocked in every
  `TestProcessVideo`.
- **Crop math untested for odd/edge dims.**
- **Real fixtures unused** (`sample_video.mp4`, `sample_logo.png`).
- **The 100% rule actively rewards dead-code tests and pins broken wiring** (Themes 1-2).

**Genuinely good:** integration DB tests (`test_settings_persistence.py`,
`test_pipeline_failures.py`) use a real aiosqlite engine — keep and extend this pattern to ffmpeg.

---

## THEME 5 — COMPLEXITY HOTSPOTS (project's own A/B rule violated)

3 grade-C functions (independently re-run via radon), all from accumulated guards/branches, all
straightforwardly extractable (not over-abstracted):
- `src/pipeline/transcribe.py:195` `_tokens_from_result`
- `src/pages/settings.py:46` `_discover_fonts`
- `src/services/video_service.py:266` `process_video` (extract 5 `_run_<stage>` helpers)

---

## THEME 6 — PRD GAPS: promised features that are stubs or unbounded

- **Logo overlay** — `clip.py:87` "not yet implemented"; `logo_path` threaded but never applied.
- **Transitions** — PRD F8 + CLAUDE.md "round-robin"; `transitions/` dir + `TRANSITIONS_DIR`
  config exist, but `add_transitions`/`transitions_dir` are reserved-for-future no-ops.
- **`MAX_WORKERS` concurrency cap absent** — unbounded `TaskGroup` spawns ALL clips at once
  (resource risk). (`video_service.py:252-254`)
- **Multi-frame face aggregation** (spec 4.14, up to 10 frames + median x-center) — code samples
  exactly 1 frame at a hardcoded +1.0s.
- **Soft-delete is actually hard-delete**; per-clip delete missing; **delete leaves .mp4 files on
  disk** (storage leak).
- **History pagination missing**; `ui.card` list instead of spec `ui.table`.
- **Upload `accept` filter / max size missing**; non-video files enter the pipeline.
- **Home page ignores `UserPreferences`** for slider defaults (Settings is a no-op for them too).
- **`get_llm_model()` silently falls back to `openai:gpt-4o`** instead of raising ValueError
  when misconfigured.
- **DateTime columns lack `timezone=True`** — latent TZ-aware/naive `TypeError` for any future
  `now()` comparison.

---

## THEME 7 — CROSS-CUTTING STANDARD VIOLATIONS (single-VUW fixes)

- **stdlib `logging` instead of mandated `structlog`** in `video_service.py`, `analyze.py`,
  `download.py` (rest of tree uses structlog).
- **`Config()` direct instantiation bypasses `get_config()` lru-cache singleton** in
  `analyze.py:364,428,538` and `video_service.py:302` (re-parses `.env` every call; defeats
  test patching).
- **Magic numbers** vs config: ffmpeg `fast`/`23` (clip.py), `chunk_duration=120`/`overlap=15`
  (transcribe.py), face offset `1.0` (clip.py), `10_485_760` (download.py).
- **`ensure_temp_dirs()` defined but never called** in startup → fresh installs may
  FileNotFoundError on first upload.
- **`database.py` swallows `ModuleNotFoundError`** on `import src.models` at DEBUG → could
  silently create a zero-table DB.

---

## THEME 8 — FOSS-BORROW OPPORTUNITIES (from research notes)

Highest leverage borrowings (all compatible with all-Python single-process constraints):
1. **Karaoke/context-line ASS subtitles** — already SPEC'd (9.2), unimplemented; pysubs2 already
   present. This is borrow + spec-compliance in one. (HIGH)
2. **Multi-frame face tracking + smoothing** (ClipsAI / ai-shorts) — fixes single-frame jitter &
   speaker movement; closes spec 4.14 gap. (HIGH)
3. **TextTiling + BERT pre-segmentation before LLM scoring** — deterministic boundaries, fewer
   tokens, less hallucination, better long-video handling. (MEDIUM)
4. **JSON-retry + `@stamina.retry` on the LLM call** (spec 11.5 requires it; download.py already
   does it; analyze.py omits it). (MEDIUM — also a spec gap)
5. **Virality/engagement scoring + clip dedup** post-LLM. (LOW)
6. **Dynamic font sizing by clip length**; optional Pyannote diarization; scene detection. (LOW)

Note: parakeet-mlx (vs WhisperX) and ffmpeg/pysubs2/yt-dlp choices are sound — keep.

---

## CONSOLIDATED, DEDUPLICATED, PRIORITIZED ISSUE LIST

### CRITICAL (app is non-functional for its core purpose)
- **C-1 Subtitles + all style customization never reach clips** (O1). Wire `UserPreferences` →
  `ProcessingRequest.subtitle_style` in `home.py`; remove tests that pin `subtitle_style=None`.
- **C-2 Clips 404** (O2). Add `app.add_media_files('/clips/', temp/clips)` in `main.py:_startup`.
- **C-3 37 MB dead `frontend/`** + paper-migration debt (Theme 2). `git rm -r`, regen graphify.
- **C-4 Phantom `checkpython.sh` gate** (Theme 2/3). Create it; no end-to-end correctness is
  enforced until it exists and runs in pre-commit/CI.
- **C-5 No real-output test** (Theme 1/4). Add fixture-based ffmpeg integration test +
  `/clips/` route + preview smoke test; this is what would have caught C-1, C-2, O3-O13.

### HIGH
- H-1 ffmpeg filter-path escaping (O3).
- H-2 BGR→RGB conversion for MediaPipe (O4).
- H-3 cv2-absent hardcoded-dimensions wrong crop; replace cv2 probe with `ffprobe`, fail loud (O5).
- H-4 Karaoke/context-line subtitles unimplemented (O6, FOSS-1).
- H-5 `custom_prompt` not in user prompt (O7).
- H-6 LLM timestamps not bounds-checked vs duration (O8).
- H-7 `error_message` never written → broken error banner (O9).
- H-8 stdlib logging instead of structlog ×3 modules (Theme 7).
- H-9 `Config()` bypasses singleton ×4 (Theme 7).
- H-10 Unbounded clip concurrency (no MAX_WORKERS) (Theme 6).
- H-11 Stale `.pre-commit-config.yaml` (^backend/) + stale `AGENTS.md` + dead
  `verify_subtitle_renderer.py` (Theme 2).
- H-12 Uploads to `/tmp` (O11); non-YouTube URL broken (O12).
- H-13 `@stamina.retry` + `InsufficientSegmentsError` + `src/exceptions.py` missing (Theme 3).

### MEDIUM
- M-1 Add `--cov-branch` + branch floor (Theme 4).
- M-2 3 grade-C functions refactor (Theme 5).
- M-3 No ffmpeg/transcription timeout (O13).
- M-4 Logo overlay + transitions: implement or remove stubs (Theme 6).
- M-5 Multi-frame face aggregation (FOSS-2, spec 4.14).
- M-6 Hard-delete + orphaned .mp4 leak; per-clip delete; pagination (Theme 6).
- M-7 9 missing spec config vars; magic numbers → config (Theme 3/7).
- M-8 DateTime `timezone=True`; `ensure_temp_dirs()` call; ModuleNotFoundError guard removal
  (Theme 7).
- M-9 `get_llm_model()` silent gpt-4o fallback → raise ValueError (Theme 6).
- M-10 Upload `accept` filter + max size; home loads UserPreferences defaults (Theme 6).
- M-11 Resolution label reconciliation (O10).
- M-12 Async-in-sync-lambda delete may no-op (`history.py:127`); fire-and-forget create_task
  leaves stuck "pending" tasks.

### LOW
- L-1 Redundant URL regex; dead exports/columns (`get_video_info`, `Task.title`,
  `settings_json`, `app_port`, `DEFAULT_BACKEND_PORT`, `clip_order` param, `words` param).
- L-2 `supoclip.db`/`.serena/memories` untrack; `graphify-out/` ignore.
- L-3 `_truncate` DRY dup; double-commit; `# type: ignore` cleanups; `# noqa: F401` removal.
- L-4 CSS injection from font family in preview; doc consolidation (qa.md/recipe.md → docs/).
- L-5 FOSS polish: TextTiling pre-seg, virality scoring, dynamic font size, diarization, scene
  detection.

---

## ROOT-CAUSE SUMMARY (one line each)

1. **Wiring gaps, not module bugs** — parts are tested in isolation; seams are not. → C-1, C-2, O7, O9.
2. **Over-mocked tests + line-only coverage** — no real artifact ever produced/inspected. → all of Theme 1.
3. **Paper migration** — redesign documented done, `git rm` never run. → Theme 2.
4. **Unenforced phantom gate** — nothing runs end-to-end, so drift never surfaces. → Themes 2,3.
5. **Coverage-as-target perversity** — 100% rule rewards dead-code tests, pins broken wiring. → Themes 1,2,4.

No input file was inaccessible. No claim is uncited. Where notes disagreed, spec.md was treated
as authoritative per docs-review guidance.
