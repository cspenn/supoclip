# start tests/integration/conftest.py
"""Shared fixtures for SupoClip integration tests."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

import src.database as db_module
from src.database import init_db


@pytest_asyncio.fixture()
async def test_db(tmp_path: Path) -> AsyncGenerator[None, None]:
    """Provide a fresh in-memory SQLite database for each test."""
    # Reset module-level DB state
    db_module._engine = None
    db_module._session_factory = None

    db_url = "sqlite+aiosqlite:///:memory:"
    await init_db(db_url)
    yield
    # Teardown
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


@pytest.fixture()
def mock_ffmpeg():
    """Mock ffmpeg subprocess calls to avoid real video processing."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        yield mock_run


@pytest.fixture()
def mock_yt_dlp():
    """Mock yt-dlp to avoid real YouTube downloads."""
    with patch("src.pipeline.download.yt_dlp") as mock_ydl:
        mock_ydl.YoutubeDL.return_value.__enter__ = MagicMock(return_value=mock_ydl.YoutubeDL.return_value)
        mock_ydl.YoutubeDL.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.YoutubeDL.return_value.download = MagicMock()
        yield mock_ydl


@pytest.fixture()
def mock_transcribe():
    """Mock parakeet-mlx transcription to avoid real audio processing."""
    word_list = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.6, "end": 1.0},
    ]
    with patch("src.pipeline.transcribe.transcribe_video") as mock_tv:
        mock_tv.return_value = word_list
        with patch("src.pipeline.transcribe.format_transcript_text") as mock_fmt:
            mock_fmt.return_value = "Hello world"
            yield mock_tv, mock_fmt


@pytest.fixture()
def mock_analyze():
    """Mock AI analysis to return deterministic segments."""
    from src.pipeline.analyze import TranscriptSegment

    segments = [
        TranscriptSegment(
            start_time=0.0,
            end_time=30.0,
            text="Hello world",
            score=0.9,
            title="Test Clip",
        )
    ]
    with patch("src.services.video_service.analyze_transcript") as mock_at:
        mock_at.return_value = segments
        yield mock_at


# end tests/integration/conftest.py
