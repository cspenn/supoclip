# SQLite Datetime Serialization Fix

**Date:** 2025-11-15
**Status:** ✅ Complete
**VUWs:** VUW-DATETIME-001 through VUW-DATETIME-006

## Problem

The application was failing with 500 errors when fetching tasks from the API. The root cause was a datetime serialization issue with SQLite.

### Error Message
```
AttributeError: 'str' object has no attribute 'isoformat'
```

### Root Cause Analysis

SQLite stores DATETIME columns as TEXT in ISO 8601 format (e.g., "2025-11-15 19:14:38.533614"). When using raw SQL via SQLAlchemy's `text()` wrapper, these values are returned as strings instead of Python datetime objects. FastAPI's JSON serialization expects datetime objects with an `.isoformat()` method, which strings don't have.

**Data Flow:**
1. SQLite stores: `"2025-11-15 19:14:38.533614"` (TEXT)
2. SQLAlchemy raw SQL returns: `str` object
3. Repository returns: `{"created_at": "2025-11-15 19:14:38.533614"}` (str)
4. FastAPI JSON encoder tries: `str.isoformat()` → **AttributeError**

## Solution

Added a datetime parsing utility function and applied it to all datetime fields in repository methods.

### Implementation

#### 1. Utility Function (VUW-DATETIME-001)

Created `parse_sqlite_datetime()` function in both repository files:

```python
def parse_sqlite_datetime(dt_value: str | datetime | None) -> datetime | None:
    """
    Convert SQLite TEXT datetime to Python datetime object.

    SQLite stores DATETIME as TEXT in ISO 8601 format. When using raw SQL
    via SQLAlchemy's text() wrapper, these values are returned as strings
    instead of datetime objects. This function handles the conversion.

    Args:
        dt_value: Either a datetime string, datetime object, or None

    Returns:
        datetime object or None
    """
    if dt_value is None or isinstance(dt_value, datetime):
        return dt_value
    return datetime.fromisoformat(dt_value)
```

#### 2. Fixed Files

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/repositories/task_repository.py`

**Changes:**
- VUW-DATETIME-002: Fixed `get_task_by_id()` - lines 98-99
- VUW-DATETIME-003: Fixed `get_user_tasks()` - lines 174-175

**Before:**
```python
return {
    # ...
    "created_at": row.created_at,  # Returns str from SQLite
    "updated_at": row.updated_at   # Returns str from SQLite
}
```

**After:**
```python
return {
    # ...
    "created_at": parse_sqlite_datetime(row.created_at),  # Returns datetime object
    "updated_at": parse_sqlite_datetime(row.updated_at)   # Returns datetime object
}
```

**File:** `/Users/cspenn/Documents/github/supoclip/backend/src/repositories/clip_repository.py`

**Changes:**
- VUW-DATETIME-004: Fixed `get_clips_by_task()` - line 106

**Before:**
```python
"created_at": row.created_at.isoformat(),  # Fails - str has no isoformat()
```

**After:**
```python
"created_at": parse_sqlite_datetime(row.created_at),  # Returns datetime object
```

## Verification (VUW-DATETIME-005)

### API Response Test
```bash
curl -X GET "http://localhost:8008/tasks/ec440373-2f7e-4341-903a-9f0b68552907" -H "x-user-id: local-user"
```

**Result:** ✅ Success
```json
{
  "id": "ec440373-2f7e-4341-903a-9f0b68552907",
  "created_at": "2025-11-15T18:36:08.212543",
  "updated_at": "2025-11-15T18:36:08.212544",
  ...
}
```

### Unit Test
```python
# Test datetime parsing utility
dt_str = '2025-11-15 19:14:38.533614'
result = parse_sqlite_datetime(dt_str)
assert isinstance(result, datetime)  # ✅ Pass
assert result.isoformat() == '2025-11-15T19:14:38.533614'  # ✅ Pass
```

### Log Analysis
**Before fix:**
```
2025-11-15 19:15:07 - ERROR - 🛑 Error retrieving task: 'str' object has no attribute 'isoformat'
```

**After fix:**
```
# No errors - API endpoints return successfully
```

## Test Results (VUW-DATETIME-006)

**Pytest Results:**
- Total tests: 222
- Passed: 204
- Failed: 17 (all unrelated to datetime fix)
- Skipped: 1

**Note:** All failures are pre-existing and related to:
- Schema validation for progress columns (removed in migration)
- Redis health checks (Redis removed in migration)
- MLX whisper model configuration (different feature)
- Local LLM configuration (different feature)

**No datetime-related test failures.**

## Impact

**Fixed Endpoints:**
- `GET /tasks/{task_id}` - Now returns tasks with properly serialized datetime fields
- `GET /tasks/{task_id}/clips` - Now returns clips with properly serialized datetime fields
- Any other endpoint using `TaskRepository` or `ClipRepository`

**Expected Behavior:**
- All datetime fields now returned as ISO 8601 strings: `"2025-11-15T18:36:08.212543"`
- FastAPI JSON encoder can properly serialize datetime objects
- No more 500 errors from datetime serialization

## Git Commits

**Checkpoint Before:**
```
beacc4e - CHECKPOINT: Before fixing SQLite datetime serialization issue
```

**Fix Commit:**
```
e6237e9 - Fix SQLite datetime serialization in repository methods
```

## Lessons Learned

1. **SQLite Type Handling:** SQLite's TEXT-based datetime storage requires explicit conversion when using raw SQL
2. **SQLAlchemy Raw SQL:** `text()` wrapper doesn't provide automatic type conversion like ORM does
3. **FastAPI JSON Serialization:** Expects datetime objects, not strings, for proper ISO 8601 formatting
4. **VUW Methodology:** Breaking the fix into 6 small VUWs made verification straightforward and safe

## Future Considerations

When migrating to SQLAlchemy ORM (as planned), this conversion will be automatic and these utility functions can be removed. The ORM will handle the TEXT→datetime conversion for us.
