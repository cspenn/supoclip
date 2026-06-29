# SupoClip

**Self-hosted AI video clipping. No subscriptions. No watermarks. No limits.**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

---

## What is SupoClip?

SupoClip is a self-hosted, open-source alternative to OpusClip. It runs entirely on your machine as a single Python process — no cloud fees, no watermarks, no monthly limits. Paste a YouTube URL or upload a video and get back polished 9:16 short clips with AI-selected segments and word-level burned-in subtitles.

---

## Features

- **YouTube + file upload** — paste a URL or upload an MP4/MOV directly
- **Local transcription** — parakeet-mlx runs offline on Apple Silicon (word-level timestamps, no API key)
- **AI clip selection** — finds 3–7 best segments (10–45 seconds each) using a local or cloud LLM
- **Smart cropping** — face-centered 9:16 framing via MediaPipe, falls back to center crop
- **Word-level subtitles** — burned in with pysubs2 + ffmpeg ASS filter, fully customizable
- **Custom fonts** — drop any TTF into `fonts/`, pick it in the Settings UI
- **Transition effects** — drop MP4 clips into `transitions/`, muxed round-robin to the front of each generated clip
- **Logo overlay** — configure a logo image in Settings; applied top-right on every clip
- **Vision-aware clipping (optional)** — enable a VLM for active-speaker framing, engagement re-ranking, and smart thumbnail selection (off by default; see Configuration)
- **Task history** — persistent tracking of every job with status and clip viewer
- **No watermarks** — your content, your clips

---

## Requirements

- Python 3.12+
- ffmpeg **built with libass** (the `ass`/`subtitles` filters are required for subtitle burn-in). Homebrew's default ffmpeg omits libass; on macOS install the community tap instead:
  ```bash
  brew tap homebrew-ffmpeg/ffmpeg
  brew install homebrew-ffmpeg/ffmpeg/ffmpeg
  # Verify libass is present:
  ffmpeg -filters | grep -E 'subtitles| ass '
  ```
- `uv` package manager (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- macOS with Apple Silicon (required for parakeet-mlx local transcription)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/[user]/supoclip
cd supoclip

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env if needed (works out of the box with a local LLM)

# 4. Run
python -m src.main
```

Opens at **http://localhost:8008**

---

## Configuration

SupoClip reads all settings from `.env`. Copy `.env.example` to `.env` to get started — defaults work without any changes if you're running a local LLM.

### LLM Options

```dotenv
# Local LLM — default, no API key required
# Run koboldcpp: koboldcpp --port 6969 --model /path/to/model.gguf
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:6969/v1
LOCAL_LLM_MODEL=local-model

# Cloud LLM — set LOCAL_LLM_ENABLED=false and pick a provider
LOCAL_LLM_ENABLED=false
LLM_MODEL=groq:meta-llama/llama-4-scout-17b-16e-instruct
GROQ_API_KEY=gsk_...

# Other supported providers:
# LLM_MODEL=openai:gpt-4o          OPENAI_API_KEY=sk-...
# LLM_MODEL=anthropic:claude-3-5-sonnet-20241022  ANTHROPIC_API_KEY=sk-ant-...
# LLM_MODEL=google:gemini-2.5-flash  GOOGLE_API_KEY=...
```

Cloud LLMs are faster for clip selection but send transcript text to the provider.

### Vision-aware clipping (optional)

All vision features are **disabled by default** and use a separate multimodal model (VLM) distinct from the text LLM.

```dotenv
# Enable VLM features
VLM_ENABLED=true
VLM_MODEL=<vision-capable model on your OpenAI-compatible endpoint>

# VLM_BASE_URL and VLM_API_KEY fall back to LOCAL_LLM_BASE_URL / LOCAL_LLM_API_KEY if not set
VLM_BASE_URL=http://localhost:6969/v1
VLM_API_KEY=

# For reasoning VLMs increase the token budget (default 1024)
VLM_MAX_TOKENS=4096

# Content mode: single (default) | duo | multi
# In duo/multi mode the VLM crops to the active speaker instead of a generic face crop
CONTENT_MODE=duo

# Re-rank clips by a fused transcript+visual score (default false)
VLM_RERANK_ENABLED=true

# Deterministic quality filters (no VLM required)
QUALITY_DARK_FILTER_ENABLED=true   # skip segments that are too dark
SCENE_SNAP_ENABLED=true            # snap clip boundaries to scene cuts
```

> **Note:** Not all multimodal server builds actually perceive images. Verify yours first:
> ```bash
> uv run --no-sync python -m tests.e2e.vision_spike <path/to/video>
> ```
> See `docs/plans/vlm-enhancement.md` for full details.

### Transcription

```dotenv
# parakeet-mlx model — runs locally on Apple Silicon
PARAKEET_MODEL=mlx-community/parakeet-tdt-0.6b-v2
```

### Storage

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./supoclip.db
TEMP_DIR=./temp
```

---

## Adding Custom Fonts

Drop any `.ttf` file into the `fonts/` directory. It appears immediately in the Settings font selector — no restart needed. Google Fonts work well.

To find a font's internal family name (required for subtitle rendering):
```bash
fc-query fonts/MyFont.ttf | grep family
```

---

## Adding Transition Effects

Drop any `.mp4` file into the `transitions/` directory. The transition clip's video content is concatenated to the front of each generated clip in round-robin order — no restart needed.

---

## Architecture

SupoClip is a single all-Python application — one process, one event loop, no Node.js, no TypeScript, no npm.

| Layer | Technology |
|---|---|
| UI + API | NiceGUI (built on FastAPI) |
| Transcription | parakeet-mlx (local, Apple Silicon, word-level timing) |
| AI analysis | Pydantic AI + Groq structured outputs (local or cloud LLM) |
| Video processing | ffmpeg (subprocess, no MoviePy) |
| Subtitles | pysubs2 → ASS files → ffmpeg `ass` filter (requires libass) |
| Face detection | MediaPipe only (center crop fallback if no face found) |
| Vision (optional) | Multimodal VLM via OpenAI-compatible endpoint — active-speaker framing, engagement re-ranking, smart thumbnails |
| Quality (optional) | Deterministic ffmpeg scene detection + brightness filtering (no VLM needed) |
| Storage | SQLite via SQLAlchemy async + aiosqlite |

### Pipeline

```
Video input (URL or upload)
  → Download (yt-dlp, YouTube only)
  → Transcribe (parakeet-mlx → word list with timestamps)
  → Analyze (LLM → 3–7 segments with start/end/title/score)
  → [optional] VLM engagement re-rank (fused transcript + visual score)
  → [optional] Deterministic quality filter (dark-segment skip, scene-cut snap)
  → Generate clips per segment:
        ffmpeg: trim
          → 9:16 crop (face-centered via MediaPipe;
                        VLM active-speaker for duo/multi;
                        center fallback)
          → karaoke subtitle burn-in (ASS via libass)
          → [optional] logo overlay (top-right)
          → [optional] transition clip mux (round-robin, prepended)
          → H.264 encode
  → Per-clip thumbnail (VLM best-frame or midpoint fallback)
  → Save to DB + serve from /clips/
```

### Project Structure

```
src/
  main.py              # FastAPI + NiceGUI entry point, lifespan
  config.py            # Pydantic BaseSettings (reads .env)
  database.py          # SQLAlchemy async engine + session
  db_base.py           # SQLAlchemy declarative Base
  models.py            # Task, GeneratedClip, UserPreferences
  exceptions.py        # SupoClipError hierarchy
  pages/
    home.py            # URL input, file upload, start processing
    task.py            # Real-time progress, clip viewer, downloads
    history.py         # All past tasks with status
    settings.py        # Font, subtitle style, AI prompt preferences
    _util.py           # Shared page helpers
  pipeline/
    download.py        # yt-dlp YouTube download
    transcribe.py      # parakeet-mlx transcription + caching
    analyze.py         # LLM clip selection (Groq structured or Pydantic AI)
    clip.py            # ffmpeg clip generation with filtergraph
    subtitles.py       # pysubs2 ASS subtitle file generation
    face_detect.py     # MediaPipe face detection, crop box calculation
    vision.py          # VLM active-speaker framing, engagement, thumbnails
    quality.py         # Deterministic scene detection + brightness filter
  services/
    video_service.py   # Pipeline orchestration, progress reporting
fonts/                 # Drop TTF files here for custom fonts
transitions/           # Drop MP4 files here for transition effects
tests/
  unit/                # Unit tests, 100% line+branch coverage
  integration/         # Integration tests (real DB, mocked externals)
  e2e/                 # Manual smoke + vision spike runners (not in gate)
```

---

## Development

```bash
# Full quality gate — run this before every commit
./checkpython.sh

# What it runs (in order):
#   ruff check + ruff format
#   mypy + pyright
#   bandit (security)
#   radon / xenon (complexity)
#   deptry + grimp (import cycle check)
#   pytest with 100% line+branch coverage (~719 tests, including real-output ffmpeg integration tests)
```

All contributions must pass `./checkpython.sh` with zero errors and 100% passing tests.

---

## License

SupoClip is released under the [AGPL-3.0 License](LICENSE). You are free to use, modify, and distribute this software under those terms.
