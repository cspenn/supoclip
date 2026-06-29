# start tests/integration/test_pipeline_e2e.py
"""End-to-end integration tests for the full video processing pipeline.

Covers:
- Local file pipeline happy path: DB task updated to completed with 100% progress
  and at least one GeneratedClip row persisted.
- Progress callback is invoked at the expected percentage milestones (0, 20, 40,
  50, 100) throughout the pipeline run.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.database import get_session
from src.models import GeneratedClip, Task
from src.services.video_service import ProcessingRequest, process_video

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_row(task_id: str, source_path: str) -> Task:
    """Return an unsaved Task ORM instance with status='pending'."""
    return Task(
        id=task_id,
        source_url=source_path,
        source_type="upload",
        status="pending",
        progress=0,
    )


# ---------------------------------------------------------------------------
# Test 1 — Local file happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_file_pipeline_happy_path(
    test_db: None,
    mock_analyze,
    tmp_path: Path,
) -> None:
    """Full pipeline runs to completion for a local video file.

    Verifies:
    - ProcessingResult.error is None.
    - Task row in DB has status='completed' and progress=100.
    - At least one GeneratedClip row exists in the DB for the task.
    """
    # Arrange — create a real (empty) file so the pipeline's existence check passes.
    fake_video = tmp_path / "fake.mp4"
    fake_video.write_bytes(b"\x00" * 64)

    task_id = "integration-test-task-001"
    async with get_session() as session:
        session.add(_make_task_row(task_id, str(fake_video)))

    word_list = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 1.0},
    ]

    with (
        patch(
            "src.services.video_service.asyncio.to_thread",
            new=AsyncMock(return_value=word_list),
        ),
        patch(
            "src.pipeline.transcribe.format_transcript_text",
            return_value="Hello world",
        ),
        patch(
            "src.pipeline.clip.generate_clip",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.video_service._generate_clips_concurrently",
            new=AsyncMock(
                return_value=[
                    (
                        tmp_path / f"{task_id}_clip_01.mp4",
                        mock_analyze.return_value[0],
                    )
                ]
            ),
        ),
        patch(
            "src.services.video_service._generate_thumbnail",
            new=AsyncMock(return_value=None),
        ),
    ):
        request = ProcessingRequest(
            source=str(fake_video),
            task_id=task_id,
        )
        result = await process_video(request)

    # Assert — no pipeline error
    assert result.error is None, f"Expected no error, got: {result.error}"

    # Assert — DB task status
    async with get_session() as session:
        task = await session.get(Task, task_id)
        assert task is not None, "Task row not found in DB"
        assert task.status == "completed"
        assert task.progress == 100

    # Assert — GeneratedClip rows created
    async with get_session() as session:
        rows = (await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == task_id))).scalars().all()
    assert len(rows) >= 1, "Expected at least one GeneratedClip row"


# ---------------------------------------------------------------------------
# Test 2 — Progress callback milestones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_callback_milestones(
    test_db: None,
    mock_analyze,
    tmp_path: Path,
) -> None:
    """Progress callback is invoked at all expected percentage milestones.

    Verifies that 0%, 20%, 40%, 50%, and 100% are all present in the
    recorded (pct, msg) tuples.
    """
    fake_video = tmp_path / "fake.mp4"
    fake_video.write_bytes(b"\x00" * 64)

    task_id = "integration-test-task-002"
    async with get_session() as session:
        session.add(_make_task_row(task_id, str(fake_video)))

    word_list = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 1.0},
    ]

    recorded_calls: list[tuple[int, str]] = []

    def _progress(pct: int, msg: str) -> None:
        recorded_calls.append((pct, msg))

    with (
        patch(
            "src.services.video_service.asyncio.to_thread",
            new=AsyncMock(return_value=word_list),
        ),
        patch(
            "src.pipeline.transcribe.format_transcript_text",
            return_value="Hello world",
        ),
        patch(
            "src.pipeline.clip.generate_clip",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.services.video_service._generate_clips_concurrently",
            new=AsyncMock(
                return_value=[
                    (
                        tmp_path / f"{task_id}_clip_01.mp4",
                        mock_analyze.return_value[0],
                    )
                ]
            ),
        ),
        patch(
            "src.services.video_service._generate_thumbnail",
            new=AsyncMock(return_value=None),
        ),
    ):
        request = ProcessingRequest(
            source=str(fake_video),
            task_id=task_id,
        )
        result = await process_video(request, progress_callback=_progress)

    assert result.error is None, f"Expected no error, got: {result.error}"

    recorded_pcts = {pct for pct, _ in recorded_calls}
    expected_milestones = {0, 20, 40, 50, 100}
    missing = expected_milestones - recorded_pcts
    assert not missing, f"Progress milestones not reported: {missing}. Recorded: {sorted(recorded_pcts)}"


# end tests/integration/test_pipeline_e2e.py
