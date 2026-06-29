# Code Review: src/services/video_service.py and src/main.py

**Auditor:** Code Review Agent (Sonnet 4.6)
**Date:** 2026-06-29
**Scope:** `src/services/video_service.py` (453 lines) and `src/main.py` (65 lines)
**Test status (measured):** 466 passed / 0 failed, 100% line coverage, ruff clean, mypy clean

---

## Methodology

All claims are grounded in the actual file content. Cross-checked against:
- `src/models.py` (data model)
- `src/pages/task.py` (UI consumer of task/clip fields)
- `src/pages/home.py` (caller of `process_video`)
- `src/config.py` (Config singleton pattern)
- `docs/prd.md` and `docs/spec.md` (requirements)
- CLAUDE.md (project coding standards)

---

## src/main.py

### ✅ Good

**Clean orchestration-only design** (`src/main.py:1-65`): 65 total lines. Registers startup/shutdown hooks and four `@ui.page` routes. Core logic lives in services and pages as required. Matches CLAUDE.md rule about main.py being "orchestration-focused."

**`__mp_main__` guard** (`src/main.py:63`): `if __name__ in {"__main__", "__mp_main__"}:` correctly handles NiceGUI's multiprocessing mode where the module is re-imported under the name `__mp_main__`. Tests verify this path (test_main.py:188-238).

**Lazy `close_db` import in `_shutdown`** (`src/main.py:51-52`): Avoids circular imports; consistent with project pattern.

**`reload=False`, `show=False`** (`src/main.py:60`): Correct for server-mode operation. Does not auto-open browser; does not enable hot-reload in production.

### ❌ Bad

**`# noqa: F401` on an actively-used import** (`src/main.py:7`): `from nicegui import app, ui  # noqa: F401` — both `app` and `ui` are used throughout the module. The noqa comment is either vestigial from a draft or was added to suppress a linter quirk; it should be removed to avoid masking any future genuine unused-import warnings.

### ❓ Missing — CRITICAL

**No static/media file mount for `/clips/`** (`src/main.py`, `src/pages/task.py:79,106`): `main.py` never calls `app.add_static_files('/clips/', ...)` or `app.add_media_files('/clips/', ...)`. The task page renders both a video player and a download button using the URL `/clips/{clip.filename}`:

```python
# src/pages/task.py:79
ui.video(src=f"/clips/{clip.filename}").classes("w-full rounded")

# src/pages/task.py:106
on_click=lambda c=clip: ui.download(f"/clips/{c.filename}")
```

NiceGUI's `app.add_media_files(url_path, local_directory)` (for streaming) or `app.add_static_files()` must be called during startup to make the `temp/clips/` directory accessible at `/clips/`. Without this mount, **every clip playback and download returns HTTP 404 in the live application**. This is a critical runtime defect that unit tests do not catch (tests mock the pipeline; no test exercises the HTTP route for actual video serving).

The appropriate registration, missing from `_startup()`:
```python
app.add_media_files('/clips/', Path(cfg.temp_dir) / 'clips')
```

CLAUDE.md spec confirms: "Clips served via FastAPI static files at `/clips/{filename}`".

**No `ensure_temp_dirs()` call on startup** (`src/main.py:43-46`, `src/config.py:89-95`): `_startup()` calls `init_db()` but never calls `cfg.ensure_temp_dirs()`. The `Config` class provides this helper to create `temp/`, `temp/uploads/`, and `temp/clips/`. Real-world impact is near-zero: `process_video` self-creates `temp/clips/` with `mkdir(parents=True, exist_ok=True)` (video_service.py:304), and uploaded files currently land in `/tmp/` (home.py:150) rather than `temp/uploads/`. The missing call is a consistency gap against the documented API rather than a concrete failure path.

---

## src/services/video_service.py

### ✅ Good

**`@dataclass(slots=True)` for `ProcessingRequest`/`ProcessingResult`** (`video_service.py:50,75`): Follows CLAUDE.md requirement for memory-efficient data structures.

**`asyncio.TaskGroup` for concurrent clip generation** (`video_service.py:252-254`): Correct use of Python 3.11+ structured concurrency. Individual clip failures are caught inside `_generate_one` before they can propagate to the TaskGroup.

**Progress callback isolated in `_notify` with exception guard** (`video_service.py:295-300`): A broken UI callback does not abort the pipeline. Defensive and correct.

**`TYPE_CHECKING` guard for forward-declared types** (`video_service.py:22-24`): `ClipOptions` and `SubtitleStyle` are imported only during type checking to break the potential circular import chain.

**Sort-by-start-time after concurrent generation** (`video_service.py:257`): Clips returned in chronological order regardless of which ffmpeg subprocess finished first.

**Staged error handling with DB status updates**: Each pipeline stage catches its specific error type (DownloadError, AnalysisError), updates task status to 'failed', then re-raises. The outer `except Exception` at line 443 converts any uncaught error into a `ProcessingResult(error=...)` return, so the orchestrator never throws to the caller.

### ❌ Bad — HIGH (Degraded error UX)

**`error_message` column is never populated, breaking the error banner** (`video_service.py:123-124` vs `models.py:72` vs `task.py:190,251`):

In `_update_task_status`, when the `error` kwarg is provided:
```python
# video_service.py:123-124
if error is not None:
    task.progress_message = error   # BUG: wrong field; should be task.error_message
```

The `Task` model has a dedicated `error_message` column (`models.py:72`) that is never written by any code in `src/`. Two distinct failure modes result:

1. **Live failure during polling** (`task.py:241-253`): The status label (line 242) displays `refreshed.progress_message or refreshed.status`, so the actual error text IS visible there. However, the red error banner (line 251) evaluates `refreshed.error_message or "An unknown error occurred."` — since `error_message` is always `None`, the banner always shows the generic string regardless of the actual failure reason.

2. **Initial load of an already-failed task** (`task.py:157,190`): `initial_error = task.error_message` is always `None`. The banner is hidden entirely via `error_card.set_visibility(initial_status == "failed" and bool(initial_error))`. On task reload, the user sees no error message at all — only the status label's last-written `progress_message`.

Confirmed: `grep -rn "error_message" src/` shows zero writes anywhere in `src/`; only reads in `task.py:157` and `task.py:251`.

Tests pass because `test_video_service.py` only checks `mock_task.progress_message` (line 248), not `mock_task.error_message`, giving 100% line coverage while masking the field mismatch.

### ❌ Bad

**`logging` module instead of `structlog`** (`video_service.py:14,35`):
```python
import logging
logger = logging.getLogger(__name__)
```
CLAUDE.md is explicit: "Do not use the Python `logging` module directly; use structlog." All other modules in the project use structlog: `main.py:6`, `database.py:12`, `pipeline/clip.py:30`, `pipeline/transcribe.py:15`. `video_service.py` is the only exception. Warning messages from the broken callback (`logger.warning("progress_callback_error: %s", cb_exc)`) and clip errors will not benefit from structlog's structured format or key=value context.

**`Config()` bypasses the `get_config()` singleton** (`video_service.py:302`):
```python
cfg = Config()  # BAD
```
The project provides `get_config()` with `@lru_cache(maxsize=1)` in `config.py:98-105` specifically to create a singleton. Using `Config()` directly re-reads all environment variables on every `process_video()` call. In a long-running server process this is wasteful and violates the SPOT principle.

### 🤫 Silent errors / PRD gap

**`progress_callback` is dead in production — UI is DB-poll-driven, not WebSocket-push** (`home.py:91-98` vs `video_service.py:295-300` vs CLAUDE.md):

`ProcessingRequest` has a `progress_callback` field and `_notify()` calls it on every status update. However, `home.py:98` calls `process_video(request)` where the request is built without providing a callback — the field defaults to `None`:

```python
# home.py:91-98 — no progress_callback set
request = ProcessingRequest(
    source=source, task_id=task_id,
    min_clip_length=min_len, max_clip_length=max_len,
    output_resolution=resolution,
)
await process_video(request)
```

The entire `_notify`/callback pathway in `video_service.py:295-300` is therefore dead in production. The task page receives updates exclusively through `ui.timer(1.0, _refresh)` polling the database (`task.py:262`).

CLAUDE.md claims: "Real-time progress feedback is delivered via WebSocket: the backend pushes updates directly to the UI without polling." This is untrue. Progress is delivered by database polling. The WebSocket-push path is implemented but never wired.

**`clip_order` parameter accepted but silently dropped** (`video_service.py:139,415` vs `models.py:GeneratedClip`):

```python
async def _save_generated_clip(
    task_id: str, clip_path: Path, segment: TranscriptSegment, clip_order: int,
) -> None:
    ...
    clip = GeneratedClip(
        task_id=task_id,
        filename=clip_path.name,
        # clip_order is NOT passed — the model has no such field
    )
```

`GeneratedClip` has no `clip_order` column. The parameter is documented, accepted, and never used. No error, no warning. The `created_at` column is used as the implicit ordering on the task page (`task.py:164-167`: `.order_by(GeneratedClip.created_at)`). Since clip generation is concurrent, `created_at` values for clips may arrive out of transcript order if ffmpeg finishes short segments before long ones.

**Double-import pattern for `src.pipeline.clip`** (`video_service.py:201-205,380-382`): The clip module is imported twice: once in `_generate_clips_concurrently` (lazily, with `ImportError` fallback) and once in `process_video` (for `ClipOptions`, with `ImportError` assigning `None`). If the first import succeeds but the second encounters a different error, or vice versa, the code silently diverges. In practice both imports always succeed; the two-import pattern adds complexity with no benefit.

**Outer `except Exception` swallows all errors into `ProcessingResult.error`** (`video_service.py:443-450`): This is intentional defensive design, but the implication is that unexpected exceptions (programming errors, AttributeErrors from mock mismatches, etc.) are converted to user-visible error messages without triggering an alert to a developer. Combined with the `progress_message`/`error_message` field mismatch above, real errors may be invisible in the UI even at the "An unknown error occurred." level.

### ❓ Missing

**User preferences never applied to clip generation**: `ProcessingRequest` has `subtitle_style`, `logo_path`, and `custom_prompt` fields (`video_service.py:71-72`), but `home.py` never reads `UserPreferences` when constructing the request:

```python
# home.py:91-98 — builds ProcessingRequest without subtitle_style/logo_path/custom_prompt
request = ProcessingRequest(
    source=source,
    task_id=task_id,
    min_clip_length=min_len,
    max_clip_length=max_len,
    output_resolution=resolution,
    # subtitle_style = None  (default)
    # logo_path = None        (default)
    # custom_prompt = None    (default)
)
```

The settings page persists font family, color, stroke, shadow, subtitle position, AI prompt, and logo path to `UserPreferences`. None of these are ever retrieved and forwarded to `process_video`. All generated clips use default (blank) subtitle styling. This renders the settings page largely non-functional for its primary purpose.

**No timeout on transcription** (`video_service.py:343`): `transcribe_video` runs synchronously in a thread pool via `asyncio.to_thread`. For very long videos (multi-hour podcasts), this could block a thread indefinitely. No timeout or cancellation mechanism exists.

**No validation that `max_clip_length > min_clip_length` at the service layer**: `home.py` validates this in the UI (`home.py:233`), but `ProcessingRequest` accepts any values. If called programmatically, an invalid range is forwarded to `analyze_transcript` where the LLM will likely reject all segments (since no segment can satisfy an impossible duration range) and raise `AnalysisError`. The service layer should guard this.

### 🗑️ Stale code / tech debt

**Stale "not yet written" comment** (`video_service.py:347`):
```python
# pipeline/transcribe not yet written — surface a clear error.
```
This comment is from initial scaffolding. `src/pipeline/transcribe.py` is fully implemented (332 lines, 100% test coverage). The `ImportError` branch it guards can still occur (e.g., dependency conflict), but the comment is misleading.

**`logging` module as tech debt**: The inconsistency between `video_service.py` (stdlib logging) and all other modules (structlog) should be resolved in a single VUW.

**`clip_order` parameter**: Either the `GeneratedClip` model needs a `clip_order` column and migration, or the parameter should be removed from `_save_generated_clip`.

### 🐷 Overengineered / complexity

**Radon grade C on `process_video`** (`video_service.py:266`): Reported in ground truth data. The function handles 5 pipeline stages (download, transcribe, analyze, generate, persist) plus error handling, status updates, and progress reporting in one body. Each stage could be extracted into a `_run_<stage>` function, reducing complexity and improving testability.

---

## Cross-cutting: Test coverage gap

All tests for `video_service.py` mock `get_session`. None exercise the `error_message` field on a real `Task` object. The `test_error_stored_in_progress_message` test (test_video_service.py:235-248) asserts `mock_task.progress_message == "Download failed badly"` — which passes because the code writes to `progress_message`. No test asserts that `error_message` is set, so the UI bug is invisible to the test suite despite 100% line coverage.

---

## Prioritized Remediation

| Priority | File | Issue |
|----------|------|-------|
| P0 | `src/main.py` | Add `app.add_media_files('/clips/', ...)` in `_startup()` — clips 404 without this |
| P1 | `src/services/video_service.py` | Write errors to `task.error_message` (not just `progress_message`) to populate error banner |
| P1 | `src/pages/home.py` | Load `UserPreferences` and forward to `ProcessingRequest` fields (subtitle_style, logo_path, custom_prompt) |
| P1 | `src/pages/home.py` | Wire `progress_callback` in `ProcessingRequest` so WebSocket push actually fires (or document that DB-poll is intentional) |
| P1 | `src/services/video_service.py` | Replace `logging` with `structlog` |
| P1 | `src/services/video_service.py` | Replace `Config()` with `get_config()` |
| P2 | `src/services/video_service.py` | Remove dead `clip_order` param or add model column |
| P2 | `src/pages/home.py` | Move uploaded file storage from `/tmp/` to `temp/uploads/` per CLAUDE.md rule |
| P3 | `src/main.py` | Call `cfg.ensure_temp_dirs()` in `_startup()` for consistency (near-zero real impact) |
| P3 | `src/services/video_service.py` | Refactor `process_video` to reduce radon C complexity |
| P3 | `src/services/video_service.py` | Remove stale "not yet written" comment on transcribe ImportError branch |
| P3 | `src/main.py` | Remove unnecessary `# noqa: F401` |
