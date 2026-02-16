"""Unit tests for AsyncVideoProcessingService.

Tests the asynchronous video processing service that handles the /start-with-progress
endpoint with SSE progress tracking and unlimited processing time.
Covers all methods and branches for 100% line coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.services.video_service_async import (
    AsyncVideoProcessingService,
    MIN_CLIP_FILE_SIZE_BYTES,
)


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
def async_service(mock_db, mock_config):
    """Create an AsyncVideoProcessingService instance for testing."""
    return AsyncVideoProcessingService(db=mock_db, config=mock_config)


def _make_async_session_context():
    """Create a properly configured mock for AsyncSessionLocal context manager."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


class TestAsyncVideoServiceInit:
    """Test service initialization."""

    def test_init_stores_db_and_config(self, mock_db, mock_config):
        """Test that __init__ stores database and config."""
        service = AsyncVideoProcessingService(db=mock_db, config=mock_config)
        assert service.db == mock_db
        assert service.config == mock_config


class TestCreateTask:
    """Test task creation functionality."""

    @pytest.mark.asyncio
    async def test_create_task_youtube_with_title(self, async_service, mock_db):
        """Test create_task with YouTube URL that returns a title."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.get_youtube_video_title",
                   return_value="Test Title") as mock_title, \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_123"
            mock_task_class.return_value = mock_task

            task_id = await async_service.create_task(raw_source, "user_123")

            assert task_id == "task_123"
            assert mock_source.title == "Test Title"
            mock_db.add.assert_called()
            mock_db.flush.assert_called()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_task_youtube_title_none(self, async_service, mock_db):
        """Test create_task when YouTube title returns None (lines 95-98)."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.get_youtube_video_title",
                   return_value=None), \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_123"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_456"
            mock_task_class.return_value = mock_task

            task_id = await async_service.create_task(raw_source, "user_123")

            assert task_id == "task_456"
            # When title is None, should default to "YouTube Video"
            assert mock_source.title == "YouTube Video"

    @pytest.mark.asyncio
    async def test_create_task_youtube_title_exception(self, async_service, mock_db):
        """Test create_task when get_youtube_video_title raises exception (lines 100-104)."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.get_youtube_video_title",
                   side_effect=RuntimeError("API error")), \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_789"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_789"
            mock_task_class.return_value = mock_task

            task_id = await async_service.create_task(raw_source, "user_123")

            assert task_id == "task_789"
            # When title retrieval raises, should default to "YouTube Video"
            assert mock_source.title == "YouTube Video"

    @pytest.mark.asyncio
    async def test_create_task_upload_source(self, async_service, mock_db):
        """Test create_task with non-YouTube (upload) source (lines 105-106)."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4", "title": "My Upload"}

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_upload"
            mock_source.type = "video_url"
            mock_source.decide_source_type = MagicMock(return_value="video_url")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_upload"
            mock_task_class.return_value = mock_task

            task_id = await async_service.create_task(raw_source, "user_123")

            assert task_id == "task_upload"
            assert mock_source.title == "My Upload"

    @pytest.mark.asyncio
    async def test_create_task_upload_default_title(self, async_service, mock_db):
        """Test create_task with upload source and no title defaults to 'Uploaded Video'."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "/path/to/video.mp4"}  # No "title" key

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_upload2"
            mock_source.type = "video_url"
            mock_source.decide_source_type = MagicMock(return_value="video_url")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_upload2"
            mock_task_class.return_value = mock_task

            task_id = await async_service.create_task(raw_source, "user_123")

            assert task_id == "task_upload2"
            assert mock_source.title == "Uploaded Video"

    @pytest.mark.asyncio
    async def test_create_task_with_custom_font_options(self, async_service, mock_db):
        """Test create_task with custom font options."""
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=test123"}

        with patch("src.services.video_service_async.Source") as mock_source_class, \
             patch("src.services.video_service_async.get_youtube_video_title",
                   return_value="Title"), \
             patch("src.services.video_service_async.Task") as mock_task_class:

            mock_source = MagicMock()
            mock_source.id = "src_font"
            mock_source.type = "youtube"
            mock_source.decide_source_type = MagicMock(return_value="youtube")
            mock_source_class.return_value = mock_source

            mock_task = MagicMock()
            mock_task.id = "task_font"
            mock_task_class.return_value = mock_task

            await async_service.create_task(
                raw_source, "user_123",
                font_family="Arial", font_size=32, font_color="#FF0000",
            )

            mock_task_class.assert_called_once()
            call_kwargs = mock_task_class.call_args[1]
            assert call_kwargs["font_family"] == "Arial"
            assert call_kwargs["font_size"] == 32
            assert call_kwargs["font_color"] == "#FF0000"


class TestProcessVideoAsync:
    """Test process_video_async method - the full async processing pipeline."""

    @pytest.mark.asyncio
    async def test_process_video_async_success_with_valid_clips(self, async_service, tmp_path):
        """Test full success path: process, validate clips, save to DB (lines 187-260)."""
        async_service._update_task_status = AsyncMock()

        # Create valid clip files
        clip1_path = tmp_path / "clip1.mp4"
        clip1_path.write_bytes(b"x" * 2000)  # > MIN_CLIP_FILE_SIZE_BYTES
        clip2_path = tmp_path / "clip2.mp4"
        clip2_path.write_bytes(b"y" * 3000)

        raw_source = {"url": "https://youtube.com/watch?v=abc"}

        # Mock source data returned from DB
        mock_source_data = MagicMock()
        mock_source_data.type = "youtube"

        # Mock DB sessions
        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = mock_source_data
        source_session.execute = AsyncMock(return_value=source_result)

        clips_session = _make_async_session_context()
        clips_session.execute = AsyncMock()
        clips_session.commit = AsyncMock()
        clips_session.flush = AsyncMock()

        # Track which session is returned for each call
        session_calls = [source_session, clips_session]
        call_index = {"i": 0}

        def get_session():
            idx = call_index["i"]
            call_index["i"] += 1
            return session_calls[idx]

        # Mock VideoService.process_video_complete result
        process_result = {
            "clips": [
                {
                    "filename": "clip1.mp4",
                    "path": str(clip1_path),
                    "start_time": "00:10",
                    "end_time": "00:30",
                    "duration": 20.0,
                    "text": "Hello world",
                    "relevance_score": 0.9,
                    "reasoning": "Good",
                },
                {
                    "filename": "clip2.mp4",
                    "path": str(clip2_path),
                    "start_time": "01:00",
                    "end_time": "01:20",
                    "duration": 20.0,
                    "text": "More content",
                    "relevance_score": 0.85,
                    "reasoning": "Also good",
                },
            ],
            "segments": [],
            "summary": None,
            "key_topics": None,
        }

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    side_effect=get_session), \
             patch("src.services.video_service_async.VideoService") as mock_vs_cls, \
             patch("src.services.video_service_async.GeneratedClip") as mock_clip_cls:

            mock_vs_cls.process_video_complete = AsyncMock(return_value=process_result)

            # Make each GeneratedClip mock have a unique id
            clip_mock_1 = MagicMock()
            clip_mock_1.id = "clip-id-1"
            clip_mock_2 = MagicMock()
            clip_mock_2.id = "clip-id-2"
            mock_clip_cls.side_effect = [clip_mock_1, clip_mock_2]

            await async_service.process_video_async(
                task_id="task-100",
                raw_source=raw_source,
                user_id="user-1",
                font_family="Arial",
                font_size=32,
                font_color="#FF0000",
                clip_min_length=10,
                clip_max_length=45,
                custom_ai_prompt="Custom prompt",
                logo_path="/path/logo.png",
                logo_corner_position="top-right",
                output_resolution="1080p",
                subtitle_style={"color": "white"},
                subtitle_position={"y": 0.75},
            )

        # Verify processing status was set
        processing_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "processing"
        ]
        assert len(processing_calls) >= 1

        # Verify completed status was set
        completed_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "completed"
        ]
        assert len(completed_calls) == 1

    @pytest.mark.asyncio
    async def test_process_video_async_clip_file_not_exist(self, async_service, tmp_path):
        """Test clip validation: file does not exist (lines 219-223)."""
        async_service._update_task_status = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=abc"}

        mock_source_data = MagicMock()
        mock_source_data.type = "youtube"

        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = mock_source_data
        source_session.execute = AsyncMock(return_value=source_result)

        clips_session = _make_async_session_context()
        clips_session.execute = AsyncMock()
        clips_session.commit = AsyncMock()

        session_calls = [source_session, clips_session]
        call_idx = {"i": 0}

        def get_session():
            idx = call_idx["i"]
            call_idx["i"] += 1
            return session_calls[idx]

        process_result = {
            "clips": [
                {
                    "filename": "nonexistent.mp4",
                    "path": str(tmp_path / "nonexistent.mp4"),
                    "start_time": "00:10",
                    "end_time": "00:30",
                    "duration": 20.0,
                    "text": "Text",
                    "relevance_score": 0.9,
                    "reasoning": "Good",
                },
            ],
            "segments": [],
        }

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    side_effect=get_session), \
             patch("src.services.video_service_async.VideoService") as mock_vs_cls:

            mock_vs_cls.process_video_complete = AsyncMock(return_value=process_result)

            await async_service.process_video_async(
                task_id="task-200", raw_source=raw_source, user_id="user-1",
            )

        # No valid clips -> error status
        error_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "error"
        ]
        assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_process_video_async_clip_file_too_small(self, async_service, tmp_path):
        """Test clip validation: file too small (lines 226-230)."""
        async_service._update_task_status = AsyncMock()

        # Create a too-small clip file
        small_clip = tmp_path / "small.mp4"
        small_clip.write_bytes(b"x" * 10)  # Only 10 bytes, below MIN_CLIP_FILE_SIZE_BYTES

        raw_source = {"url": "https://youtube.com/watch?v=abc"}

        mock_source_data = MagicMock()
        mock_source_data.type = "youtube"

        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = mock_source_data
        source_session.execute = AsyncMock(return_value=source_result)

        clips_session = _make_async_session_context()
        clips_session.execute = AsyncMock()
        clips_session.commit = AsyncMock()

        session_calls = [source_session, clips_session]
        call_idx = {"i": 0}

        def get_session():
            idx = call_idx["i"]
            call_idx["i"] += 1
            return session_calls[idx]

        process_result = {
            "clips": [
                {
                    "filename": "small.mp4",
                    "path": str(small_clip),
                    "start_time": "00:10",
                    "end_time": "00:30",
                    "duration": 20.0,
                    "text": "Text",
                    "relevance_score": 0.9,
                    "reasoning": "Good",
                },
            ],
            "segments": [],
        }

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    side_effect=get_session), \
             patch("src.services.video_service_async.VideoService") as mock_vs_cls:

            mock_vs_cls.process_video_complete = AsyncMock(return_value=process_result)

            await async_service.process_video_async(
                task_id="task-300", raw_source=raw_source, user_id="user-1",
            )

        # No valid clips -> error status
        error_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "error"
        ]
        assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_process_video_async_source_not_found(self, async_service):
        """Test when source is not found in database (line 184)."""
        async_service._update_task_status = AsyncMock()

        raw_source = {"url": "/video.mp4"}

        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = None  # Source not found
        source_session.execute = AsyncMock(return_value=source_result)

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    return_value=source_session):

            await async_service.process_video_async(
                task_id="task-404", raw_source=raw_source, user_id="user-1",
            )

        # Should mark as error
        error_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "error"
        ]
        assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_process_video_async_processing_exception(self, async_service):
        """Test error handling when video processing raises exception (lines 271-275)."""
        async_service._update_task_status = AsyncMock()

        raw_source = {"url": "https://youtube.com/watch?v=abc"}

        mock_source_data = MagicMock()
        mock_source_data.type = "youtube"

        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = mock_source_data
        source_session.execute = AsyncMock(return_value=source_result)

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    return_value=source_session), \
             patch("src.services.video_service_async.VideoService") as mock_vs_cls:

            mock_vs_cls.process_video_complete = AsyncMock(
                side_effect=RuntimeError("Processing exploded")
            )

            await async_service.process_video_async(
                task_id="task-500", raw_source=raw_source, user_id="user-1",
            )

        # Verify error status with error message
        error_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "error"
        ]
        assert len(error_calls) >= 1
        # Verify error message is passed
        error_call = error_calls[-1]
        assert "Processing exploded" in str(error_call)

    @pytest.mark.asyncio
    async def test_process_video_async_no_valid_clips_produced(self, async_service, tmp_path):
        """Test when no valid clips are produced - all skipped (lines 261-269)."""
        async_service._update_task_status = AsyncMock()

        # Create a clip file that doesn't exist
        raw_source = {"url": "https://youtube.com/watch?v=abc"}

        mock_source_data = MagicMock()
        mock_source_data.type = "youtube"

        source_session = _make_async_session_context()
        source_result = MagicMock()
        source_result.fetchone.return_value = mock_source_data
        source_session.execute = AsyncMock(return_value=source_result)

        clips_session = _make_async_session_context()
        clips_session.execute = AsyncMock()
        clips_session.commit = AsyncMock()

        session_calls = [source_session, clips_session]
        call_idx = {"i": 0}

        def get_session():
            idx = call_idx["i"]
            call_idx["i"] += 1
            return session_calls[idx]

        # All clips have non-existent paths
        process_result = {
            "clips": [
                {
                    "filename": "gone1.mp4",
                    "path": "/nonexistent/gone1.mp4",
                    "start_time": "00:10",
                    "end_time": "00:30",
                    "duration": 20.0,
                    "text": "Text",
                    "relevance_score": 0.9,
                    "reasoning": "Good",
                },
            ],
            "segments": [],
        }

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    side_effect=get_session), \
             patch("src.services.video_service_async.VideoService") as mock_vs_cls:

            mock_vs_cls.process_video_complete = AsyncMock(return_value=process_result)

            await async_service.process_video_async(
                task_id="task-600", raw_source=raw_source, user_id="user-1",
            )

        # Verify error status with specific message about no valid clips
        error_calls = [
            call for call in async_service._update_task_status.call_args_list
            if call[0][1] == "error"
        ]
        assert len(error_calls) >= 1


class TestUpdateTaskStatus:
    """Test _update_task_status method."""

    @pytest.mark.asyncio
    async def test_update_task_status_without_error_message(self, async_service):
        """Test status update without error message (lines 296-300)."""
        mock_session = _make_async_session_context()

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    return_value=mock_session):
            await async_service._update_task_status("task_123", "completed")

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task_status_with_error_message(self, async_service):
        """Test status update with error message (lines 288-295)."""
        mock_session = _make_async_session_context()

        with patch("src.services.video_service_async.AsyncSessionLocal",
                    return_value=mock_session):
            await async_service._update_task_status(
                "task_123", "error", error_message="Something went wrong"
            )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify the query included error_msg parameter
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["error_msg"] == "Something went wrong"
        assert params["status"] == "error"

    @pytest.mark.asyncio
    async def test_update_task_status_different_statuses(self, async_service):
        """Test that different statuses can be set."""
        for status in ["processing", "completed", "error", "queued"]:
            mock_session = _make_async_session_context()

            with patch("src.services.video_service_async.AsyncSessionLocal",
                        return_value=mock_session):
                await async_service._update_task_status("task_123", status)

            mock_session.execute.assert_called()


# end backend/tests/unit/test_video_service_async.py
