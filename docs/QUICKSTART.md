# SupoClip Quick Start Guide

Run SupoClip natively on macOS (no Docker required)!

## Prerequisites

1. **macOS 13.5+** (Ventura or later)
2. **Apple Silicon** (M1/M2/M3) recommended for MLX optimization
3. **Homebrew** - Install via https://brew.sh/
4. **Python 3.11+** - `brew install python@3.11`
5. **Node.js 18+** - `brew install node`
6. **FFmpeg** - `brew install ffmpeg`
7. **Local LLM** (optional - recommended for fully offline operation):
   - KoboldCPP for local LLM inference
   - A GGUF model file (7B-13B recommended)

## Local LLM Setup (Recommended)

For fully offline operation, run a local LLM using KoboldCPP. This enables AI segment analysis without any cloud API calls or costs.

### Install KoboldCPP

```bash
# macOS (Apple Silicon)
brew install koboldcpp

# Or download from: https://github.com/LostRuins/koboldcpp/releases
```

### Download a Model

Download a GGUF model file (recommended: 7B-13B parameter models for good speed/quality balance):

- [Mistral-7B-Instruct](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF) - Fast, good quality
- [Llama-2-13B-Chat](https://huggingface.co/TheBloke/Llama-2-13B-chat-GGUF) - Good all-around
- [OpenHermes-2.5-Mistral-7B](https://huggingface.co/TheBloke/OpenHermes-2.5-Mistral-7B-GGUF) - Balanced

After downloading, note the path to the model file (e.g., `~/Models/mistral-7b.gguf`).

### Start KoboldCPP

```bash
koboldcpp --port 6969 --model ~/Models/mistral-7b.gguf --contextsize 4096
```

Leave this terminal running. KoboldCPP will:
- Load your local model (~2-5 minutes first time)
- Start OpenAI-compatible API on `http://localhost:6969`
- Display memory usage and generation speed

### Configure SupoClip for Local LLM

The default configuration is already set for local LLM:

```bash
# Copy the environment template (already configured for local LLM)
cp .env.example .env

# No API keys needed for local mode!
# LOCAL_LLM_ENABLED=true (default)
# LOCAL_LLM_BASE_URL=http://localhost:6969/v1 (default)
```

That's it! When you process videos, SupoClip will use your local model instead of cloud APIs.

### Cloud LLM Alternative (Optional)

If you prefer cloud LLMs, simply edit your `.env` file:

```bash
LOCAL_LLM_ENABLED=false
LLM_MODEL=openai:gpt-4o  # or google:gemini-2.5-flash
OPENAI_API_KEY=your-key-here
```

## Quick Start

### Fastest Way - One-Command Startup ⚡

```bash
# Clone the repository (if not already done)
git clone https://github.com/supoclip/supoclip.git
cd supoclip

# Run this single command to start everything:
./start.sh
```

That's it! The script will:
- ✅ Auto-create `.env` from `.env.example` (no API keys needed!)
- ✅ Check and install Python dependencies
- ✅ Check and install Node dependencies
- ✅ Verify KoboldCPP is running (optional, warns if not)
- ✅ Auto-detect available ports (if 8000/3000 busy, uses 8001/3001, etc.)
- ✅ Start backend and frontend automatically
- ✅ Show you the actual URLs being used

Then open your browser:
- **Frontend**: http://localhost:3003
- **API Docs**: http://localhost:8008/docs

### Manual Setup (If Preferred)

#### 1. Install Dependencies

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

#### 2. Configure Environment (Optional)

```bash
# Copy environment template (now uses local-first defaults!)
cp .env.example .env

# No API keys needed for local operation!
# - parakeet-mlx works completely offline for transcription
# - KoboldCPP provides local AI without any cloud services
```

#### 3. Run the Application

```bash
# Terminal 1: Start Backend
cd backend
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8008

# Terminal 2: Start Frontend (in a new terminal)
cd frontend
PORT=3003 npm run dev
```

#### 4. Access the Application

- **Frontend**: http://localhost:3003
- **Backend API**: http://localhost:8008
- **API Documentation**: http://localhost:8008/docs

## Authentication (No Sign-In Required!)

By default, authentication is **disabled** for local development. You can immediately start using the application without creating an account or signing in:

- ✅ No sign-up form blocking you
- ✅ No email verification needed
- ✅ Direct access to video processing
- ✅ All features available as "local-user"

**How it works:**
- Frontend automatically uses a mock user when `DISABLE_AUTH=true`
- Backend accepts requests without authentication headers
- Both default to `local-user` as the user ID

**To enable authentication (for production):**

1. Set `DISABLE_AUTH=false` in `backend/.env`
2. Set `NEXT_PUBLIC_DISABLE_AUTH=false` in `frontend/.env.local`
3. Configure Better Auth properly with a valid database connection
4. Restart the application

Authentication code is fully preserved - just toggle the environment variables to enable it!

## What's Offline vs Online?

✅ **Works Completely Offline (Default):**
- Video transcription (parakeet-mlx - no internet needed)
- AI segment analysis (Local LLM via KoboldCPP - no internet needed)
- Video processing and clip generation (MoviePy, OpenCV)
- Database operations (SQLite - local file)
- Authentication (disabled by default - no sign-in needed!)
- User management (mock local user)

⚙️ **Requires Internet/API Keys (Optional Cloud Mode):**
- Cloud AI analysis (uses OpenAI/Google/Anthropic LLMs) - optional if you prefer cloud
- Optional: YouTube video downloads (yt-dlp)

## Environment Configuration

### Local LLM Configuration (Default - No API Keys Needed)

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCAL_LLM_ENABLED` | `true` | Enable local LLM (recommended) |
| `LOCAL_LLM_BASE_URL` | `http://localhost:6969/v1` | KoboldCPP endpoint |
| `LOCAL_LLM_MODEL` | `local-model` | Local model name (passed to KoboldCPP) |

### Cloud LLM Configuration (Optional - Only if Using Cloud APIs)

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `LOCAL_LLM_ENABLED` | Set to `false` to use cloud APIs | - |
| `OPENAI_API_KEY` | OpenAI GPT models | https://platform.openai.com/api-keys |
| `GOOGLE_API_KEY` | Google Gemini models | https://aistudio.google.com/app/apikey |
| `ANTHROPIC_API_KEY` | Anthropic Claude models | https://console.anthropic.com/ |
| `LLM_MODEL` | AI model identifier | e.g., `openai:gpt-4o` |

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PARAKEET_MODEL` | `mlx-community/parakeet-tdt-0.6b-v2` | parakeet-mlx model identifier |
| `DATABASE_URL` | `sqlite+aiosqlite:///./supoclip.db` | SQLite database path |
| `MAX_WORKERS` | `2` | Local job queue workers |
| `TEMP_DIR` | `./temp` | Temporary directory for video processing |
| `DISABLE_AUTH` | `true` | Disable authentication for local dev (no sign-in needed) |
| `DEFAULT_USER_ID` | `local-user` | User ID to use when auth is disabled |
| `NEXT_PUBLIC_DISABLE_AUTH` | `true` | Frontend: disable auth (must match backend) |
| `NEXT_PUBLIC_MOCK_USER_ID` | `local-user` | Frontend: mock user ID |

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

3. **Check if port 8008 is in use**:
   ```bash
   lsof -i :8008
   # Note: ./start.sh will auto-detect and use alternate port (8009, 8010, etc.) if needed
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

2. **Check if port 3003 is in use**:
   ```bash
   lsof -i :3003
   ```

### parakeet-mlx model not downloading?

1. **Ensure internet connection** (first run only)
2. **Check disk space** (models are ~1-2GB)
3. **Manual download**:
   ```bash
   python3 -c "from parakeet_mlx.utils import from_pretrained; from_pretrained('mlx-community/parakeet-tdt-0.6b-v2')"
   ```

### Database issues?

Reset the SQLite database:
```bash
rm backend/supoclip.db
# Database will be recreated on next run
```

## Architecture

SupoClip runs natively on macOS:

1. **Frontend** (Next.js 15) - Port 3003
2. **Backend** (FastAPI + Python) - Port 8008
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

- Check logs:
  - Backend: `tail -f /tmp/supoclip_backend.log`
  - Frontend: `tail -f /tmp/supoclip_frontend.log`
- View API documentation: http://localhost:8000/docs
- Report issues: Create a GitHub issue with logs and error messages
- No .env file needed anymore! The app works with local-first defaults
