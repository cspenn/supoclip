# SupoClip Technology Stack

## Backend (Python 3.11+)
- **Framework**: FastAPI (async, uvicorn)
- **AI/ML**:
  - parakeet-mlx (transcription with word-level timing, offline)
  - Pydantic AI (transcript analysis and segment selection)
  - MediaPipe (face detection)
- **Video Processing**:
  - MoviePy 2.2.1 (clip generation)
  - OpenCV (face detection fallback)
  - ffmpeg (system dependency)
  - yt-dlp (YouTube downloads)
- **Database**:
  - SQLite (local file database via supoclip.db)
  - SQLAlchemy (ORM)
  - aiosqlite (async SQLite driver)
- **Job Queue**:
  - Local asyncio queue (no external dependencies)
- **Real-time Communication**:
  - sse-starlette (Server-Sent Events)
- **File Handling**: aiofiles (async file I/O)
- **Package Manager**: uv

## Frontend (Node.js)
- **Framework**: Next.js 15 (App Router, Turbopack)
- **React**: React 19
- **Auth**: Better Auth with Prisma adapter
- **UI Framework**: ShadCN UI components
- **Styling**: TailwindCSS 4
- **Icons**: Lucide React
- **Theme**: next-themes (dark mode)
- **Notifications**: Sonner
- **Database Client**: Prisma Client
- **Node Package Manager**: npm

## Database (SQLite)
- **Tables**: users, tasks, sources, generated_clips, session, account, system_fonts
- **Naming Convention**:
  - Tasks/sources/clips use snake_case (created_at, updated_at)
  - Better Auth tables use camelCase (createdAt, userId)
- **Storage**: UUIDs stored as VARCHAR(36)
- **File**: backend/supoclip.db (created automatically on first start)

## Development Environment
- **Version Control**: Git
- **API Documentation**: Swagger UI (FastAPI /docs)
- **Logging**: Python logging module with emoji indicators

## Key Version Constraints
- Python: >=3.11
- Node.js: Recommended 18+ (for Next.js 15 compatibility)
- FFmpeg: Required system dependency
