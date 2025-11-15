# Cloud Dependencies Audit - SupoClip Backend

## Summary
The SupoClip backend has been partially migrated to remove cloud dependencies. However, there are still **CRITICAL** cloud service references that need to be identified and removed for a truly local-only application.

## Status
- SQLite: DONE (replaces PostgreSQL)
- Local Job Queue: DONE (replaces Redis/arq)
- Local Progress Tracking: DONE (replaces Redis pub/sub)
- YouTube Downloads: ACTIVE (yt-dlp - local, internet-required)
- Cloud LLM Support: OPTIONAL (configurable, local LLM default)
- Local Transcription: DONE (parakeet-mlx replaces AssemblyAI)

## DEPRECATED but Still Referenced
- Redis references in worker_main.py and old config attributes
- arq imports (worker_main.py still tries to import it)
- PostgreSQL configuration (config used to have it)

## Active Cloud/Network Dependencies
1. **YouTube Download** (yt-dlp) - Requires internet to download videos
2. **Cloud LLM Fallback** - Optional but configured for OpenAI/Anthropic/Google APIs
3. **Local LLM HTTP Endpoint** - Requires running koboldcpp at http://localhost:6969/v1

## Key Files with Cloud References

### HIGH PRIORITY (Actively Used)
- `/backend/src/youtube_utils.py` - yt-dlp for YouTube downloads
- `/backend/src/config.py` - Cloud LLM API keys configured
- `/backend/src/main_refactored.py` - Health check endpoint for Redis (line 119-127)
- `/backend/src/api/routes/tasks.py` - Redis connection attempt (lines 217-240)
- `/backend/src/workers/progress.py` - Still imports Redis

### MEDIUM PRIORITY (Legacy, Not Used in Current Flow)
- `/backend/src/worker_main.py` - References Redis host/port, imports arq
- `/backend/src/workers/job_queue.py.bak` - Old arq-based implementation
- `/backend/src/workers/progress.py.bak` - Old Redis-based progress tracking

### LOW PRIORITY (Config Only)
- No actual references to cloud storage services (S3, GCS, Azure Blob)
- No Docker-specific hardcoding in source code

## Detailed Findings

### 1. Redis References (DEPRECATED but still in code)
**Status**: Removed from active code path, but references remain

**Files**:
- `/backend/src/worker_main.py` line 22: References `config.redis_host` and `config.redis_port` (DEAD CODE - worker_main.py is not used)
- `/backend/src/api/routes/tasks.py` lines 217-240: Tries to connect to Redis for SSE updates (UNUSED - falls back gracefully if Redis not available)
- `/backend/src/main_refactored.py` lines 119-127: `/health/redis` endpoint (MISLEADING - not checking actual Redis)

**Analysis**:
- `Config` class no longer defines `redis_host` and `redis_port` - this will cause AttributeError if accessed
- Local progress tracking (`local_progress.py`) exists as replacement but isn't integrated in all paths
- SSE endpoint in tasks.py tries to import Redis, catches ImportError gracefully

### 2. Local LLM HTTP Endpoint (ACTIVE, INTENTIONAL)
**Status**: Active by design, supports both local and cloud LLM

**Files**:
- `/backend/src/config.py` lines 27-41: LLM configuration
- Default: `LOCAL_LLM_BASE_URL` = `http://localhost:6969/v1` (requires running service)
- Fallback: Cloud APIs (OpenAI, Anthropic, Google) if configured

**Analysis**:
- This is INTENTIONAL and expected for local development
- Requires running a local LLM service (koboldcpp) on port 6969
- Good design: local-first with cloud fallback

### 3. YouTube Download (ACTIVE, INTENTIONAL)
**Status**: Active and required for YouTube video processing

**Files**:
- `/backend/src/youtube_utils.py` - All functions
- `/backend/src/services/video_service.py` lines 39-56: `download_video()` method
- `/backend/src/main.py` lines 187, 434: Direct calls to `download_youtube_video()`

**Analysis**:
- Uses `yt-dlp` library for downloads
- Requires internet connectivity to YouTube
- This is a FUNCTIONAL REQUIREMENT, not optional
- Includes User-Agent headers to bypass YouTube restrictions (lines 47-53)
- Includes Android client switching for reliability (lines 55-58)

### 4. Cloud LLM API Keys (OPTIONAL, CONFIGURABLE)
**Status**: Optional fallback, disabled by default

**Files**:
- `/backend/src/config.py` lines 37-41: OpenAI, Anthropic, Google API key configuration
- `/backend/src/config.py` lines 110-118: `_has_cloud_api_key()` method
- `/backend/src/config.py` lines 73-91: `get_llm_model()` with fallback logic

**Analysis**:
- Cloud APIs are completely optional
- Local LLM is default (LOCAL_LLM_ENABLED=true by default)
- Will fail gracefully if local LLM not available AND no cloud keys set
- Configuration allows easy enabling/disabling

### 5. PostgreSQL References (COMPLETELY REMOVED)
**Status**: Successfully replaced with SQLite

**Files**:
- `/backend/src/database.py` - Using `aiosqlite` for SQLite, not asyncpg
- `/backend/src/config.py` lines 54-57: DATABASE_URL defaults to SQLite
- No asyncpg imports anywhere

**Analysis**:
- CLEAN migration, fully completed
- No PostgreSQL dependencies remain

### 6. arq/Job Queue References (LEGACY, NOT USED)
**Status**: Deprecated, replaced with local asyncio queue

**Files**:
- `/backend/src/worker_main.py` lines 9-10: Tries to import `arq`
- `/backend/src/workers/job_queue.py.bak` - Old implementation (backup)
- No current imports of `arq` in active code

**Analysis**:
- `/backend/src/workers/job_queue.py` is the NEW compatibility wrapper
- `/backend/src/workers/local_queue.py` provides actual implementation
- `worker_main.py` is LEGACY and not used by current system
- No production code tries to import arq

### 7. Docker Configuration (EXTERNAL ONLY)
**Status**: No hardcoding in Python code

**Files Checked**:
- No docker/container-specific code in `/backend/src`
- Docker is orchestration layer only, not application logic
- Config values can be overridden via environment variables

**Analysis**:
- CLEAN separation of concerns
- Application is container-agnostic

## Summary Table

| Dependency | Type | Status | Actively Used | Replacem ent | Priority |
|-----------|------|--------|--------------|-------------|----------|
| Redis | Cache/Queue | REMOVED | NO* | Local asyncio queue | CLEANUP |
| PostgreSQL | Database | REMOVED | NO | SQLite | DONE |
| arq | Job Queue | REMOVED | NO | Local asyncio queue | CLEANUP |
| YouTube (yt-dlp) | Service | ACTIVE | YES | Local alternative N/A | FUNCTIONAL |
| Cloud LLM | AI Service | OPTIONAL | NO (default) | Local parakeet-mlx | OPTIONAL |
| Local LLM HTTP | AI Service | ACTIVE | YES | N/A (required) | FUNCTIONAL |
| AssemblyAI | Transcription | REMOVED | NO | parakeet-mlx | DONE |
| OpenAI/Anthropic API | AI | OPTIONAL | NO (fallback) | N/A (optional) | OPTIONAL |

*RedIS is referenced in error handlers but not in active code path

## Recommended Cleanup Actions

### CRITICAL (Will cause errors)
1. Remove `config.redis_host` and `config.redis_port` references from `worker_main.py`
2. Remove or disable `/health/redis` endpoint in `main_refactored.py`
3. Update tasks.py SSE endpoint to use local_progress instead of Redis

### IMPORTANT (Dead code)
1. Delete or archive `worker_main.py` (legacy, not used)
2. Delete `jobs_queue.py.bak`, `progress.py.bak`
3. Remove arq imports and references

### NICE-TO-HAVE (Clarification)
1. Remove OpenAI/Anthropic/Google API key configuration from Config class
2. Add configuration check to fail early if local LLM not available
3. Document YouTube download as intentional external requirement

## Notes
- The migration is ~85% complete
- Main system works with NO cloud dependencies
- YouTube download is a FEATURE requirement, not a bug
- Local LLM HTTP requirement is intentional design choice
- Cloud LLM fallback is useful for users with API keys
