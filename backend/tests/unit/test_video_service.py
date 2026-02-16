"""Unit tests for VideoService.

Tests the video processing service that handles video download, transcription,
AI analysis, clip creation, and the complete processing pipeline.
Covers all methods and branches for 100% line coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from typing import Any

from src.services.video_service import (
    VideoService,
    VideoDownloadError,
    VideoNotFoundError,
    VideoProcessingResponse,
)


# --- Custom Exception Tests ---

class TestCustomExceptions:
    """Test custom exception classes."""

    def test_video_download_error(self):
        """Test VideoDownloadError can be raised."""
        with pytest.raises(VideoDownloadError):
            raise VideoDownloadError("Download failed")

    def test_video_not_found_error(self):
        """Test VideoNotFoundError can be raised."""
        with pytest.raises(VideoNotFoundError):
            raise VideoNotFoundError("Not found")


# --- VideoProcessingResponse Tests ---

class TestVideoProcessingResponse:
    """Test VideoProcessingResponse helper class."""

    def test_build_response(self):
        """Test building a response dictionary."""
        segments = [{"start": 0, "end": 10}]
        clips = [{"filename": "clip1.mp4"}]
        relevant_parts = MagicMock()
        relevant_parts.summary = "A summary"
        relevant_parts.key_topics = ["topic1"]

        result = VideoProcessingResponse.build_response(segments, clips, relevant_parts)
        assert result["segments"] == segments
        assert result["clips"] == clips
        assert result["summary"] == "A summary"
        assert result["key_topics"] == ["topic1"]

    def test_build_response_no_relevant_parts(self):
        """Test building response when relevant_parts is None."""
        result = VideoProcessingResponse.build_response([], [], None)
        assert result["summary"] is None
        assert result["key_topics"] is None

    def test_segments_to_json(self):
        """Test converting segment objects to JSON."""
        mock_segment = MagicMock()
        mock_segment.start_time = "00:10"
        mock_segment.end_time = "00:30"
        mock_segment.text = "Hello world"
        mock_segment.relevance_score = 0.9
        mock_segment.reasoning = "Good"

        result = VideoProcessingResponse.segments_to_json([mock_segment])
        assert len(result) == 1
        assert result[0]["start_time"] == "00:10"
        assert result[0]["end_time"] == "00:30"
        assert result[0]["text"] == "Hello world"
        assert result[0]["relevance_score"] == 0.9
        assert result[0]["reasoning"] == "Good"


# --- VideoService._get_video_path Tests ---

class TestGetVideoPath:
    """Test _get_video_path static method."""

    @pytest.mark.asyncio
    async def test_get_video_path_youtube_success(self):
        """Test downloading YouTube video (lines 80-84)."""
        with patch.object(VideoService, "download_video",
                          new_callable=AsyncMock, return_value=Path("/tmp/video.mp4")):
            result = await VideoService._get_video_path("https://youtube.com/watch?v=abc", "youtube")
            assert result == Path("/tmp/video.mp4")

    @pytest.mark.asyncio
    async def test_get_video_path_youtube_download_fails(self):
        """Test YouTube download failure raises VideoDownloadError (line 83)."""
        with patch.object(VideoService, "download_video",
                          new_callable=AsyncMock, return_value=None):
            with pytest.raises(VideoDownloadError, match="Failed to download"):
                await VideoService._get_video_path("https://youtube.com/watch?v=abc", "youtube")

    @pytest.mark.asyncio
    async def test_get_video_path_upload_exists(self, tmp_path):
        """Test upload path when file exists (lines 86-89)."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"video data")
        result = await VideoService._get_video_path(str(video_file), "upload")
        assert result == video_file

    @pytest.mark.asyncio
    async def test_get_video_path_upload_not_found(self):
        """Test upload path when file doesn't exist (lines 87-88)."""
        with pytest.raises(VideoNotFoundError, match="Video file not found"):
            await VideoService._get_video_path("/nonexistent/path.mp4", "upload")


# --- VideoService.download_video Tests ---

class TestDownloadVideo:
    """Test download_video static method."""

    @pytest.mark.asyncio
    async def test_download_video_success(self):
        """Test successful video download (lines 97-106)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value=Path("/tmp/video.mp4")):
            result = await VideoService.download_video("https://youtube.com/watch?v=abc")
            assert result == Path("/tmp/video.mp4")

    @pytest.mark.asyncio
    async def test_download_video_returns_none(self):
        """Test download returning None (lines 101-103)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value=None):
            result = await VideoService.download_video("https://youtube.com/watch?v=abc")
            assert result is None

    @pytest.mark.asyncio
    async def test_download_video_exception(self):
        """Test download exception is re-raised (lines 107-111)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, side_effect=RuntimeError("network error")):
            with pytest.raises(RuntimeError, match="network error"):
                await VideoService.download_video("https://youtube.com/watch?v=abc")


# --- VideoService.get_video_title Tests ---

class TestGetVideoTitle:
    """Test get_video_title static method."""

    @pytest.mark.asyncio
    async def test_get_video_title_success(self):
        """Test successful title retrieval (lines 119-121)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value="My Video Title"):
            result = await VideoService.get_video_title("https://youtube.com/watch?v=abc")
            assert result == "My Video Title"

    @pytest.mark.asyncio
    async def test_get_video_title_returns_none(self):
        """Test title retrieval returning None falls back to default (line 121)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value=None):
            result = await VideoService.get_video_title("https://youtube.com/watch?v=abc")
            assert result == "YouTube Video"

    @pytest.mark.asyncio
    async def test_get_video_title_exception(self):
        """Test title retrieval exception returns default (lines 122-124)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, side_effect=RuntimeError("error")):
            result = await VideoService.get_video_title("https://youtube.com/watch?v=abc")
            assert result == "YouTube Video"


# --- VideoService.generate_transcript Tests ---

class TestGenerateTranscript:
    """Test generate_transcript static method."""

    @pytest.mark.asyncio
    async def test_generate_transcript_success(self):
        """Test successful transcript generation (lines 132-136)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value="This is a transcript"):
            result = await VideoService.generate_transcript(Path("/tmp/video.mp4"))
            assert result == "This is a transcript"

    @pytest.mark.asyncio
    async def test_generate_transcript_exception(self):
        """Test transcript generation failure (lines 137-142)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, side_effect=RuntimeError("transcription error")):
            with pytest.raises(RuntimeError, match="transcription error"):
                await VideoService.generate_transcript(Path("/tmp/video.mp4"))


# --- VideoService.analyze_transcript Tests ---

class TestAnalyzeTranscript:
    """Test analyze_transcript static method."""

    @pytest.mark.asyncio
    async def test_analyze_transcript_success(self):
        """Test successful AI analysis."""
        mock_result = MagicMock()
        mock_result.most_relevant_segments = [MagicMock(), MagicMock()]

        with patch("src.services.video_service.get_most_relevant_parts_by_transcript",
                    new_callable=AsyncMock, return_value=mock_result):
            result = await VideoService.analyze_transcript(
                "Some transcript text",
                min_length=10,
                max_length=45,
                custom_ai_prompt="Custom prompt",
            )
            assert result is mock_result


# --- VideoService.create_video_clips Tests ---

class TestCreateVideoClips:
    """Test create_video_clips static method."""

    @pytest.mark.asyncio
    async def test_create_video_clips_success(self):
        """Test successful clip creation (lines 202-223)."""
        clips_info = [
            {"filename": "clip1.mp4", "path": "/tmp/clips/clip1.mp4"},
            {"filename": "clip2.mp4", "path": "/tmp/clips/clip2.mp4"},
        ]

        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, return_value=clips_info), \
             patch("src.services.video_service.config") as mock_config:
            mock_config.temp_dir = "/tmp"

            result = await VideoService.create_video_clips(
                Path("/tmp/video.mp4"),
                [{"start_time": "00:10", "end_time": "00:30"}],
                font_family="Arial",
                font_size=32,
                font_color="#FF0000",
                output_resolution="1080p",
                logo_path="/path/logo.png",
                logo_corner_position="top-left",
                subtitle_style={"color": "yellow"},
                subtitle_position={"y": 0.8},
            )

            assert len(result) == 2
            assert result[0]["filename"] == "clip1.mp4"

    @pytest.mark.asyncio
    async def test_create_video_clips_exception(self):
        """Test clip creation failure (lines 224-228)."""
        with patch("src.services.video_service.run_in_thread",
                    new_callable=AsyncMock, side_effect=RuntimeError("clip error")), \
             patch("src.services.video_service.config") as mock_config:
            mock_config.temp_dir = "/tmp"

            with pytest.raises(RuntimeError, match="clip error"):
                await VideoService.create_video_clips(
                    Path("/tmp/video.mp4"),
                    [{"start_time": "00:10", "end_time": "00:30"}],
                )


# --- VideoService.determine_source_type Tests ---

class TestDetermineSourceType:
    """Test determine_source_type static method."""

    def test_determine_source_type_youtube(self):
        """Test YouTube URL detection."""
        with patch("src.services.video_service.get_youtube_video_id", return_value="abc123"):
            result = VideoService.determine_source_type("https://youtube.com/watch?v=abc123")
            assert result == "youtube"

    def test_determine_source_type_upload(self):
        """Test upload detection for non-YouTube URLs."""
        with patch("src.services.video_service.get_youtube_video_id", return_value=None):
            result = VideoService.determine_source_type("/path/to/video.mp4")
            assert result == "upload"


# --- VideoService._validate_clip_duration_params Tests ---

class TestValidateClipDurationParams:
    """Test _validate_clip_duration_params static method."""

    def test_valid_params(self):
        """Test valid parameters pass through unchanged."""
        min_l, max_l = VideoService._validate_clip_duration_params(15, 45)
        assert min_l == 15
        assert max_l == 45

    def test_min_too_short(self):
        """Test min_length below 10 is capped (lines 249-251)."""
        min_l, max_l = VideoService._validate_clip_duration_params(5, 45)
        assert min_l == 10

    def test_min_too_long(self):
        """Test min_length above 60 is capped (lines 253-257)."""
        min_l, max_l = VideoService._validate_clip_duration_params(70, 120)
        assert min_l == 60

    def test_max_too_long(self):
        """Test max_length above 120 is capped (lines 259-263)."""
        min_l, max_l = VideoService._validate_clip_duration_params(10, 200)
        assert max_l == 120

    def test_max_less_than_min(self):
        """Test max_length less than min_length is adjusted (lines 265-267)."""
        min_l, max_l = VideoService._validate_clip_duration_params(30, 20)
        assert max_l == 40  # min_length + 10


# --- VideoService._apply_verbatim_text_to_segment Tests ---

class TestApplyVerbatimTextToSegment:
    """Test _apply_verbatim_text_to_segment static method."""

    def test_snaps_start_and_replaces_text(self):
        """Test segment start snapping and text replacement (lines 293-323)."""
        segment = {
            "start_time": "00:00:10.000",
            "end_time": "00:00:30.000",
            "text": "AI generated summary",
        }

        with patch("src.services.video_service.parse_timestamp_to_seconds") as mock_pts, \
             patch("src.services.video_service.snap_segment_to_sentence_start") as mock_snap, \
             patch("src.services.video_service.format_ms_to_timestamp_precise") as mock_fmt, \
             patch("src.video_utils.extract_text_from_cache") as mock_extract:

            mock_pts.side_effect = [10.0, 9.5, 30.0]
            mock_snap.return_value = (9.5, "The", "snapped to sentence")
            mock_fmt.return_value = "00:00:09.500"
            mock_extract.return_value = "The actual verbatim text"

            VideoService._apply_verbatim_text_to_segment(segment, Path("/tmp/video.mp4"))

            assert segment["start_time"] == "00:00:09.500"
            assert segment["text"] == "The actual verbatim text"
            assert segment["original_ai_start_time"] == "00:00:10.000"

    def test_no_snap_needed(self):
        """Test when no snapping is needed (lines 301-304)."""
        segment = {
            "start_time": "00:00:10.000",
            "end_time": "00:00:30.000",
            "text": "AI text",
        }

        with patch("src.services.video_service.parse_timestamp_to_seconds") as mock_pts, \
             patch("src.services.video_service.snap_segment_to_sentence_start") as mock_snap, \
             patch("src.video_utils.extract_text_from_cache") as mock_extract:

            mock_pts.side_effect = [10.0, 10.0, 30.0]
            mock_snap.return_value = (10.0, "The", "no snap needed")
            mock_extract.return_value = "Verbatim text"

            VideoService._apply_verbatim_text_to_segment(segment, Path("/tmp/video.mp4"))

            assert segment["start_time"] == "00:00:10.000"
            assert "original_ai_start_time" not in segment

    def test_no_verbatim_text_found(self):
        """Test when verbatim text extraction returns empty (lines 324-328)."""
        segment = {
            "start_time": "00:00:10.000",
            "end_time": "00:00:30.000",
            "text": "Original AI text",
        }

        with patch("src.services.video_service.parse_timestamp_to_seconds") as mock_pts, \
             patch("src.services.video_service.snap_segment_to_sentence_start") as mock_snap, \
             patch("src.video_utils.extract_text_from_cache") as mock_extract:

            mock_pts.side_effect = [10.0, 10.0, 30.0]
            mock_snap.return_value = (10.0, "The", "no snap")
            mock_extract.return_value = ""

            VideoService._apply_verbatim_text_to_segment(segment, Path("/tmp/video.mp4"))

            # Text should remain as original since verbatim_text is empty (falsy)
            assert segment["text"] == "Original AI text"


# --- VideoService.process_video_complete Tests ---

class TestProcessVideoComplete:
    """Test process_video_complete static method."""

    @pytest.mark.asyncio
    async def test_process_video_complete_success_with_callback(self):
        """Test full pipeline with progress callback (lines 381-448)."""
        mock_callback = AsyncMock()

        mock_relevant_parts = MagicMock()
        mock_segment = MagicMock()
        mock_segment.start_time = "00:00:10.000"
        mock_segment.end_time = "00:00:30.000"
        mock_segment.text = "Some text"
        mock_segment.relevance_score = 0.9
        mock_segment.reasoning = "Good"
        mock_relevant_parts.most_relevant_segments = [mock_segment]
        mock_relevant_parts.summary = "Summary"
        mock_relevant_parts.key_topics = ["topic"]

        clips_info = [{"filename": "clip1.mp4", "path": "/tmp/clips/clip1.mp4"}]

        with patch.object(VideoService, "_get_video_path", new_callable=AsyncMock,
                          return_value=Path("/tmp/video.mp4")), \
             patch.object(VideoService, "generate_transcript", new_callable=AsyncMock,
                          return_value="transcript text"), \
             patch.object(VideoService, "_validate_clip_duration_params",
                          return_value=(10, 45)), \
             patch.object(VideoService, "analyze_transcript", new_callable=AsyncMock,
                          return_value=mock_relevant_parts), \
             patch.object(VideoService, "_apply_verbatim_text_to_segment"), \
             patch.object(VideoService, "create_video_clips", new_callable=AsyncMock,
                          return_value=clips_info):

            result = await VideoService.process_video_complete(
                url="https://youtube.com/watch?v=abc",
                source_type="youtube",
                font_family="Arial",
                font_size=32,
                font_color="#FF0000",
                min_length=10,
                max_length=45,
                output_resolution="720p",
                logo_path="/path/logo.png",
                logo_corner_position="top-right",
                progress_callback=mock_callback,
                custom_ai_prompt="Custom prompt",
                subtitle_style={"color": "white"},
                subtitle_position={"y": 0.75},
            )

            assert result["clips"] == clips_info
            assert result["summary"] == "Summary"
            assert result["key_topics"] == ["topic"]

            # Verify callback was called at all progress points
            assert mock_callback.call_count == 5  # 10, 30, 50, 70, 100

    @pytest.mark.asyncio
    async def test_process_video_complete_without_callback(self):
        """Test full pipeline without progress callback (lines 381, 388, 397, 416, 443)."""
        mock_relevant_parts = MagicMock()
        mock_relevant_parts.most_relevant_segments = []
        mock_relevant_parts.summary = None
        mock_relevant_parts.key_topics = None

        with patch.object(VideoService, "_get_video_path", new_callable=AsyncMock,
                          return_value=Path("/tmp/video.mp4")), \
             patch.object(VideoService, "generate_transcript", new_callable=AsyncMock,
                          return_value="transcript"), \
             patch.object(VideoService, "_validate_clip_duration_params",
                          return_value=(10, 45)), \
             patch.object(VideoService, "analyze_transcript", new_callable=AsyncMock,
                          return_value=mock_relevant_parts), \
             patch.object(VideoService, "create_video_clips", new_callable=AsyncMock,
                          return_value=[]):

            result = await VideoService.process_video_complete(
                url="/video.mp4",
                source_type="upload",
                progress_callback=None,
            )

            assert result["clips"] == []

    @pytest.mark.asyncio
    async def test_process_video_complete_exception(self):
        """Test pipeline exception handling (lines 450-452)."""
        with patch.object(VideoService, "_get_video_path", new_callable=AsyncMock,
                          side_effect=VideoDownloadError("download failed")):
            with pytest.raises(VideoDownloadError, match="download failed"):
                await VideoService.process_video_complete(
                    url="https://youtube.com/watch?v=abc",
                    source_type="youtube",
                )


# end backend/tests/unit/test_video_service.py
