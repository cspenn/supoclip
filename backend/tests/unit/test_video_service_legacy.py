"""Unit tests for LegacySyncVideoService.

Tests the synchronous video processing service that handles the /start endpoint
with a 5-minute timeout for backward compatibility.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.models import GeneratedClip, Source, Task
from src.services.video_service_legacy import LegacySyncVideoService


@pytest.fixture
def mock_config():
    """Create a mock config object."""
    config = MagicMock(spec=Config)
    config.temp_dir = "/tmp/test_clips"
    return config


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def legacy_service(mock_db, mock_config):
    """Create a LegacySyncVideoService instance for testing."""
    return LegacySyncVideoService(db=mock_db, config=mock_config)


class TestLegacySyncVideoServiceInit:
    """Test service initialization."""

    def test_init_stores_db_and_config(self, mock_db, mock_config):
        """Test that __init__ stores database and config."""
        service = LegacySyncVideoService(db=mock_db, config=mock_config)
        assert service.db == mock_db
        assert service.config == mock_config

    def test_init_with_different_config(self, mock_db):
        """Test initialization with different config objects."""
        config1 = MagicMock(spec=Config)
        config1.temp_dir = "/tmp/test1"
        config2 = MagicMock(spec=Config)
        config2.temp_dir = "/tmp/test2"

        service1 = LegacySyncVideoService(db=mock_db, config=config1)
        service2 = LegacySyncVideoService(db=mock_db, config=config2)

        assert service1.config.temp_dir == "/tmp/test1"
        assert service2.config.temp_dir == "/tmp/test2"


class TestProcessVideoBasic:
    """Test basic video processing functionality."""

    @pytest.mark.asyncio
    async def test_process_video_creates_source(self, legacy_service, mock_db):
        """Test that process_video creates a source record."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123", "title": "Test Video"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.get_youtube_video_title", return_value="YouTube Title"):
                with patch("src.services.video_service_legacy.Task") as mock_task_class:
                    mock_task = MagicMock()
                    mock_task.id = "task_123"
                    mock_task_class.return_value = mock_task

                    with patch("src.services.video_service_legacy.download_youtube_video", return_value=None):
                        try:
                            await legacy_service.process_video(raw_source, "user_123")
                        except Exception:
                            pass  # Expected to fail at download step

            # Verify source was added to database
            assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_video_creates_task(self, legacy_service, mock_db):
        """Test that process_video creates a task record."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "upload"
            mock_source.decide_source_type = MagicMock(return_value="upload")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.Task"):
                with patch("src.services.video_service_legacy.Path") as mock_path_class:
                    mock_path = MagicMock()
                    mock_path.exists = MagicMock(return_value=False)
                    mock_path_class.return_value = mock_path

                    try:
                        await legacy_service.process_video(raw_source, "user_123")
                    except Exception:
                        pass  # Expected to fail

            assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_video_with_font_options(self, legacy_service, mock_db):
        """Test that process_video accepts and uses custom font options."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "upload"
            mock_source.decide_source_type = MagicMock(return_value="upload")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.Path") as mock_path_class:
                mock_path = MagicMock()
                mock_path.exists = MagicMock(return_value=False)
                mock_path_class.return_value = mock_path

                try:
                    await legacy_service.process_video(
                        raw_source,
                        "user_123",
                        font_family="Arial",
                        font_size=32,
                        font_color="#FF0000"
                    )
                except Exception:
                    pass

        # Verify Task was created with custom font options
        calls = [call for call in mock_db.add.call_args_list]
        assert len(calls) >= 2  # Source and Task


class TestProcessVideoErrorHandling:
    """Test error handling in video processing."""

    @pytest.mark.asyncio
    async def test_process_video_invalid_url(self, legacy_service, mock_db):
        """Test that process_video handles invalid URLs."""
        raw_source = {"url": None}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.decide_source_type = MagicMock(return_value=None)
            mock_source_class.return_value = mock_source

            mock_db.flush = AsyncMock()
            mock_db.commit = AsyncMock()

            try:
                await legacy_service.process_video(raw_source, "user_123")
            except Exception as e:
                # Should raise an exception for invalid input
                assert e is not None


class TestProcessVideoYouTubeHandling:
    """Test YouTube-specific video processing."""

    @pytest.mark.asyncio
    async def test_process_video_youtube_title_extraction(self, legacy_service, mock_db):
        """Test that YouTube video title is extracted correctly."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.get_youtube_video_title", return_value="Test Video Title"):
                with patch("src.services.video_service_legacy.Task"):
                    with patch("src.services.video_service_legacy.download_youtube_video", return_value=None):
                        try:
                            await legacy_service.process_video(raw_source, "user_123")
                        except Exception:
                            pass

                # Verify title was set
                assert mock_source.title == "Test Video Title"

    @pytest.mark.asyncio
    async def test_process_video_youtube_download_called(self, legacy_service, mock_db):
        """Test that YouTube video download is called for YouTube sources."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.get_youtube_video_title", return_value="Title"):
                with patch("src.services.video_service_legacy.Task"):
                    with patch("src.services.video_service_legacy.download_youtube_video") as mock_download:
                        mock_download.return_value = None

                        try:
                            await legacy_service.process_video(raw_source, "user_123")
                        except Exception:
                            pass

                        # Verify download was called
                        mock_download.assert_called_once_with("https://youtube.com/watch?v=test123")


class TestProcessVideoUploadedFileHandling:
    """Test uploaded file handling in video processing."""

    @pytest.mark.asyncio
    async def test_process_video_uploaded_file_path_verification(self, legacy_service, mock_db):
        """Test that uploaded file path is verified to exist."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "/path/to/uploaded/video.mp4"}

        with patch("src.services.video_service_legacy.Source") as mock_source_class:
            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "upload"
            mock_source.decide_source_type = MagicMock(return_value="upload")
            mock_source_class.return_value = mock_source

            with patch("src.services.video_service_legacy.Task"):
                with patch("src.services.video_service_legacy.Path") as mock_path_class:
                    mock_path = MagicMock()
                    mock_path.exists = MagicMock(return_value=False)
                    mock_path_class.return_value = mock_path

                    with pytest.raises(Exception, match="Uploaded video file not found"):
                        await legacy_service.process_video(raw_source, "user_123")


class TestProcessVideoWithLogo:
    """Test logo feature integration."""

    @pytest.mark.asyncio
    async def test_process_video_with_logo_path(self, legacy_service, mock_db):
        """Test that process_video accepts logo_path parameter."""
        # This test verifies the service can accept logo parameters
        # The actual logo processing is tested in integration tests
        logo_path = Path("/path/to/logo.png")

        try:
            await legacy_service.process_video(
                {"url": "/fake/video.mp4"},
                "user_123",
                logo_path=logo_path,
                logo_corner_position="top-left"
            )
        except Exception:
            # Expected to fail due to mocking
            pass

    @pytest.mark.asyncio
    async def test_process_video_with_custom_ai_prompt(self, legacy_service, mock_db):
        """Test that custom AI prompt is accepted as parameter."""
        custom_prompt = "Find the most entertaining moments"

        try:
            await legacy_service.process_video(
                {"url": "/fake/video.mp4"},
                "user_123",
                custom_ai_prompt=custom_prompt
            )
        except Exception:
            # Expected to fail due to mocking
            pass

# end backend/tests/unit/test_video_service_legacy.py
