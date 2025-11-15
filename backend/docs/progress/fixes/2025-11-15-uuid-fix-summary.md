# UUID Auto-Generation Fix - Quick Summary

## The Problem

```
(sqlite3.IntegrityError) NOT NULL constraint failed: tasks.id
```

## Root Cause

SQLite's DEFAULT clause for UUID generation does NOT work with SQLAlchemy's `text()` wrapper for raw SQL queries.

```python
# Schema says this should work:
id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))

# But this fails when using text():
await db.execute(
    text("INSERT INTO tasks (user_id, status) VALUES (:user_id, :status)")
)
# ERROR: id column is NULL → violates NOT NULL constraint
```

## Why Source Creation Works But Task Creation Fails

| File | Method | Approach | UUID Generation | Status |
|------|--------|----------|-----------------|--------|
| source_repository.py | create_source() | SQLAlchemy ORM | Python default applies | ✅ WORKS |
| task_repository.py | create_task() | Raw SQL via text() | Relies on DB DEFAULT | ❌ FAILS |
| clip_repository.py | create_clip() | Raw SQL via text() | Relies on DB DEFAULT | ❌ WILL FAIL |

## The Fix

### Before (BROKEN):
```python
# task_repository.py
async def create_task(...) -> str:
    result = await db.execute(
        text("""
            INSERT INTO tasks (user_id, source_id, status)
            VALUES (:user_id, :source_id, :status)
            RETURNING id
        """),
        {"user_id": user_id, "source_id": source_id, "status": status}
    )
    return result.scalar()
```

### After (FIXED):
```python
# task_repository.py
import uuid  # ✅ ADDED

async def create_task(...) -> str:
    task_id = str(uuid.uuid4())  # ✅ ADDED: Explicit UUID generation

    result = await db.execute(
        text("""
            INSERT INTO tasks (id, user_id, source_id, status)
            VALUES (:id, :user_id, :source_id, :status)
            RETURNING id
        """),  # ✅ CHANGED: Added 'id' column
        {
            "id": task_id,  # ✅ ADDED: Include id in parameters
            "user_id": user_id,
            "source_id": source_id,
            "status": status
        }
    )
    return result.scalar()
```

## Files to Fix

1. **VUW-UUID-001:** `src/repositories/task_repository.py` - create_task()
   - Priority: CRITICAL (P0)
   - Blocks all video processing

2. **VUW-UUID-002:** `src/repositories/clip_repository.py` - create_clip()
   - Priority: HIGH (P1)
   - Blocks clip generation

3. **VUW-UUID-003:** `src/repositories/source_repository.py` - create_source()
   - Priority: LOW (P3)
   - Already works - verify only

## Quick Fix Checklist

For each repository file:

- [ ] Add `import uuid` at top
- [ ] Generate UUID before INSERT: `record_id = str(uuid.uuid4())`
- [ ] Add `id` to INSERT column list
- [ ] Add `:id` to VALUES clause
- [ ] Add `"id": record_id` to parameters dict
- [ ] Run `./checkpython.sh` - must be zero errors
- [ ] Test the create method
- [ ] Verify UUID in database

## Testing

### Test task creation:
```bash
# After fixing task_repository.py
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"source": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}}'

# Verify in database
sqlite3 backend/supoclip.db "SELECT id, status FROM tasks;"
# Should show valid UUID (e.g., a1b2c3d4-5678-...)
```

### Test clip creation:
```bash
# Clips created automatically during video processing
# After full pipeline runs, verify:
sqlite3 backend/supoclip.db "SELECT id, filename FROM generated_clips;"
# Should show valid UUIDs
```

## Detailed Documentation

See: `/Users/cspenn/Documents/github/supoclip/backend/docs/progress/fixes/2025-11-15-sqlite-uuid-repair-plan.md`

Contains:
- Complete technical analysis
- Before/after code for each file
- Step-by-step implementation guide
- Testing strategy
- Risk mitigation
- Rollback procedures
