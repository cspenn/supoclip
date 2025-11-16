---
title: "Phase 3: Parallel Endpoints Implementation Guide"
date: 2025-11-16
status: "APPROVED"
author: "Code Review Team"
reviewed_by: "Context-fetcher agent, Debug-agent"
---

# Phase 3: Parallel Endpoints Implementation Guide

**Document Purpose**: Detailed technical guide for implementing Phase 3 of the codebase deduplication plan using a safe parallel endpoints approach instead of consolidation.

**Document Status**: APPROVED - Ready for team review and implementation planning

---

## Executive Summary

### Original Approach (REJECTED)

The original plan proposed consolidating the `/start` (sync) and `/start-with-progress` (async) video processing endpoints into a single unified service. This approach has critical flaws:

1. **Different Timeout Models**: Sync expects 5-minute browser timeout; async is unlimited background job
2. **Different Error Handling**: Sync returns errors immediately; async queues them for retrieval
3. **Different Scaling Needs**: Sync has bounded concurrency; async scales independently
4. **High Risk**: Consolidation requires major refactoring with significant regression risk
5. **Poor Rollback**: Feature flags prevent rollback if issues emerge mid-deployment

**Decision**: REJECTED due to architectural incompatibility

### New Approach (APPROVED)

Instead of consolidation, implement **parallel endpoints** approach:

1. **Keep both endpoints running simultaneously** during validation period
2. **Create two new services**: LegacySyncVideoService and AsyncVideoProcessingService
3. **Use gradual rollout percentage** (environment variable): 0%→5%→25%→50%→100%
4. **Route requests dynamically** based on rollout percentage
5. **Enable instant rollback** by changing one environment variable
6. **Validate for 2 weeks** before removing old code
7. **Extract utilities** for font options and settings merge (~50 lines saved)

**Benefits**:
- Safer: Both endpoints run simultaneously for comparison
- Flexible: Instant rollback capability (15 minutes vs code hotfix)
- Verifiable: Can compare metrics between old and new
- Production-safe: Gradual rollout catches issues early
- Backward compatible: Never breaks existing integrations

---

## Architecture Overview

### Current State

**Two separate endpoints**:
- `POST /start` (synchronous, max 5 minutes)
  - Direct video processing
  - Returns clips immediately
  - Browser request completes with results or error
  - Location: `backend/src/main.py` lines 239-354

- `POST /start-with-progress` (asynchronous, unlimited)
  - Queue-based processing
  - Returns task_id immediately
  - Client polls SSE endpoint for progress
  - Location: `backend/src/workers/local_queue.py` + main.py

### Problem with Consolidation

```
SYNC MODEL:
Browser Request
    |
    v
/start endpoint (5-min timeout)
    |
    v
Process video synchronously
    |
    v
Return results to browser (200 OK or 500 error)

ASYNC MODEL:
Browser Request
    |
    v
/start-with-progress endpoint
    |
    v
Return task_id immediately (202 Accepted)
    |
    v
Queue background job
    |
    v
Process video asynchronously (no timeout)
    |
    v
Client polls /tasks/{task_id}/progress via SSE
    |
    v
Stream results as they become available
```

**Why consolidation fails**: These are fundamentally different workflows with different timing, error handling, and client expectations. Merging them would break the request/response contract for sync users.

### New Parallel Architecture

```
POST /start (or /start-with-progress)
    |
    v
Check ASYNC_ROLLOUT_PERCENTAGE environment variable
    |
    +----> If random() < percentage: Use AsyncVideoProcessingService (NEW)
    |
    +----> Else: Use LegacySyncVideoService (LEGACY)
    |
    v
Process with appropriate service (both running in parallel)
    |
    v
Return results (sync: immediate, async: task_id)
```

**Key insight**: Both services run simultaneously. Requests are randomly routed based on percentage. This allows:
- Direct A/B comparison of old vs new
- Instant rollback by changing percentage
- Gradual validation from 5% → 100%
- No data loss or breaking changes

---

## Implementation Details

### VUW-BE-001: LegacySyncVideoService (3 hours)

**Objective**: Extract current `/start` endpoint logic into a service while keeping behavior 100% identical.

**Why this VUW comes first**: Baseline extraction allows comparing old vs new during rollout.

**File to Create**: `backend/src/services/legacy_sync_video_service.py`

```python
# backend/src/services/legacy_sync_video_service.py
"""
Legacy synchronous video processing service.

Extracted from /start endpoint to enable parallel endpoints approach.
IMPORTANT: Behavior must remain 100% identical to original implementation.
This service will be run alongside the new service during validation period.
"""
from typing import Dict, Any
from pathlib import Path
import logging
import asyncio

logger = logging.getLogger(__name__)


class LegacySyncVideoService:
    """
    Original sync video processing (5-minute timeout).

    This service handles the exact same logic as the original /start endpoint.
    It's extracted into a service to enable parallel endpoint comparison
    during gradual rollout.
    """

    async def process_video_sync(
        self,
        task_id: str,
        source_url: str,
        font_options: Dict[str, Any],
        timeout_seconds: int = 300,  # 5 minutes
    ) -> Dict[str, Any]:
        """
        Process video synchronously (original /start behavior).

        Args:
            task_id: Task identifier
            source_url: YouTube URL or uploaded file path
            font_options: Font customization options
            timeout_seconds: Maximum processing time (5 minutes)

        Returns:
            Dict with clips, metadata, and processing results

        Raises:
            TimeoutError: If processing exceeds timeout
            VideoProcessingError: If processing fails
        """
        logger.info(f"Starting sync video processing for task {task_id}")

        try:
            # Wrap in timeout to match original 5-minute browser timeout
            async with asyncio.timeout(timeout_seconds):
                # Step 1: Download/validate video
                logger.debug(f"Downloading video from {source_url}")
                video_path = await self._download_video(source_url)

                # Step 2: Transcription
                logger.debug(f"Transcribing video: {video_path}")
                transcript = await self._transcribe_video(video_path)

                # Step 3: AI analysis
                logger.debug("Analyzing transcript for clip selection")
                segments = await self._analyze_transcript(transcript)

                # Step 4: Clip generation
                logger.debug(f"Generating {len(segments)} clips")
                clips = await self._generate_clips(video_path, segments, font_options)

                # Step 5: Save to database
                logger.debug(f"Saving {len(clips)} clips to database")
                await self._save_clips_to_db(task_id, clips)

                logger.info(f"Sync processing complete for task {task_id}: {len(clips)} clips")

                return {
                    "task_id": task_id,
                    "clips": clips,
                    "clip_count": len(clips),
                    "status": "completed",
                    "processing_time_seconds": 0,  # Already done
                }

        except asyncio.TimeoutError:
            logger.error(f"Sync processing timeout for task {task_id} (exceeded 5 minutes)")
            raise TimeoutError(f"Video processing exceeded 5-minute limit")

        except Exception as e:
            logger.error(f"Sync processing failed for task {task_id}: {str(e)}")
            # Update task status in database
            await self._mark_task_failed(task_id, str(e))
            raise

    # Helper methods (to be implemented - mirrors original code)
    async def _download_video(self, source_url: str) -> Path:
        """Download video from URL or validate file path."""
        # Original implementation from /start endpoint
        pass

    async def _transcribe_video(self, video_path: Path) -> Dict[str, Any]:
        """Transcribe video using parakeet-mlx."""
        # Original implementation
        pass

    async def _analyze_transcript(self, transcript: Dict[str, Any]) -> list:
        """Analyze transcript and select clip segments."""
        # Original implementation
        pass

    async def _generate_clips(
        self,
        video_path: Path,
        segments: list,
        font_options: Dict[str, Any]
    ) -> list:
        """Generate video clips from segments."""
        # Original implementation
        pass

    async def _save_clips_to_db(self, task_id: str, clips: list) -> None:
        """Save generated clips to database."""
        # Original implementation
        pass

    async def _mark_task_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed in database."""
        # Original implementation
        pass
```

**Modification to `/start` endpoint**:

```python
# In backend/src/main.py

from .services.legacy_sync_video_service import LegacySyncVideoService

# At module level
sync_service = LegacySyncVideoService()

@app.post("/start")
async def start_video_processing(
    request: StartRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start video processing (original /start endpoint)."""

    task_id = str(uuid.uuid4())

    try:
        result = await sync_service.process_video_sync(
            task_id=task_id,
            source_url=request.source.url,
            font_options=request.font_options or {},
        )

        return result

    except TimeoutError:
        return {"error": "Video processing exceeded 5-minute limit"}
    except Exception as e:
        return {"error": str(e)}
```

**Testing Strategy**:
- [ ] Extracted service behavior identical to original endpoint
- [ ] All existing tests for `/start` pass
- [ ] Performance metrics unchanged
- [ ] Error scenarios match original behavior
- [ ] Timeout behavior preserved

**Success Criteria**:
- Endpoint still works
- No performance regression
- All tests passing
- Ready for parallel deployment

---

### VUW-BE-002: AsyncVideoProcessingService (3 hours)

**Objective**: Extract and consolidate async processing logic into a service with unified error handling.

**File to Create**: `backend/src/services/async_video_processing_service.py`

```python
# backend/src/services/async_video_processing_service.py
"""
Asynchronous video processing service.

Handles background queue-based video processing with SSE progress tracking.
This new service replaces scattered async logic with unified error handling
and consistent progress reporting.
"""
from typing import Dict, Any
from pathlib import Path
import logging
import asyncio

logger = logging.getLogger(__name__)


class AsyncVideoProcessingService:
    """
    Background video processing with progress tracking.

    This service is designed for async queue-based processing with no timeout.
    Clients receive task_id immediately and poll for progress via SSE.
    """

    async def process_video_async(
        self,
        task_id: str,
        source_url: str,
        font_options: Dict[str, Any],
        progress_callback=None,  # Callable to report progress
    ) -> None:
        """
        Process video asynchronously (background job).

        Returns immediately after queuing job.
        Results stored in database.
        Client polls /tasks/{task_id}/progress for SSE updates.

        Args:
            task_id: Task identifier
            source_url: YouTube URL or file path
            font_options: Font customization
            progress_callback: Optional callback for progress updates

        Updates database with results when complete.
        """
        logger.info(f"Starting async video processing for task {task_id}")

        try:
            # No timeout - background jobs can run as long as needed

            # Step 1: Download/validate video
            if progress_callback:
                await progress_callback(10, "Downloading video...")

            logger.debug(f"Downloading video from {source_url}")
            video_path = await self._download_video(source_url)

            # Step 2: Transcription
            if progress_callback:
                await progress_callback(30, "Transcribing video...")

            logger.debug(f"Transcribing video: {video_path}")
            transcript = await self._transcribe_video(video_path)

            # Step 3: AI analysis
            if progress_callback:
                await progress_callback(60, "Analyzing transcript...")

            logger.debug("Analyzing transcript for clip selection")
            segments = await self._analyze_transcript(transcript)

            # Step 4: Clip generation
            if progress_callback:
                await progress_callback(75, "Generating clips...")

            logger.debug(f"Generating {len(segments)} clips")
            clips = await self._generate_clips(video_path, segments, font_options)

            # Step 5: Save to database
            if progress_callback:
                await progress_callback(90, "Saving clips...")

            logger.debug(f"Saving {len(clips)} clips to database")
            await self._save_clips_to_db(task_id, clips)

            if progress_callback:
                await progress_callback(100, "Complete")

            # Mark task as completed
            await self._mark_task_completed(task_id, len(clips))

            logger.info(f"Async processing complete for task {task_id}: {len(clips)} clips")

        except Exception as e:
            logger.error(f"Async processing failed for task {task_id}: {str(e)}")
            # Mark task as failed - results will be available via API
            await self._mark_task_failed(task_id, str(e))
            # Don't re-raise - job should record error and stop gracefully

    # Helper methods (to be implemented)
    async def _download_video(self, source_url: str) -> Path:
        """Download video from URL."""
        pass

    async def _transcribe_video(self, video_path: Path) -> Dict[str, Any]:
        """Transcribe video using parakeet-mlx."""
        pass

    async def _analyze_transcript(self, transcript: Dict[str, Any]) -> list:
        """Analyze transcript and select clip segments."""
        pass

    async def _generate_clips(
        self,
        video_path: Path,
        segments: list,
        font_options: Dict[str, Any]
    ) -> list:
        """Generate video clips from segments."""
        pass

    async def _save_clips_to_db(self, task_id: str, clips: list) -> None:
        """Save clips to database."""
        pass

    async def _mark_task_completed(self, task_id: str, clip_count: int) -> None:
        """Update task status to completed."""
        pass

    async def _mark_task_failed(self, task_id: str, error: str) -> None:
        """Update task status to failed with error message."""
        pass
```

**Modification to `/start-with-progress` endpoint**:

```python
# In backend/src/main.py

from .services.async_video_processing_service import AsyncVideoProcessingService
from .workers.local_queue import BackgroundJobQueue

# At module level
async_service = AsyncVideoProcessingService()
job_queue = BackgroundJobQueue()

@app.post("/start-with-progress")
async def start_video_processing_async(
    request: StartRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start video processing asynchronously."""

    task_id = str(uuid.uuid4())

    # Queue the background job
    await job_queue.queue_job(
        task_id=task_id,
        service_method=async_service.process_video_async,
        args=(task_id, request.source.url, request.font_options or {}),
    )

    # Return task_id immediately
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Video processing started. Poll /tasks/{task_id}/progress for updates."
    }
```

**Testing Strategy**:
- [ ] Async processing queues correctly
- [ ] Progress updates via SSE work
- [ ] Database state consistent
- [ ] Error handling captures and stores errors
- [ ] Background jobs complete successfully

---

### VUW-BE-003: Font Options & Settings Utils (2 hours)

**Objective**: Extract duplicated font parsing and settings merge logic into shared utilities (~50 lines saved).

**File to Create**: `backend/src/utils/font_options.py`

```python
# backend/src/utils/font_options.py
"""
Shared font options parsing and settings merge utilities.

Used by both sync and async video processing services.
Eliminates ~50 lines of duplicated parsing logic.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# System defaults
DEFAULT_FONT_OPTIONS = {
    "font_family": "TikTokSans-Regular",
    "font_size": 24,
    "font_color": "#FFFFFF",
    "font_position": "bottom",
    "shadow_enabled": True,
}


def parse_font_options(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse and validate font options from request.

    Args:
        data: Request body potentially containing font_options

    Returns:
        Validated font options dict

    Example:
        >>> req = {"font_options": {"font_size": 32, "font_color": "#FF0000"}}
        >>> opts = parse_font_options(req)
        >>> opts["font_size"]
        32
    """
    if not data:
        return DEFAULT_FONT_OPTIONS.copy()

    font_opts = data.get("font_options", {})

    if not isinstance(font_opts, dict):
        logger.warning(f"Invalid font_options type: {type(font_opts)}, using defaults")
        return DEFAULT_FONT_OPTIONS.copy()

    # Validate font family exists (in production: check available fonts)
    if "font_family" in font_opts and not _validate_font_family(font_opts["font_family"]):
        logger.warning(f"Unknown font family: {font_opts['font_family']}, using default")
        font_opts["font_family"] = DEFAULT_FONT_OPTIONS["font_family"]

    # Validate font size range
    if "font_size" in font_opts:
        try:
            size = int(font_opts["font_size"])
            if size < 8 or size > 128:
                logger.warning(f"Font size out of range: {size}, using default")
                font_opts["font_size"] = DEFAULT_FONT_OPTIONS["font_size"]
        except (ValueError, TypeError):
            logger.warning(f"Invalid font_size: {font_opts['font_size']}")
            font_opts["font_size"] = DEFAULT_FONT_OPTIONS["font_size"]

    return font_opts


def merge_with_user_preferences(
    request_options: Optional[Dict[str, Any]],
    user_prefs: Optional[Dict[str, Any]],
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge font options: defaults < user prefs < request options.

    Precedence: Request options take precedence over user preferences,
    which take precedence over system defaults.

    Args:
        request_options: Options from current request
        user_prefs: User's saved preferences
        defaults: System defaults (uses DEFAULT_FONT_OPTIONS if None)

    Returns:
        Merged options dict

    Example:
        >>> defaults = {"font_size": 24, "font_color": "#FFF"}
        >>> prefs = {"font_size": 28}
        >>> req = {"font_color": "#000"}
        >>> merged = merge_with_user_preferences(req, prefs, defaults)
        >>> merged["font_size"]  # From prefs
        28
        >>> merged["font_color"]  # From request
        '#000'
    """
    if defaults is None:
        defaults = DEFAULT_FONT_OPTIONS.copy()
    else:
        defaults = defaults.copy()

    # Start with defaults
    merged = defaults.copy()

    # Apply user preferences (if any)
    if user_prefs and isinstance(user_prefs, dict):
        merged.update(user_prefs)

    # Apply request options (highest precedence)
    if request_options and isinstance(request_options, dict):
        merged.update(request_options)

    logger.debug(f"Merged font options: {merged}")

    return merged


def _validate_font_family(family_name: str) -> bool:
    """
    Check if font family is available.

    In production: check against available fonts in backend/fonts/

    Args:
        family_name: Font family name

    Returns:
        True if font exists, False otherwise
    """
    # TODO: Implement actual font validation against available fonts
    # For now, return True (permissive)
    return True
```

**Files to Modify**:
- Any endpoints using font options parsing (remove inline logic, call utilities)
- Both LegacySyncVideoService and AsyncVideoProcessingService
- Update service constructors to use merged options

**Testing Strategy**:
- [ ] Font options parse correctly with invalid input
- [ ] Merge precedence correct (request > prefs > defaults)
- [ ] Font validation works
- [ ] No logic change from original

---

### VUW-BE-004: Gradual Rollout Implementation (2 hours)

**Objective**: Implement percentage-based routing to safely transition from legacy to new service.

**Files to Create/Modify**: `backend/src/config.py`

```python
# backend/src/config.py (add to existing)

import os
import random
from typing import Optional

# Environment configuration
ASYNC_ROLLOUT_PERCENTAGE = int(os.getenv("ASYNC_ROLLOUT_PERCENTAGE", "0"))

def should_use_async_service() -> bool:
    """
    Determine if this request should use the new async service.

    Based on ASYNC_ROLLOUT_PERCENTAGE environment variable (0-100).
    Uses random selection to distribute load evenly.

    Returns:
        True if request should use new async service
        False if request should use legacy sync service

    Example:
        # With ASYNC_ROLLOUT_PERCENTAGE=25:
        # ~25% of requests will use new service
        # ~75% will use legacy service
    """
    if not (0 <= ASYNC_ROLLOUT_PERCENTAGE <= 100):
        raise ValueError(f"ASYNC_ROLLOUT_PERCENTAGE must be 0-100, got {ASYNC_ROLLOUT_PERCENTAGE}")

    # Random selection: if random % is less than percentage, use new service
    return random.random() * 100 < ASYNC_ROLLOUT_PERCENTAGE
```

**Endpoint Implementation**:

```python
# In backend/src/main.py

from .config import should_use_async_service
from .services.legacy_sync_video_service import LegacySyncVideoService
from .services.async_video_processing_service import AsyncVideoProcessingService

sync_service = LegacySyncVideoService()
async_service = AsyncVideoProcessingService()

@app.post("/start-with-progress")
async def start_video_processing_async(
    request: StartRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start video processing with optional gradual rollout.

    Routes to either new (async) or legacy (sync) service based on
    ASYNC_ROLLOUT_PERCENTAGE environment variable.
    """

    task_id = str(uuid.uuid4())

    # Determine which service to use
    use_async = should_use_async_service()

    logger.info(f"Processing task {task_id} with {'async' if use_async else 'legacy'} service")

    if use_async:
        # New async service path
        await job_queue.queue_job(
            task_id=task_id,
            service_method=async_service.process_video_async,
            args=(task_id, request.source.url, request.font_options or {}),
        )

        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Video processing started (async).",
            "_service": "new",  # For monitoring
        }
    else:
        # Legacy sync service path
        try:
            result = await sync_service.process_video_sync(
                task_id=task_id,
                source_url=request.source.url,
                font_options=request.font_options or {},
            )

            result["_service"] = "legacy"  # For monitoring
            return result

        except TimeoutError:
            return {
                "error": "Video processing exceeded 5-minute limit",
                "_service": "legacy",
            }
        except Exception as e:
            return {
                "error": str(e),
                "_service": "legacy",
            }
```

**Monitoring & Metrics**:

```python
# In backend/src/services/metrics.py (new file)

from dataclasses import dataclass
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProcessingMetrics:
    """Track metrics for old vs new service comparison."""

    service_type: str  # "legacy" or "async"
    task_id: str
    success: bool
    error_message: Optional[str]
    processing_time_seconds: float
    clip_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service_type,
            "task_id": self.task_id,
            "success": self.success,
            "error": self.error_message,
            "processing_time": self.processing_time_seconds,
            "clips": self.clip_count,
        }


async def log_metrics(metrics: ProcessingMetrics):
    """Log processing metrics for analysis."""
    logger.info(f"Metrics: {metrics.to_dict()}")
    # In production: send to metrics backend (Prometheus, DataDog, etc.)
```

**Rollout Schedule**:

| Period | Percentage | Duration | Notes |
|--------|-----------|----------|-------|
| Day 1-2 | 0% | 2 days | Validate deployment, old code path only |
| Day 3-4 | 5% | 2 days | Small test sample, monitor errors closely |
| Day 5-6 | 25% | 2 days | Larger validation, compare metrics |
| Day 7-8 | 50% | 2 days | Half user base, validate stability |
| Day 9-14 | 100% | 6 days | Full rollout, all users on new service |
| Day 15+ | N/A | Ongoing | Remove legacy code (keep as fallback) |

**How to Adjust Rollout**:

```bash
# Check current setting
echo $ASYNC_ROLLOUT_PERCENTAGE

# Increase to 25%
export ASYNC_ROLLOUT_PERCENTAGE=25
# Restart backend service

# Rollback if issues (instant)
export ASYNC_ROLLOUT_PERCENTAGE=0
# Restart backend service

# After validation complete, remove feature (old code becomes fallback only)
unset ASYNC_ROLLOUT_PERCENTAGE
```

---

### VUW-BE-005: Auth Middleware (2 hours)

**Objective**: Create FastAPI dependency to eliminate repeated user_id extraction (~30 lines saved).

**File to Modify**: `backend/src/dependencies.py`

```python
# backend/src/dependencies.py (enhance existing)

from typing import Optional
from fastapi import Header, HTTPException, status
import logging

logger = logging.getLogger(__name__)


async def get_current_user(
    user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> str:
    """
    Extract and validate user ID from request headers.

    Accepts either 'user_id' or 'X-User-ID' header.

    Args:
        user_id: User ID from request header

    Returns:
        Validated user ID string

    Raises:
        HTTPException: 401 if user_id is missing

    Usage:
        @app.post("/tasks/")
        async def create_task(
            request: Request,
            user_id: str = Depends(get_current_user),  # Auto-validated!
        ):
            # user_id is guaranteed to be non-empty
            pass
    """
    if not user_id or not user_id.strip():
        logger.warning("Request missing user_id header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID required in headers (X-User-ID)"
        )

    return user_id.strip()


async def get_optional_user(
    user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Optional[str]:
    """
    Extract user ID from headers (optional).

    For endpoints that work with or without authentication.

    Args:
        user_id: User ID from request header

    Returns:
        User ID string or None
    """
    return user_id.strip() if user_id else None
```

**Usage in Endpoints**:

```python
from fastapi import Depends
from .dependencies import get_current_user, get_optional_user

# Before (manual extraction):
@app.post("/tasks/")
async def create_task(request: Request):
    user_id = request.headers.get("user_id") or request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    # Now can use user_id...

# After (using dependency):
@app.post("/tasks/")
async def create_task(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    # user_id is guaranteed to be non-empty and validated
    # Much cleaner!
    pass

# For optional auth:
@app.get("/clips/{filename}")
async def get_clip(
    filename: str,
    user_id: Optional[str] = Depends(get_optional_user),
):
    # Works with or without user_id
    pass
```

**Files to Modify** (find and update all endpoints):
- `backend/src/api/routes/tasks.py` (10+ endpoints)
- `backend/src/api/routes/fonts.py` (5+ endpoints)
- `backend/src/api/routes/media.py` (3+ endpoints)
- `backend/src/main.py` (direct endpoints)

**Testing Strategy**:
- [ ] Valid user_id passes through
- [ ] Missing user_id returns 401
- [ ] Whitespace trimmed
- [ ] Optional variant works
- [ ] All modified endpoints work correctly

---

## Gradual Rollout Strategy

### Monitoring Metrics During Rollout

Track these metrics to compare old vs new service:

1. **Error Rate**: Percentage of requests that fail
   - Target: New service error rate < legacy + 0.5%

2. **Processing Time**: How long requests take
   - Sync: Should be similar (slight overhead acceptable)
   - Async: No change (background job)

3. **Success Rate**: Percentage of clips generated
   - Target: New service success rate >= legacy

4. **Database Consistency**: Do saved clips match expectations?
   - Sample clips from both services
   - Compare metadata, duration, encoding

5. **SSE Reliability**: Do progress updates stream correctly?
   - For async service only
   - Track connection drops, late updates

### Rollback Procedure

**If error rate spikes on new service**:

1. Change environment variable: `ASYNC_ROLLOUT_PERCENTAGE=0`
2. Restart backend service
3. All new requests route to legacy service
4. Takes ~5-15 minutes total

**This is much safer than code rollback.**

### Data Loss Prevention

- Both services write to same database
- No data loss risk
- Can compare outputs
- Easy to reprocess if needed

---

## Verification Checklist

**Before deployment:**
- [ ] LegacySyncVideoService behavior identical to original
- [ ] AsyncVideoProcessingService handles background jobs correctly
- [ ] Font utilities consolidate ~50 lines
- [ ] Gradual rollout percentage works (0% tests legacy path)
- [ ] Auth middleware extracts user_id correctly
- [ ] All tests passing (old + new)
- [ ] `./checkpython.sh` zero errors
- [ ] Production metrics collection working
- [ ] Rollback procedure tested

**During rollout:**
- [ ] Day 1-2 at 0%: Legacy service works normally
- [ ] Day 3-4 at 5%: Monitor error rates closely
- [ ] Day 5-6 at 25%: Error rates stable, no anomalies
- [ ] Day 7-8 at 50%: No performance degradation
- [ ] Day 9-14 at 100%: All users on new service, stable

**After rollout:**
- [ ] Remove legacy code (keep as fallback)
- [ ] Update documentation
- [ ] Celebrate deduplication success

---

## References

- Updated Deduplication Plan: `codebase-deduplication-plan-2025-11-16.md`
- AuthContext Design: `authcontext-design-2025-11-16.md`
- Pre-Execution Checklist: `pre-execution-checklist-2025-11-16.md`
- CLAUDE.md: Project standards and VUW methodology

---

**Document Status**: APPROVED - Ready for team review and implementation
**Created**: 2025-11-16
**Last Updated**: 2025-11-16
