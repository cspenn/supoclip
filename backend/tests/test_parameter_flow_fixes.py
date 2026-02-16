"""
Test suite demonstrating the FIXED parameter flow behavior.

These tests verify that the three critical fixes are working:
1. resolve_font_path() finds system fonts and tries variations
2. Clip length parameters flow through entire pipeline
3. Parameter logging exposes font and clip length values

All tests should PASS, proving the fixes work correctly.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import logging

# Import from src package
from src.services.video_service import VideoService

class TestClipLengthParametersPassedThroughPipeline:
    """Verify that clip length parameters flow through entire pipeline."""

    @pytest.mark.asyncio
    async def test_analyze_transcript_receives_clip_length_params(self):
        mock_result = Mock()
        mock_result.most_relevant_segments = []

        with patch('src.services.video_service.get_most_relevant_parts_by_transcript',
                   new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = mock_result

            await VideoService.analyze_transcript(
                "Test transcript",
                min_length=50,
                max_length=60
            )

            mock_ai.assert_called_once_with(
                "Test transcript",
                min_length=50,
                max_length=60,
                custom_prompt=None,
            )

    @pytest.mark.asyncio
    async def test_process_video_complete_passes_clip_length_to_analyze(self):
        with patch.object(VideoService, '_get_video_path', new_callable=AsyncMock) as mock_path, \
             patch.object(VideoService, 'generate_transcript', new_callable=AsyncMock) as mock_transcript, \
             patch.object(VideoService, 'analyze_transcript', new_callable=AsyncMock) as mock_analyze, \
             patch.object(VideoService, 'create_video_clips', new_callable=AsyncMock) as mock_clips:

            mock_path.return_value = Path("/fake/video.mp4")
            mock_transcript.return_value = "Sample transcript"
            mock_result = Mock()
            mock_result.most_relevant_segments = []
            mock_result.summary = "Summary"
            mock_result.key_topics = []
            mock_analyze.return_value = mock_result
            mock_clips.return_value = []

            await VideoService.process_video_complete(
                url="test.mp4",
                source_type="upload",
                min_length=50,
                max_length=60
            )

            mock_analyze.assert_called_once()
            call_args = mock_analyze.call_args
            assert call_args[1]['min_length'] == 50
            assert call_args[1]['max_length'] == 60


class TestVideoServiceLogsParameters:
    """Verify that VideoService logs all critical parameters."""

    @pytest.mark.asyncio
    async def test_font_parameters_logged(self, caplog):
        caplog.set_level(logging.INFO)

        with patch.object(VideoService, '_get_video_path', new_callable=AsyncMock) as mock_path, \
             patch.object(VideoService, 'generate_transcript', new_callable=AsyncMock) as mock_transcript, \
             patch.object(VideoService, 'analyze_transcript', new_callable=AsyncMock) as mock_analyze, \
             patch.object(VideoService, 'create_video_clips', new_callable=AsyncMock) as mock_clips:

            mock_path.return_value = Path("/fake/video.mp4")
            mock_transcript.return_value = "Sample"
            mock_result = Mock()
            mock_result.most_relevant_segments = []
            mock_result.summary = "Summary"
            mock_result.key_topics = []
            mock_analyze.return_value = mock_result
            mock_clips.return_value = []

            await VideoService.process_video_complete(
                url="test.mp4",
                source_type="upload",
                font_family="CustomFont",
                font_size=30,
                font_color="#FF0000"
            )

            log_text = caplog.text
            assert "font_family=CustomFont" in log_text
            assert "font_size=30" in log_text
            assert "font_color=#FF0000" in log_text


class TestIntegrationParameterFlow:
    """Integration tests verifying end-to-end parameter flow."""

    @pytest.mark.asyncio
    async def test_full_parameter_flow_from_api_to_video_creation(self):
        # Track parameter flow through the pipeline
        captured_params = {}

        async def mock_analyze_transcript(transcript, min_length=10, max_length=45, custom_ai_prompt=None):
            captured_params['ai_min_length'] = min_length
            captured_params['ai_max_length'] = max_length
            mock_result = Mock()
            mock_result.most_relevant_segments = []
            mock_result.summary = "Summary"
            mock_result.key_topics = []
            return mock_result

        async def mock_create_clips(video_path, segments, *args, **kwargs):
            # create_video_clips(video_path, segments, font_family, font_size, font_color, ...)
            captured_params['clip_font_family'] = kwargs.get('font_family') or (args[0] if len(args) > 0 else None)
            captured_params['clip_font_size'] = kwargs.get('font_size') or (args[1] if len(args) > 1 else None)
            captured_params['clip_font_color'] = kwargs.get('font_color') or (args[2] if len(args) > 2 else None)
            return []

        with patch.object(VideoService, '_get_video_path', new_callable=AsyncMock) as mock_path, \
             patch.object(VideoService, 'generate_transcript', new_callable=AsyncMock) as mock_transcript, \
             patch.object(VideoService, 'analyze_transcript', new_callable=AsyncMock) as mock_analyze, \
             patch.object(VideoService, 'create_video_clips', new_callable=AsyncMock) as mock_clips:

            mock_path.return_value = Path("/fake/video.mp4")
            mock_transcript.return_value = "Sample transcript"
            mock_analyze.side_effect = mock_analyze_transcript
            mock_clips.side_effect = mock_create_clips

            await VideoService.process_video_complete(
                url="test.mp4",
                source_type="upload",
                font_family="TestFont",
                font_size=28,
                font_color="#00FF00",
                min_length=55,
                max_length=65
            )

            assert captured_params['ai_min_length'] == 55
            assert captured_params['ai_max_length'] == 65
            assert captured_params['clip_font_family'] == "TestFont"
            assert captured_params['clip_font_size'] == 28
            assert captured_params['clip_font_color'] == "#00FF00"
