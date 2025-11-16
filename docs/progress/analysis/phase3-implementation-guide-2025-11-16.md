# Phase 3 Implementation Guide: Backend Service Unification
**Date**: 2025-11-16
**Focus**: How to safely implement Phase 3 without production risk

---

## Problem Statement

**Original Plan**: Consolidate video processing logic from `main.py` (sync) and `workers/tasks.py` (async) into single `VideoProcessingService`.

**Issue**: These are fundamentally different workflows:
- **Sync**: Request → Process immediately → Response (max ~5 min videos)
- **Async**: Request → Enqueue → Return task_id → Stream progress (unlimited)

Consolidating breaks both workflows. Users with long videos fail silently.

---

## Better Approach: Parallel Endpoints + Gradual Rollout

### Architecture Overview

```
Current State:
├── GET /tasks/                (list tasks)
├── POST /start                (SYNC - old, in main.py)
└── POST /tasks/               (ASYNC - new, in routes/tasks.py)
    └── Uses JobQueue
        └── Uses TaskService

Target State:
├── GET /tasks/                (keep existing)
├── POST /api/v1/videos/sync   (SYNC - explicit, legacy)
│   └── LegacySyncVideoService
├── POST /api/v1/videos/async  (ASYNC - explicit, new)
│   └── AsyncVideoProcessingService
└── Gradual migration (5% → 25% → 50% → 100%)
```

### Why This is Better

1. **Clear Semantics**: Each endpoint explicit about its behavior
2. **Easy Rollback**: Keep old endpoint indefinitely
3. **Measurable**: Compare both paths side-by-side
4. **Safe**: No feature flag complexity
5. **Production Ready**: No impossible rollback scenarios

---

## Phase 3 Revised VUWs

### VUW-BE-001: Extract and Test Sync Service (3 hours)

**Objective**: Move sync logic from `main.py /start` into `LegacySyncVideoService`

**Current Code Location**: `backend/src/main.py` lines 131-354 (approximate)

**Deliverable**: `backend/src/services/legacy_sync_video_service.py`

```python
# backend/src/services/legacy_sync_video_service.py
"""
Legacy synchronous video processing service.
Maintains original behavior from /start endpoint.
For backwards compatibility and testing.
"""

class LegacySyncVideoService:
    """Synchronous video processing (original /start behavior)."""

    def __init__(self, config: Config):
        self.config = config

    async def process_video_synchronous(
        self,
        url: str,
        source_title: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ) -> Dict[str, Any]:
        """
        Process video synchronously - exactly like original /start endpoint.

        Warning: Will fail on videos >5 minutes.
        Use AsyncVideoProcessingService for production.
        """
        try:
            # Step 1: Download
            # Step 2: Transcribe
            # Step 3: Analyze
            # Step 4: Generate clips
            # Step 5: Return results
            pass
        except Exception as e:
            logger.error(f"Sync processing failed: {e}")
            raise
```

**Testing**:
- Create test with short sample video
- Verify output matches original `/start` endpoint
- Test error scenarios (invalid URL, etc.)

**Git Commit**:
```
VUW-BE-001: Extract legacy sync video processing service

- Create LegacySyncVideoService with original /start logic
- Maintains backwards compatibility
- To be used for testing and gradual migration
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-002: Extract and Test Async Service (3 hours)

**Objective**: Move async logic from `TaskService.process_task()` into `AsyncVideoProcessingService`

**Current Code Location**: `backend/src/services/task_service.py` method `process_task()`

**Deliverable**: `backend/src/services/async_video_processing_service.py`

```python
# backend/src/services/async_video_processing_service.py
"""
Async video processing service for production.
Uses job queue and progress tracking.
Suitable for videos of any length.
"""

from ..repositories.task_repository import TaskRepository
from ..repositories.clip_repository import ClipRepository
from ..workers.local_progress import ProgressTracker

class AsyncVideoProcessingService:
    """Asynchronous video processing for production use."""

    def __init__(
        self,
        task_repo: TaskRepository,
        clip_repo: ClipRepository,
        config: Config,
    ):
        self.task_repo = task_repo
        self.clip_repo = clip_repo
        self.config = config

    async def process_video_asynchronously(
        self,
        task_id: str,
        url: str,
        source_title: str,
        source_type: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Process video asynchronously with progress tracking.

        Returns immediately with task_id.
        Progress streamed via SSE.
        Suitable for videos of any length.
        """
        try:
            # Step 1: Download with progress
            # Step 2: Transcribe with progress
            # Step 3: Analyze with progress
            # Step 4: Generate clips with progress
            # Step 5: Return results
            pass
        except Exception as e:
            logger.error(f"Async processing failed: {e}")
            # Update task status to error
            raise
```

**Testing**:
- Create test with sample video
- Verify progress callbacks fire correctly
- Verify task status updates
- Verify error handling and recovery

**Git Commit**:
```
VUW-BE-002: Extract async video processing service

- Create AsyncVideoProcessingService from TaskService logic
- Adds progress tracking and error handling
- Production-ready for long videos
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-003: Create Parallel API Endpoints (2 hours)

**Objective**: Expose both services via new endpoints

**Deliverable**: Update `backend/src/api/routes/videos.py` (new file)

```python
# backend/src/api/routes/videos.py
"""
Video processing endpoints - v1 API.
Supports both sync and async workflows.
"""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...config import Config
from ...services.legacy_sync_video_service import LegacySyncVideoService
from ...services.async_video_processing_service import AsyncVideoProcessingService

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])
config = Config()

@router.post("/sync")
async def process_video_sync(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Synchronous video processing (legacy).
    Returns all clips in response.
    Warning: Fails on videos >5 minutes.
    Use /async for production.
    """
    data = await request.json()
    user_id = request.headers.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="User required")

    service = LegacySyncVideoService(config)

    try:
        result = await service.process_video_synchronous(
            url=data["url"],
            source_title=data.get("title", "Video"),
            font_family=data.get("font_family", "TikTokSans-Regular"),
            font_size=data.get("font_size", 24),
            font_color=data.get("font_color", "#FFFFFF"),
        )
        return {
            "clips": result.get("clips", []),
            "count": len(result.get("clips", [])),
            "source": "sync"  # Indicate which path was used
        }
    except Exception as e:
        logger.error(f"Sync processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/async")
async def process_video_async(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Asynchronous video processing (production).
    Returns task_id immediately.
    Progress streamed via SSE.
    Suitable for videos of any length.
    """
    data = await request.json()
    user_id = request.headers.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="User required")

    # Create task and enqueue job (existing implementation)
    # This is what /tasks POST already does
    # Keep existing implementation
    pass
```

**Include in main.py**:
```python
from .api.routes.videos import router as videos_router
app.include_router(videos_router)
```

**Testing**:
- Test both endpoints with sample video
- Verify correct service is called
- Verify response format matches expectations
- Test error cases

**Git Commit**:
```
VUW-BE-003: Add parallel video processing endpoints

- Create /api/v1/videos/sync endpoint (legacy)
- Create /api/v1/videos/async endpoint (production)
- Both endpoints fully functional
- Ready for gradual migration
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-004: Implement Gradual Rollout Mechanism (3 hours)

**Objective**: Enable controlled traffic migration from old to new

**Deliverable**: Update endpoints to use gradual rollout

```python
# backend/src/config.py (add to Config class)
class Config:
    # ... existing config ...

    # Gradual rollout percentage for new service
    ASYNC_ROLLOUT_PERCENTAGE = int(env.get("ASYNC_ROLLOUT_PERCENTAGE", 0))

# backend/src/api/routes/tasks.py (update existing POST /tasks endpoint)
@router.post("/")
async def create_task(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Create a new task and enqueue it for processing.

    Routes to async service with gradual rollout.
    Tracks metrics for both paths.
    """
    data = await request.json()
    user_id = request.headers.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="User required")

    # Determine which path to use
    rollout_percentage = config.ASYNC_ROLLOUT_PERCENTAGE
    should_use_new = (hash(user_id) % 100) < rollout_percentage

    # Log the decision
    logger.info(
        f"Task creation: user={user_id}, using={'NEW' if should_use_new else 'OLD'}, "
        f"rollout={rollout_percentage}%"
    )

    # Track metrics
    if should_use_new:
        metrics['async_service_count'] += 1
    else:
        metrics['legacy_service_count'] += 1

    try:
        if should_use_new:
            # Use AsyncVideoProcessingService
            service = AsyncVideoProcessingService(...)
            task_id = await service.create_and_queue_task(...)
        else:
            # Use existing/legacy implementation
            task_id = await existing_create_task_logic(...)

        logger.info(f"Task created: {task_id}")
        return {"task_id": task_id}

    except Exception as e:
        # Track errors by path
        if should_use_new:
            metrics['async_service_errors'] += 1
        else:
            metrics['legacy_service_errors'] += 1

        logger.error(f"Task creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Rollout Schedule**:
```
Day 1 (Mon):  ASYNC_ROLLOUT_PERCENTAGE=5   (5% of users)
Day 2 (Tue):  ASYNC_ROLLOUT_PERCENTAGE=5
Day 3 (Wed):  ASYNC_ROLLOUT_PERCENTAGE=10  (10% of users)
Day 4 (Thu):  ASYNC_ROLLOUT_PERCENTAGE=10
Day 5 (Fri):  ASYNC_ROLLOUT_PERCENTAGE=25  (25% of users)
Day 6-7:      ASYNC_ROLLOUT_PERCENTAGE=25
Day 8 (Mon):  ASYNC_ROLLOUT_PERCENTAGE=50  (50% of users)
Day 9-11:     ASYNC_ROLLOUT_PERCENTAGE=50
Day 12 (Thu): ASYNC_ROLLOUT_PERCENTAGE=100 (100% of users)
Day 13-14:    Monitor 100% rollout for any issues
Day 15:       If no issues, safe to remove old code
```

**Monitoring Requirements**:
```python
# Create metrics.py
class ProcessingMetrics:
    async_service_count = 0
    legacy_service_count = 0
    async_service_errors = 0
    legacy_service_errors = 0
    async_success_rate = 100.0
    legacy_success_rate = 100.0

    @property
    def async_error_rate(self):
        if self.async_service_count == 0:
            return 0.0
        return (self.async_service_errors / self.async_service_count) * 100

    @property
    def legacy_error_rate(self):
        if self.legacy_service_count == 0:
            return 0.0
        return (self.legacy_service_errors / self.legacy_service_count) * 100

    def should_halt_rollout(self):
        """Return True if async error rate exceeds 5%"""
        return self.async_error_rate > 5.0 and self.async_service_count > 100

# Log metrics every hour
async def log_metrics():
    logger.info(
        f"Metrics - Async: {metrics.async_service_count} calls, "
        f"{metrics.async_error_rate:.1f}% error rate. "
        f"Legacy: {metrics.legacy_service_count} calls, "
        f"{metrics.legacy_error_rate:.1f}% error rate."
    )
```

**Testing**:
- Simulate 100 users, verify distribution
- Verify metrics logged correctly
- Test error tracking
- Verify halt condition works

**Git Commit**:
```
VUW-BE-004: Implement gradual rollout mechanism

- Add ASYNC_ROLLOUT_PERCENTAGE config
- Route requests to old/new service based on user hash
- Track metrics for both paths
- Automatic halt if error rate >5%
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-005: Monitor and Complete Migration (3 hours)

**Objective**: Manage rollout day-by-day, respond to issues

**Activities**:
```
Day 1-7 (5% rollout):
- Monitor async error rate hourly
- Check response times
- Verify data consistency
- If issues: keep at 5% longer, debug
- If stable: proceed to next level

Day 8-11 (50% rollout):
- Increase monitoring frequency
- Run end-to-end tests with both paths
- Stress test with real workload
- Monitor database consistency
- If issues: lower percentage, investigate

Day 12 (100% rollout):
- All users on new service
- Monitor closely for 24 hours
- Check for edge cases
- Verify old service no longer needed

Day 13-14 (Stabilization):
- Monitor for any delayed issues
- Confirm data integrity
- Prepare to remove old code
```

**Rollback Procedure** (if issues found):
```python
# If async error rate exceeds 5%:
config.ASYNC_ROLLOUT_PERCENTAGE = 0  # Fall back to 0% immediately

# Log incident
logger.critical(f"Rollout halted: error rate exceeded threshold")

# Notify team
send_alert("Video processing rollout halted - investigating")

# Investigate while in fallback mode
# If can fix quickly: resume rollout
# If not: plan hotfix, rollback old code

# Check data consistency
# Determine if affected tasks need re-processing
```

**Git Commit**:
```
VUW-BE-005: Complete gradual rollout and migration

- Monitor metrics throughout rollout
- Handle issues and fallback scenarios
- Verify data consistency at each stage
- Document rollout results
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-006: Remove Legacy Code (2 hours)

**Objective**: Clean up after successful 100% migration (only after Day 14)

**Only proceed if**:
- 14 days of 100% rollout completed
- Zero issues found
- All metrics confirmed
- Team agreement obtained

**Remove**:
1. `LegacySyncVideoService` class
2. Old logic from `main.py /start` endpoint
3. Configuration for rollout percentage (set to 100 permanently)
4. Metrics tracking code

**Keep**:
- `AsyncVideoProcessingService` (now standard service)
- New endpoints

**Git Commit**:
```
VUW-BE-006: Remove legacy sync video processing code

- Delete LegacySyncVideoService
- Remove old /start endpoint implementation
- Clean up rollout metrics tracking
- Migration to async service complete
- Related to: codebase-deduplication-plan
```

---

### VUW-BE-007: Auth Middleware & Preferences (3 hours)

**Objective**: Extract auth patterns, optimize preferences

**VUW-BE-007a: Auth Middleware** (1.5 hours)
```python
# backend/src/dependencies.py (enhance existing)
from fastapi import Depends, HTTPException, Header

async def get_current_user(
    user_id: Optional[str] = Header(None)
) -> str:
    """
    Dependency: Extract and validate current user from headers.
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="User authentication required")
    return user_id

async def get_optional_user(
    user_id: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Dependency: Extract user from headers (optional).
    """
    return user_id
```

Usage in routes:
```python
@router.get("/tasks/")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Automatic auth validation via dependency."""
    # user_id is guaranteed to be present
    task_service = TaskService(db, config)
    tasks = await task_service.get_user_tasks(user_id)
    return {"tasks": tasks}
```

**VUW-BE-007b: Preferences Service** (1.5 hours)

**Don't create new service** - use existing `FontService`:

```python
# backend/src/api/routes/preferences.py (new)
@router.get("/preferences")
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Get user preferences using FontService."""
    font_service = get_font_service()
    prefs = await font_service.get_user_preferences(user_id)
    return prefs

@router.patch("/preferences")
async def update_preferences(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Update user preferences using FontService."""
    font_service = get_font_service()
    data = await request.json()
    prefs = await font_service.update_user_preferences(user_id, data)
    return prefs
```

**Testing**:
- Test auth dependency with/without header
- Test preferences endpoint
- Verify defaults work correctly

**Git Commit**:
```
VUW-BE-007: Extract auth middleware and leverage FontService for preferences

- Create get_current_user() dependency for routes
- Create get_optional_user() for public endpoints
- Use FontService for preference management
- Reduces manual auth checks in routes
- Related to: codebase-deduplication-plan
```

---

## Phase 3 Timeline

| VUW | Task | Hours | Timeline |
|-----|------|-------|----------|
| BE-001 | Extract Sync Service | 3 | Day 1 morning |
| BE-002 | Extract Async Service | 3 | Day 1 afternoon |
| BE-003 | Create Endpoints | 2 | Day 2 morning |
| BE-004 | Implement Rollout | 3 | Day 2 afternoon |
| BE-005 | Monitor Migration | 3 | Days 3-17 (2 weeks) |
| BE-006 | Remove Legacy | 2 | Day 18 |
| BE-007 | Auth + Prefs | 3 | Day 2 (parallel) |
| **TOTAL** | **7 parallel VUWs** | **20h** | **2.5 weeks** |

---

## Key Principles

### 1. Keep Old Code Until Confident
- Don't delete legacy code immediately
- Keep for at least 2 weeks at 100% rollout
- If issues surface late, old code is available

### 2. Monitor, Monitor, Monitor
- Track error rates for both paths
- Log decisions about which path is used
- Have metrics dashboard visible to team
- Halt rollout immediately if issues arise

### 3. Easy Rollback
- With parallel endpoints: flip config to 0%
- Old code remains functional
- No data migrations needed
- Can re-examine code for bugs

### 4. Clear Communication
- Document rollout schedule
- Notify team of each milestone
- Share metrics regularly
- Celebrate at 100% completion

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Async service has bugs | 40% | Run both for 2 weeks, compare metrics |
| Data inconsistency | 30% | Use same data schema in both paths |
| User confusion | 20% | Log which path each user takes |
| Rollback needed | 10% | Keep old code, easy config revert |

---

## Success Criteria

**Phase 3 is successful when**:
- ✅ All 7 VUWs completed
- ✅ 14 days at 100% async rollout completed
- ✅ Zero critical issues found
- ✅ Error rate <1% on async service
- ✅ Performance equivalent to old service
- ✅ Legacy code removed
- ✅ Team confidence high

---

## Questions?

Refer to:
- Full analysis: `/docs/progress/analysis/deduplication-plan-deep-analysis-2025-11-16.md`
- Executive summary: `/docs/progress/analysis/deduplication-executive-summary-2025-11-16.md`
- CLAUDE.md: Project standards
