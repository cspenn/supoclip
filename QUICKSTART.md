# SupoClip Quick Start Guide

Run SupoClip natively on macOS (no Docker required)!

## Prerequisites

1. **macOS 13.5+** (Ventura or later)
2. **Apple Silicon** (M1/M2/M3) recommended for MLX optimization
3. **Homebrew** - Install via https://brew.sh/
4. **Python 3.11+** - `brew install python@3.11`
5. **Node.js 18+** - `brew install node`
6. **FFmpeg** - `brew install ffmpeg`
7. **API Keys** (optional - only needed for AI analysis):
   - At least one AI provider:
     - [OpenAI API Key](https://platform.openai.com/api-keys) (recommended)
     - [Google AI API Key](https://aistudio.google.com/app/apikey)
     - [Anthropic API Key](https://console.anthropic.com/)

## Quick Start

### 1. Install Dependencies

```bash
# Install system dependencies
brew install python@3.11 node ffmpeg

# Clone the repository (if not already done)
git clone https://github.com/supoclip/supoclip.git
cd supoclip

# Backend setup
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
uv sync

# Frontend setup
cd ../frontend
npm install
```

### 2. Configure Environment (Optional)

```bash
# Copy environment template
cp .env.example .env

# Edit .env to add API keys (only needed for AI analysis)
# - MLX Whisper works completely offline for transcription
# - LLM keys only needed for segment selection (optional)
```

### 3. Run the Application

```bash
# Terminal 1: Start Backend
cd backend
source .venv/bin/activate
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend (in a new terminal)
cd frontend
npm run dev
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## What's Offline vs Online?

✅ **Works Completely Offline:**
- Video transcription (MLX Whisper - no internet needed)
- Video processing and clip generation (MoviePy, OpenCV)
- Database operations (SQLite)
- Authentication (Better Auth)

❌ **Requires Internet/API Keys:**
- AI segment analysis (uses OpenAI/Google/Anthropic LLMs)
- Optional: YouTube video downloads (yt-dlp)

## Environment Configuration

### Optional Variables (API Keys)

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `OPENAI_API_KEY` | OpenAI GPT models | https://platform.openai.com/api-keys |
| `GOOGLE_API_KEY` | Google Gemini models | https://aistudio.google.com/app/apikey |
| `ANTHROPIC_API_KEY` | Anthropic Claude models | https://console.anthropic.com/ |
| `LLM_MODEL` | AI model identifier | e.g., `openai:gpt-4o` |

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MLX_WHISPER_MODEL` | `medium` | MLX Whisper model (tiny/base/small/medium/large) |
| `BETTER_AUTH_SECRET` | dev secret | Auth secret (change in production!) |
| `DATABASE_URL` | `file:./supoclip.db` | SQLite database path |
| `MAX_WORKERS` | `2` | Local job queue workers |
| `TEMP_DIR` | `./temp` | Temporary directory for video processing |

## Supported AI Models

### OpenAI (Recommended)
```bash
LLM=openai:gpt-4
LLM=openai:gpt-4-turbo
LLM=openai:gpt-3.5-turbo
```

### Anthropic
```bash
LLM=anthropic:claude-3-5-sonnet-20241022
LLM=anthropic:claude-3-opus
LLM=anthropic:claude-3-haiku
```

### Google
```bash
LLM=google:gemini-1.5-pro
LLM=google:gemini-pro
```

## Troubleshooting

### Backend won't start?

1. **Verify Python 3.11+**:
   ```bash
   python3 --version
   ```

2. **Activate virtual environment**:
   ```bash
   cd backend
   source .venv/bin/activate
   ```

3. **Check if port 8000 is in use**:
   ```bash
   lsof -i :8000
   # Kill process if needed: kill -9 <PID>
   ```

4. **Verify dependencies**:
   ```bash
   uv sync
   ```

### Frontend won't start?

1. **Clear node_modules and reinstall**:
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **Check if port 3000 is in use**:
   ```bash
   lsof -i :3000
   ```

### MLX Whisper model not downloading?

1. **Ensure internet connection** (first run only)
2. **Check disk space** (models are ~1-2GB)
3. **Manual download**:
   ```bash
   python3 -c "import mlx_whisper; mlx_whisper.load_models('medium')"
   ```

### Database issues?

Reset the SQLite database:
```bash
rm backend/supoclip.db
# Database will be recreated on next run
```

## Architecture

SupoClip runs natively on macOS:

1. **Frontend** (Next.js 15) - Port 3000
2. **Backend** (FastAPI + Python) - Port 8000
3. **Database** (SQLite) - Local file `supoclip.db`
4. **Job Queue** (Local asyncio) - In-process workers

All services run in the same process/machine with no Docker overhead.

## Production Deployment

For production use:

1. Change `BETTER_AUTH_SECRET` to a secure random string
2. Use strong database passwords
3. Enable HTTPS with a reverse proxy (nginx/Caddy)
4. Set up persistent volumes for data
5. Configure backup strategies

## Next Steps

- Read the full documentation in `CLAUDE.md`
- Check out the API docs at http://localhost:8000/docs
- View example clips in the frontend
- Customize fonts by adding TTF files to `backend/fonts/`
- Add transition effects by adding MP4 files to `backend/transitions/`

## Getting Help

- Check logs: `docker-compose logs -f`
- View API documentation: http://localhost:8000/docs
- Report issues: Create a GitHub issue with logs and error messages
