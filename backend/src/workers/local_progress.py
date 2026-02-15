# start backend/src/workers/local_progress.py
"""
In-memory progress tracking (replaces Redis pub/sub).
Provides real-time progress updates with async generators for SSE streaming.

Module: backend/src/workers/local_progress.py
"""

import asyncio
import logging
from contextlib import suppress
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Progress:
    """Progress information for a task."""

    task_id: str
    progress: int  # 0-100
    message: str
    status: str  # queued, processing, completed, error
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert progress to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "progress": self.progress,
            "message": self.message,
            "status": self.status,
            "updated_at": self.updated_at.isoformat(),
        }


class LocalProgressTracker:
    """In-memory progress tracking with async notification."""

    def __init__(self) -> None:
        """Initialize the progress tracker."""
        self.progress_data: dict[str, Progress] = {}
        self.subscribers: dict[str, list] = {}  # task_id -> list of asyncio.Queue

    async def update(
        self, task_id: str, progress: int, message: str, status: str = "processing"
    ) -> None:
        """
        Update progress for a task.

        Args:
            task_id: Unique task identifier
            progress: Progress percentage (0-100)
            message: Progress message
            status: Task status (queued, processing, completed, error)
        """
        prog = Progress(
            task_id=task_id,
            progress=progress,
            message=message,
            status=status,
            updated_at=datetime.now(),
        )

        self.progress_data[task_id] = prog

        # Notify all subscribers
        if task_id in self.subscribers:
            for queue in self.subscribers[task_id]:
                try:
                    await queue.put(prog)
                except Exception as e:
                    logger.warning(f"Failed to notify subscriber: {e}")

        logger.debug(f"Progress update for {task_id}: {progress}% - {message}")

    def get(self, task_id: str) -> Progress | None:
        """
        Get current progress.

        Args:
            task_id: Unique task identifier

        Returns:
            Progress object if exists, None otherwise
        """
        return self.progress_data.get(task_id)

    async def complete(self, task_id: str, message: str = "Complete!") -> None:
        """
        Mark task as completed.

        Args:
            task_id: Unique task identifier
            message: Completion message
        """
        await self.update(task_id, 100, message, "completed")

    async def error(self, task_id: str, message: str) -> None:
        """
        Mark task as failed.

        Args:
            task_id: Unique task identifier
            message: Error message
        """
        await self.update(task_id, 0, message, "error")

    async def subscribe(self, task_id: str) -> AsyncGenerator[Progress, None]:
        """
        Subscribe to progress updates for a task.
        Yields progress updates as they occur.

        Args:
            task_id: Unique task identifier

        Yields:
            Progress objects as they are updated
        """
        queue: asyncio.Queue = asyncio.Queue()

        # Add subscriber
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        self.subscribers[task_id].append(queue)

        try:
            # Send current progress if exists
            current = self.get(task_id)
            if current:
                yield current

            # Wait for updates
            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=60.0)
                    yield progress

                    # Stop if completed or errored
                    if progress.status in ("completed", "error"):
                        break

                except asyncio.TimeoutError:
                    # Send keep-alive
                    current = self.get(task_id)
                    if current:
                        yield current

        finally:
            # Remove subscriber
            if task_id in self.subscribers:
                with suppress(ValueError):
                    self.subscribers[task_id].remove(queue)


# Global tracker instance
_progress_tracker: LocalProgressTracker | None = None


def get_progress_tracker() -> LocalProgressTracker:
    """
    Get or create the global progress tracker.

    Returns:
        LocalProgressTracker instance
    """
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = LocalProgressTracker()
    return _progress_tracker


# end backend/src/workers/local_progress.py
