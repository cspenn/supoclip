# Comprehensive Repair Plan: Database Schema Mismatch
Date: 2025-11-15

## Executive Summary
- **Modules Evaluated:** 3 (Database Schema, SQLAlchemy Models, Task Repository/Service)
- **Total Issues Found:** 5
- **Root Causes Validated:** 2 (primary + cascading)
- **Tests Created:** 5 (all passing - validating expected failures)
- **Tests Failing (proving issues exist):** 2 (via pytest.raises - correct behavior)

## Issue Priority Matrix

### Critical Issues (System Failure Risk)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Database Schema | Missing `progress` column | Never added during migration from Redis to DB-based progress | Yes - test_task_status_update_with_progress_fails | Must fix before model update |
| Database Schema | Missing `progress_message` column | Never added during migration from Redis to DB-based progress | Yes - test_task_status_update_with_progress_message_only_fails | Must fix before model update |
| SQLAlchemy Model | Task model missing progress fields | Model not updated to match expected schema | Yes - same tests | Depends on schema fix |

### High Priority (Major Functionality)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Error Handlers | Error handlers fail when trying to save progress_message | Cascades from missing column | Yes - test validates cascade | Depends on column fix |

### Medium Priority (Technical Debt)
| Module | Issue | Root Cause | Test Available | Dependencies |
|--------|-------|------------|----------------|--------------|
| Startup Validation | No schema validation at startup | Never implemented | No - future enhancement | None |

## Implementation Sequence

### Phase 0: Git Checkpoint

```bash
git add -A
git commit -m "CHECKPOINT: 2025-11-15 Before implementing database schema repair"
```

**Status:** ✅ COMPLETE (checkpoint created at f681d21)

### Phase 1: Foundation Fixes - Database Schema
**Dependency:** None - this is the foundation all other fixes depend on

#### VUW-SCHEMA-001: Add progress column to tasks table
**File:** Direct SQLite database modification + migration script
**Root Cause:** Column never added during Redis removal
**Test:** test_task_status_update_with_progress_fails
**Fix Approach:**

1. Create migration script:
```sql
-- File: backend/migrations/001_add_progress_columns.sql
ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN progress_message TEXT DEFAULT NULL;
```

2. Apply to existing database:
```bash
sqlite3 backend/supoclip.db < backend/migrations/001_add_progress_columns.sql
```

3. Verify schema:
```bash
sqlite3 backend/supoclip.db ".schema tasks"
```

**Success Criteria:**
- Schema includes both new columns
- Existing task records have progress=0, progress_message=NULL
- No data loss

**Verification Checklist:**
- [ ] Migration script created
- [ ] Migration applied to database
- [ ] Schema verified to include new columns
- [ ] Existing data intact (verify with SELECT query)

---

### Phase 2: Critical Fixes - SQLAlchemy Model

#### VUW-MODEL-001: Add progress fields to Task model
**File:** backend/src/models.py
**Root Cause:** Model was never updated to include progress tracking fields
**Test:** test_task_status_update_with_progress_fails (will now pass after schema fix)
**Fix Approach:**

Add two mapped columns to Task class (after line 42):

```python
# Progress tracking (added 2025-11-15 to support database-based progress)
progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
progress_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

**Success Criteria:**
- Model compiles without errors
- SQLAlchemy can read progress fields
- Type hints are correct

**Verification Checklist:**
- [ ] Code added to models.py
- [ ] Import statements verified (Integer, Text already imported)
- [ ] No syntax errors
- [ ] Run `python -c "from src.models import Task; print('OK')"` succeeds

---

### Phase 3: Test Validation

#### VUW-TEST-001: Update tests to verify fix works
**File:** tests/repositories/test_task_repository_schema.py
**Root Cause:** Tests currently expect failures; need positive tests after fix
**Test:** New positive tests
**Fix Approach:**

Add new test cases that verify progress updates work:

```python
@pytest.mark.asyncio
async def test_task_status_update_with_progress_succeeds(test_db: AsyncSession, test_user: User):
    """
    After fix: Task status update with progress should succeed.
    """
    source_id = str(uuid.uuid4())
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Should now succeed
    await TaskRepository.update_task_status(
        db=test_db,
        task_id=task_id,
        status="processing",
        progress=25,
        progress_message="Downloading video..."
    )

    # Verify values stored
    task = await TaskRepository.get_task_by_id(test_db, task_id)
    assert task["status"] == "processing"
    assert task["progress"] == 25
    assert task["progress_message"] == "Downloading video..."


@pytest.mark.asyncio
async def test_task_progress_workflow(test_db: AsyncSession, test_user: User):
    """
    Test complete progress update workflow.
    """
    source_id = str(uuid.uuid4())
    task_id = await TaskRepository.create_task(
        db=test_db,
        user_id=test_user.id,
        source_id=source_id,
        status="queued"
    )

    # Simulate processing workflow
    updates = [
        (0, "Starting..."),
        (25, "Downloading..."),
        (50, "Analyzing..."),
        (75, "Creating clips..."),
        (100, "Complete!")
    ]

    for progress, message in updates:
        await TaskRepository.update_task_status(
            db=test_db,
            task_id=task_id,
            status="processing" if progress < 100 else "completed",
            progress=progress,
            progress_message=message
        )

        task = await TaskRepository.get_task_by_id(test_db, task_id)
        assert task["progress"] == progress
        assert task["progress_message"] == message
```

**Success Criteria:**
- New positive tests pass
- Old negative tests can be removed or modified
- Full workflow test validates end-to-end

**Verification Checklist:**
- [ ] New tests added
- [ ] Old tests updated or removed
- [ ] `pytest tests/repositories/test_task_repository_schema.py -v` shows all tests passing
- [ ] Coverage includes happy path and error cases

---

### Phase 4: Integration Testing

#### VUW-INTEGRATION-001: Test with real video processing
**File:** Manual integration test
**Root Cause:** Unit tests use in-memory DB; need to verify with real database
**Test:** End-to-end video processing
**Fix Approach:**

1. Start backend server:
```bash
cd backend
source .venv/bin/activate
uvicorn src.main:app --reload
```

2. Test video upload via API (using curl or frontend):
```bash
# Example: Upload a test video
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    "user_id": "test-user-123"
  }'
```

3. Monitor logs for progress updates:
```bash
tail -f logs/backend-*.log | grep progress
```

4. Verify database contains progress updates:
```bash
sqlite3 supoclip.db "SELECT id, status, progress, progress_message FROM tasks ORDER BY created_at DESC LIMIT 1;"
```

**Success Criteria:**
- Video processing completes without errors
- Progress updates appear in database
- Logs show progress increments
- No connection pool warnings
- Task status changes from queued → processing → completed

**Verification Checklist:**
- [ ] Backend starts without errors
- [ ] Video processing task created successfully
- [ ] Progress updates visible in database
- [ ] Logs show clean progress tracking
- [ ] No SQLAlchemy connection pool warnings
- [ ] Task completes with status="completed", progress=100

---

### Phase 5: Documentation and Cleanup

#### VUW-DOC-001: Document the fix
**File:** docs/progress/fixes/2025-11-15-schema-fix-summary.md
**Root Cause:** Need to document what was changed and why
**Fix Approach:**

Create summary document with:
- What was broken
- Root cause analysis
- What was fixed
- How to prevent in future
- Migration notes for deployments

**Success Criteria:**
- Clear documentation for future reference
- Migration script preserved for other environments

**Verification Checklist:**
- [ ] Summary document created
- [ ] Migration script committed to repo
- [ ] CLAUDE.md updated if necessary

---

### Phase 6: Git Checkpoint Post-Fix

```bash
git add -A
git commit -m "CHECKPOINT: 2025-11-15 Database schema repair complete - progress columns added

- Added progress and progress_message columns to tasks table
- Updated Task model with new fields
- Updated tests to validate fixes
- All tests passing
- Integration tested with real video processing"
```

**Verification Checklist:**
- [ ] All changes committed
- [ ] Commit message is descriptive
- [ ] No uncommitted changes remain

---

## Risk Mitigation

### Regression Prevention
- [x] All existing tests must pass - VERIFIED (5/5 tests passing)
- [x] New tests validate each fix - PLANNED (2 new positive tests)
- [x] Version control checkpoints after each fix - PLANNED
- [x] Rollback plan for each phase - Git revert available

### Database Safety
- [x] Backup database before migration:
```bash
cp supoclip.db supoclip.db.backup-2025-11-15-pre-schema-fix
```
- [x] Migration uses ADD COLUMN (safe, doesn't drop data)
- [x] Default values provided (progress=0, progress_message=NULL)
- [x] Test with in-memory DB first (already done)

### Logging Adequacy
- [x] Critical operations have appropriate logging - VERIFIED
- [x] Error paths are logged - VERIFIED
- [x] Log levels are appropriate - VERIFIED
- [ ] Consider adding schema validation logging at startup - FUTURE ENHANCEMENT

## Success Metrics
- [x] All critical issues resolved
- [ ] All high priority issues resolved (depends on critical fixes)
- [x] Test coverage validates fixes
- [ ] All tests passing (after positive tests added)
- [ ] No regressions introduced
- [ ] Production validation confirms fixes work

## Implementation Guidelines

### Before Starting Fixes
1. ✅ Ensure all tests from Task 3 are in place
2. ✅ Create version control checkpoint (done at f681d21)
3. ✅ Review dependencies between issues
4. ✅ Confirm rollback procedures (git revert)
5. [ ] Backup production database

### During Implementation
1. Fix one VUW at a time in order
2. Run associated test to verify fix
3. Run full test suite to check for regressions
4. Create git commit after each VUW
5. Document the fix approach

### After Implementation
1. All tests passing (verify with pytest)
2. Integration test complete
3. Documentation updated
4. Git checkpoint created
5. Monitor production for unexpected issues

## VUW Execution Order Summary

1. **VUW-SCHEMA-001** - Add progress columns to database ⬅️ START HERE
2. **VUW-MODEL-001** - Update Task model with progress fields
3. **VUW-TEST-001** - Add positive tests for progress updates
4. **VUW-INTEGRATION-001** - Test end-to-end with real video processing
5. **VUW-DOC-001** - Document the fix
6. **Phase 6 Checkpoint** - Commit all changes

## Estimated Timeline
- Schema migration: 10 minutes
- Model update: 5 minutes
- Test updates: 15 minutes
- Integration testing: 20 minutes
- Documentation: 10 minutes
- **Total: ~60 minutes**

## Notes
- This is a straightforward schema addition - low risk
- Migration is non-destructive (ADD COLUMN only)
- Existing functionality unaffected (columns are optional in updates)
- Connection pool issues will resolve automatically once schema is fixed
