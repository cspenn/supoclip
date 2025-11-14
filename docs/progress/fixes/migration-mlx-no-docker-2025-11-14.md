# SupoClip Migration Plan: parakeet-MLX + Docker Removal

**Document Version:** 1.0  
**Date:** 2025-11-14  
**Status:** Planning Phase  
**Target Environment:** macOS with Python 3.11, fully offline-capable

---

## Executive Summary

This document outlines a comprehensive migration plan to transform SupoClip from a Docker-based, cloud-dependent application into a native macOS application that runs completely offline. The migration involves three major architectural changes:

1. **Remove all Docker infrastructure** - Convert to native macOS processes
2. **Replace AssemblyAI with parakeet-MLX** - Use Apple Silicon-optimized offline transcription
3. **Replace PostgreSQL with SQLite** - Lightweight, embedded database

**Key Benefits:**
- No Docker overhead or complexity
- Complete offline operation (no internet required after initial setup)
- Optimized for Apple Silicon (M1/M2/M3) via MLX
- Simplified deployment and maintenance
- Faster startup and lower resource usage

**Estimated Effort:** 3-5 days for full migration  
**Risk Level:** Medium (significant architectural changes but clear migration path)

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Target State](#2-target-state)
3. [Dependencies to Remove](#3-dependencies-to-remove)
4. [Dependencies to Add](#4-dependencies-to-add)
5. [Step-by-Step Migration Path](#5-step-by-step-migration-path)
6. [Code Changes by Module](#6-code-changes-by-module)
7. [Database Migration](#7-database-migration)
8. [Configuration Changes](#8-configuration-changes)
9. [Testing Strategy](#9-testing-strategy)
10. [Risk Assessment](#10-risk-assessment)
11. [Rollback Strategy](#11-rollback-strategy)

---

## 1. Current State Analysis

### 1.1 Architecture Overview

SupoClip currently consists of:
- **5 Docker containers** orchestrated via docker-compose.yml
- **PostgreSQL 15** for data persistence
- **Redis 7** for job queues and real-time progress tracking
- **AssemblyAI cloud API** for video transcription
- **Next.js frontend** (port 3000)
- **FastAPI backend** (port 8000)
- **arq worker process** for background jobs

### 1.2 Docker Infrastructure

**docker-compose.yml Services:**
1. `frontend` - Next.js 15 development server
2. `backend` - FastAPI application (main.py or main_refactored.py)
3. `worker` - arq background job processor
4. `postgres` - PostgreSQL 15-alpine
5. `redis` - Redis 7-alpine

**Volumes:**
- `uploads/` - Uploaded video files
- `clips/` - Generated clip outputs
- `postgres_data/` - Database persistence
- `redis_data/` - Redis persistence
- `backend/fonts/` - Custom TTF fonts (read-only mount)
- `backend/transitions/` - Transition effect videos (read-only mount)

**Network:**
- Custom network `supoclip-network` for inter-container communication

### 1.3 AssemblyAI Integration

**Current Usage:**
- `backend/src/video_utils.py` (line 17): `import assemblyai as aai`
- `backend/src/config.py` (line 13): `assembly_ai_api_key` configuration
- Two main functions:
  - `create_assemblyai_subtitles()` - Word-level subtitle generation (line 475)
  - `get_video_transcript_with_assemblyai()` - Transcript extraction (line 817)

**Transcription Flow:**
1. Video uploaded or downloaded via yt-dlp
2. AssemblyAI API called with video file
3. Receives word-level timestamps (start/end in milliseconds)
4. Cached as `.transcript_cache.json` alongside video
5. Used for AI segment analysis and subtitle generation

**Key Features Used:**
- Word-level timing (`words` array with `start`, `end`, `text`, `confidence`)
- Speaker diarization (potentially)
- Best speech model (`aai.SpeechModel.best`)
- Language detection

### 1.4 Redis Dependencies

**Files Using Redis:**
- `backend/src/config.py` - Redis host/port configuration (lines 24-25)
- `backend/src/workers/job_queue.py` - arq job queue wrapper (77 lines)
- `backend/src/workers/progress.py` - Real-time progress tracking (82 lines)
- `backend/src/workers/tasks.py` - Worker task definitions
- `backend/src/main_refactored.py` - SSE endpoint for progress streaming
- `backend/src/api/routes/tasks.py` - Task enqueueing

**Redis Usage Patterns:**
1. **Job Queue (arq):**
   - Enqueue video processing tasks
   - Background worker execution
   - Job status tracking
   
2. **Progress Tracking:**
   - `progress:{task_id}` keys with JSON data
   - Pub/sub for real-time updates
   - SSE streaming to frontend

3. **Caching (if used):**
   - Potentially for video metadata
   - API response caching

### 1.5 PostgreSQL Schema

**Tables (from init.sql):**
1. `users` - User accounts with Better Auth (camelCase columns)
2. `sources` - Video source metadata (YouTube/uploaded)
3. `tasks` - Video processing tasks (snake_case columns)
4. `generated_clips` - Output video clips with metadata
5. `session` - Better Auth sessions
6. `account` - Better Auth OAuth accounts
7. `verification` - Better Auth verification tokens

**Key Features:**
- UUID extension for ID generation
- Triggers for auto-updating `updated_at`/`updatedAt`
- Indexes on foreign keys and common query columns
- Mixed naming convention (snake_case + camelCase)

**Current Access Pattern:**
- Backend: asyncpg + SQLAlchemy ORM (`backend/src/database.py`)
- Frontend: Prisma Client (`frontend/src/lib/prisma.ts`)

### 1.6 Current Dependencies (pyproject.toml)

**Cloud/Network Dependencies:**
- `assemblyai>=0.35.0` - Cloud transcription API
- `yt-dlp>=2025.7.21` - YouTube downloads (can work offline with local files)
- `openai-whisper>=20250625` - Offline transcription (not currently used)

**Docker/Infrastructure Dependencies:**
- `redis>=5.0.0` - In-memory data store
- `arq>=0.26.0` - Redis-based job queue
- `asyncpg>=0.29.0` - PostgreSQL async driver

**Video Processing (keep these):**
- `moviepy>=2.2.1` - Video editing
- `opencv-python>=4.8.0` - Face detection
- `mediapipe>=0.10.0` - Advanced face detection
- `srt>=3.5.3` - Subtitle formatting

**AI/ML (keep these):**
- `pydantic-ai>=0.4.9` - Transcript analysis
- `openai`, `anthropic`, `google-generativeai` - LLM APIs

### 1.7 Two Implementation Patterns

**Monolithic (`main.py`):**
- 655 lines, all endpoints in one file
- Synchronous and async processing endpoints
- Direct database queries inline

**Layered (`main_refactored.py`):**
- 128 lines, delegates to services
- Separation: API routes → Services → Repositories
- Uses arq worker for background processing
- Better separation of concerns

**Migration Decision:** Target the layered architecture but adapt worker pattern for local threads/processes.

---

## 2. Target State

### 2.1 Architecture Vision

**Native macOS Application:**
```
┌─────────────────────────────────────────────────────────┐
│                  Next.js Frontend                       │
│                  (Port 3000)                            │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/SSE
┌────────────────────┴────────────────────────────────────┐
│              FastAPI Backend (Port 8000)                │
│  ┌──────────────────────────────────────────────────┐  │
│  │  API Endpoints                                   │  │
│  │  - Video upload/processing                       │  │
│  │  - Task status (with SSE for real-time updates) │  │
│  │  - Clip retrieval                                │  │
│  └────────────┬─────────────────────────────────────┘  │
│               │                                         │
│  ┌────────────┴─────────────────────────────────────┐  │
│  │  Background Processing (threading/multiprocessing)│  │
│  │  - Video transcription (parakeet-MLX)            │  │
│  │  - AI analysis (Pydantic AI)                     │  │
│  │  - Clip generation (MoviePy)                     │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│              SQLite Database                            │
│  - Local file: supoclip.db                             │
│  - Same schema as PostgreSQL                           │
│  - No network overhead                                 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Key Changes

**No Docker:**
- Run frontend: `cd frontend && npm run dev`
- Run backend: `cd backend && uv run uvicorn src.main:app --reload`
- All processes managed by developer or process manager (PM2, systemd, etc.)

**Offline Transcription:**
- parakeet-MLX replaces AssemblyAI
- Models downloaded once, stored locally
- Runs on Apple Silicon's Neural Engine via MLX
- Word-level timestamps preserved (MLX supports this)

**Embedded Database:**
- SQLite replaces PostgreSQL
- Single file: `backend/supoclip.db`
- Async access via `aiosqlite` + SQLAlchemy
- Better Auth compatible (Prisma supports SQLite)

**In-Process Job Queue:**
- Python `asyncio.Queue` or `threading.Queue` replaces Redis/arq
- Or `python-multiprocessing` for CPU-heavy tasks
- Progress tracking via in-memory dict + SSE
- No external dependencies

### 2.3 Technology Stack (Post-Migration)

**Backend:**
- FastAPI (unchanged)
- parakeet-MLX (new) - Offline transcription
- SQLite + aiosqlite (replaces PostgreSQL)
- SQLAlchemy ORM (adapted for SQLite)
- MoviePy, OpenCV, MediaPipe (unchanged)
- Pydantic AI with local LLMs or API (unchanged)
- Python threading/multiprocessing (replaces arq)

**Frontend:**
- Next.js 15 (unchanged)
- Better Auth (works with SQLite)
- Prisma with SQLite provider (update schema)
- ShadCN UI + Tailwind (unchanged)

**System Requirements:**
- macOS (M1/M2/M3 recommended for MLX acceleration)
- Python 3.11+
- Node.js 18+
- ffmpeg (Homebrew: `brew install ffmpeg`)
- SQLite (built into Python)

---

## 3. Dependencies to Remove

### 3.1 Python Packages (backend/pyproject.toml)

**Remove:**
```toml
"assemblyai>=0.35.0",     # Cloud transcription API
"redis>=5.0.0",           # Redis client
"arq>=0.26.0",            # Redis job queue
"asyncpg>=0.29.0",        # PostgreSQL driver
```

**Optional Remove (if not using cloud LLMs):**
```toml
# Keep if using OpenAI/Anthropic for AI analysis
# Remove if switching to local LLMs
```

### 3.2 Docker Files

**Delete:**
- `docker-compose.yml` - Orchestration config
- `backend/Dockerfile` - Backend container
- `frontend/Dockerfile` - Frontend container
- `init.sql` - PostgreSQL initialization (replace with SQLite schema)

**Keep (for reference or future Docker support):**
- Move to `archive/docker/` for potential future use

### 3.3 Configuration Files

**Remove/Modify:**
- `.env.example` - Remove ASSEMBLY_AI_API_KEY, REDIS_HOST, REDIS_PORT, DATABASE_URL (PostgreSQL)
- `backend/src/config.py` - Remove Redis and AssemblyAI config

### 3.4 Code Files

**Delete (if refactored pattern not used):**
- `backend/src/workers/job_queue.py` - arq wrapper
- `backend/src/workers/progress.py` - Redis progress tracking

**Modify (adapt for local processing):**
- `backend/src/workers/tasks.py` - Convert to local async tasks

---

## 4. Dependencies to Add

### 4.1 Python Packages

**Add to backend/pyproject.toml:**
```toml
dependencies = [
    # Existing (keep)
    "fastapi>=0.110.0",
    "uvicorn>=0.27.0",
    "pydantic-ai>=0.4.9",
    "sqlalchemy>=2.0.25",
    "alembic>=1.13.0",
    "python-dotenv>=1.0.0",
    "yt-dlp>=2025.7.21",
    "moviepy>=2.2.1",
    "opencv-python>=4.8.0",
    "mediapipe>=0.10.0",
    "numpy>=1.24.0",
    "aiofiles>=23.2.0",
    "sse-starlette>=1.6.5",
    "srt>=3.5.3",
    
    # NEW: Transcription
    "mlx-whisper>=0.3.0",          # MLX-optimized Whisper for Apple Silicon
    # OR "parakeet-tdt-mlx>=1.0.0", # If using parakeet specifically
    
    # NEW: Database
    "aiosqlite>=0.19.0",           # Async SQLite driver
    # SQLAlchemy already included, works with SQLite
    
    # NEW: Optional local LLM support
    "mlx-lm>=0.2.0",               # If using local MLX-based LLMs
    
    # Remove: assemblyai, redis, arq, asyncpg
]
```

### 4.2 MLX Installation

**Prerequisites:**
```bash
# Ensure Mac has Apple Silicon (M1/M2/M3)
uname -m  # Should show "arm64"

# MLX requires macOS 13.5+ (Ventura or Sonnet)
sw_vers
```

**Installation:**
```bash
cd backend
uv pip install mlx-whisper  # or parakeet-tdt-mlx
uv pip install aiosqlite
```

**Model Download (one-time):**
```bash
# MLX Whisper models are downloaded automatically on first use
# They're cached in ~/.cache/mlx/ or similar
# For manual pre-download:
python -c "import mlx_whisper; mlx_whisper.load_models('medium')"
```

### 4.3 Frontend Changes

**Update frontend/prisma/schema.prisma:**
```prisma
datasource db {
  provider = "sqlite"  // Changed from "postgresql"
  url      = env("DATABASE_URL")
}

// Rest of schema remains similar
// SQLite uses INTEGER PRIMARY KEY for auto-increment
// Change VARCHAR to TEXT where needed
```

**Update .env:**
```bash
DATABASE_URL="file:../backend/supoclip.db"
```

### 4.4 System Dependencies

**Homebrew (if not already installed):**
```bash
# ffmpeg (already required)
brew install ffmpeg

# Optional: SQLite browser for database inspection
brew install --cask db-browser-for-sqlite
```

---

## 5. Step-by-Step Migration Path

### Phase 1: Preparation (Day 1, Morning)

**Step 1.1: Backup Current System**
```bash
# Backup Docker volumes (if any important data)
docker-compose exec postgres pg_dump -U supoclip supoclip > backup_postgres.sql

# Backup Redis data (if needed)
docker-compose exec redis redis-cli SAVE
docker cp supoclip-redis:/data/dump.rdb backup_redis.rdb

# Archive Docker files
mkdir -p archive/docker
mv docker-compose.yml archive/docker/
mv backend/Dockerfile archive/docker/backend-Dockerfile
mv frontend/Dockerfile archive/docker/frontend-Dockerfile
```

**Step 1.2: Create Feature Branch**
```bash
git checkout -b feature/mlx-no-docker-migration
git add -A
git commit -m "Backup: Archive Docker infrastructure before migration"
```

**Step 1.3: Document Current State**
```bash
# Export current dependencies
cd backend
uv pip freeze > requirements_pre_migration.txt
cd ../frontend
npm list --depth=0 > packages_pre_migration.txt
```

### Phase 2: Database Migration (Day 1, Afternoon)

**Step 2.1: Create SQLite Schema**
```bash
cd backend
touch supoclip.db
```

Create `backend/migrations/sqlite_schema.sql`:
```sql
-- SQLite schema based on init.sql
-- Main differences: No UUID extension, use TEXT for UUIDs, INTEGER PRIMARY KEY for auto-increment

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    emailVerified INTEGER NOT NULL DEFAULT 0,  -- SQLite uses 0/1 for boolean
    image TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    first_name TEXT,
    last_name TEXT,
    password_hash TEXT,
    default_font_family TEXT DEFAULT 'TikTokSans-Regular',
    default_font_size INTEGER DEFAULT 24,
    default_font_color TEXT DEFAULT '#FFFFFF'
);

-- (Similar conversions for other tables)
-- See detailed schema in Section 7
```

**Step 2.2: Update SQLAlchemy Engine**

Edit `backend/src/database.py`:
```python
import os
from dotenv import load_dotenv
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import aiosqlite  # NEW

load_dotenv()

# SQLite database (local file)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./supoclip.db"  # Changed from PostgreSQL
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # SQLite-specific settings
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    # For SQLite, create tables from models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await engine.dispose()
```

**Step 2.3: Update Prisma Schema**

Edit `frontend/prisma/schema.prisma`:
```prisma
datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}

// Update models for SQLite compatibility
// Main changes:
// - Remove Uuid type, use String
// - Change @db.VarChar to @db.Text or remove
// - Update array types (SQLite doesn't have native arrays)
```

**Step 2.4: Run Migrations**
```bash
# Backend
cd backend
uv run alembic revision --autogenerate -m "Convert to SQLite schema"
uv run alembic upgrade head

# Frontend
cd ../frontend
npx prisma generate
npx prisma db push  # Or prisma migrate dev
```

### Phase 3: Remove Redis/arq (Day 2, Morning)

**Step 3.1: Create In-Process Queue**

Create `backend/src/workers/local_queue.py`:
```python
"""
Local async queue for background tasks (replaces Redis/arq).
Uses asyncio.Queue for lightweight job processing.
"""
import asyncio
import logging
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

@dataclass
class Job:
    """Represents a background job."""
    job_id: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: str = "queued"  # queued, processing, completed, error
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class LocalJobQueue:
    """Async job queue using asyncio (no Redis required)."""
    
    def __init__(self, max_workers: int = 2):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.jobs: Dict[str, Job] = {}  # In-memory job storage
        self.max_workers = max_workers
        self.workers: list = []
        self._running = False
    
    async def start_workers(self):
        """Start background worker tasks."""
        if self._running:
            return
        
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} local workers")
    
    async def stop_workers(self):
        """Stop all workers gracefully."""
        self._running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Stopped all local workers")
    
    async def _worker(self, name: str):
        """Worker coroutine that processes jobs from the queue."""
        logger.info(f"Worker {name} started")
        
        while self._running:
            try:
                job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                logger.info(f"Worker {name} processing job {job.job_id}")
                job.status = "processing"
                job.started_at = datetime.now()
                
                try:
                    # Execute the job function
                    result = await job.function(*job.args, **job.kwargs)
                    job.result = result
                    job.status = "completed"
                    logger.info(f"Job {job.job_id} completed successfully")
                
                except Exception as e:
                    job.error = str(e)
                    job.status = "error"
                    logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)
                
                finally:
                    job.completed_at = datetime.now()
                    self.queue.task_done()
            
            except asyncio.TimeoutError:
                continue  # No jobs in queue, keep waiting
            except asyncio.CancelledError:
                logger.info(f"Worker {name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}", exc_info=True)
    
    async def enqueue_job(self, function: Callable, *args, **kwargs) -> str:
        """
        Enqueue a job to be processed by workers.
        
        Args:
            function: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            function=function,
            args=args,
            kwargs=kwargs
        )
        
        self.jobs[job_id] = job
        await self.queue.put(job)
        
        logger.info(f"Enqueued job {job_id}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get job status."""
        job = self.get_job(job_id)
        return job.status if job else None
    
    def get_job_result(self, job_id: str) -> Any:
        """Get job result (if completed)."""
        job = self.get_job(job_id)
        if job and job.status == "completed":
            return job.result
        return None


# Global queue instance
_job_queue: Optional[LocalJobQueue] = None

def get_job_queue() -> LocalJobQueue:
    """Get or create the global job queue."""
    global _job_queue
    if _job_queue is None:
        _job_queue = LocalJobQueue(max_workers=2)
    return _job_queue
```

**Step 3.2: Create In-Memory Progress Tracker**

Create `backend/src/workers/local_progress.py`:
```python
"""
In-memory progress tracking (replaces Redis pub/sub).
"""
import asyncio
import logging
from typing import Dict, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@dataclass
class Progress:
    """Progress information for a task."""
    task_id: str
    progress: int  # 0-100
    message: str
    status: str  # queued, processing, completed, error
    updated_at: datetime = field(default_factory=datetime.now)


class LocalProgressTracker:
    """In-memory progress tracking with async notification."""
    
    def __init__(self):
        self.progress_data: Dict[str, Progress] = {}
        self.subscribers: Dict[str, list] = {}  # task_id -> list of asyncio.Queue
    
    async def update(self, task_id: str, progress: int, message: str, status: str = "processing"):
        """Update progress for a task."""
        prog = Progress(
            task_id=task_id,
            progress=progress,
            message=message,
            status=status,
            updated_at=datetime.now()
        )
        
        self.progress_data[task_id] = prog
        
        # Notify all subscribers
        if task_id in self.subscribers:
            for queue in self.subscribers[task_id]:
                try:
                    await queue.put(prog)
                except Exception as e:
                    logger.warning(f"Failed to notify subscriber: {e}")
        
        logger.debug(f"Progress update for {task_id}: {progress}% - {message}")
    
    def get(self, task_id: str) -> Optional[Progress]:
        """Get current progress."""
        return self.progress_data.get(task_id)
    
    async def complete(self, task_id: str, message: str = "Complete!"):
        """Mark task as completed."""
        await self.update(task_id, 100, message, "completed")
    
    async def error(self, task_id: str, message: str):
        """Mark task as failed."""
        await self.update(task_id, 0, message, "error")
    
    async def subscribe(self, task_id: str) -> AsyncGenerator[Progress, None]:
        """
        Subscribe to progress updates for a task.
        Yields progress updates as they occur.
        """
        queue = asyncio.Queue()
        
        # Add subscriber
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        self.subscribers[task_id].append(queue)
        
        try:
            # Send current progress if exists
            current = self.get(task_id)
            if current:
                yield current
            
            # Wait for updates
            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=60.0)
                    yield progress
                    
                    # Stop if completed or errored
                    if progress.status in ["completed", "error"]:
                        break
                
                except asyncio.TimeoutError:
                    # Send keep-alive
                    current = self.get(task_id)
                    if current:
                        yield current
        
        finally:
            # Remove subscriber
            if task_id in self.subscribers:
                try:
                    self.subscribers[task_id].remove(queue)
                except ValueError:
                    pass


# Global tracker instance
_progress_tracker: Optional[LocalProgressTracker] = None

def get_progress_tracker() -> LocalProgressTracker:
    """Get or create the global progress tracker."""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = LocalProgressTracker()
    return _progress_tracker
```

**Step 3.3: Update Worker Tasks**

Edit `backend/src/workers/tasks.py` to use local queue:
```python
"""
Background tasks for video processing (local async version).
"""
import logging
from pathlib import Path
from typing import Dict, Any

from ..video_utils import (
    get_video_transcript,
    create_optimized_clip,
    # ... other imports
)
from ..ai import get_most_relevant_parts_by_transcript
from .local_queue import get_job_queue
from .local_progress import get_progress_tracker

logger = logging.getLogger(__name__)

async def process_video_task(
    task_id: str,
    video_path: str,
    user_id: str,
    font_options: Dict[str, Any],
    # ... other params
):
    """
    Process video in background (replaces arq worker function).
    """
    tracker = get_progress_tracker()
    
    try:
        await tracker.update(task_id, 10, "Starting video processing...")
        
        # 1. Transcribe with parakeet-MLX
        await tracker.update(task_id, 20, "Transcribing video...")
        transcript_data = await get_video_transcript(Path(video_path))
        
        # 2. AI analysis
        await tracker.update(task_id, 40, "Analyzing transcript for viral segments...")
        segments = await get_most_relevant_parts_by_transcript(transcript_data)
        
        # 3. Generate clips
        await tracker.update(task_id, 60, "Generating clips...")
        # ... clip generation logic
        
        await tracker.complete(task_id, "Video processing complete!")
        
        return {"status": "completed", "clips_count": len(segments)}
    
    except Exception as e:
        logger.error(f"Video processing failed for task {task_id}: {e}", exc_info=True)
        await tracker.error(task_id, f"Error: {str(e)}")
        raise
```

**Step 3.4: Remove Old Redis Files**
```bash
# Delete (or move to archive)
rm backend/src/workers/job_queue.py
rm backend/src/workers/progress.py
```

### Phase 4: Replace AssemblyAI with parakeet-MLX (Day 2, Afternoon)

**Step 4.1: Install and Test MLX Whisper**
```bash
cd backend
uv pip install mlx-whisper

# Test installation
python -c "import mlx_whisper; print(mlx_whisper.__version__)"

# Download medium model (recommended balance of speed/accuracy)
python -c "import mlx_whisper; mlx_whisper.load_models('medium')"
```

**Step 4.2: Create MLX Transcription Module**

Create `backend/src/transcription_mlx.py`:
```python
"""
Video transcription using MLX Whisper (offline, Apple Silicon optimized).
Replaces AssemblyAI cloud API.
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import mlx_whisper
from .config import Config

logger = logging.getLogger(__name__)
config = Config()


def transcribe_video_mlx(video_path: Path, model_size: str = "medium") -> Dict[str, Any]:
    """
    Transcribe video using MLX Whisper (offline).
    
    Args:
        video_path: Path to video file
        model_size: Model size (tiny, base, small, medium, large)
    
    Returns:
        Dict with:
            - text: Full transcript text
            - words: List of word-level timestamps
            - segments: List of sentence/phrase segments
    """
    logger.info(f"Transcribing video with MLX Whisper ({model_size}): {video_path}")
    
    # Check cache first
    cache_path = video_path.parent / f"{video_path.stem}.transcript_cache.json"
    if cache_path.exists():
        logger.info(f"Loading cached transcript: {cache_path}")
        with open(cache_path, 'r') as f:
            return json.load(f)
    
    try:
        # MLX Whisper transcription
        result = mlx_whisper.transcribe(
            str(video_path),
            path_or_hf_repo=f"mlx-community/whisper-{model_size}",
            word_timestamps=True,  # Enable word-level timing (like AssemblyAI)
            language="en",  # Or detect automatically
            fp16=False,  # MLX uses native precision
        )
        
        # Format result to match AssemblyAI structure
        formatted_result = {
            "text": result["text"],
            "segments": result["segments"],
            "words": _extract_words_from_segments(result["segments"]),
            "language": result.get("language", "en"),
        }
        
        # Cache for future use
        with open(cache_path, 'w') as f:
            json.dump(formatted_result, f, indent=2)
        
        logger.info(f"Transcription complete. Word count: {len(formatted_result['words'])}")
        return formatted_result
    
    except Exception as e:
        logger.error(f"MLX transcription failed: {e}", exc_info=True)
        raise


def _extract_words_from_segments(segments: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract word-level timestamps from Whisper segments.
    Formats to match AssemblyAI structure.
    """
    words = []
    
    for segment in segments:
        if "words" in segment:
            for word_data in segment["words"]:
                words.append({
                    "text": word_data["word"].strip(),
                    "start": int(word_data["start"] * 1000),  # Convert to milliseconds
                    "end": int(word_data["end"] * 1000),
                    "confidence": word_data.get("probability", 1.0),
                })
    
    return words


def get_video_transcript_mlx(video_path: Path) -> str:
    """
    Get full transcript text from video.
    Convenience wrapper for transcribe_video_mlx.
    """
    result = transcribe_video_mlx(video_path)
    return result["text"]


def load_cached_transcript_mlx(video_path: Path) -> Optional[Dict[str, Any]]:
    """Load cached transcript if available."""
    cache_path = video_path.parent / f"{video_path.stem}.transcript_cache.json"
    
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached transcript: {e}")
    
    return None
```

**Step 4.3: Update video_utils.py**

Edit `backend/src/video_utils.py`:
```python
# Replace AssemblyAI import with MLX
# OLD:
# import assemblyai as aai

# NEW:
from .transcription_mlx import (
    transcribe_video_mlx,
    get_video_transcript_mlx,
    load_cached_transcript_mlx,
)

# Update function: get_video_transcript()
def get_video_transcript(path: Path) -> Dict[str, Any]:
    """
    Get video transcript with word-level timing using MLX Whisper.
    """
    logger.info(f"Transcribing video: {path}")
    
    # Use MLX instead of AssemblyAI
    transcript_data = transcribe_video_mlx(path, model_size=config.whisper_model)
    
    return transcript_data

# Update function: load_cached_transcript_data()
def load_cached_transcript_data(video_path: Path) -> Optional[Dict[str, Any]]:
    """Load cached transcript data if available."""
    return load_cached_transcript_mlx(video_path)

# Update function: create_assemblyai_subtitles()
# Rename to: create_mlx_subtitles() or just create_subtitles()
def create_subtitles(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_width: int,
    video_height: int,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF"
) -> List[TextClip]:
    """
    Create subtitles using MLX Whisper's precise word timing.
    (Formerly create_assemblyai_subtitles)
    """
    transcript_data = load_cached_transcript_data(video_path)
    
    if not transcript_data or not transcript_data.get('words'):
        logger.warning("No cached transcript data available for subtitles")
        return []
    
    # Rest of logic unchanged - word-level timing structure is compatible
    # ...

# Update all references from create_assemblyai_subtitles to create_subtitles
```

**Step 4.4: Update config.py**

Edit `backend/src/config.py`:
```python
class Config:
    def __init__(self):
        # Remove AssemblyAI
        # self.assembly_ai_api_key = os.getenv("ASSEMBLY_AI_API_KEY")
        
        # Update Whisper model (now for MLX)
        self.whisper_model = os.getenv("WHISPER_MODEL", "medium")  # tiny, base, small, medium, large
        
        # LLM config (unchanged)
        self.llm = os.getenv("LLM_MODEL", "google-gla:gemini-2.5-flash-lite")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        
        # Remove Redis
        # self.redis_host = os.getenv("REDIS_HOST", "localhost")
        # self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        
        # Other config unchanged
        self.max_video_duration = int(os.getenv("MAX_VIDEO_DURATION", "3600"))
        self.output_dir = os.getenv("OUTPUT_DIR", "outputs")
        self.temp_dir = os.getenv("TEMP_DIR", "temp")
        self.max_clips = int(os.getenv("MAX_CLIPS", "10"))
        self.clip_duration = int(os.getenv("CLIP_DURATION", "30"))
```

### Phase 5: Update Backend Application (Day 3, Morning)

**Step 5.1: Update main.py (or main_refactored.py)**

Edit `backend/src/main.py`:
```python
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
from pathlib import Path
import logging

from .database import get_db, init_db, close_db, AsyncSessionLocal
from .workers.local_queue import get_job_queue, LocalJobQueue
from .workers.local_progress import get_progress_tracker, LocalProgressTracker
from .workers.tasks import process_video_task
from .config import Config

logger = logging.getLogger(__name__)
config = Config()

# Initialize FastAPI
app = FastAPI(title="SupoClip Backend", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
job_queue: Optional[LocalJobQueue] = None
progress_tracker: Optional[LocalProgressTracker] = None

@app.on_event("startup")
async def startup_event():
    """Initialize database and workers on startup."""
    global job_queue, progress_tracker
    
    logger.info("Starting SupoClip backend...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start local job queue workers
    job_queue = get_job_queue()
    await job_queue.start_workers()
    logger.info("Job queue workers started")
    
    # Initialize progress tracker
    progress_tracker = get_progress_tracker()
    logger.info("Progress tracker initialized")
    
    # Create necessary directories
    Path(config.temp_dir).mkdir(parents=True, exist_ok=True)
    Path("clips").mkdir(exist_ok=True)
    Path("uploads").mkdir(exist_ok=True)
    logger.info("Directories created")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global job_queue
    
    logger.info("Shutting down SupoClip backend...")
    
    if job_queue:
        await job_queue.stop_workers()
    
    await close_db()
    logger.info("Shutdown complete")

# Health check
@app.get("/health")
async def health_check():
    """Simple health check."""
    return {"status": "healthy", "database": "sqlite", "transcription": "mlx-whisper"}

@app.get("/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """Database health check."""
    try:
        # Simple query to verify DB connection
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable")

# Video processing endpoint (async with progress tracking)
@app.post("/start-with-progress")
async def start_video_processing_with_progress(request: VideoProcessingRequest):
    """
    Start video processing in background and return task_id for progress tracking.
    """
    global job_queue, progress_tracker
    
    # Validate request
    # ... (similar to current implementation)
    
    # Create task in database
    task_id = str(uuid.uuid4())
    # ... (insert task into SQLite)
    
    # Enqueue job
    job_id = await job_queue.enqueue_job(
        process_video_task,
        task_id=task_id,
        video_path=str(video_path),
        user_id=request.user_id,
        font_options=request.font_options.dict(),
    )
    
    logger.info(f"Enqueued video processing job: {job_id} for task: {task_id}")
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Video processing started"
    }

# SSE endpoint for real-time progress
@app.get("/tasks/{task_id}/progress")
async def stream_task_progress(task_id: str):
    """
    Server-Sent Events endpoint for real-time progress updates.
    """
    global progress_tracker
    
    async def event_generator():
        """Generate SSE events for progress updates."""
        async for progress in progress_tracker.subscribe(task_id):
            yield {
                "event": "progress",
                "data": json.dumps({
                    "task_id": progress.task_id,
                    "progress": progress.progress,
                    "message": progress.message,
                    "status": progress.status,
                })
            }
            
            # Stop streaming if completed or errored
            if progress.status in ["completed", "error"]:
                break
    
    return EventSourceResponse(event_generator())

# ... (rest of endpoints: /tasks/{id}, /clips/{filename}, /fonts, /transitions, etc.)
```

**Step 5.2: Update Service Layer (if using main_refactored.py)**

Edit `backend/src/services/video_service.py`:
```python
# Replace Redis/arq imports with local queue
from ..workers.local_queue import get_job_queue
from ..workers.local_progress import get_progress_tracker

# Update methods to use local queue instead of arq
async def enqueue_video_processing(self, task_id: str, video_path: Path, ...):
    """Enqueue video processing job."""
    queue = get_job_queue()
    job_id = await queue.enqueue_job(
        process_video_task,
        task_id=task_id,
        video_path=str(video_path),
        # ... other args
    )
    return job_id
```

### Phase 6: Update Frontend (Day 3, Afternoon)

**Step 6.1: Update Environment Configuration**

Edit `frontend/.env`:
```bash
# SQLite database (file path relative to project root)
DATABASE_URL="file:../backend/supoclip.db"

# Better Auth (unchanged)
BETTER_AUTH_SECRET=your_secret_here
BETTER_AUTH_URL=http://localhost:3000

# Backend API (unchanged)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Step 6.2: Regenerate Prisma Client**
```bash
cd frontend
npx prisma generate
npx prisma db push
```

**Step 6.3: Update API Clients (if needed)**

Frontend API calls should remain mostly unchanged since backend endpoints maintain compatibility.

Check `frontend/src/app/tasks/[id]/page.tsx` for SSE usage:
```typescript
// Should still work with local progress tracking
const eventSource = new EventSource(`${API_URL}/tasks/${taskId}/progress`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update UI with progress
};
```

### Phase 7: Testing and Validation (Day 4)

**Step 7.1: Unit Tests**
```bash
# Backend tests
cd backend
uv run pytest tests/ -v

# Test MLX transcription specifically
uv run pytest tests/test_transcription_mlx.py -v

# Test local queue
uv run pytest tests/test_local_queue.py -v
```

**Step 7.2: Integration Tests**

Create `backend/tests/test_integration_offline.py`:
```python
"""
Integration tests for offline operation.
"""
import pytest
from pathlib import Path
import asyncio
from src.transcription_mlx import transcribe_video_mlx
from src.workers.local_queue import LocalJobQueue
from src.workers.local_progress import LocalProgressTracker

@pytest.mark.asyncio
async def test_offline_transcription():
    """Test MLX transcription works offline."""
    # Use a small test video
    video_path = Path("tests/fixtures/test_video.mp4")
    
    # Disconnect network (manual step)
    result = transcribe_video_mlx(video_path, model_size="tiny")
    
    assert result is not None
    assert "text" in result
    assert "words" in result
    assert len(result["words"]) > 0

@pytest.mark.asyncio
async def test_local_job_queue():
    """Test local job queue works without Redis."""
    queue = LocalJobQueue(max_workers=1)
    await queue.start_workers()
    
    async def sample_task(x, y):
        await asyncio.sleep(0.1)
        return x + y
    
    job_id = await queue.enqueue_job(sample_task, 5, 3)
    
    # Wait for completion
    await asyncio.sleep(0.5)
    
    status = queue.get_job_status(job_id)
    assert status == "completed"
    
    result = queue.get_job_result(job_id)
    assert result == 8
    
    await queue.stop_workers()

@pytest.mark.asyncio
async def test_progress_tracking():
    """Test in-memory progress tracking."""
    tracker = LocalProgressTracker()
    
    task_id = "test-task-123"
    
    # Update progress
    await tracker.update(task_id, 50, "Halfway done", "processing")
    
    # Check progress
    progress = tracker.get(task_id)
    assert progress is not None
    assert progress.progress == 50
    assert progress.message == "Halfway done"
    assert progress.status == "processing"
```

**Step 7.3: Manual Testing Checklist**

1. **Backend Startup**
   ```bash
   cd backend
   uv run uvicorn src.main:app --reload
   # Should start without errors
   # Check logs for "Job queue workers started"
   ```

2. **Frontend Startup**
   ```bash
   cd frontend
   npm run dev
   # Should connect to SQLite database
   # No Prisma connection errors
   ```

3. **Video Upload and Processing**
   - Upload a short video (< 1 min)
   - Check task status updates in real-time
   - Verify MLX transcription runs offline (disconnect WiFi)
   - Confirm clips are generated correctly

4. **Database Operations**
   - Create user account
   - Check tasks persist in SQLite
   - Verify clips metadata is saved

5. **Offline Operation**
   - Disconnect internet
   - Upload local video file
   - Process video (should work completely offline)
   - Only LLM API call should fail (if using cloud LLMs)

**Step 7.4: Performance Benchmarks**

Compare old vs. new:
```bash
# Measure transcription time
# OLD (AssemblyAI): ~30 sec for 5-min video (network + API processing)
# NEW (MLX): ~10-20 sec for 5-min video (local processing)

# Measure startup time
# OLD (Docker): ~30-60 sec to start all containers
# NEW (Native): ~5-10 sec to start backend + frontend

# Measure memory usage
# OLD (Docker): ~2-3 GB (all containers)
# NEW (Native): ~500 MB - 1 GB (backend + frontend)
```

### Phase 8: Documentation and Cleanup (Day 5)

**Step 8.1: Update README.md**
```markdown
# SupoClip - Native macOS Version

## Requirements
- macOS 13.5+ (Ventura or later)
- Apple Silicon (M1/M2/M3) recommended
- Python 3.11+
- Node.js 18+
- ffmpeg (install via Homebrew)

## Quick Start (No Docker)

1. **Install Dependencies**
   ```bash
   # Install ffmpeg
   brew install ffmpeg
   
   # Backend
   cd backend
   uv venv .venv
   source .venv/bin/activate
   uv sync
   
   # Frontend
   cd ../frontend
   npm install
   ```

2. **Setup Database**
   ```bash
   # Backend (SQLite auto-creates)
   cd backend
   uv run alembic upgrade head
   
   # Frontend (Prisma)
   cd frontend
   npx prisma generate
   npx prisma db push
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env - only LLM API keys needed, no AssemblyAI/Redis
   ```

4. **Run Application**
   ```bash
   # Terminal 1: Backend
   cd backend
   uv run uvicorn src.main:app --reload
   
   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

5. **Access Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Offline Operation

SupoClip works completely offline after initial setup:
- ✅ Video transcription (MLX Whisper)
- ✅ Video processing (MoviePy + OpenCV)
- ✅ Database operations (SQLite)
- ❌ AI segment analysis (requires LLM API - consider local MLX-LM)

To enable 100% offline:
- Install local LLM via MLX-LM
- Update `config.py` to use local model
```

**Step 8.2: Update CLAUDE.md**

Add migration notes section:
```markdown
## Migration History

### 2025-11-14: Native macOS Version (v2.0)

**Major Changes:**
- Removed all Docker infrastructure
- Replaced AssemblyAI with MLX Whisper (offline transcription)
- Replaced PostgreSQL with SQLite
- Replaced Redis/arq with local asyncio queue
- Optimized for Apple Silicon via MLX

**Breaking Changes:**
- Docker commands no longer work
- Environment variables changed (no REDIS_*, ASSEMBLY_AI_*)
- Database connection string changed to SQLite

**Migration Guide:** See `docs/progress/fixes/migration-mlx-no-docker-2025-11-14.md`
```

**Step 8.3: Create Startup Scripts**

Create `start-dev.sh` in project root:
```bash
#!/bin/bash
# Start SupoClip in development mode (native macOS)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting SupoClip (Native macOS)...${NC}"

# Check prerequisites
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not installed. Run: brew install ffmpeg"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "Error: uv not installed. Run: pip install uv"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Error: Node.js not installed"; exit 1; }

# Start backend in background
echo -e "${GREEN}Starting backend...${NC}"
cd backend
source .venv/bin/activate 2>/dev/null || { echo "Virtual environment not found. Run: uv venv .venv && uv sync"; exit 1; }
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
cd ..

# Wait for backend to start
sleep 5

# Start frontend in background
echo -e "${GREEN}Starting frontend...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd ..

echo ""
echo -e "${GREEN}✅ SupoClip is running!${NC}"
echo "Frontend: http://localhost:3000"
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To stop: kill $BACKEND_PID $FRONTEND_PID"
echo "Or run: ./stop-dev.sh"

# Save PIDs for stop script
echo "$BACKEND_PID" > .backend.pid
echo "$FRONTEND_PID" > .frontend.pid

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
```

Create `stop-dev.sh`:
```bash
#!/bin/bash
# Stop SupoClip development servers

if [ -f .backend.pid ]; then
    BACKEND_PID=$(cat .backend.pid)
    echo "Stopping backend (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || true
    rm .backend.pid
fi

if [ -f .frontend.pid ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    echo "Stopping frontend (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null || true
    rm .frontend.pid
fi

echo "✅ SupoClip stopped"
```

Make executable:
```bash
chmod +x start-dev.sh stop-dev.sh
```

**Step 8.4: Final Commit**
```bash
git add -A
git commit -m "feat: Migrate to native macOS with MLX transcription

- Remove Docker infrastructure (docker-compose.yml, Dockerfiles)
- Replace AssemblyAI with MLX Whisper for offline transcription
- Replace PostgreSQL with SQLite for embedded database
- Replace Redis/arq with local asyncio job queue
- Add in-memory progress tracking
- Optimize for Apple Silicon via MLX
- Update documentation and startup scripts

BREAKING CHANGE: Docker deployment no longer supported.
Use native macOS installation (see README.md).
"
```

---

## 6. Code Changes by Module

### 6.1 Backend Configuration

**File: `backend/src/config.py`**
```python
# BEFORE
class Config:
    def __init__(self):
        self.assembly_ai_api_key = os.getenv("ASSEMBLY_AI_API_KEY")  # REMOVE
        self.redis_host = os.getenv("REDIS_HOST", "localhost")  # REMOVE
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))  # REMOVE

# AFTER
class Config:
    def __init__(self):
        self.whisper_model = os.getenv("WHISPER_MODEL", "medium")  # ADD
        # Redis and AssemblyAI config removed
```

### 6.2 Database Layer

**File: `backend/src/database.py`**
```python
# BEFORE
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://localhost:5432/supoclip"
)
engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, ...)

# AFTER
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./supoclip.db"
)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
```

### 6.3 Transcription Module

**File: `backend/src/video_utils.py`**
```python
# BEFORE (lines 17, 65-80, 475-520, 817-819)
import assemblyai as aai

aai.settings.api_key = config.assembly_ai_api_key
transcriber = aai.Transcriber()
transcript = transcriber.transcribe(str(path), config=config_obj)

def create_assemblyai_subtitles(...):
    # Uses aai transcript data

def get_video_transcript_with_assemblyai(path: Path) -> str:
    return get_video_transcript(path)

# AFTER
from .transcription_mlx import (
    transcribe_video_mlx,
    get_video_transcript_mlx,
    load_cached_transcript_mlx,
)

transcript_data = transcribe_video_mlx(path, model_size=config.whisper_model)

def create_subtitles(...):  # Renamed
    # Uses MLX transcript data (same structure as AssemblyAI)

def get_video_transcript(path: Path) -> Dict[str, Any]:
    return transcribe_video_mlx(path)
```

**New File: `backend/src/transcription_mlx.py`**
- ~150 lines
- Functions: `transcribe_video_mlx()`, `get_video_transcript_mlx()`, `load_cached_transcript_mlx()`
- MLX Whisper integration with word-level timestamps

### 6.4 Job Queue System

**File: `backend/src/workers/job_queue.py` - DELETE or ARCHIVE**

**New File: `backend/src/workers/local_queue.py`**
- ~200 lines
- Class: `LocalJobQueue` with methods: `start_workers()`, `enqueue_job()`, `get_job()`, `get_job_status()`
- Uses `asyncio.Queue` instead of Redis

**File: `backend/src/workers/progress.py` - DELETE or ARCHIVE**

**New File: `backend/src/workers/local_progress.py`**
- ~150 lines
- Class: `LocalProgressTracker` with methods: `update()`, `get()`, `subscribe()`
- In-memory dict + asyncio.Queue for pub/sub

### 6.5 Worker Tasks

**File: `backend/src/workers/tasks.py`**
```python
# BEFORE
from arq import create_pool
from ..workers.job_queue import JobQueue, ARQ_REDIS_SETTINGS
from redis.asyncio import Redis

async def process_video(ctx: dict, task_id: str, ...):
    redis: Redis = ctx['redis']
    # Use Redis for progress

# AFTER
from ..workers.local_queue import get_job_queue
from ..workers.local_progress import get_progress_tracker

async def process_video_task(task_id: str, ...):
    tracker = get_progress_tracker()
    await tracker.update(task_id, 10, "Starting...")
    # No ctx or Redis dependency
```

### 6.6 Main Application

**File: `backend/src/main.py`**
```python
# BEFORE
from redis.asyncio import Redis
from arq import create_pool

redis_pool = None

@app.on_event("startup")
async def startup():
    global redis_pool
    redis_pool = await create_pool(...)

# AFTER
from .workers.local_queue import get_job_queue
from .workers.local_progress import get_progress_tracker

job_queue = None

@app.on_event("startup")
async def startup():
    global job_queue
    job_queue = get_job_queue()
    await job_queue.start_workers()
```

### 6.7 API Routes

**File: `backend/src/api/routes/tasks.py`**
```python
# BEFORE
from ...workers.job_queue import JobQueue

router = APIRouter()

@router.post("/start-with-progress")
async def start_processing(...):
    job_id = await JobQueue.enqueue_job("process_video", task_id, ...)

# AFTER
from ...workers.local_queue import get_job_queue

@router.post("/start-with-progress")
async def start_processing(...):
    queue = get_job_queue()
    job_id = await queue.enqueue_job(process_video_task, task_id, ...)
```

### 6.8 Frontend Database

**File: `frontend/prisma/schema.prisma`**
```prisma
// BEFORE
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id String @id @default(uuid()) @db.Uuid
  // ...
}

// AFTER
datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}

model User {
  id String @id @default(uuid())  // Remove @db.Uuid
  // ...
}
```

### 6.9 Dependencies

**File: `backend/pyproject.toml`**
```toml
# REMOVE
"assemblyai>=0.35.0",
"redis>=5.0.0",
"arq>=0.26.0",
"asyncpg>=0.29.0",

# ADD
"mlx-whisper>=0.3.0",
"aiosqlite>=0.19.0",

# KEEP (unchanged)
"fastapi>=0.110.0",
"uvicorn>=0.27.0",
"pydantic-ai>=0.4.9",
"sqlalchemy>=2.0.25",
# ... (rest of video processing libs)
```

---

## 7. Database Migration

### 7.1 PostgreSQL to SQLite Schema Conversion

**Key Differences:**
1. **UUIDs:** PostgreSQL has native UUID type, SQLite uses TEXT
2. **Booleans:** PostgreSQL has BOOLEAN, SQLite uses INTEGER (0/1)
3. **Arrays:** PostgreSQL has array types, SQLite requires JSON or separate table
4. **Auto-increment:** PostgreSQL uses SERIAL/uuid_generate_v4(), SQLite uses INTEGER PRIMARY KEY or randomblob()
5. **Timestamps:** Both support TIMESTAMP, but SQLite uses DATETIME

**SQLite Schema (init_sqlite.sql):**
```sql
-- SupoClip SQLite Schema
-- Converted from PostgreSQL (init.sql)

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    emailVerified INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
    image TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    first_name TEXT,
    last_name TEXT,
    password_hash TEXT,
    default_font_family TEXT DEFAULT 'TikTokSans-Regular',
    default_font_size INTEGER DEFAULT 24,
    default_font_color TEXT DEFAULT '#FFFFFF'
);

-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    type TEXT CHECK (type IN ('youtube', 'video_url')) NOT NULL,
    title TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    source_id TEXT,
    generated_clips_ids TEXT,  -- JSON array stored as TEXT
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    progress_message TEXT,
    font_family TEXT DEFAULT 'TikTokSans-Regular',
    font_size INTEGER DEFAULT 24,
    font_color TEXT DEFAULT '#FFFFFF',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

-- Generated clips table
CREATE TABLE IF NOT EXISTS generated_clips (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    task_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration REAL NOT NULL,
    text TEXT,
    relevance_score REAL NOT NULL,
    reasoning TEXT,
    clip_order INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- Better Auth tables
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    expiresAt DATETIME NOT NULL,
    token TEXT UNIQUE NOT NULL,
    createdAt DATETIME NOT NULL,
    updatedAt DATETIME NOT NULL,
    ipAddress TEXT,
    userAgent TEXT,
    userId TEXT NOT NULL,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS account (
    id TEXT PRIMARY KEY,
    accountId TEXT NOT NULL,
    providerId TEXT NOT NULL,
    userId TEXT NOT NULL,
    accessToken TEXT,
    refreshToken TEXT,
    idToken TEXT,
    accessTokenExpiresAt DATETIME,
    refreshTokenExpiresAt DATETIME,
    scope TEXT,
    password TEXT,
    createdAt DATETIME NOT NULL,
    updatedAt DATETIME NOT NULL,
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS verification (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL,
    value TEXT NOT NULL,
    expiresAt DATETIME NOT NULL,
    createdAt DATETIME,
    updatedAt DATETIME
);

-- Indexes (same as PostgreSQL)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_source_id ON tasks(source_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at);
CREATE INDEX IF NOT EXISTS idx_generated_clips_task_id ON generated_clips(task_id);
CREATE INDEX IF NOT EXISTS idx_generated_clips_clip_order ON generated_clips(clip_order);
CREATE INDEX IF NOT EXISTS idx_generated_clips_created_at ON generated_clips(created_at);
CREATE INDEX IF NOT EXISTS idx_session_token ON session(token);
CREATE INDEX IF NOT EXISTS idx_session_userId ON session(userId);
CREATE INDEX IF NOT EXISTS idx_account_userId ON account(userId);
CREATE INDEX IF NOT EXISTS idx_verification_identifier ON verification(identifier);

-- Triggers for auto-updating timestamps
-- SQLite doesn't have the same trigger syntax, but we can use similar approach

CREATE TRIGGER IF NOT EXISTS update_users_updatedAt
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_sources_updated_at
AFTER UPDATE ON sources
FOR EACH ROW
BEGIN
    UPDATE sources SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_generated_clips_updated_at
AFTER UPDATE ON generated_clips
FOR EACH ROW
BEGIN
    UPDATE generated_clips SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_session_updatedAt
AFTER UPDATE ON session
FOR EACH ROW
BEGIN
    UPDATE session SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_account_updatedAt
AFTER UPDATE ON account
FOR EACH ROW
BEGIN
    UPDATE account SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_verification_updatedAt
AFTER UPDATE ON verification
FOR EACH ROW
BEGIN
    UPDATE verification SET updatedAt = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

### 7.2 Data Migration Script

**If migrating existing PostgreSQL data:**

Create `backend/scripts/migrate_postgres_to_sqlite.py`:
```python
"""
Migrate data from PostgreSQL to SQLite.
Run this script once during migration.
"""
import asyncio
import asyncpg
import aiosqlite
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POSTGRES_URL = "postgresql://supoclip:supoclip_password@localhost:5432/supoclip"
SQLITE_PATH = Path(__file__).parent.parent / "supoclip.db"

async def migrate():
    """Migrate all data from PostgreSQL to SQLite."""
    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_URL)
    logger.info("Connected to PostgreSQL")
    
    # Connect to SQLite
    sqlite_conn = await aiosqlite.connect(SQLITE_PATH)
    logger.info("Connected to SQLite")
    
    try:
        # Migrate users
        logger.info("Migrating users...")
        users = await pg_conn.fetch("SELECT * FROM users")
        for user in users:
            await sqlite_conn.execute("""
                INSERT INTO users (id, name, email, emailVerified, image, createdAt, updatedAt,
                                  first_name, last_name, password_hash,
                                  default_font_family, default_font_size, default_font_color)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user['id'], user['name'], user['email'], 
                1 if user['emailVerified'] else 0,
                user['image'], user['createdAt'], user['updatedAt'],
                user['first_name'], user['last_name'], user['password_hash'],
                user['default_font_family'], user['default_font_size'], user['default_font_color']
            ))
        await sqlite_conn.commit()
        logger.info(f"Migrated {len(users)} users")
        
        # Migrate sources
        logger.info("Migrating sources...")
        sources = await pg_conn.fetch("SELECT * FROM sources")
        for source in sources:
            await sqlite_conn.execute("""
                INSERT INTO sources (id, type, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (source['id'], source['type'], source['title'], 
                 source['created_at'], source['updated_at']))
        await sqlite_conn.commit()
        logger.info(f"Migrated {len(sources)} sources")
        
        # Migrate tasks
        logger.info("Migrating tasks...")
        tasks = await pg_conn.fetch("SELECT * FROM tasks")
        for task in tasks:
            # Convert array to JSON string for SQLite
            clip_ids_json = json.dumps(task['generated_clips_ids']) if task['generated_clips_ids'] else None
            
            await sqlite_conn.execute("""
                INSERT INTO tasks (id, user_id, source_id, generated_clips_ids, status,
                                  progress, progress_message, font_family, font_size, font_color,
                                  created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task['id'], task['user_id'], task['source_id'], clip_ids_json,
                task['status'], task['progress'], task['progress_message'],
                task['font_family'], task['font_size'], task['font_color'],
                task['created_at'], task['updated_at']
            ))
        await sqlite_conn.commit()
        logger.info(f"Migrated {len(tasks)} tasks")
        
        # Migrate generated_clips
        logger.info("Migrating generated clips...")
        clips = await pg_conn.fetch("SELECT * FROM generated_clips")
        for clip in clips:
            await sqlite_conn.execute("""
                INSERT INTO generated_clips (id, task_id, filename, file_path,
                                           start_time, end_time, duration, text,
                                           relevance_score, reasoning, clip_order,
                                           created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clip['id'], clip['task_id'], clip['filename'], clip['file_path'],
                clip['start_time'], clip['end_time'], clip['duration'], clip['text'],
                clip['relevance_score'], clip['reasoning'], clip['clip_order'],
                clip['created_at'], clip['updated_at']
            ))
        await sqlite_conn.commit()
        logger.info(f"Migrated {len(clips)} clips")
        
        # Migrate Better Auth tables (session, account, verification)
        # Similar approach...
        
        logger.info("✅ Migration complete!")
    
    finally:
        await pg_conn.close()
        await sqlite_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

**Run migration:**
```bash
cd backend
uv run python scripts/migrate_postgres_to_sqlite.py
```

### 7.3 SQLAlchemy Models Update

**File: `backend/src/models.py`**
```python
# Update column types for SQLite compatibility

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    # BEFORE: id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # AFTER:
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # BEFORE: emailVerified = Column(Boolean, default=False)
    # AFTER:
    emailVerified = Column(Integer, default=0)  # 0=False, 1=True
    
    # ... rest of columns

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    
    # BEFORE: generated_clips_ids = Column(ARRAY(String))  # PostgreSQL array
    # AFTER:
    generated_clips_ids = Column(Text)  # JSON string for SQLite
    
    # ... rest of columns
    
    # Helper methods for array handling
    def get_clip_ids(self) -> list:
        """Parse JSON clip IDs."""
        if self.generated_clips_ids:
            return json.loads(self.generated_clips_ids)
        return []
    
    def set_clip_ids(self, clip_ids: list):
        """Set clip IDs as JSON."""
        self.generated_clips_ids = json.dumps(clip_ids)

# Similar updates for Source, GeneratedClip, Session, Account, Verification
```

---

## 8. Configuration Changes

### 8.1 Environment Variables

**File: `.env` (create from .env.example)**
```bash
# ===============================================
# SupoClip Environment Configuration
# Native macOS Version (No Docker)
# ===============================================

# ----------------------------------------------
# Database (SQLite)
# ----------------------------------------------
DATABASE_URL="sqlite+aiosqlite:///./backend/supoclip.db"

# ----------------------------------------------
# Transcription (MLX Whisper)
# ----------------------------------------------
# Model size: tiny, base, small, medium, large
# Larger = more accurate but slower
WHISPER_MODEL=medium

# ----------------------------------------------
# AI Model for Segment Analysis
# ----------------------------------------------
# Format: "provider:model-name"
# Examples:
#   - openai:gpt-4.1
#   - anthropic:claude-3-5-sonnet
#   - google:gemini-2.5-pro

LLM=openai:gpt-4.1

# AI Provider API Keys (choose one or more)
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_API_KEY=your_google_key_here

# ----------------------------------------------
# Better Auth (Frontend Authentication)
# ----------------------------------------------
BETTER_AUTH_SECRET=your_random_secret_here_change_in_production
BETTER_AUTH_URL=http://localhost:3000

# ----------------------------------------------
# Application Settings
# ----------------------------------------------
# Temporary directory for uploads and processing
TEMP_DIR=./temp

# Maximum video duration in seconds (1 hour)
MAX_VIDEO_DURATION=3600

# Maximum number of clips to generate per video
MAX_CLIPS=10

# Default clip duration in seconds
CLIP_DURATION=30

# ----------------------------------------------
# Development Settings
# ----------------------------------------------
NODE_ENV=development
NEXT_TELEMETRY_DISABLED=1
NEXT_PUBLIC_API_URL=http://localhost:8000

# ----------------------------------------------
# REMOVED (No longer needed)
# ----------------------------------------------
# ASSEMBLY_AI_API_KEY - Replaced by MLX Whisper
# REDIS_HOST - Replaced by local queue
# REDIS_PORT - Replaced by local queue
# POSTGRES_DB - Replaced by SQLite
# POSTGRES_USER - Replaced by SQLite
# POSTGRES_PASSWORD - Replaced by SQLite
# DOCKER_BUILDKIT - No Docker
```

### 8.2 Backend Configuration Class

**File: `backend/src/config.py`** (updated)
```python
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

class Config:
    """Application configuration (native macOS version)."""
    
    def __init__(self):
        # Transcription (MLX Whisper)
        self.whisper_model = os.getenv("WHISPER_MODEL", "medium")
        
        # AI Models
        self.llm = os.getenv("LLM", "openai:gpt-4.1")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        
        # Application settings
        self.max_video_duration = int(os.getenv("MAX_VIDEO_DURATION", "3600"))
        self.max_clips = int(os.getenv("MAX_CLIPS", "10"))
        self.clip_duration = int(os.getenv("CLIP_DURATION", "30"))
        
        # Directories
        self.temp_dir = Path(os.getenv("TEMP_DIR", "temp"))
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
        self.clips_dir = Path("clips")
        self.uploads_dir = Path("uploads")
        
        # Create directories if they don't exist
        for directory in [self.temp_dir, self.output_dir, self.clips_dir, self.uploads_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Database (SQLite)
        self.database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./supoclip.db")
        
        # Job queue settings
        self.job_queue_workers = int(os.getenv("JOB_QUEUE_WORKERS", "2"))
        
    def validate(self):
        """Validate configuration."""
        # Check if at least one LLM API key is provided
        if not any([self.openai_api_key, self.anthropic_api_key, self.google_api_key]):
            raise ValueError("At least one AI provider API key must be set")
        
        # Validate whisper model
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if self.whisper_model not in valid_models:
            raise ValueError(f"Invalid WHISPER_MODEL: {self.whisper_model}. Choose from: {valid_models}")
        
        return True

# Global config instance
config = Config()
```

### 8.3 Frontend Configuration

**File: `frontend/.env`**
```bash
# Database (SQLite)
DATABASE_URL="file:../backend/supoclip.db"

# Better Auth
BETTER_AUTH_SECRET="your_random_secret_here"
BETTER_AUTH_URL="http://localhost:3000"

# Backend API
NEXT_PUBLIC_API_URL="http://localhost:8000"

# Development
NODE_ENV=development
NEXT_TELEMETRY_DISABLED=1
```

**File: `frontend/next.config.ts`** (no changes needed, but verify)
```typescript
// Should already be compatible
const nextConfig = {
  // ... existing config
};

export default nextConfig;
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Backend Tests Structure:**
```
backend/tests/
├── __init__.py
├── conftest.py                      # Pytest fixtures
├── test_transcription_mlx.py        # MLX transcription tests
├── test_local_queue.py              # Local job queue tests
├── test_local_progress.py           # Progress tracking tests
├── test_database_sqlite.py          # SQLite database tests
├── test_video_utils.py              # Video processing tests
├── test_ai.py                       # AI analysis tests
└── fixtures/
    ├── test_video.mp4               # Sample 10-sec video
    └── test_video_long.mp4          # Sample 2-min video
```

**Key Test Files:**

**test_transcription_mlx.py:**
```python
import pytest
from pathlib import Path
from src.transcription_mlx import transcribe_video_mlx, load_cached_transcript_mlx

@pytest.mark.asyncio
async def test_transcribe_video_mlx_basic(test_video_path):
    """Test basic MLX transcription."""
    result = transcribe_video_mlx(test_video_path, model_size="tiny")
    
    assert result is not None
    assert "text" in result
    assert "words" in result
    assert "segments" in result
    assert len(result["words"]) > 0

@pytest.mark.asyncio
async def test_transcribe_video_mlx_caching(test_video_path):
    """Test that transcription is cached."""
    # First transcription
    result1 = transcribe_video_mlx(test_video_path, model_size="tiny")
    
    # Should load from cache
    result2 = load_cached_transcript_mlx(test_video_path)
    
    assert result2 is not None
    assert result1["text"] == result2["text"]

@pytest.mark.asyncio
async def test_transcribe_video_mlx_word_timing(test_video_path):
    """Test word-level timing format."""
    result = transcribe_video_mlx(test_video_path, model_size="tiny")
    
    words = result["words"]
    assert len(words) > 0
    
    # Check format matches AssemblyAI structure
    first_word = words[0]
    assert "text" in first_word
    assert "start" in first_word  # Milliseconds
    assert "end" in first_word
    assert "confidence" in first_word
    
    # Verify timing is reasonable
    assert first_word["end"] > first_word["start"]
    assert 0 <= first_word["confidence"] <= 1.0
```

**test_local_queue.py:**
```python
import pytest
import asyncio
from src.workers.local_queue import LocalJobQueue, Job

@pytest.mark.asyncio
async def test_local_queue_basic():
    """Test basic job enqueueing and processing."""
    queue = LocalJobQueue(max_workers=1)
    await queue.start_workers()
    
    async def sample_task(x, y):
        await asyncio.sleep(0.1)
        return x + y
    
    job_id = await queue.enqueue_job(sample_task, 5, 3)
    
    # Wait for completion
    await asyncio.sleep(0.5)
    
    job = queue.get_job(job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.result == 8
    
    await queue.stop_workers()

@pytest.mark.asyncio
async def test_local_queue_multiple_jobs():
    """Test multiple jobs are processed."""
    queue = LocalJobQueue(max_workers=2)
    await queue.start_workers()
    
    async def task(n):
        await asyncio.sleep(0.1)
        return n * 2
    
    job_ids = []
    for i in range(5):
        job_id = await queue.enqueue_job(task, i)
        job_ids.append(job_id)
    
    # Wait for all to complete
    await asyncio.sleep(1.0)
    
    for i, job_id in enumerate(job_ids):
        job = queue.get_job(job_id)
        assert job.status == "completed"
        assert job.result == i * 2
    
    await queue.stop_workers()

@pytest.mark.asyncio
async def test_local_queue_error_handling():
    """Test error handling in jobs."""
    queue = LocalJobQueue(max_workers=1)
    await queue.start_workers()
    
    async def failing_task():
        raise ValueError("Test error")
    
    job_id = await queue.enqueue_job(failing_task)
    
    await asyncio.sleep(0.5)
    
    job = queue.get_job(job_id)
    assert job.status == "error"
    assert "Test error" in job.error
    
    await queue.stop_workers()
```

**test_local_progress.py:**
```python
import pytest
import asyncio
from src.workers.local_progress import LocalProgressTracker

@pytest.mark.asyncio
async def test_progress_tracking_basic():
    """Test basic progress tracking."""
    tracker = LocalProgressTracker()
    
    task_id = "test-task-123"
    await tracker.update(task_id, 50, "Halfway", "processing")
    
    progress = tracker.get(task_id)
    assert progress.progress == 50
    assert progress.message == "Halfway"
    assert progress.status == "processing"

@pytest.mark.asyncio
async def test_progress_tracking_subscription():
    """Test subscribing to progress updates."""
    tracker = LocalProgressTracker()
    task_id = "test-task-456"
    
    updates_received = []
    
    async def subscriber():
        async for progress in tracker.subscribe(task_id):
            updates_received.append(progress.progress)
            if progress.status == "completed":
                break
    
    # Start subscriber
    sub_task = asyncio.create_task(subscriber())
    
    # Send updates
    await asyncio.sleep(0.1)
    await tracker.update(task_id, 25, "Quarter done", "processing")
    await asyncio.sleep(0.1)
    await tracker.update(task_id, 50, "Half done", "processing")
    await asyncio.sleep(0.1)
    await tracker.complete(task_id, "Done!")
    
    # Wait for subscriber to finish
    await sub_task
    
    assert 25 in updates_received
    assert 50 in updates_received
    assert 100 in updates_received
```

### 9.2 Integration Tests

**test_integration_offline.py:**
```python
import pytest
from pathlib import Path
import asyncio
from src.transcription_mlx import transcribe_video_mlx
from src.ai import get_most_relevant_parts_by_transcript
from src.video_utils import create_optimized_clip

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_video_processing_offline(test_video_path, tmp_path):
    """
    Test complete video processing pipeline offline.
    
    This test should pass with internet disconnected.
    """
    # 1. Transcribe
    transcript_data = transcribe_video_mlx(test_video_path, model_size="tiny")
    assert transcript_data is not None
    
    # 2. AI analysis (will fail if using cloud LLMs - expect this)
    try:
        segments = await get_most_relevant_parts_by_transcript(transcript_data)
        assert len(segments) > 0
    except Exception as e:
        # Expected if using cloud LLM without internet
        pytest.skip(f"LLM API unavailable (expected offline): {e}")
    
    # 3. Generate clips
    output_path = tmp_path / "clip_0.mp4"
    success = create_optimized_clip(
        test_video_path,
        start_time=0,
        end_time=10,
        output_path=output_path,
        add_subtitles=True
    )
    
    assert success
    assert output_path.exists()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_health_check():
    """Test FastAPI health check endpoint."""
    # This would use httpx or similar to test API
    # For now, manual test via:
    # curl http://localhost:8000/health
    pass
```

### 9.3 Manual Testing Checklist

**Phase 1: Offline Verification**
- [ ] Disconnect from internet
- [ ] Upload local video file
- [ ] Verify transcription works (MLX Whisper runs locally)
- [ ] Verify database operations work (SQLite)
- [ ] Verify video processing completes
- [ ] Verify clips are generated correctly
- [ ] Only LLM analysis should fail (if using cloud API)

**Phase 2: Performance Testing**
- [ ] Measure transcription time (compare to old AssemblyAI)
- [ ] Measure clip generation time
- [ ] Measure memory usage
- [ ] Measure startup time (compare to Docker)

**Phase 3: UI Testing**
- [ ] User registration/login works
- [ ] Video upload form works
- [ ] Task status updates in real-time (SSE)
- [ ] Clips display correctly
- [ ] Progress bar updates smoothly
- [ ] Error messages display properly

**Phase 4: Edge Cases**
- [ ] Very short video (< 10 sec)
- [ ] Very long video (> 1 hour)
- [ ] Video with no speech
- [ ] Video with multiple speakers
- [ ] Corrupted video file
- [ ] Unsupported video format

### 9.4 Performance Benchmarks

**Baseline Measurements (Docker + AssemblyAI):**
| Metric | Old (Docker) | Target (Native) |
|--------|--------------|-----------------|
| Startup time | 30-60 sec | 5-10 sec |
| Transcription (5 min video) | ~30 sec | ~15 sec |
| Clip generation (3 clips) | ~20 sec | ~20 sec |
| Memory usage | 2-3 GB | 500 MB - 1 GB |
| Cold start (first transcription) | 30 sec | 30 sec (model load) |
| Warm start (cached model) | 30 sec | 10 sec |

**Test Script:**
```python
import time
from pathlib import Path
from src.transcription_mlx import transcribe_video_mlx

def benchmark_transcription():
    video_path = Path("tests/fixtures/test_video_5min.mp4")
    
    # Warm up
    print("Warming up MLX...")
    transcribe_video_mlx(video_path, model_size="tiny")
    
    # Benchmark
    print("Benchmarking transcription...")
    start = time.time()
    result = transcribe_video_mlx(video_path, model_size="medium")
    end = time.time()
    
    duration = end - start
    word_count = len(result["words"])
    
    print(f"Transcription time: {duration:.2f} seconds")
    print(f"Words transcribed: {word_count}")
    print(f"Words per second: {word_count / duration:.2f}")

if __name__ == "__main__":
    benchmark_transcription()
```

### 9.5 Continuous Testing

**GitHub Actions (if applicable):**
```yaml
name: Test Migration

on: [push, pull_request]

jobs:
  test:
    runs-on: macos-latest  # Must use macOS for MLX
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        brew install ffmpeg
        cd backend
        pip install uv
        uv sync
    
    - name: Run tests
      run: |
        cd backend
        uv run pytest tests/ -v --tb=short
```

---

## 10. Risk Assessment

### 10.1 High-Risk Areas

**1. MLX Transcription Accuracy**
- **Risk:** MLX Whisper may be less accurate than AssemblyAI
- **Likelihood:** Medium
- **Impact:** High (affects all downstream processing)
- **Mitigation:** 
  - Use larger model (medium or large) for production
  - Add manual transcript editing feature
  - Keep AssemblyAI as optional fallback (feature flag)

**2. SQLite Concurrency**
- **Risk:** SQLite handles concurrent writes differently than PostgreSQL
- **Likelihood:** Medium
- **Impact:** Medium (potential write conflicts)
- **Mitigation:**
  - Use WAL mode (Write-Ahead Logging)
  - Limit concurrent write operations
  - Add retry logic for database locks
  - Test with multiple concurrent users

**3. In-Process Job Queue Scalability**
- **Risk:** Local queue may not scale to many concurrent jobs
- **Likelihood:** Low (typical use case: 1-2 videos at a time)
- **Impact:** Medium
- **Mitigation:**
  - Add queue size limits
  - Add job prioritization
  - Monitor queue length and worker status
  - Consider optional Redis support for high-volume deployments

### 10.2 Medium-Risk Areas

**4. Array Type Handling (PostgreSQL → SQLite)**
- **Risk:** PostgreSQL arrays must be converted to JSON strings
- **Likelihood:** High
- **Impact:** Low (affects `generated_clips_ids` field)
- **Mitigation:**
  - Add helper methods for JSON serialization/deserialization
  - Update all array access code
  - Add migration tests

**5. Better Auth Compatibility**
- **Risk:** Better Auth may have SQLite-specific issues
- **Likelihood:** Low (Better Auth supports SQLite)
- **Impact:** High (breaks authentication)
- **Mitigation:**
  - Test authentication thoroughly
  - Review Better Auth SQLite adapter code
  - Have rollback plan

**6. Frontend SSE Changes**
- **Risk:** SSE progress tracking behavior may differ
- **Likelihood:** Low
- **Impact:** Medium (affects UX)
- **Mitigation:**
  - Test SSE thoroughly
  - Add fallback polling mechanism
  - Add connection retry logic

### 10.3 Low-Risk Areas

**7. Video Processing Logic**
- **Risk:** MoviePy/OpenCV/MediaPipe behavior changes
- **Likelihood:** Very Low (no changes to this code)
- **Impact:** Low
- **Mitigation:** No changes needed to video processing

**8. YouTube Download**
- **Risk:** yt-dlp behavior changes
- **Likelihood:** Very Low (yt-dlp still used as-is)
- **Impact:** Low
- **Mitigation:** Keep yt-dlp updated regularly

### 10.4 Risk Matrix

| Risk Area | Likelihood | Impact | Priority | Mitigation Cost |
|-----------|------------|--------|----------|-----------------|
| MLX Accuracy | Medium | High | **P0** | Medium |
| SQLite Concurrency | Medium | Medium | **P1** | Low |
| Job Queue Scale | Low | Medium | P2 | Medium |
| Array Handling | High | Low | P2 | Low |
| Better Auth | Low | High | **P1** | Low |
| SSE Changes | Low | Medium | P2 | Low |
| Video Processing | Very Low | Low | P3 | None |
| yt-dlp | Very Low | Low | P3 | None |

### 10.5 Unknowns and Assumptions

**Assumptions:**
1. Users primarily process 1-2 videos at a time (not batch processing)
2. Apple Silicon Macs available (M1/M2/M3)
3. Internet available for LLM API calls (not transcription)
4. Video files are local or can be downloaded once
5. No need for distributed processing across multiple machines

**Unknowns:**
1. MLX Whisper performance on very long videos (> 2 hours)
2. SQLite performance with thousands of clips
3. Better Auth edge cases with SQLite
4. Frontend production build differences
5. Memory usage with multiple concurrent transcriptions

---

## 11. Rollback Strategy

### 11.1 Rollback Triggers

**When to rollback:**
- MLX transcription quality is unacceptable
- SQLite cannot handle load
- Critical bugs that block core functionality
- Performance is significantly worse than Docker version
- Data loss or corruption issues

### 11.2 Rollback Procedure

**Step 1: Restore Docker Branch**
```bash
# If migration was done on a feature branch
git checkout main
git pull origin main

# Or if main was updated
git revert <migration-commit-sha>
```

**Step 2: Restore Docker Compose**
```bash
# Copy archived files back
cp archive/docker/docker-compose.yml ./
cp archive/docker/backend-Dockerfile backend/Dockerfile
cp archive/docker/frontend-Dockerfile frontend/Dockerfile
```

**Step 3: Restore Dependencies**
```bash
# Backend
cd backend
git checkout main -- pyproject.toml
uv sync

# Frontend
cd ../frontend
git checkout main -- package.json
npm install
```

**Step 4: Restore Database**

**Option A: Restore PostgreSQL from backup**
```bash
docker-compose up -d postgres
docker-compose exec postgres psql -U supoclip supoclip < backup_postgres.sql
```

**Option B: Migrate SQLite back to PostgreSQL**
```bash
# Use migration script in reverse
cd backend
uv run python scripts/migrate_sqlite_to_postgres.py
```

**Step 5: Restore Configuration**
```bash
# Restore old .env
cp .env.docker.backup .env
```

**Step 6: Restart Docker Services**
```bash
docker-compose down
docker-compose up -d --build
```

### 11.3 Rollback Timeline

- **Immediate (< 1 hour):** Revert to main branch, start Docker
- **Partial (< 4 hours):** Keep SQLite, restore AssemblyAI or restore Docker, keep MLX
- **Full (< 8 hours):** Complete rollback with data migration

### 11.4 Data Preservation

**Before Migration:**
```bash
# Backup all data
./scripts/backup_all.sh

# Contents:
# - PostgreSQL dump
# - Redis dump
# - All uploaded videos
# - All generated clips
# - Database schema
# - Environment config
```

**Backup Script (`scripts/backup_all.sh`):**
```bash
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
docker-compose exec postgres pg_dump -U supoclip supoclip > "$BACKUP_DIR/postgres.sql"

# Backup Redis
docker-compose exec redis redis-cli SAVE
docker cp supoclip-redis:/data/dump.rdb "$BACKUP_DIR/redis.rdb"

# Backup videos and clips
tar -czf "$BACKUP_DIR/videos.tar.gz" uploads/ clips/

# Backup config
cp .env "$BACKUP_DIR/.env.backup"
cp backend/pyproject.toml "$BACKUP_DIR/pyproject.toml.backup"

echo "Backup complete: $BACKUP_DIR"
```

### 11.5 Hybrid Approach (If Needed)

**Scenario: Keep MLX, restore Docker for other components**

Possible if:
- MLX transcription works well
- But SQLite or job queue has issues

**Changes:**
1. Keep `transcription_mlx.py` and MLX dependencies
2. Restore PostgreSQL via Docker
3. Restore Redis via Docker
4. Update `database.py` to use PostgreSQL connection string
5. Restore arq worker

This allows incremental migration:
- **Phase 1:** MLX only (fastest, lowest risk)
- **Phase 2:** SQLite (medium risk)
- **Phase 3:** Local queue (medium risk)
- **Phase 4:** Remove Docker entirely (full migration)

---

## Conclusion

This migration plan provides a comprehensive roadmap for transitioning SupoClip from a Docker-based, cloud-dependent application to a native macOS application optimized for Apple Silicon and offline operation.

**Key Milestones:**
1. ✅ Docker infrastructure removed
2. ✅ AssemblyAI replaced with MLX Whisper
3. ✅ PostgreSQL replaced with SQLite
4. ✅ Redis/arq replaced with local queue
5. ✅ Complete offline operation (except LLM API)

**Success Criteria:**
- Application starts in < 10 seconds
- Transcription works offline with acceptable quality
- All existing features remain functional
- Performance is comparable or better than Docker version
- No data loss during migration

**Next Steps After Migration:**
1. Monitor performance and accuracy
2. Gather user feedback
3. Consider optional local LLM integration (MLX-LM) for 100% offline
4. Optimize MLX model selection based on user hardware
5. Add optional cloud features as plugins (AssemblyAI, Redis) for power users

---

**Document Metadata:**
- **Created:** 2025-11-14
- **Author:** Migration Planning Team
- **Version:** 1.0
- **Status:** Ready for Implementation
- **Estimated Duration:** 3-5 days
- **Risk Level:** Medium

---
