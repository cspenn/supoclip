"""
Local job queue tests for SupoClip backend.

Tests:
- Job queue initialization
- Job enqueueing
- Job processing
- Job status tracking
- Worker lifecycle management
- Error handling in jobs
- Multiple concurrent workers
"""
import asyncio
import pytest
import sys
from pathlib import Path
from datetime import datetime

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.workers.local_queue import LocalJobQueue, Job


class TestLocalJobQueueInitialization:
    """Test job queue initialization."""

    def test_queue_initialization(self):
        """Test creating a LocalJobQueue instance."""
        queue = LocalJobQueue(max_workers=2)
        assert queue is not None
        assert queue.max_workers == 2
        assert not queue._running

    def test_custom_worker_count(self):
        """Test creating queue with custom worker count."""
        queue = LocalJobQueue(max_workers=4)
        assert queue.max_workers == 4

    def test_queue_internal_state(self):
        """Test queue internal state after initialization."""
        queue = LocalJobQueue(max_workers=2)
        assert isinstance(queue.queue, asyncio.Queue)
        assert isinstance(queue.jobs, dict)
        assert len(queue.jobs) == 0


class TestJobDataStructure:
    """Test the Job data structure."""

    async def test_job_creation(self):
        """Test creating a Job instance."""
        async def sample_func():
            return "result"

        job = Job(
            job_id="job-1",
            function=sample_func,
            args=(),
            kwargs={}
        )

        assert job.job_id == "job-1"
        assert job.status == "queued"
        assert job.result is None
        assert job.error is None
        assert job.created_at is not None

    async def test_job_with_arguments(self):
        """Test creating a Job with arguments."""
        async def sample_func(a, b, c=None):
            return a + b

        job = Job(
            job_id="job-2",
            function=sample_func,
            args=(1, 2),
            kwargs={"c": 3}
        )

        assert job.args == (1, 2)
        assert job.kwargs == {"c": 3}


class TestJobEnqueueing:
    """Test enqueueing jobs to the queue."""

    async def test_enqueue_job(self):
        """Test enqueueing a job."""
        queue = LocalJobQueue(max_workers=1)

        async def simple_job():
            return "done"

        job_id = await queue.enqueue_job(simple_job)

        assert job_id is not None
        assert job_id in queue.jobs
        assert queue.jobs[job_id].status == "queued"

    async def test_enqueue_multiple_jobs(self):
        """Test enqueueing multiple jobs."""
        queue = LocalJobQueue(max_workers=2)

        async def simple_job(value):
            return value * 2

        job_ids = []
        for i in range(3):
            job_id = await queue.enqueue_job(simple_job, i)
            job_ids.append(job_id)

        assert len(job_ids) == 3
        assert len(queue.jobs) == 3

    async def test_enqueue_job_with_args_kwargs(self):
        """Test enqueueing job with arguments and kwargs."""
        queue = LocalJobQueue(max_workers=1)

        async def job_with_params(a, b, multiplier=1):
            return (a + b) * multiplier

        job_id = await queue.enqueue_job(
            job_with_params,
            10,
            20,
            multiplier=2
        )

        job = queue.jobs[job_id]
        assert job.args == (10, 20)
        assert job.kwargs == {"multiplier": 2}


class TestJobProcessing:
    """Test job processing by workers."""

    async def test_worker_processes_job(self):
        """Test that worker processes a simple job."""
        queue = LocalJobQueue(max_workers=1)

        async def simple_job():
            return "success"

        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(simple_job)

            # Wait for job to complete
            max_attempts = 50
            for _ in range(max_attempts):
                if queue.get_job_status(job_id) == "completed":
                    break
                await asyncio.sleep(0.1)

            job = queue.get_job(job_id)
            assert job.status == "completed"
            assert job.result == "success"

        finally:
            await queue.stop_workers()

    async def test_worker_processes_job_with_args(self):
        """Test worker processing job with arguments."""
        queue = LocalJobQueue(max_workers=1)

        async def add_numbers(a, b):
            return a + b

        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(add_numbers, 5, 3)

            # Wait for job to complete
            max_attempts = 50
            for _ in range(max_attempts):
                if queue.get_job_status(job_id) == "completed":
                    break
                await asyncio.sleep(0.1)

            result = queue.get_job_result(job_id)
            assert result == 8

        finally:
            await queue.stop_workers()

    async def test_multiple_workers_process_jobs(self):
        """Test multiple workers processing jobs concurrently."""
        queue = LocalJobQueue(max_workers=2)

        processed_values = []

        async def process_value(value):
            await asyncio.sleep(0.05)  # Simulate processing time
            processed_values.append(value)
            return value * 2

        await queue.start_workers()

        try:
            job_ids = []
            for i in range(4):
                job_id = await queue.enqueue_job(process_value, i)
                job_ids.append(job_id)

            # Wait for all jobs to complete
            max_attempts = 100
            for _ in range(max_attempts):
                all_done = all(
                    queue.get_job_status(jid) == "completed"
                    for jid in job_ids
                )
                if all_done:
                    break
                await asyncio.sleep(0.1)

            # Verify all jobs completed
            for job_id in job_ids:
                assert queue.get_job_status(job_id) == "completed"

            # Verify results
            results = [queue.get_job_result(jid) for jid in job_ids]
            assert len(results) == 4
            assert all(r is not None for r in results)

        finally:
            await queue.stop_workers()


class TestJobStatusTracking:
    """Test job status tracking."""

    async def test_job_status_queued(self):
        """Test job status is 'queued' when created."""
        queue = LocalJobQueue(max_workers=1)

        async def dummy_job():
            pass

        job_id = await queue.enqueue_job(dummy_job)
        assert queue.get_job_status(job_id) == "queued"

    async def test_get_job_status(self):
        """Test retrieving job status."""
        queue = LocalJobQueue(max_workers=1)

        async def dummy_job():
            return None

        job_id = await queue.enqueue_job(dummy_job)
        status = queue.get_job_status(job_id)

        assert status in ["queued", "processing"]

    async def test_get_job_result_pending(self):
        """Test getting result of pending job returns None."""
        queue = LocalJobQueue(max_workers=1)

        async def dummy_job():
            await asyncio.sleep(1)
            return "done"

        job_id = await queue.enqueue_job(dummy_job)
        result = queue.get_job_result(job_id)

        assert result is None

    async def test_get_nonexistent_job(self):
        """Test getting nonexistent job returns None."""
        queue = LocalJobQueue(max_workers=1)

        job = queue.get_job("nonexistent-job-id")
        assert job is None

    async def test_job_timestamps(self):
        """Test job timestamps are set correctly."""
        queue = LocalJobQueue(max_workers=1)

        async def dummy_job():
            return None

        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(dummy_job)
            job = queue.get_job(job_id)

            assert job.created_at is not None
            assert isinstance(job.created_at, datetime)

            # Wait for processing
            max_attempts = 50
            for _ in range(max_attempts):
                if job.status == "completed":
                    break
                await asyncio.sleep(0.1)

            # Check processing timestamps
            assert job.started_at is not None
            assert job.completed_at is not None

        finally:
            await queue.stop_workers()


class TestErrorHandling:
    """Test error handling in job processing."""

    async def test_job_error_handling(self):
        """Test that job errors are caught and stored."""
        queue = LocalJobQueue(max_workers=1)

        async def failing_job():
            raise ValueError("Test error")

        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(failing_job)

            # Wait for job to fail
            max_attempts = 50
            for _ in range(max_attempts):
                if queue.get_job_status(job_id) == "error":
                    break
                await asyncio.sleep(0.1)

            job = queue.get_job(job_id)
            assert job.status == "error"
            assert "Test error" in job.error

        finally:
            await queue.stop_workers()

    async def test_job_error_with_result_none(self):
        """Test that failing job has no result."""
        queue = LocalJobQueue(max_workers=1)

        async def failing_job():
            raise RuntimeError("Job failed")

        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(failing_job)

            # Wait for job to fail
            max_attempts = 50
            for _ in range(max_attempts):
                if queue.get_job_status(job_id) == "error":
                    break
                await asyncio.sleep(0.1)

            result = queue.get_job_result(job_id)
            assert result is None

        finally:
            await queue.stop_workers()


class TestWorkerLifecycle:
    """Test worker lifecycle management."""

    async def test_start_workers(self):
        """Test starting workers."""
        queue = LocalJobQueue(max_workers=2)

        assert not queue._running
        assert len(queue.workers) == 0

        await queue.start_workers()

        assert queue._running
        assert len(queue.workers) == 2

        await queue.stop_workers()

    async def test_stop_workers(self):
        """Test stopping workers."""
        queue = LocalJobQueue(max_workers=2)

        await queue.start_workers()
        assert queue._running

        await queue.stop_workers()

        assert not queue._running
        assert len(queue.workers) == 0

    async def test_start_workers_idempotent(self):
        """Test that starting workers multiple times is safe."""
        queue = LocalJobQueue(max_workers=1)

        await queue.start_workers()
        initial_count = len(queue.workers)

        # Start again - should not create new workers
        await queue.start_workers()
        assert len(queue.workers) == initial_count

        await queue.stop_workers()

    async def test_queue_with_context_manager_pattern(self):
        """Test queue lifecycle pattern."""
        queue = LocalJobQueue(max_workers=1)

        async def simple_job():
            return "done"

        # Start workers
        await queue.start_workers()

        try:
            job_id = await queue.enqueue_job(simple_job)
            assert job_id is not None

        finally:
            # Stop workers
            await queue.stop_workers()

        assert not queue._running


class TestJobQueueIntegration:
    """Integration tests for job queue functionality."""

    async def test_full_job_lifecycle(self):
        """Test complete job lifecycle from enqueue to completion."""
        queue = LocalJobQueue(max_workers=1)

        async def calculate(x, y):
            await asyncio.sleep(0.05)
            return x * y

        await queue.start_workers()

        try:
            # Enqueue job
            job_id = await queue.enqueue_job(calculate, 6, 7)
            assert queue.get_job_status(job_id) == "queued"

            # Wait for completion
            max_attempts = 100
            for _ in range(max_attempts):
                if queue.get_job_status(job_id) == "completed":
                    break
                await asyncio.sleep(0.05)

            # Verify result
            result = queue.get_job_result(job_id)
            assert result == 42

        finally:
            await queue.stop_workers()

    async def test_sequential_jobs(self):
        """Test that jobs process sequentially in order."""
        queue = LocalJobQueue(max_workers=1)

        results = []

        async def append_value(value):
            await asyncio.sleep(0.05)
            results.append(value)
            return value

        await queue.start_workers()

        try:
            job_ids = []
            for i in range(3):
                job_id = await queue.enqueue_job(append_value, i)
                job_ids.append(job_id)

            # Wait for all jobs
            max_attempts = 150
            for _ in range(max_attempts):
                if all(queue.get_job_status(jid) == "completed" for jid in job_ids):
                    break
                await asyncio.sleep(0.05)

            # Results should be in order
            assert results == [0, 1, 2]

        finally:
            await queue.stop_workers()
