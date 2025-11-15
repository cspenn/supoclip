# SQLite NOW() Function Incompatibility - Comprehensive Repair Plan
Date: 2025-11-15

## Executive Summary

**Issue:** PostgreSQL-specific `NOW()` function used in raw SQL queries causes SQLite failures.

**Root Cause:** Application uses raw SQL queries with PostgreSQL's `NOW()` function, which doesn't exist in SQLite. SQLite uses `CURRENT_TIMESTAMP` instead.

**Impact:**
- Task creation fails immediately (CRITICAL - blocks all video processing)
- Task status updates fail (CRITICAL - blocks workflow progression)
- Clip creation fails (CRITICAL - blocks final output)

**Total Occurrences:** 5 instances of `NOW()` across 3 files

**Resolution Strategy:** Remove explicit timestamp setting from INSERT/UPDATE queries and rely on schema defaults (`CURRENT_TIMESTAMP`) defined in `migrations/init_sqlite.sql`.

---

## Complete Inventory of NOW() Occurrences

### File 1: `src/repositories/task_repository.py` (3 occurrences)

#### Occurrence 1 - Task Creation (Line 30)
**Location:** `TaskRepository.create_task()`
**Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO tasks (user_id, source_id, status, font_family, font_size, font_color, created_at, updated_at)
        VALUES (:user_id, :source_id, :status, :font_family, :font_size, :font_color, NOW(), NOW())
        RETURNING id
    """),
    {...}
)
```

**Issue:** Uses `NOW()` for both `created_at` and `updated_at` columns
**Severity:** CRITICAL - This is the error reported by the user
**Schema Default:** Both columns have `DEFAULT CURRENT_TIMESTAMP` in schema (lines 47-48 of init_sqlite.sql)

#### Occurrence 2 - Task Status Update (Line 106)
**Location:** `TaskRepository.update_task_status()`
**Code:**
```python
query_parts.append("updated_at = NOW()")
query_parts.append("WHERE id = :task_id")
query = ", ".join(query_parts)
await db.execute(text(query), params)
```

**Issue:** Dynamically builds query string with `NOW()`
**Severity:** HIGH - Will fail when task status changes
**Schema Default:** `updated_at` has trigger `update_tasks_updated_at` (lines 134-139 of init_sqlite.sql) that auto-updates

#### Occurrence 3 - Task Clips Update (Line 120)
**Location:** `TaskRepository.update_task_clips()`
**Code:**
```python
await db.execute(
    text("UPDATE tasks SET generated_clips_ids = :clip_ids, updated_at = NOW() WHERE id = :task_id"),
    {"clip_ids": clip_ids, "task_id": task_id}
)
```

**Issue:** Explicit `NOW()` in UPDATE statement
**Severity:** HIGH - Will fail when saving generated clips
**Schema Default:** Same trigger as Occurrence 2 handles this automatically

---

### File 2: `src/repositories/clip_repository.py` (1 occurrence)

#### Occurrence 4 - Clip Creation (Line 37)
**Location:** `ClipRepository.create_clip()`
**Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO generated_clips
        (task_id, filename, file_path, start_time, end_time, duration,
         text, relevance_score, reasoning, clip_order, created_at)
        VALUES
        (:task_id, :filename, :file_path, :start_time, :end_time, :duration,
         :text, :relevance_score, :reasoning, :clip_order, NOW())
        RETURNING id
    """),
    {...}
)
```

**Issue:** Uses `NOW()` for `created_at` column
**Severity:** CRITICAL - Will fail when creating clip records
**Schema Default:** `created_at` has `DEFAULT CURRENT_TIMESTAMP` in schema (line 66 of init_sqlite.sql)

---

### File 3: `src/main.py` (1 occurrence)

#### Occurrence 5 - Legacy Task Status Update (Line 395)
**Location:** `update_task_status()` helper function
**Code:**
```python
async def update_task_status(task_id: str, status: str):
    """Update task status in database"""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE tasks SET status = :status, updated_at = NOW() WHERE id = :task_id"
            ),
            {"status": status, "task_id": task_id},
        )
        await db.commit()
```

**Issue:** Direct `NOW()` usage in UPDATE
**Severity:** MEDIUM - This appears to be legacy code, might be unused
**Schema Default:** Trigger handles auto-update
**Note:** This function appears to duplicate `TaskRepository.update_task_status()` - may be dead code

---

## Schema Analysis

The SQLite schema (`migrations/init_sqlite.sql`) already provides proper timestamp handling:

### Default Values (Lines 47-48, 66-67)
```sql
-- Tasks table
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

-- Generated clips table
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
```

### Auto-Update Triggers (Lines 134-139, 148-153)
```sql
CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_generated_clips_updated_at
AFTER UPDATE ON generated_clips
FOR EACH ROW
BEGIN
    UPDATE generated_clips SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

**Key Insight:** The schema is already configured correctly. The application code should NOT be setting timestamps explicitly - it should rely on schema defaults and triggers.

---

## Repair Strategy

### Approach
**Remove explicit timestamp columns from INSERT/UPDATE queries** and let the database schema handle timestamps via:
1. `DEFAULT CURRENT_TIMESTAMP` for inserts
2. Triggers for updates

### Why This Approach?
1. **Database-agnostic**: Works with both SQLite and PostgreSQL (when schema is configured correctly)
2. **Single source of truth**: Timestamp logic lives in schema, not scattered across repository code
3. **Cleaner code**: Removes redundant timestamp parameters
4. **Safer**: Prevents timestamp inconsistencies from application code

### Alternative Considered
Replace `NOW()` with `CURRENT_TIMESTAMP` - **REJECTED** because:
- Still duplicates schema logic
- Doesn't leverage existing triggers
- More code to maintain
- Could cause inconsistencies if triggers also fire

---

## Verifiable Units of Work (VUWs)

### VUW-1: Fix TaskRepository.create_task()
**File:** `src/repositories/task_repository.py`
**Line:** 28-32

**Current Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO tasks (user_id, source_id, status, font_family, font_size, font_color, created_at, updated_at)
        VALUES (:user_id, :source_id, :status, :font_family, :font_size, :font_color, NOW(), NOW())
        RETURNING id
    """),
    {...}
)
```

**Fixed Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO tasks (user_id, source_id, status, font_family, font_size, font_color)
        VALUES (:user_id, :source_id, :status, :font_family, :font_size, :font_color)
        RETURNING id
    """),
    {...}
)
```

**Verification Checklist:**
- [ ] Code compiles without syntax errors
- [ ] Test task creation in SQLite database
- [ ] Verify `created_at` and `updated_at` are auto-populated
- [ ] Check timestamps are in correct format
- [ ] Run `./checkpython.sh` - must report zero errors

---

### VUW-2: Fix TaskRepository.update_task_status()
**File:** `src/repositories/task_repository.py`
**Lines:** 98-111

**Current Code:**
```python
query_parts = ["UPDATE tasks SET status = :status"]

if progress is not None:
    query_parts.append("progress = :progress")

if progress_message is not None:
    query_parts.append("progress_message = :progress_message")

query_parts.append("updated_at = NOW()")
query_parts.append("WHERE id = :task_id")

query = ", ".join(query_parts)
await db.execute(text(query), params)
```

**Fixed Code:**
```python
query_parts = ["UPDATE tasks SET status = :status"]

if progress is not None:
    query_parts.append("progress = :progress")

if progress_message is not None:
    query_parts.append("progress_message = :progress_message")

# Note: updated_at auto-updated by trigger, no need to set explicitly
query_parts.append("WHERE id = :task_id")

query = ", ".join(query_parts)
await db.execute(text(query), params)
```

**Verification Checklist:**
- [ ] Code compiles without syntax errors
- [ ] Test task status update in SQLite database
- [ ] Verify `updated_at` is automatically updated by trigger
- [ ] Verify trigger updates timestamp correctly
- [ ] Run `./checkpython.sh` - must report zero errors

---

### VUW-3: Fix TaskRepository.update_task_clips()
**File:** `src/repositories/task_repository.py`
**Lines:** 119-121

**Current Code:**
```python
await db.execute(
    text("UPDATE tasks SET generated_clips_ids = :clip_ids, updated_at = NOW() WHERE id = :task_id"),
    {"clip_ids": clip_ids, "task_id": task_id}
)
```

**Fixed Code:**
```python
await db.execute(
    text("UPDATE tasks SET generated_clips_ids = :clip_ids WHERE id = :task_id"),
    {"clip_ids": clip_ids, "task_id": task_id}
)
```

**Verification Checklist:**
- [ ] Code compiles without syntax errors
- [ ] Test clips update in SQLite database
- [ ] Verify `updated_at` is automatically updated by trigger
- [ ] Check trigger behavior matches expectation
- [ ] Run `./checkpython.sh` - must report zero errors

---

### VUW-4: Fix ClipRepository.create_clip()
**File:** `src/repositories/clip_repository.py`
**Lines:** 30-39

**Current Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO generated_clips
        (task_id, filename, file_path, start_time, end_time, duration,
         text, relevance_score, reasoning, clip_order, created_at)
        VALUES
        (:task_id, :filename, :file_path, :start_time, :end_time, :duration,
         :text, :relevance_score, :reasoning, :clip_order, NOW())
        RETURNING id
    """),
    {...}
)
```

**Fixed Code:**
```python
result = await db.execute(
    text("""
        INSERT INTO generated_clips
        (task_id, filename, file_path, start_time, end_time, duration,
         text, relevance_score, reasoning, clip_order)
        VALUES
        (:task_id, :filename, :file_path, :start_time, :end_time, :duration,
         :text, :relevance_score, :reasoning, :clip_order)
        RETURNING id
    """),
    {...}
)
```

**Verification Checklist:**
- [ ] Code compiles without syntax errors
- [ ] Test clip creation in SQLite database
- [ ] Verify `created_at` and `updated_at` are auto-populated
- [ ] Check timestamp format is correct
- [ ] Run `./checkpython.sh` - must report zero errors

---

### VUW-5: Fix or Remove main.py update_task_status()
**File:** `src/main.py`
**Lines:** 390-399

**Investigation Required:**
1. Check if this function is actually called anywhere
2. If yes: Fix to match TaskRepository pattern
3. If no: Delete as dead code

**Option A - Fix (if used):**
```python
async def update_task_status(task_id: str, status: str):
    """Update task status in database"""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE tasks SET status = :status WHERE id = :task_id"
            ),
            {"status": status, "task_id": task_id},
        )
        await db.commit()
```

**Option B - Remove (if unused):**
Delete the entire function and verify no calls exist.

**Verification Checklist:**
- [ ] Search codebase for calls to this function
- [ ] If used: Apply fix and test
- [ ] If unused: Delete function
- [ ] Run `./checkpython.sh` - must report zero errors
- [ ] Verify no references remain

---

## Implementation Sequence

### Phase 0: Git Checkpoint
```bash
git add -A
git commit -m "CHECKPOINT: Before SQLite NOW() compatibility fixes"
```

### Phase 1: Critical Path Fixes (Blocks Task Creation)
**Order of execution:**
1. **VUW-1** - Fix `TaskRepository.create_task()` (IMMEDIATE - this is the reported error)
2. **VUW-4** - Fix `ClipRepository.create_clip()` (HIGH - needed for end-to-end flow)

**Rationale:** These are INSERT operations on the critical path. User cannot create tasks until VUW-1 is fixed.

### Phase 2: Update Operation Fixes
**Order of execution:**
3. **VUW-2** - Fix `TaskRepository.update_task_status()`
4. **VUW-3** - Fix `TaskRepository.update_task_clips()`

**Rationale:** These are UPDATE operations. Less critical than INSERTs but still required for complete workflow.

### Phase 3: Cleanup
**Order of execution:**
5. **VUW-5** - Investigate and fix/remove `main.py` helper function

**Rationale:** May be dead code, needs investigation. Lower priority.

### Phase 4: Git Checkpoint Post-Fix
```bash
git add -A
git commit -m "Fix SQLite compatibility: Replace NOW() with schema defaults

- Remove explicit timestamp setting from INSERT queries
- Remove explicit timestamp setting from UPDATE queries
- Rely on schema DEFAULT CURRENT_TIMESTAMP and triggers
- Fixes 5 occurrences across 3 files
- All tests passing"
```

---

## Testing Strategy

### Test 1: Task Creation Flow
```python
# Create a task
task_id = await TaskRepository.create_task(
    db=db,
    user_id="test-user",
    source_id="test-source-id",
    status="queued"
)

# Verify timestamps were set
task = await TaskRepository.get_task_by_id(db, task_id)
assert task["created_at"] is not None
assert task["updated_at"] is not None
assert isinstance(task["created_at"], datetime)
```

### Test 2: Task Update Flow
```python
# Update task status
await TaskRepository.update_task_status(
    db=db,
    task_id=task_id,
    status="processing",
    progress=50
)

# Verify updated_at changed
updated_task = await TaskRepository.get_task_by_id(db, task_id)
assert updated_task["updated_at"] > task["updated_at"]
```

### Test 3: Clip Creation Flow
```python
# Create a clip
clip_id = await ClipRepository.create_clip(
    db=db,
    task_id=task_id,
    filename="test.mp4",
    file_path="/path/to/test.mp4",
    start_time="00:10",
    end_time="00:30",
    duration=20.0,
    text="Test clip",
    relevance_score=0.95,
    reasoning="Test reasoning",
    clip_order=1
)

# Verify timestamp was set
result = await db.execute(
    text("SELECT created_at FROM generated_clips WHERE id = :clip_id"),
    {"clip_id": clip_id}
)
row = result.fetchone()
assert row.created_at is not None
```

### Test 4: End-to-End Video Processing
```bash
# Run actual video processing
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "test-video.mp4"},
    "font_options": {
      "font_family": "TikTokSans-Regular",
      "font_size": 24,
      "font_color": "#FFFFFF"
    }
  }'

# Check logs for successful task creation
tail -100 logs/application.log | grep "Created task"

# Verify no NOW() errors
tail -100 logs/application.log | grep -i "no such function"
```

---

## Risk Assessment

### High Risk Areas
1. **Trigger Dependency**: If SQLite triggers don't fire as expected, `updated_at` won't update
   - **Mitigation**: Test trigger behavior explicitly before deploying

2. **Timestamp Format**: SQLite vs PostgreSQL datetime format differences
   - **Mitigation**: Verify timestamp format in tests

3. **Schema Migration**: Users with existing databases may need migration
   - **Mitigation**: Document that `migrations/init_sqlite.sql` must be applied

### Low Risk Areas
1. **Code Changes**: Simple string removals, low risk of introducing bugs
2. **Performance**: No performance impact (removing code is faster)

---

## Success Metrics

- [ ] All 5 `NOW()` occurrences removed or fixed
- [ ] Task creation succeeds without errors
- [ ] Task updates work correctly
- [ ] Clip creation succeeds
- [ ] Timestamps are auto-populated correctly
- [ ] Triggers fire as expected
- [ ] `./checkpython.sh` reports zero errors
- [ ] All tests pass
- [ ] No PostgreSQL regressions (if dual DB support needed)

---

## Post-Implementation Validation

### 1. Database Inspection
```bash
# Connect to SQLite database
sqlite3 backend/supoclip.db

# Check a task record
SELECT id, created_at, updated_at FROM tasks LIMIT 1;

# Check a clip record
SELECT id, created_at, updated_at FROM generated_clips LIMIT 1;

# Verify trigger exists
.schema tasks
```

### 2. Log Analysis
```bash
# Check for any NOW() errors
grep -i "no such function" logs/application.log

# Verify successful task creation
grep "Created task" logs/application.log | tail -5

# Check for timestamp-related errors
grep -i "timestamp\|datetime" logs/application.log | grep -i error
```

### 3. Code Verification
```bash
# Verify no NOW() remains in repository code
grep -r "NOW()" backend/src/repositories/

# Should return empty
```

---

## Notes

1. **Schema Defaults Are Sufficient**: The SQLite schema already has proper defaults and triggers. The application code was redundantly setting timestamps.

2. **Trigger Behavior**: SQLite triggers update timestamps AFTER the row is modified, which is the correct behavior.

3. **PostgreSQL Compatibility**: If future PostgreSQL support is needed, the PostgreSQL schema should also use `DEFAULT CURRENT_TIMESTAMP` and triggers instead of application-level `NOW()`.

4. **Best Practice**: Database schemas should handle timestamp management, not application code. This provides:
   - Consistency across different code paths
   - Single source of truth for timestamp logic
   - Database-agnostic application code

5. **SQLAlchemy Migration Path**: When migrating to SQLAlchemy ORM (per CLAUDE.md), the `server_default=func.now()` and `onupdate=func.now()` in models.py (lines 49-50, 96) already implement this pattern correctly.

---

## References

- **Error Report**: User message (2025-11-15 15:55:11)
- **SQLite Schema**: `backend/migrations/init_sqlite.sql`
- **SQLAlchemy Models**: `backend/src/models.py`
- **Task Repository**: `backend/src/repositories/task_repository.py`
- **Clip Repository**: `backend/src/repositories/clip_repository.py`
- **Main Application**: `backend/src/main.py`
