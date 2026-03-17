# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SupoClip is an open-source alternative to OpusClip - an AI-powered video clipping tool that transforms long-form content into viral short clips. It is a **single all-Python application** using NiceGUI for the UI and FastAPI for the API, running in one process with no frontend build step.

There is no React, no TypeScript, no Node.js, no npm. Everything is Python.

## Architecture

### Project Structure

```
supoclip/
├── src/
│   ├── main.py              # FastAPI + NiceGUI app entry point
│   ├── config.py            # Pydantic BaseSettings
│   ├── database.py          # SQLAlchemy async + SQLite
│   ├── models.py            # Task, GeneratedClip, UserPreferences
│   ├── pages/
│   │   ├── home.py          # URL input, file upload, start
│   │   ├── task.py          # Progress, clip viewer, download
│   │   ├── history.py       # Task list
│   │   └── settings.py      # Font, preferences
│   ├── pipeline/
│   │   ├── download.py      # yt-dlp YouTube downloads
│   │   ├── transcribe.py    # parakeet-mlx transcription
│   │   ├── analyze.py       # Pydantic AI (unified LLM analysis)
│   │   ├── clip.py          # ffmpeg video operations
│   │   ├── subtitles.py     # pysubs2 ASS subtitle generation
│   │   └── face_detect.py   # MediaPipe face detection
│   └── services/
│       └── video_service.py # Pipeline orchestration
├── fonts/                   # Custom TTF font files
├── transitions/             # Transition effect videos (.mp4)
├── tests/
├── docs/
│   ├── prd.md               # Product requirements
│   ├── spec.md              # Technical specification
│   └── rules-python.md      # Python coding standards
├── pyproject.toml
├── checkpython.sh           # Automated quality gate (never modify)
└── .pre-commit-config.yaml
```

### Technology Stack

**Python only. No JavaScript, TypeScript, or Node.js.**

Core:
- FastAPI + NiceGUI (UI and API in one process, one event loop)
- SQLAlchemy + aiosqlite (async SQLite)
- Pydantic + pydantic-settings (models and configuration)
- structlog (structured logging)

Pipeline:
- parakeet-mlx (offline transcription, Apple Silicon, word-level timing)
- pydantic-ai (LLM analysis and structured outputs)
- yt-dlp (YouTube download)
- mediapipe (face detection only; no OpenCV DNN fallbacks)
- pysubs2 (ASS subtitle generation)
- ffmpeg (all video operations via subprocess; no MoviePy)
- Pillow (image processing)

Package manager: `uv` (not pip, not poetry)

Database:
- SQLite with 3 tables: Task, GeneratedClip, UserPreferences
- All snake_case field names
- Created automatically on startup via SQLAlchemy

## Development Commands

### Prerequisites

- Python 3.11+
- ffmpeg installed (`brew install ffmpeg` on macOS)
- `uv` package manager (`brew install uv` on macOS)

### Running the Application

```bash
# Install dependencies
uv sync

# Run the application
python -m src.main
```

The app runs at **http://localhost:8008** (UI + API in one process).
API docs (Swagger) are available at http://localhost:8008/docs.

There is no separate frontend server. There are no npm commands.

### Testing

```bash
uv run pytest tests/
```

### Quality Gate

```bash
./checkpython.sh
```

This must report zero errors and 100% passing tests before any commit.

### Environment Variables (.env file at project root)

**Local LLM (Default - No API Key Required):**
```
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:6969/v1
LOCAL_LLM_MODEL=local-model
```

**Cloud LLM (Optional):**
```
LLM_MODEL=groq:meta-llama/llama-4-scout-17b-16e-instruct
GROQ_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
ANTHROPIC_API_KEY=...
```

**Storage:**
```
DATABASE_URL=sqlite+aiosqlite:///./supoclip.db
TEMP_DIR=./temp
```

## Key Architecture Patterns

### NiceGUI Pages

The UI lives in `src/pages/`. NiceGUI IS FastAPI - same process, same event loop. Pages use the `@ui.page` decorator. Real-time progress feedback is delivered via WebSocket: the backend pushes updates directly to the UI without polling.

Each page file registers its own route. `src/main.py` imports them to trigger registration.

### Video Processing Pipeline

1. **Video Input** - YouTube URL (yt-dlp) or uploaded file
2. **Transcription** - parakeet-mlx generates word-level timestamps (offline, Apple Silicon)
3. **AI Analysis** - `src/pipeline/analyze.py` selects 3-7 viral segments (10-45s each)
4. **Clip Generation** - Single ffmpeg subprocess per clip: trim, crop to 9:16, burn subtitles, encode H.264
5. **Storage** - Clips saved to `{TEMP_DIR}/clips/`, metadata in SQLite

### ffmpeg Pipeline

All video operations happen in single ffmpeg subprocess calls. There is no MoviePy. The clip pipeline in `src/pipeline/clip.py` constructs an ffmpeg filtergraph that handles:
- Trim to segment timestamps
- Smart crop to 9:16 (face-centered or center fallback)
- Subtitle burn-in via `-vf "ass=file.ass:fontsdir=fonts/"`
- H.264 encoding with even dimensions

### Subtitle System

`src/pipeline/subtitles.py` uses pysubs2 to generate `.ass` (Advanced SubStation Alpha) files with per-word timing from the parakeet-mlx transcript. ffmpeg burns them into the video via the `ass` filter with `fontsdir=fonts/` pointing at the project fonts directory.

Custom TTF fonts (including Google Fonts) are supported by dropping `.ttf` files into `fonts/`. The font name in the `.ass` file must match the font's internal family name.

Subtitles are positioned at 75% down the video (lower-middle, not bottom).

### AI Analysis

`src/pipeline/analyze.py` is the single unified AI module. It routes to Groq structured outputs or Pydantic AI based on the `LLM_MODEL` string prefix. There is no separate `ai_structured.py`.

The AI selects segments based on:
- Strong hooks and attention-grabbing moments
- Valuable content (tips, insights, stories)
- Emotional moments (excitement, humor, inspiration)
- Complete thoughts that stand alone
- Duration: 10-45 seconds per clip
- Validation: start_time != end_time, minimum 5-10s duration

To modify clip selection criteria, edit `src/pipeline/analyze.py`:
- System prompt string
- `TranscriptSegment` Pydantic model
- Validation logic in the analysis function

### Face Detection

`src/pipeline/face_detect.py` uses MediaPipe only. If no face is detected, the pipeline falls back to center crop. There are no OpenCV DNN or Haar cascade fallbacks.

### Database Access

- SQLAlchemy async models in `src/models.py`
- Async sessions via `AsyncSessionLocal` context manager in `src/database.py`
- No database access outside the database module
- Schema created on startup; no migrations needed for local development

### Pipeline Orchestration

`src/services/video_service.py` owns the end-to-end pipeline. It calls each `src/pipeline/` module in sequence and pushes progress updates via NiceGUI's WebSocket mechanism. The FastAPI lifespan in `src/main.py` is kept orchestration-focused; core logic lives in services and pipeline modules.

## Code Organization

### Source Files

- `src/main.py` - FastAPI + NiceGUI app, lifespan management, page registration
- `src/config.py` - Pydantic BaseSettings, all configuration loaded from .env
- `src/database.py` - SQLAlchemy engine, session factory, startup schema creation
- `src/models.py` - SQLAlchemy ORM models: Task, GeneratedClip, UserPreferences
- `src/pages/home.py` - Home page: URL input, file upload, processing start
- `src/pages/task.py` - Task page: real-time progress, clip viewer, download
- `src/pages/history.py` - History page: task list with status
- `src/pages/settings.py` - Settings page: font selection, preferences
- `src/pipeline/download.py` - yt-dlp wrapper for YouTube downloads
- `src/pipeline/transcribe.py` - parakeet-mlx transcription, transcript cache
- `src/pipeline/analyze.py` - Unified LLM analysis, segment selection, validation
- `src/pipeline/clip.py` - ffmpeg clip generation, filtergraph construction
- `src/pipeline/subtitles.py` - pysubs2 ASS file generation with word timing
- `src/pipeline/face_detect.py` - MediaPipe face detection, crop box calculation
- `src/services/video_service.py` - Pipeline orchestration, progress reporting

### File Conventions

- All source files must begin with a file path comment: `# start src/example/file.py`
- Absolute imports from project root only (no relative imports)
- `python -m src.main` is the standard invocation

### File Storage

- Uploaded videos: `{TEMP_DIR}/uploads/`
- Downloaded videos: `{TEMP_DIR}/` (via yt-dlp)
- Generated clips: `{TEMP_DIR}/clips/`
- Transcript cache: `.transcript_cache.json` alongside the source video
- Clips served via FastAPI static files at `/clips/{filename}`

## Configuration Management

**CORE RULE:** Configuration must be externalized and validated.

- All settings defined in `src/config.py` using Pydantic `BaseSettings`
- Values loaded from `.env` at startup
- No hardcoded secrets, URLs, or magic numbers in source code
- Sensitive credentials stay in `.env` (which is gitignored)
- See `docs/spec.md` for full configuration reference

## Logging

This project uses structlog for structured logging. Log level is configurable via environment variable. Do not use emoji-based logging patterns from the old codebase. Do not use the Python `logging` module directly; use structlog.

## Common Workflows

### Running the App

```bash
uv sync
python -m src.main
# Open http://localhost:8008
```

### Adding a New Font

1. Drop a `.ttf` file into `fonts/`
2. The font is immediately available in the Settings page font selector
3. ffmpeg uses `fontsdir=fonts/` so the font name must match its internal family name
4. To find a font's internal name: `fc-query fonts/MyFont.ttf | grep family`

### Adding Transition Effects

1. Add a `.mp4` file to `transitions/`
2. The transition is picked up automatically by the clip assembly pipeline
3. Transitions are applied in round-robin fashion across generated clips

### Modifying AI Clip Selection

Edit `src/pipeline/analyze.py`:
- System prompt string - criteria for what makes a good clip
- `TranscriptSegment` Pydantic model - fields returned by the LLM
- Validation logic - minimum duration, start != end guards

### Configuring the LLM

Set `LLM_MODEL` in `.env`. The string prefix determines the provider:

```
# Local (default, no API key)
LOCAL_LLM_ENABLED=true

# Groq (fast, cheap)
LLM_MODEL=groq:meta-llama/llama-4-scout-17b-16e-instruct
GROQ_API_KEY=gsk_...

# OpenAI
LLM_MODEL=openai:gpt-4o
OPENAI_API_KEY=sk-...

# Anthropic
LLM_MODEL=anthropic:claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

## Development Standards and Best Practices

Full coding standards are documented in `docs/rules-python.md`. The summary below covers the most critical rules.

### Python 3.11+ Requirements

- Type hints required on all functions and class methods
- PEP 8 compliance via Ruff
- Google-style docstrings (PEP 257)
- Python 3.11+ features: structural pattern matching (`match-case`), exception groups (`except*`)
- Asyncio best practices: `TaskGroup`, explicit timeouts, proper exception handling
- `@dataclass(slots=True)` for memory-efficient data structures

**Anti-Patterns to Avoid:**
- Mutable defaults in function signatures
- Bare `except` clauses
- Circular imports
- Global variable overuse
- Hardcoded secrets or magic numbers
- Deeply nested logic (maximum 2 levels)

### Code Quality Principles

- DRY (Don't Repeat Yourself)
- SPOT (Single Point of Truth)
- SOLID principles
- YAGNI (You Aren't Gonna Need It)
- Functions must have a single responsibility
- Maximum radon/xenon complexity grade of A or B; C and below must be refactored
- Prefer explicit over implicit behavior

### Testing Requirements

- Use pytest for all unit tests
- Tests must cover: Pydantic model validation, database logic, pipeline logic, configuration loading
- Update tests whenever code changes
- 100% passing tests required before commit
- Run `./checkpython.sh` before every commit

### Quality Gate Tools

`./checkpython.sh` runs:
- Ruff (linting and formatting)
- mypy (type checking)
- pyright (type checking)
- Bandit (security scanning)
- radon/xenon (complexity)
- grimp (import graph)
- pytest (tests)

### External HTTP Requests

- Use HTTPX for all external API calls (sync and async)
- Strict timeouts required on all requests
- No bare `requests` calls

### Project-Specific Configuration

| Standard | This Project | Notes |
|----------|--------------|-------|
| Dependency manager | `uv` | Faster than pip/poetry |
| Configuration | `.env` + Pydantic BaseSettings | Validated at startup |
| Database | SQLite | Local file, no server needed |
| UI framework | NiceGUI | Python-native, same process as API |
| Video processing | ffmpeg subprocess | No MoviePy |
| Logging | structlog | Structured, not emoji-based |

## Development Tips

- API docs (Swagger UI): http://localhost:8008/docs
- SQLite database created automatically on first run at `./supoclip.db`
- Transcript results are cached as `.transcript_cache.json` next to the video file; delete this file to force re-transcription
- NiceGUI dev mode provides hot reload; pass `reload=True` to `ui.run()` during development

---

# DEBUGGING STANDARDS: THE VUW

## How to Debug: "Verifiable Units of Work"

We will no longer provide large, multi-step "plans." Instead, we will provide a sequence of small, isolated **"Verifiable Units of Work" (VUWs)**. Each VUW is a micro-plan for a single, contained task to break work down into small, bite-sized chunks.

The core principles of this approach are:

1. **Extreme Granularity:** Each VUW targets a single file or a single, specific error across a few files. This minimizes cognitive load and prevents the "tunnel-vision" refactoring problem. No VUW should ever have a diff longer than a single function or class.
2. **Verification is the Definition of "Done":** Every VUW has a mandatory, non-negotiable **Verification Checklist**. The task is not complete until that checklist passes.
3. **Sequential, Not Parallel:** One VUW at a time. The next VUW cannot start until the previous one passes the QA check.
4. **Repetition Builds Discipline:** The constant repetition of the Verification Checklist builds the muscle memory of a disciplined workflow.
5. **Clarity over Conciseness:** Instructions are painfully literal. If an import is needed, the plan states, "Add this exact import statement to the top of the file." Changes are shown as git diffs.

---

### The Structure of a "Verifiable Unit of Work" (VUW)

Every work plan follows this exact template:

---
**VUW_ID:** [A unique identifier, e.g., `BUGFIX-001`]

**Objective:** [A one-sentence explanation of *why* this task is important.]
- *Example: "To fix the fatal `ModuleNotFoundError` that prevents the application from starting."*

**Files to Modify:**
- `[List of file paths]`

**Mandatory Pre-Work Checkpoint:**

Use git to make a checkpoint before making ANY changes. This is for backup and rollback and must not be skipped. If you cannot make a checkpoint, stop.

**Step-by-Step Instructions:**

1. **[Literal instruction 1]**: *Example: "Open the file `src/pipeline/clip.py`."*
2. **[Literal instruction 2]**: *Example: "Find the line: `import pdfplumber.errors`."*
3. **[Literal instruction 3]**: *Example: "Delete that line and replace it with: `from pdfplumber.exceptions import PDFSyntaxError`."*
4. **[Literal instruction 4]**: Show as a git diff exactly.

**Mandatory Verification Checklist:**

You are not done until these commands succeed. Check the box only when the command passes.

- `[ ]` **Run `./checkpython.sh`**: Must report **zero errors** and **100% passing tests**.

**Self-Attestation:**

- `[ ]` I attest that I have run `./checkpython.sh` and all tests have passed.

**Mandatory Post-Work Checkpoint:**

Use git to make a checkpoint after the VUW passes all tests. This is for backup and rollback and must not be skipped. If you cannot make a checkpoint, stop.

---

### The Grand Strategy: Sequencing the VUWs

Organize the overall repair effort into "Campaigns," where each campaign is a sequence of related VUWs.

**Campaign 1: Application Stability (The Blockers)**
- **Goal:** Make the application runnable and the tests executable.
- **Sequence:** One VUW per error that prevents `pytest` from running successfully.

**Campaign 2: Type Safety (`mypy` Errors)**
- **Goal:** Achieve zero `mypy` errors project-wide.
- **Sequence:** One VUW per `mypy` error.

**Campaign 3: Code Quality (`ruff` Errors)**
- **Goal:** Achieve zero `ruff` errors project-wide.
- **Sequence:** One VUW per file, starting with files that have the most severe violations (e.g., `BLE001` blind exceptions).

By breaking the work down this way, we build rigid scaffolding around the developer: not just a map, but turn-by-turn directions with mandatory checkpoints. This approach directly targets the specific failure modes of lack of verification, incomplete changes, and getting lost.

Build VUW Campaign Workplans with the individual VUWs. Arrange the work plan in order of importance, most important to least important.

# END REMINDERS
