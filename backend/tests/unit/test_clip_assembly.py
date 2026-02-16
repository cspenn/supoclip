# start tests/unit/test_clip_assembly.py
"""
Unit tests for backend/src/clip_assembly.py

Covers: _add_logo_overlay, _validate_clip_timing, _prepare_cropped_clip,
_build_subtitle_overlays, _compose_and_encode, create_optimized_clip,
create_clips_from_segments, get_available_transitions, apply_transition_effect,
create_clips_with_transitions
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

backend_root = Path(__file__).parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Patch config before importing
with patch("src.config.Config"):
    from src.clip_assembly import (
        _add_logo_overlay,
        _validate_clip_timing,
        _prepare_cropped_clip,
        _build_subtitle_overlays,
        _compose_and_encode,
        create_optimized_clip,
        create_clips_from_segments,
        get_available_transitions,
        apply_transition_effect,
        create_clips_with_transitions,
        RESOLUTION_PRESETS,
        AUDIO_BUFFER_SECONDS,
    )


# ---------------------------------------------------------------------------
# _add_logo_overlay (lines 59, 73-74, 109-110)
# ---------------------------------------------------------------------------
class TestAddLogoOverlay:
    def test_no_logo_path(self):
        clips = []
        _add_logo_overlay(clips, None, "top-right", 720, 1280, 10.0)
        assert clips == []

    def test_logo_not_found(self, tmp_path):
        clips = []
        _add_logo_overlay(
            clips, str(tmp_path / "missing.png"), "top-right", 720, 1280, 10.0
        )
        assert clips == []

    @patch("src.clip_assembly.ImageClip")
    def test_logo_success(self, mock_imageclip, tmp_path):
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"fake png")

        mock_clip = MagicMock()
        mock_clip.size = (100, 50)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_imageclip.return_value = mock_clip

        clips = []
        _add_logo_overlay(
            clips, str(logo_file), "top-right", 720, 1280, 10.0
        )
        assert len(clips) == 1

    @patch("src.clip_assembly.ImageClip")
    def test_logo_positions(self, mock_imageclip, tmp_path):
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"fake png")

        mock_clip = MagicMock()
        mock_clip.size = (100, 50)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_imageclip.return_value = mock_clip

        for pos in ["top-left", "top-right", "bottom-left", "bottom-right", "invalid"]:
            clips = []
            _add_logo_overlay(clips, str(logo_file), pos, 720, 1280, 10.0)
            assert len(clips) == 1

    @patch("src.clip_assembly.ImageClip")
    def test_logo_relative_path(self, mock_imageclip, tmp_path):
        """Test relative path gets resolved (lines 68-70)."""
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"fake png")

        mock_clip = MagicMock()
        mock_clip.size = (100, 50)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_imageclip.return_value = mock_clip

        clips = []
        # Use absolute path since relative path resolution depends on cwd
        _add_logo_overlay(clips, str(logo_file), "top-right", 720, 1280, 10.0)
        assert len(clips) == 1

    @patch("src.clip_assembly.ImageClip")
    def test_logo_exception(self, mock_imageclip, tmp_path):
        """Exception during logo creation is caught (lines 109-110)."""
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"fake png")
        mock_imageclip.side_effect = RuntimeError("fail")

        clips = []
        _add_logo_overlay(clips, str(logo_file), "top-right", 720, 1280, 10.0)
        assert clips == []

    @patch("src.clip_assembly.ImageClip")
    def test_logo_relative_path_resolved(self, mock_imageclip, tmp_path, monkeypatch):
        """Relative path gets resolved to absolute (lines 69-70)."""
        import os
        # Create the logo in a known relative location
        logo_file = tmp_path / "logo.png"
        logo_file.write_bytes(b"fake png")

        mock_clip = MagicMock()
        mock_clip.size = (100, 50)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_imageclip.return_value = mock_clip

        # Change cwd so relative path resolves to tmp_path/logo.png
        monkeypatch.chdir(tmp_path)
        clips = []
        _add_logo_overlay(clips, "logo.png", "top-right", 720, 1280, 10.0)
        assert len(clips) == 1


# ---------------------------------------------------------------------------
# _validate_clip_timing (lines 128, 130)
# ---------------------------------------------------------------------------
class TestValidateClipTiming:
    def test_valid(self):
        assert _validate_clip_timing(0.0, 5.0, 60.0) is None

    def test_zero_duration(self):
        result = _validate_clip_timing(5.0, 5.0, 60.0)
        assert result is not None
        assert "Invalid" in result

    def test_negative_duration(self):
        result = _validate_clip_timing(10.0, 5.0, 60.0)
        assert result is not None

    def test_start_exceeds_duration(self):
        result = _validate_clip_timing(70.0, 80.0, 60.0)
        assert result is not None
        assert "exceeds" in result


# ---------------------------------------------------------------------------
# _prepare_cropped_clip
# ---------------------------------------------------------------------------
class TestPrepareCroppedClip:
    @patch("src.clip_assembly.detect_optimal_crop_region")
    def test_basic_preparation(self, mock_crop):
        mock_crop.return_value = (0, 0, 720, 1280)

        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_subclip = MagicMock()
        mock_video.subclipped.return_value = mock_subclip

        mock_cropped = MagicMock()
        mock_subclip.cropped.return_value = mock_cropped

        mock_resized = MagicMock()
        mock_cropped.resized.return_value = mock_resized

        cropped, w, h, bs, be = _prepare_cropped_clip(
            mock_video, 5.0, 15.0, "720p"
        )
        assert w == 720
        assert h == 1280

    @patch("src.clip_assembly.detect_optimal_crop_region")
    def test_no_resize_needed(self, mock_crop):
        """When dimensions match target, no resize (line 178)."""
        mock_crop.return_value = (0, 0, 720, 1280)

        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_subclip = MagicMock()
        mock_video.subclipped.return_value = mock_subclip

        mock_cropped = MagicMock()
        mock_subclip.cropped.return_value = mock_cropped

        cropped, w, h, bs, be = _prepare_cropped_clip(
            mock_video, 5.0, 15.0, "720p"
        )
        assert w == 720
        assert h == 1280
        mock_cropped.resized.assert_not_called()

    @patch("src.clip_assembly.detect_optimal_crop_region")
    def test_buffer_applied(self, mock_crop):
        mock_crop.return_value = (0, 0, 720, 1280)

        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_subclip = MagicMock()
        mock_video.subclipped.return_value = mock_subclip
        mock_subclip.cropped.return_value = MagicMock()

        _prepare_cropped_clip(mock_video, 5.0, 15.0, "720p")

        call_args = mock_video.subclipped.call_args[0]
        assert call_args[0] == pytest.approx(5.0 - AUDIO_BUFFER_SECONDS)
        assert call_args[1] == pytest.approx(15.0 + AUDIO_BUFFER_SECONDS)

    @patch("src.clip_assembly.detect_optimal_crop_region")
    def test_buffer_clamped_at_zero(self, mock_crop):
        mock_crop.return_value = (0, 0, 720, 1280)

        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_subclip = MagicMock()
        mock_video.subclipped.return_value = mock_subclip
        mock_subclip.cropped.return_value = MagicMock()

        _prepare_cropped_clip(mock_video, 0.0, 5.0, "720p")
        call_args = mock_video.subclipped.call_args[0]
        assert call_args[0] == 0  # clamped at 0

    @patch("src.clip_assembly.detect_optimal_crop_region")
    def test_different_resolutions(self, mock_crop):
        mock_crop.return_value = (0, 0, 500, 900)

        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_subclip = MagicMock()
        mock_video.subclipped.return_value = mock_subclip
        mock_cropped = MagicMock()
        mock_subclip.cropped.return_value = mock_cropped
        mock_cropped.resized.return_value = MagicMock()

        for res in ["480p", "720p", "1080p"]:
            _prepare_cropped_clip(mock_video, 5.0, 15.0, res)


# ---------------------------------------------------------------------------
# _build_subtitle_overlays
# ---------------------------------------------------------------------------
class TestBuildSubtitleOverlays:
    @patch("src.clip_assembly.create_subtitles")
    def test_offsets_subtitles(self, mock_create):
        mock_clip1 = MagicMock()
        mock_clip1.start = 1.0
        mock_clip1.with_start.return_value = mock_clip1

        mock_clip2 = MagicMock()
        mock_clip2.start = 2.0
        mock_clip2.with_start.return_value = mock_clip2

        mock_create.return_value = [mock_clip1, mock_clip2]

        result = _build_subtitle_overlays(
            Path("/fake/video.mp4"), 5.0, 15.0, 720, 1280,
            "TestFont", 24, "#FFF", None, None
        )
        assert len(result) == 2
        # Each clip should have with_start called with start + buffer
        mock_clip1.with_start.assert_called_once_with(1.0 + AUDIO_BUFFER_SECONDS)
        mock_clip2.with_start.assert_called_once_with(2.0 + AUDIO_BUFFER_SECONDS)


# ---------------------------------------------------------------------------
# _compose_and_encode
# ---------------------------------------------------------------------------
class TestComposeAndEncode:
    @patch("src.clip_assembly.VideoProcessor")
    @patch("src.clip_assembly.CompositeVideoClip")
    def test_multiple_clips(self, mock_composite, mock_processor_cls):
        mock_final = MagicMock()
        mock_composite.return_value = mock_final

        mock_processor = MagicMock()
        mock_processor.get_optimal_encoding_settings.return_value = {
            "codec": "libx264", "audio_codec": "aac",
            "bitrate": "8000k", "audio_bitrate": "256k",
            "preset": "medium", "ffmpeg_params": [],
        }
        mock_processor_cls.return_value = mock_processor

        clips = [MagicMock(), MagicMock()]
        _compose_and_encode(clips, clips[0], Path("/out.mp4"), "Font", 24, "#FFF")
        mock_composite.assert_called_once()
        mock_final.write_videofile.assert_called_once()

    @patch("src.clip_assembly.VideoProcessor")
    def test_single_clip_no_composite(self, mock_processor_cls):
        mock_processor = MagicMock()
        mock_processor.get_optimal_encoding_settings.return_value = {
            "codec": "libx264", "audio_codec": "aac",
            "bitrate": "8000k", "audio_bitrate": "256k",
            "preset": "medium", "ffmpeg_params": [],
        }
        mock_processor_cls.return_value = mock_processor

        mock_cropped = MagicMock()
        clips = [mock_cropped]
        _compose_and_encode(clips, mock_cropped, Path("/out.mp4"), "Font", 24, "#FFF")
        mock_cropped.write_videofile.assert_called_once()


# ---------------------------------------------------------------------------
# create_optimized_clip (lines 322-323, 356-358)
# ---------------------------------------------------------------------------
class TestCreateOptimizedClip:
    @patch("src.clip_assembly._compose_and_encode")
    @patch("src.clip_assembly._add_logo_overlay")
    @patch("src.clip_assembly._build_subtitle_overlays")
    @patch("src.clip_assembly._prepare_cropped_clip")
    @patch("src.clip_assembly._validate_clip_timing")
    @patch("src.clip_assembly.VideoFileClip")
    def test_success(self, mock_vfc, mock_validate, mock_prepare, mock_subs,
                     mock_logo, mock_encode):
        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_video.fps = 30
        mock_vfc.return_value = mock_video

        mock_validate.return_value = None

        mock_cropped = MagicMock()
        mock_cropped.duration = 10.0
        mock_prepare.return_value = (mock_cropped, 720, 1280, 4.85, 15.15)

        mock_subs.return_value = [MagicMock()]

        result = create_optimized_clip(
            Path("/fake/video.mp4"), 5.0, 15.0, Path("/out/clip.mp4")
        )
        assert result is True

    @patch("src.clip_assembly.VideoFileClip")
    def test_invalid_timing(self, mock_vfc):
        """Invalid timing returns False (lines 322-323)."""
        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_video.fps = 30
        mock_vfc.return_value = mock_video

        result = create_optimized_clip(
            Path("/fake/video.mp4"), 70.0, 80.0, Path("/out/clip.mp4")
        )
        assert result is False

    @patch("src.clip_assembly.VideoFileClip")
    def test_exception_returns_false(self, mock_vfc):
        """Top-level exception returns False (lines 356-358)."""
        mock_vfc.side_effect = RuntimeError("fail")

        result = create_optimized_clip(
            Path("/fake/video.mp4"), 5.0, 15.0, Path("/out/clip.mp4")
        )
        assert result is False

    @patch("src.clip_assembly._compose_and_encode")
    @patch("src.clip_assembly._add_logo_overlay")
    @patch("src.clip_assembly._build_subtitle_overlays")
    @patch("src.clip_assembly._prepare_cropped_clip")
    @patch("src.clip_assembly._validate_clip_timing")
    @patch("src.clip_assembly.VideoFileClip")
    def test_no_subtitles(self, mock_vfc, mock_validate, mock_prepare,
                          mock_subs, mock_logo, mock_encode):
        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_video.fps = 30
        mock_vfc.return_value = mock_video

        mock_validate.return_value = None
        mock_cropped = MagicMock()
        mock_cropped.duration = 10.0
        mock_prepare.return_value = (mock_cropped, 720, 1280, 4.85, 15.15)

        result = create_optimized_clip(
            Path("/fake/video.mp4"), 5.0, 15.0, Path("/out/clip.mp4"),
            add_subtitles=False
        )
        assert result is True
        mock_subs.assert_not_called()

    @patch("src.clip_assembly._compose_and_encode")
    @patch("src.clip_assembly._add_logo_overlay")
    @patch("src.clip_assembly._build_subtitle_overlays")
    @patch("src.clip_assembly._prepare_cropped_clip")
    @patch("src.clip_assembly._validate_clip_timing")
    @patch("src.clip_assembly.VideoFileClip")
    def test_cleanup_on_success(self, mock_vfc, mock_validate, mock_prepare,
                                mock_subs, mock_logo, mock_encode):
        """Cleanup runs in finally block."""
        mock_video = MagicMock()
        mock_video.duration = 60.0
        mock_video.fps = 30
        mock_vfc.return_value = mock_video

        mock_validate.return_value = None
        mock_cropped = MagicMock()
        mock_cropped.duration = 10.0
        mock_prepare.return_value = (mock_cropped, 720, 1280, 4.85, 15.15)
        mock_subs.return_value = []

        create_optimized_clip(
            Path("/fake/video.mp4"), 5.0, 15.0, Path("/out/clip.mp4")
        )
        # Video should be closed
        mock_video.close.assert_called()


# ---------------------------------------------------------------------------
# create_clips_from_segments (lines 429-432, 471-478)
# ---------------------------------------------------------------------------
class TestCreateClipsFromSegments:
    @patch("src.clip_assembly.create_optimized_clip")
    @patch("src.clip_assembly.parse_timestamp_to_seconds")
    def test_success(self, mock_parse, mock_create, tmp_path):
        mock_parse.side_effect = [5.0, 15.0]
        mock_create.return_value = True

        segments = [{
            "start_time": "00:05",
            "end_time": "00:15",
            "text": "hello world",
            "relevance_score": 0.9,
            "reasoning": "good content",
        }]

        result = create_clips_from_segments(
            Path("/fake/video.mp4"), segments, tmp_path
        )
        assert len(result) == 1
        assert result[0]["clip_id"] == 1

    @patch("src.clip_assembly.create_optimized_clip")
    @patch("src.clip_assembly.parse_timestamp_to_seconds")
    def test_invalid_duration_skipped(self, mock_parse, mock_create, tmp_path):
        """Duration <= 0 skips clip (lines 429-432)."""
        mock_parse.side_effect = [15.0, 5.0]  # end < start
        mock_create.return_value = True

        segments = [{
            "start_time": "00:15",
            "end_time": "00:05",
            "text": "reversed",
            "relevance_score": 0.5,
            "reasoning": "test",
        }]

        result = create_clips_from_segments(
            Path("/fake/video.mp4"), segments, tmp_path
        )
        assert len(result) == 0

    @patch("src.clip_assembly.create_optimized_clip")
    @patch("src.clip_assembly.parse_timestamp_to_seconds")
    def test_clip_creation_fails(self, mock_parse, mock_create, tmp_path):
        """Failed clip creation logged (lines 471-474)."""
        mock_parse.side_effect = [5.0, 15.0]
        mock_create.return_value = False

        segments = [{
            "start_time": "00:05",
            "end_time": "00:15",
            "text": "hello",
            "relevance_score": 0.9,
            "reasoning": "test",
        }]

        result = create_clips_from_segments(
            Path("/fake/video.mp4"), segments, tmp_path
        )
        assert len(result) == 0

    @patch("src.clip_assembly.parse_timestamp_to_seconds")
    def test_segment_exception(self, mock_parse, tmp_path):
        """Exception processing segment (lines 476-478)."""
        mock_parse.side_effect = ValueError("bad timestamp")

        segments = [{
            "start_time": "bad",
            "end_time": "also_bad",
            "text": "hello",
            "relevance_score": 0.9,
            "reasoning": "test",
        }]

        result = create_clips_from_segments(
            Path("/fake/video.mp4"), segments, tmp_path
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# get_available_transitions (lines 494-495)
# ---------------------------------------------------------------------------
class TestGetAvailableTransitions:
    @patch("src.clip_assembly.Path")
    def test_no_transitions_dir(self, mock_path_cls):
        mock_dir = MagicMock()
        mock_dir.exists.return_value = False
        # __file__.parent.parent / "transitions"
        mock_path_cls.return_value = MagicMock()
        mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_dir

        result = get_available_transitions()
        assert result == []

    def test_with_transitions(self, tmp_path):
        """Test with actual transition files."""
        transitions_dir = tmp_path / "transitions"
        transitions_dir.mkdir()
        (transitions_dir / "fade.mp4").touch()
        (transitions_dir / "slide.mp4").touch()

        with patch("src.clip_assembly.Path") as mock_path_cls:
            # Make __file__ resolve to a path under tmp_path
            mock_file = MagicMock()
            mock_file.parent.parent.__truediv__.return_value = transitions_dir
            mock_path_cls.return_value = mock_file

            result = get_available_transitions()
            assert len(result) == 2


# ---------------------------------------------------------------------------
# apply_transition_effect (lines 517-567)
# ---------------------------------------------------------------------------
class TestApplyTransitionEffect:
    @patch("src.clip_assembly.VideoProcessor")
    def test_success(self, mock_processor_cls):
        """Test successful transition (lines 517-567)."""
        mock_clip1 = MagicMock()
        mock_clip1.size = (720, 1280)
        mock_clip1.with_effects.return_value = mock_clip1

        mock_clip2 = MagicMock()
        mock_clip2.with_effects.return_value = mock_clip2

        mock_transition = MagicMock()
        mock_transition.duration = 1.0
        mock_transition.subclipped.return_value = mock_transition
        mock_transition.resized.return_value = mock_transition

        mock_final = MagicMock()

        mock_vfc = MagicMock(side_effect=[mock_clip1, mock_clip2, mock_transition])
        mock_concat = MagicMock(return_value=mock_final)

        mock_processor = MagicMock()
        mock_processor.get_optimal_encoding_settings.return_value = {
            "codec": "libx264", "audio_codec": "aac",
            "bitrate": "8000k", "audio_bitrate": "256k",
            "preset": "medium", "ffmpeg_params": [],
        }
        mock_processor_cls.return_value = mock_processor

        # Patch the moviepy module so the local import inside the function
        # gets our mocked objects
        import moviepy as moviepy_mod
        with patch.object(moviepy_mod, "VideoFileClip", mock_vfc), \
             patch.object(moviepy_mod, "concatenate_videoclips", mock_concat):
            result = apply_transition_effect(
                Path("/clip1.mp4"), Path("/clip2.mp4"),
                Path("/trans.mp4"), Path("/out.mp4")
            )
            assert result is True
            mock_final.write_videofile.assert_called_once()
            mock_final.close.assert_called_once()

    def test_exception_returns_false(self):
        """Exception returns False (lines 565-567)."""
        import moviepy as moviepy_mod
        with patch.object(moviepy_mod, "VideoFileClip", side_effect=RuntimeError("fail")):
            result = apply_transition_effect(
                Path("/clip1.mp4"), Path("/clip2.mp4"),
                Path("/trans.mp4"), Path("/out.mp4")
            )
            assert result is False


# ---------------------------------------------------------------------------
# create_clips_with_transitions (lines 625-670)
# ---------------------------------------------------------------------------
class TestCreateClipsWithTransitions:
    @patch("src.clip_assembly.create_clips_from_segments")
    def test_not_enough_clips(self, mock_create):
        """Less than 2 clips = no transitions (line 620-622)."""
        mock_create.return_value = [
            {"clip_id": 1, "path": "/clip1.mp4", "filename": "clip1.mp4"}
        ]

        result = create_clips_with_transitions(
            Path("/video.mp4"), [{}], Path("/output")
        )
        assert len(result) == 1

    @patch("src.clip_assembly.get_available_transitions")
    @patch("src.clip_assembly.create_clips_from_segments")
    def test_no_transitions_available(self, mock_create, mock_trans):
        """No transition files found (lines 626-628)."""
        mock_create.return_value = [
            {"clip_id": 1, "path": "/clip1.mp4", "filename": "clip1.mp4"},
            {"clip_id": 2, "path": "/clip2.mp4", "filename": "clip2.mp4"},
        ]
        mock_trans.return_value = []

        result = create_clips_with_transitions(
            Path("/video.mp4"), [{}, {}], Path("/output")
        )
        assert len(result) == 2

    @patch("src.clip_assembly.apply_transition_effect")
    @patch("src.clip_assembly.get_available_transitions")
    @patch("src.clip_assembly.create_clips_from_segments")
    def test_transitions_applied(self, mock_create, mock_trans, mock_apply, tmp_path):
        mock_create.return_value = [
            {"clip_id": 1, "path": "/clip1.mp4", "filename": "clip1.mp4"},
            {"clip_id": 2, "path": "/clip2.mp4", "filename": "clip2.mp4"},
        ]
        mock_trans.return_value = ["/trans1.mp4"]
        mock_apply.return_value = True

        result = create_clips_with_transitions(
            Path("/video.mp4"), [{}, {}], tmp_path
        )
        assert len(result) == 2
        # First clip has no transition, second does
        assert result[1].get("has_transition") is True

    @patch("src.clip_assembly.apply_transition_effect")
    @patch("src.clip_assembly.get_available_transitions")
    @patch("src.clip_assembly.create_clips_from_segments")
    def test_transition_failure_uses_original(self, mock_create, mock_trans,
                                              mock_apply, tmp_path):
        """Failed transition falls back to original clip (lines 663-667)."""
        mock_create.return_value = [
            {"clip_id": 1, "path": "/clip1.mp4", "filename": "clip1.mp4"},
            {"clip_id": 2, "path": "/clip2.mp4", "filename": "clip2.mp4"},
        ]
        mock_trans.return_value = ["/trans1.mp4"]
        mock_apply.return_value = False

        result = create_clips_with_transitions(
            Path("/video.mp4"), [{}, {}], tmp_path
        )
        assert len(result) == 2
        assert result[1].get("has_transition") is None  # Original, no transition

    @patch("src.clip_assembly.apply_transition_effect")
    @patch("src.clip_assembly.get_available_transitions")
    @patch("src.clip_assembly.create_clips_from_segments")
    def test_multiple_clips_cycle_transitions(self, mock_create, mock_trans,
                                              mock_apply, tmp_path):
        """Transitions cycle through available files."""
        mock_create.return_value = [
            {"clip_id": 1, "path": "/c1.mp4", "filename": "c1.mp4"},
            {"clip_id": 2, "path": "/c2.mp4", "filename": "c2.mp4"},
            {"clip_id": 3, "path": "/c3.mp4", "filename": "c3.mp4"},
        ]
        mock_trans.return_value = ["/t1.mp4", "/t2.mp4"]
        mock_apply.return_value = True

        result = create_clips_with_transitions(
            Path("/video.mp4"), [{}, {}, {}], tmp_path
        )
        assert len(result) == 3


# end tests/unit/test_clip_assembly.py
