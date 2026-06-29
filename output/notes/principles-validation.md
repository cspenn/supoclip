# First Principles Validation — SupoClip

Audit-only. No source files modified. Evidence cited as `file:line`.
Ground-truth from orchestrator used verbatim (pytest 466 pass, 100% cov, ruff/mypy clean,
3 radon-C functions, leftover frontend/, phantom checkpython.sh).

---

## P1 — Fix-Over-Create (refactor existing; new files only when justified) — FAIL

The project standard (CLAUDE.md "Maximum radon/xenon complexity grade of A or B; C and
below must be refactored") is violated by **3 confirmed grade-C functions** (independently
re-run via `radon cc src/ -nc`):

- `src/pipeline/transcribe.py:195` `_tokens_from_result` (C) — nested sentence/token loops
  with multiple guard clauses.
- `src/pages/settings.py:46` `_discover_fonts` (C) — nested nameID/record loops + fallback
  branches.
- `src/services/video_service.py:266` `process_video` (C) — long linear orchestration with
  many try/except stages.

Remediation: extract helpers to bring each to grade A/B. None are over-abstracted; the C
grade is from accumulated guards/branches, so straightforward extraction applies.

Unjustified leftover files (creation/retention not justified by current all-Python scope):
- `frontend/` (37MB, 123 git-tracked files) — deleted-from-scope React/Next.js + Prisma.
- `tests/verify_subtitle_renderer.py` and `tests/output/logo_test.mp4` (see P2).

---

## P2 — Reusable Testing (no one-off scripts; utilities located correctly) — FAIL

- `tests/verify_subtitle_renderer.py` is a one-off verification script, **not a pytest test**
  (defines `verify_styling()`, no `test_` functions, not collected). Worse, it is **broken
  dead code from the old architecture**: it does `sys.path.append(.../"backend")`
  (`tests/verify_subtitle_renderer.py:7`) and `from src.subtitle_renderer import
  BrowserSubtitleRenderer` (`:9`). Neither `src/subtitle_renderer.py` nor a `backend/`
  directory exists (`fd subtitle_renderer src/` → empty; `fd -t d backend` → empty). Running
  it raises `ModuleNotFoundError`. It is git-tracked (`git ls-files` confirms).
  `BrowserSubtitleRenderer` is the Playwright-era renderer removed in the redesign.
- `tests/output/logo_test.mp4` — stray git-tracked binary test artifact committed into the
  repo. Belongs in a gitignored temp/output path, not version control.

Remediation: delete `tests/verify_subtitle_renderer.py` (orphaned, references nonexistent
modules) and untrack `tests/output/logo_test.mp4`.

Scope note: no `src/scripts/` directory exists (`fd -t d scripts src/` → empty; `tree src`
confirms), so no mislocated utilities there. The misplaced/dead test artifacts above are the
only P2 findings.

---

## P3 — Docs Location (all docs in docs/; CLAUDE.md the only root exception) — MINOR

Core docs correctly in `docs/` (prd.md, spec.md, rules-python.md, orientation.md, etc.).
Root contains: `CLAUDE.md` (allowed), `README.md` (conventional), `AGENTS.md` (agent config,
conventional). Two project docs sit at root that arguably belong under `docs/`:
- `qa.md` (root) — quality-gate documentation.
- `recipe.md` (root) — project doc.

Reported literally against the rule as written ("CLAUDE.md the only root exception"), the
deviating root files are: `AGENTS.md`, `README.md`, `qa.md`, `recipe.md`. README and AGENTS
are conventional and likely acceptable; `qa.md` and `recipe.md` are the genuine outliers that
should move under `docs/`. Low severity. (Cross-ref: `qa.md` documents `./checkpython.sh` as
the mandatory gate, which does not exist in the tree or git history — phantom gate.)

---

## P4 — Never Defer (no TODO/FIXME/"for now"/"out of scope") — PASS

`rg -i "TODO|FIXME|fix later|out of scope|for now|unrelated|hack|xxx" src/` → **None found**.
Clean.

---

## P6 — Anti-Elision (no stubs, `...`, bare pass, NotImplementedError, truncation) — PASS

`rg "NotImplementedError|^\s*\.\.\.\s*$" src/` → none. No bare `pass` bodies
(`rg "^\s*pass\s*$" src/` → none). No stubs/truncations found. Clean.

---

## P7 — Contextual Strictness (validate signatures/dict keys/state) — MOSTLY PASS (1 low)

Good defensive patterns: `_tokens_from_result` (`transcribe.py:210-236`) uses `getattr(...,
default)` throughout for the untyped `AlignedResult`; `clip.py:392-408` guards optional cv2
and checks `width>0 and height>0`.

One low concern: `src/pipeline/subtitles.py:159-160,172` directly indexes
`word_data["start_ms"]`, `word_data["end_ms"]`, `word_data["text"]` (note line 166 uses
`.get("text")` for logging, then 172 hard-indexes `["text"]` — inconsistent). This assumes an
undocumented dict contract. The upstream producer `_tokens_from_result`
(`transcribe.py:222`) emits keys `text/start/end` (seconds), not `start_ms/end_ms`, so a
conversion layer is implied but the key contract is unvalidated. A malformed word dict raises
`KeyError` (which propagates loudly — acceptable failure mode), but there is no explicit
validation/schema. Low severity since 100% tests exercise the live contract.

---

## P8 — Explicit Failure Propagation (no swallowed exceptions) — PASS (strong)

Well-designed domain error model (the AnalysisError/DownloadError god-nodes are a deliberate
hierarchy):
- Domain exceptions: `AnalysisError` (`analyze.py:60`), `ClipGenerationError`
  (`clip.py:99`), `TranscriptionError` (`transcribe.py:34`), `DownloadError`
  (`download.py:48`).
- Proper chaining: `raise AnalysisError(...) from exc` (`analyze.py:406,559`),
  re-raise of domain errors then wrap-unexpected (`analyze.py:555-559`).
- `process_video` updates Task status to "failed" then re-raises at each stage
  (`video_service.py:327,333-334,349-353,370`), with a top-level handler that logs with
  `exc_info=True` and returns a `ProcessingResult(error=...)` (`:443-450`) — failure surfaces
  to the UI, not swallowed.
- DB session `except Exception: rollback(); raise` (`database.py:63-65`) — re-raises.
- Font/import fallbacks (`settings.py:77-84`, `face_detect.py:50`, `clip.py:394`) log and
  degrade gracefully — appropriate, not silent.

The two `# noqa: BLE001` blind-excepts (`transcribe.py:144,186`) were inspected: both are
optional transcript-cache load/save fallbacks that log a warning and degrade gracefully
(return None / no-op) — not pipeline-error swallowing. `transcribe.py:289` wraps the model
call and re-raises `TranscriptionError(...) from exc`. PASS confirmed.

One nuance (not a failure): per-clip generation errors are caught and logged at warning,
continuing (`video_service.py:245-250`), but the **all-clips-failed** case is explicitly
guarded and raised (`:404-407`). Partial-failure tolerance is intentional and bounded.

---

## P9 — Idempotent Mutation (idempotent file/db ops; state verified) — MOSTLY PASS (1 med)

Idempotent ops verified:
- `init_db` is explicitly idempotent with an early return when `_engine is not None`
  (`database.py:80-82`) and docstring states it (`:71`).
- Directory creation uses `mkdir(parents=True, exist_ok=True)` (`video_service.py:304`).
- `Base.metadata.create_all` (`database.py:104`) is create-if-not-exists.

Non-idempotent write path: `_save_generated_clip` (`video_service.py:135-164`) performs a
bare `session.add(GeneratedClip(...))` insert with **no upsert / no dedup** on
`(task_id, clip_order)`. Re-processing the same `task_id` (retry, re-run) appends duplicate
clip rows rather than replacing. State is not verified before mutation. Medium severity.
Remediation: delete existing clips for the task first, or upsert on (task_id, clip_order).

---

## P10 — Simplicity (no premature abstraction / needless complexity) — PASS

No premature abstraction observed. Error hierarchy is minimal and earns its keep. The C-grade
`process_video` is long but a flat, readable orchestration (not over-engineered) — its issue
is length/branching (P1), not unnecessary abstraction. Pipeline modules are single-purpose.

---

## P12 — Never Reinvent (use proven FOSS) — MOSTLY PASS (1 low)

Correctly leans on FOSS: ffmpeg (clip ops), yt-dlp (download), pysubs2 (ASS), mediapipe (face
detect), parakeet-mlx (transcribe), pydantic-ai/groq (LLM).

One low concern: `clip.py:392-408` uses OpenCV (`cv2.VideoCapture` /
`CAP_PROP_FRAME_WIDTH/HEIGHT`) to probe video dimensions, whereas the project-canonical tool
is `ffprobe` (ships with the already-required ffmpeg; spec says "all video operations via
ffmpeg"). This adds a soft cv2 dependency for a job ffprobe already does. Borderline
silent-error too: on cv2 unavailable or read failure it returns a **hardcoded (1920, 1080)
guess** (`:396,405,408`) rather than failing, which can drive an incorrect 9:16 crop box
silently. Low severity; recommend ffprobe + explicit failure instead of a magic-number
default.

---

## Summary Verdict

| Principle | Verdict |
|-----------|---------|
| P1 Fix-Over-Create | FAIL (3 grade-C functions) |
| P2 Reusable Testing | FAIL (broken orphan script + tracked binary) |
| P3 Docs Location | MINOR (qa.md, recipe.md at root) |
| P4 Never Defer | PASS |
| P6 Anti-Elision | PASS |
| P7 Contextual Strictness | MOSTLY PASS (1 low: subtitle dict keys) |
| P8 Failure Propagation | PASS (strong error model) |
| P9 Idempotent Mutation | MOSTLY PASS (clip insert not idempotent) |
| P10 Simplicity | PASS |
| P12 Never Reinvent | MOSTLY PASS (1 low: cv2 dim probe + magic default) |
