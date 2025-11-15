# start backend/src/workers/job_queue.py
"""
Job queue adapter - delegates to LocalJobQueue for compatibility.

This module provides a compatibility layer for code that still imports
from job_queue. It wraps the asyncio-based LocalJobQueue to provide
a unified interface.

MODULE: backend/src/workers/job_queue.py
"""
import logging
from typing import Optional, Callable, Any

from .local_queue import get_job_queue, LocalJobQueue

logger = logging.getLogger(__name__)


class JobQueue:
    """
    Compatibility wrapper for local asyncio job queue.

    Maintains the class-method interface of the original arq-based
    JobQueue while delegating to LocalJobQueue internally.
    """

    _instance: Optional[LocalJobQueue] = None

    @classmethod
    async def get_pool(cls) -> LocalJobQueue:
        """
        Get or create the job queue instance.

        For compatibility with original JobQueue API that had
        get_pool() for initialization.

        Returns:
            LocalJobQueue instance
        """
        if cls._instance is None:
            cls._instance = get_job_queue()
            logger.info("✅ Job queue initialized (local asyncio)")
        return cls._instance

    @classmethod
    async def close_pool(cls) -> None:
        """
        Close and cleanup the job queue.

        For compatibility with original JobQueue API that had
        close_pool() for shutdown.
        """
        if cls._instance is not None:
            await cls._instance.stop_workers()
            cls._instance = None
            logger.info("✅ Job queue closed")

    @classmethod
    async def enqueue_job(
        cls,
        function_name: str | Callable,
        *args: Any,
        **kwargs: Any
    ) -> str:
        """
        Enqueue a job for background processing.

        Accepts both string function names (old arq API) and function
        objects (new asyncio API) for compatibility.

        Args:
            function_name: Function name (str) or callable
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            job_id: Unique identifier for the enqueued job
        """
        queue = await cls.get_pool()

        # Handle both string function names (old arq API) and callables
        if isinstance(function_name, str):
            logger.info(f"📝 Enqueueing job by string name: {function_name}")
            # For now, we only support "process_video_task"
            if function_name == "process_video_task":
                from .tasks import process_video_task
                actual_function = process_video_task
            else:
                raise ValueError(
                    f"Unknown worker function: {function_name}. "
                    "Supported: 'process_video_task'"
                )
        else:
            actual_function = function_name

        job_id = await queue.enqueue_job(actual_function, *args, **kwargs)
        logger.info(f"📝 Enqueued job {job_id}")
        return job_id

    @classmethod
    async def get_job_status(cls, job_id: str) -> Optional[str]:
        """
        Get the status of a job.

        Args:
            job_id: The job ID

        Returns:
            Job status string ("queued", "processing", "completed", "error")
            or None if job not found
        """
        queue = await cls.get_pool()
        return queue.get_job_status(job_id)

    @classmethod
    async def get_job_result(cls, job_id: str) -> Any:
        """
        Get the result of a completed job.

        Args:
            job_id: The job ID

        Returns:
            Job result if completed, None otherwise
        """
        queue = await cls.get_pool()
        return queue.get_job_result(job_id)

# end backend/src/workers/job_queue.py
