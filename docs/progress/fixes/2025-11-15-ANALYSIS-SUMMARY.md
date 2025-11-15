# Root Cause Analysis Summary: Video Processing Crash
Date: 2025-11-15

## Quick Reference
- **Primary Issue:** Database schema missing `progress` and `progress_message` columns
- **Impact:** Complete failure of all video processing tasks
- **Severity:** CRITICAL - Application crashes during core functionality
- **Fix Complexity:** LOW - Simple schema addition
- **Estimated Fix Time:** 60 minutes

## Root Cause

### Primary Cause
The SQLite database schema is missing two columns that the application code expects:
- `progress` (INTEGER) - stores processing progress percentage (0-100)
- `progress_message` (TEXT) - stores current processing step message

### How This Happened
During migration from cloud architecture to offline mode:
1. Previous version used Redis for real-time progress tracking via SSE
2. Redis was removed as part of offline migration
3. Code was updated to use database for progress tracking
4. **Schema was never migrated to add the columns**
5. **SQLAlchemy model was never updated to include the fields**

### Cascading Failures
1. **Primary:** UPDATE query fails with "no such column: progress"
2. **Secondary:** Error handler also fails trying to save progress_message
3. **Tertiary:** Failed transactions accumulate, exhausting connection pool (200+ leaked connections)
4. **Final:** Application becomes completely unresponsive

## Evidence

### From Production Logs
```
sqlite3.OperationalError: no such column: progress
[SQL: UPDATE tasks SET status = ?, progress = ?, progress_message = ? WHERE id = ?]
[parameters: ('processing', 0, 'Starting...', '1f28b6bc-d25c-40de-a42e-ba04afecdd2d')]
```

### From Database Schema
```sql
-- Current schema (MISSING progress columns):
CREATE TABLE tasks (
    id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    source_id VARCHAR(36),
    generated_clips_ids JSON,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    font_family VARCHAR(100) DEFAULT 'TikTokSans-Regular',
    font_size INTEGER DEFAULT '24',
    font_color VARCHAR(7) DEFAULT '#FFFFFF',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    -- NO progress INTEGER
    -- NO progress_message TEXT
    ...
)
```

### From Code
**Repository calls UPDATE with non-existent columns:**
```python
# task_repository.py line 100-106
if progress is not None:
    set_parts.append("progress = :progress")  # ← Column doesn't exist!

if progress_message is not None:
    set_parts.append("progress_message = :progress_message")  # ← Column doesn't exist!
```

**Service layer makes multiple calls:**
```python
# task_service.py
await task_repo.update_task_status(
    db, task_id, "processing",
    progress=0,  # ← Tries to save to non-existent column
    progress_message="Starting..."  # ← Tries to save to non-existent column
)
```

## Files Requiring Changes

### 1. Database Schema (CRITICAL)
**File:** `backend/supoclip.db`
**Change:** Add two columns to tasks table
```sql
ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN progress_message TEXT DEFAULT NULL;
```

### 2. SQLAlchemy Model (CRITICAL)
**File:** `backend/src/models.py`
**Change:** Add two mapped columns to Task class (after line 42)
```python
# Progress tracking (added 2025-11-15)
progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
progress_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

### 3. Tests (HIGH)
**File:** `tests/repositories/test_task_repository_schema.py`
**Change:** Add positive tests to verify progress updates work after fix

### 4. Migration Script (MEDIUM)
**File:** `backend/migrations/001_add_progress_columns.sql` (NEW)
**Change:** Create reusable migration script for other environments

## Repair Plan VUWs

Detailed VUWs are documented in `2025-11-15-comprehensive-repair-plan.md`. Summary:

1. **VUW-SCHEMA-001** - Add columns to database (10 min)
2. **VUW-MODEL-001** - Update Task model (5 min)
3. **VUW-TEST-001** - Add positive tests (15 min)
4. **VUW-INTEGRATION-001** - End-to-end testing (20 min)
5. **VUW-DOC-001** - Document the fix (10 min)

**Total estimated time:** 60 minutes

## Test Coverage

Created 5 tests in `tests/repositories/test_task_repository_schema.py`:

✅ **test_task_creation_without_progress** - Verifies basic task creation still works
✅ **test_task_status_update_with_progress_fails** - Reproduces primary failure
✅ **test_task_status_update_with_progress_message_only_fails** - Reproduces error handler failure
✅ **test_task_get_with_progress_gracefully_handles_missing_columns** - Verifies defensive reads work
✅ **test_connection_cleanup_after_failed_update** - Validates connection cleanup

All tests PASSING (correctly expect and catch OperationalError exceptions).

After fix, will need 2 new positive tests to verify progress updates work.

## Related Issues to Address Proactively

### Issue 1: No Schema Validation at Startup
**Impact:** Schema mismatches only discovered at runtime during actual operations
**Recommendation:** Add startup health check that validates schema matches models
**Priority:** Medium (prevent future issues)

### Issue 2: No Migration System
**Impact:** Schema changes require manual SQL intervention
**Recommendation:** Implement Alembic migrations or document manual migration process
**Priority:** Medium (improve development workflow)

### Issue 3: Defensive getattr() Pattern
**Impact:** Masks schema issues during reads but fails catastrophically during writes
**Recommendation:** After schema fix, consider removing defensive pattern and letting errors surface early
**Priority:** Low (code cleanup)

## Prevention Strategies

1. **Add startup schema validation:**
```python
# In application startup (lifespan)
async def validate_schema(db: AsyncSession):
    """Validate database schema matches SQLAlchemy models."""
    # Check that all model columns exist in database
    # Log warnings or raise errors if mismatches found
```

2. **Implement Alembic migrations:**
```bash
alembic init migrations
alembic revision --autogenerate -m "Add progress columns"
alembic upgrade head
```

3. **Add pre-commit schema checks:**
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: validate-schema
      name: Validate database schema
      entry: python -m scripts.validate_schema
      language: system
```

## Success Criteria

Fix is successful when:
- [ ] Schema includes progress and progress_message columns
- [ ] Task model defines progress fields
- [ ] All existing tests pass
- [ ] New positive tests pass
- [ ] Video processing completes end-to-end
- [ ] Progress updates visible in database
- [ ] No connection pool warnings in logs
- [ ] Task status progresses: queued → processing → completed

## Rollback Plan

If issues occur during fix:
```bash
# Restore database backup
cp supoclip.db.backup-2025-11-15-pre-schema-fix supoclip.db

# Revert code changes
git revert HEAD

# Restart backend
uvicorn src.main:app --reload
```

## Documentation Created

1. ✅ `2025-11-15-database-schema-qa-eval.md` - TASK 1: Module evaluation
2. ✅ `2025-11-15-database-schema-root-causes.md` - TASK 2: Root cause analysis
3. ✅ `2025-11-15-qa-test-audit.md` - TASK 3: Test validation report
4. ✅ `2025-11-15-comprehensive-repair-plan.md` - TASK 4: Complete repair plan
5. ✅ `2025-11-15-ANALYSIS-SUMMARY.md` - This document

## Next Steps

1. Review this analysis and repair plan
2. Backup production database
3. Execute VUW-SCHEMA-001 (add columns)
4. Execute VUW-MODEL-001 (update model)
5. Execute VUW-TEST-001 (add positive tests)
6. Execute VUW-INTEGRATION-001 (end-to-end testing)
7. Execute VUW-DOC-001 (document the fix)
8. Create git checkpoint
9. Monitor production for 24 hours

## Contact/Questions

If questions arise during implementation, refer to:
- Comprehensive repair plan for detailed VUW steps
- Root cause analysis for hypothesis validation
- Test audit for validation approach
- Module evaluation for complete system understanding
