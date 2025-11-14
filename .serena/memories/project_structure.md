# SupoClip Project Structure

## Directory Layout

```
supoclip/
├── backend/                      # Python FastAPI backend
│   ├── src/
│   │   ├── main.py              # Current entry point (monolithic)
│   │   ├── main_refactored.py   # New entry point (layered architecture)
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── tasks.py     # Task API endpoints
│   │   │       └── media.py     # Fonts, transitions, uploads
│   │   ├── services/
│   │   │   ├── task_service.py  # Task business logic
│   │   │   └── video_service.py # Video processing logic
│   │   ├── repositories/
│   │   │   ├── task_repository.py    # Task data access
│   │   │   ├── clip_repository.py    # Clip data access
│   │   │   └── source_repository.py  # Source data access
│   │   ├── workers/
│   │   │   ├── tasks.py         # arq worker functions
│   │   │   ├── job_queue.py     # Queue management
│   │   │   └── progress.py      # Progress tracking (Redis pub/sub)
│   │   ├── utils/
│   │   │   └── async_helpers.py # Async utility functions
│   │   ├── video_utils.py       # Video processing (~820 lines)
│   │   ├── ai.py                # Pydantic AI agents
│   │   ├── youtube_utils.py     # YouTube download utilities
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── database.py          # Database connection management
│   │   ├── config.py            # Environment configuration
│   │   └── worker_main.py       # Worker entry point
│   ├── fonts/                    # TTF font files (custom styling)
│   ├── transitions/              # MP4 transition effect files
│   ├── migrations/               # Alembic database migrations
│   ├── Dockerfile               # Container definition
│   ├── pyproject.toml           # uv dependencies
│   ├── uv.lock                  # Dependency lock file
│   └── README.md                # Backend-specific docs
│
├── frontend/                     # Next.js 15 main application
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Root layout
│   │   │   ├── page.tsx         # Home/dashboard page
│   │   │   ├── tasks/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx # Task detail page
│   │   │   ├── list/
│   │   │   │   └── page.tsx     # Task list page
│   │   │   ├── settings/
│   │   │   │   └── page.tsx     # Settings page
│   │   │   ├── sign-in/
│   │   │   │   └── page.tsx     # Sign in page
│   │   │   ├── sign-up/
│   │   │   │   └── page.tsx     # Sign up page
│   │   │   ├── api/
│   │   │   │   ├── auth/
│   │   │   │   │   └── [...all]/
│   │   │   │   │       └── route.ts  # Better Auth routes
│   │   │   │   └── preferences/
│   │   │   │       └── route.ts      # User preferences
│   │   │   └── globals.css      # Global styles
│   │   ├── components/
│   │   │   ├── ui/              # ShadCN UI components
│   │   │   ├── auth/            # Auth components
│   │   │   └── dynamic-video-player.tsx # Video player
│   │   └── lib/
│   │       ├── auth.ts          # Better Auth server config
│   │       ├── auth-client.ts   # Better Auth client
│   │       ├── prisma.ts        # Prisma client
│   │       └── utils.ts         # Utility functions
│   ├── prisma/
│   │   └── schema.prisma        # Prisma database schema
│   ├── public/                   # Static assets
│   ├── Dockerfile               # Container definition
│   ├── package.json             # npm dependencies
│   ├── package-lock.json        # npm lock file
│   ├── next.config.ts           # Next.js configuration
│   ├── tailwind.config.ts       # Tailwind configuration
│   ├── tsconfig.json            # TypeScript configuration
│   └── README.md                # Frontend-specific docs
│
├── waitlist/                     # Next.js 15 landing page
│   ├── src/                     # Same structure as frontend
│   ├── Dockerfile
│   ├── package.json
│   └── ...
│
├── docker-compose.yml           # Orchestration config (5 services)
├── init.sql                     # PostgreSQL schema + initial data
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore patterns
├── start.sh                     # Quick start script
├── CLAUDE.md                    # Developer guidance (this repo)
├── CLAUDE_MD_AUDIT_REPORT.md   # Documentation audit
├── REFACTORING_COMPLETE.md     # Refactoring notes
├── QUICKSTART.md               # Quick start guide
├── README.md                   # Main project README
├── LICENSE                     # AGPL-3.0 license
└── .git/                       # Version control

## Docker Services (docker-compose.yml)

1. **frontend** (port 3000)
   - Next.js 15 development server
   - Hot reload enabled
   - Health check: curl http://localhost:3000/
   - Depends on: postgres, backend

2. **backend** (port 8000)
   - FastAPI application
   - Runs: `uvicorn src.main:app` OR `uvicorn src.main_refactored:app`
   - Health checks: /health, /health/db, /health/redis
   - Depends on: postgres, redis

3. **worker** (no external port)
   - arq background job processor
   - Runs: `arq src.workers.tasks.WorkerSettings`
   - Depends on: postgres, redis, backend
   - **Only runs refactored architecture**

4. **postgres** (port 5432)
   - PostgreSQL 15-alpine
   - Initialization: init.sql
   - Data persistence: postgres_data volume

5. **redis** (port 6379)
   - Redis 7-alpine
   - For: job queue, progress tracking, caching
   - Data persistence: redis_data volume

## Key File Purposes

### Backend Core
- **main.py**: Monolithic approach with all endpoints in one file
- **main_refactored.py**: Layered architecture with separated concerns
- **video_utils.py**: Core video processing (face detection, cropping, subtitle generation)
- **ai.py**: Pydantic AI agents for transcript analysis and segment selection
- **models.py**: SQLAlchemy ORM definitions (User, Task, Source, GeneratedClip)
- **database.py**: AsyncSession factory and connection management
- **config.py**: Environment variable loading and validation

### Frontend Core
- **page.tsx** files: Next.js pages (automatically routed)
- **route.ts** files: Next.js API routes
- **auth.ts**: Better Auth server-side configuration
- **auth-client.ts**: Better Auth client-side configuration
- **prisma.ts**: Singleton Prisma Client instance

### Database
- **init.sql**: Creates all tables, triggers, and indexes
- **prisma/schema.prisma**: Prisma schema (frontend uses this)
- Tables created:
  - users (Better Auth + custom fields)
  - tasks (video processing tasks)
  - sources (YouTube/uploaded video metadata)
  - generated_clips (output video clips)
  - session, account, verification (Better Auth)

## Important Notes

### Architecture Transition
- **Current production**: main.py (monolithic, ~630 lines)
- **Recommended new code**: main_refactored.py (layered, 3 services + 3 repos)
- **Decision point**: Both implementations exist; use based on requirements

### Volume Mounts (Docker)
- Uploads: `/app/uploads` → `uploads/` volume
- Clips: `/app/clips` → `clips/` volume
- Fonts: `./backend/fonts` → read-only
- Transitions: `./backend/transitions` → read-only
- Redis data: `/data` → `redis_data/` volume
- Postgres data: `/var/lib/postgresql/data` → `postgres_data/` volume

### Naming Patterns
- **Backend files**: snake_case.py
- **Frontend components**: PascalCase.tsx for components, kebab-case.tsx for pages
- **Tables**: snake_case (except Better Auth camelCase)
- **Functions**: snake_case in Python, camelCase in TypeScript
