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

**Local LLM (Default - No API Key Required):**
- `LOCAL_LLM_ENABLED` - Enable local LLM (default: true)
- `LOCAL_LLM_BASE_URL` - Local LLM endpoint (default: http://localhost:6969/v1)
- `LOCAL_LLM_MODEL` - Model name for local LLM (default: local-model)

**Cloud LLM (Optional Fallback):**
- `LLM_MODEL` - AI model identifier (e.g., "openai:gpt-4", "anthropic:claude-3-5-sonnet")
- `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY` - Depending on LLM choice

**Other Configuration:**
- `DATABASE_URL` - SQLite connection string (default: sqlite+aiosqlite:///./supoclip.db)
- `TEMP_DIR` - Directory for temporary files (defaults to ./temp)

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
2. **Transcription** → MLX Whisper generates word-level timestamps (offline)
3. **AI Analysis** → Local LLM or cloud LLM analyzes transcript for viral segments (10-45s clips)
4. **Clip Generation** → MoviePy creates 9:16 clips with:
   - Smart face-centered cropping (MediaPipe + OpenCV fallbacks)
   - MLX Whisper-powered subtitles (word-level sync)
   - Custom fonts (TTF files in backend/fonts/)
   - Optional transition effects (videos in backend/transitions/)
5. **Storage** → Clips saved to `{TEMP_DIR}/clips/` and metadata in SQLite

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

## Development Standards and Best Practices

This project adheres to strict coding standards documented in `docs/standards.md`. These standards ensure code quality, maintainability, and consistency across the codebase.

### Python 3.11+ Requirements

**Mandatory:**
- Type hints required on all functions and class methods
- PEP 8 compliance enforced via Ruff and Black
- Google-style docstrings (PEP 257)
- Python 3.11+ specific features: structural pattern matching (`match-case`), exception groups (`except*`), TOML parsing
- Asyncio best practices: `TaskGroup`, explicit timeouts, exception handling
- `dataclass(slots=True)` for memory-efficient structures

**Anti-Patterns to Avoid:**
- Mutable defaults in function signatures
- Bare `except` clauses
- Circular imports
- Global variable overuse
- Hardcoded secrets or magic numbers
- Spaghetti code (max 2 levels of nesting)

### Project Structure

**File Conventions:**
- All source files must start and end with a file path comment: `# start src/example/file.py`
- Use absolute imports from project root only (no relative imports)
- Maximum 750 lines per file (refactor if exceeded)
- Standard invocation: `python -m src.main`
- Keep main.py orchestration-focused; move core logic to modules

**Required Project Files:**
- `docs/prd.md` - Product requirements
- `docs/workplan.md` - Development plan
- `docs/polish.md` - Refinement checklist
- `checkpython.sh` - Automated quality checks (never modify)
- `.pre-commit-config.yaml` - Pre-commit framework configuration
- `migrations/` - Alembic database migration scripts (when applicable)

**Project-Specific Note:** This project uses `uv` for dependency management instead of Poetry. Environment variables are stored in `.env` files for local development.

### Configuration Management

**CORE RULE:** Configuration must be externalized and validated.
- Environment-specific settings go in `.env` files (for local development)
- Sensitive credentials must be kept in `.env` (and added to `.gitignore`)
- Configuration should be validated with Pydantic at application startup
- Never hardcode configuration values or secrets in source code
- All configuration loading should use Pydantic models for type safety and validation

### Code Quality Principles

**Design Principles:**
- DRY (Don't Repeat Yourself)
- SPOT (Single Point of Truth)
- SOLID principles
- GRASP (General Responsibility Assignment)
- YAGNI (You Aren't Gonna Need It)

**Implementation Rules:**
- Functions and methods must have a single responsibility
- Inline code comments must not exceed 2 lines (prefer clear naming)
- Avoid deeply nested logic (maximum 2 levels)
- Use clear, descriptive, unambiguous names
- Resource safety: always use `with` statements and `finally` blocks
- Prefer explicit over implicit behavior

### Database Access

**Backend Database Patterns:**
- Currently uses raw SQL via asyncpg for performance (as documented in `backend/src/database.py`)
- SQLAlchemy models in `backend/src/models.py` for type safety
- Async sessions via `AsyncSessionLocal` context manager
- No direct database connection calls outside database module
- When migrating to SQLite: use SQLAlchemy Core/ORM for all operations (raw SQL forbidden in app code)
- Use Alembic for all schema migrations (manual schema changes are forbidden)

**Frontend Database Access:**
- Prisma Client via Better Auth adapter
- All queries type-safe and generated
- Session management automatic via Better Auth

### API Communication

**External HTTP Requests:**
- Use HTTPX for all external API calls (both sync and async)
- Strict timeouts required
- Connection pooling and reuse
- Exponential backoff for retries where appropriate
- No bare requests; all requests explicitly configured

### Logging Standards

**Logging Configuration:**
- Use Python logging module exclusively
- Log to timestamped files in `logs/` directory and console simultaneously
- Emoji indicators for log levels:
  - 🟢 INFO
  - 🟡 WARN
  - 🛑 ERROR
- Log level must be configurable (currently via environment variables)
- Avoid logging sensitive information (credentials, tokens, etc.)

**Current Pattern:**
Backend uses emoji-based logging: 🚀 (startup), 📝 (info), ✅ (success), ❌ (error), 🎬 (video ops), 🤖 (AI), ⬇️ (download), 📊 (stats)

### Testing Requirements

**Test Coverage:**
- Use pytest for all unit tests
- Tests must cover:
  - Pydantic model validation
  - Database logic (using test database or fixtures)
  - API interactions (using pytest-httpx mocking)
  - Alembic migrations (when applicable)
  - Configuration loading
- Update tests whenever code changes
- All tests must pass before committing (`pytest` shows 100% passing)

**Quality Checks:**
- Run `./checkpython.sh` before committing (must report zero errors)
- Pre-commit hooks enforce these checks automatically
- Tools used:
  - Ruff (linting and formatting)
  - mypy (type checking)
  - Bandit (security scanning)
  - pytest (testing)

### Debugging Methodology: Verifiable Units of Work (VUWs)

For complex changes and bug fixes, work is organized into **Verifiable Units of Work (VUWs)** - small, isolated tasks with mandatory verification checklists.

**VUW Principles:**
1. **Extreme Granularity** - Each VUW targets a single file or specific error across a few files
2. **Verification is Done** - Every VUW has a mandatory verification checklist that must pass
3. **Sequential Execution** - One VUW at a time; cannot start next until previous passes
4. **Mandatory Checkpoints** - Git checkpoint before and after each VUW

**VUW Verification Checklist:**
- `[ ]` **Run `./checkpython.sh`:** Must report **zero errors** with **100% passing tests**
- `[ ]` **Self-attestation:** Confirm `checkpython.sh` passed and tests succeeded

**Campaign Organization:**
- **Campaign 1:** Application Stability (blockers that prevent running)
- **Campaign 2:** Type Safety (zero `mypy` errors)
- **Campaign 3:** Code Quality (zero `ruff` errors)
- Work from highest-priority issues to lowest

### Performance and Progress Monitoring

**Progress Feedback:**
- Use `tqdm` for loops expected to have >5 steps or take >10 seconds
- Provides clear user feedback during long operations
- Counts iterations and time elapsed

**Performance Optimization:**
- Profile with cProfile and line_profiler before optimizing
- Cache connections with `lru_cache`
- Use memory-efficient structures (dataclass slots, generators)
- Leverage Python 3.11's faster CPython with adaptive interpreter

### Project-Specific Deviations

This project currently deviates from some docs/standards.md recommendations:

| Standard | Project Current | Migration Plan |
|----------|-----------------|---|
| Dependency Manager | Uses `uv` | Keep `uv` (better than Poetry for this project) |
| Configuration | Uses `.env` files | May migrate to YAML if project grows |
| Database (Backend) | Raw SQL via asyncpg | Will migrate to SQLAlchemy for offline version |
| Database (Current) | PostgreSQL | Will migrate to SQLite for offline version |
| Job Queue | Redis + arq | Will replace with local asyncio queue |

These deviations are documented and tracked in the migration plan (`docs/progress/fixes/migration-mlx-no-docker-2025-11-14.md`).

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
