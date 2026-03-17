# start docs/spec.md

# SupoClip Technical Specification — "Clean Consolidation" Redesign

**Version:** 1.0
**Date:** 2026-03-17
**Status:** Approved for Implementation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Module Specifications](#4-module-specifications)
5. [Pipeline Flow](#5-pipeline-flow)
6. [UI Specification](#6-ui-specification)
7. [Data Model](#7-data-model)
8. [Configuration](#8-configuration)
9. [Subtitle System](#9-subtitle-system)
10. [Video Processing](#10-video-processing)
11. [AI Integration](#11-ai-integration)
12. [Development Standards](#12-development-standards)
13. [Testing Strategy](#13-testing-strategy)

---

## 1. Overview

### What This Spec Covers

This document specifies the target architecture for SupoClip after the "Clean Consolidation" redesign. It covers every module, table, configuration variable, ffmpeg filter chain, and UI page in the new system. It is the authoritative reference for developers implementing the redesign.

### Why the Redesign Was Done

The original architecture split the application across two processes: a Python/FastAPI backend and a React/Next.js frontend. This created unnecessary complexity:

- **Two runtimes to install and run:** Node.js plus Python, coordinated by a `start.sh` orchestrator script
- **Playwright/Chromium for subtitles:** A headless browser launched per-clip solely to render styled text onto a canvas, then screenshot it. This was a 300 MB dependency that consumed significant memory and introduced timing fragility
- **MoviePy as a video layer:** MoviePy added abstraction but produced single-threaded, slow video processing and did not expose the full power of the underlying ffmpeg
- **Duplicate AI paths:** `ai.py` and `ai_structured.py` implemented the same clip-selection logic with different output routing, causing drift
- **Over-abstracted backend:** Repositories, services, workers, and utils layers for what is fundamentally a small local application
- **Authentication overhead:** Better Auth and Prisma were included for a single-user local tool where authentication was already bypassed in practice

The redesign collapses the entire application into a single Python process. NiceGUI (which is built on FastAPI) serves both the web UI and the API from the same process. ffmpeg replaces both MoviePy and Playwright for all video and subtitle work. The result is faster, simpler, and requires only Python and ffmpeg to run.

---

## 2. Architecture

### New Project Structure

```
supoclip/
├── src/
│   ├── __init__.py
│   ├── main.py              # NiceGUI + FastAPI app entry point; orchestration only
│   ├── config.py            # Pydantic BaseSettings; all env/config loading
│   ├── database.py          # SQLAlchemy async engine, session factory, Base
│   ├── models.py            # SQLAlchemy ORM models (3 tables)
│   ├── pages/               # NiceGUI UI pages (one file per route)
│   │   ├── home.py          # URL input, file upload, start processing
│   │   ├── task.py          # Real-time progress, clip viewer, download
│   │   ├── history.py       # Task list with status badges
│   │   └── settings.py      # Font, clip length, AI prompt, logo, resolution prefs
│   ├── pipeline/            # Video processing pipeline stages
│   │   ├── download.py      # yt-dlp YouTube/URL download
│   │   ├── transcribe.py    # parakeet-mlx transcription + cache
│   │   ├── analyze.py       # Unified Pydantic AI clip selection
│   │   ├── clip.py          # ffmpeg trim, 9:16 crop, H.264 encode
│   │   ├── subtitles.py     # pysubs2 ASS subtitle file generation
│   │   └── face_detect.py   # MediaPipe face detection; center crop fallback
│   └── services/
│       └── video_service.py # Orchestrates pipeline stages; asyncio.TaskGroup
├── fonts/                   # Bundled TTF font files
├── transitions/             # Optional transition effect MP4 files
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
├── pyproject.toml           # uv-managed; ruff, mypy, pytest config
└── .pre-commit-config.yaml
```

### Architectural Principles

**Single process.** NiceGUI IS FastAPI. The same Python process serves the web UI at `/` and any raw API endpoints. No inter-process communication, no port negotiation.

**No Node.js.** The `frontend/` and `waitlist/` directories are deleted. There is no npm, no webpack, no Turbopack. All HTML is rendered by NiceGUI components.

**No authentication.** SupoClip is a single-user local application. The auth system (Better Auth, Prisma adapter, sessions, accounts tables) is removed entirely. There is no `user_id` header, no login page, no session management.

**ffmpeg is the video engine.** Every video operation — trim, crop, scale, subtitle burn, logo overlay, encode — is expressed as a single ffmpeg subprocess call. No Python video library sits between the application and ffmpeg.

**asyncio.TaskGroup for concurrency.** The custom job queue (`workers/`) is deleted. Processing jobs run as asyncio tasks. `TaskGroup` provides structured concurrency with proper error propagation.

**Three database tables.** The five-table schema (users, tasks, sources, generated_clips, system_fonts) is simplified to three tables: Task, GeneratedClip, UserPreferences. Font metadata is not persisted; fonts are discovered at startup from the `fonts/` directory.

---

## 3. Technology Stack

### New Dependencies

| Package | Version | Purpose |
|---|---|---|
| nicegui | >=3.0 | Python web UI built on FastAPI/Starlette; replaces React/Next.js |
| pysubs2 | >=1.7 | ASS/SRT subtitle file generation; replaces Playwright canvas rendering |
| structlog | >=24.0 | Structured JSON/console logging; replaces custom emoji logging |

### Kept Dependencies

| Package | Purpose |
|---|---|
| fastapi | HTTP framework (NiceGUI uses it internally) |
| uvicorn | ASGI server |
| pydantic | Data validation; strict mode enforced |
| pydantic-settings | `.env` file loading into typed config |
| sqlalchemy + aiosqlite | Async SQLite ORM |
| pydantic-ai | LLM agent for clip segment selection |
| parakeet-mlx | Apple Silicon offline transcription with word-level timing |
| yt-dlp | YouTube and video URL download |
| mediapipe | Face detection (primary; no fallback detectors) |
| Pillow | Logo image resize before ffmpeg overlay |
| groq | Groq API client for cloud LLM |
| openai | OpenAI-compatible API client (also used for local LLM) |
| fonttools | TTF font inspection at startup |
| httpx | External HTTP calls; strict timeouts |
| orjson | Fast JSON serialization |
| stamina | Retry logic with exponential backoff |
| rich | Console progress and tables |

### Removed Dependencies

| Package | Reason for Removal |
|---|---|
| playwright | Replaced by pysubs2 + ffmpeg ASS subtitle rendering |
| moviepy | Replaced by direct ffmpeg subprocess calls |
| opencv-python | Only used for DNN/Haar fallback detectors; removed with MediaPipe-only strategy |
| matplotlib | Was unused |
| sse-starlette | NiceGUI uses WebSocket; SSE polling is not needed |
| aiofiles | Replaced by `pathlib.Path` + `asyncio.to_thread` |
| greenlet | No longer needed without MoviePy/gevent |
| python-dotenv | pydantic-settings loads `.env` natively |
| All npm packages | No Node.js in the new architecture |
| better-auth | Auth removed entirely |
| @prisma/client | Auth/frontend database layer removed |

### System Dependencies

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12 preferred, 3.11 minimum | Runtime |
| ffmpeg | Latest stable | Video processing, subtitle rendering, encoding |
| uv | Latest | Package manager (pip and poetry are banned) |

---

## 4. Module Specifications

### 4.1 `src/main.py`

**Purpose:** Application entry point. Mounts NiceGUI pages and configures the FastAPI app. Contains no business logic.

**Responsibilities:**
- Configure structlog at startup
- Initialise the SQLAlchemy async engine (call `database.init_db()`)
- Register all `@ui.page` decorated page functions from `pages/`
- Configure static file serving for `fonts/` and the clip output directory
- Start uvicorn via `ui.run()` with the host/port from config
- Register application lifespan for startup/shutdown hooks

**Entry point invocation:**
```bash
python -m src.main
# or:
uv run run-dev
```

**Inputs:** None (reads config via `Config()` at module level)
**Outputs:** Running ASGI server

---

### 4.2 `src/config.py`

**Purpose:** All application configuration loaded from `.env` and environment variables via `pydantic-settings`. Single source of truth for every tuneable value.

**Class:** `Config(BaseSettings)` with `model_config = SettingsConfigDict(extra="ignore")`

See Section 8 for the complete list of fields and defaults.

---

### 4.3 `src/database.py`

**Purpose:** SQLAlchemy async engine, session factory, and declarative base.

**Exports:**
- `Base` — `DeclarativeBase` subclass; all ORM models inherit from it
- `AsyncSessionLocal` — `async_sessionmaker` factory
- `init_db()` — async function; creates all tables via `Base.metadata.create_all`
- `get_session()` — async context manager yielding `AsyncSession`

**Pattern:**
```python
async with get_session() as session:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
```

---

### 4.4 `src/models.py`

**Purpose:** SQLAlchemy ORM models for the three database tables.

See Section 7 for complete field specifications.

---

### 4.5 `src/pages/home.py`

**Purpose:** NiceGUI page at `/`. Accepts YouTube URL or uploaded video file; submits a processing job.

See Section 6.1 for UI component details.

---

### 4.6 `src/pages/task.py`

**Purpose:** NiceGUI page at `/task/{task_id}`. Shows real-time processing progress and displays generated clips when done.

See Section 6.2 for UI component details.

---

### 4.7 `src/pages/history.py`

**Purpose:** NiceGUI page at `/history`. Paginated list of all past tasks with status, title, and clip count.

See Section 6.3 for UI component details.

---

### 4.8 `src/pages/settings.py`

**Purpose:** NiceGUI page at `/settings`. Persists user preferences to the `UserPreferences` table.

See Section 6.4 for UI component details.

---

### 4.9 `src/pipeline/download.py`

**Purpose:** Download a video from a YouTube URL or any yt-dlp-supported URL to a local file.

**Key function:**
```python
async def download_video(url: str, output_dir: Path) -> Path:
    """Download video to output_dir; return path to downloaded file."""
```

**Inputs:** URL string, output directory path
**Outputs:** `Path` to the downloaded MP4 file
**Error:** Raises `DownloadError` if yt-dlp fails or URL is unsupported

**Implementation notes:**
- Runs `yt-dlp` as a subprocess via `asyncio.to_thread` (yt-dlp is synchronous)
- Selects best video+audio format up to 1080p
- Validates that the output file exists and is non-empty after download
- Strips the URL of query parameters before using in filename to avoid injection

---

### 4.10 `src/pipeline/transcribe.py`

**Purpose:** Transcribe a video file using parakeet-mlx, producing word-level timestamps. Cache results to avoid re-transcription.

**Key functions:**
```python
async def transcribe(video_path: Path) -> TranscriptData:
    """Transcribe video; use cache if available."""

def load_cache(video_path: Path) -> TranscriptData | None:
    """Load cached transcript from .transcript_cache.json next to video."""

def save_cache(video_path: Path, data: TranscriptData) -> None:
    """Write transcript cache to disk."""
```

**Inputs:** Path to video file
**Outputs:** `TranscriptData` — a `dataclass(slots=True)` with:
  - `words: list[WordTiming]` — each word with `text`, `start_ms`, `end_ms`, `confidence`
  - `full_text: str` — concatenated transcript text
  - `duration_s: float`

**Cache location:** `{video_path}.transcript_cache.json`

**Implementation notes:**
- parakeet-mlx runs synchronously on Apple Silicon; wrap in `asyncio.to_thread`
- Cache file is JSON; deserialised via Pydantic model, not raw dict access
- If word reconstruction via LLM is enabled (`config.reconstruct_words_with_llm`), sends the raw word list to the configured LLM to fix sub-word tokens before returning

---

### 4.11 `src/pipeline/analyze.py`

**Purpose:** Unified AI clip selection. Takes a `TranscriptData` object and returns a list of candidate clip segments. This module merges the functionality of the old `ai.py` and `ai_structured.py`.

**Key function:**
```python
async def select_segments(
    transcript: TranscriptData,
    settings: ClipSettings,
) -> list[ClipSegment]:
    """Analyse transcript and return ranked clip segments."""
```

**Inputs:**
- `transcript: TranscriptData` from `transcribe.py`
- `settings: ClipSettings` — min/max duration, target count, custom system prompt override

**Outputs:** `list[ClipSegment]`, sorted by descending `score`

**`ClipSegment` fields:** `start_ms: int`, `end_ms: int`, `title: str`, `transcript_text: str`, `score: float`, `reasoning: str`

See Section 11 for full AI integration specification.

---

### 4.12 `src/pipeline/clip.py`

**Purpose:** Produce a final MP4 clip for a given `ClipSegment`. Orchestrates face detection, crops, subtitle file path, and a single ffmpeg subprocess call.

**Key function:**
```python
async def build_clip(
    source_video: Path,
    segment: ClipSegment,
    subtitle_file: Path,
    output_path: Path,
    settings: RenderSettings,
) -> Path:
    """Render one clip; return output path."""
```

**Inputs:**
- `source_video` — full-length downloaded video
- `segment` — timing and text from `analyze.py`
- `subtitle_file` — `.ass` file from `subtitles.py`
- `output_path` — where to write the output MP4
- `settings: RenderSettings` — resolution, logo path/position, font dir, encoding preset

**Outputs:** `Path` to the rendered MP4

See Section 10 for ffmpeg filter chain details.

---

### 4.13 `src/pipeline/subtitles.py`

**Purpose:** Generate a `.ass` subtitle file from word-level timing data using pysubs2.

**Key function:**
```python
def build_ass_file(
    words: list[WordTiming],
    clip_start_ms: int,
    clip_end_ms: int,
    output_path: Path,
    style: SubtitleStyle,
) -> Path:
    """Write an ASS subtitle file and return its path."""
```

**Inputs:**
- `words` — word timing list from `TranscriptData`
- `clip_start_ms`, `clip_end_ms` — clip boundaries in milliseconds
- `output_path` — where to write the `.ass` file
- `style: SubtitleStyle` — font family, size, color, stroke width, shadow, vertical position

**Outputs:** `Path` to the `.ass` file

See Section 9 for the full subtitle system specification.

---

### 4.14 `src/pipeline/face_detect.py`

**Purpose:** Sample frames from a video segment and return a crop rectangle that keeps detected faces centred in a 9:16 frame.

**Key function:**
```python
async def get_crop_rect(
    video_path: Path,
    start_s: float,
    end_s: float,
    target_width: int,
    target_height: int,
) -> CropRect:
    """Return (x, y, w, h) crop rectangle for 9:16 framing."""
```

**Inputs:** Video path, segment start/end in seconds, target output dimensions
**Outputs:** `CropRect(x=int, y=int, w=int, h=int)` — coordinates in source video pixels

**Implementation notes:**
- Samples up to 10 evenly spaced frames within the segment using ffmpeg `select` filter
- Runs MediaPipe face detection on each frame
- Aggregates face bounding boxes across frames; takes the median x-centre
- If MediaPipe detects no face in any sampled frame: returns a centre crop with no further fallback
- Ensures `w` and `h` are even numbers (H.264 requirement)
- Runs synchronous MediaPipe calls in `asyncio.to_thread`

---

### 4.15 `src/services/video_service.py`

**Purpose:** Orchestrates the full pipeline from a submitted job to finished clips. Called by the NiceGUI task page and the background task runner.

**Key function:**
```python
async def process_video(
    task_id: str,
    source_path: Path | str,
    settings: JobSettings,
    progress_callback: Callable[[int, str], Awaitable[None]],
) -> list[GeneratedClip]:
    """Run full pipeline; update task progress; return clips."""
```

**Inputs:**
- `task_id` — UUID string for the Task row to update
- `source_path` — local file path or YouTube/video URL
- `settings` — merged task + user preferences
- `progress_callback` — async function called with `(percent: int, message: str)` to push progress to the UI

**Outputs:** List of `GeneratedClip` ORM objects (persisted to DB before returning)

**Pipeline stages and progress checkpoints:**

| Stage | Progress % | Message |
|---|---|---|
| Download (if URL) | 5–20 | "Downloading video..." |
| Transcribe | 20–50 | "Transcribing audio..." |
| Analyse | 50–60 | "Selecting best segments..." |
| Render clips (per clip) | 60–95 | "Rendering clip N of M..." |
| Save to database | 95–100 | "Saving clips..." |

**Concurrency:** Clip rendering uses `asyncio.TaskGroup` to render up to `config.max_workers` clips in parallel.

---

## 5. Pipeline Flow

This section traces the complete path from user input to downloadable clip.

### 5.1 YouTube URL Input

```
User submits URL on home page
  │
  ▼
video_service.process_video(task_id, url, settings, callback)
  │
  ├─► pipeline/download.py
  │     yt-dlp downloads video → temp/{task_id}/source.mp4
  │     progress: 5% → 20%
  │
  ├─► pipeline/transcribe.py
  │     parakeet-mlx transcribes → TranscriptData (words + timestamps)
  │     cache written to temp/{task_id}/source.mp4.transcript_cache.json
  │     progress: 20% → 50%
  │
  ├─► pipeline/analyze.py
  │     LLM reads transcript → list[ClipSegment] (3–7 segments)
  │     progress: 50% → 60%
  │
  └─► For each ClipSegment (parallel via TaskGroup):
        │
        ├─► pipeline/face_detect.py
        │     Sample frames → CropRect (x, y, w, h)
        │
        ├─► pipeline/subtitles.py
        │     words + timing + style → temp/{task_id}/clip_{n}.ass
        │
        ├─► pipeline/clip.py
        │     Single ffmpeg call:
        │       trim + crop + scale + burn ASS + overlay logo + encode
        │     → temp/clips/{task_id}_clip_{n}.mp4
        │
        └─► Persist GeneratedClip row to database
              progress: 60% → 95% (increments per clip)

Task status set to "done"; progress: 100%
NiceGUI page updates via WebSocket push
```

### 5.2 File Upload Input

Same as 5.1, except the `download.py` stage is skipped. The uploaded file is saved to `temp/{task_id}/source.mp4` by the NiceGUI upload handler before `process_video` is called.

### 5.3 Error Handling in the Pipeline

Any exception raised in a pipeline stage is caught in `video_service.py`. The task status is set to `"failed"` and the error message is stored in `Task.settings_json["error"]`. The progress callback is called with `(0, "Error: {message}")`. The exception is re-raised so structlog captures the full traceback.

---

## 6. UI Specification

All pages are implemented as async functions decorated with `@ui.page(path)` in the respective `src/pages/*.py` file. NiceGUI renders them server-side and pushes updates to the browser via WebSocket.

### 6.1 Home Page (`/`)

**File:** `src/pages/home.py`

**Purpose:** Primary entry point. User provides a YouTube URL or uploads a video file, configures processing options, and launches a job.

**Components:**

| Component | Type | Behaviour |
|---|---|---|
| URL input | `ui.input` | Accepts YouTube or direct video URL; validated on submit |
| Upload zone | `ui.upload` | Accepts `.mp4`, `.mov`, `.avi`, `.mkv`; max size from config |
| Font family selector | `ui.select` | Options populated from `fonts/` directory scan at page load |
| Font size slider | `ui.slider` | Range 12–72; default 24 |
| Font colour picker | `ui.color_input` | Default `#FFFFFF` |
| Clip length range | Two `ui.number` inputs | Min and max seconds; default 10–45 |
| Target clip count | `ui.number` | Default 5; range 1–10 |
| Output resolution | `ui.select` | Options: `720p`, `1080p`; default `720p` |
| Submit button | `ui.button` | Disabled while a job is running; triggers `process_video` coroutine |
| Loading spinner | `ui.spinner` | Shown while job is enqueued |

**On submit:**
1. Validate URL or check that a file was uploaded (not both)
2. Create a `Task` row in the database with status `"pending"` and settings JSON
3. Navigate to `/task/{task_id}` — the task page handles progress from there

### 6.2 Task Page (`/task/{task_id}`)

**File:** `src/pages/task.py`

**Purpose:** Shows processing progress in real time; displays completed clips with playback and download.

**Components:**

| Component | Type | Behaviour |
|---|---|---|
| Task title | `ui.label` | Source title or URL, loaded from DB |
| Status badge | `ui.badge` | Colour-coded: grey (pending), blue (processing), green (done), red (failed) |
| Progress bar | `ui.linear_progress` | Value 0.0–1.0; updated via WebSocket |
| Progress message | `ui.label` | e.g., "Rendering clip 2 of 5..." |
| Clip grid | `ui.grid` | Rendered after status = "done" |
| Per-clip card | `ui.card` | Contains video player, title, timestamps, download button |
| Video player | `ui.video` | Served from `/clips/{filename}` static route |
| Download button | `ui.button` | Links to `/clips/{filename}` with `Content-Disposition: attachment` |
| Back button | `ui.button` | Returns to `/` |

**Real-time updates:**
The `progress_callback` passed to `video_service.process_video` calls `ui.update()` on the progress bar and message label. NiceGUI pushes the DOM mutation to the browser via WebSocket. No polling.

**Error state:**
If `task.status == "failed"`, show the error message from `task.settings_json["error"]` in a red alert card.

### 6.3 History Page (`/history`)

**File:** `src/pages/history.py`

**Purpose:** Browse all past tasks. Navigate to any task to re-view its clips.

**Components:**

| Component | Type | Behaviour |
|---|---|---|
| Page title | `ui.label` | "Processing History" |
| Task table | `ui.table` | Columns: title, status, clip count, created date; sorted newest-first |
| Status badge per row | `ui.badge` | Same colour coding as task page |
| Row click | `on_click` | Navigates to `/task/{task_id}` |
| Delete button per row | `ui.button` | Soft-deletes task and associated clips from DB |
| Empty state | `ui.label` | "No tasks yet. Process a video to get started." |

### 6.4 Settings Page (`/settings`)

**File:** `src/pages/settings.py`

**Purpose:** Edit and persist user preferences. Pre-populated from the `UserPreferences` singleton row.

**Components:**

| Component | Type | Field saved |
|---|---|---|
| Default font family | `ui.select` | `UserPreferences.font_family` |
| Default font size | `ui.slider` | `UserPreferences.font_size` |
| Default font colour | `ui.color_input` | `UserPreferences.font_color` |
| Min clip length | `ui.number` | `UserPreferences.clip_min_s` |
| Target clip length | `ui.number` | `UserPreferences.clip_target_s` |
| Max clip length | `ui.number` | `UserPreferences.clip_max_s` |
| Custom AI prompt | `ui.textarea` | `UserPreferences.custom_ai_prompt`; empty = use default |
| Logo upload | `ui.upload` | Saves file to `temp/logo.png`; `UserPreferences.logo_path` |
| Logo corner | `ui.select` | Options: top-left, top-right, bottom-left, bottom-right |
| Output resolution | `ui.select` | Options: `720p` (1080×1920), `1080p` (2160×3840 — note: 2160w × 3840h) |
| Save button | `ui.button` | Upserts the singleton `UserPreferences` row |

---

## 7. Data Model

The new schema has three tables. All IDs are UUID v4 strings stored as `VARCHAR(36)`. Timestamps use `DATETIME` with UTC timezone.

### 7.1 `tasks`

Represents one processing job — from video input to finished clips.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | NO | uuid4() | Primary key |
| `source_url` | TEXT | YES | NULL | YouTube URL or uploaded filename |
| `source_type` | VARCHAR(20) | NO | — | `'youtube'`, `'upload'`, `'url'` |
| `status` | VARCHAR(20) | NO | `'pending'` | `'pending'`, `'processing'`, `'done'`, `'failed'` |
| `progress` | INTEGER | NO | `0` | 0–100 percent |
| `progress_message` | TEXT | YES | NULL | Current stage description |
| `settings_json` | JSON | YES | NULL | Snapshot of job settings at submit time; also stores `error` key on failure |
| `created_at` | DATETIME | NO | now() | |
| `updated_at` | DATETIME | NO | now() | Auto-updated on row change |

**Constraints:**
- `status IN ('pending', 'processing', 'done', 'failed')`
- `source_type IN ('youtube', 'upload', 'url')`

### 7.2 `generated_clips`

One row per output clip file.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | NO | uuid4() | Primary key |
| `task_id` | VARCHAR(36) | NO | — | FK → `tasks.id` ON DELETE CASCADE |
| `filename` | VARCHAR(255) | NO | — | Output MP4 filename (no path) |
| `start_time` | VARCHAR(20) | NO | — | `MM:SS.mmm` format |
| `end_time` | VARCHAR(20) | NO | — | `MM:SS.mmm` format |
| `title` | VARCHAR(255) | YES | NULL | AI-generated clip title |
| `transcript_text` | TEXT | YES | NULL | Verbatim transcript for this segment |
| `score` | FLOAT | NO | — | AI relevance score 0.0–1.0 |
| `reasoning` | TEXT | YES | NULL | AI explanation of segment selection |
| `clip_order` | INTEGER | NO | — | Display order within the task |
| `created_at` | DATETIME | NO | now() | |
| `updated_at` | DATETIME | NO | now() | Auto-updated on row change |

### 7.3 `user_preferences`

Singleton table — always exactly one row (created on first app start).

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | NO | 1 | Fixed primary key; always 1 |
| `font_family` | VARCHAR(100) | NO | `'TikTokSans-Regular'` | Font file stem from `fonts/` |
| `font_size` | INTEGER | NO | `24` | Points |
| `font_color` | VARCHAR(7) | NO | `'#FFFFFF'` | Hex colour code |
| `clip_min_s` | INTEGER | NO | `10` | Minimum clip duration seconds |
| `clip_target_s` | INTEGER | NO | `30` | Target clip duration seconds |
| `clip_max_s` | INTEGER | NO | `45` | Maximum clip duration seconds |
| `target_clip_count` | INTEGER | NO | `5` | How many clips to request from AI |
| `custom_ai_prompt` | TEXT | YES | NULL | Appended to system prompt; NULL = use default |
| `logo_path` | VARCHAR(500) | YES | NULL | Absolute path to logo image |
| `logo_position` | VARCHAR(20) | NO | `'top-right'` | `'top-left'`, `'top-right'`, `'bottom-left'`, `'bottom-right'` |
| `output_resolution` | VARCHAR(10) | NO | `'720p'` | `'720p'` or `'1080p'` |
| `updated_at` | DATETIME | NO | now() | Auto-updated on row change |

**Constraints:**
- `logo_position IN ('top-left', 'top-right', 'bottom-left', 'bottom-right')`
- `output_resolution IN ('720p', '1080p')`

---

## 8. Configuration

All configuration is loaded by `src/config.py` via `pydantic-settings`. Values come from environment variables or a `.env` file in the project root. The class is `Config(BaseSettings)`.

### 8.1 LLM Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `LOCAL_LLM_ENABLED` | bool | `true` | Use local LLM (e.g., KoboldCPP) as primary |
| `LOCAL_LLM_BASE_URL` | str | `http://localhost:6969/v1` | OpenAI-compatible local endpoint |
| `LOCAL_LLM_MODEL` | str | `local-model` | Model name sent to local endpoint |
| `LOCAL_LLM_API_KEY` | str | `not-needed` | Placeholder key for local endpoint |
| `LLM_MODEL` | str | `""` | Cloud model string, e.g. `groq:llama-4-scout-17b` |
| `GROQ_API_KEY` | str | `""` | Groq API key for cloud LLM |
| `OPENAI_API_KEY` | str | `""` | OpenAI API key |
| `ANTHROPIC_API_KEY` | str | `""` | Anthropic API key |
| `GOOGLE_API_KEY` | str | `""` | Google API key |

LLM selection priority: local (if `LOCAL_LLM_ENABLED=true`) → cloud (if `LLM_MODEL` + matching API key set) → raise `ValueError`.

### 8.2 Transcription Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `PARAKEET_MODEL` | str | `mlx-community/parakeet-tdt-0.6b-v2` | HuggingFace model ID for parakeet-mlx |
| `RECONSTRUCT_WORDS_WITH_LLM` | bool | `true` | Fix sub-word tokens via LLM post-processing |

### 8.3 Video Processing Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `TEMP_DIR` | str | `temp` | Root directory for downloads, clip output, uploads |
| `MAX_VIDEO_DURATION` | int | `3600` | Seconds; reject downloads longer than this |
| `MAX_CLIPS` | int | `10` | Hard ceiling on clips per task |
| `FFMPEG_PRESET` | str | `fast` | libx264 preset: `ultrafast`, `fast`, `medium`, `slow` |
| `FFMPEG_CRF` | int | `23` | libx264 CRF quality; lower = better quality + larger file |

### 8.4 Application Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | str | `sqlite+aiosqlite:///./supoclip.db` | SQLAlchemy connection string |
| `HOST` | str | `0.0.0.0` | Bind address for uvicorn |
| `PORT` | int | `8008` | Bind port |
| `MAX_WORKERS` | int | `2` | Parallel clip rendering tasks |
| `LOG_LEVEL` | str | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_DIR` | str | `logs` | Directory for structlog file output |

---

## 9. Subtitle System

The subtitle system replaces the previous Playwright-based approach. The prior system launched a headless Chromium browser, rendered each word onto an HTML canvas with CSS styling, and took a screenshot to use as a video overlay frame. The new system generates a standard ASS (Advanced SubStation Alpha) subtitle file using pysubs2 and passes it to ffmpeg's native `libass` renderer via the `ass=` video filter.

### 9.1 ASS Format Overview

ASS is a rich subtitle format that supports:
- Per-event fonts (typeface, size, bold, italic)
- Colours with alpha (primary, secondary, outline, shadow)
- Outline width and shadow depth
- Margin offsets from edges
- Override tags inline with text for per-word colour changes

An ASS file has two sections: `[Script Info]` (metadata) and `[Events]` (one line per subtitle event, each with a start/end timestamp and text).

### 9.2 Word-Level Event Strategy

Each word in the clip's word-timing list becomes one ASS `Dialogue` event. The event spans from the word's start time to its end time. This produces per-word subtitle highlighting when combined with ffmpeg's `libass` renderer.

For readability, a "context line" approach is used: the active word is shown in the primary colour (e.g., white), and the surrounding words from the current phrase (up to 6 words) are shown in a dimmed secondary colour. This is implemented using ASS inline override tags (`{\c&HBBGGRR&}`) within a single event that groups the phrase.

### 9.3 `SubtitleStyle` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `font_family` | str | `TikTokSans-Regular` | Font file stem; must exist in `fonts/` |
| `font_size` | int | `24` | ASS `Fontsize` in points (ASS points, not CSS pixels) |
| `primary_color` | str | `&H00FFFFFF` | ASS colour format `&HAABBGGRR` for active word |
| `secondary_color` | str | `&H80FFFFFF` | Dimmed context words |
| `outline_color` | str | `&H00000000` | Stroke colour |
| `shadow_color` | str | `&H80000000` | Drop shadow colour |
| `outline_width` | float | `2.0` | Stroke width in ASS units |
| `shadow_depth` | float | `1.0` | Shadow offset in ASS units |
| `vertical_margin` | int | `25` | Bottom margin percent of video height |
| `bold` | bool | `False` | Bold weight |

### 9.4 pysubs2 Generation Pattern

```python
import pysubs2

subs = pysubs2.SSAFile()

style = pysubs2.SSAStyle(
    fontname=style.font_family,
    fontsize=style.font_size,
    primarycolor=pysubs2.Color.from_ass_string(style.primary_color),
    outlinecolor=pysubs2.Color.from_ass_string(style.outline_color),
    outline=style.outline_width,
    shadow=style.shadow_depth,
    marginv=int(output_height * style.vertical_margin / 100),
    bold=style.bold,
    alignment=pysubs2.Alignment.BOTTOM_CENTER,
)
subs.styles["Default"] = style

for word in clip_words:
    event = pysubs2.SSAEvent(
        start=pysubs2.make_time(s=word.start_s),
        end=pysubs2.make_time(s=word.end_s),
        text=word.text,
    )
    subs.append(event)

subs.save(str(output_path))
```

### 9.5 Font Support

Custom TTF fonts are stored in the `fonts/` directory. ffmpeg's `libass` filter accepts a `fontsdir` parameter that points to a directory of TTF files. The font name in the ASS style must match the font's internal name (not the filename).

At application startup, `main.py` scans `fonts/` using fonttools to read the `name` table from each TTF and build a mapping of `{internal_name: file_path}`. This mapping is used by the settings page dropdown and validates font selections before job submission.

The `fontsdir=fonts/` parameter in the ffmpeg filter chain makes custom fonts available to libass during encoding without installing them system-wide.

### 9.6 Colour Format Note

ASS colours are in `&HAABBGGRR` format (alpha, blue, green, red — reversed from HTML). pysubs2 handles the conversion. When accepting hex colour strings from the UI (`#RRGGBB`), `subtitles.py` converts to ASS format:

```python
def hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """Convert #RRGGBB to &HAABBGGRR ASS colour format."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
```

---

## 10. Video Processing

All video operations are performed by a single ffmpeg subprocess call per clip. No intermediate files are written between stages. The filter chain is constructed as a Python string and passed to `ffmpeg` via `subprocess.run` (list form — never `shell=True`).

### 10.1 Resolution Targets

| Setting | Output Width | Output Height | Aspect Ratio |
|---|---|---|---|
| `720p` | 1080 | 1920 | 9:16 |
| `1080p` | 2160 | 3840 | 9:16 |

All dimensions are forced to even numbers (H.264 requirement). The `round_to_even(n)` utility enforces this: `return n if n % 2 == 0 else n - 1`.

### 10.2 Core ffmpeg Command Pattern

```
ffmpeg -y \
  -ss {start_s} \
  -to {end_s} \
  -i {source_video} \
  -vf "{crop_filter},{scale_filter},{ass_filter}{logo_filter}" \
  -c:v libx264 \
  -preset {preset} \
  -crf {crf} \
  -c:a aac \
  -b:a 128k \
  -movflags +faststart \
  {output_path}
```

Explanation of flags:
- `-ss` / `-to` before `-i`: input-seeking (fast; keyframe-accurate seek before input decode begins)
- `-y`: overwrite output without prompting
- `-movflags +faststart`: place MOOV atom at file start for streaming

### 10.3 Crop and Scale Filter

Crop to the face-centred rectangle, then scale to the target resolution:

```
crop={w}:{h}:{x}:{y},scale={out_w}:{out_h}
```

Where `w`, `h`, `x`, `y` come from `face_detect.get_crop_rect()` and `out_w`/`out_h` are the target resolution.

Example for 720p output with a 1920×1080 source:
```
crop=608:1080:656:0,scale=1080:1920
```

### 10.4 Subtitle Burn-In Filter

```
ass={subtitle_path}:fontsdir={fonts_dir}
```

`{subtitle_path}` is the absolute path to the `.ass` file. `{fonts_dir}` is the absolute path to the `fonts/` directory. Paths containing colons or spaces must be escaped with backslash for the ffmpeg filter graph parser.

Full filter combining crop, scale, and subtitles:
```
crop={w}:{h}:{x}:{y},scale={out_w}:{out_h},ass={subtitle_path}:fontsdir={fonts_dir}
```

### 10.5 Logo Overlay Filter

When a logo is configured, an `overlay` filter is appended as a second video stream:

```
ffmpeg -y \
  -ss {start_s} -to {end_s} -i {source_video} \
  -i {logo_path} \
  -filter_complex "
    [0:v]crop={w}:{h}:{x}:{y},scale={out_w}:{out_h},ass={subtitle_path}:fontsdir={fonts_dir}[base];
    [1:v]scale={logo_w}:{logo_h}[logo];
    [base][logo]overlay={logo_x}:{logo_y}[out]
  " \
  -map "[out]" \
  -map 0:a \
  -c:v libx264 -preset {preset} -crf {crf} \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  {output_path}
```

Logo sizing: the logo is scaled to 10% of the output width, maintaining aspect ratio.

Logo position mapping:

| Setting | `logo_x` | `logo_y` |
|---|---|---|
| `top-left` | `20` | `20` |
| `top-right` | `W-w-20` | `20` |
| `bottom-left` | `20` | `H-h-20` |
| `bottom-right` | `W-w-20` | `H-h-20` |

Where `W`/`H` are output video dimensions and `w`/`h` are logo dimensions (ffmpeg overlay variables).

### 10.6 Filter Construction Rules

- Never use `shell=True` with `subprocess.run`; pass the command as a `list[str]`
- Escape the colon in Windows absolute paths (e.g., `C\:/path/...`) when building the `ass=` filter value — on macOS/Linux this is not needed
- Always validate that `output_path` parent directory exists before calling ffmpeg
- Capture both `stdout` and `stderr`; log stderr at DEBUG level; raise `FfmpegError` if return code is non-zero
- Use `asyncio.to_thread(subprocess.run, ...)` — ffmpeg is a blocking subprocess

---

## 11. AI Integration

### 11.1 Unified `analyze.py` Design

The old codebase had two AI modules:

- `ai.py` (551 lines): Pydantic AI agent; routed to local LLM or cloud
- `ai_structured.py` (461 lines): Groq structured outputs path; partially duplicated prompt and validation logic

These are merged into `src/pipeline/analyze.py` (~250 lines). There is one system prompt, one validation pipeline, and one public entry point (`select_segments`). Routing to Groq structured outputs vs. Pydantic AI is done by inspecting the model string in config.

### 11.2 System Prompt

The system prompt instructs the LLM to:

1. Identify 3–7 segments that would be compelling as standalone short-form content
2. Apply the **Clean Start Rule**: never begin a clip with a filler or transitional word ("And", "But", "So", "Well", "Um", "Uh", "Like", "You know"). If the natural segment start is a weak word, adjust forward to the first strong word.
3. Return timestamps in `MM:SS.mmm` format with millisecond precision, matching the transcript's word timing
4. Return the verbatim transcript text for each segment (no paraphrasing)
5. Provide a title and reasoning for each selection

The system prompt is a module-level constant. If `UserPreferences.custom_ai_prompt` is non-null, it is appended to the standard prompt as an additional instruction block.

### 11.3 Output Schema

The LLM is asked to return a JSON array. Each element matches `ClipSegment`:

```python
@dataclass(slots=True)
class ClipSegment:
    start_time: str      # MM:SS.mmm
    end_time: str        # MM:SS.mmm
    title: str
    text: str            # verbatim transcript
    score: float         # 0.0–1.0
    reasoning: str
```

Pydantic validation enforces:
- `start_time != end_time`
- Duration (end − start) >= `settings.clip_min_s`
- Duration (end − start) <= `settings.clip_max_s`
- `score` is in [0.0, 1.0]

Segments failing validation are logged and dropped. If fewer than one valid segment remains, `select_segments` raises `InsufficientSegmentsError`.

### 11.4 Model Routing

```python
def _build_agent(config: Config) -> Agent:
    """Return a Pydantic AI agent configured for the active LLM."""
    model = config.get_llm_model()
    return Agent(model=model, result_type=list[ClipSegment])
```

`Config.get_llm_model()` returns:
- An `OpenAIModel` pointing at the local LLM endpoint when `LOCAL_LLM_ENABLED=true`
- A pydantic-ai model string (e.g., `"groq:llama-4-scout-17b"`) when using a cloud LLM

For Groq structured outputs specifically (model string starts with `groq:`), pydantic-ai's Groq provider uses the Groq structured outputs API which enforces schema compliance in the response. For all other providers, pydantic-ai falls back to prompt-based JSON extraction with retry.

### 11.5 Retry and Validation

```python
@stamina.retry(on=Exception, attempts=3, wait_initial=2.0, wait_max=10.0)
async def select_segments(
    transcript: TranscriptData,
    settings: ClipSettings,
) -> list[ClipSegment]:
    ...
```

`stamina` provides exponential backoff retries. The inner validation loop re-attempts the LLM call if the returned segments all fail validation (e.g., all timestamps are identical).

---

## 12. Development Standards

This section summarises the rules from `docs/rules-python.md` that are most directly relevant to this codebase. The full rules document is authoritative; this section is a quick reference.

### 12.1 Language and Syntax

- **Python 3.12 target.** Use `type` aliases (PEP 695), generic classes with `class Foo[T]:`, `@override` from `typing`.
- **No typing imports for builtins.** Use `list[str]`, `dict[str, int]`, `str | None`. Never `List`, `Dict`, `Optional`, `Union`.
- **No relative imports.** All imports are absolute from the project source root (`from src.pipeline.clip import build_clip`).
- **File markers.** Every file starts with `# start src/path/to/file.py` and ends with `# end src/path/to/file.py`.

### 12.2 Banned Patterns

- `print()` — use `structlog`
- `logging` stdlib in application code — use `structlog`
- `subprocess.run(cmd, shell=True)` with any user-supplied string — always use list form
- `moviepy`, `playwright`, `tqdm`, `tenacity`, `requests`, `poetry` — all banned
- `assert` for runtime checks — use `if/raise`
- Mutable defaults in function signatures
- Bare `except:` or `except Exception:` that swallows exceptions
- `# TODO`, `pass`, `...` bodies (no stubs or placeholders)
- Magic numbers — extract to named constants or config

### 12.3 Complexity Limits

| Limit | Max |
|---|---|
| Statements per function | 50 |
| Cyclomatic complexity (radon/ruff C901) | 10 |
| Parameters per function | 5 |
| Return statements | 6 |
| Nesting levels inside a function | 4 |

### 12.4 Structlog Usage

```python
import structlog
log = structlog.get_logger()

# Bind context at the start of a request or job
log = log.bind(task_id=task_id)

log.info("pipeline.download.started", url=url)
log.info("pipeline.clip.rendered", clip_index=i, duration_s=duration)
log.error("pipeline.ffmpeg.failed", returncode=proc.returncode, stderr=stderr)
```

Production output is JSON (one object per line). Development output uses structlog's `ConsoleRenderer` with coloured key-value pairs. Log level is set from `config.log_level`.

### 12.5 Error Handling

- Define a custom exception hierarchy in `src/exceptions.py`: `SupoClipError` as base; `DownloadError`, `TranscriptionError`, `AnalysisError`, `RenderError`, `InsufficientSegmentsError` as subclasses.
- Raise the most specific exception at the point of failure.
- Catch broad exceptions only at the pipeline orchestration level (`video_service.py`), log the full traceback with structlog, and translate to task status `"failed"`.
- Never catch and suppress exceptions silently.

### 12.6 Subprocess Safety

All ffmpeg and yt-dlp calls use list-form subprocess with no shell:

```python
proc = await asyncio.to_thread(
    subprocess.run,
    ["ffmpeg", "-y", "-ss", str(start_s), ...],  # list, not string
    capture_output=True,
    text=True,
    check=False,  # check return code manually to log stderr first
)
if proc.returncode != 0:
    log.error("ffmpeg.failed", stderr=proc.stderr)
    raise RenderError(f"ffmpeg exited {proc.returncode}")
```

### 12.7 Pydantic Models

All data models use strict mode:

```python
from pydantic import BaseModel, ConfigDict

class ClipSettings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    clip_min_s: int
    clip_max_s: int
    target_count: int
    custom_prompt: str | None = None
```

### 12.8 Package Management

`uv` only. No `pip install`, no `poetry`. Adding a dependency: `uv add <package>`. Running the app: `uv run python -m src.main` or `uv run run-dev`.

---

## 13. Testing Strategy

### 13.1 Coverage Requirement

100% test coverage is mandatory. `pytest --cov=src --cov-fail-under=100` must pass before any commit. This is enforced by `checkpython.sh` and the pre-commit hook.

### 13.2 Test Structure

```
tests/
├── unit/
│   ├── pipeline/
│   │   ├── test_download.py
│   │   ├── test_transcribe.py
│   │   ├── test_analyze.py
│   │   ├── test_clip.py
│   │   ├── test_subtitles.py
│   │   └── test_face_detect.py
│   ├── test_config.py
│   ├── test_models.py
│   └── test_video_service.py
└── integration/
    ├── test_pipeline_end_to_end.py
    └── test_nicegui_pages.py
```

### 13.3 Unit Testing Guidelines

**Config (`test_config.py`):**
- Test that each env var overrides the default
- Test `get_llm_model()` returns correct model type for each combination of `LOCAL_LLM_ENABLED` + cloud keys
- Test `get_llm_model()` raises `ValueError` when nothing is configured

**Models (`test_models.py`):**
- Test all Pydantic model validations (strict mode rejects coercion; `extra="forbid"` rejects unknown fields)
- Test `ClipSegment` validation rejects equal start/end times
- Use `pytest.mark.parametrize` for boundary cases

**Download (`test_download.py`):**
- Mock `subprocess.run` via `unittest.mock.patch`
- Test that `DownloadError` is raised when yt-dlp returns non-zero exit code
- Test that `DownloadError` is raised when output file is missing after download
- Test URL sanitisation

**Transcription (`test_transcribe.py`):**
- Test cache hit path: mock file system; verify parakeet-mlx is never called
- Test cache miss path: mock parakeet-mlx call; verify cache is written
- Test `TranscriptData` Pydantic parsing with valid and invalid JSON

**Analysis (`test_analyze.py`):**
- Mock the Pydantic AI agent's `run()` method using `pytest-httpx` or direct monkeypatching
- Test that segments with equal start/end times are dropped
- Test that segments with duration below `clip_min_s` are dropped
- Test retry behaviour: mock agent returns invalid segments on first call, valid on second
- Test that `InsufficientSegmentsError` is raised when all segments are invalid

**Subtitles (`test_subtitles.py`):**
- Test `hex_to_ass_color` with known inputs/outputs
- Test `build_ass_file` produces a parseable ASS file using pysubs2
- Test that words outside the clip window are excluded
- Test `SubtitleStyle` Pydantic validation (e.g., font_size bounds)

**Face Detection (`test_face_detect.py`):**
- Mock MediaPipe calls via monkeypatch
- Test that `get_crop_rect` returns a centred rectangle when MediaPipe finds no faces
- Test that dimensions are always even numbers
- Test aggregation logic with multiple frames and varying face positions

**Clip Building (`test_clip.py`):**
- Mock `subprocess.run` to return a success code; verify the ffmpeg command list is correctly constructed
- Test that `RenderError` is raised on non-zero exit code
- Test filter chain construction for: no logo, top-right logo, bottom-left logo, 720p, 1080p

**Video Service (`test_video_service.py`):**
- Mock all pipeline modules
- Test that `progress_callback` is called with monotonically increasing percent values
- Test that task status is set to `"failed"` when any pipeline stage raises
- Test parallel clip rendering with `asyncio.TaskGroup` using async mocks

### 13.4 Integration Testing

**End-to-end pipeline (`test_pipeline_end_to_end.py`):**
- Use a short (< 30s) real `.mp4` fixture committed to `tests/fixtures/`
- Run the full pipeline (no LLM mocking; use a real local LLM or a deterministic stub)
- Assert that at least one `.mp4` clip is produced
- Assert that all produced clips are valid ffmpeg-readable files (probe with `ffprobe`)

**NiceGUI pages (`test_nicegui_pages.py`):**
- Use NiceGUI's built-in test client (`nicegui.testing.User`)
- Test that the home page renders the URL input and upload zone
- Test that submitting a URL navigates to `/task/{id}`
- Test that the history page lists tasks from the test database

### 13.5 Quality Gate

Before any commit, run `./checkpython.sh` which executes:

| Tool | Command | Must Pass |
|---|---|---|
| ruff | `ruff check src/` | Zero errors |
| ruff | `ruff format --check src/` | Zero format violations |
| mypy | `mypy src/` | Zero type errors |
| pytest | `pytest tests/ --cov=src --cov-fail-under=100` | 100% coverage, 100% passing |
| deptry | `deptry src/` | Zero unused/missing deps |
| xenon | `xenon src/ --max-absolute B` | All files grade B or better |
| bandit | `bandit -r src/` | Zero high-severity issues |

---

## Appendix A: Deleted Files and Their Replacements

| Deleted | Replaced By |
|---|---|
| `frontend/` (React/Next.js, ~3,900 lines) | `src/pages/` (NiceGUI) |
| `waitlist/` (Next.js landing page) | Not replaced (out of scope for local app) |
| `backend/src/subtitle_renderer.py` (Playwright) | `src/pipeline/subtitles.py` (pysubs2) |
| `backend/src/ai_structured.py` | `src/pipeline/analyze.py` (unified) |
| `backend/src/ai.py` | `src/pipeline/analyze.py` (unified) |
| `backend/src/cropping.py` | `src/pipeline/face_detect.py` + ffmpeg `crop=` filter |
| `backend/src/clip_assembly.py` | `src/pipeline/clip.py` (single ffmpeg call) |
| `backend/src/logging_config.py` | structlog configured in `main.py` |
| `backend/src/dependencies.py` | Not replaced (auth removed) |
| `backend/src/workers/` | `asyncio.TaskGroup` in `video_service.py` |
| `backend/src/api/` | NiceGUI `@ui.page` routes + minimal FastAPI endpoints |
| `backend/src/repositories/` | Direct SQLAlchemy calls in service layer |
| `backend/src/services/video_service_async.py` | `src/services/video_service.py` |
| `backend/src/services/task_service.py` | Inlined into `video_service.py` |
| `backend/src/services/user_preferences_service.py` | Direct ORM calls in settings page |
| `backend/src/utils/` | Inline utilities in each module |
| `backend/src/video_utils.py` | Not replaced (was a re-export facade) |
| `start.sh` | `uv run run-dev` (single process) |

---

## Appendix B: Migration Notes

The old database schema had 5 tables: `users`, `tasks`, `sources`, `generated_clips`, `system_fonts`. The new schema has 3 tables: `tasks`, `generated_clips`, `user_preferences`. There is no data migration path — this is a from-scratch implementation. The old database file (`supoclip.db`) should be removed before running the new application for the first time.

---

# end docs/spec.md
