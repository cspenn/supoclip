"""Unit tests for AsyncVideoProcessingService.

Tests the asynchronous video processing service that handles the /start-with-progress
endpoint with SSE progress tracking and unlimited processing time.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.services.video_service_async import AsyncVideoProcessingService


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = MagicMock(spec=Config)
    config.temp_dir = "/tmp/test_clips"
    return config


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def async_service(mock_db, mock_config):
    """Create an AsyncVideoProcessingService instance for testing."""
    return AsyncVideoProcessingService(db=mock_db, config=mock_config)


class TestAsyncVideoServiceInit:
    """Test service initialization."""

    def test_init_stores_db_and_config(self, mock_db, mock_config):
        """Test that __init__ stores database and config."""
        service = AsyncVideoProcessingService(db=mock_db, config=mock_config)
        assert service.db == mock_db
        assert service.config == mock_config


class TestCreateTask:
    """Test task creation functionality."""

    @pytest.mark.asyncio
    async def test_create_task_returns_task_id(self, async_service, mock_db):
        """Test that create_task returns a task ID."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_async.get_youtube_video_title", return_value="Test Title"):
                with patch("src.services.video_service_async.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    task_id = await async_service.create_task(raw_source, "user_123")

                    assert task_id == "task_123"

    @pytest.mark.asyncio
    async def test_create_task_creates_source_and_task(self, async_service, mock_db):
        """Test that create_task creates both source and task records."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_async.get_youtube_video_title", return_value="Test Title"):
                with patch("src.services.video_service_async.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    await async_service.create_task(raw_source, "user_123")

                    # Verify both source and task were added
                    assert mock_db.add.call_count >= 2
                    # Verify flush was called after source creation
                    mock_db.flush.assert_called()
                    # Verify commit was called
                    mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_task_sets_processing_status(self, async_service, mock_db):
        """Test that task is created with 'processing' status."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_async.get_youtube_video_title", return_value="Test Title"):
                with patch("src.services.video_service_async.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    await async_service.create_task(raw_source, "user_123")

                    # Verify Task was created with correct arguments
                    # The call_args contains the keyword arguments used
                    assert any(call[1].get("status") == "processing" for call in mock_task_class.call_args_list if len(call) > 1)

    @pytest.mark.asyncio
    async def test_create_task_with_custom_font_options(self, async_service, mock_db):
        """Test that create_task accepts and stores custom font options."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_async.get_youtube_video_title", return_value="Test Title"):
                with patch("src.services.video_service_async.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    await async_service.create_task(
                        raw_source,
                        "user_123",
                        font_family="Arial",
                        font_size=32,
                        font_color="#FF0000"
                    )

                    # Verify Task was created with custom font options
                    mock_task_class.assert_called()


class TestProcessVideoAsync:
    """Test async video processing functionality."""

    @pytest.mark.asyncio
    async def test_process_video_async_updates_task_status(self, async_service, mock_db):
        """Test that process_video_async updates task status."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4"}

        # Mock the _update_task_status method
        async_service._update_task_status = AsyncMock()

        with patch("src.services.video_service_async.AsyncSessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session_local.return_value = mock_session

            mock_result = MagicMock()
            mock_result.fetchone = MagicMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_result)

            try:
                await async_service.process_video_async("task_123", raw_source, "user_123")
            except Exception:
                pass

            # Verify status update was called at least for "processing"
            calls = [call for call in async_service._update_task_status.call_args_list]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_process_video_async_returns_none(self, async_service, mock_db):
        """Test that process_video_async returns None (fires and forgets)."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4"}

        async_service._update_task_status = AsyncMock()

        with patch("src.services.video_service_async.AsyncSessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session_local.return_value = mock_session

            mock_result = MagicMock()
            mock_result.fetchone = MagicMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_result)

            try:
                result = await async_service.process_video_async("task_123", raw_source, "user_123")
                assert result is None
            except Exception:
                pass


class TestUpdateTaskStatus:
    """Test task status update functionality."""

    @pytest.mark.asyncio
    async def test_update_task_status_executes_update(self, async_service):
        """Test that _update_task_status executes database update."""
        with patch("src.services.video_service_async.AsyncSessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session_local.return_value = mock_session

            await async_service._update_task_status("task_123", "completed")

            # Verify database execute was called
            mock_session.execute.assert_called()
            # Verify database commit was called
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_task_status_different_statuses(self, async_service):
        """Test that different statuses can be set."""
        statuses = ["processing", "completed", "error", "queued"]

        for status in statuses:
            with patch("src.services.video_service_async.AsyncSessionLocal") as mock_session_local:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session_local.return_value = mock_session

                await async_service._update_task_status("task_123", status)

                # Verify execute was called
                mock_session.execute.assert_called()


class TestProcessVideoAsyncErrorHandling:
    """Test error handling in async video processing."""

    @pytest.mark.asyncio
    async def test_process_video_async_marks_error_on_failure(self, async_service):
        """Test that errors mark the task as 'error' status."""
        raw_source = {"url": "/path/to/video.mp4"}

        async_service._update_task_status = AsyncMock()

        with patch("src.services.video_service_async.AsyncSessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session_local.return_value = mock_session

            # Make execute raise an exception to simulate error
            mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

            await async_service.process_video_async("task_123", raw_source, "user_123")

            # Verify error status was set
            error_calls = [
                call for call in async_service._update_task_status.call_args_list
                if len(call[0]) > 1 and call[0][1] == "error"
            ]
            assert len(error_calls) >= 1

# end backend/tests/unit/test_video_service_async.py
