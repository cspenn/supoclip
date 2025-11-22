#!/usr/bin/env python3
"""
Test for logo parameter passing through the video processing pipeline.

This test verifies that logo_path and logo_corner_position are correctly passed
from the API endpoint through the worker, task service, and video service to the
actual clip generation function.

Expected behavior:
- Logo parameters should flow through the entire call chain
- Logo overlay code in video_utils.py should execute
- Log message "Added logo overlay at {position}" should appear
- Logo should appear on generated clips

Current behavior (BUG):
- Logo parameters are NOT passed through pipeline
- video_service.py hardcodes None for logo_path (line 184)
- Logo overlay code never executes
- No logo on clips

This test should FAIL until the bug is fixed.
"""

from pathlib import Path
import pytest

# Test configuration
TEST_USER_ID = "test-logo-user"
TEST_LOGO_PATH = Path("temp/logos/test-logo-user_logo.png")
TEST_LOGO_POSITION = "bottom-right"
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=test123"


class TestLogoParameterPassing:
    """Test suite for logo parameter passing through the pipeline."""

    @pytest.mark.asyncio
    async def test_logo_params_in_worker_task(self):
        """Test that worker task accepts logo parameters."""
        from src.workers.tasks import process_video_task
        import inspect

        # Get function signature
        sig = inspect.signature(process_video_task)
        params = list(sig.parameters.keys())

        # Check if logo parameters are present
        assert "logo_path" in params, "process_video_task missing logo_path parameter"
        assert (
            "logo_corner_position" in params
        ), "process_video_task missing logo_corner_position parameter"

        print("✅ Worker task has logo parameters")

    @pytest.mark.asyncio
    async def test_logo_params_in_task_service(self):
        """Test that task service process_task accepts logo parameters."""
        from src.services.task_service import TaskService
        import inspect

        # Get method signature
        sig = inspect.signature(TaskService.process_task)
        params = list(sig.parameters.keys())

        # Check if logo parameters are present
        assert (
            "logo_path" in params
        ), "TaskService.process_task missing logo_path parameter"
        assert (
            "logo_corner_position" in params
        ), "TaskService.process_task missing logo_corner_position parameter"

        print("✅ Task service has logo parameters")

    @pytest.mark.asyncio
    async def test_logo_params_in_video_service(self):
        """Test that video service process_video_complete accepts logo parameters."""
        from src.services.video_service import VideoService
        import inspect

        # Get method signature
        sig = inspect.signature(VideoService.process_video_complete)
        params = list(sig.parameters.keys())

        # Check if logo parameters are present
        assert (
            "logo_path" in params
        ), "VideoService.process_video_complete missing logo_path parameter"
        assert (
            "logo_corner_position" in params
        ), "VideoService.process_video_complete missing logo_corner_position parameter"

        print("✅ Video service has logo parameters")

    @pytest.mark.asyncio
    async def test_logo_params_passed_to_clip_creation(self):
        """Test that logo parameters are passed to create_clips_with_transitions."""
        from src.services.video_service import VideoService
        from unittest.mock import patch
        from pathlib import Path

        # Mock dependencies
        with patch(
            "src.services.video_service.VideoService._get_video_path"
        ) as mock_get_video, patch(
            "src.services.video_service.VideoService.generate_transcript"
        ) as mock_transcript, patch(
            "src.services.video_service.analyze_transcript_for_clips"
        ) as mock_analyze, patch(
            "src.services.video_service.run_in_thread"
        ) as mock_run_in_thread:
            # Setup mocks
            mock_get_video.return_value = Path("/tmp/test_video.mp4")
            mock_transcript.return_value = "test transcript"
            mock_analyze.return_value = [
                {
                    "start_time": 0,
                    "end_time": 10,
                    "text": "test segment",
                    "relevance_score": 0.9,
                    "reasoning": "test",
                }
            ]
            mock_run_in_thread.return_value = [
                {
                    "filename": "clip_1.mp4",
                    "path": "/tmp/clips/clip_1.mp4",
                    "start_time": 0,
                    "end_time": 10,
                    "duration": 10,
                    "text": "test",
                    "relevance_score": 0.9,
                    "reasoning": "test",
                }
            ]

            # Call the method WITH logo parameters
            test_logo_path = Path(TEST_LOGO_PATH)
            result = await VideoService.process_video_complete(
                url=TEST_VIDEO_URL,
                source_type="youtube",
                font_family="TikTokSans-Regular",
                font_size=24,
                font_color="#FFFFFF",
                min_length=10,
                max_length=45,
                output_resolution="720p",
                logo_path=test_logo_path,
                logo_corner_position=TEST_LOGO_POSITION,
            )

            # Verify that run_in_thread was called (this calls create_clips_with_transitions)
            assert mock_run_in_thread.called, "create_clips_with_transitions not called"

            # Get the actual call arguments
            call_args = mock_run_in_thread.call_args[0]

            # The call should be:
            # run_in_thread(create_clips_with_transitions, video_path, segments,
            #               clips_output_dir, font_family, font_size, font_color,
            #               logo_path, logo_position, output_resolution)

            # Check logo parameters are passed (not None)
            # Logo path should be at index 7, logo position at index 8
            if len(call_args) > 7:
                actual_logo_path = call_args[7]
                assert (
                    actual_logo_path is not None
                ), "Logo path is None - NOT PASSED TO CLIP CREATION"
                assert (
                    actual_logo_path == test_logo_path
                ), f"Logo path mismatch: expected {test_logo_path}, got {actual_logo_path}"
                print(f"✅ Logo path passed correctly: {actual_logo_path}")
            else:
                pytest.fail(
                    f"create_clips_with_transitions called with insufficient args: {len(call_args)}"
                )

            if len(call_args) > 8:
                actual_logo_position = call_args[8]
                assert (
                    actual_logo_position == TEST_LOGO_POSITION
                ), f"Logo position mismatch: expected {TEST_LOGO_POSITION}, got {actual_logo_position}"
                print(f"✅ Logo position passed correctly: {actual_logo_position}")
            else:
                pytest.fail("Logo position not passed to create_clips_with_transitions")

    @pytest.mark.asyncio
    async def test_logo_overlay_code_executes(self):
        """Test that logo overlay code in video_utils.py actually executes."""
        from src.video_utils import create_clips_with_transitions
        from pathlib import Path
        from unittest.mock import patch, MagicMock

        # Create a mock logger to capture log messages
        log_messages = []

        def capture_log(msg, *args, **kwargs):
            formatted = msg % args if args else msg
            log_messages.append(formatted)

        # Test data
        test_video_path = Path("/tmp/test_video.mp4")
        test_segments = [
            {
                "start_time": 0,
                "end_time": 10,
                "text": "test segment",
                "relevance_score": 0.9,
                "reasoning": "test",
            }
        ]
        test_output_dir = Path("/tmp/test_clips")
        test_logo_path = Path(TEST_LOGO_PATH)

        # Patch video processing functions and logger
        with patch("src.video_utils.VideoFileClip") as mock_video, patch(
            "src.video_utils.CompositeVideoClip"
        ) as mock_composite, patch("src.video_utils.TextClip") as mock_text, patch(
            "src.video_utils.ImageClip"
        ) as mock_image, patch(
            "src.video_utils.logger.info", side_effect=capture_log
        ) as mock_logger_info, patch(
            "src.video_utils.logger.warning"
        ) as mock_logger_warning:
            # Setup mocks
            mock_video_clip = MagicMock()
            mock_video_clip.duration = 100
            mock_video_clip.size = (1920, 1080)
            mock_video_clip.fps = 30
            mock_video.return_value = mock_video_clip

            # Mock logo file exists
            with patch.object(Path, "exists", return_value=True):
                # Mock ImageClip for logo
                mock_logo_clip = MagicMock()
                mock_logo_clip.size = (60, 60)
                mock_image.return_value = mock_logo_clip

                try:
                    # Call with logo parameters
                    result = create_clips_with_transitions(
                        video_path=test_video_path,
                        segments=test_segments,
                        output_dir=test_output_dir,
                        font_family="TikTokSans-Regular",
                        font_size=24,
                        font_color="#FFFFFF",
                        logo_path=test_logo_path,  # PASS LOGO PATH
                        logo_position=TEST_LOGO_POSITION,  # PASS LOGO POSITION
                        output_resolution="720p",
                    )

                    # Check if logo overlay message was logged
                    logo_messages = [
                        msg for msg in log_messages if "logo" in msg.lower()
                    ]

                    # We expect to see "Added logo overlay at {position}"
                    overlay_added = any(
                        "Added logo overlay" in msg for msg in logo_messages
                    )

                    if not overlay_added:
                        print("❌ Logo overlay code NOT executed")
                        print(f"   Captured log messages: {log_messages}")
                        pytest.fail(
                            "Logo overlay code did not execute - no log message found"
                        )
                    else:
                        print("✅ Logo overlay code executed successfully")
                        print(f"   Logo messages: {logo_messages}")

                except Exception as e:
                    print(f"❌ Test failed with exception: {e}")
                    raise


def test_logo_file_exists():
    """Verify test logo file exists for testing."""
    logo_path = Path(__file__).parent / "docs" / "TI_Primary_2Color_Reverse.png"

    if not logo_path.exists():
        pytest.skip(f"Test logo file not found at {logo_path}")

    print(f"✅ Test logo file found: {logo_path}")
    print(f"   Size: {logo_path.stat().st_size} bytes")


def test_logo_overlay_code_exists():
    """Verify logo overlay code exists in video_utils.py."""
    from pathlib import Path

    video_utils_path = Path(__file__).parent / "src" / "video_utils.py"
    content = video_utils_path.read_text()

    # Check for key parts of logo overlay code
    checks = [
        ("if logo_path and logo_path.exists():", "Logo path check"),
        ("ImageClip(str(logo_path))", "Logo ImageClip creation"),
        ("logo_position_coords =", "Logo position calculation"),
        ('logger.info(f"Added logo overlay', "Logo overlay success log"),
        ('logger.warning(f"Failed to add logo overlay', "Logo overlay error log"),
    ]

    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description} found in video_utils.py")
        else:
            pytest.fail(f"❌ {description} NOT found in video_utils.py")


if __name__ == "__main__":
    print("=" * 70)
    print("LOGO PIPELINE TEST SUITE")
    print("=" * 70)
    print()
    print("This test suite verifies that logo parameters are correctly passed")
    print("through the entire video processing pipeline:")
    print()
    print("1. API endpoint receives logo_path from user preferences")
    print("2. Worker task accepts logo parameters")
    print("3. Task service accepts and passes logo parameters")
    print("4. Video service accepts and passes logo parameters")
    print("5. create_clips_with_transitions receives non-None logo_path")
    print("6. Logo overlay code executes")
    print("7. Log message confirms logo application")
    print()
    print("=" * 70)
    print("RUNNING TESTS...")
    print("=" * 70)
    print()

    # Run pytest
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
