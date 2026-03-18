# start tests/integration/test_pipeline_failures.py
"""Integration tests for SupoClip pipeline failure modes.

Covers end-to-end failure scenarios using a real in-memory SQLite database:
- Local file not found
- Transcription failure (RuntimeError)
- AI analysis failure (AnalysisError)
- All clips fail to generate (ClipGenerationError)

Each test verifies that:
1. ProcessingResult.error is set (not None) with an appropriate message.
2. The Task row in the database is marked as 'failed'.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.database import get_session
from src.models import Task
from src.pipeline.analyze import AnalysisError, TranscriptSegment
from src.services.video_service import ProcessingRequest, process_video

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_task(task_id: str) -> None:
    """Insert a minimal Task row so _update_task_status can find it."""
    async with get_session() as session:
        task = Task(
            id=task_id,
            source_url="test-source",
            source_type="upload",
            status="pending",
            progress=0,
        )
        session.add(task)


async def _get_task_status(task_id: str) -> str | None:
    """Return the status field of the Task row with the given ID."""
    async with get_session() as session:
        task = await session.get(Task, task_id)
        return task.status if task is not None else None


def _make_request(source: str, task_id: str) -> ProcessingRequest:
    """Build a minimal ProcessingRequest for test use."""
    return ProcessingRequest(source=source, task_id=task_id)


def _make_segment(
    start: float = 0.0,
    end: float = 30.0,
    text: str = "Great viral content worth clipping.",
    score: float = 0.9,
    title: str = "Test Clip",
) -> TranscriptSegment:
    """Return a TranscriptSegment with sensible defaults."""
    return TranscriptSegment(start_time=start, end_time=end, text=text, score=score, title=title)


# ---------------------------------------------------------------------------
# Test 1: Local file not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_file_not_found(test_db: None) -> None:  # noqa: ARG001
    """process_video returns an error when the source file does not exist.

    The pipeline should detect the missing file before attempting transcription
    and mark the Task as 'failed' in the database.
    """
    task_id = str(uuid.uuid4())
    await _create_task(task_id)

    request = _make_request(source="/nonexistent/file.mp4", task_id=task_id)
    result = await process_video(request)

    assert result.error is not None, "Expected an error for missing file"
    assert "not found" in result.error.lower(), f"Expected 'not found' in error message, got: {result.error!r}"
    assert result.clips == []

    status = await _get_task_status(task_id)
    assert status == "failed", f"Expected task status 'failed', got {status!r}"


# ---------------------------------------------------------------------------
# Test 2: Transcription failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcription_failure(test_db: None, tmp_path: Path) -> None:  # noqa: ARG001
    """process_video propagates RuntimeError from transcribe_video.

    When transcription raises an exception the pipeline must surface the
    error message and mark the Task as 'failed'.
    """
    task_id = str(uuid.uuid4())
    await _create_task(task_id)

    # Create a real (empty) file so the file-existence check passes.
    source_file = tmp_path / "sample.mp4"
    source_file.write_bytes(b"")

    with patch(
        "src.pipeline.transcribe.transcribe_video",
        side_effect=RuntimeError("transcribe failed"),
    ):
        request = _make_request(source=str(source_file), task_id=task_id)
        result = await process_video(request)

    assert result.error is not None, "Expected an error when transcription fails"
    assert "transcribe failed" in result.error, f"Expected 'transcribe failed' in error, got: {result.error!r}"
    assert result.clips == []

    status = await _get_task_status(task_id)
    assert status == "failed", f"Expected task status 'failed', got {status!r}"


# ---------------------------------------------------------------------------
# Test 3: AI analysis failure (AnalysisError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_failure(test_db: None, tmp_path: Path) -> None:  # noqa: ARG001
    """process_video propagates AnalysisError from analyze_transcript.

    When the AI analysis step raises AnalysisError the pipeline must surface
    the error message and mark the Task as 'failed'.
    """
    task_id = str(uuid.uuid4())
    await _create_task(task_id)

    source_file = tmp_path / "sample.mp4"
    source_file.write_bytes(b"")

    word_list = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 1.0},
    ]

    with (
        patch(
            "src.pipeline.transcribe.transcribe_video",
            return_value=word_list,
        ),
        patch(
            "src.pipeline.transcribe.format_transcript_text",
            return_value="Hello world",
        ),
        patch(
            "src.services.video_service.analyze_transcript",
            new_callable=AsyncMock,
            side_effect=AnalysisError("too short"),
        ),
    ):
        request = _make_request(source=str(source_file), task_id=task_id)
        result = await process_video(request)

    assert result.error is not None, "Expected an error when analysis fails"
    assert "too short" in result.error, f"Expected 'too short' in error, got: {result.error!r}"
    assert result.clips == []

    status = await _get_task_status(task_id)
    assert status == "failed", f"Expected task status 'failed', got {status!r}"


# ---------------------------------------------------------------------------
# Test 4: All clips fail to generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_clips_fail(test_db: None, tmp_path: Path) -> None:  # noqa: ARG001
    """process_video fails when every clip generation raises ClipGenerationError.

    Transcription and analysis succeed but every call to generate_clip raises
    ClipGenerationError.  The orchestrator must detect zero successful clips,
    set ProcessingResult.error, and mark the Task as 'failed'.
    """
    task_id = str(uuid.uuid4())
    await _create_task(task_id)

    source_file = tmp_path / "sample.mp4"
    source_file.write_bytes(b"")

    word_list = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 1.0},
    ]
    segments = [_make_segment()]

    from src.pipeline.clip import ClipGenerationError

    with (
        patch(
            "src.pipeline.transcribe.transcribe_video",
            return_value=word_list,
        ),
        patch(
            "src.pipeline.transcribe.format_transcript_text",
            return_value="Hello world",
        ),
        patch(
            "src.services.video_service.analyze_transcript",
            new_callable=AsyncMock,
            return_value=segments,
        ),
        patch(
            "src.pipeline.clip.generate_clip",
            new_callable=AsyncMock,
            side_effect=ClipGenerationError("ffmpeg returned non-zero"),
        ),
    ):
        request = _make_request(source=str(source_file), task_id=task_id)
        result = await process_video(request)

    assert result.error is not None, "Expected error when all clips fail"
    assert result.clips == []

    status = await _get_task_status(task_id)
    assert status == "failed", f"Expected task status 'failed', got {status!r}"


# end tests/integration/test_pipeline_failures.py
