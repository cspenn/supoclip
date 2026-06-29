# start docs/spec.md

# SupoClip Technical Specification — "Clean Consolidation" Redesign

**Version:** 1.1
**Date:** 2026-06-29
**Status:** Living document — updated to reflect current codebase

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
14. [Vision-Aware Clipping](#14-vision-aware-clipping)

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
│   ├── db_base.py           # DeclarativeBase only — prevents import cycle
│   ├── database.py          # SQLAlchemy async engine, session factory (imports Base from db_base)
│   ├── exceptions.py        # SupoClipError hierarchy
│   ├── models.py            # SQLAlchemy ORM models (3 tables)
│   ├── pages/               # NiceGUI UI pages (one file per route)
│   │   ├── _util.py         # Shared page helpers (truncate, remove_clip_files)
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
│   │   ├── face_detect.py   # MediaPipe face detection; center crop fallback
│   │   ├── vision.py        # VLM multimodal orchestration (active speaker, engagement, thumbnails)
│   │   └── quality.py       # Deterministic ffmpeg quality utilities (scene snap, brightness)
│   └── services/
│       └── video_service.py # Orchestrates pipeline stages; asyncio.TaskGroup
├── fonts/                   # Bundled TTF font files
├── transitions/             # Optional transition effect MP4 files
├── tests/
│   ├── unit/                # Pytest-collected unit tests (mocked I/O)
│   ├── integration/         # Pytest-collected integration tests (real ffmpeg output)
│   └── e2e/                 # Manual smoke tests (NOT pytest-collected; see §13.2)
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
| ffmpeg | Latest stable — must be built with **libass** | Video processing, subtitle rendering, encoding |
| uv | Latest | Package manager (pip and poetry are banned) |

**Important:** The `ass=` and `subtitles=` ffmpeg filters require libass support compiled into ffmpeg. The system ffmpeg shipped by Homebrew core (`brew install ffmpeg`) lacks libass on many macOS setups, causing subtitle burn-in to silently fail. Use the community tap instead:

```bash
brew tap homebrew-ffmpeg/ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libass
```

Verify libass is available: `ffmpeg -filters 2>&1 | grep ass` — must show `ass` and `subtitles` entries.

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

**Purpose:** SQLAlchemy async engine, session factory, and lazy schema initialisation.

**Note on import structure:** `Base` (the `DeclarativeBase` subclass) is defined in `src/db_base.py` and re-exported from `database.py` so existing callers using `from src.database import Base` continue to work. This indirection breaks the import cycle that would occur if `database.py` imported `models.py` directly at module level.

**Exports:**
- `Base` — re-exported from `src.db_base`; all ORM models inherit from it
- `init_db(database_url: str)` — async; creates all tables via `Base.metadata.create_all`, then calls `_add_missing_columns`
- `get_session()` — async context manager yielding `AsyncSession`; auto-commits on exit, rolls back on exception
- `get_engine()` — returns the active `AsyncEngine`; raises `RuntimeError` if `init_db()` has not been called
- `close_db()` — async; disposes the engine on application shutdown

**Additive migration:** After `create_all`, `init_db` calls `_add_missing_columns(connection)`. This function inspects each existing table and issues `ALTER TABLE "{table}" ADD COLUMN "{column}" {type}` for any column present in the ORM model but absent in the live table. This handles nullable columns added after initial deployment without a migration framework. New NOT NULL columns require a server default to be safe under SQLite.

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
- Sub-word token cleanup is handled in the transcription layer itself; there is no `reconstruct_words_with_llm` configuration knob

---

### 4.11 `src/pipeline/analyze.py`

**Purpose:** Unified AI clip selection. Takes a `TranscriptData` object and returns a list of candidate clip segments. This module merges the functionality of the old `ai.py` and `ai_structured.py`.

**Key function:**
```python
async def analyze_transcript(
    transcript_text: str,
    words: list[dict],
    min_length_s: float = 15.0,
    max_length_s: float = 45.0,
    custom_prompt: str | None = None,
) -> list[TranscriptSegment]:
    """Select the best clips from a video transcript."""
```

**Inputs:**
- `transcript_text: str` — full transcript as plain text
- `words: list[dict]` — word-level timing data `[{"text", "start_ms", "end_ms"}, ...]` used to derive an upper time bound for hallucination rejection
- `min_length_s` / `max_length_s` — clip duration constraints in seconds
- `custom_prompt: str | None` — appended to the default system prompt when provided

**Outputs:** `list[TranscriptSegment]`, sorted by descending `score`

**`TranscriptSegment` fields (Pydantic `BaseModel`, `strict=True`, `extra="forbid"`):**
- `start_time: float` — clip start in seconds
- `end_time: float` — clip end in seconds
- `text: str` — verbatim transcript text
- `score: float` — relevance score in [0.0, 1.0], default 0.8
- `title: str` — suggested clip title, default `""`

**Internal `_RawSegment`:** The LLM receives and returns timestamps in `MM:SS.mmm` string format. `_raw_segments_to_transcript_segments()` parses them to float seconds before constructing `TranscriptSegment` objects. The `reasoning` field is accepted by `_RawSegment` (extra-ignore) but is not propagated to the public `TranscriptSegment`.

See Section 11 for full AI integration specification.

---

### 4.12 `src/pipeline/clip.py`

**Purpose:** Produce a final MP4 clip for a given segment. Orchestrates face detection, crops, subtitle generation, and a single ffmpeg subprocess call per clip. Optionally prepends a transition clip via a two-pass concat command.

**Key functions:**
```python
async def generate_clip(
    source_video: Path,
    segment: TranscriptSegment,
    words: list[dict],
    output_path: Path,
    options: ClipOptions | None = None,
) -> Path:
    """Render one clip; return output path."""

def build_ffmpeg_command(
    source_video: Path,
    segment: TranscriptSegment,
    crop_box: tuple[int, int, int, int],
    output_path: Path,
    options: ClipOptions,
    video_width: int,
    video_height: int,
    ass_path: Path | None,
) -> list[str]:
    """Build the ffmpeg argument list for a clip (no transition)."""

def build_concat_command(
    transition_path: Path,
    clip_path: Path,
    output_path: Path,
) -> list[str]:
    """Build the ffmpeg concat command to prepend a transition clip."""
```

**`ClipOptions` fields:**
- `output_resolution: str` — e.g. `"1080p"` (default) or `"720p"`
- `subtitle_style: SubtitleStyle | None` — ASS subtitle styling; `None` = no subtitles
- `logo_path: str | Path | None` — path to branding overlay image; `None` = no logo
- `transition_path: str | Path | None` — transition MP4 prepended to the clip; `None` = no transition
- `active_speaker_side: str | None` — `"left"/"right"/"center"` from VLM; overrides face-based crop

**Resolution presets:**

| Setting | Output Width | Output Height |
|---|---|---|
| `720p` | 720 | 1280 |
| `1080p` | 1080 | 1920 |

Default is `1080p`. Logo width is scaled to ~18% of output width (`_LOGO_WIDTH_FRACTION = 0.18`).

**Video dimensions:** probed via `ffprobe` (JSON output). `cv2` is NOT used for dimension probing.

**Timeout:** ffmpeg is killed after `config.ffmpeg_timeout_s` seconds (default 300). The timeout is applied via `asyncio.wait_for` wrapping the `asyncio.to_thread` call.

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

**Purpose:** Detect faces in video frames and return a crop rectangle that keeps the primary face centred in a 9:16 frame.

**Key functions:**
```python
def detect_face_center(frame: np.ndarray) -> tuple[int, int] | None:
    """Return (cx, cy) of the largest detected face, or None."""

def detect_face_center_multi(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int = 10,
) -> tuple[int, int] | None:
    """Sample multiple frames, aggregate face centres, return median (cx, cy) or None."""

def calculate_crop_box(
    frame_width: int,
    frame_height: int,
    face_center: tuple[int, int] | None,
    target_width: int = 1080,
    target_height: int = 1920,
) -> tuple[int, int, int, int]:
    """Return (x, y, crop_w, crop_h) in source-video pixels for 9:16 framing."""

def get_representative_frame(
    video_path: str | Path,
    timestamp_s: float,
) -> np.ndarray | None:
    """Extract a single frame via cv2; returns None if cv2 is unavailable."""
```

**Face detector:** MediaPipe Tasks API — `mediapipe.tasks.python.vision.FaceDetector` backed by the BlazeFace short-range `.tflite` model. The model is downloaded once and cached to `{temp_dir}/models/blaze_face_short_range.tflite`. The detector instance is cached via `@lru_cache(maxsize=1)`.

**No OpenCV DNN or Haar fallback.** cv2 is used only in `get_representative_frame()` for frame extraction (optional soft import; returns `None` if cv2 is absent). Face detection uses MediaPipe exclusively.

**Multi-frame aggregation:** `detect_face_center_multi` samples `samples` (default 10) evenly-spaced timestamps, extracts frames, runs `detect_face_center` on each, then takes the median x-coordinate and median y-coordinate across all frames with a detection. This produces a stable crop position that does not jump between individual frames.

**Fallback:** If no face is detected in any sampled frame, or if MediaPipe is unavailable, the crop is centred in the frame (horizontal midpoint, vertical top-aligned to preserve the upper body).

---

### 4.15 `src/services/video_service.py`

**Purpose:** Orchestrates the full pipeline from a submitted job to finished clips. UI-agnostic — progress is reported via a plain callable so this module works with NiceGUI, tests, or any other caller.

**Key function:**
```python
async def process_video(
    request: ProcessingRequest,
    progress_callback: ProgressCallback | None = None,
) -> ProcessingResult:
    """Run full pipeline; return ProcessingResult with clip paths and metadata."""
```

**`ProcessingRequest` fields:**
- `source: str` — YouTube URL or absolute local file path
- `task_id: str` — Database Task UUID
- `min_clip_length: int` — minimum clip seconds (default 15)
- `max_clip_length: int` — maximum clip seconds (default 45)
- `output_resolution: str` — e.g. `"1080p"` (default)
- `subtitle_style: SubtitleStyle | None`
- `logo_path: Path | None`
- `custom_prompt: str | None`
- `content_mode: str` — `"single"` (default) / `"duo"` / `"multi"` — drives framing strategy

**Pipeline stages and progress checkpoints:**

| Stage | Progress % | Message |
|---|---|---|
| Preparing | 0 | "Preparing..." |
| Download (YouTube URL only) | 10 | "Downloading video..." |
| Transcribe | 20 | "Transcribing..." |
| Analyse | 40 | "Analyzing transcript..." |
| Generate clips (updated per clip) | 50–100 | "Generating clips..." / "Generated clip N/M" |
| Complete | 100 | "Complete" |

**Optional pipeline stages** (called between Analyse and Generate, both are no-ops when disabled):
- `_rerank_by_engagement(source_video, segments)` — VLM engagement re-ranking; skipped when `vlm_rerank_enabled=False` (default)
- `_apply_quality_filters(source_video, segments)` — dark-segment filter + scene-start snapping; skipped when both `quality_dark_filter_enabled` and `scene_snap_enabled` are `False` (defaults)

**Per-clip extras** (both called inside `_generate_clips_concurrently`):
- `_resolve_active_speaker_side(source_video, start_s, end_s, content_mode)` — VLM active-speaker detection for `duo`/`multi` content; no-op for `single`
- `_generate_thumbnail(source_video, segment, clip_path, clips_dir)` — writes `{clip_stem}.jpg` alongside the clip; persisted to `GeneratedClip.thumbnail_filename`

**Concurrency:** Clip rendering uses `asyncio.TaskGroup` bounded by an `asyncio.Semaphore(max_workers)` so no more than `config.max_workers` ffmpeg subprocesses run at once.

**Task status values:** `'pending'` → `'processing'` → `'completed'` (or `'failed'`). Errors are written to `Task.error_message` (not embedded in `settings_json`).

---

### 4.16 `src/pipeline/vision.py`

**Purpose:** VLM (Vision Language Model) multimodal orchestration. Provides active-speaker detection, engagement scoring, thumbnail selection, and frame extraction utilities. All entry points degrade gracefully to `None`/midpoint when the VLM is disabled (`vlm_enabled=False`, the default).

**Determinism boundary:** Pure helpers (frame sampling, base64 encoding, JSON parsing, score fusion, thumbnail writing) are deterministic and gate-tested without any VLM. The VLM HTTP call is isolated in `_vlm_chat(frames_b64, prompt, cfg)` which is the sole e2e seam.

**Public entry points (all call `asyncio.to_thread` internally when used in the pipeline):**
```python
def detect_active_speaker(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    config=None,
) -> ActiveSpeaker | None:
    """Return side ('left'/'right'/'center') + confidence, or None when VLM off."""

def score_engagement(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    config=None,
) -> float | None:
    """Return a 0.0–1.0 engagement score from the VLM, or None."""

def select_best_frame_timestamp(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    config=None,
) -> float:
    """Return the VLM-selected best frame timestamp; falls back to segment midpoint."""
```

**`ActiveSpeaker` dataclass:** `side: str`, `confidence: float`

**Pure helpers (gate-tested):**
- `sample_timestamps(start_s, end_s, samples) -> list[float]` — evenly-spaced timestamps
- `extract_frame_b64(video_path, timestamp_s, max_dim) -> str | None` — ffmpeg → JPEG → base64
- `extract_json(content: str) -> dict | None` — handles reasoning VLMs (finds the LAST JSON object)
- `parse_active_speaker(content) -> ActiveSpeaker | None`
- `parse_engagement(content) -> float | None`
- `fuse_scores(transcript_score, engagement, transcript_weight, visual_weight) -> float`
- `parse_frame_index(content, count) -> int | None`
- `write_thumbnail(video_path, timestamp_s, dest, max_dim) -> Path | None`
- `build_vlm_payload(frames_b64, prompt, cfg) -> dict` — constructs OpenAI-compatible vision chat-completion payload with `data:image/jpeg;base64,{f}` image_url parts

**VLM configuration:** The VLM model, endpoint, and API key are separate from the text-analysis LLM. `config.get_vlm_base_url()` and `config.get_vlm_api_key()` fall back to the local LLM values when no VLM-specific values are set. See §8.5 for the full VLM config group.

---

### 4.17 `src/pipeline/quality.py`

**Purpose:** Deterministic visual-quality utilities using ffmpeg and Pillow only — no VLM. Implements cheap, gate-testable quality gates over sampled frames.

**Key functions:**
```python
def detect_scene_timestamps(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    threshold: float,
) -> list[float]:
    """Return absolute timestamps of visual scene cuts within [start_s, end_s].
    Uses ffmpeg select='gt(scene,...)' + showinfo, parses pts_time from stderr."""

def snap_start_to_scene(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    threshold: float,
    window_s: float,
) -> float:
    """Snap clip start back to the nearest scene cut within window_s; returns start_s unchanged if none found."""

def frame_brightness(
    video_path: str | Path,
    timestamp_s: float,
    max_dim: int,
) -> float | None:
    """Return mean luma (0–255) of one frame via Pillow, or None on failure."""

def segment_mean_brightness(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int,
    max_dim: int,
) -> float | None:
    """Return mean brightness across sampled frames of a segment."""

def is_segment_too_dark(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int,
    max_dim: int,
    min_brightness: float,
) -> bool:
    """Return True when segment mean luma is below min_brightness. Fail-open: unreadable frames → not too dark."""
```

**Design note:** `quality.py` imports `extract_frame_b64` and `sample_timestamps` from `src.pipeline.vision` (the deterministic pure helpers, not the VLM entry points). All features are off by default — see §8.6 for the quality config group.

---

### 4.18 `src/pages/_util.py`

**Purpose:** Shared utilities used across multiple NiceGUI page modules.

**Functions:**
```python
def truncate(text: str, max_len: int, *, reserve_ellipsis: bool = False) -> str:
    """Truncate text to max_len characters; optionally append '...'."""

def remove_clip_files(filenames: Iterable[str]) -> None:
    """Best-effort removal of clip files from {config.temp_dir}/clips/.
    Logs warnings on individual failures; never raises."""
```

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
  │     progress: 0% → 10%
  │
  ├─► pipeline/transcribe.py
  │     parakeet-mlx transcribes → TranscriptData (words + timestamps)
  │     cache written to temp/{task_id}/source.mp4.transcript_cache.json
  │     progress: 10% → 20%
  │
  ├─► pipeline/analyze.py
  │     LLM reads transcript → list[TranscriptSegment] (3–7 segments)
  │     progress: 20% → 40%
  │
  └─► For each TranscriptSegment (parallel via TaskGroup):
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
              progress: 50% → 100% (increments per clip)

Task status set to "completed"; progress: 100%
NiceGUI page updates via WebSocket push
```

### 5.2 File Upload Input

Same as 5.1, except the `download.py` stage is skipped. The uploaded file is saved to `temp/{task_id}/source.mp4` by the NiceGUI upload handler before `process_video` is called.

### 5.3 Error Handling in the Pipeline

Any exception raised in a pipeline stage is caught in `video_service.py`. The task status is set to `"failed"` and the error message is stored in `Task.error_message` (a dedicated nullable Text column, not embedded in `settings_json`). The exception is logged at ERROR level with `exc_info=True` by structlog. `process_video` returns a `ProcessingResult` with `error` set rather than re-raising, so the caller always receives a structured result.

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
| Clip length range | Two `ui.number` inputs | Min and max seconds; default 15–45 (from `DEFAULT_MIN_CLIP_LENGTH` / `DEFAULT_MAX_CLIP_LENGTH`) |
| Target clip count | `ui.number` | Default 7 (from `MAX_CLIPS`); range 1–`MAX_CLIPS` |
| Output resolution | `ui.select` | Options: `720p`, `1080p`; default `1080p` |
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
| Status badge | `ui.badge` | Colour-coded: grey (pending), blue (processing), green (completed), red (failed) |
| Progress bar | `ui.linear_progress` | Value 0.0–1.0; updated via WebSocket |
| Progress message | `ui.label` | e.g., "Rendering clip 2 of 5..." |
| Clip grid | `ui.grid` | Rendered after status = "completed" |
| Per-clip card | `ui.card` | Contains video player, title, timestamps, download button |
| Video player | `ui.video` | Served from `/clips/{filename}` static route |
| Download button | `ui.button` | Links to `/clips/{filename}` with `Content-Disposition: attachment` |
| Back button | `ui.button` | Returns to `/` |

**Real-time updates:**
The `progress_callback` passed to `video_service.process_video` calls `ui.update()` on the progress bar and message label. NiceGUI pushes the DOM mutation to the browser via WebSocket. No polling.

**Error state:**
If `task.status == "failed"`, show the error message from `task.error_message` in a red alert card.

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
| Stroke colour | `ui.color_input` | `UserPreferences.font_stroke_color` |
| Stroke width | `ui.number` | `UserPreferences.font_stroke_width` |
| Shadow offset | `ui.number` | `UserPreferences.font_shadow_offset` |
| Subtitle vertical position | `ui.slider` | `UserPreferences.subtitle_position_y` (0–100 % from top; default 75) |
| Min clip length | `ui.number` | `UserPreferences.min_clip_length` |
| Max clip length | `ui.number` | `UserPreferences.max_clip_length` |
| Custom AI prompt | `ui.textarea` | `UserPreferences.ai_prompt`; empty = use default |
| Logo upload | `ui.upload` | Saves file path; `UserPreferences.logo_path` |
| Output resolution | `ui.select` | Options: `720p` (720×1280), `1080p` (1080×1920); default `1080p` |
| Save button | `ui.button` | Upserts the singleton `UserPreferences` row |

---

## 7. Data Model

The new schema has three tables. All IDs are UUID v4 strings stored as `VARCHAR(36)`. Timestamps use `DATETIME` with UTC timezone.

### 7.1 `tasks`

Represents one processing job — from video input to finished clips.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | NO | uuid4() | Primary key |
| `source_url` | TEXT | NO | — | YouTube URL or uploaded filename (NOT NULL) |
| `source_type` | VARCHAR(20) | NO | `'youtube'` | `'youtube'` or `'upload'` |
| `status` | VARCHAR(20) | NO | `'pending'` | `'pending'`, `'processing'`, `'completed'`, `'failed'` |
| `progress` | INTEGER | NO | `0` | 0–100 percent |
| `progress_message` | TEXT | YES | NULL | Current stage description shown in UI |
| `settings_json` | TEXT | YES | NULL | Snapshot of job settings at submit time |
| `error_message` | TEXT | YES | NULL | Human-readable error detail when `status = 'failed'` |
| `created_at` | DATETIME | NO | now() | |
| `updated_at` | DATETIME | NO | now() | Auto-updated on row change |

**Constraints:**
- `status IN ('pending', 'processing', 'completed', 'failed')`
- `source_type IN ('youtube', 'upload')`

**Note:** Task failure is recorded in `error_message`, not as a key inside `settings_json`.

### 7.2 `generated_clips`

One row per output clip file.

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | VARCHAR(36) | NO | uuid4() | Primary key |
| `task_id` | VARCHAR(36) | NO | — | FK → `tasks.id` ON DELETE CASCADE |
| `filename` | VARCHAR(255) | NO | — | Output MP4 filename (no path; served from `/clips/`) |
| `start_time` | FLOAT | NO | — | Start offset in source video, **seconds** |
| `end_time` | FLOAT | NO | — | End offset in source video, **seconds** |
| `duration` | FLOAT | NO | — | Computed `end_time − start_time` in seconds |
| `title` | TEXT | YES | NULL | AI-generated clip title |
| `transcript_text` | TEXT | YES | NULL | Verbatim transcript for this segment |
| `score` | FLOAT | YES | NULL | AI relevance score 0.0–1.0 (nullable) |
| `thumbnail_filename` | VARCHAR(255) | YES | NULL | JPEG thumbnail filename served from `/clips/` |
| `created_at` | DATETIME | NO | now() | |

**Note:** `start_time` and `end_time` are stored as seconds (Float), not formatted strings. There is no `reasoning`, `clip_order`, or `updated_at` column in this table.

### 7.3 `user_preferences`

Singleton table — always exactly one row (created on first app start).

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | INTEGER | NO | 1 | Fixed primary key; always 1 |
| `font_family` | VARCHAR(100) | NO | `'Arial'` | Font internal family name (must match TTF in `fonts/`) |
| `font_size` | INTEGER | NO | `24` | Points |
| `font_color` | VARCHAR(7) | NO | `'#FFFFFF'` | Subtitle text colour `#RRGGBB` |
| `font_stroke_color` | VARCHAR(7) | NO | `'#000000'` | Subtitle stroke (outline) colour `#RRGGBB` |
| `font_stroke_width` | FLOAT | NO | `2.0` | Stroke width in ASS units |
| `font_shadow_offset` | INTEGER | NO | `1` | Drop-shadow offset in pixels |
| `subtitle_position_y` | INTEGER | NO | `75` | Vertical position as % from top (75 = lower-middle) |
| `min_clip_length` | INTEGER | NO | `15` | Minimum clip duration in seconds |
| `max_clip_length` | INTEGER | NO | `45` | Maximum clip duration in seconds |
| `output_resolution` | VARCHAR(10) | NO | `'1080p'` | `'720p'` or `'1080p'` |
| `ai_prompt` | TEXT | YES | NULL | Custom system prompt override; NULL = use default |
| `logo_path` | TEXT | YES | NULL | Absolute path to logo image file |
| `updated_at` | DATETIME | NO | now() | Auto-updated on row change |

**Constraints:**
- `output_resolution IN ('720p', '1080p')`

**Note:** There is no `clip_target_s`, `target_clip_count`, `custom_ai_prompt`, or `logo_position` column. Logo position is not persisted; logos are always placed at the top-right corner (see §10.5).

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

LLM selection priority: local (if `LOCAL_LLM_ENABLED=true`) → cloud (if `LLM_MODEL` + matching API key set) → raise `ConfigurationError`.

### 8.2 Transcription Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `PARAKEET_MODEL` | str | `mlx-community/parakeet-tdt-0.6b-v2` | HuggingFace model ID for parakeet-mlx |

### 8.3 Video Processing Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `TEMP_DIR` | str | `./temp` | Root directory for downloads, clip output, uploads |
| `MAX_VIDEO_DURATION` | int | `0` | Seconds; `0` = no limit; reject downloads longer than this when > 0 |
| `MAX_CLIPS` | int | `7` | Hard ceiling on clips per task |
| `FFMPEG_PRESET` | str | `fast` | libx264 preset: `ultrafast`, `fast`, `medium`, `slow` |
| `FFMPEG_CRF` | int | `23` | libx264 CRF quality; lower = better quality + larger file |
| `DEFAULT_MIN_CLIP_LENGTH` | int | `15` | Default minimum clip duration in seconds |
| `DEFAULT_MAX_CLIP_LENGTH` | int | `45` | Default maximum clip duration in seconds |

### 8.4 Application Configuration

| Env Var | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | str | `sqlite+aiosqlite:///./supoclip.db` | SQLAlchemy connection string |
| `HOST` | str | `0.0.0.0` | Bind address for uvicorn |
| `MAX_WORKERS` | int | `2` | Parallel clip rendering tasks |
| `LOG_LEVEL` | str | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_DIR` | Path | `./logs` | Directory for structlog file output |

### 8.5 Vision / VLM Configuration

The VLM (Vision Language Model) is a separate model from the text-analysis LLM and is **off by default**. All VLM features degrade gracefully to `None`/no-op when disabled.

| Env Var | Type | Default | Description |
|---|---|---|---|
| `CONTENT_MODE` | str | `single` | `single`/`duo`/`multi`; drives framing/speaker-detection strategy |
| `VLM_ENABLED` | bool | `false` | Enable VLM calls (active speaker, engagement scoring, thumbnail selection) |
| `VLM_MODEL` | str | `""` | VLM model identifier; empty = use local LLM model |
| `VLM_BASE_URL` | str | `""` | VLM endpoint; empty = fall back to `LOCAL_LLM_BASE_URL` |
| `VLM_API_KEY` | str | `""` | VLM API key; empty = fall back to `LOCAL_LLM_API_KEY` |
| `VLM_MAX_TOKENS` | int | `1024` | Max output tokens; raise for reasoning VLMs (e.g. Qwen) |
| `VLM_FRAMES_PER_CLIP` | int | `5` | Frames sampled per clip for VLM analysis |
| `VLM_IMAGE_MAX_DIM` | int | `768` | Maximum JPEG dimension sent to VLM |
| `VLM_TIMEOUT_S` | float | `180.0` | HTTP timeout for each VLM call |
| `VLM_RERANK_ENABLED` | bool | `false` | Re-order segments by transcript+visual fused score |
| `VLM_TRANSCRIPT_WEIGHT` | float | `0.7` | Weight of transcript relevance in fused score |
| `VLM_VISUAL_WEIGHT` | float | `0.3` | Weight of VLM engagement score in fused score |

**Endpoint fallback:** `Config.get_vlm_base_url()` returns `VLM_BASE_URL` when set, otherwise `LOCAL_LLM_BASE_URL`. `Config.get_vlm_api_key()` behaves identically for the API key. This lets a single local server serve both the text LLM and the VLM without separate configuration.

### 8.6 Quality Configuration

Deterministic ffmpeg/Pillow quality utilities. All features are **off by default**; enabling them adds no VLM cost.

| Env Var | Type | Default | Description |
|---|---|---|---|
| `QUALITY_PROBE_DIM` | int | `320` | Frame width for brightness probing (smaller = faster) |
| `QUALITY_DARK_FILTER_ENABLED` | bool | `false` | Drop segments whose mean luma is below the floor |
| `QUALITY_MIN_BRIGHTNESS` | float | `16.0` | Minimum mean luma (0–255); segments below this are dropped |
| `QUALITY_BRIGHTNESS_SAMPLES` | int | `3` | Frames sampled per segment for brightness measurement |
| `SCENE_SNAP_ENABLED` | bool | `false` | Snap clip start to nearest scene cut |
| `SCENE_THRESHOLD` | float | `0.4` | Scene-change sensitivity (0–1; higher = fewer cuts detected) |
| `SCENE_SNAP_WINDOW_S` | float | `2.0` | How far before the proposed start to look for a cut |

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
| `720p` | 720 | 1280 | 9:16 |
| `1080p` | 1080 | 1920 | 9:16 |

Default resolution is `1080p`. These are portrait (vertical) dimensions suited for TikTok/Reels/Shorts.

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

Example for 1080p output with a 1920×1080 source:
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

These are merged into `src/pipeline/analyze.py` (~250 lines). There is one system prompt, one validation pipeline, and one public entry point (`analyze_transcript`). Routing to Groq structured outputs vs. Pydantic AI is done by inspecting the model string in config.

### 11.2 System Prompt

The system prompt instructs the LLM to:

1. Identify 3–7 segments that would be compelling as standalone short-form content
2. Apply the **Clean Start Rule**: never begin a clip with a filler or transitional word ("And", "But", "So", "Well", "Um", "Uh", "Like", "You know"). If the natural segment start is a weak word, adjust forward to the first strong word.
3. Return timestamps in `MM:SS.mmm` format with millisecond precision, matching the transcript's word timing
4. Return the verbatim transcript text for each segment (no paraphrasing)
5. Provide a title for each selection (a `reasoning` field is accepted but not propagated to `TranscriptSegment`)

The system prompt is built by `build_system_prompt(min_length_s, max_length_s, custom_prompt)`. If `UserPreferences.ai_prompt` is non-null, it is passed as `custom_prompt` and appended to the standard prompt as an additional instruction block.

### 11.3 Output Schema

The LLM returns a JSON object with `most_relevant_segments` matching `_RawAnalysis` / `_RawSegment` (internal models). Each raw segment uses string timestamps in `MM:SS.mmm` format. These are parsed by `_raw_segments_to_transcript_segments()` into the public `TranscriptSegment` Pydantic model:

```python
class TranscriptSegment(BaseModel):
    """A selected clip segment from the AI analysis."""
    model_config = ConfigDict(strict=True, extra="forbid")

    start_time: float   # seconds (parsed from MM:SS.mmm)
    end_time: float     # seconds (parsed from MM:SS.mmm)
    text: str           # verbatim transcript text
    score: float        # relevance score 0.0–1.0, default 0.8
    title: str          # suggested clip title, default ""
```

`validate_segments()` enforces:
- `end_time > start_time` (duration > 0)
- Duration >= `min_length_s`
- Duration <= `max_length_s`
- `start_time` / `end_time` within transcript time bound (hallucination guard)
- Text does not start with a filler/transitional word

Segments failing validation are logged and dropped. If no valid segments remain, `analyze_transcript` raises `InsufficientSegmentsError`.

### 11.4 Model Routing

`_should_use_structured_output(model_string)` returns `True` when the model string contains both `"groq:"` and `"llama"`. On that path, `_analyze_with_groq_structured` calls the Groq API directly with `response_format={"type": "json_schema", ...}` using the `_RawAnalysis.model_json_schema()`. On all other paths (local LLM, OpenAI, Anthropic), `_analyze_with_pydantic_ai` builds a Pydantic AI `Agent` with `output_type=_RawAnalysis`:

```python
agent: Agent[None, _RawAnalysis] = Agent(
    model=llm_model,
    output_type=_RawAnalysis,
    system_prompt=system_prompt,
)
```

When `LOCAL_LLM_ENABLED=true`, `llm_model` is an `OpenAIModel` pointing at `local_llm_base_url` with `local_llm_api_key`. For cloud models, `cfg.get_llm_model()` returns the configured pydantic-ai model string.

### 11.5 Retry and Validation

Both `_analyze_with_groq_structured` and `_analyze_with_pydantic_ai` are decorated with:

```python
@stamina.retry(on=Exception, attempts=3, wait_initial=2.0, wait_max=10.0)
```

`stamina` provides exponential backoff retries. After each backend call, `validate_segments()` filters the results. If all segments are rejected (e.g., all timestamps are identical or hallucinated), `analyze_transcript` raises `InsufficientSegmentsError` — the backend is not retried a second time for validation failures; the retry is at the HTTP call level only.

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

- `src/exceptions.py` defines the full hierarchy:
  - `SupoClipError` (base)
    - `DownloadError`
    - `TranscriptionError`
    - `AnalysisError`
      - `InsufficientSegmentsError`
    - `ClipGenerationError`
    - `ConfigurationError`
- Raise the most specific exception at the point of failure.
- Catch broad exceptions only at the pipeline orchestration level (`video_service.py`), log the full traceback with structlog, and set task status to `"completed"` or `"failed"` accordingly.
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
    raise ClipGenerationError(f"ffmpeg exited {proc.returncode}")
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

719 tests total (confirmed by `uv run pytest tests/unit tests/integration --collect-only -q`).

```
tests/
├── unit/                         # Pytest-collected; all I/O mocked
│   ├── test_analyze.py
│   ├── test_clip.py
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_download.py
│   ├── test_face_detect.py
│   ├── test_history.py
│   ├── test_home.py
│   ├── test_main.py
│   ├── test_models.py
│   ├── test_pages_util.py
│   ├── test_quality.py
│   ├── test_settings.py
│   ├── test_subtitles.py
│   ├── test_task_page.py
│   ├── test_transcribe.py
│   ├── test_video_service.py
│   └── test_vision.py
├── integration/                  # Pytest-collected; uses real ffmpeg
│   ├── test_clips_route.py
│   ├── test_pipeline_e2e.py
│   ├── test_pipeline_failures.py
│   ├── test_pipeline_real_output.py
│   ├── test_settings_persistence.py
│   └── test_settings_pipeline_wiring.py
└── e2e/                          # NOT pytest-collected; manual smoke tests
    ├── smoke_pipeline.py
    ├── vision_features.py
    └── vision_spike.py
```

**e2e tests** are standalone scripts in `tests/e2e/` that are explicitly excluded from the pytest collection. They require a running local LLM and/or VLM and produce real output files. They are not included in the coverage gate.

### 13.3 Unit Testing Guidelines

**Config (`test_config.py`):**
- Test that each env var overrides the default
- Test `get_llm_model()` returns correct model type for each combination of `LOCAL_LLM_ENABLED` + cloud keys
- Test `get_llm_model()` raises `ValueError` when nothing is configured

**Models (`test_models.py`):**
- Test all Pydantic model validations (strict mode rejects coercion; `extra="forbid"` rejects unknown fields)
- Test `TranscriptSegment` validation rejects equal start/end times
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
| pyright | `pyright src/` | Zero type errors |
| bandit | `bandit -r src/` | Zero high-severity issues |
| radon | `radon cc src/ -n C` | No function grades C or below |
| xenon | `xenon src/ --max-absolute B --max-modules B --max-average A` | Complexity within bounds |
| deptry | `deptry src/` | Zero unused/missing deps |
| grimp | import-cycle check | Zero import cycles |
| pytest | `pytest tests/unit tests/integration --cov=src --cov-branch --cov-fail-under=100` | 100% line+branch coverage, 100% passing |

**Note:** `checkpython.sh` is a protected file — never modify it. The exact flags used by each tool are authoritative as written in `checkpython.sh`.

---

## 14. Vision-Aware Clipping

Vision-aware clipping extends the core pipeline with optional VLM (Vision Language Model) capabilities that improve clip quality for multi-person content. All features are **off by default** and degrade cleanly to the deterministic baseline when disabled.

### 14.1 Content Modes

The `content_mode` setting (controlled by `CONTENT_MODE` env var, default `"single"`) selects the framing strategy for generated clips:

| Mode | Description | Face Detection | VLM Active Speaker |
|---|---|---|---|
| `single` | Single speaker or object-focused content | MediaPipe face crop | Not used |
| `duo` | Two speakers (e.g., podcast, interview) | Not used | VLM detects who is speaking |
| `multi` | Three or more people | Not used | VLM detects who is speaking |

For `duo`/`multi` content, the VLM examines sampled frames and returns an `ActiveSpeaker` result with a `side` (`"left"`, `"right"`, or `"center"`) and a `confidence` score. The `active_speaker_side` is passed to `ClipOptions` so the crop is offset toward the identified speaker rather than centred on the face or frame.

### 14.2 Engagement Re-Ranking

When `VLM_RERANK_ENABLED=true` (default off), the pipeline re-orders the AI-selected segments before rendering by fusing each segment's transcript relevance score with a VLM-assessed visual engagement score:

```
fused_score = transcript_weight × transcript_score + visual_weight × engagement_score
```

Default weights: `transcript_weight = 0.7`, `visual_weight = 0.3` (configurable via `VLM_TRANSCRIPT_WEIGHT`/`VLM_VISUAL_WEIGHT`). Segments are sorted by `fused_score` descending so the highest-value clip is rendered first. If the VLM call fails for a segment, that segment retains its transcript score — the VLM being unavailable never drops content.

### 14.3 Thumbnail Generation

After each clip is rendered, `_generate_thumbnail` selects the best representative frame:
- **VLM on:** `select_best_frame_timestamp` samples frames and asks the VLM to pick the clearest, most expressive frame. Falls back to the segment midpoint if the VLM call fails.
- **VLM off:** Always uses the segment midpoint.

The selected frame is encoded as a JPEG and written as `{clip_stem}.jpg` in the clips directory. The filename is stored in `GeneratedClip.thumbnail_filename` and served from `/clips/{filename}`.

### 14.4 Determinism Boundary

The vision pipeline is designed to be gate-tested without any VLM or network:

- **Deterministic (gate-tested):** `sample_timestamps`, `extract_frame_b64`, `extract_json`, `parse_active_speaker`, `parse_engagement`, `fuse_scores`, `parse_frame_index`, `write_thumbnail`, `build_vlm_payload`, and all of `src/pipeline/quality.py`.
- **VLM seam (e2e-only):** `_vlm_chat(frames_b64, prompt, cfg)` in `vision.py` is the sole HTTP call. It is monkey-patched in unit tests; exercised only in `tests/e2e/vision_features.py` against a live VLM.

This boundary means the entire vision module is 100% covered by unit tests without requiring a VLM. The e2e tests in `tests/e2e/` verify integration with real models but are not collected by the CI gate.

### 14.5 Quality Filters

`src/pipeline/quality.py` provides two deterministic ffmpeg-based quality gates applied after segment selection and re-ranking:

1. **Dark filter** (`QUALITY_DARK_FILTER_ENABLED=true`): Segments whose sampled mean luma falls below `QUALITY_MIN_BRIGHTNESS` (default 16.0) are dropped before rendering. Unreadable frames are treated as acceptable (fail-open) so the filter never silently removes content due to probe errors.

2. **Scene snap** (`SCENE_SNAP_ENABLED=true`): Each clip's start is pulled back to the nearest visual scene cut within `SCENE_SNAP_WINDOW_S` (default 2.0 s). This avoids clips that begin mid-shot. The scene-detection threshold (`SCENE_THRESHOLD`, default 0.4) controls sensitivity.

Both features are independent and can be enabled separately.

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
