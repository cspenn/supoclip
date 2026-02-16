# start backend/tests/unit/test_job_queue.py
"""
Unit tests for src/workers/job_queue.py - JobQueue compatibility wrapper.

Covers all lines including get_pool, close_pool, enqueue_job (string and callable),
get_job_status, and get_job_result.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.workers.job_queue import JobQueue


class TestJobQueueGetPool:
    """Tests for JobQueue.get_pool classmethod."""

    async def test_get_pool_creates_instance_when_none(self):
        """Test that get_pool creates a new instance when _instance is None."""
        mock_queue = MagicMock()

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            # Reset class state
            JobQueue._instance = None

            pool = await JobQueue.get_pool()

            assert pool is mock_queue
            assert JobQueue._instance is mock_queue

        # Cleanup
        JobQueue._instance = None

    async def test_get_pool_returns_existing_instance(self):
        """Test that get_pool returns existing instance without creating new one."""
        mock_queue = MagicMock()
        JobQueue._instance = mock_queue

        with patch("src.workers.job_queue.get_job_queue") as mock_get:
            pool = await JobQueue.get_pool()

            assert pool is mock_queue
            # get_job_queue should NOT be called since instance exists
            mock_get.assert_not_called()

        # Cleanup
        JobQueue._instance = None


class TestJobQueueClosePool:
    """Tests for JobQueue.close_pool classmethod."""

    async def test_close_pool_stops_workers_and_clears_instance(self):
        """Test that close_pool stops workers and sets instance to None."""
        mock_queue = MagicMock()
        mock_queue.stop_workers = AsyncMock()
        JobQueue._instance = mock_queue

        await JobQueue.close_pool()

        mock_queue.stop_workers.assert_called_once()
        assert JobQueue._instance is None

    async def test_close_pool_noop_when_no_instance(self):
        """Test that close_pool does nothing when _instance is None."""
        JobQueue._instance = None

        # Should not raise
        await JobQueue.close_pool()

        assert JobQueue._instance is None


class TestJobQueueEnqueueJob:
    """Tests for JobQueue.enqueue_job classmethod."""

    async def test_enqueue_job_with_callable(self):
        """Test enqueueing a job with a callable function."""
        mock_queue = MagicMock()
        mock_queue.enqueue_job = AsyncMock(return_value="job-123")

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            async def my_task(x, y):
                pass

            job_id = await JobQueue.enqueue_job(my_task, 1, 2, key="val")

            assert job_id == "job-123"
            mock_queue.enqueue_job.assert_called_once_with(my_task, 1, 2, key="val")

        # Cleanup
        JobQueue._instance = None

    async def test_enqueue_job_with_string_process_video_task(self):
        """Test enqueueing a job by string name 'process_video_task'."""
        mock_queue = MagicMock()
        mock_queue.enqueue_job = AsyncMock(return_value="job-456")

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            job_id = await JobQueue.enqueue_job(
                "process_video_task", "task-1", url="http://example.com"
            )

            assert job_id == "job-456"
            # Verify it resolved the string to the actual function
            call_args = mock_queue.enqueue_job.call_args
            assert callable(call_args.args[0])
            assert call_args.args[1] == "task-1"
            assert call_args.kwargs["url"] == "http://example.com"

        # Cleanup
        JobQueue._instance = None

    async def test_enqueue_job_with_unknown_string_raises_error(self):
        """Test that an unknown string function name raises ValueError."""
        mock_queue = MagicMock()
        mock_queue.enqueue_job = AsyncMock()

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            with pytest.raises(
                ValueError, match="Unknown worker function: unknown_function"
            ):
                await JobQueue.enqueue_job("unknown_function")

        # Cleanup
        JobQueue._instance = None


class TestJobQueueGetJobStatus:
    """Tests for JobQueue.get_job_status classmethod."""

    async def test_get_job_status_returns_status(self):
        """Test get_job_status returns the status from the queue."""
        mock_queue = MagicMock()
        mock_queue.get_job_status = MagicMock(return_value="processing")

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            status = await JobQueue.get_job_status("job-789")

            assert status == "processing"
            mock_queue.get_job_status.assert_called_once_with("job-789")

        # Cleanup
        JobQueue._instance = None

    async def test_get_job_status_returns_none_for_unknown_job(self):
        """Test get_job_status returns None when job is not found."""
        mock_queue = MagicMock()
        mock_queue.get_job_status = MagicMock(return_value=None)

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            status = await JobQueue.get_job_status("nonexistent")

            assert status is None

        # Cleanup
        JobQueue._instance = None


class TestJobQueueGetJobResult:
    """Tests for JobQueue.get_job_result classmethod."""

    async def test_get_job_result_returns_result(self):
        """Test get_job_result returns the result from the queue."""
        mock_queue = MagicMock()
        mock_queue.get_job_result = MagicMock(
            return_value={"clips": [{"id": "clip-1"}]}
        )

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            result = await JobQueue.get_job_result("job-completed")

            assert result == {"clips": [{"id": "clip-1"}]}
            mock_queue.get_job_result.assert_called_once_with("job-completed")

        # Cleanup
        JobQueue._instance = None

    async def test_get_job_result_returns_none_for_incomplete_job(self):
        """Test get_job_result returns None when job is not completed."""
        mock_queue = MagicMock()
        mock_queue.get_job_result = MagicMock(return_value=None)

        with patch("src.workers.job_queue.get_job_queue", return_value=mock_queue):
            JobQueue._instance = None

            result = await JobQueue.get_job_result("job-pending")

            assert result is None

        # Cleanup
        JobQueue._instance = None


# end backend/tests/unit/test_job_queue.py
