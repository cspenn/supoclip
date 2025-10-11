# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SupoClip is an open-source alternative to OpusClip - an AI-powered video clipping tool that transforms long-form content into viral short clips. The project consists of three main applications:

1. **Backend** (Python/FastAPI) - Video processing, AI analysis, and API
2. **Frontend** (Next.js 15) - Main application interface
3. **Waitlist** (Next.js 15) - Landing page for hosted version signups

## Architecture

### Monorepo Structure

```
supoclip/
├── backend/       # Python FastAPI backend
├── frontend/      # Next.js 15 main app
├── waitlist/      # Next.js 15 landing page
├── docker-compose.yml
└── init.sql       # PostgreSQL schema
```

### Technology Stack

**Backend:**
- FastAPI with async/await patterns
- AssemblyAI for video transcription (word-level timing)
- Pydantic AI for transcript analysis and clip selection
- MoviePy v2 for video processing
- OpenCV + MediaPipe for face detection and smart cropping
- PostgreSQL (via asyncpg/SQLAlchemy) for persistence
- Redis for caching/job queues
- yt-dlp for YouTube video downloads

**Frontend:**
- Next.js 15 with App Router and Turbopack
- Better Auth with Prisma adapter for authentication
- ShadCN UI components + TailwindCSS v4
- Server-side rendering patterns

**Database:**
- PostgreSQL 15 with tables: users, tasks, sources, generated_clips, session, account, verification
- Uses both snake_case (tasks) and camelCase (Better Auth tables) conventions

## Development Commands

### Backend Development

The backend uses `uv` package manager (not pip or poetry).

```bash
cd backend

# Create virtual environment
uv venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
uv sync

# Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Prerequisites:**
- Python 3.11+
- ffmpeg installed (`brew install ffmpeg` on macOS)
- `uv` package manager

**Environment variables (backend/.env):**
- `ASSEMBLY_AI_API_KEY` - Required for video transcription
- `LLM` - AI model identifier (e.g., "openai:gpt-4", "anthropic:claude-3-5-sonnet")
- `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY` - Depending on LLM choice
- `DATABASE_URL` - PostgreSQL connection string
- `TEMP_DIR` - Directory for temporary files (defaults to /tmp)

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server with Turbopack
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint
npm run lint
```

### Waitlist Development

Same commands as frontend:

```bash
cd waitlist
npm install
npm run dev
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (API docs at /docs)
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Key Architecture Patterns

### Video Processing Pipeline

1. **Video Input** → YouTube URL (via yt-dlp) or uploaded file
2. **Transcription** → AssemblyAI generates word-level timestamps
3. **AI Analysis** → Pydantic AI analyzes transcript for viral segments (10-45s clips)
4. **Clip Generation** → MoviePy creates 9:16 clips with:
   - Smart face-centered cropping (MediaPipe + OpenCV fallbacks)
   - AssemblyAI-powered subtitles (word-level sync)
   - Custom fonts (TTF files in backend/fonts/)
   - Optional transition effects (videos in backend/transitions/)
5. **Storage** → Clips saved to `{TEMP_DIR}/clips/` and metadata in PostgreSQL

### Authentication Flow

- Better Auth handles authentication with email/password
- Frontend uses Prisma Client with Better Auth adapter
- Backend receives `user_id` via request headers
- Session management via PostgreSQL session table

### Database Access Patterns

**Frontend:**
- Uses Prisma Client (`@prisma/client`)
- Better Auth manages user/session tables

**Backend:**
- Uses raw SQL via asyncpg for performance
- SQLAlchemy models defined in `backend/src/models.py`
- Async sessions via `AsyncSessionLocal` context manager

### API Endpoints

Key backend endpoints (see `backend/src/main.py`):

- `POST /start` - Synchronous video processing (returns results immediately)
- `POST /start-with-progress` - Async video processing (returns task_id for SSE tracking)
- `GET /tasks/{task_id}` - Get task status and details
- `GET /tasks/{task_id}/clips` - Get all clips for a task
- `GET /fonts` - List available fonts
- `GET /transitions` - List available transition effects
- `POST /upload` - Upload video file
- `GET /clips/{filename}` - Serve generated clips (static files)

### Video Processing Customization

Font customization is passed via `font_options` in request body:

```json
{
  "source": {"url": "..."},
  "font_options": {
    "font_family": "TikTokSans-Regular",
    "font_size": 24,
    "font_color": "#FFFFFF"
  }
}
```

Backend stores font preferences in tasks table and applies during clip generation.

## Code Organization

### Backend Structure

- `backend/src/main.py` - FastAPI app, endpoints, lifespan management
- `backend/src/video_utils.py` - Video processing, cropping, subtitle generation (~820 lines)
- `backend/src/ai.py` - Pydantic AI agents for transcript analysis
- `backend/src/youtube_utils.py` - YouTube download and metadata
- `backend/src/models.py` - SQLAlchemy models
- `backend/src/database.py` - Database connection management
- `backend/src/config.py` - Environment configuration
- `backend/fonts/` - Custom TTF font files
- `backend/transitions/` - Transition effect videos (.mp4)

### Frontend Structure

- `frontend/src/app/` - Next.js App Router pages
- `frontend/src/app/page.tsx` - Main landing/dashboard
- `frontend/src/app/tasks/[id]/page.tsx` - Task detail view
- `frontend/src/app/api/auth/[...all]/route.ts` - Better Auth API route
- `frontend/src/components/` - React components
- `frontend/src/lib/auth.ts` - Better Auth server config
- `frontend/src/lib/auth-client.ts` - Better Auth client

## Important Considerations

### Video Processing

- All clips are converted to 9:16 aspect ratio (vertical format)
- Face detection uses MediaPipe (primary), OpenCV DNN (fallback), Haar cascade (last resort)
- Subtitles positioned at 75% down the video (lower-middle, not bottom)
- H.264 encoding with even dimensions required (uses `round_to_even()`)
- AssemblyAI transcript data cached as `.transcript_cache.json` alongside video files

### AI Segment Selection

The AI (via Pydantic AI) selects 3-7 segments based on:
- Strong hooks and attention-grabbing moments
- Valuable content (tips, insights, stories)
- Emotional moments (excitement, humor, inspiration)
- Complete thoughts that work standalone
- Duration: 10-45 seconds per clip
- Critical validation: start_time ≠ end_time, minimum 5-10s duration

### Database Conventions

- Tasks/sources/clips use snake_case fields
- Better Auth tables use camelCase (createdAt, updatedAt, userId, etc.)
- UUIDs stored as VARCHAR(36), not native UUID type
- Triggers auto-update `updated_at` and `updatedAt` columns

### File Storage

- Uploaded videos: `{TEMP_DIR}/uploads/`
- Downloaded videos: `{TEMP_DIR}/` (via yt-dlp)
- Generated clips: `{TEMP_DIR}/clips/`
- Clips served via FastAPI static files at `/clips/{filename}`

## Testing and Development Tips

- Backend API docs available at http://localhost:8000/docs (Swagger UI)
- Check backend logs for detailed processing steps (uses emoji logging 🚀📝✅❌)
- Frontend uses React 19 and Next.js 15 - be aware of breaking changes
- Database initialized via `init.sql` on first PostgreSQL container start
- Use `docker-compose logs -f backend` to debug video processing issues

## Common Workflows

### Adding a New Font

1. Add `.ttf` file to `backend/fonts/`
2. Font becomes available via `GET /fonts` endpoint
3. Reference by filename (without extension) in `font_family` parameter

### Adding Transition Effects

1. Add `.mp4` file to `backend/transitions/`
2. Transition becomes available via `GET /transitions` endpoint
3. Automatically used by `create_clips_with_transitions()` in round-robin fashion

### Modifying AI Clip Selection

Edit `backend/src/ai.py`:
- `simplified_system_prompt` - AI instructions for segment selection
- `TranscriptSegment` - Pydantic model for segment structure
- `get_most_relevant_parts_by_transcript()` - Main analysis function with validation logic
