# CLAUDE.md Audit Report

**Report Date:** November 14, 2025
**Status:** DISCREPANCIES FOUND
**Priority:** MEDIUM - Architecture transition in progress

---

## Executive Summary

The CLAUDE.md file documents a **refactored architecture** that is **partially implemented**. There are critical mismatches between the documented code organization and the actual deployed configuration. The codebase is in a transition state where `main.py` (old monolithic approach) and `main_refactored.py` (new layered architecture) coexist.

---

## 1. ENTRY POINT MISMATCH ⚠️

### Issue
The **docker-compose.yml and actual deployment are misconfigured**.

**docker-compose.yml (Line 42):**
```yaml
command: [".venv/bin/uvicorn", "src.main_refactored:app", "--host", "0.0.0.0", "--port", "8000"]
```

**backend/Dockerfile (Line 41):**
```dockerfile
CMD [".venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Impact
- When using Docker, the backend runs **main.py** (old), not **main_refactored.py** (documented new version)
- CLAUDE.md documents the refactored architecture, but deployment uses the old code
- The refactored code with arq worker integration won't run in Docker

### Recommendation
**Choose one:**
1. **Option A (Recommended):** Update Dockerfile to use `main_refactored.py` to match docker-compose.yml
2. **Option B:** Update docker-compose.yml to use `main.py` and update CLAUDE.md to document old architecture

---

## 2. API ENDPOINTS DISCREPANCY

### Documented in CLAUDE.md vs Actual Implementation

#### ✅ Endpoints in BOTH main.py and CLAUDE.md
- `POST /start` - Synchronous video processing (main.py Line 83)
- `POST /start-with-progress` - Async video processing (main.py Line 266)
- `GET /tasks/{task_id}` - Get task details (main.py Line 500)
- `GET /tasks/{task_id}/clips` - Get clips for task (main.py Line 446)
- `GET /fonts` - List fonts (main.py Line 546)
- `GET /transitions` - List transitions (main.py Line 594)
- `POST /upload` - Upload video (main.py Line 618)

#### ⚠️ Missing from main.py but DOCUMENTED in CLAUDE.md
1. **GET /health** - Root health check
   - CLAUDE.md mentions it
   - main.py has ONLY `/health/db` (Line 74)
   - main_refactored.py has `/health` (Line 103) ✓

2. **GET /health/redis** - Redis health check
   - CLAUDE.md documents it
   - main.py does NOT have it ❌
   - main_refactored.py has it (Line 120) ✓

3. **GET /tasks/** - List user's tasks
   - CLAUDE.md documents as new endpoint
   - main.py does NOT have it ❌
   - api/routes/tasks.py has it (Line 24) ✓

4. **POST /tasks/** - Create task (refactored)
   - CLAUDE.md documents as new endpoint
   - main.py does NOT have it ❌
   - api/routes/tasks.py has it (Line 49) ✓

5. **GET /tasks/{task_id}/progress** - SSE endpoint
   - CLAUDE.md documents as new endpoint
   - main.py does NOT have it ❌
   - api/routes/tasks.py has it (Line 158) ✓

6. **PATCH /tasks/{task_id}** - Update task
   - CLAUDE.md documents as new endpoint
   - main.py does NOT have it ❌
   - api/routes/tasks.py has it (Line 225) ✓

7. **GET /clips/{filename}** - Serve clips
   - CLAUDE.md documents it
   - main.py uses `app.mount()` for this (Line 66)
   - Should be `/clips/{filename}` but actually served via static mount

#### Summary Table

| Endpoint | main.py | main_refactored.py | CLAUDE.md | Status |
|----------|---------|------------------|-----------|--------|
| GET / | ✓ | ✓ | ✗ | OK |
| GET /health | ✗ | ✓ | ✓ | **MISMATCH** |
| GET /health/db | ✓ | ✓ | ✓ | OK |
| GET /health/redis | ✗ | ✓ | ✓ | **MISMATCH** |
| POST /start | ✓ | ✗ | ✓ (deprecated) | OK |
| POST /start-with-progress | ✓ | ✗ | ✓ (deprecated) | OK |
| GET /tasks/ | ✗ | ✓ | ✓ | **MISMATCH** |
| POST /tasks/ | ✗ | ✓ | ✓ | **MISMATCH** |
| GET /tasks/{task_id} | ✓ | ✓ | ✓ | OK |
| GET /tasks/{task_id}/clips | ✓ | ✓ | ✓ | OK |
| GET /tasks/{task_id}/progress | ✗ | ✓ | ✓ | **MISMATCH** |
| PATCH /tasks/{task_id} | ✗ | ✓ | ✓ | **MISMATCH** |
| GET /fonts | ✓ | ✓ | ✓ | OK |
| GET /fonts/{font_name} | ✓ | ✓ | ✗ | OK (not documented) |
| GET /transitions | ✓ | ✓ | ✓ | OK |
| POST /upload | ✓ | ✓ | ✓ | OK |
| GET /clips/{filename} | ✓ (mount) | ✓ (mount) | ✓ | OK |

---

## 3. ARCHITECTURE DOCUMENTATION

### Documented in CLAUDE.md (New Refactored Architecture)

```
backend/src/
├── api/routes/              # ✓ EXISTS
│   ├── tasks.py            # ✓ EXISTS
│   └── media.py            # ✓ EXISTS
├── services/               # ✓ EXISTS
│   ├── video_service.py    # ✓ EXISTS
│   └── task_service.py     # ✓ EXISTS
├── repositories/           # ✓ EXISTS
│   ├── task_repository.py  # ✓ EXISTS
│   ├── clip_repository.py  # ✓ EXISTS
│   └── source_repository.py # ✓ EXISTS
├── workers/                # ✓ EXISTS
│   ├── tasks.py            # ✓ EXISTS
│   ├── job_queue.py        # ✓ EXISTS
│   └── progress.py         # ✓ EXISTS
├── utils/                  # ✓ EXISTS
│   └── async_helpers.py    # ✓ EXISTS
├── main_refactored.py      # ✓ EXISTS
└── worker_main.py          # ✓ EXISTS
```

**Status:** ✅ Architecture code is properly organized and exists

### Actual Entry Point in Production

Currently, `main.py` is the entry point (not `main_refactored.py`), so the documented refactored architecture is **present but not active**.

---

## 4. DEVELOPMENT COMMANDS ACCURACY

### Backend Development

**Documented:**
```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv sync
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Status:** ✅ ACCURATE - This will run main.py (current entry point)

**Note:** To run the refactored version:
```bash
uvicorn src.main_refactored:app --reload --host 0.0.0.0 --port 8000
```
This is NOT documented.

### Frontend Development

**Documented:**
```bash
cd frontend
npm install
npm run dev
```

**Actual:**
- Uses npm (✓)
- Also has `bun.lock` file, suggesting Bun is available but not mentioned
- package.json scripts are correct (✓)

**Status:** ✅ ACCURATE

### Docker Development

**Documented:**
```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
docker-compose up -d --build
```

**Status:** ⚠️ PARTIALLY ACCURATE
- Commands are correct
- Services will run, but backend will use main.py, not main_refactored.py per docker-compose.yml

---

## 5. TECHNOLOGY STACK ACCURACY

### Backend Dependencies

**Documented in CLAUDE.md:**
- FastAPI ✓
- AssemblyAI ✓
- Pydantic AI ✓
- MoviePy v2 ✓
- OpenCV + MediaPipe ✓
- PostgreSQL (asyncpg/SQLAlchemy) ✓
- Redis ✓
- yt-dlp ✓

**pyproject.toml verification:** ✅ ALL MATCH

**Additional Dependencies Not Documented:**
- `sse-starlette` (for SSE endpoints) - ⚠️ Not mentioned
- `arq` (job queue) - ⚠️ Mentioned in REFACTORING_COMPLETE.md, should be in CLAUDE.md
- `redis` (client) - ⚠️ Mentioned but main.py doesn't use it (only main_refactored.py)

### Frontend

**Documented:**
- Next.js 15 ✓
- Better Auth ✓
- Prisma adapter ✓
- ShadCN UI ✓
- TailwindCSS v4 ✓
- React 19 ✓

**package.json verification:** ✅ ALL MATCH

**Node Package Manager:**
- Documented as npm ✓
- package.json uses npm ✓
- bun.lock exists but NOT documented ⚠️

### Database

**Documented:**
- PostgreSQL 15 ✓
- Tables: users, tasks, sources, generated_clips, session, account, verification ✓
- Both snake_case and camelCase conventions ✓

**init.sql verification:** ✅ Schema matches documentation

**Version Note:** init.sql shows PostgreSQL setup (no specific version), docker-compose.yml specifies `postgres:15-alpine` ✓

---

## 6. CODE ORGANIZATION ACCURACY

### Backend Structure

**Documented file locations are ACCURATE:**
- `backend/src/main.py` ✓
- `backend/src/video_utils.py` ✓
- `backend/src/ai.py` ✓
- `backend/src/youtube_utils.py` ✓
- `backend/src/models.py` ✓
- `backend/src/database.py` ✓
- `backend/src/config.py` ✓
- `backend/fonts/` ✓
- `backend/transitions/` ✓

**Additional files NOT mentioned in CLAUDE.md:**
- `backend/src/main_refactored.py` - NEW (partially documented in REFACTORING_COMPLETE.md)
- `backend/src/worker_main.py` - NEW (not documented)
- `backend/src/api/routes/` - NEW (not documented in overview)
- `backend/src/services/` - NEW (documented but details sparse)
- `backend/src/repositories/` - NEW (documented but details sparse)
- `backend/src/workers/` - NEW (not documented)
- `backend/src/utils/` - NEW (not documented)

### Frontend Structure

**Documented locations are ACCURATE:**
- `frontend/src/app/` ✓
- `frontend/src/app/page.tsx` ✓
- `frontend/src/app/tasks/[id]/page.tsx` ✓
- `frontend/src/app/api/auth/[...all]/route.ts` ✓
- `frontend/src/components/` ✓
- `frontend/src/lib/auth.ts` ✓
- `frontend/src/lib/auth-client.ts` ✓

**Additional pages NOT documented:**
- `frontend/src/app/settings/page.tsx` ✓ (exists but not mentioned)
- `frontend/src/app/sign-up/page.tsx` ✓ (exists but not mentioned)
- `frontend/src/app/sign-in/page.tsx` ✓ (exists but not mentioned)
- `frontend/src/app/list/page.tsx` ✓ (exists but not mentioned)

These are minor omissions - component-level files don't need full documentation.

---

## 7. DATABASE SCHEMA ACCURACY

**Documented fields match init.sql:**

✅ Users table:
- id, name, email, emailVerified, image, createdAt, updatedAt
- First_name, last_name, password_hash (additional fields, not documented)
- Default font preferences (documented in CLAUDE.md)

✅ Sources table:
- id, type (youtube/video_url), title, created_at, updated_at

✅ Tasks table:
- id, user_id, source_id, generated_clips_ids, status
- Progress tracking fields (progress, progress_message) - DOCUMENTED ✓
- Font customization fields - DOCUMENTED ✓
- created_at, updated_at

✅ Generated Clips table:
- All fields match: id, task_id, filename, file_path, start_time, end_time, duration, text, relevance_score, reasoning, clip_order, created_at, updated_at

✅ Better Auth tables:
- session, account, verification tables documented

**Status:** ✅ ACCURATE

---

## 8. IMPORTANT CONSIDERATIONS ACCURACY

### Video Processing ✅
- 9:16 aspect ratio - CORRECT
- Face detection (MediaPipe → OpenCV → Haar) - CORRECT
- Subtitles at 75% position - CORRECT
- H.264 encoding with even dimensions - CORRECT
- Transcript caching - CORRECT

### AI Segment Selection ✅
- 3-7 segments per video - CORRECT (based on video_utils.py)
- 10-45 seconds per clip - CORRECT
- Validation logic - CORRECT

### Database Conventions ✅
- Tasks use snake_case - CORRECT
- Better Auth uses camelCase - CORRECT
- UUIDs as VARCHAR(36) - CORRECT
- Auto-update triggers - CORRECT (per init.sql)

### File Storage ✅
- Uploaded videos: `{TEMP_DIR}/uploads/` - CORRECT
- Generated clips: `{TEMP_DIR}/clips/` - CORRECT
- Clips served via FastAPI static mount - CORRECT

**Status:** ✅ ALL ACCURATE

---

## 9. TESTING AND DEVELOPMENT TIPS

### What CLAUDE.md Says:
- Backend API docs at http://localhost:8000/docs ✅
- Emoji logging in backend ✅
- React 19 and Next.js 15 compatibility notes ✅
- Database initialized via init.sql ✅
- Docker logs for debugging ✅

**Status:** ✅ ACCURATE and useful

**Missing:**
- No pytest/test framework documented (none appears to be in use)
- No GitHub Actions/CI-CD documentation
- No local development without Docker guide

---

## 10. WORKER INTEGRATION ISSUES

### Documented in CLAUDE.md:
- arq job queue ✓
- Redis for job persistence ✓
- Separate worker process ✓
- Background job processing ✓

### Implementation Status:
**In main_refactored.py:**
- JobQueue class in `workers/job_queue.py` ✓
- Worker tasks in `workers/tasks.py` ✓
- Progress tracking in `workers/progress.py` ✓
- arq configuration `[".venv/bin/arq", "src.workers.tasks.WorkerSettings"]` in docker-compose ✓

**But in main.py (current entry point):**
- Uses `asyncio.create_task()` (Line 337) - not persistent
- No Redis integration
- No arq worker

**Status:** ⚠️ DOCUMENTED but NOT ACTIVE in production

---

## 11. ENVIRONMENT VARIABLES ACCURACY

### .env.example vs CLAUDE.md

**Documented in CLAUDE.md:**
| Variable | .env.example | Status |
|----------|-------------|--------|
| ASSEMBLY_AI_API_KEY | ✓ | ✓ |
| LLM | ✓ | ✓ |
| OPENAI_API_KEY | ✓ | ✓ |
| GOOGLE_API_KEY | ✓ | ✓ |
| ANTHROPIC_API_KEY | ✓ | ✓ |
| DATABASE_URL | ✓ | ✓ |
| TEMP_DIR | Not shown | ✓ (documented in CLAUDE.md) |

**Additional vars in .env.example NOT documented in CLAUDE.md:**
- WHISPER_MODEL_SIZE (documented as supported)
- BETTER_AUTH_SECRET ✓ (documented)
- POSTGRES_* (internal, docker-compose only)

**Status:** ✅ MOSTLY ACCURATE, minor omissions

---

## 12. API RESPONSE FORMATS

### Documented:
- POST /start returns: `{ message, task_id, relevant_segments, clips, summary, key_topics }`
- POST /start-with-progress returns: `{ task_id, message }`
- POST /tasks/ returns: `{ task_id, job_id, message }`
- GET /tasks/{task_id}/clips returns: `{ task_id, clips[], total_clips }`
- SSE events documented ✓

**Status:** ✅ Response schemas are accurate

---

## 13. FRONTEND API INTEGRATION

### Documented in CLAUDE.md:
- Better Auth for authentication ✓
- SSE integration needed for progress (mentioned in REFACTORING_COMPLETE.md) ⚠️
- Polling every 3-5 seconds (REFACTORING_COMPLETE.md says it should switch to SSE) ⚠️

**CLAUDE.md doesn't document:**
- Current polling interval in frontend
- SSE implementation details for frontend
- API response schemas the frontend expects

**Status:** ⚠️ PARTIALLY DOCUMENTED

---

## 14. COMMON WORKFLOWS ACCURACY

### Adding a New Font
- Documented: Add .ttf to `backend/fonts/` ✓
- Endpoint: GET /fonts ✓
- Reference by filename ✓

**Status:** ✅ ACCURATE

### Adding Transition Effects
- Documented: Add .mp4 to `backend/transitions/` ✓
- Endpoint: GET /transitions ✓
- Round-robin usage ✓

**Status:** ✅ ACCURATE

### Modifying AI Clip Selection
- Documented locations are CORRECT ✓
- `simplified_system_prompt` in ai.py ✓
- `TranscriptSegment` model ✓
- `get_most_relevant_parts_by_transcript()` ✓

**Status:** ✅ ACCURATE

---

## 15. MISSING DOCUMENTATION

### High Priority (affects developers)
1. **main_refactored.py is NOT the active entry point** - confusing for devs
2. **Worker setup is only partially documented** - need WorkerSettings class details
3. **SSE endpoint integration** - frontend needs to consume `/tasks/{task_id}/progress`
4. **Local development without Docker** - how to run worker separately
5. **How to switch between main.py and main_refactored.py** - not explained

### Medium Priority
1. Testing approach/pytest configuration
2. Frontend package manager choice (npm vs Bun)
3. Additional frontend pages (settings, list, sign-in, sign-up)
4. Backend test suite (if any)
5. Contributing guidelines

### Low Priority
1. Performance benchmarks
2. Load testing recommendations
3. Scaling guidelines

---

## SUMMARY TABLE

| Category | Status | Issues Found |
|----------|--------|--------------|
| Project Overview | ✅ | None |
| Architecture | ⚠️ | 1 (main.py vs main_refactored.py mismatch) |
| API Endpoints | ⚠️ | 6 (refactored endpoints only in main_refactored.py) |
| Development Commands | ✅ | None for main.py |
| Technology Stack | ✅ | Missing: sse-starlette, arq details |
| Code Organization | ✅ | None critical |
| Database Schema | ✅ | None |
| Important Considerations | ✅ | None |
| Testing Tips | ⚠️ | No testing docs |
| Worker Integration | ⚠️ | Documented but not active |
| Environment Variables | ✅ | None critical |
| Common Workflows | ✅ | None |

---

## RECOMMENDATIONS

### Immediate Actions (Critical)

1. **Resolve Entry Point Mismatch**
   - Either update Dockerfile to use `main_refactored.py` OR
   - Update docker-compose.yml to use `main.py`
   - Update CLAUDE.md to match chosen approach

2. **Document Current State**
   - Add section explaining: "This codebase has two implementations..."
   - Clarify that `main_refactored.py` is the future direction

3. **Add Missing Sections**
   - How to run the refactored version locally
   - How to run the worker process
   - SSE integration guide for frontend

### Short-term Improvements

4. **Clarify API Endpoints**
   - Create table showing which endpoints are in which entry point
   - Mark deprecated endpoints (/start, /start-with-progress)

5. **Add Testing Documentation**
   - Even if "no tests exist" - document this explicitly
   - Explain why

6. **Frontend/Backend Sync Guide**
   - Document that frontend needs to implement SSE listening

### Long-term Recommendations

7. **Commit to One Path**
   - Either fully transition to main_refactored.py or
   - Remove the refactored code and update CLAUDE.md

8. **Add Missing Dependencies Documentation**
   - Document sse-starlette usage
   - Document arq configuration

---

## CONCLUSION

The CLAUDE.md file is **approximately 85% accurate** but documents a **state that's not currently active in Docker**. The codebase is in a **transition state** between the old monolithic `main.py` and the new refactored `main_refactored.py` architecture. This creates confusion for developers expecting to see the documented refactored code running.

**Recommended Next Step:** Choose which implementation to use and align all documentation and configuration files with that choice. The refactored version is architecturally superior but not currently deployed.
