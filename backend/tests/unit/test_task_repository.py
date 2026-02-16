# start backend/tests/unit/test_task_repository.py
"""
Unit tests for TaskRepository — covers parse_sqlite_datetime, create_task,
get_task_by_id, update_task_status, update_task_clips, get_user_tasks,
user_exists, and delete_task.

Goal: 100% line coverage for src/repositories/task_repository.py.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestParseSqliteDatetimeTask:
    """Test parse_sqlite_datetime() in task_repository."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        from src.repositories.task_repository import parse_sqlite_datetime

        assert parse_sqlite_datetime(None) is None

    def test_datetime_passthrough(self):
        """Test that datetime objects are returned as-is (covers line 31)."""
        from src.repositories.task_repository import parse_sqlite_datetime

        dt = datetime(2024, 6, 15, 12, 0, 0)
        result = parse_sqlite_datetime(dt)
        assert result is dt

    def test_valid_string_parsed(self):
        """Test that valid ISO format strings are parsed to datetime."""
        from src.repositories.task_repository import parse_sqlite_datetime

        result = parse_sqlite_datetime("2024-06-15T12:00:00")
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_invalid_string_returns_none(self):
        """Test that invalid datetime strings return None (covers lines 34-36)."""
        from src.repositories.task_repository import parse_sqlite_datetime

        result = parse_sqlite_datetime("not-a-date")
        assert result is None

    def test_empty_string_returns_none(self):
        """Test that empty string returns None via ValueError."""
        from src.repositories.task_repository import parse_sqlite_datetime

        result = parse_sqlite_datetime("")
        assert result is None


class TestTaskRepositoryCreateTask:
    """Test TaskRepository.create_task()."""

    async def test_create_task_returns_uuid(self):
        """Test that create_task executes INSERT, commits, and returns a UUID."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("src.repositories.task_repository.uuid.uuid4", return_value="task-uuid-abc"):
            result = await TaskRepository.create_task(
                db=mock_db,
                user_id="user-1",
                source_id="source-1",
            )

        assert result == "task-uuid-abc"
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    async def test_create_task_with_custom_params(self):
        """Test create_task with custom status and font settings."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("src.repositories.task_repository.uuid.uuid4", return_value="task-uuid-def"):
            result = await TaskRepository.create_task(
                db=mock_db,
                user_id="user-2",
                source_id="source-2",
                status="queued",
                font_family="Arial",
                font_size=32,
                font_color="#000000",
            )

        assert result == "task-uuid-def"

        # Check the params passed to execute
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["user_id"] == "user-2"
        assert params["source_id"] == "source-2"
        assert params["status"] == "queued"
        assert params["font_family"] == "Arial"
        assert params["font_size"] == 32
        assert params["font_color"] == "#000000"


class TestTaskRepositoryGetTaskById:
    """Test TaskRepository.get_task_by_id()."""

    async def test_get_task_by_id_found(self):
        """Test get_task_by_id returns dict when task exists."""
        from src.repositories.task_repository import TaskRepository

        mock_row = MagicMock()
        mock_row.id = "task-1"
        mock_row.user_id = "user-1"
        mock_row.source_id = "source-1"
        mock_row.source_title = "Test Video"
        mock_row.source_type = "youtube"
        mock_row.status = "completed"
        mock_row.progress = 100
        mock_row.progress_message = "Done"
        mock_row.generated_clips_ids = '["clip-1", "clip-2"]'
        mock_row.font_family = "TikTokSans-Regular"
        mock_row.font_size = 24
        mock_row.font_color = "#FFFFFF"
        mock_row.created_at = "2024-01-15T10:00:00"
        mock_row.updated_at = "2024-01-15T11:00:00"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await TaskRepository.get_task_by_id(mock_db, "task-1")

        assert result is not None
        assert result["id"] == "task-1"
        assert result["user_id"] == "user-1"
        assert result["source_title"] == "Test Video"
        assert result["status"] == "completed"
        assert result["font_family"] == "TikTokSans-Regular"
        assert isinstance(result["created_at"], datetime)
        assert isinstance(result["updated_at"], datetime)

    async def test_get_task_by_id_not_found(self):
        """Test get_task_by_id returns None when task does not exist (covers line 91)."""
        from src.repositories.task_repository import TaskRepository

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await TaskRepository.get_task_by_id(mock_db, "nonexistent")

        assert result is None

    async def test_get_task_by_id_missing_progress_attrs(self):
        """Test get_task_by_id handles missing progress/progress_message via getattr."""
        from src.repositories.task_repository import TaskRepository

        mock_row = MagicMock(spec=[
            "id", "user_id", "source_id", "source_title", "source_type",
            "status", "generated_clips_ids", "font_family", "font_size",
            "font_color", "created_at", "updated_at",
        ])
        mock_row.id = "task-2"
        mock_row.user_id = "user-2"
        mock_row.source_id = "source-2"
        mock_row.source_title = "Another Video"
        mock_row.source_type = "upload"
        mock_row.status = "processing"
        mock_row.generated_clips_ids = None
        mock_row.font_family = "Arial"
        mock_row.font_size = 20
        mock_row.font_color = "#000000"
        mock_row.created_at = datetime(2024, 6, 1, 12, 0, 0)
        mock_row.updated_at = datetime(2024, 6, 1, 13, 0, 0)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await TaskRepository.get_task_by_id(mock_db, "task-2")

        assert result is not None
        assert result["progress"] is None
        assert result["progress_message"] is None


class TestTaskRepositoryUpdateTaskStatus:
    """Test TaskRepository.update_task_status()."""

    async def test_update_status_only(self):
        """Test update_task_status with status only (no progress or message)."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_status(
            mock_db, "task-1", "completed"
        )

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    async def test_update_status_with_progress(self):
        """Test update_task_status with progress percentage."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_status(
            mock_db, "task-1", "processing", progress=50
        )

        mock_db.execute.assert_awaited_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["progress"] == 50

    async def test_update_status_with_progress_message(self):
        """Test update_task_status with progress_message."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_status(
            mock_db, "task-1", "error", progress_message="Something went wrong"
        )

        mock_db.execute.assert_awaited_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["progress_message"] == "Something went wrong"

    async def test_update_status_with_all_params(self):
        """Test update_task_status with all parameters provided."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_status(
            mock_db,
            "task-1",
            "processing",
            progress=75,
            progress_message="Almost done",
        )

        mock_db.execute.assert_awaited_once()


class TestTaskRepositoryUpdateTaskClips:
    """Test TaskRepository.update_task_clips()."""

    async def test_update_task_clips(self):
        """Test that update_task_clips serializes clip IDs and updates the task (covers lines 150-161)."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_clips(
            mock_db, "task-1", ["clip-1", "clip-2", "clip-3"]
        )

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify the clip_ids were serialized to JSON
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["task_id"] == "task-1"
        assert params["clip_ids"] == '["clip-1", "clip-2", "clip-3"]'

    async def test_update_task_clips_empty_list(self):
        """Test update_task_clips with empty clip list."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.update_task_clips(mock_db, "task-2", [])

        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["clip_ids"] == "[]"


class TestTaskRepositoryGetUserTasks:
    """Test TaskRepository.get_user_tasks()."""

    async def test_get_user_tasks_returns_list(self):
        """Test that get_user_tasks returns list of task dicts (covers lines 168-198)."""
        from src.repositories.task_repository import TaskRepository

        mock_row = MagicMock()
        mock_row.id = "task-1"
        mock_row.user_id = "user-1"
        mock_row.source_id = "source-1"
        mock_row.source_title = "Test Video"
        mock_row.source_type = "youtube"
        mock_row.status = "completed"
        mock_row.clips_count = 3
        mock_row.created_at = "2024-01-15T10:00:00"
        mock_row.updated_at = "2024-01-15T11:00:00"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        tasks = await TaskRepository.get_user_tasks(mock_db, "user-1")

        assert len(tasks) == 1
        assert tasks[0]["id"] == "task-1"
        assert tasks[0]["user_id"] == "user-1"
        assert tasks[0]["source_title"] == "Test Video"
        assert tasks[0]["clips_count"] == 3
        assert isinstance(tasks[0]["created_at"], datetime)

    async def test_get_user_tasks_empty(self):
        """Test get_user_tasks returns empty list when no tasks found."""
        from src.repositories.task_repository import TaskRepository

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        tasks = await TaskRepository.get_user_tasks(mock_db, "user-no-tasks")

        assert tasks == []

    async def test_get_user_tasks_with_custom_limit(self):
        """Test get_user_tasks respects the limit parameter."""
        from src.repositories.task_repository import TaskRepository

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        await TaskRepository.get_user_tasks(mock_db, "user-1", limit=10)

        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 10

    async def test_get_user_tasks_multiple_rows(self):
        """Test get_user_tasks with multiple task rows."""
        from src.repositories.task_repository import TaskRepository

        rows = []
        for i in range(3):
            mock_row = MagicMock()
            mock_row.id = f"task-{i}"
            mock_row.user_id = "user-1"
            mock_row.source_id = f"source-{i}"
            mock_row.source_title = f"Video {i}"
            mock_row.source_type = "youtube"
            mock_row.status = "completed"
            mock_row.clips_count = i + 1
            mock_row.created_at = None
            mock_row.updated_at = None
            rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        tasks = await TaskRepository.get_user_tasks(mock_db, "user-1")

        assert len(tasks) == 3
        assert tasks[0]["id"] == "task-0"
        assert tasks[2]["clips_count"] == 3


class TestTaskRepositoryUserExists:
    """Test TaskRepository.user_exists()."""

    async def test_user_exists_true(self):
        """Test user_exists returns True when user found (covers lines 203-206)."""
        from src.repositories.task_repository import TaskRepository

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await TaskRepository.user_exists(mock_db, "user-1")

        assert result is True

    async def test_user_exists_false(self):
        """Test user_exists returns False when user not found."""
        from src.repositories.task_repository import TaskRepository

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await TaskRepository.user_exists(mock_db, "nonexistent")

        assert result is False


class TestTaskRepositoryDeleteTask:
    """Test TaskRepository.delete_task()."""

    async def test_delete_task(self):
        """Test that delete_task executes DELETE and commits (covers lines 211-215)."""
        from src.repositories.task_repository import TaskRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await TaskRepository.delete_task(mock_db, "task-to-delete")

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify the task_id is in params
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["task_id"] == "task-to-delete"


# end backend/tests/unit/test_task_repository.py
