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
└── waitlist/      # Next.js 15 landing page
```

### Technology Stack

**Backend:**
- FastAPI with async/await patterns
- parakeet-mlx for video transcription (word-level timing, offline)
- Pydantic AI for transcript analysis and clip selection
- MoviePy v2 for video processing
- OpenCV + MediaPipe for face detection and smart cropping
- SQLite for local persistence
- Local asyncio queue for job processing
- yt-dlp for YouTube video downloads

**Frontend:**
- Next.js 15 with App Router and Turbopack
- Better Auth with Prisma adapter for authentication
- ShadCN UI components + TailwindCSS v4
- Server-side rendering patterns

**Database:**
- SQLite with tables: users, tasks, sources, generated_clips, session, account, system_fonts
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

# Run development server with AUTOMATIC PORT SELECTION (Recommended)
python -m src.main
# OR if using uv:
uv run run-dev

# WARNING: Running uvicorn directly bypasses the port selector!
# uvicorn src.main:app --reload --port 8000
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
- `LLM_MODEL` - AI model identifier (e.g., "groq:meta-llama/llama-4-scout-17b-16e-instruct", "openai:gpt-4", "anthropic:claude-3-5-sonnet")
- `GROQ_API_KEY` - Groq API key (if using Groq models - recommended for speed and cost)
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

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (API docs at /docs)
- SQLite: ./backend/supoclip.db (local file database)

## Key Architecture Patterns

### Video Processing Pipeline

1. **Video Input** → YouTube URL (via yt-dlp) or uploaded file
2. **Transcription** → parakeet-mlx generates word-level timestamps (offline)
3. **AI Analysis** → Local LLM or cloud LLM analyzes transcript for viral segments (10-45s clips)
4. **Clip Generation** → MoviePy creates 9:16 clips with:
   - Smart face-centered cropping (MediaPipe + OpenCV fallbacks)
   - parakeet-mlx-powered subtitles (word-level sync)
   - Custom fonts (TTF files in backend/fonts/)
   - Optional transition effects (videos in backend/transitions/)
5. **Storage** → Clips saved to `{TEMP_DIR}/clips/` and metadata in SQLite

### Authentication Flow

- Better Auth handles authentication with email/password
- Frontend uses Prisma Client with Better Auth adapter
- Backend receives `user_id` via request headers
- Session management via SQLite session table

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
- Maximum radon/xenon grade of A or B - C and below MUST be refactored
- Standard invocation: `python -m src.main`
- Keep main.py orchestration-focused; move core logic to modules

**Required Project Files:**
- `docs/prd.md` - Product requirements
- `docs/workplan.md` - Development plan
- `docs/polish.md` - Refinement checklist
- `checkpython.sh` - Automated quality checks (never modify)
- `.pre-commit-config.yaml` - Pre-commit framework configuration

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
- Uses SQLite via aiosqlite for async database access
- SQLAlchemy models in `backend/src/models.py` for type safety
- Async sessions via `AsyncSessionLocal` context manager
- No direct database connection calls outside database module
- Schema managed via Prisma for frontend and SQLAlchemy for backend

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

This project deviates from some docs/standards.md recommendations:

| Standard | Project Current | Notes |
|----------|-----------------|-------|
| Dependency Manager | Uses `uv` | Preferred for this project (faster than Poetry) |
| Configuration | Uses `.env` files | Simple and effective for local dev |
| Database | SQLite | Local file-based database (no server needed) |
| Job Queue | Local asyncio queue | No external dependencies required |

## Testing and Development Tips

- Backend API docs available at http://localhost:8000/docs (Swagger UI)
- Check backend logs for detailed processing steps (uses emoji logging 🚀📝✅❌)
- Frontend uses React 19 and Next.js 15 - be aware of breaking changes
- SQLite database created automatically on first backend start

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

# DEBUGGING STANDARDS : THE VUW

## How to Debug: "Verifiable Units of Work"

We will no longer provide large, multi-step "plans." Instead, we will provide a sequence of small, isolated **"Verifiable Units of Work" (VUWs)**. Each VUW_ is a micro-plan for a single, contained task to break work down into small, bite-sized chunks. Our developer is inexperienced and unskilled, so we must provide tiny work units and frequent validation.

The core principles of this approach are:

1.  **Extreme Granularity:** Each VUW_will target a single file or a single, specific error across a few files. This minimizes cognitive load and prevents the "tunnel-vision" refactoring problem. No VUW should ever have a diff longer than a single function or class.
2.  **Verification is the Definition of "Done":** Every VUW_ will have a mandatory, non-negotiable **Verification Checklist**. The task is not complete until that checklist is passed. This moves verification from an assumed skill to an explicit task requirement.
3.  **Sequential, Not Parallel:** The developer will be given **one VUW_ at a time**. They cannot start the next one until the previous one is submitted and passes a QA check. This prevents them from getting lost or working on unverified code.
4.  **Repetition Builds Discipline:** The constant repetition of the Verification Checklist on every single task is designed to build the muscle memory of a disciplined workflow.
5.  **Clarity over Conciseness:** The instructions will be painfully literal, assuming nothing. If an import is needed, the plan will state, "Add this exact import statement to the top of the file." We will use git diffs to show exact changes needed so the developer knows exactly what to type.

---

### The Structure of a "Verifiable Unit of Work" (VUW_)

Every work plan will now follow this exact template:

---
**VUW_ID:** [A unique identifier, e.g., `BUGFIX-001`]

**Objective:** [A one-sentence explanation of *why* this task is important.]
*   *Example: "To fix the fatal `ModuleNotFoundError` that prevents the application from starting."*

**Files to Modify:**
*   `[List of file paths]`

***Mandatory Pre-Work Checkpoint:***

Use git to make a checkpoint in advance of making ANY changes to a file. This is for backup and rollback, and must not be skipped. If you cannot make a checkpoint, stop.

**Step-by-Step Instructions:**

You are not done with this task until you run these commands and they succeed. Check the box only when the command passes.

1.  **[Literal instruction 1]**: *Example: "Open the file `src/crawler/extractor.py`."*
2.  **[Literal instruction 2]**: *Example: "Find the line: `import pdfplumber.errors`."*
3.  **[Literal instruction 3]**: *Example: "Delete that line and replace it with: `from pdfplumber.exceptions import PDFSyntaxError`."*
4.  **[Literal instruction 4]**: *Example: "In the `_extract_from_pdf` method, find the `except` block and change `except (pdfplumber.errors.PDFSyntaxError, ...)` to `except (PDFSyntaxError, ...)`."* - show this as a git diff exactly.

**Mandatory Verification Checklist:**

You are not done with this task until you run these commands and they succeed. Check the box only when the command passes.

*   `[ ]` **Run `./checkpython.sh`**: Must report **zero errors** for tests  **"Success: no issues found"**, **100% passing tests**.

**Self-Attestation:**

*   `[ ]` I attest that I have run checkpython.sh and tests have all passed.

***Mandatory Post-Work Checkpoint:***

Use git to make a checkpoint after a VUW passes all tests. This is for backup and rollback, and must not be skipped. If you cannot make a checkpoint, stop.

---

### The Grand Strategy: Sequencing the VUWs

We will organize the overall repair effort into a series of "Campaigns," where each campaign is a sequence of related VUWs.

**Campaign 1: Application Stability (The Blockers)**
*   **Goal:** Make the application runnable and the tests executable.
*   **Sequence of VUWs:**
    1.  **VUW_BUGFIX-001:** {explanation}
    2.  **VUW_BUGFIX-002:**  {explanation}
    3.  ... and so on for every error that prevents `pytest` from running successfully.

**Campaign 2: Type Safety (`mypy` Errors)**
*   **Goal:** Achieve zero `mypy` errors project-wide.
*   **Sequence of VUWs:**
    1.  **VUW_MYPY-001:** {explanation}
    2.  **VUW_MYPY-002:** {explanation}
    3.  ... one VUW_for each of the remaining `mypy` errors.

**Campaign 3: Code Quality (`ruff` Errors)**
*   **Goal:** Achieve zero `ruff` errors project-wide.
*   **Sequence of VUWs:**
    *   This will be the longest campaign, with one VUW_for each file that has `ruff` errors, starting with the files that have the most severe violations (like `BLE001` blind exceptions).

By breaking the work down this way, we are building a rigid "scaffolding" of process around the developer. We are not just giving them a map; we are giving them turn-by-turn directions with mandatory checkpoints. This approach directly targets their specific weaknesses—lack of verification, incomplete changes, and getting lost—and forces the adoption of a more disciplined, robust, and successful development workflow.

Build VUW Campaign Workplans with the individual VUWs. Arrange the work plan in order of importance, most important to least important.

# END REMINDERS