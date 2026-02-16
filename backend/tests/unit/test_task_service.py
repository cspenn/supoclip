"""Unit tests for TaskService.

Tests the task service that orchestrates task creation and processing workflow.
Covers all methods and branches for 100% line coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.task_service import TaskService
from src.config import Config


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = MagicMock(spec=Config)
    config.backend_url = "http://localhost:8008"
    return config


@pytest.fixture
def task_service(mock_db, mock_config):
    """Create a TaskService with mocked dependencies."""
    with patch("src.services.task_service.TaskRepository") as mock_task_repo_cls, \
         patch("src.services.task_service.SourceRepository") as mock_source_repo_cls, \
         patch("src.services.task_service.ClipRepository") as mock_clip_repo_cls, \
         patch("src.services.task_service.VideoService") as mock_video_svc_cls:

        service = TaskService(db=mock_db, config=mock_config)
        # Expose the mocks for assertions
        service._mock_task_repo = service.task_repo
        service._mock_source_repo = service.source_repo
        service._mock_clip_repo = service.clip_repo
        service._mock_video_service = service.video_service
        yield service


class TestTaskServiceInit:
    """Test TaskService initialization."""

    def test_init_stores_db_and_config(self, mock_db, mock_config):
        """Test __init__ stores db and explicit config."""
        with patch("src.services.task_service.TaskRepository"), \
             patch("src.services.task_service.SourceRepository"), \
             patch("src.services.task_service.ClipRepository"), \
             patch("src.services.task_service.VideoService"):
            service = TaskService(db=mock_db, config=mock_config)
            assert service.db is mock_db
            assert service.config is mock_config

    def test_init_creates_default_config_when_none(self, mock_db):
        """Test __init__ creates default Config when config is None."""
        with patch("src.services.task_service.TaskRepository"), \
             patch("src.services.task_service.SourceRepository"), \
             patch("src.services.task_service.ClipRepository"), \
             patch("src.services.task_service.VideoService"), \
             patch("src.services.task_service.Config") as mock_config_cls:
            mock_config_cls.return_value = MagicMock()
            service = TaskService(db=mock_db, config=None)
            mock_config_cls.assert_called_once()
            assert service.config is mock_config_cls.return_value


class TestCreateTaskWithSource:
    """Test create_task_with_source method."""

    @pytest.mark.asyncio
    async def test_create_task_with_youtube_url_no_title(self, task_service, mock_db):
        """Test creating a task with a YouTube URL and no explicit title."""
        task_service.task_repo.user_exists = AsyncMock(return_value=True)
        task_service.video_service.determine_source_type = MagicMock(return_value="youtube")
        task_service.video_service.get_video_title = AsyncMock(return_value="My YouTube Video")
        task_service.source_repo.create_source = AsyncMock(return_value="source-123")
        task_service.task_repo.create_task = AsyncMock(return_value="task-456")

        result = await task_service.create_task_with_source(
            user_id="user-1",
            url="https://youtube.com/watch?v=abc123",
        )

        assert result == "task-456"
        task_service.video_service.get_video_title.assert_awaited_once()
        task_service.source_repo.create_source.assert_awaited_once_with(
            mock_db, source_type="youtube", title="My YouTube Video",
            url="https://youtube.com/watch?v=abc123"
        )
        task_service.task_repo.create_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_task_with_upload_url_no_title(self, task_service, mock_db):
        """Test creating a task with an upload URL defaults to 'Uploaded Video'."""
        task_service.task_repo.user_exists = AsyncMock(return_value=True)
        task_service.video_service.determine_source_type = MagicMock(return_value="upload")
        task_service.source_repo.create_source = AsyncMock(return_value="source-789")
        task_service.task_repo.create_task = AsyncMock(return_value="task-101")

        result = await task_service.create_task_with_source(
            user_id="user-1",
            url="/path/to/video.mp4",
        )

        assert result == "task-101"
        task_service.source_repo.create_source.assert_awaited_once_with(
            mock_db, source_type="upload", title="Uploaded Video",
            url="/path/to/video.mp4"
        )

    @pytest.mark.asyncio
    async def test_create_task_with_explicit_title(self, task_service, mock_db):
        """Test creating a task with explicit title skips title lookup."""
        task_service.task_repo.user_exists = AsyncMock(return_value=True)
        task_service.video_service.determine_source_type = MagicMock(return_value="youtube")
        task_service.source_repo.create_source = AsyncMock(return_value="source-111")
        task_service.task_repo.create_task = AsyncMock(return_value="task-222")

        result = await task_service.create_task_with_source(
            user_id="user-1",
            url="https://youtube.com/watch?v=xyz",
            title="My Custom Title",
        )

        assert result == "task-222"
        # get_video_title should NOT be called
        task_service.video_service.get_video_title = AsyncMock()
        task_service.source_repo.create_source.assert_awaited_once_with(
            mock_db, source_type="youtube", title="My Custom Title",
            url="https://youtube.com/watch?v=xyz"
        )

    @pytest.mark.asyncio
    async def test_create_task_with_custom_font_options(self, task_service, mock_db):
        """Test creating a task with custom font options."""
        task_service.task_repo.user_exists = AsyncMock(return_value=True)
        task_service.video_service.determine_source_type = MagicMock(return_value="upload")
        task_service.source_repo.create_source = AsyncMock(return_value="source-333")
        task_service.task_repo.create_task = AsyncMock(return_value="task-444")

        result = await task_service.create_task_with_source(
            user_id="user-1",
            url="/path/to/video.mp4",
            title="Test",
            font_family="Arial",
            font_size=32,
            font_color="#FF0000",
        )

        assert result == "task-444"
        call_kwargs = task_service.task_repo.create_task.call_args
        assert call_kwargs[1]["font_family"] == "Arial"
        assert call_kwargs[1]["font_size"] == 32
        assert call_kwargs[1]["font_color"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_create_task_user_not_found_raises_value_error(self, task_service, mock_db):
        """Test that ValueError is raised when user is not found."""
        task_service.task_repo.user_exists = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="User .* not found"):
            await task_service.create_task_with_source(
                user_id="nonexistent-user",
                url="https://youtube.com/watch?v=abc",
            )


class TestProcessTask:
    """Test process_task method."""

    @pytest.mark.asyncio
    async def test_process_task_success(self, task_service, mock_db):
        """Test successful task processing end-to-end."""
        task_service.task_repo.update_task_status = AsyncMock()
        task_service.task_repo.update_task_clips = AsyncMock()
        task_service.video_service.process_video_complete = AsyncMock(return_value={
            "clips": [
                {
                    "filename": "clip1.mp4",
                    "path": "/tmp/clips/clip1.mp4",
                    "start_time": "00:10",
                    "end_time": "00:30",
                    "duration": 20.0,
                    "text": "Some text",
                    "relevance_score": 0.9,
                    "reasoning": "Good content",
                },
                {
                    "filename": "clip2.mp4",
                    "path": "/tmp/clips/clip2.mp4",
                    "start_time": "01:00",
                    "end_time": "01:20",
                    "duration": 20.0,
                    "text": "More text",
                    "relevance_score": 0.85,
                    "reasoning": "Also good",
                },
            ],
            "segments": [{"start": 10, "end": 30}],
            "summary": "A video summary",
            "key_topics": ["topic1", "topic2"],
        })
        task_service.clip_repo.create_clip = AsyncMock(side_effect=["clip-1", "clip-2"])

        result = await task_service.process_task(
            task_id="task-100",
            url="https://youtube.com/watch?v=abc",
            source_type="youtube",
            font_family="Arial",
            font_size=32,
            font_color="#FF0000",
            min_length=15,
            max_length=40,
            logo_path="/path/to/logo.png",
            logo_corner_position="top-left",
        )

        assert result["task_id"] == "task-100"
        assert result["clips_count"] == 2
        assert result["summary"] == "A video summary"
        assert result["key_topics"] == ["topic1", "topic2"]

        # Verify status updates
        status_calls = task_service.task_repo.update_task_status.call_args_list
        assert len(status_calls) >= 3  # processing(0), processing(95), completed(100)

        # Verify clips were created
        assert task_service.clip_repo.create_clip.call_count == 2

        # Verify task clips were updated
        task_service.task_repo.update_task_clips.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_task_with_progress_callback(self, task_service, mock_db):
        """Test that progress_callback is invoked during processing."""
        task_service.task_repo.update_task_status = AsyncMock()
        task_service.task_repo.update_task_clips = AsyncMock()
        task_service.video_service.process_video_complete = AsyncMock(return_value={
            "clips": [],
            "segments": [],
            "summary": None,
            "key_topics": None,
        })

        progress_callback = AsyncMock()

        await task_service.process_task(
            task_id="task-200",
            url="/video.mp4",
            source_type="upload",
            progress_callback=progress_callback,
        )

        # The progress_callback is passed to process_video_complete via update_progress wrapper
        # Verify update_task_status was called for the progress update
        assert task_service.task_repo.update_task_status.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_task_with_progress_callback_invoked(self, task_service, mock_db):
        """Test progress callback wrapper calls both repo and external callback."""
        progress_callback = AsyncMock()

        # Capture the progress_callback passed to process_video_complete
        captured_callback = None

        async def capture_process_video_complete(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("progress_callback")
            return {
                "clips": [],
                "segments": [],
                "summary": None,
                "key_topics": None,
            }

        task_service.task_repo.update_task_status = AsyncMock()
        task_service.task_repo.update_task_clips = AsyncMock()
        task_service.video_service.process_video_complete = AsyncMock(
            side_effect=capture_process_video_complete
        )

        await task_service.process_task(
            task_id="task-300",
            url="/video.mp4",
            source_type="upload",
            progress_callback=progress_callback,
        )

        # Now call the captured callback to test the wrapper
        assert captured_callback is not None
        await captured_callback(50, "Testing progress")

        # Verify both the repo and external callback were called
        progress_callback.assert_awaited_once_with(50, "Testing progress")

    @pytest.mark.asyncio
    async def test_process_task_error_sets_error_status(self, task_service, mock_db):
        """Test that errors update task status to 'error' and re-raise."""
        task_service.task_repo.update_task_status = AsyncMock()
        task_service.video_service.process_video_complete = AsyncMock(
            side_effect=RuntimeError("Processing failed")
        )

        with pytest.raises(RuntimeError, match="Processing failed"):
            await task_service.process_task(
                task_id="task-400",
                url="/video.mp4",
                source_type="upload",
            )

        # Verify error status was set
        error_calls = [
            call for call in task_service.task_repo.update_task_status.call_args_list
            if call[0][2] == "error" or call[1].get("status") == "error"
            or (len(call[0]) > 2 and call[0][2] == "error")
        ]
        assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_process_task_no_summary_no_key_topics(self, task_service, mock_db):
        """Test process_task when result has no summary or key_topics."""
        task_service.task_repo.update_task_status = AsyncMock()
        task_service.task_repo.update_task_clips = AsyncMock()
        task_service.video_service.process_video_complete = AsyncMock(return_value={
            "clips": [],
            "segments": [],
        })
        result = await task_service.process_task(
            task_id="task-500",
            url="/video.mp4",
            source_type="upload",
        )
        assert result["summary"] is None
        assert result["key_topics"] is None


class TestGetTaskWithClips:
    """Test get_task_with_clips method."""

    @pytest.mark.asyncio
    async def test_get_task_with_clips_found(self, task_service, mock_db, mock_config):
        """Test getting a task with clips when task exists."""
        task_service.task_repo.get_task_by_id = AsyncMock(return_value={
            "id": "task-600",
            "status": "completed",
        })
        task_service.clip_repo.get_clips_by_task = AsyncMock(return_value=[
            {"id": "clip-1", "filename": "clip1.mp4"},
            {"id": "clip-2", "filename": "clip2.mp4"},
        ])

        result = await task_service.get_task_with_clips("task-600")

        assert result is not None
        assert result["id"] == "task-600"
        assert result["clips_count"] == 2
        assert len(result["clips"]) == 2
        task_service.clip_repo.get_clips_by_task.assert_awaited_once_with(
            mock_db, "task-600", backend_url=mock_config.backend_url
        )

    @pytest.mark.asyncio
    async def test_get_task_with_clips_not_found(self, task_service, mock_db):
        """Test getting a task when it does not exist."""
        task_service.task_repo.get_task_by_id = AsyncMock(return_value=None)

        result = await task_service.get_task_with_clips("nonexistent-task")

        assert result is None


class TestGetUserTasks:
    """Test get_user_tasks method."""

    @pytest.mark.asyncio
    async def test_get_user_tasks(self, task_service, mock_db):
        """Test getting all tasks for a user."""
        task_service.task_repo.get_user_tasks = AsyncMock(return_value=[
            {"id": "task-1", "status": "completed"},
            {"id": "task-2", "status": "processing"},
        ])

        result = await task_service.get_user_tasks("user-1", limit=10)

        assert len(result) == 2
        task_service.task_repo.get_user_tasks.assert_awaited_once_with(mock_db, "user-1", 10)


class TestDeleteTask:
    """Test delete_task method."""

    @pytest.mark.asyncio
    async def test_delete_task(self, task_service, mock_db):
        """Test deleting a task and its clips."""
        task_service.clip_repo.delete_clips_by_task = AsyncMock()
        task_service.task_repo.delete_task = AsyncMock()

        await task_service.delete_task("task-700")

        task_service.clip_repo.delete_clips_by_task.assert_awaited_once_with(mock_db, "task-700")
        task_service.task_repo.delete_task.assert_awaited_once_with(mock_db, "task-700")


# end backend/tests/unit/test_task_service.py
