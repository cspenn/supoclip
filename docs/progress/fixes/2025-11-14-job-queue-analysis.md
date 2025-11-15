# Job Queue Module Analysis and Repair Plan
Date: 2025-11-14

## Executive Summary

The SupoClip backend is failing to start with `ModuleNotFoundError: No module named 'arq'` because:

1. **Root Cause**: The migration from Docker + Redis to native macOS with SQLite removed the `arq` dependency from `pyproject.toml`, but the `job_queue.py` module still attempts to import `arq`
2. **Status**: A replacement local asyncio-based `LocalJobQueue` has already been implemented in `local_queue.py`, but code still imports the broken `job_queue.py` module
3. **Impact**: **CRITICAL** - Application cannot start; prevents any task processing
4. **Solution**: Replace broken `job_queue.py` with a compatibility wrapper that delegates to `LocalJobQueue`

---

## Part 1: Current Job Queue Implementation Analysis

### 1.1 Current Broken Implementation (job_queue.py)

**File**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/job_queue.py`

**Status**: BROKEN - Attempts to import removed dependency `arq`

**What It Does**:
- Manages Redis connection pool for async job queue processing
- Provides class-level interface for enqueueing jobs
- Tracks job status and retrieves results
- Requires Redis to be running (external dependency)

**API Interface**:
```python
JobQueue.enqueue_job(function_name, *args, **kwargs) -> job_id
JobQueue.get_job_status(job_id) -> str (status)
JobQueue.get_job_result(job_id) -> result
JobQueue.get_pool() -> ArqRedis  # Startup initialization
JobQueue.close_pool() -> None     # Shutdown cleanup
```

**Problem**: References non-existent configuration:
- `config.redis_host` (not defined in Config class)
- `config.redis_port` (not defined in Config class)

---

### 1.2 New LocalJobQueue Implementation (local_queue.py)

**File**: `/Users/cspenn/Documents/github/supoclip/backend/src/workers/local_queue.py`

**Status**: COMPLETE and TESTED - Fully functional

**What It Does**:
- In-memory async job queue using `asyncio.Queue`
- No external dependencies (Redis, arq, etc.)
- Manages worker pool for concurrent job processing
- Tracks job status and results in-memory
- Supports async worker functions with automatic error handling

**API Interface**:
```python
# Instance-based API (different from JobQueue!)
queue = LocalJobQueue(max_workers=2)
await queue.enqueue_job(function, *args, **kwargs) -> job_id
queue.get_job_status(job_id) -> str
queue.get_job_result(job_id) -> result
await queue.start_workers()
await queue.stop_workers()

# Global accessor
get_job_queue() -> LocalJobQueue  # Singleton pattern
```

**Implementation Details**:
- Uses `asyncio.Queue` for thread-safe job queueing
- Maintains in-memory job registry: `jobs: Dict[str, Job]`
- Each worker is an asyncio Task running `_worker()` coroutine
- Job lifecycle: `Job` dataclass with status tracking
- Logging uses emoji indicators (📝, ✅, ❌)
- Supports configurable worker pool size via `Config.max_workers`

**Key Differences from arq**:
| Feature | arq (Redis) | LocalJobQueue (asyncio) |
|---------|-------------|------------------------|
| Backend | Redis | In-memory dict |
| Persistence | Durable | Lost on restart |
| Distribution | Multi-process/machine | Single process only |
| Dependencies | Redis, arq | asyncio only |
| Config | redis_host, redis_port | max_workers, worker_timeout |

---

## Part 2: Code References Analysis

### 2.1 Files Importing JobQueue

Found in codebase:

1. **`backend/src/api/routes/tasks.py`** (Line 14)
   ```python
   from ...workers.job_queue import JobQueue
   ```
   **Usage** (Line 98):
   ```python
   job_id = await JobQueue.enqueue_job(
       "process_video_task",
       task_id,
       raw_source["url"],
       source_type,
       user_id,
       font_family,
       font_size,
       font_color
   )
   ```
   **Issue**: Calls `JobQueue.enqueue_job()` as class method with string function name

2. **`backend/src/main_refactored.py`** (Line 21)
   ```python
   from .workers.job_queue import JobQueue
   ```
   **Usage** (Lines 48, 57):
   ```python
   await JobQueue.get_pool()        # Startup
   await JobQueue.close_pool()      # Shutdown
   ```
   **Issue**: main_refactored.py is not the active main.py; used for architectural reference

3. **`backend/src/workers/tasks.py`** (dependency reference)
   - Contains worker task definitions (arq-specific)
   - References `ctx['redis']` for progress tracking
   - Not directly imported but defines worker functions

4. **`backend/src/workers/progress.py`** (Line 7)
   - Uses `from redis.asyncio import Redis`
   - Tied to Redis-based progress tracking
   - Needs alternative for local queue

### 2.2 Active Entry Points

The **active** application entry point is `/Users/cspenn/Documents/github/supoclip/backend/src/main.py`:
- Does NOT import JobQueue directly
- Does NOT use arq or Redis
- Uses standard SQLite database
- Synchronous `POST /start` endpoint (not job queue based)

The **inactive** refactored entry point is `/Users/cspenn/Documents/github/supoclip/backend/src/main_refactored.py`:
- Imports JobQueue for lifespan management
- Uses async job queue for background processing
- Uses `tasks.py` worker functions

---

## Part 3: Root Cause Analysis

### Why Did This Happen?

**Timeline of Migration**:
1. Original architecture used Docker + PostgreSQL + Redis + arq workers
2. Migration to native macOS removed Docker dependency
3. Migration to SQLite removed PostgreSQL dependency
4. Migration removed Redis and arq from dependencies
5. **Gap**: `local_queue.py` was created as replacement, but:
   - Old `job_queue.py` was not replaced/deleted
   - Code still imports from `job_queue.py` instead of `local_queue.py`
   - Tasks.py and progress.py still reference arq/Redis patterns

### Codebase State

**Current Status**:
- ✅ `local_queue.py` - Complete replacement (READY TO USE)
- ✅ `local_progress.py` - Progress tracking replacement (READY TO USE)
- ❌ `job_queue.py` - Still tries to import removed `arq` (BROKEN)
- ❌ `tasks.py` - References arq context and Redis (PARTIALLY BROKEN)
- ❌ `progress.py` - References Redis/pub-sub (UNUSED)
- ✅ `config.py` - Fully configured for local queue (MAX_WORKERS, WORKER_TIMEOUT)
- ✅ Tests - Complete test suite for `LocalJobQueue` exists and passes

---

## Part 4: Required Interface and Usage Patterns

### 4.1 Current Usage (tasks.py)

```python
# What job_queue.py expects (BROKEN pattern)
await JobQueue.enqueue_job("process_video_task", task_id, url, ...)
# Returns: job_id (string)
```

### 4.2 LocalJobQueue Interface (AVAILABLE pattern)

```python
# Direct usage
queue = LocalJobQueue(max_workers=2)
await queue.enqueue_job(process_video_task, task_id, url, ...)
# Returns: job_id (string)

# Singleton pattern (recommended)
from src.workers.local_queue import get_job_queue
queue = get_job_queue()
await queue.enqueue_job(process_video_task, task_id, url, ...)
```

### 4.3 Key Differences

| Aspect | arq Pattern | LocalQueue Pattern |
|--------|-------------|-------------------|
| Job Identification | String function name | Async callable function object |
| Enqueueing | `await JobQueue.enqueue_job("func_name", ...)` | `await queue.enqueue_job(func, ...)` |
| Worker Context | `ctx` parameter with Redis | No context parameter |
| Progress Tracking | Redis pub/sub via `ctx['redis']` | In-memory event notification |
| Persistence | Durable across restarts | Lost on restart |
| Distribution | Multi-process/multi-machine | Single-process only |

---

## Part 5: Implementation Plan

### Phase 1: Replace job_queue.py with Compatibility Wrapper

**Goal**: Create a drop-in replacement that delegates to LocalJobQueue

**File**: Replace `/Users/cspenn/Documents/github/supoclip/backend/src/workers/job_queue.py`

```python
"""
Job queue adapter - delegates to LocalJobQueue for compatibility.

This module provides a compatibility layer for code that still imports
from job_queue. It wraps the asyncio-based LocalJobQueue to provide
a unified interface.

Migration from Redis/arq to local asyncio queue:
- OLD: JobQueue.enqueue_job("process_video_task", args...)
- NEW: await get_job_queue().enqueue_job(process_video_task, args...)
"""

import logging
from typing import Optional, Callable, Any
from .local_queue import get_job_queue, LocalJobQueue

logger = logging.getLogger(__name__)


class JobQueue:
    """
    Compatibility wrapper for local asyncio job queue.

    Maintains the class-method interface of the original arq-based
    JobQueue while delegating to LocalJobQueue internally.
    """

    _instance: Optional[LocalJobQueue] = None

    @classmethod
    async def get_pool(cls) -> LocalJobQueue:
        """
        Get or create the job queue instance.

        For compatibility with original JobQueue API that had
        get_pool() for initialization.

        Returns:
            LocalJobQueue instance
        """
        if cls._instance is None:
            cls._instance = get_job_queue()
            logger.info("✅ Job queue initialized (local asyncio)")
        return cls._instance

    @classmethod
    async def close_pool(cls) -> None:
        """
        Close and cleanup the job queue.

        For compatibility with original JobQueue API that had
        close_pool() for shutdown.
        """
        if cls._instance is not None:
            await cls._instance.stop_workers()
            cls._instance = None
            logger.info("✅ Job queue closed")

    @classmethod
    async def enqueue_job(
        cls,
        function_name: str | Callable,
        *args: Any,
        **kwargs: Any
    ) -> str:
        """
        Enqueue a job for background processing.

        Args:
            function_name: Function name (str) or callable
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            job_id: Unique identifier for the enqueued job

        Note:
            For now, we accept string function names for API compatibility
            but ignore them - the actual function must be looked up by
            the caller or we need to refactor the worker pattern.
        """
        queue = await cls.get_pool()

        # Handle both string function names (old arq API) and callables
        if isinstance(function_name, str):
            # This is the old arq pattern - we'd need to resolve
            # the string to a function. For now, log a warning.
            logger.warning(
                f"Job enqueueing with string function name '{function_name}' "
                "is deprecated. Pass the actual function object instead."
            )
            # TODO: After refactoring tasks.py, this won't be needed
            # For now, we'll need to import and resolve the function
            from .tasks import process_video_task  # Import here to avoid circular deps
            actual_function = process_video_task
        else:
            actual_function = function_name

        job_id = await queue.enqueue_job(actual_function, *args, **kwargs)
        logger.info(f"📝 Enqueued job {job_id}")
        return job_id

    @classmethod
    async def get_job_status(cls, job_id: str) -> Optional[str]:
        """
        Get the status of a job.

        Args:
            job_id: The job ID

        Returns:
            Job status string ("queued", "processing", "completed", "error")
            or None if job not found
        """
        queue = await cls.get_pool()
        return queue.get_job_status(job_id)

    @classmethod
    async def get_job_result(cls, job_id: str) -> Any:
        """
        Get the result of a completed job.

        Args:
            job_id: The job ID

        Returns:
            Job result if completed, None otherwise
        """
        queue = await cls.get_pool()
        return queue.get_job_result(job_id)


# end backend/src/workers/job_queue.py
```

### Phase 2: Initialize LocalJobQueue in FastAPI Lifespan

**File**: Update `/Users/cspenn/Documents/github/supoclip/backend/src/main.py`

**Changes**:
```python
# Add imports
from .workers.local_queue import get_job_queue

# Update lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()

        # Initialize job queue
        queue = get_job_queue()
        await queue.start_workers()
        logger.info("✅ Job queue workers started")

        yield
    finally:
        # Shutdown job queue
        queue = get_job_queue()
        await queue.stop_workers()
        logger.info("✅ Job queue workers stopped")

        await close_db()
```

### Phase 3: Refactor tasks.py to Work Without arq Context

**File**: Update `/Users/cspenn/Documents/github/supoclip/backend/src/workers/tasks.py`

**Current Pattern** (arq-specific):
```python
async def process_video_task(
    ctx: Dict[str, Any],  # arq context with Redis
    task_id: str,
    ...
) -> Dict[str, Any]:
    progress = ProgressTracker(ctx['redis'], task_id)
```

**New Pattern** (local asyncio):
```python
async def process_video_task(
    task_id: str,
    url: str,
    ...
) -> Dict[str, Any]:
    # Use local progress tracker instead
    progress = LocalProgressTracker()
    # Update progress
    await progress.update(task_id, 0, "Starting...", "processing")
```

### Phase 4: Update Progress Tracking Integration

**Current**: tasks.py uses `ProgressTracker(ctx['redis'], task_id)`

**New**: tasks.py uses `LocalProgressTracker()` or global instance

**File**: Consider updating `backend/src/workers/progress.py` or creating adapter

---

## Part 6: Files That Need Updates

### Critical (Application Won't Start Without These)

1. **`backend/src/workers/job_queue.py`** ← REPLACE with compatibility wrapper
   - Remove arq imports
   - Import LocalJobQueue
   - Implement class methods that delegate to LocalJobQueue

2. **`backend/src/main.py`** ← ADD lifespan initialization
   - Import get_job_queue
   - Add startup: `await get_job_queue().start_workers()`
   - Add shutdown: `await get_job_queue().stop_workers()`

### Important (Functionality Won't Work Without These)

3. **`backend/src/workers/tasks.py`** ← REFACTOR worker function
   - Remove `ctx` parameter
   - Remove `ProgressTracker(ctx['redis'], ...)` dependency
   - Replace with local progress tracking (if needed)
   - Import actual `process_video_task` function

4. **`backend/src/api/routes/tasks.py`** ← UPDATE job enqueueing
   - Change from: `await JobQueue.enqueue_job("process_video_task", ...)`
   - Change to: Pass actual function, not string name
   - Or: Import function from tasks.py and pass it

### Optional (For Full Modernization)

5. **`backend/src/workers/progress.py`** ← Consider deprecating
   - Current: Redis-based pub/sub
   - Alternative: Already have `local_progress.py` as replacement
   - Decision: Keep both or consolidate?

---

## Part 7: Testing Strategy

### Existing Tests
- ✅ `tests/test_local_queue.py` - 20+ tests for LocalJobQueue (all passing)
- ✅ `tests/test_offline_capability.py` - Tests for offline queue
- ✅ `tests/test_configuration.py` - Configuration tests

### Required Validation
1. **Import Test**: `from src.workers.job_queue import JobQueue` works
2. **Startup Test**: `pytest tests/test_local_queue.py` passes
3. **Integration Test**: Application starts: `uvicorn src.main:app`
4. **API Test**: POST /tasks endpoint works without errors

---

## Part 8: Implementation Sequence (Minimal Risk)

### Step 1: Create Compatibility Wrapper (File Replacement)
- Replace `job_queue.py` with new implementation
- Keep the same import path: `from src.workers.job_queue import JobQueue`
- Verify: `python -c "from src.workers.job_queue import JobQueue"` works

### Step 2: Update Main Application Startup
- Add job queue initialization to `main.py` lifespan
- Verify: Application starts without errors

### Step 3: Fix Job Enqueueing
- Update `api/routes/tasks.py` to pass actual function
- Or: Update `job_queue.py` to resolve string function names

### Step 4: Verify End-to-End
- Run tests: `pytest tests/test_local_queue.py`
- Start app: `uvicorn src.main:app`
- Make API call: POST /tasks
- Check logs: Verify job processing works

### Step 5: Optional Cleanup
- Remove unused `main_refactored.py`
- Consolidate progress tracking if needed
- Update documentation

---

## Part 9: Configuration Summary

### Environment Variables (Already in Config)
- `MAX_WORKERS` (default: 2) - Number of job processing workers
- `WORKER_TIMEOUT` (default: 3600) - Timeout per job
- `DATABASE_URL` (SQLite) - Job data stored in DB
- `TEMP_DIR` - Temporary storage for video processing

### No Longer Needed
- `REDIS_HOST` - Removed
- `REDIS_PORT` - Removed
- All Redis-related environment variables

---

## Part 10: Risk Assessment

### Low Risk Changes
- ✅ Replacing `job_queue.py` - File is only imported by 2 files
- ✅ Adding startup/shutdown to main.py lifespan - Standard pattern
- ✅ Running existing tests - Suite already validates LocalJobQueue

### Medium Risk Changes
- ⚠️ Refactoring `tasks.py` - Changes worker function signature
- ⚠️ Updating `api/routes/tasks.py` - Changes job enqueueing call

### Mitigation Strategies
1. Create git checkpoint before each change
2. Run tests after each file modification
3. Test application startup after each change
4. Verify no regressions in existing functionality

---

## Summary

**Problem**: Backend fails to start with `ModuleNotFoundError: No module named 'arq'`

**Root Cause**: Migration removed arq dependency but old `job_queue.py` still imports it

**Solution**: Replace `job_queue.py` with a compatibility wrapper that uses the existing `LocalJobQueue` implementation

**Implementation**:
1. Replace job_queue.py (1 file)
2. Update main.py lifespan (add 4 lines)
3. Update api/routes/tasks.py job enqueueing (update 1 function call)
4. Optionally refactor tasks.py for better architecture

**Effort**: Low-to-Medium (3-4 small file changes)
**Risk**: Low (existing tests validate replacements)
**Impact**: CRITICAL (application can't start without this)
