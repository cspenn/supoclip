# SupoClip Technology Stack

## Backend (Python 3.11+)
- **Framework**: FastAPI (async, uvicorn)
- **AI/ML**:
  - AssemblyAI (transcription with word-level timing)
  - Pydantic AI (transcript analysis and segment selection)
  - MediaPipe (face detection)
- **Video Processing**:
  - MoviePy 2.2.1 (clip generation)
  - OpenCV (face detection fallback)
  - ffmpeg (system dependency)
  - yt-dlp (YouTube downloads)
- **Database**:
  - PostgreSQL 15 (primary data storage)
  - SQLAlchemy (ORM)
  - asyncpg (async PostgreSQL driver)
  - Alembic (migrations)
- **Job Queue**:
  - Redis 7 (job queue backend)
  - arq (async job queue library)
- **Real-time Communication**:
  - sse-starlette (Server-Sent Events)
  - redis.asyncio (async Redis client)
- **File Handling**: aiofiles (async file I/O)
- **Package Manager**: uv (UV package manager)

## Frontend (Node.js)
- **Framework**: Next.js 15 (App Router, Turbopack)
- **React**: React 19
- **Auth**: Better Auth 1.3.4 with Prisma adapter
- **UI Framework**: ShadCN UI components
- **Styling**: TailwindCSS 4
- **Icons**: Lucide React
- **Theme**: next-themes (dark mode)
- **Notifications**: Sonner
- **Database Client**: Prisma Client 6.12.0
- **Node Package Manager**: npm (bun.lock also present)

## Database (PostgreSQL 15)
- **Tables**: users, tasks, sources, generated_clips, session, account, verification
- **Naming Convention**: 
  - Tasks/sources/clips use snake_case (created_at, updated_at)
  - Better Auth tables use camelCase (createdAt, userId)
- **Storage**: UUIDs stored as VARCHAR(36)
- **Initialization**: init.sql (applied on container startup)

## Development Environment
- **Version Control**: Git
- **Container Orchestration**: Docker & Docker Compose
- **API Documentation**: Swagger UI (FastAPI /docs)
- **Logging**: Python logging module with emoji indicators

## Key Version Constraints
- Python: >=3.11
- Node.js: Recommended 18+ (for Next.js 15 compatibility)
- FFmpeg: Required system dependency
- PostgreSQL: 15-alpine (in Docker)
- Redis: 7-alpine (in Docker)
