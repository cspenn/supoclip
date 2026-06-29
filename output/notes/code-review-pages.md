# Code Review: src/pages/ — Audit Notes

**Files audited:** `src/pages/home.py`, `src/pages/task.py`, `src/pages/history.py`, `src/pages/settings.py`
**Date:** 2026-06-29
**Reviewer:** Automated audit agent

---

## Ground Truth Used

- pytest: 466 passed, 0 failed
- Coverage: 100% on src/
- ruff: clean (all checks passed)
- mypy: success (19 files, no issues)
- radon cc Grade C violations: `settings.py:46 _discover_fonts`, `task.py` and `settings.py` tasks noted
- `checkpython.sh` does not exist (phantom gate)

---

## ✅ Good — Well-implemented Features and Clean Patterns

### home.py

- **home.py:20** — Uses `structlog.get_logger()` throughout. No bare `logging` or emoji patterns.
- **home.py:39-49** — `_is_youtube_url()` is a clean, well-tested helper with proper docstring.
- **home.py:52-69** — `_create_task()` uses the `get_session()` context manager correctly (auto-commit). Calls `flush()` then `refresh()` to obtain the UUID before the session closes — correct SQLAlchemy async pattern.
- **home.py:115** — Mutable-cell pattern `uploaded_path: list[str] = []` correctly sidesteps Python's closure/nonlocal complexity. Unusual but intentional and correct.
- **home.py:206-256** — `on_start()` validates inputs before touching the database: URL-or-file mutual exclusion, min/max ordering. Error paths all surface via `ui.notify()`.
- **home.py:26-32** — All magic numbers (slider bounds, defaults) extracted to module-level constants. Good SPOT adherence.

### task.py

- **task.py:20-47** — `_truncate()` and `_format_seconds()` are clean, well-typed utilities.
- **task.py:50-65** — `_score_color()` properly handles `None` score, avoids `.value` attribute access on `None`.
- **task.py:117-266** — The overall DB-prefetch on page load + conditional timer pattern is well-structured. Completed tasks render immediately; active tasks poll.
- **task.py:244-260** — Structural `match-case` over task status is idiomatic Python 3.11+ and clearly readable.
- **task.py:262** — `poll_timer = ui.timer(1.0, _refresh)` is assigned AFTER `_refresh` is defined, so the `poll_timer.active = False` closure reference is correctly resolvable.

### history.py

- **history.py:19-24** — `_STATUS_COLORS` dict is clean config that avoids scattered string checks.
- **history.py:54-75** — `_load_tasks()` performs both DB queries in one session context and uses a `GROUP BY` count query instead of per-row N+1 queries. Efficient.
- **history.py:97-103** — `_render_navigation()`, `_render_task_row()`, `_render_empty_state()` factored out of `render()` — good decomposition.
- **history.py:161-165** — Exception on DB load is caught and surfaced via `ui.notify()` rather than crashing the page.

### settings.py

- **settings.py:26-38** — `is_valid_hex_color()` with a compiled regex constant is correct and tested.
- **settings.py:103-131** — `_build_subtitle_style()` and `_build_typo_html()`/`_build_phone_html()` are well-factored HTML builders; reuse the style helper.
- **settings.py:339-340** — `ui.html("", sanitize=False)` with `sanitize=False` correctly prevents NiceGUI from stripping inline styles. This was recently fixed (commit 529be05).
- **settings.py:512-546** — All reactive wiring is deferred to after all widget references exist, then `_update_preview()` is called once on page load. Clean initialization pattern.
- **settings.py:211-236** — `load_prefs()` returns a fully-populated in-memory default `UserPreferences` when no DB row exists, avoiding `None` checks on every field. Correct.
- **settings.py:477-499** — `reset()` correctly notes the forward reference to `_update_preview` with an explanatory comment, rather than leaving it as a mystery.

---

## ❌ Bad — Bugs, Errors, Anti-Patterns

### home.py:150 — CRITICAL: `/tmp` hardcoded for uploaded files

```python
save_path = Path("/tmp") / name
```

This violates CLAUDE.md ("you are expressly forbidden from working in the temp directory /tmp") and the project config which provides `config.temp_dir` (defaulting to `./temp/uploads/`). Per spec section 5.2, "The uploaded file is saved to `temp/{task_id}/source.mp4` by the NiceGUI upload handler." Files written to `/tmp` will not be cleaned up by `config.ensure_temp_dirs()` and may not survive across OS reboots on some systems. On macOS, `/tmp` is a symlink to `/private/tmp` which is session-temporary. The pipeline receives this path and attempts to transcribe it — if the OS clears `/tmp`, the pipeline fails with a confusing FileNotFoundError.

**Remediation:** Replace with `get_config().temp_dir / "uploads" / name` and call `get_config().ensure_temp_dirs()` or ensure `uploads/` exists before writing.

### home.py:219 — Logic bug: non-YouTube URLs stored as `source_type="upload"`

```python
source_type = "youtube" if _is_youtube_url(url_text) else "upload"
```

A Vimeo URL, a direct `.mp4` URL, or any other yt-dlp-supported URL entered in the URL field gets stored as `source_type="upload"` in the Task row. The pipeline itself routes correctly (via `validate_youtube_url` in `video_service.py`), but the database metadata is wrong. The history page displays and links these tasks, and any downstream code that reads `task.source_type` to determine behavior will be misled.

**Remediation:** Use a third source type (e.g. `"url"`) for non-YouTube URL inputs, or keep as `"youtube"` for all yt-dlp-handled URLs.

### home.py:27 — Default resolution contradicts spec

```python
_DEFAULT_RESOLUTION = "1080p"
```

Spec section 6.1 states: "Output resolution | `ui.select` | Options: `720p`, `1080p`; **default `720p`**". The implementation defaults to `1080p`. Higher resolution means larger output files and longer encoding times for the default path.

### settings.py:83 — Bare `except Exception` swallows all font parse errors silently

```python
except Exception:
    log.warning("settings.discover_fonts.parse_error", path=str(ttf_path))
```

The only context logged is the file path. The exception type, message, and traceback are lost. A corrupt TTF causing a memory error or OS-level IOError will look identical to a fontTools parse error. The inner bare exception at line 77 is even worse — it silently skips individual name records without any logging.

---

## ❓ Missing — Incomplete Features, Gaps vs. Spec/PRD

### home.py — No `accept` filter on `ui.upload`

**home.py:157:**
```python
ui.upload(on_upload=handle_upload, label="Drop or click to upload a video file")
```

Spec section 6.1: "Upload zone | `ui.upload` | Accepts `.mp4`, `.mov`, `.avi`, `.mkv`; max size from config". There is no `.props('accept=".mp4,.mov,.avi,.mkv"')` and no `max_file_size` prop. Any file (including images, documents, executables) can be uploaded. The pipeline will fail silently during ffmpeg processing, leaving the task in a "failed" state with a cryptic error.

### home.py — User preferences not loaded as defaults

The home page has hardcoded defaults for min clip length (15s), max clip length (45s), and resolution (1080p). The settings page exists precisely to let users configure these defaults. But `home.py` never loads `UserPreferences` from the DB to pre-populate the sliders. The settings page is effectively a no-op for these values because the home page ignores them.

**Remediation:** Call `load_prefs()` (imported from `settings.py`) in `render()` and use those values as slider defaults.

### home.py — No file-type validation in `handle_upload`

The upload handler at lines 137-155 accepts any file content and writes it to disk without checking extension or MIME type. Combined with the missing `accept` filter above, this means non-video files proceed into the pipeline.

### task.py — DB polling instead of WebSocket push (spec deviation)

Spec section 6.2: "The `progress_callback` passed to `video_service.process_video` calls `ui.update()` on the progress bar and message label. NiceGUI pushes the DOM mutation to the browser via WebSocket. **No polling.**"

The actual implementation uses `ui.timer(1.0, _refresh)` — 1-second DB polling. This adds ~1 second latency to all progress updates, hits the DB every second, and contradicts the spec's architectural intent. The spec envisions the pipeline directly mutating NiceGUI UI elements via `ui.update()`. The polling approach works but creates unnecessary DB load and is architecturally misaligned.

### task.py — No status badge on the task page

Spec section 6.2: "Status badge | `ui.badge` | Colour-coded: grey (pending), blue (processing), green (done), red (failed)". The task page has no `ui.badge` showing the current status — only a text label and a progress bar.

### history.py — No pagination

Spec section 4.7: "Paginated list of all past tasks". The implementation loads all tasks unconditionally with `select(Task).order_by(Task.created_at.desc())`. No LIMIT/OFFSET, no `ui.pagination`. A user with 1000 tasks will load them all into memory and DOM on every page visit.

### history.py — Uses `ui.card` list instead of `ui.table`

Spec section 6.3: "Task table | `ui.table`". The history page uses a list of `ui.card` elements. While the end result is similar, `ui.table` provides built-in sorting, filtering, and pagination hooks. Using a custom card list requires reimplementing all of that.

### settings.py — Missing font stroke/shadow fields in spec

Spec section 6.4 lists `font_color`, `font_family`, `font_size`, `clip_min_s`, `clip_target_s`, `clip_max_s`, `output_resolution`, `custom_ai_prompt`, `logo` as settings fields. The implementation additionally has `font_stroke_color`, `font_stroke_width`, `font_shadow_offset`, `subtitle_position_y` — these extra fields are present in the `UserPreferences` model and are good additions, but the spec doesn't list them. This is a spec-to-code drift where the implementation exceeds the spec (acceptable, but worth noting for spec update).

---

## 🗑️ Unnecessary — Redundant or Unused Code

### `_truncate()` duplicated across task.py and history.py

- `task.py:20-33` — `_truncate(text, max_len=60)`
- `history.py:39-51` — `_truncate(text, max_len=50)`

Identical logic with different default values. Should be extracted to a shared utility module (e.g., `src/utils.py`). DRY violation. If the truncation behavior needs to change, it must be changed in two places.

### history.py:89 — Double commit

```python
async with get_session() as session:
    task = await session.get(Task, task_id)
    if task:
        await session.delete(task)
        await session.commit()      # explicit commit
        ...
# get_session() auto-commits on exit — second commit is a no-op
```

`get_session()` (database.py:62) calls `await session.commit()` on exit. The explicit `session.commit()` inside `delete_task()` is redundant. It is not harmful (SQLAlchemy treats post-commit commits as no-ops), but it creates a false impression that the context manager does not commit, which could mislead future maintainers.

---

## 🤫 Silent Errors — Swallowed Exceptions, Unhandled Edge Cases

### home.py:250 — Fire-and-forget asyncio.create_task with no error callback

```python
asyncio.create_task(
    _start_processing(task_id, source, min_len, max_len, resolution)
)
```

If `_start_processing` raises an unhandled exception before `video_service.py` can set `task.status = "failed"`, the Task row stays in `"pending"` state forever. The polling timer in `task.py` will keep querying the DB every second indefinitely. `asyncio.create_task` does log unhandled exceptions to the event loop's exception handler, but the UI shows no feedback.

**Remediation:** Add `task.add_done_callback(lambda t: t.exception())` or wrap with a top-level error handler that sets the task status to "failed" if the coroutine raises.

### task.py — No poll timeout guard for stuck tasks

The `poll_timer` at task.py:262 only stops on `"completed"` or `"failed"` status. A pipeline that hangs mid-execution (e.g., ffmpeg blocked, parakeet-mlx stalled) will leave the task in `"processing"` state forever, and the UI timer will poll the DB indefinitely. There is no maximum elapsed time after which the UI gives up and shows a "timed out" error.

### task.py:106 — `ui.download()` with type: ignore — uncertain API usage

```python
on_click=lambda c=clip: ui.download(f"/clips/{c.filename}"),  # type: ignore[reportAttributeAccessIssue]
```

The `type: ignore` comment acknowledges that `ui.download()` may not accept a URL string. In NiceGUI, `ui.download()` is typically used for bytes or `Path` objects, not URL strings. If the actual NiceGUI API doesn't handle URL strings, the download button will silently fail or throw a runtime error (which NiceGUI may suppress). The spec says the download button "Links to `/clips/{filename}` with `Content-Disposition: attachment`" — this should probably be a `ui.link` with a download attribute or a server-side response header.

### settings.py:77 — Inner bare `except Exception` loses all error context

```python
try:
    family = record.toUnicode()
    break
except Exception:
    continue
```

Any error during `record.toUnicode()` is silently swallowed. No logging, no exception info. A UnicodeDecodeError, MemoryError, or any other failure causes the loop to silently try the next record. At minimum this should `log.debug()` the exception.

### settings.py:406 — `handle_logo_upload` calls `content.read()` without `hasattr` check

```python
dest.write_bytes(content.read())
```

Unlike `home.py:151` which checks `content.read() if hasattr(content, "read") else content`, the logo upload handler assumes `content` always has a `read()` method. If NiceGUI passes raw bytes instead of a file-like object (which varies by NiceGUI version), this will throw `AttributeError` — silently, because NiceGUI event handlers catch exceptions.

### history.py:127 — Async function wrapped in sync lambda for `on_click`

```python
on_click=lambda t_id=task.id: delete_task(t_id),  # type: ignore[reportArgumentType]
```

`delete_task` is `async def`. The lambda is synchronous and returns a coroutine object. Whether NiceGUI awaits coroutines returned by sync `on_click` callbacks is implementation-dependent. If NiceGUI does not detect and schedule the returned coroutine, the delete operation silently does nothing — the user clicks Delete, the button appears to work (no error), but the task remains in the list until the next page refresh, at which point it still exists in the DB.

**Remediation:** Define an `async def` wrapper and pass it directly: `on_click=lambda t_id=task.id: asyncio.ensure_future(delete_task(t_id))` or use `async def` closure.

---

## 🐷 Overengineered — Unnecessary Complexity

### settings.py:46-91 — `_discover_fonts()` — Grade C complexity (confirmed radon)

The function has a triple-nested control flow: outer `for` (TTF files) → `try/except` block → inner `for` (name IDs 1 and 4) → inner `for` (name records) → inner `try/except`. Radon grades this C; the project standard is A or B. The function can be decomposed into:
- `_extract_family_name(ttf_path: Path) -> str | None` — handles one file
- `_discover_fonts(...)` — calls the helper, handles errors at file level

This also separates the testable logic (name extraction) from the directory scan.

---

## 🚮 Tech Debt / Dead Code

### settings.py:47 — `Config.FONTS_DIR` class attribute access in default argument

```python
def _discover_fonts(
    fonts_dir: Path = Config.FONTS_DIR,
    ...
```

This evaluates `Config.FONTS_DIR` at **module load time** (function definition), not at call time. While `Config.FONTS_DIR: ClassVar[Path] = Path("fonts")` is a constant, this pattern bypasses `get_config()` singleton used everywhere else in the codebase. If the project ever wants to configure `FONTS_DIR` differently between environments, this default argument won't respect the change. The call site in `render()` could pass `get_config().fonts_dir` explicitly, or the function should use `get_config()` internally.

### settings.py:239 — `dict` type hint without type parameters

```python
async def save_prefs(data: dict) -> None:  # type: ignore[type-arg]
```

The `# type: ignore[type-arg]` comment acknowledges the incomplete type. Should be `dict[str, Any]` or a typed `TypedDict`. The type: ignore is tech debt.

### home.py — No loading indicator while processing starts

After the Start button is clicked and the pipeline fires off, the page navigates immediately to `/task/{task_id}`. There is no disabled state on the Start button and no spinner while the DB task is created (which takes an async DB round-trip). A user who double-clicks could submit the same URL twice.

---

## Runtime / Output Correctness Risks

These issues are not flagged by static analysis but could cause incorrect runtime output — the class of bugs that unit tests miss.

### home.py:150 — `/tmp` path for uploads causes pipeline FileNotFoundError at runtime

See "Bad" section above. The pipeline is handed a path in `/tmp` for uploaded files. This path may not exist on subsequent pipeline stages if `/tmp` is cleared between steps, or if the `_start_processing` runs on a different asyncio task after a delay. The pipeline's `transcribe.py` will get a `FileNotFoundError` for the uploaded video, surfacing as a confusing "failed" task state.

### task.py:106 — Download button runtime behavior uncertain

The `ui.download()` call with a URL string may work in some NiceGUI versions and fail silently in others. This is a runtime-only failure not caught by unit tests.

### settings.py:125-131 — CSS injection from font family name

```python
f"font-family: {font_family}, sans-serif;"
```

The font family name is injected directly into an inline CSS string without escaping. A TTF file whose internal family name contains `; malicious: css` or `</style><script>` could break the CSS in the preview, or on browsers that handle `sanitize=False` HTML unsafely. While the font files are local (controlled by the user), this is still an output-correctness risk if custom fonts are shared.

### history.py:78-94 — `delete_task` leaves MP4 files on disk

```python
async with get_session() as session:
    task = await session.get(Task, task_id)
    if task:
        await session.delete(task)
```

The ORM cascade deletes `GeneratedClip` rows from the DB, but the actual `.mp4` files in `temp/clips/` are never removed. Over time, deleting tasks will leave orphaned video files consuming disk space. The spec says "Soft-deletes task and associated clips from DB" but does not mention file cleanup — however, as an AI video clipping tool, clip files can be very large (100s MB each), making this a practical resource leak.

---

## Summary Table

| Severity | File:Line | Issue |
|---|---|---|
| Critical | home.py:150 | Uploads written to `/tmp` instead of `config.temp_dir/uploads/` |
| High | home.py:219 | Non-YouTube URLs stored as `source_type="upload"` (DB metadata wrong) |
| High | history.py:127 | Sync lambda wraps async `delete_task`; NiceGUI may not await it → silent no-op delete |
| High | history.py:78-94 | Delete task leaves MP4 files on disk (storage leak) |
| High | settings.py:46 | `_discover_fonts` is radon grade C — must be refactored per project rules |
| Medium | home.py:250 | Fire-and-forget `asyncio.create_task` — exceptions before DB update leave tasks stuck in "pending" |
| Medium | home.py:157 | `ui.upload` has no `accept` filter; spec requires `.mp4,.mov,.avi,.mkv` |
| Medium | home.py | No UserPreferences load for default slider values — settings page is ignored by home page |
| Medium | home.py:27 | Default resolution `1080p` contradicts spec which says `720p` |
| Medium | task.py:106 | `ui.download(url_string)` with `type: ignore` — download behavior uncertain at runtime |
| Medium | task.py | No polling timeout guard — stuck tasks cause infinite DB polling |
| Medium | task.py | DB polling model contradicts spec (spec says WebSocket push, no polling) |
| Medium | history.py | No pagination — all tasks loaded unconditionally |
| Medium | settings.py:83 | Bare `except Exception` swallows font parse errors with no stack trace |
| Low | history.py | Uses `ui.card` list instead of `ui.table` as spec requires |
| Low | settings.py:406 | `content.read()` without `hasattr` check (unlike home.py:151) |
| Low | settings.py:125 | Font family name injected unescaped into CSS (CSS injection risk) |
| Low | task.py:20 / history.py:39 | `_truncate` duplicated (DRY violation) |
| Low | history.py:89 | Double-commit: explicit commit inside auto-committing session context |
| Low | settings.py:47 | `Config.FONTS_DIR` class attr used as default arg (evaluated at module load) |
| Low | settings.py:239 | `dict` without type params (`# type: ignore[type-arg]` tech debt) |
| Info | task.py | No status badge on task page (spec requires colour-coded `ui.badge`) |
| Info | home.py | Start button not disabled during DB task creation; double-click could duplicate tasks |
