# Job Queue Fix - Quick Reference Guide

## The Problem in One Picture

```
Current Code Flow (BROKEN):

    api/routes/tasks.py
         ↓
    from src.workers.job_queue import JobQueue  ← Import attempts
         ↓
    job_queue.py
         ↓
    from arq import create_pool  ← FAILS! arq not installed
         ↓
    ❌ ModuleNotFoundError: No module named 'arq'

What We Need (WORKING):

    api/routes/tasks.py
         ↓
    from src.workers.job_queue import JobQueue (compatibility wrapper)
         ↓
    job_queue.py (NEW - delegates to LocalJobQueue)
         ↓
    from .local_queue import get_job_queue
         ↓
    LocalJobQueue instance
         ↓
    ✅ Works! Uses asyncio.Queue, no external dependencies
```

---

## Files: Current vs. Required

### What Exists Now

| File | Status | Purpose |
|------|--------|---------|
| `job_queue.py` | ❌ BROKEN | Tries to import arq (removed) |
| `local_queue.py` | ✅ READY | Asyncio-based replacement |
| `local_progress.py` | ✅ READY | Progress tracking replacement |
| `progress.py` | ⚠️ UNUSED | Redis-based (no longer needed) |
| `tasks.py` | ⚠️ BROKEN | References arq ctx parameter |
| `main.py` | ✅ ACTIVE | Doesn't use JobQueue currently |
| `main_refactored.py` | ⚠️ INACTIVE | Uses JobQueue (reference only) |

### What Needs to Change

| File | Change | Priority |
|------|--------|----------|
| `job_queue.py` | REPLACE with wrapper | CRITICAL |
| `main.py` | ADD worker startup/shutdown | IMPORTANT |
| `api/routes/tasks.py` | FIX job enqueueing call | IMPORTANT |
| `workers/tasks.py` | REFACTOR worker function | OPTIONAL |

---

## Implementation Checklist

### Phase 1: Core Fix (Makes app start)
- [ ] **Step 1**: Replace `job_queue.py` with compatibility wrapper
  - [ ] Remove arq imports
  - [ ] Import LocalJobQueue
  - [ ] Implement class methods delegating to LocalJobQueue
  - [ ] Test: `python -c "from src.workers.job_queue import JobQueue"` ✅

- [ ] **Step 2**: Update `main.py` lifespan
  - [ ] Import `get_job_queue` from `local_queue`
  - [ ] Add startup: `await get_job_queue().start_workers()`
  - [ ] Add shutdown: `await get_job_queue().stop_workers()`
  - [ ] Test: `uvicorn src.main:app` starts ✅

- [ ] **Step 3**: Update `api/routes/tasks.py` job enqueueing
  - [ ] Import `process_video_task` function from `workers.tasks`
  - [ ] Change: `JobQueue.enqueue_job("process_video_task", ...)`
  - [ ] To: `JobQueue.enqueue_job(process_video_task, ...)`
  - [ ] Test: POST /tasks endpoint works ✅

### Phase 2: Refinement (Cleans up architecture)
- [ ] **Step 4**: Refactor `workers/tasks.py`
  - [ ] Remove `ctx` parameter
  - [ ] Remove `ctx['redis']` dependency
  - [ ] Update progress tracking mechanism
  - [ ] Test: Job execution completes ✅

- [ ] **Step 5**: Consider consolidating progress tracking
  - [ ] Decide: Keep both or use only `local_progress.py`
  - [ ] Update references if consolidating
  - [ ] Test: Progress tracking works ✅

### Phase 3: Validation
- [ ] Run: `pytest tests/test_local_queue.py` (all pass)
- [ ] Run: `pytest tests/test_offline_capability.py` (all pass)
- [ ] Run: `pytest tests/` (full suite passes)
- [ ] Manual: Start app and create a task
- [ ] Manual: Verify task processes without errors

---

## Code Changes Summary

### Change 1: Replace job_queue.py (~60 lines)

**OLD**: Imports arq, references redis_host/port
**NEW**:
```python
from .local_queue import get_job_queue, LocalJobQueue

class JobQueue:
    _instance = None

    @classmethod
    async def get_pool(cls) -> LocalJobQueue:
        if cls._instance is None:
            cls._instance = get_job_queue()
        return cls._instance

    @classmethod
    async def close_pool(cls):
        if cls._instance is not None:
            await cls._instance.stop_workers()
            cls._instance = None

    @classmethod
    async def enqueue_job(cls, function_name, *args, **kwargs) -> str:
        queue = await cls.get_pool()
        # Handle string function names for compatibility
        if isinstance(function_name, str):
            from .tasks import process_video_task
            actual_function = process_video_task
        else:
            actual_function = function_name
        return await queue.enqueue_job(actual_function, *args, **kwargs)

    @classmethod
    async def get_job_status(cls, job_id: str):
        queue = await cls.get_pool()
        return queue.get_job_status(job_id)

    @classmethod
    async def get_job_result(cls, job_id: str):
        queue = await cls.get_pool()
        return queue.get_job_result(job_id)
```

### Change 2: Update main.py lifespan (~6 lines)

**BEFORE**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        yield
    finally:
        await close_db()
```

**AFTER**:
```python
from .workers.local_queue import get_job_queue

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        queue = get_job_queue()
        await queue.start_workers()
        logger.info("✅ Job queue workers started")
        yield
    finally:
        queue = get_job_queue()
        await queue.stop_workers()
        await close_db()
```

### Change 3: Update api/routes/tasks.py (~5 lines)

**BEFORE**:
```python
from ...workers.job_queue import JobQueue

# In create_task():
job_id = await JobQueue.enqueue_job(
    "process_video_task",  ← String name
    task_id,
    raw_source["url"],
    ...
)
```

**AFTER**:
```python
from ...workers.job_queue import JobQueue
from ...workers.tasks import process_video_task  ← Add this import

# In create_task():
job_id = await JobQueue.enqueue_job(
    process_video_task,  ← Pass actual function
    task_id,
    raw_source["url"],
    ...
)
```

---

## Architecture Comparison

### OLD Architecture (Redis/arq)
```
Frontend
    ↓
Backend API (FastAPI)
    ↓
JobQueue (arq)
    ↓
Redis (external service)
    ↓
Worker Process (arq worker CLI)
    ↓
Task Processing

Characteristics:
- Distributed (multi-process/multi-machine)
- Persistent (survives restarts)
- Requires: Redis, arq, separate worker process
- Complex deployment
```

### NEW Architecture (Local Asyncio)
```
Frontend
    ↓
Backend API (FastAPI)
    ↓
JobQueue (LocalJobQueue)
    ↓
asyncio.Queue (in-memory)
    ↓
Worker Coroutines (in same process)
    ↓
Task Processing

Characteristics:
- Single-process (same FastAPI process)
- Non-persistent (lost on restart)
- Requires: asyncio only (Python stdlib)
- Simple deployment (one process)
- Perfect for: Local/offline development, single-machine deployments
```

---

## Key Concepts

### LocalJobQueue vs JobQueue

| Aspect | LocalJobQueue | JobQueue (wrapper) |
|--------|---------------|--------------------|
| Import Path | `from src.workers.local_queue import LocalJobQueue, get_job_queue` | `from src.workers.job_queue import JobQueue` |
| Interface | Instance methods | Class methods |
| Usage | `queue = LocalJobQueue()` → `await queue.enqueue_job(...)` | `await JobQueue.enqueue_job(...)` |
| Singleton | `get_job_queue()` returns global instance | `JobQueue._instance` manages internal instance |
| Purpose | Actual implementation | Compatibility layer for existing code |

### Function Parameter Difference

**OLD (arq style)**:
```python
await JobQueue.enqueue_job("process_video_task", task_id, url, ...)
# String function name - worker resolves it
```

**NEW (asyncio style)**:
```python
await queue.enqueue_job(process_video_task, task_id, url, ...)
# Function object - directly executable
```

**WRAPPER (compatibility)**:
```python
await JobQueue.enqueue_job("process_video_task", task_id, url, ...)
# OR
await JobQueue.enqueue_job(process_video_task, task_id, url, ...)
# Wrapper handles both!
```

---

## Configuration

### LocalJobQueue Configuration (in Config class)
```python
self.max_workers = int(os.getenv("MAX_WORKERS", "2"))
self.worker_timeout = int(os.getenv("WORKER_TIMEOUT", "3600"))
```

### Environment Variables
```bash
# Jobs
MAX_WORKERS=2              # Number of concurrent workers
WORKER_TIMEOUT=3600        # Timeout per job (seconds)

# No longer needed:
# REDIS_HOST
# REDIS_PORT
```

---

## Testing

### Existing Tests (Already Passing)
```bash
# Test local queue
pytest tests/test_local_queue.py -v

# Test offline capability
pytest tests/test_offline_capability.py -v

# Test configuration
pytest tests/test_configuration.py::TestJobQueueConfig -v
```

### Manual Testing
```bash
# 1. Import test
python -c "from src.workers.job_queue import JobQueue; print('✅ Import works')"

# 2. Start app
cd backend
uv run uvicorn src.main:app --reload

# 3. Create task (in another terminal)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"source": {"url": "https://example.com/video.mp4"}}'

# 4. Check logs for:
# ✅ Job queue workers started
# 📝 Enqueued job
# ✅ Job completed
```

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Revert changes
git checkout -- backend/src/workers/job_queue.py
git checkout -- backend/src/main.py
git checkout -- backend/src/api/routes/tasks.py

# 2. Or specific files
git checkout HEAD -- backend/src/main.py

# 3. Verify
git status
git diff
```

---

## Files Reference

### All Job Queue Related Files
```
backend/src/workers/
├── job_queue.py          ← REPLACE (was broken, now wrapper)
├── job_queue.py.bak      ← Original broken version (keep as reference)
├── local_queue.py        ← Use this (asyncio based)
├── local_queue_test      ← Delete after confirming works
├── progress.py           ← Old (Redis-based, unused)
├── local_progress.py     ← New (in-memory, ready to use)
├── tasks.py              ← Needs refactoring
├── __init__.py
└── __pycache__/

backend/src/api/routes/
└── tasks.py              ← Update imports

backend/src/
└── main.py               ← Update lifespan
```

---

## Success Criteria

All of these must be true:

1. ✅ `python -c "from src.workers.job_queue import JobQueue"` works
2. ✅ `uvicorn src.main:app` starts without errors
3. ✅ Log shows: "✅ Job queue workers started"
4. ✅ `pytest tests/test_local_queue.py` - all tests pass
5. ✅ API endpoint `POST /tasks` responds successfully
6. ✅ Jobs are processed (check logs for "✅ Job completed")

---

## Questions & Answers

**Q: Will this break anything?**
A: No. LocalJobQueue has been thoroughly tested. The wrapper maintains API compatibility.

**Q: What about job persistence?**
A: Jobs lost on restart (expected for local development). Production would need persistent queue.

**Q: Can I use the old Redis/arq?**
A: Yes, if you want - but it's not configured. The codebase has moved to local asyncio.

**Q: What about remote workers?**
A: LocalJobQueue is single-process only. For distributed workers, would need different solution.

**Q: When should I use main_refactored.py?**
A: It's for reference. The active app is main.py. Eventually may migrate to refactored version.

**Q: Why not use Celery or other queue?**
A: Project requirement: native macOS without Docker/Redis. Asyncio is Python stdlib.

---

## See Also

- Detailed Analysis: `docs/progress/fixes/2025-11-14-job-queue-analysis.md`
- Implementation Status: Check after running fixes
- Git History: `git log --oneline | grep -i "job\|queue\|arq\|redis"`
- Config Reference: `backend/src/config.py` (MAX_WORKERS, WORKER_TIMEOUT)
- Test Suite: `backend/tests/test_local_queue.py` (20+ tests)
