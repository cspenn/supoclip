# SupoClip

**Self-hosted AI video clipping. No subscriptions. No watermarks. No limits.**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

---

## What is SupoClip?

SupoClip is a self-hosted, open-source alternative to OpusClip. It runs entirely on your machine as a single Python process - no cloud fees, no watermarks, no monthly limits. Drop in a YouTube URL or upload a video and get back polished 9:16 short clips with AI-selected segments and word-level subtitles.

---

## Features

- **YouTube + file upload** - paste a URL or upload an MP4/MOV directly
- **Local transcription** - parakeet-mlx runs offline on Apple Silicon (no API key, no data leaves your machine)
- **AI clip selection** - finds the 3-7 best segments (10-45 seconds each) using a local or cloud LLM
- **Smart cropping** - face-centered 9:16 framing via MediaPipe + OpenCV
- **Word-level subtitles** - burned in with pysubs2 + ffmpeg, fully customizable
- **Custom fonts** - drop any TTF into `fonts/`, pick it in the UI
- **No watermarks** - your content, your clips

---

## Requirements

- Python 3.12+
- ffmpeg (`brew install ffmpeg`)
- uv package manager (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- macOS (Apple Silicon recommended for parakeet-mlx transcription)

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

# 4. Run
python -m src.main
```

Opens at **http://localhost:8008**

---

## Configuration

SupoClip works out of the box with a local LLM. Edit `.env` to change behavior:

```dotenv
# Local LLM (default - no API key required)
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:6969/v1
LOCAL_LLM_MODEL=local-model

# Optional: switch to a cloud LLM
# LLM_MODEL=groq:meta-llama/llama-4-scout-17b-16e-instruct
# GROQ_API_KEY=your-key-here

# Other supported providers: openai, anthropic, google
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...
```

Cloud LLMs are faster for clip selection but require an API key and send transcript text to the provider.

---

## Adding Custom Fonts

Drop any `.ttf` file into the `fonts/` directory. It appears immediately in the font selector - no restart needed. Google Fonts work well: download the TTF file and drop it in.

---

## Development

```bash
# Run tests
pytest

# Run quality gate (ruff, mypy, bandit, pytest)
./checkpython.sh
```

All PRs must pass `./checkpython.sh` with zero errors before merging.

---

## Architecture

SupoClip is a single all-Python application:

| Layer | Technology |
|---|---|
| UI + API | NiceGUI (built on FastAPI) |
| Transcription | parakeet-mlx (local, Apple Silicon) |
| AI analysis | Pydantic AI (local or cloud LLM) |
| Video processing | ffmpeg + MoviePy |
| Subtitles | pysubs2 + ffmpeg |
| Face detection | MediaPipe + OpenCV |
| Storage | SQLite |

**No Node.js. No TypeScript. No npm.**

The full technical spec is in `docs/spec.md`.

---

## License

SupoClip is released under the [AGPL-3.0 License](LICENSE). You are free to use, modify, and distribute this software under those terms.
