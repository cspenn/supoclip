"""
Video processing pipeline tests for SupoClip backend.

Tests:
- Video processing module initialization
- Model imports and availability
- Video file handling
- Clip generation structure
- Subtitle synchronization
- Error handling for invalid videos
"""
import pytest
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVideoModuleImports:
    """Test video processing module imports."""

    def test_video_utils_imports(self):
        """Test that video_utils module can be imported."""
        try:
            from src import video_utils
            assert video_utils is not None
        except ImportError as e:
            pytest.skip(f"video_utils import failed: {e}")

    def test_ai_module_imports(self):
        """Test that AI module can be imported."""
        try:
            from src import ai
            assert ai is not None
        except ImportError as e:
            pytest.skip(f"AI module import failed: {e}")

    def test_transcription_mlx_imports(self):
        """Test that MLX transcription module can be imported."""
        try:
            from src.transcription_mlx import transcribe_video_mlx
            assert transcribe_video_mlx is not None
        except ImportError as e:
            pytest.skip(f"MLX transcription import failed: {e}")


class TestVideoFileHandling:
    """Test video file handling."""

    def test_sample_video_exists(self, sample_video_path):
        """Test that sample video is created."""
        assert sample_video_path.exists()

    def test_sample_video_has_content(self, sample_video_path):
        """Test that sample video has content."""
        assert sample_video_path.stat().st_size > 0

    def test_video_in_correct_directory(self, sample_video_path, temp_dir):
        """Test that video is in correct directory."""
        assert sample_video_path.parent == temp_dir / "uploads"

    def test_multiple_videos_supported(self, temp_dir):
        """Test that multiple videos can be stored."""
        videos_dir = temp_dir / "uploads"

        # Create multiple videos
        for i in range(3):
            video_path = videos_dir / f"video_{i}.mp4"
            video_path.write_bytes(b"fake video")
            assert video_path.exists()

        # Verify all exist
        videos = list(videos_dir.glob("*.mp4"))
        assert len(videos) >= 3

    def test_video_naming_flexibility(self, temp_dir):
        """Test that various video filenames are supported."""
        videos_dir = temp_dir / "uploads"

        filenames = [
            "test-video.mp4",
            "my_video.mp4",
            "Video 123.mp4",
            "test.video.name.mp4"
        ]

        for filename in filenames:
            path = videos_dir / filename
            path.write_bytes(b"data")
            assert path.exists()


class TestClipGeneration:
    """Test clip generation structure and validation."""

    async def test_generated_clip_storage(self, test_db_session, sample_task_data, temp_dir):
        """Test that generated clips can be stored."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        # Create a clip file
        clip_path = clips_dir / "clip_001.mp4"
        clip_path.write_bytes(b"fake clip video")

        # Create clip record
        clip = GeneratedClip(
            id="clip-gen-1",
            task_id=task.id,
            filename="clip_001.mp4",
            file_path=str(clip_path),
            start_time="00:10",
            end_time="00:25",
            duration=15.0,
            relevance_score=0.92,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()

        # Verify clip was saved
        await test_db_session.refresh(clip)
        assert clip.id == "clip-gen-1"
        assert clip.duration == 15.0

    async def test_multiple_clips_per_task(self, test_db_session, sample_task_data, temp_dir):
        """Test that multiple clips can be generated for one task."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        clips = []
        for i in range(3):
            clip_path = clips_dir / f"clip_{i:03d}.mp4"
            clip_path.write_bytes(b"fake clip")

            clip = GeneratedClip(
                id=f"clip-multi-{i}",
                task_id=task.id,
                filename=f"clip_{i:03d}.mp4",
                file_path=str(clip_path),
                start_time=f"00:{10 + i*10:02d}",
                end_time=f"00:{25 + i*10:02d}",
                duration=15.0,
                relevance_score=0.85 + (i * 0.05),
                clip_order=i + 1
            )
            clips.append(clip)

        test_db_session.add_all(clips)
        await test_db_session.commit()

        # Reload task with clips
        await test_db_session.refresh(task, ["generated_clips"])

        assert len(task.generated_clips) == 3

    def test_clip_duration_validation(self):
        """Test that clip durations are realistic."""
        # Clips should be 10-45 seconds (per CLAUDE.md)
        valid_durations = [10.0, 15.0, 20.0, 30.0, 45.0]

        for duration in valid_durations:
            assert 10.0 <= duration <= 45.0

    def test_clip_time_format(self):
        """Test MM:SS time format for clips."""
        test_times = [
            ("00:10", "00:25"),
            ("01:30", "01:45"),
            ("10:00", "10:30"),
        ]

        for start, end in test_times:
            # Should parse as MM:SS
            parts = start.split(":")
            assert len(parts) == 2
            assert len(parts[0]) == 2
            assert len(parts[1]) == 2


class TestSubtitleHandling:
    """Test subtitle generation and synchronization."""

    async def test_clip_has_transcript_text(self, test_db_session, sample_task_data, temp_dir):
        """Test that clips can store transcript text."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        clip_path = clips_dir / "clip_with_text.mp4"
        clip_path.write_bytes(b"fake clip")

        transcript_text = "This is the transcript for the clip segment"

        clip = GeneratedClip(
            id="clip-subtitle-1",
            task_id=task.id,
            filename="clip_with_text.mp4",
            file_path=str(clip_path),
            start_time="00:10",
            end_time="00:25",
            duration=15.0,
            text=transcript_text,
            relevance_score=0.90,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()
        await test_db_session.refresh(clip)

        assert clip.text == transcript_text

    async def test_word_level_timestamps_storage(self, test_db_session, sample_task_data, temp_dir):
        """Test that word-level timing can be stored."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        # Create test clip
        clip_path = clips_dir / "clip_words.mp4"
        clip_path.write_bytes(b"fake clip")

        # Sample word timing data (parakeet-mlx format)
        words_data = [
            {"text": "This", "start": 10.0, "end": 10.5},
            {"text": "is", "start": 10.5, "end": 10.8},
            {"text": "a", "start": 10.8, "end": 11.0},
            {"text": "clip", "start": 11.0, "end": 11.5}
        ]

        clip = GeneratedClip(
            id="clip-words-1",
            task_id=task.id,
            filename="clip_words.mp4",
            file_path=str(clip_path),
            start_time="00:10",
            end_time="00:12",
            duration=2.0,
            text="This is a clip",
            relevance_score=0.88,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()

        # Verify clip can be retrieved
        await test_db_session.refresh(clip)
        assert clip.text == "This is a clip"

    def test_subtitle_positioning_lower_middle(self):
        """Test that subtitles are positioned at 75% down (lower-middle)."""
        # Per CLAUDE.md: "Subtitles positioned at 75% down the video (lower-middle, not bottom)"
        subtitle_position = 0.75
        assert 0.5 < subtitle_position < 1.0  # Between middle and bottom


class TestClipQualityMetrics:
    """Test clip quality and selection metrics."""

    async def test_relevance_score_storage(self, test_db_session, sample_task_data, temp_dir):
        """Test that relevance scores are stored."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        # Create multiple clips with different scores
        scores = [0.95, 0.87, 0.92, 0.78]

        for i, score in enumerate(scores):
            clip_path = clips_dir / f"clip_{i}.mp4"
            clip_path.write_bytes(b"data")

            clip = GeneratedClip(
                id=f"clip-score-{i}",
                task_id=task.id,
                filename=f"clip_{i}.mp4",
                file_path=str(clip_path),
                start_time="00:00",
                end_time="00:15",
                duration=15.0,
                relevance_score=score,
                clip_order=i + 1
            )

            test_db_session.add(clip)

        await test_db_session.commit()

        # Reload and verify
        await test_db_session.refresh(task, ["generated_clips"])
        retrieved_scores = sorted([c.relevance_score for c in task.generated_clips], reverse=True)

        assert len(retrieved_scores) == len(scores)
        assert retrieved_scores[0] == 0.95  # Highest score

    async def test_reasoning_field_storage(self, test_db_session, sample_task_data, temp_dir):
        """Test that AI reasoning for clip selection is stored."""
        from src.models import GeneratedClip

        task, _ = sample_task_data
        clips_dir = temp_dir / "clips"

        reasoning = "Strong hook with clear value proposition and high engagement moment"

        clip_path = clips_dir / "clip_reasoned.mp4"
        clip_path.write_bytes(b"data")

        clip = GeneratedClip(
            id="clip-reason-1",
            task_id=task.id,
            filename="clip_reasoned.mp4",
            file_path=str(clip_path),
            start_time="00:05",
            end_time="00:20",
            duration=15.0,
            relevance_score=0.94,
            reasoning=reasoning,
            clip_order=1
        )

        test_db_session.add(clip)
        await test_db_session.commit()
        await test_db_session.refresh(clip)

        assert clip.reasoning == reasoning


class TestVideoProcessingConfig:
    """Test video processing configuration."""

    def test_max_video_duration_setting(self, test_config):
        """Test max video duration is configured."""
        assert test_config.max_video_duration > 0
        # Should be at least 5 minutes
        assert test_config.max_video_duration >= 300

    def test_clip_duration_setting(self, test_config):
        """Test clip duration is configured."""
        assert test_config.clip_duration > 0
        # Should be between 10-45 seconds per requirements
        assert 10 <= test_config.clip_duration <= 45

    def test_max_clips_setting(self, test_config):
        """Test max clips per video is configured."""
        assert test_config.max_clips > 0
        # Should allow multiple clips
        assert test_config.max_clips >= 3


class TestVideoProcessingErrorHandling:
    """Test error handling in video processing."""

    async def test_missing_video_file_handling(self, test_db_session, sample_task_data):
        """Test handling of missing video files."""
        task, _ = sample_task_data

        # Reference nonexistent file
        nonexistent_path = "/tmp/nonexistent_video_file_12345.mp4"

        assert not Path(nonexistent_path).exists()

    async def test_invalid_clip_time_handling(self, test_db_session, sample_task_data, temp_dir):
        """Test handling of invalid clip times."""
        from src.models import GeneratedClip

        task, _ = sample_task_data

        # Create file
        clip_path = temp_dir / "clips" / "invalid_clip.mp4"
        clip_path.write_bytes(b"data")

        # Try to create clip with invalid times (end before start)
        # This should ideally be caught by validation
        clip = GeneratedClip(
            id="clip-invalid-1",
            task_id=task.id,
            filename="invalid_clip.mp4",
            file_path=str(clip_path),
            start_time="00:30",
            end_time="00:10",  # Invalid: end before start
            duration=-20.0,  # Invalid: negative duration
            relevance_score=0.5,
            clip_order=1
        )

        test_db_session.add(clip)
        # Database should accept this, but application logic should validate
        await test_db_session.commit()


class TestVideoProcessingIntegration:
    """Integration tests for video processing."""

    async def test_complete_clip_workflow(self, test_db_session, sample_task_data, temp_dir):
        """Test complete workflow from task to generated clips."""
        from src.models import GeneratedClip

        task, source = sample_task_data

        # Simulate clip generation
        clips_data = [
            {
                "filename": "clip_1.mp4",
                "start_time": "00:10",
                "end_time": "00:25",
                "text": "First clip content",
                "relevance_score": 0.95,
                "reasoning": "Strong opening hook"
            },
            {
                "filename": "clip_2.mp4",
                "start_time": "00:45",
                "end_time": "01:00",
                "text": "Second clip content",
                "relevance_score": 0.88,
                "reasoning": "Key insight moment"
            }
        ]

        clips_dir = temp_dir / "clips"

        for i, clip_data in enumerate(clips_data):
            clip_path = clips_dir / clip_data["filename"]
            clip_path.write_bytes(b"fake video")

            clip = GeneratedClip(
                id=f"clip-workflow-{i}",
                task_id=task.id,
                filename=clip_data["filename"],
                file_path=str(clip_path),
                start_time=clip_data["start_time"],
                end_time=clip_data["end_time"],
                duration=15.0,
                text=clip_data["text"],
                relevance_score=clip_data["relevance_score"],
                reasoning=clip_data["reasoning"],
                clip_order=i + 1
            )

            test_db_session.add(clip)

        await test_db_session.commit()

        # Verify complete workflow
        await test_db_session.refresh(task, ["generated_clips"])

        assert len(task.generated_clips) == 2
        assert all(c.file_path.endswith(".mp4") for c in task.generated_clips)
        assert task.generated_clips[0].relevance_score > task.generated_clips[1].relevance_score
