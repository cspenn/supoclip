# Backend Docs

## Requirements

Ensure you have `ffmpeg` installed.

```
# MacOS
brew install ffmpeg

# Linux (Ubuntu)
sudo apt update -y && sudo apt install install ffmpeg -y

# Windows (Chocolatey https://chocolatey.org/)
choco install ffmpeg
```

You must also have `uv` package manager installed.

1. Create a virtual environment

```
uv venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
uv sync
```

3. Run the backend

```bash
# RECOMMENDED: Auto-selects free port (starts at 8000)
python -m src.main
# OR
uv run run-dev

# NOTE: uvicorn CLI (uvicorn src.main:app) will NOT auto-select ports.
```
