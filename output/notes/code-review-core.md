# Code Review: Core Layer — src/config.py, src/database.py, src/models.py

Auditor: automated review subagent  
Scope: config.py, database.py, models.py  
Ground-truth: pytest 466/0, 100% coverage, ruff clean, mypy clean

---

## ✅ Good — Well-Implemented Patterns

### src/config.py

- `pydantic_settings.BaseSettings` with `SettingsConfigDict(extra="ignore")` correctly absorbs stray env vars without crashing startup. (config.py:22-27)
- `lru_cache(maxsize=1)` on `get_config()` provides a cheap singleton without importing any framework machinery. (config.py:98)
- `ClassVar` fields for `FONTS_DIR`, `TRANSITIONS_DIR`, `DEFAULT_BACKEND_PORT` correctly keep them out of env-var resolution. (config.py:72-74)
- `ensure_temp_dirs()` uses `exist_ok=True` making it idempotent, and it covers uploads/, clips/, and root in one call. (config.py:89-95)
- `case_sensitive=False` on SettingsConfigDict prevents user frustration from capitalization mismatch in `.env`. (config.py:27)

### src/database.py

- Lazy initialization (`_engine = None`) avoids module-level side effects that break test isolation. (database.py:23-24)
- `asynccontextmanager get_session()` with try/except commit/rollback is the correct pattern for async SQLAlchemy sessions. (database.py:59-65)
- `expire_on_commit=False` on the session factory prevents the common async SQLAlchemy pitfall of expired objects after commit. (database.py:90-94)
- `check_same_thread=False` is correctly included for SQLite async use (aiosqlite uses threads internally). (database.py:88)
- `init_db()` is idempotent — second call returns immediately if engine already set. (database.py:80-82)

### src/models.py

- SQLAlchemy 2.0 `Mapped[T]` + `mapped_column()` style throughout — type-safe and mypy-friendly. (models.py:56-188)
- `_new_uuid()` and `_utcnow()` as named functions instead of lambdas — compatible with mypy and pickle, introspectable. (models.py:15-30)
- Cascade `"all, delete-orphan"` on the Task→GeneratedClip relationship is correct — deleting a Task cleans up all its clips. (models.py:81-83)
- `_utcnow()` correctly returns `datetime.now(UTC)` (timezone-aware) rather than `datetime.utcnow()` (deprecated naive). (models.py:30)
- Three-table schema is lean (no auth, no source/systemfont tables). (models.py:33-189)

---

## ❌ Bad — Bugs, Errors, Anti-Patterns

### config.py: `app_port` env var alias mismatch with spec (medium)

`app_port` uses `validation_alias="BACKEND_PORT"` (config.py:30) but the spec (docs/spec.md §8.4) specifies `PORT` as the env var name. The `.env` file loaded via `pydantic-settings` would need `BACKEND_PORT=...` to override this, but users following the spec would set `PORT=...` and be confused when it has no effect. Additionally, `main.py:60` hardcodes `port=8008` unconditionally — `cfg.app_port` is never read at runtime.

### config.py: `get_llm_model()` silent fallback instead of ValueError (medium)

When `local_llm_enabled=False` and `llm_model=""`, `get_llm_model()` falls back to `"openai:gpt-4o"` silently (config.py:87). The spec (§8.1) states: "LLM selection priority: local → cloud → **raise ValueError**". A user who sets `LOCAL_LLM_ENABLED=false` but forgets `LLM_MODEL` will get silent GPT-4o requests, possibly with no API key set, causing opaque runtime failures deep in the pipeline rather than a clear startup error.

### database.py: `connect_args` is SQLite-specific but applied unconditionally (low)

`connect_args={"check_same_thread": False}` at database.py:88 is silently accepted by `aiosqlite` but would raise `TypeError: 'check_same_thread' is an invalid keyword argument` if `DATABASE_URL` were changed to PostgreSQL. The guard should check the URL scheme before passing this argument.

### models.py: `Task.source_url` is nullable=False but spec says nullable (low)

`source_url: Mapped[str]` with `nullable=False` (models.py:59) means a non-null string is always required. The spec §7.1 marks `source_url` as nullable (`YES | NULL`) with description "YouTube URL or uploaded filename". In the upload case, the filename is passed as source_url (home.py:63), so this is not currently a runtime crash — but it diverges from the spec and would fail on future attempts to create a Task without a URL.

---

## 🤫 Silent Errors — Swallowed Exceptions, Runtime Ambiguity

### models.py: DateTime without timezone=True causes TZ-aware/naive mismatch (high)

All `DateTime` columns use SQLAlchemy's plain `DateTime` type (models.py:9, 74, 77, 122, 188). SQLAlchemy's `DateTime` without `timezone=True` strips tzinfo when persisting to SQLite and returns naive datetimes on read. `_utcnow()` produces timezone-aware datetimes (`datetime.now(UTC)`). Result: every timestamp written is TZ-aware, every timestamp read back is naive. Any code comparing a DB timestamp to `datetime.now(UTC)` — e.g., for expiry logic or sorting — will raise `TypeError: can't compare offset-naive and offset-aware datetimes` at runtime. Tests pass because they do not compare timestamps against `datetime.now(UTC)`. Fix: use `DateTime(timezone=True)` on all columns.

### database.py: ModuleNotFoundError swallowed silently creates a zero-table database (medium)

Lines 98-101:
```python
try:
    import src.models  # noqa: F401
except ModuleNotFoundError:
    log.debug("database.models_not_found", note="Skipping model registration")
```
If `src.models` fails to import for any reason caught by `ModuleNotFoundError`, `Base.metadata.create_all` (line 104) runs immediately afterward with zero registered models and creates an empty database file. Every subsequent query will fail with `OperationalError: no such table`. The log entry is a DEBUG message — invisible at INFO level. This is a silent failure mode that produces a completely broken application state with no visible error at startup. Currently `src.models` imports successfully, so this path is dormant but dangerous.

### config.py: ensure_temp_dirs() is defined but never called at startup (high)

`ensure_temp_dirs()` (config.py:89-95) creates `temp/`, `temp/uploads/`, and `temp/clips/`. It is never called in `main.py:_startup()` (main.py:43-46). The `video_service.py:303-304` inlines `clips_dir.mkdir(parents=True, exist_ok=True)` for the clips directory only. The `uploads/` directory is **never created** unless a user calls it manually. When a file is uploaded via the home page, `src/pages/home.py` likely writes to `{TEMP_DIR}/uploads/` — if that directory does not exist, the upload will fail with `FileNotFoundError` at runtime, producing no user-visible error message (NiceGUI will show a generic error). Tests pass because they mock file system calls or use tmp_path.

### models.py: UserPreferences singleton not enforced at DB level (low)

`id: Mapped[int]` with `default=1` (models.py:154) documents a singleton pattern, but no `CheckConstraint(id == 1)` exists in the schema. A code bug that creates `UserPreferences(id=2)` inserts silently. Callers use `session.get(UserPreferences, 1)` — a second row at id=2 is silently ignored, but the data is lost.

### config.py / clip.py: FFMPEG_PRESET and FFMPEG_CRF are hardcoded instead of configurable (medium)

`clip.py:227-228` hardcodes `"-preset", "fast"` and `"-crf", "23"` in the ffmpeg subprocess call. The spec (§8.3) defines `FFMPEG_PRESET` and `FFMPEG_CRF` as configurable env vars. Since they are not in `config.py`, operators cannot tune encoding quality or speed without modifying source code. This is a silent "it works, but you can't change it" failure for a tunable parameter.

---

## ❓ Missing — Gaps vs Spec/PRD

### config.py: 9 of 14 spec-defined configuration variables are absent

Spec §8.1–8.4 defines the following env vars that have no corresponding field in `config.py`:

| Spec Env Var | Spec Section | Status in code |
|---|---|---|
| `PARAKEET_MODEL` | §8.2 | Hardcoded in transcribe.py |
| `RECONSTRUCT_WORDS_WITH_LLM` | §8.2 | Not implemented |
| `MAX_VIDEO_DURATION` | §8.3 | Not enforced anywhere |
| `MAX_CLIPS` | §8.3 | Not enforced anywhere |
| `FFMPEG_PRESET` | §8.3 | Hardcoded `"fast"` in clip.py:227 |
| `FFMPEG_CRF` | §8.3 | Hardcoded `"23"` in clip.py:228 |
| `HOST` | §8.4 | main.py has no host config |
| `MAX_WORKERS` | §8.4 | TaskGroup has no concurrency limit |
| `LOG_DIR` | §8.4 | Not used |

Most critically: `MAX_VIDEO_DURATION` means arbitrarily long downloads are accepted; `MAX_CLIPS` means runaway clip generation is uncapped; `MAX_WORKERS` means all clips are generated simultaneously with no backpressure.

### models.py: Missing columns from spec

**GeneratedClip (spec §7.2):**
- `reasoning: TEXT | NULL` — AI explanation of segment selection (not present)
- `clip_order: INTEGER | NOT NULL` — display sort order (not present; code sorts by start_time instead)
- `updated_at: DATETIME | NOT NULL` — auto-updated timestamp (not present; only has `created_at`)

**UserPreferences (spec §7.3):**
- `logo_position: VARCHAR(20)` — `'top-left'/'top-right'/'bottom-left'/'bottom-right'` (not present; model has `logo_path` but not `logo_position`). Settings page UI shows no logo position control.
- `clip_target_s / target_clip_count` — spec defines a target clip count; model has only min/max clip length with no target count.
- `custom_ai_prompt` — spec column name; model uses `ai_prompt` (minor naming drift)

### models.py: font_family default 'Arial' vs spec 'TikTokSans-Regular'

`server_default=text("'Arial'")` (models.py:157) diverges from spec §7.3 which says default is `'TikTokSans-Regular'`. If the font file `fonts/TikTokSans-Regular.ttf` exists, the spec-correct default would allow out-of-box usage. With `'Arial'`, subtitle rendering may use a system font not present in the `fonts/` directory.

---

## 🗑️ Unnecessary — Redundant / Unused / Over-Engineered

### config.py: DEFAULT_BACKEND_PORT ClassVar is unreferenced dead code

`DEFAULT_BACKEND_PORT: ClassVar[int] = 8008` (config.py:72) is tested in `test_config.py:37` but never used in any application code. `main.py` hardcodes `port=8008` directly. This ClassVar has no purpose and should be removed.

### config.py: app_port field is dead config

`app_port: int = Field(default=8008, validation_alias="BACKEND_PORT")` (config.py:30) is loaded from the environment but never consumed — `main.py:60` uses `port=8008` literally. The field parses and validates a setting that has no effect on runtime behavior.

### models.py: Task.title is a dead column

`title: Mapped[str | None] = mapped_column(Text, nullable=True)` (models.py:70) is never written by any pipeline code. `home.py` creates Tasks without setting `title`. `video_service.py` never sets it. The field exists in the database and docstring but carries no data.

### models.py: Task.settings_json is a dead column

`settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)` (models.py:71) is declared with the intent (from docstring) to store "JSON blob of processing settings". It is never written by `video_service.py`, `home.py`, or any other module. The spec §7.1 describes it as storing the error key on failure, but the code uses `task.progress_message` for errors and `Task.error_message` for error detail instead.

### models.py: GeneratedClip.duration is a stored computed value

`duration: Mapped[float] = mapped_column(Float, nullable=False)` (models.py:117) is always computed as `segment.end_time - segment.start_time` (video_service.py:149) before insert. The spec §7.2 does not define a `duration` column — it can always be derived. Storing it risks inconsistency if start/end times are ever updated.

### database.py: get_engine() is only called in tests

`get_engine()` (database.py:31-43) is not used by any application code path — only by `test_database.py`. The engine is accessed indirectly through `_session_factory`. It adds an API surface with a misleading `raise RuntimeError` that implies callers might call it, but none do.

### database.py: "models haven't been written yet" boilerplate is development-era debt

The comment "This is optional: if models haven't been written yet, skip gracefully" (database.py:97) with the `try/except ModuleNotFoundError` guard is a development-phase safety net. The project is past that phase. This guard now solely acts as a silent failure trap (see Silent Errors section).

---

## 🐷 Overengineered

### config.py / analyze.py / video_service.py: singleton broken by direct Config() instantiation

`get_config()` is the lru-cached singleton function, but `Config()` is called directly in:
- `src/pipeline/analyze.py:364` — creates a new Config on every call to the Groq analysis path
- `src/pipeline/analyze.py:427` — creates a new Config on every call to the pydantic-ai path
- `src/pipeline/analyze.py:538` — creates a new Config on every call to the analyze wrapper
- `src/services/video_service.py:302` — creates a new Config on each `process_video()` call

Each direct `Config()` call re-parses the `.env` file and all environment variables from scratch. The four Config() calls in the hot pipeline path execute on every video processing job, adding unnecessary overhead and inconsistency. Any test that patches `get_config()` will not affect these direct instantiations.

---

## 🚮 Tech Debt / Dead Code

1. **`database.py:97-101`** — ModuleNotFoundError guard + "haven't been written yet" comment. Remove the try/except; `import src.models` should run unconditionally and fail loudly if broken.

2. **`config.py:72`** — `DEFAULT_BACKEND_PORT: ClassVar[int] = 8008` — unreferenced dead constant.

3. **`config.py:30`** — `app_port` field — defined but never used by `main.py`; port is hardcoded.

4. **`models.py:70-71`** — `Task.title` and `Task.settings_json` — columns in schema that are never written. Represent divergence from initial design intent that was never implemented.

5. **`models.py:117`** — `GeneratedClip.duration` — stored computed value; redundant with `end_time - start_time`.

---

## Status: 'completed' vs spec 'done'

The spec §7.1 defines `status IN ('pending', 'processing', 'done', 'failed')` but all code — `video_service.py:432`, `task.py:161,196,199,245,264`, `history.py:20` — consistently uses `'completed'`. This is a spec divergence, not a code bug (the code is internally consistent). The spec should be updated to say `'completed'`.

---

## Runtime Correctness Risk Summary (subtitle/video/LLM output)

The DateTime TZ-naive/aware mismatch (models.py) is the highest runtime correctness risk for the core layer. It does not affect clip generation today (no timestamp comparisons against `now()` in the hot path), but would silently break any future feature that compares stored timestamps to live time.

The `ensure_temp_dirs()` never being called is a practical runtime risk: fresh installations will fail on the first file upload with an opaque `FileNotFoundError` since `temp/uploads/` is never created.

The `FFMPEG_PRESET` / `FFMPEG_CRF` hardcoding is a correctness constraint on output quality — operators cannot tune it without source edits.
