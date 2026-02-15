"""
Local async queue for background tasks (replaces Redis/arq).
Uses asyncio.Queue for lightweight job processing without external dependencies.

Module: backend/src/workers/local_queue.py
"""

import asyncio
import logging
import traceback
from typing import Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents a background job."""

    job_id: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: str = "queued"  # queued, processing, completed, error
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class LocalJobQueue:
    """Async job queue using asyncio (no Redis required)."""

    def __init__(self, max_workers: int = 2) -> None:
        """
        Initialize the local job queue.

        Args:
            max_workers: Number of concurrent workers
        """
        self.queue: asyncio.Queue = asyncio.Queue()
        self.jobs: Dict[str, Job] = {}  # In-memory job storage
        self.max_workers: int = max_workers
        self.workers: list = []
        self._running: bool = False

    async def start_workers(self) -> None:
        """Start background worker tasks."""
        if self._running:
            return

        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

        logger.info(f"Started {self.max_workers} local workers")

    async def stop_workers(self) -> None:
        """Stop all workers gracefully."""
        self._running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Stopped all local workers")

    async def _worker(self, name: str) -> None:
        """
        Worker coroutine that processes jobs from the queue.

        Args:
            name: Worker identifier
        """
        logger.info(f"Worker {name} started")

        while self._running:
            try:
                job = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                logger.info(f"Worker {name} processing job {job.job_id}")
                job.status = "processing"
                job.started_at = datetime.now()

                try:
                    # Execute the job function
                    result = await job.function(*job.args, **job.kwargs)
                    job.result = result
                    job.status = "completed"
                    logger.info(f"Job {job.job_id} completed successfully")

                except Exception as e:
                    job.error = f"{e}\n\nTraceback:\n{traceback.format_exc()}"
                    job.status = "error"
                    logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)

                finally:
                    job.completed_at = datetime.now()
                    self.queue.task_done()

            except asyncio.TimeoutError:
                continue  # No jobs in queue, keep waiting
            except asyncio.CancelledError:
                logger.info(f"Worker {name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}", exc_info=True)

    async def enqueue_job(self, function: Callable, *args: Any, **kwargs: Any) -> str:
        """
        Enqueue a job to be processed by workers.

        Args:
            function: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, function=function, args=args, kwargs=kwargs)

        self.jobs[job_id] = job
        await self.queue.put(job)

        logger.info(f"Enqueued job {job_id}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.

        Args:
            job_id: Unique job identifier

        Returns:
            Job object if found, None otherwise
        """
        return self.jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[str]:
        """
        Get job status.

        Args:
            job_id: Unique job identifier

        Returns:
            Job status string or None
        """
        job = self.get_job(job_id)
        return job.status if job else None

    def get_job_result(self, job_id: str) -> Any:
        """
        Get job result (if completed).

        Args:
            job_id: Unique job identifier

        Returns:
            Job result if completed, None otherwise
        """
        job = self.get_job(job_id)
        if job and job.status == "completed":
            return job.result
        return None


# Global queue instance
_job_queue: Optional[LocalJobQueue] = None


def get_job_queue() -> LocalJobQueue:
    """
    Get or create the global job queue.

    Returns:
        LocalJobQueue instance
    """
    global _job_queue
    if _job_queue is None:
        _job_queue = LocalJobQueue(max_workers=2)
    return _job_queue


# end backend/src/workers/local_queue.py
