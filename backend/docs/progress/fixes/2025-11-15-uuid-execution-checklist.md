# UUID Fix Execution Checklist
Date: 2025-11-15

Use this checklist to track your progress implementing the UUID auto-generation fixes.

---

## Phase 0: Pre-Flight Checks

- [ ] Read CLAUDE.md
- [ ] Read detailed repair plan: `2025-11-15-sqlite-uuid-repair-plan.md`
- [ ] Read quick summary: `2025-11-15-uuid-fix-summary.md`
- [ ] Understand the root cause (SQLite DEFAULT doesn't work with text())
- [ ] Understand why source_repository.py works (uses ORM)
- [ ] Understand why task/clip repositories fail (use raw SQL)

---

## Phase 1: Git Checkpoint (Before Fixes)

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
git status
git add -A
git commit -m "CHECKPOINT: [2025-11-15] Before UUID auto-generation fixes for SQLite raw SQL"
```

- [ ] Git checkpoint created
- [ ] Commit hash recorded: ___________________________

---

## Phase 2: VUW-UUID-001 - Fix task_repository.py

### File: src/repositories/task_repository.py

- [ ] Open file in editor
- [ ] Line 9: Add `import uuid` after `import logging`
- [ ] Line 27: Add `task_id = str(uuid.uuid4())` before db.execute()
- [ ] Line 30: Change `INSERT INTO tasks (user_id, source_id, status, ...)`
      to `INSERT INTO tasks (id, user_id, source_id, status, ...)`
- [ ] Line 31: Change `VALUES (:user_id, :source_id, :status, ...)`
      to `VALUES (:id, :user_id, :source_id, :status, ...)`
- [ ] Line 33: Add `"id": task_id,` to parameters dict (first item)
- [ ] Save file

### Verification

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
./checkpython.sh
```

- [ ] checkpython.sh reports zero errors
- [ ] All tests passing (100%)

### Testing

```bash
# Start server
cd /Users/cspenn/Documents/github/supoclip/backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, test task creation
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    "font_options": {
      "font_family": "TikTokSans-Regular",
      "font_size": 24,
      "font_color": "#FFFFFF"
    }
  }'

# Verify task in database
sqlite3 supoclip.db "SELECT id, user_id, status FROM tasks ORDER BY created_at DESC LIMIT 1;"
```

- [ ] Task creation succeeded (no NOT NULL constraint error)
- [ ] Task has valid UUID in id column
- [ ] API response includes task_id

### Git Commit

```bash
git add src/repositories/task_repository.py
git commit -m "VUW-UUID-001: Fix task_repository.py UUID auto-generation for SQLite

- Add explicit UUID generation before INSERT
- Include id column in INSERT statement
- Fixes: NOT NULL constraint failed: tasks.id
- Status: Tested and verified"
```

- [ ] Git commit created
- [ ] Commit hash: ___________________________

---

## Phase 3: VUW-UUID-002 - Fix clip_repository.py

### File: src/repositories/clip_repository.py

- [ ] Open file in editor
- [ ] Line 8: Add `import uuid` after `import logging`
- [ ] Line 30: Add `clip_id = str(uuid.uuid4())` before db.execute()
- [ ] Line 34: Change `INSERT INTO generated_clips (task_id, filename, ...)`
      to `INSERT INTO generated_clips (id, task_id, filename, ...)`
- [ ] Line 36: Change `VALUES (:task_id, :filename, ...)`
      to `VALUES (:id, :task_id, :filename, ...)`
- [ ] Line 40: Add `"id": clip_id,` to parameters dict (first item)
- [ ] Save file

### Verification

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
./checkpython.sh
```

- [ ] checkpython.sh reports zero errors
- [ ] All tests passing (100%)

### Testing

```bash
# Full video processing pipeline (creates clips)
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    "font_options": {
      "font_family": "TikTokSans-Regular",
      "font_size": 24,
      "font_color": "#FFFFFF"
    }
  }'

# Wait for processing to complete, then verify clips in database
sqlite3 supoclip.db "SELECT id, task_id, filename FROM generated_clips ORDER BY created_at DESC LIMIT 3;"
```

- [ ] Clip creation succeeded (no NOT NULL constraint error)
- [ ] Clips have valid UUIDs in id column
- [ ] Clips properly linked to task via task_id

### Git Commit

```bash
git add src/repositories/clip_repository.py
git commit -m "VUW-UUID-002: Fix clip_repository.py UUID auto-generation for SQLite

- Add explicit UUID generation before INSERT
- Include id column in INSERT statement
- Ensures clips are created with valid UUIDs
- Status: Tested and verified"
```

- [ ] Git commit created
- [ ] Commit hash: ___________________________

---

## Phase 4: VUW-UUID-003 - Verify source_repository.py

### File: src/repositories/source_repository.py

- [ ] Review create_source() method (lines 14-36)
- [ ] Confirm it uses SQLAlchemy ORM: `source = Source()`
- [ ] Confirm it uses model: `from ..models import Source`
- [ ] Confirm no raw SQL in create_source()
- [ ] Verify models.py has: `default=generate_uuid_string` for Source.id

### Testing

```bash
# Source creation is part of video processing
# Verify existing sources have UUIDs
sqlite3 supoclip.db "SELECT id, type, title FROM sources ORDER BY created_at DESC LIMIT 3;"
```

- [ ] Sources have valid UUIDs in id column
- [ ] No changes needed to source_repository.py
- [ ] Document why ORM approach works (Python-side default applies)

### Documentation

- [ ] Add note to CLAUDE.md about ORM vs raw SQL UUID generation
- [ ] Document recommended pattern: use ORM when possible

---

## Phase 5: Integration Testing

### Full Pipeline Test

```bash
# Process a real video end-to-end
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    "font_options": {
      "font_family": "TikTokSans-Regular",
      "font_size": 24,
      "font_color": "#FFFFFF"
    }
  }'

# Monitor logs for errors
tail -f logs/*.log

# Wait for completion
# Check task status via API
curl http://localhost:8000/tasks/{task_id}
```

- [ ] Video processing completes successfully
- [ ] No database errors in logs
- [ ] No NOT NULL constraint errors
- [ ] Task status = "completed"

### Database Validation

```bash
# Verify all tables have valid UUIDs
sqlite3 supoclip.db "SELECT COUNT(*) as total, COUNT(id) as with_id FROM tasks;"
sqlite3 supoclip.db "SELECT COUNT(*) as total, COUNT(id) as with_id FROM generated_clips;"
sqlite3 supoclip.db "SELECT COUNT(*) as total, COUNT(id) as with_id FROM sources;"

# Check for NULL ids (should be 0)
sqlite3 supoclip.db "SELECT COUNT(*) FROM tasks WHERE id IS NULL;"
sqlite3 supoclip.db "SELECT COUNT(*) FROM generated_clips WHERE id IS NULL;"
sqlite3 supoclip.db "SELECT COUNT(*) FROM sources WHERE id IS NULL;"
```

- [ ] All tasks have valid UUIDs (no NULLs)
- [ ] All clips have valid UUIDs (no NULLs)
- [ ] All sources have valid UUIDs (no NULLs)
- [ ] Foreign key relationships intact (clips.task_id references tasks.id)

### Performance Check

```bash
# Process 3 videos to ensure consistent behavior
# Video 1
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"source": {"url": "VIDEO_URL_1"}}'

# Video 2
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"source": {"url": "VIDEO_URL_2"}}'

# Video 3
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"source": {"url": "VIDEO_URL_3"}}'
```

- [ ] All 3 videos processed successfully
- [ ] No performance degradation
- [ ] No memory leaks
- [ ] All records have valid UUIDs

---

## Phase 6: Final Validation

### Code Quality

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
./checkpython.sh
```

- [ ] Ruff: zero errors
- [ ] mypy: zero errors
- [ ] Bandit: zero security issues
- [ ] pytest: 100% passing

### Documentation

- [ ] CLAUDE.md updated with UUID generation pattern
- [ ] Repair plan documented (2025-11-15-sqlite-uuid-repair-plan.md)
- [ ] Quick summary created (2025-11-15-uuid-fix-summary.md)
- [ ] Execution checklist completed (this file)

### Git History

```bash
git log --oneline -5
```

- [ ] Checkpoint commit before fixes visible
- [ ] VUW-UUID-001 commit visible
- [ ] VUW-UUID-002 commit visible
- [ ] All commits have clear messages

---

## Phase 7: Git Checkpoint (After Fixes)

```bash
cd /Users/cspenn/Documents/github/supoclip/backend
git status
git add -A
git commit -m "CHECKPOINT: [2025-11-15] Fixed UUID auto-generation for SQLite - all tests passing

- VUW-UUID-001: Fixed task_repository.py
- VUW-UUID-002: Fixed clip_repository.py
- VUW-UUID-003: Verified source_repository.py (no changes needed)
- All INSERT statements now generate UUIDs explicitly
- All tests passing, zero errors in checkpython.sh
- Full video processing pipeline validated"
```

- [ ] Final checkpoint created
- [ ] Commit hash: ___________________________

---

## Phase 8: Cleanup and Future Improvements

### Immediate Cleanup

- [ ] Remove old database if exists: `rm supoclip.db`
- [ ] Recreate with schema: `sqlite3 supoclip.db < migrations/init_sqlite.sql`
- [ ] Test with fresh database
- [ ] Verify all tables created correctly

### Future Improvements (Document Only - Don't Implement)

Ideas to document for future work:

- [ ] Consider migrating all repositories to SQLAlchemy ORM (consistency)
- [ ] Add helper function for UUID generation to reduce duplication
- [ ] Add pre-commit hook to detect raw SQL INSERT without explicit id
- [ ] Add integration tests for all repository create methods
- [ ] Consider using Alembic for schema migrations

---

## Rollback Procedure (If Needed)

### If VUW-UUID-001 fails:
```bash
git reset --hard <checkpoint-before-fixes>
```

### If VUW-UUID-002 fails:
```bash
git reset --hard <commit-after-VUW-UUID-001>
```

### If entire fix fails:
```bash
git reset --hard <checkpoint-before-fixes>
rm supoclip.db
sqlite3 supoclip.db < migrations/init_sqlite.sql
```

- [ ] Rollback procedure tested (if needed)
- [ ] Documented issues encountered
- [ ] Escalated blocking issues

---

## Success Criteria

All checkboxes must be checked for complete success:

- [ ] VUW-UUID-001 completed and verified
- [ ] VUW-UUID-002 completed and verified
- [ ] VUW-UUID-003 verified (no changes)
- [ ] Integration testing passed
- [ ] All database records have valid UUIDs
- [ ] No NOT NULL constraint errors
- [ ] checkpython.sh reports zero errors
- [ ] All tests passing (100%)
- [ ] Documentation complete
- [ ] Git commits clean and descriptive
- [ ] Final checkpoint created

---

## Sign-Off

- [ ] All VUWs completed successfully
- [ ] All verification checklists passed
- [ ] Self-attestation: checkpython.sh passed and tests succeeded
- [ ] Ready for production use

**Completed by:** ____________________

**Date:** ____________________

**Notes:**
_______________________________________________________________________
_______________________________________________________________________
_______________________________________________________________________
