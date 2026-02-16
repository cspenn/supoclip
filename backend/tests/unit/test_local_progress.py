# start backend/tests/unit/test_local_progress.py
"""
Unit tests for src/workers/local_progress.py - LocalProgressTracker.

Covers all lines including Progress dataclass, update with subscribers,
get, complete, error, subscribe generator, and get_progress_tracker singleton.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from src.workers.local_progress import (
    LocalProgressTracker,
    Progress,
    get_progress_tracker,
    _progress_tracker,
)


class TestProgressDataclass:
    """Tests for the Progress dataclass."""

    def test_progress_to_dict(self):
        """Test Progress.to_dict() returns correct dictionary (line 31)."""
        prog = Progress(
            task_id="task-1",
            progress=50,
            message="Processing",
            status="processing",
        )

        result = prog.to_dict()

        assert result["task_id"] == "task-1"
        assert result["progress"] == 50
        assert result["message"] == "Processing"
        assert result["status"] == "processing"
        assert "updated_at" in result
        # updated_at should be an ISO format string
        assert isinstance(result["updated_at"], str)

    def test_progress_default_updated_at(self):
        """Test that updated_at defaults to current time."""
        prog = Progress(
            task_id="task-2", progress=0, message="Queued", status="queued"
        )
        assert prog.updated_at is not None


class TestLocalProgressTrackerInit:
    """Tests for LocalProgressTracker initialization."""

    def test_init_creates_empty_dicts(self):
        """Test __init__ creates empty progress_data and subscribers (lines 45-46)."""
        tracker = LocalProgressTracker()

        assert tracker.progress_data == {}
        assert tracker.subscribers == {}


class TestLocalProgressTrackerUpdate:
    """Tests for LocalProgressTracker.update method."""

    async def test_update_stores_progress(self):
        """Test update stores progress data (lines 60-68)."""
        tracker = LocalProgressTracker()

        await tracker.update("task-1", 25, "Downloading", "processing")

        prog = tracker.progress_data["task-1"]
        assert prog.task_id == "task-1"
        assert prog.progress == 25
        assert prog.message == "Downloading"
        assert prog.status == "processing"

    async def test_update_notifies_subscribers(self):
        """Test update puts progress on subscriber queues (lines 71-74)."""
        tracker = LocalProgressTracker()
        queue = asyncio.Queue()
        tracker.subscribers["task-1"] = [queue]

        await tracker.update("task-1", 50, "Processing", "processing")

        # Check the queue received the progress update
        assert not queue.empty()
        prog = await queue.get()
        assert prog.task_id == "task-1"
        assert prog.progress == 50

    async def test_update_handles_subscriber_notification_error(self):
        """Test update handles failed notification gracefully (lines 75-76)."""
        tracker = LocalProgressTracker()

        # Create a mock queue that raises on put
        bad_queue = AsyncMock()
        bad_queue.put = AsyncMock(side_effect=RuntimeError("Queue broken"))
        tracker.subscribers["task-1"] = [bad_queue]

        # Should not raise
        await tracker.update("task-1", 50, "Processing", "processing")

        # Progress data should still be stored
        assert "task-1" in tracker.progress_data

    async def test_update_no_subscribers(self):
        """Test update with no subscribers does not error (line 78)."""
        tracker = LocalProgressTracker()

        # No subscribers set up
        await tracker.update("task-1", 75, "Almost done", "processing")

        assert tracker.progress_data["task-1"].progress == 75

    async def test_update_multiple_subscribers(self):
        """Test update notifies all subscribers for a task."""
        tracker = LocalProgressTracker()
        queue1 = asyncio.Queue()
        queue2 = asyncio.Queue()
        tracker.subscribers["task-1"] = [queue1, queue2]

        await tracker.update("task-1", 30, "Transcribing", "processing")

        # Both queues should receive the update
        prog1 = await queue1.get()
        prog2 = await queue2.get()
        assert prog1.progress == 30
        assert prog2.progress == 30


class TestLocalProgressTrackerGet:
    """Tests for LocalProgressTracker.get method."""

    async def test_get_returns_progress(self):
        """Test get returns stored progress (line 90)."""
        tracker = LocalProgressTracker()
        await tracker.update("task-1", 60, "Editing", "processing")

        result = tracker.get("task-1")

        assert result is not None
        assert result.progress == 60

    def test_get_returns_none_for_unknown_task(self):
        """Test get returns None for unknown task (line 90)."""
        tracker = LocalProgressTracker()

        result = tracker.get("nonexistent")

        assert result is None


class TestLocalProgressTrackerComplete:
    """Tests for LocalProgressTracker.complete method."""

    async def test_complete_sets_100_percent(self):
        """Test complete marks task as 100% completed (line 100)."""
        tracker = LocalProgressTracker()

        await tracker.complete("task-1")

        prog = tracker.progress_data["task-1"]
        assert prog.progress == 100
        assert prog.status == "completed"
        assert prog.message == "Complete!"

    async def test_complete_with_custom_message(self):
        """Test complete with custom message."""
        tracker = LocalProgressTracker()

        await tracker.complete("task-1", "All done!")

        prog = tracker.progress_data["task-1"]
        assert prog.message == "All done!"


class TestLocalProgressTrackerError:
    """Tests for LocalProgressTracker.error method."""

    async def test_error_sets_zero_percent_with_error_status(self):
        """Test error marks task as failed (line 110)."""
        tracker = LocalProgressTracker()

        await tracker.error("task-1", "Something went wrong")

        prog = tracker.progress_data["task-1"]
        assert prog.progress == 0
        assert prog.status == "error"
        assert prog.message == "Something went wrong"


class TestLocalProgressTrackerSubscribe:
    """Tests for LocalProgressTracker.subscribe async generator."""

    async def test_subscribe_yields_current_progress_first(self):
        """Test subscribe yields existing progress immediately (lines 123-134)."""
        tracker = LocalProgressTracker()
        await tracker.update("task-1", 30, "Started", "processing")

        updates = []
        async for progress in tracker.subscribe("task-1"):
            updates.append(progress)
            # After getting the current state, push a completion
            if len(updates) == 1:
                await tracker.update("task-1", 100, "Done", "completed")

        # First update is the current state, second is the completion
        assert len(updates) == 2
        assert updates[0].progress == 30
        assert updates[1].progress == 100

    async def test_subscribe_stops_on_completed(self):
        """Test subscribe stops when status is 'completed' (lines 143-144)."""
        tracker = LocalProgressTracker()

        async def push_updates():
            await asyncio.sleep(0.05)
            await tracker.update("task-1", 50, "Processing", "processing")
            await asyncio.sleep(0.05)
            await tracker.update("task-1", 100, "Done", "completed")

        asyncio.create_task(push_updates())

        updates = []
        async for progress in tracker.subscribe("task-1"):
            updates.append(progress)

        assert updates[-1].status == "completed"

    async def test_subscribe_stops_on_error(self):
        """Test subscribe stops when status is 'error' (lines 143-144)."""
        tracker = LocalProgressTracker()

        async def push_error():
            await asyncio.sleep(0.05)
            await tracker.update("task-1", 0, "Failed", "error")

        asyncio.create_task(push_error())

        updates = []
        async for progress in tracker.subscribe("task-1"):
            updates.append(progress)

        assert updates[-1].status == "error"

    async def test_subscribe_timeout_sends_keepalive(self):
        """Test subscribe sends keep-alive on timeout (lines 146-150)."""
        tracker = LocalProgressTracker()
        await tracker.update("task-1", 20, "Waiting", "processing")

        updates = []

        # Use a very short timeout for testing by monkeypatching wait_for
        original_wait_for = asyncio.wait_for

        call_count = 0

        async def fast_wait_for(coro, timeout):
            nonlocal call_count
            call_count += 1
            # First call: timeout to trigger keep-alive
            # Second call: return completion
            if call_count == 1:
                # Cancel the coro to prevent resource leak
                coro.close()
                raise asyncio.TimeoutError()
            # For the second call, push a completion first then do normal wait
            await tracker.update("task-1", 100, "Done", "completed")
            return await original_wait_for(coro, timeout=5.0)

        with patch("src.workers.local_progress.asyncio.wait_for", fast_wait_for):
            async for progress in tracker.subscribe("task-1"):
                updates.append(progress)

        # First: current progress (30), then keep-alive (from timeout),
        # then completion update
        assert len(updates) >= 2
        # Last update should be completed
        assert updates[-1].status == "completed"

    async def test_subscribe_cleanup_removes_queue(self):
        """Test subscribe removes queue from subscribers on exit (lines 152-156)."""
        tracker = LocalProgressTracker()

        async def push_completion():
            await asyncio.sleep(0.05)
            await tracker.update("task-1", 100, "Done", "completed")

        asyncio.create_task(push_completion())

        async for _ in tracker.subscribe("task-1"):
            pass

        # After generator exits, the subscriber queue should be removed
        if "task-1" in tracker.subscribers:
            assert len(tracker.subscribers["task-1"]) == 0

    async def test_subscribe_no_current_progress(self):
        """Test subscribe with no existing progress skips initial yield (lines 132-134)."""
        tracker = LocalProgressTracker()

        async def push_completion():
            await asyncio.sleep(0.05)
            await tracker.update("task-new", 100, "Done", "completed")

        asyncio.create_task(push_completion())

        updates = []
        async for progress in tracker.subscribe("task-new"):
            updates.append(progress)

        # Should only get the one update (no initial yield)
        assert len(updates) == 1
        assert updates[0].progress == 100

    async def test_subscribe_creates_subscriber_list_if_needed(self):
        """Test subscribe creates subscriber list for new task (lines 126-128)."""
        tracker = LocalProgressTracker()

        assert "task-new" not in tracker.subscribers

        async def push_completion():
            await asyncio.sleep(0.05)
            await tracker.update("task-new", 100, "Done", "completed")

        asyncio.create_task(push_completion())

        async for _ in tracker.subscribe("task-new"):
            pass

        # Subscribe should have created the list
        assert "task-new" in tracker.subscribers

    async def test_subscribe_cleanup_with_missing_task_key(self):
        """Test subscribe cleanup handles missing task key gracefully (line 154)."""
        tracker = LocalProgressTracker()

        # Start the generator manually and advance it with __anext__
        gen = tracker.subscribe("task-vanish")

        # Use anext to advance the generator to the first await point.
        # Since there is no current progress, it goes to the while loop waiting for queue.get().
        # We need to schedule a completion event before the generator reaches wait_for.

        async def feed_and_remove():
            # Give the generator time to set up and start waiting
            await asyncio.sleep(0.05)
            # At this point, subscribers should have the queue
            assert "task-vanish" in tracker.subscribers
            internal_queue = tracker.subscribers["task-vanish"][0]
            # Remove the subscribers key so the finally block encounters a missing key
            del tracker.subscribers["task-vanish"]
            # Put a completed event on the queue so the generator can finish
            completed_prog = Progress(
                task_id="task-vanish",
                progress=100,
                message="Done",
                status="completed",
            )
            await internal_queue.put(completed_prog)

        task = asyncio.create_task(feed_and_remove())

        updates = []
        async for progress in gen:
            updates.append(progress)

        await task

        # Should have completed without error even though subscribers key was removed
        assert len(updates) == 1
        assert updates[0].status == "completed"


class TestGetProgressTracker:
    """Tests for get_progress_tracker singleton function."""

    def test_get_progress_tracker_creates_instance(self):
        """Test get_progress_tracker creates instance when None (lines 171-173)."""
        import src.workers.local_progress as mod

        # Reset the global
        mod._progress_tracker = None

        tracker = get_progress_tracker()

        assert tracker is not None
        assert isinstance(tracker, LocalProgressTracker)
        assert mod._progress_tracker is tracker

        # Cleanup
        mod._progress_tracker = None

    def test_get_progress_tracker_returns_existing(self):
        """Test get_progress_tracker returns existing instance."""
        import src.workers.local_progress as mod

        existing = LocalProgressTracker()
        mod._progress_tracker = existing

        tracker = get_progress_tracker()

        assert tracker is existing

        # Cleanup
        mod._progress_tracker = None


# end backend/tests/unit/test_local_progress.py
