# Root Cause Analysis: Database Schema Mismatch
Date: 2025-11-15

## Issues Under Investigation
1. Video processing fails immediately on first status update
2. Database connection pool exhaustion after multiple failed attempts
3. Application becomes unresponsive after ~15 failed processing attempts

## Log Evidence

### Primary Failure:
```
sqlite3.OperationalError: no such column: progress
[SQL: UPDATE tasks SET status = ?, progress = ?, progress_message = ? WHERE id = ?]
[parameters: ('processing', 0, 'Starting...', '1f28b6bc-d25c-40de-a42e-ba04afecdd2d')]
```

### Cascading Failure:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: progress_message
[parameters: ('error', "(sqlite3.OperationalError) no such column: progress...", '1f28b6bc-...')]
```
The error handler itself fails because it also tries to write progress_message!

### Connection Pool Exhaustion:
```
QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00
```

### Connection Leaks (200+ instances):
```
The garbage collector is trying to clean up non-checked-in connection
<AdaptedConnection <Connection(Thread-98, started daemon 15506649088)>>
```

## All Hypotheses

1. **Database schema is missing `progress` and `progress_message` columns that code expects**
2. Alembic migrations were not run after model changes
3. Database was created with old schema before columns were added to model
4. SQLAlchemy model was never updated to include progress columns
5. Code was written expecting Redis-based progress tracking, now uses database without schema update
6. Manual schema edits were made but not synchronized with SQLAlchemy model
7. Previous migration from PostgreSQL to SQLite lost these columns

## Top 2 Hypotheses - Detailed Analysis

### Most Likely Root Cause
**Hypothesis:** Database schema is missing `progress` and `progress_message` columns that application code expects to exist.

**Why this is #1:**
- Direct evidence from error message: "no such column: progress"
- Database schema inspection confirms columns do not exist
- SQLAlchemy Task model does NOT define these columns
- Repository code attempts to UPDATE these non-existent columns
- Service layer calls repository with progress parameters
- Multiple code layers all expect these columns to exist
- No migration system in place to detect/fix schema drift

**Supporting Evidence:**
1. **Database Schema** (via `sqlite3 .schema tasks`):
   - Lists 10 columns: id, user_id, source_id, generated_clips_ids, status, font_family, font_size, font_color, created_at, updated_at
   - Does NOT include: progress, progress_message

2. **SQLAlchemy Model** (models.py lines 34-55):
   ```python
   class Task(Base):
       __tablename__ = "tasks"
       id: Mapped[str]
       user_id: Mapped[str]
       source_id: Mapped[Optional[str]]
       generated_clips_ids: Mapped[Optional[List[str]]]
       status: Mapped[str]
       font_family: Mapped[Optional[str]]
       font_size: Mapped[Optional[int]]
       font_color: Mapped[Optional[str]]
       created_at: Mapped[datetime]
       updated_at: Mapped[datetime]
       # NO progress or progress_message fields!
   ```

3. **Repository Code** (task_repository.py lines 84-114):
   ```python
   async def update_task_status(
       db: AsyncSession,
       task_id: str,
       status: str,
       progress: Optional[int] = None,        # ← Parameter exists
       progress_message: Optional[str] = None # ← Parameter exists
   ):
       # ...
       if progress is not None:
           set_parts.append("progress = :progress")  # ← Tries to UPDATE
       if progress_message is not None:
           set_parts.append("progress_message = :progress_message")  # ← Tries to UPDATE
   ```

4. **Service Layer Calls** (task_service.py multiple lines):
   - Line 94: `update_task_status(db, task_id, "processing", progress=0, progress_message="Starting...")`
   - Line 100: `update_task_status(db, task_id, "processing", progress=progress, progress_message=message)`
   - Line 117: `update_task_status(db, task_id, "processing", progress=95, progress_message="Saving clips...")`
   - Line 142: `update_task_status(db, task_id, "completed", progress=100, progress_message="Complete!")`
   - Line 158: `update_task_status(db, task_id, "error", progress_message=str(e))`

5. **Error Log Sequence**:
   - First error: "no such column: progress" during normal status update
   - Second error: "no such column: progress_message" during error handling
   - This proves the error handler itself fails, creating unclosed transactions

**Contradicting Evidence:**
- None found. All evidence supports this hypothesis.

**Confidence Level:** High (95-100%)

This is unambiguously the root cause. The code expects columns that don't exist.

### Second Most Likely Root Cause
**Hypothesis:** Failed database transactions from schema errors don't properly release connections, causing pool exhaustion.

**Why this is #2:**
- This is actually a **cascading failure** from hypothesis #1
- Not an independent root cause, but a secondary effect
- Connection pool exhaustion only happens AFTER repeated schema errors
- Error handlers may not properly clean up sessions on exception

**Supporting Evidence:**
1. **Connection Pool Warnings** (200+ instances in logs):
   ```
   The garbage collector is trying to clean up non-checked-in connection
   ```
   This indicates sessions/connections were not properly closed.

2. **Pool Exhaustion After Repeated Failures**:
   ```
   QueuePool limit of size 5 overflow 10 reached, connection timed out
   ```
   Default pool size is 5, overflow allows 10 more, totaling 15 connections max.

3. **Error Handler Code** (task_service.py lines 155-160):
   ```python
   except Exception as e:
       logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
       await self.task_repo.update_task_status(
           self.db, task_id, "error", progress_message=str(e)
       )
       raise
   ```
   The error handler ALSO tries to update progress_message, which will fail!
   This creates a nested exception that may prevent proper session cleanup.

4. **Database Context Manager Pattern** (workers/tasks.py lines 48-75):
   ```python
   async with AsyncSessionLocal() as db:
       task_service = TaskService(db)
       try:
           # ... processing ...
       except Exception as e:
           # Error handling that also fails
           raise
   ```
   The `async with` should handle cleanup, but nested exceptions may interfere.

**Contradicting Evidence:**
- SQLAlchemy's `async with` context manager SHOULD handle cleanup even on exceptions
- However, if the exception happens during commit/cleanup itself, connections may leak
- Need to verify SQLAlchemy's exception handling in this scenario

**Confidence Level:** Medium-High (70-85%)

This is definitely happening, but it's a symptom rather than root cause. Fixing hypothesis #1 should prevent this from occurring.

## Testing Strategy

### Hypothesis #1 Validation:
1. Create a test that attempts to update task status with progress
2. Test should fail with "no such column: progress" error
3. Add columns to schema
4. Test should pass

### Hypothesis #2 Validation:
1. Monitor connection pool before and after failed transactions
2. Verify connections are properly cleaned up after schema fix
3. Test that error handlers don't create secondary failures

## Migration Context

From CLAUDE.md and previous fixes, this project is migrating from:
- PostgreSQL → SQLite
- Docker + Redis → Standalone offline mode
- arq queue → Local asyncio queue

**Analysis:** The progress tracking was likely originally designed for Redis-based real-time updates (via SSE). During the migration:
1. Redis removal left progress tracking needing a new home
2. Code was updated to use database for progress tracking
3. **But database schema was never migrated to add the columns**
4. **And SQLAlchemy model was never updated**

This explains why the code structure exists but the schema doesn't support it.

## Recommended Fix Order

1. **Add columns to SQLite database** (immediate fix for schema)
2. **Update SQLAlchemy Task model** (align code with schema)
3. **Verify error handlers don't cascade failures** (prevent secondary issues)
4. **Add startup schema validation** (prevent future drift)
5. **Consider Alembic** (proper migration workflow for future)
