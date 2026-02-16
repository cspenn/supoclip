# start backend/tests/unit/test_workers_tasks.py
"""
Unit tests for src/workers/tasks.py - process_video_task worker function.

Covers all lines including the happy path, error handling, and progress updates.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestProcessVideoTask:
    """Tests for process_video_task worker function."""

    @pytest.fixture
    def mock_progress_tracker(self):
        """Create a mock progress tracker."""
        tracker = MagicMock()
        tracker.update = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_task_service(self):
        """Create a mock TaskService."""
        service = AsyncMock()
        service.process_task = AsyncMock(return_value={"clips": [{"id": "clip-1"}]})
        return service

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock async database session context manager."""
        session = AsyncMock()
        return session

    async def test_process_video_task_success(
        self, mock_progress_tracker, mock_task_service, mock_db_session
    ):
        """Test successful video processing with all parameters."""
        with (
            patch(
                "src.workers.tasks.get_progress_tracker",
                return_value=mock_progress_tracker,
            ),
            patch("src.workers.tasks.Config") as mock_config_cls,
            patch("src.workers.tasks.AsyncSessionLocal") as mock_session_local,
            patch("src.workers.tasks.TaskService", return_value=mock_task_service),
        ):
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config

            # Make AsyncSessionLocal work as async context manager
            mock_session_local.return_value.__aenter__ = AsyncMock(
                return_value=mock_db_session
            )
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.workers.tasks import process_video_task

            result = await process_video_task(
                task_id="task-123",
                url="https://youtube.com/watch?v=test",
                source_type="youtube",
                user_id="user-1",
                font_family="Arial",
                font_size=30,
                font_color="#FF0000",
                min_length=15,
                max_length=60,
                logo_path="/path/to/logo.png",
                logo_corner_position="top-left",
            )

            # Verify result
            assert result == {"clips": [{"id": "clip-1"}]}

            # Verify TaskService was instantiated with session and config
            from src.workers.tasks import TaskService

            TaskService.assert_called_once_with(mock_db_session, mock_config)

            # Verify process_task was called with correct parameters
            mock_task_service.process_task.assert_called_once()
            call_kwargs = mock_task_service.process_task.call_args
            assert call_kwargs.kwargs["task_id"] == "task-123"
            assert call_kwargs.kwargs["url"] == "https://youtube.com/watch?v=test"
            assert call_kwargs.kwargs["source_type"] == "youtube"
            assert call_kwargs.kwargs["font_family"] == "Arial"
            assert call_kwargs.kwargs["font_size"] == 30
            assert call_kwargs.kwargs["font_color"] == "#FF0000"
            assert call_kwargs.kwargs["min_length"] == 15
            assert call_kwargs.kwargs["max_length"] == 60
            assert call_kwargs.kwargs["logo_path"] == "/path/to/logo.png"
            assert call_kwargs.kwargs["logo_corner_position"] == "top-left"
            assert callable(call_kwargs.kwargs["progress_callback"])

            # Verify completion progress was reported
            mock_progress_tracker.update.assert_any_call(
                "task-123", 100, "Completed", "completed"
            )

    async def test_process_video_task_default_parameters(
        self, mock_progress_tracker, mock_task_service, mock_db_session
    ):
        """Test process_video_task with default parameters."""
        with (
            patch(
                "src.workers.tasks.get_progress_tracker",
                return_value=mock_progress_tracker,
            ),
            patch("src.workers.tasks.Config") as mock_config_cls,
            patch("src.workers.tasks.AsyncSessionLocal") as mock_session_local,
            patch("src.workers.tasks.TaskService", return_value=mock_task_service),
        ):
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config
            mock_session_local.return_value.__aenter__ = AsyncMock(
                return_value=mock_db_session
            )
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.workers.tasks import process_video_task

            result = await process_video_task(
                task_id="task-456",
                url="/uploads/video.mp4",
                source_type="upload",
                user_id="user-2",
            )

            assert result == {"clips": [{"id": "clip-1"}]}

            # Verify defaults were passed
            call_kwargs = mock_task_service.process_task.call_args.kwargs
            assert call_kwargs["font_family"] == "TikTokSans-Regular"
            assert call_kwargs["font_size"] == 24
            assert call_kwargs["font_color"] == "#FFFFFF"
            assert call_kwargs["min_length"] == 10
            assert call_kwargs["max_length"] == 45
            assert call_kwargs["logo_path"] is None
            assert call_kwargs["logo_corner_position"] == "top-right"

    async def test_process_video_task_error_handling(
        self, mock_progress_tracker, mock_db_session
    ):
        """Test error handling when process_task raises an exception."""
        failing_service = AsyncMock()
        failing_service.process_task = AsyncMock(
            side_effect=RuntimeError("Processing failed")
        )

        with (
            patch(
                "src.workers.tasks.get_progress_tracker",
                return_value=mock_progress_tracker,
            ),
            patch("src.workers.tasks.Config") as mock_config_cls,
            patch("src.workers.tasks.AsyncSessionLocal") as mock_session_local,
            patch("src.workers.tasks.TaskService", return_value=failing_service),
        ):
            mock_config_cls.return_value = MagicMock()
            mock_session_local.return_value.__aenter__ = AsyncMock(
                return_value=mock_db_session
            )
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.workers.tasks import process_video_task

            with pytest.raises(RuntimeError, match="Processing failed"):
                await process_video_task(
                    task_id="task-error",
                    url="https://youtube.com/watch?v=fail",
                    source_type="youtube",
                    user_id="user-1",
                )

            # Verify error progress was reported
            mock_progress_tracker.update.assert_any_call(
                "task-error", 0, "Error: Processing failed", "error"
            )

    async def test_progress_callback_invokes_tracker(
        self, mock_progress_tracker, mock_db_session
    ):
        """Test that the progress callback correctly calls the progress tracker."""
        captured_callback = None

        async def capture_process_task(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs["progress_callback"]
            # Invoke the callback to exercise lines 67-68
            await captured_callback(50, "Half done")
            return {"clips": []}

        mock_service = AsyncMock()
        mock_service.process_task = capture_process_task

        with (
            patch(
                "src.workers.tasks.get_progress_tracker",
                return_value=mock_progress_tracker,
            ),
            patch("src.workers.tasks.Config") as mock_config_cls,
            patch("src.workers.tasks.AsyncSessionLocal") as mock_session_local,
            patch("src.workers.tasks.TaskService", return_value=mock_service),
        ):
            mock_config_cls.return_value = MagicMock()
            mock_session_local.return_value.__aenter__ = AsyncMock(
                return_value=mock_db_session
            )
            mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.workers.tasks import process_video_task

            await process_video_task(
                task_id="task-progress",
                url="https://youtube.com/watch?v=test",
                source_type="youtube",
                user_id="user-1",
            )

            # Verify progress tracker was called by the callback
            mock_progress_tracker.update.assert_any_call(
                "task-progress", 50, "Half done", "processing"
            )


# end backend/tests/unit/test_workers_tasks.py
