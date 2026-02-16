# start backend/tests/unit/test_clip_repository.py
"""
Unit tests for ClipRepository — covers parse_sqlite_datetime, create_clip,
get_clips_by_task, get_clips_count, delete_clips_by_task, and delete_clip.

Goal: 100% line coverage for src/repositories/clip_repository.py.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestParseSqliteDatetimeClip:
    """Test parse_sqlite_datetime() in clip_repository."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        from src.repositories.clip_repository import parse_sqlite_datetime

        assert parse_sqlite_datetime(None) is None

    def test_datetime_passthrough(self):
        """Test that datetime objects are returned as-is (covers line 31 isinstance branch)."""
        from src.repositories.clip_repository import parse_sqlite_datetime

        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = parse_sqlite_datetime(dt)
        assert result is dt

    def test_string_parsed(self):
        """Test that ISO format strings are parsed to datetime."""
        from src.repositories.clip_repository import parse_sqlite_datetime

        result = parse_sqlite_datetime("2024-01-15T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15


class TestClipRepositoryCreateClip:
    """Test ClipRepository.create_clip()."""

    async def test_create_clip_returns_uuid(self):
        """Test that create_clip executes INSERT and returns a UUID."""
        from src.repositories.clip_repository import ClipRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        with patch("src.repositories.clip_repository.uuid.uuid4", return_value="clip-uuid-123"):
            result = await ClipRepository.create_clip(
                db=mock_db,
                task_id="task-1",
                filename="clip_01.mp4",
                file_path="/tmp/clips/clip_01.mp4",
                start_time="00:10",
                end_time="00:30",
                duration=20.0,
                clip_text="Test transcript text",
                relevance_score=0.95,
                reasoning="High engagement",
                clip_order=1,
            )

        assert result == "clip-uuid-123"
        mock_db.execute.assert_awaited_once()


class TestClipRepositoryGetClipsByTask:
    """Test ClipRepository.get_clips_by_task()."""

    async def test_get_clips_by_task_returns_list(self):
        """Test that get_clips_by_task returns list of clip dicts with video URLs."""
        from src.repositories.clip_repository import ClipRepository

        mock_row = MagicMock()
        mock_row.id = "clip-1"
        mock_row.filename = "clip_01.mp4"
        mock_row.file_path = "/tmp/clips/clip_01.mp4"
        mock_row.start_time = "00:10"
        mock_row.end_time = "00:30"
        mock_row.duration = 20.0
        mock_row.text = "Test transcript"
        mock_row.relevance_score = 0.95
        mock_row.reasoning = "Engaging moment"
        mock_row.clip_order = 1
        mock_row.created_at = "2024-01-15T10:00:00"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        clips = await ClipRepository.get_clips_by_task(
            mock_db, "task-1", backend_url="http://localhost:9000"
        )

        assert len(clips) == 1
        assert clips[0]["id"] == "clip-1"
        assert clips[0]["filename"] == "clip_01.mp4"
        assert clips[0]["video_url"] == "http://localhost:9000/clips/clip_01.mp4"
        assert isinstance(clips[0]["created_at"], datetime)

    async def test_get_clips_by_task_empty_result(self):
        """Test that get_clips_by_task returns empty list when no clips found."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        clips = await ClipRepository.get_clips_by_task(mock_db, "nonexistent-task")

        assert clips == []

    async def test_get_clips_by_task_default_backend_url(self):
        """Test get_clips_by_task uses default backend_url."""
        from src.repositories.clip_repository import ClipRepository

        mock_row = MagicMock()
        mock_row.id = "clip-2"
        mock_row.filename = "clip_02.mp4"
        mock_row.file_path = "/tmp/clips/clip_02.mp4"
        mock_row.start_time = "01:00"
        mock_row.end_time = "01:30"
        mock_row.duration = 30.0
        mock_row.text = "More text"
        mock_row.relevance_score = 0.8
        mock_row.reasoning = "Good content"
        mock_row.clip_order = 2
        mock_row.created_at = None

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        clips = await ClipRepository.get_clips_by_task(mock_db, "task-2")

        assert clips[0]["video_url"] == "http://localhost:8008/clips/clip_02.mp4"
        assert clips[0]["created_at"] is None


class TestClipRepositoryGetClipsCount:
    """Test ClipRepository.get_clips_count()."""

    async def test_get_clips_count_with_results(self):
        """Test get_clips_count returns count when clips exist."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock()
        mock_result.scalar.return_value = 5

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await ClipRepository.get_clips_count(mock_db, "task-1")

        assert count == 5

    async def test_get_clips_count_zero(self):
        """Test get_clips_count returns 0 when scalar is None."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock()
        mock_result.scalar.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await ClipRepository.get_clips_count(mock_db, "task-empty")

        assert count == 0

    async def test_get_clips_count_returns_integer(self):
        """Test get_clips_count converts scalar result to int."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock()
        mock_result.scalar.return_value = "3"  # String from database

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        count = await ClipRepository.get_clips_count(mock_db, "task-1")

        assert count == 3
        assert isinstance(count, int)


class TestClipRepositoryDeleteClipsByTask:
    """Test ClipRepository.delete_clips_by_task()."""

    async def test_delete_clips_by_task_returns_count(self):
        """Test delete_clips_by_task executes DELETE and returns rowcount."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock()
        mock_result.rowcount = 3

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        deleted = await ClipRepository.delete_clips_by_task(mock_db, "task-1")

        assert deleted == 3
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    async def test_delete_clips_by_task_no_rowcount(self):
        """Test delete_clips_by_task returns 0 when rowcount is None."""
        from src.repositories.clip_repository import ClipRepository

        mock_result = MagicMock(spec=[])  # No rowcount attribute

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        deleted = await ClipRepository.delete_clips_by_task(mock_db, "task-empty")

        assert deleted == 0


class TestClipRepositoryDeleteClip:
    """Test ClipRepository.delete_clip()."""

    async def test_delete_clip(self):
        """Test that delete_clip executes DELETE and commits."""
        from src.repositories.clip_repository import ClipRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await ClipRepository.delete_clip(mock_db, "clip-123")

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify clip_id is in the params
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["clip_id"] == "clip-123"


# end backend/tests/unit/test_clip_repository.py
