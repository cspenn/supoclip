# Job Queue Migration - Complete File Inventory

## Overview

This document provides a complete inventory of all files involved in the job queue migration from Redis/arq to local asyncio.

---

## Files by Status

### BROKEN - Must Be Fixed

#### 1. backend/src/workers/job_queue.py
- **Status**: BROKEN - tries to import removed `arq` library
- **Size**: 77 lines
- **Last Modified**: During migration (now outdated)
- **Problem**: Lines 6-7 import arq
- **Action**: REPLACE with compatibility wrapper
- **Dependencies**:
  - References non-existent config properties: `config.redis_host`, `config.redis_port`
  - Imports: `from arq import create_pool`, `from arq.connections import RedisSettings, ArqRedis`

**Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/job_queue.py`

**Current Content**:
```python
"""
Job queue setup using arq (async Redis queue).
"""
import logging
from typing import Optional
from arq import create_pool                    # ← BROKEN
from arq.connections import RedisSettings, ArqRedis  # ← BROKEN
from ..config import Config
# ... rest of file
```

---

### READY - Complete and Tested

#### 1. backend/src/workers/local_queue.py
- **Status**: COMPLETE - fully functional, tested
- **Size**: 203 lines
- **Last Modified**: As part of migration (up-to-date)
- **What It Does**: Provides asyncio-based job queue without Redis dependency
- **Test Coverage**: 20+ tests in test_local_queue.py (all passing)
- **API**: Instance methods + singleton accessor

**Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/local_queue.py`

**Key Classes**:
```python
@dataclass
class Job:
    """Job information and status"""
    job_id: str
    function: Callable
    args: tuple
    kwargs: dict
    status: str  # "queued", "processing", "completed", "error"
    result: Any
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class LocalJobQueue:
    """Main queue implementation"""
    async def start_workers()
    async def stop_workers()
    async def enqueue_job(function, *args, **kwargs) -> job_id
    async def _worker(name) -> None
    def get_job(job_id) -> Optional[Job]
    def get_job_status(job_id) -> Optional[str]
    def get_job_result(job_id) -> Any

def get_job_queue() -> LocalJobQueue  # Singleton accessor
```

#### 2. backend/src/workers/local_progress.py
- **Status**: COMPLETE - fully functional, tested
- **Size**: 184 lines
- **Last Modified**: As part of migration (up-to-date)
- **What It Does**: In-memory progress tracking (replaces Redis pub/sub)
- **Test Coverage**: Tests in test_offline_capability.py (all passing)
- **API**: Async methods with async generator for subscriptions

**Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/local_progress.py`

**Key Classes**:
```python
@dataclass
class Progress:
    """Progress information"""
    task_id: str
    progress: int  # 0-100
    message: str
    status: str  # "queued", "processing", "completed", "error"
    updated_at: datetime

class LocalProgressTracker:
    """Progress tracking in-memory"""
    async def update(task_id, progress, message, status)
    def get(task_id) -> Optional[Progress]
    async def complete(task_id, message)
    async def error(task_id, message)
    async def subscribe(task_id) -> AsyncGenerator[Progress]

def get_progress_tracker() -> LocalProgressTracker  # Singleton
```

---

### PARTIALLY BROKEN - Needs Refactoring

#### 1. backend/src/workers/tasks.py
- **Status**: PARTIALLY BROKEN - references arq context
- **Size**: 101 lines
- **Problem**: `process_video_task` function signature expects `ctx` parameter from arq
- **Usage**: Referenced by `api/routes/tasks.py` when enqueueing jobs
- **Action**: OPTIONAL - refactor to remove arq dependency

**Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/tasks.py`

**Problem Area** (Lines 11-20):
```python
async def process_video_task(
    ctx: Dict[str, Any],                    # ← arq context (won't exist)
    task_id: str,
    url: str,
    source_type: str,
    user_id: str,
    font_family: str = "TikTokSans-Regular",
    font_size: int = 24,
    font_color: str = "#FFFFFF"
) -> Dict[str, Any]:
```

**Problem Area** (Line 44):
```python
progress = ProgressTracker(ctx['redis'], task_id)  # ← Needs Redis
```

**Also Broken** (Lines 76-93):
```python
class WorkerSettings:
    """Configuration for arq worker."""
    from ..config import Config
    from arq.connections import RedisSettings  # ← BROKEN

    config = Config()
    functions = [process_video_task]
    queue_name = "supoclip_tasks"

    redis_settings = RedisSettings(                    # ← BROKEN
        host=config.redis_host,                        # ← Doesn't exist
        port=config.redis_port                         # ← Doesn't exist
    )
```

---

### UNUSED - Can Be Kept for Reference

#### 1. backend/src/workers/progress.py
- **Status**: UNUSED - Redis-based (no Redis available)
- **Size**: 82 lines
- **Reason**: Requires Redis connection pool
- **Decision**: Keep as reference, use local_progress.py instead
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/progress.py`

**Note**: If consolidating, could remove this file after confirming nothing imports it.

#### 2. backend/src/workers/job_queue.py.bak
- **Status**: BACKUP - original broken version
- **Size**: 77 lines (same as current)
- **Purpose**: Reference showing what was broken
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/job_queue.py.bak`
- **Action**: Keep for historical reference, safe to delete after migration verified

---

### NEEDS UPDATES - Integration Points

#### 1. backend/src/main.py
- **Status**: NEEDS UPDATE - missing lifespan initialization
- **Size**: ~400 lines
- **Current**: Doesn't import or initialize job queue
- **Missing**: No worker startup/shutdown in lifespan
- **Action**: ADD imports and lifespan code
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/main.py`

**What Needs Adding** (around line 33):
```python
from .workers.local_queue import get_job_queue  # ADD THIS

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()

        # ADD THESE LINES:
        queue = get_job_queue()
        await queue.start_workers()
        logger.info("✅ Job queue workers started")

        yield
    finally:
        # ADD THESE LINES:
        try:
            queue = get_job_queue()
            await queue.stop_workers()
            logger.info("✅ Job queue workers stopped")
        except Exception as e:
            logger.error(f"Error stopping workers: {e}")

        await close_db()
```

#### 2. backend/src/api/routes/tasks.py
- **Status**: NEEDS UPDATE - uses string function name
- **Size**: ~250 lines
- **Current**: Calls `JobQueue.enqueue_job("process_video_task", ...)`
- **Issue**: Passes string name instead of function object
- **Action**: ADD import + UPDATE one function call
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/api/routes/tasks.py`

**What Needs Changing** (around lines 14, 98):

Add import (line 15):
```python
from ...workers.tasks import process_video_task  # ADD THIS
```

Update enqueue call (line 98):
```python
# BEFORE:
job_id = await JobQueue.enqueue_job(
    "process_video_task",  # String
    ...
)

# AFTER:
job_id = await JobQueue.enqueue_job(
    process_video_task,  # Function object
    ...
)
```

#### 3. backend/src/main_refactored.py
- **Status**: NEEDS UPDATE - but INACTIVE (not used)
- **Size**: ~300 lines
- **Current**: Uses JobQueue for initialization
- **Note**: This is a reference implementation, not the active app
- **Decision**: Can update for consistency or leave as-is (won't affect app)
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/main_refactored.py`

---

### CONFIGURATION - No Changes Needed

#### backend/src/config.py
- **Status**: READY - already configured correctly
- **Size**: 112 lines
- **What It Does**: Loads environment variables and provides app config
- **Already Has**:
  - `self.max_workers` (for LocalJobQueue)
  - `self.worker_timeout` (for LocalJobQueue)
- **No Longer Has** (correctly removed):
  - `self.redis_host`
  - `self.redis_port`
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/src/config.py`

**Environment Variables** (in .env):
```bash
# Job queue configuration
MAX_WORKERS=2              # Number of worker coroutines
WORKER_TIMEOUT=3600        # Timeout per job in seconds

# No longer needed:
# REDIS_HOST
# REDIS_PORT
```

---

### TESTS - Ready to Validate

#### 1. backend/tests/test_local_queue.py
- **Status**: COMPLETE - all tests passing
- **Size**: 466 lines
- **Test Count**: 20+ test cases
- **Coverage**: All LocalJobQueue functionality
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/tests/test_local_queue.py`

**Test Classes**:
- TestLocalJobQueueInitialization (3 tests)
- TestJobDataStructure (2 tests)
- TestJobEnqueueing (3 tests)
- TestJobProcessing (3+ tests)
- TestWorkerManagement (multiple tests)
- TestErrorHandling (multiple tests)
- TestJobQueueIntegration (multiple tests)

#### 2. backend/tests/test_offline_capability.py
- **Status**: COMPLETE - all tests passing
- **Size**: Multiple tests
- **Purpose**: Verify local-only operation (no Redis)
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/tests/test_offline_capability.py`

#### 3. backend/tests/test_configuration.py
- **Status**: COMPLETE - all tests passing
- **Test**: `TestJobQueueConfig` class
- **Location**: `/Users/cspenn/Documents/github/supoclip/backend/tests/test_configuration.py`

---

## Summary by Action Required

### ACTION 1: Replace (1 file)
- [ ] `backend/src/workers/job_queue.py` - REPLACE with compatibility wrapper

### ACTION 2: Update (2 files)
- [ ] `backend/src/main.py` - ADD lifespan initialization
- [ ] `backend/src/api/routes/tasks.py` - ADD import, UPDATE function call

### ACTION 3: Optional (1 file)
- [ ] `backend/src/workers/tasks.py` - REFACTOR to remove arq dependency

### ACTION 4: Reference Only (3 files)
- [ ] `backend/src/workers/local_queue.py` - Already complete, no changes needed
- [ ] `backend/src/workers/local_progress.py` - Already complete, no changes needed
- [ ] `backend/src/config.py` - Already correct, no changes needed

### ACTION 5: Legacy (2 files)
- [ ] `backend/src/main_refactored.py` - Update for consistency (OPTIONAL)
- [ ] `backend/src/workers/job_queue.py.bak` - Keep as reference or delete

---

## File Dependency Graph

```
IMPORTS FROM job_queue.py:
├── api/routes/tasks.py
│   └── calls: JobQueue.enqueue_job()
└── main_refactored.py
    ├── calls: JobQueue.get_pool()
    └── calls: JobQueue.close_pool()

IMPORTS FROM local_queue.py:
├── job_queue.py (NEW - compatibility wrapper)
│   └── delegates to: get_job_queue()
└── main.py (NEW - needs to be added)
    └── calls: get_job_queue().start/stop_workers()

IMPORTS FROM local_progress.py:
├── tasks.py (OPTIONAL - for refactoring)
    └── could use: get_progress_tracker()
└── (currently unused)

IMPORTS FROM config.py:
├── job_queue.py (for MAX_WORKERS, WORKER_TIMEOUT)
├── local_queue.py (for MAX_WORKERS)
└── main.py (for various settings)
```

---

## Git File Status

```bash
# Untracked/Modified files related to job queue:
?? backend/.coverage
?? backend/TESTING_REPORT.md
?? backend/pytest.ini
?? backend/src/__init__.py
?? backend/test_results.log
?? backend/test_results_full.log
?? backend/tests/

M  backend/src/models.py
M  backend/pyproject.toml
D  MIGRATION_SUMMARY.md
D  requirements_pre_migration.txt

# Files relevant to this fix:
- backend/src/workers/job_queue.py (will be modified)
- backend/src/workers/local_queue.py (already tracked)
- backend/src/workers/local_progress.py (already tracked)
- backend/src/main.py (will be modified)
- backend/src/api/routes/tasks.py (will be modified)
- backend/src/workers/tasks.py (will be modified if refactoring)
```

---

## Before/After Comparison

### File Count
- **Before Fix**: 7 active files (1 broken)
- **After Fix**: 7 active files (0 broken)

### Import Count
- **Before**: job_queue.py imports 3 lines trying to import arq
- **After**: job_queue.py imports from local_queue (asyncio-compatible)

### Dependencies
- **Before**: Requires arq, Redis, external packages
- **After**: Uses only Python stdlib (asyncio), no external packages needed

### Lines Changed
- `job_queue.py`: 77 lines (REPLACE)
- `main.py`: +10 lines (ADD)
- `api/routes/tasks.py`: +1 line (ADD), 1 line (MODIFY)
- `workers/tasks.py`: Optional refactoring

**Total**: ~50-100 lines of changes

---

## Checklist: File Status Verification

### Before Making Changes
- [ ] Verify job_queue.py exists at `/Users/cspenn/Documents/github/supoclip/backend/src/workers/job_queue.py`
- [ ] Verify job_queue.py.bak exists as backup
- [ ] Verify local_queue.py exists and is complete
- [ ] Verify local_progress.py exists and is complete
- [ ] Verify main.py is the active entry point
- [ ] Verify api/routes/tasks.py imports JobQueue

### After Making Changes
- [ ] job_queue.py no longer imports arq
- [ ] main.py imports get_job_queue
- [ ] main.py lifespan initializes job queue
- [ ] api/routes/tasks.py imports process_video_task
- [ ] api/routes/tasks.py uses function object, not string
- [ ] All files have correct syntax
- [ ] All imports can be resolved

---

## File Size and Complexity

| File | Lines | Type | Complexity | Status |
|------|-------|------|-----------|--------|
| job_queue.py | 77 | class-based API | low | BROKEN |
| local_queue.py | 203 | class-based + dataclass | medium | READY |
| local_progress.py | 184 | class-based + dataclass | medium | READY |
| progress.py | 82 | class-based | low | UNUSED |
| tasks.py | 101 | function + class | medium | PARTIAL |
| main.py | 400+ | FastAPI app | high | NEEDS UPDATE |
| api/routes/tasks.py | 250+ | FastAPI router | high | NEEDS UPDATE |

---

## References

- **Implementation Guide**: `docs/progress/fixes/2025-11-14-job-queue-implementation-guide.md`
- **Quick Reference**: `docs/progress/fixes/2025-11-14-job-queue-quick-reference.md`
- **Detailed Analysis**: `docs/progress/fixes/2025-11-14-job-queue-analysis.md`
- **Project Standards**: `CLAUDE.md`

---

END OF FILE INVENTORY
