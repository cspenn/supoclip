# start tests/unit/test_subtitles.py
"""
Unit tests for backend/src/subtitles.py

Covers: SubtitleWordFilter, SubtitleTextClipCreator, SubtitlePositioner,
SubtitleClipBuilder, VideoProcessor, create_subtitles
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

backend_root = Path(__file__).parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


# We need to mock Config before importing subtitles
with patch("src.config.Config"):
    with patch("src.subtitles.config", MagicMock()):
        from src.subtitles import (
            SubtitleWordFilter,
            SubtitleTextClipCreator,
            SubtitlePositioner,
            SubtitleClipBuilder,
            VideoProcessor,
            create_subtitles,
        )


# ---------------------------------------------------------------------------
# SubtitleWordFilter.get_relevant_words (lines 39-66)
# ---------------------------------------------------------------------------
class TestSubtitleWordFilter:
    def test_basic_extraction(self):
        transcript_data = {
            "words": [
                {"text": "hello", "start": 1000, "end": 1500, "confidence": 0.9},
                {"text": "world", "start": 2000, "end": 2500, "confidence": 0.95},
                {"text": "extra", "start": 6000, "end": 6500},
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 500, 5000)
        assert len(result) == 2
        assert result[0]["text"] == "hello"
        assert result[1]["text"] == "world"

    def test_relative_timing(self):
        transcript_data = {
            "words": [
                {"text": "word", "start": 2000, "end": 2500},
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 1000, 5000)
        assert len(result) == 1
        # Relative start = (2000 - 1000) / 1000 = 1.0s
        assert result[0]["start"] == pytest.approx(1.0)

    def test_end_time_capped(self):
        """End time should not exceed clip duration."""
        transcript_data = {
            "words": [
                {"text": "word", "start": 2000, "end": 6000},  # end extends past clip
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 1000, 5000)
        assert len(result) == 1
        # Relative end = min((5000-1000)/1000, (6000-1000)/1000) = 4.0
        assert result[0]["end"] == pytest.approx(4.0)

    def test_no_words_in_range(self):
        transcript_data = {
            "words": [
                {"text": "word", "start": 10000, "end": 10500},
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert result == []

    def test_empty_words(self):
        transcript_data = {"words": []}
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert result == []

    def test_no_words_key(self):
        transcript_data = {}
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert result == []

    def test_word_end_before_start_filtered(self):
        """If relative_end <= relative_start, word is skipped."""
        transcript_data = {
            "words": [
                {"text": "word", "start": 4999, "end": 4999},  # zero duration
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert result == []

    def test_default_confidence(self):
        transcript_data = {
            "words": [
                {"text": "word", "start": 1000, "end": 1500},
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert result[0]["confidence"] == 1.0

    def test_first_words_logged(self):
        """When words found, first 3 should be logged (lines 62-65)."""
        transcript_data = {
            "words": [
                {"text": "a", "start": 100, "end": 200},
                {"text": "b", "start": 200, "end": 300},
                {"text": "c", "start": 300, "end": 400},
                {"text": "d", "start": 400, "end": 500},
            ]
        }
        result = SubtitleWordFilter.get_relevant_words(transcript_data, 0, 5000)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# SubtitleTextClipCreator._create_clip_candidate (lines 104-134)
# ---------------------------------------------------------------------------
class TestSubtitleTextClipCreator:
    @patch("src.subtitles.BrowserSubtitleRenderer")
    @patch("src.subtitles.ImageClip")
    def test_create_clip_candidate_success(self, mock_imageclip, mock_renderer_cls):
        mock_renderer = MagicMock()
        mock_renderer.__enter__ = MagicMock(return_value=mock_renderer)
        mock_renderer.__exit__ = MagicMock(return_value=False)
        mock_renderer.render_text_to_image.return_value = Path("/fake/image.png")
        mock_renderer_cls.return_value = mock_renderer

        mock_clip = MagicMock()
        mock_imageclip.return_value = mock_clip

        result = SubtitleTextClipCreator._create_clip_candidate(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result == mock_clip

    @patch("src.subtitles.BrowserSubtitleRenderer")
    def test_create_clip_candidate_render_none(self, mock_renderer_cls):
        mock_renderer = MagicMock()
        mock_renderer.__enter__ = MagicMock(return_value=mock_renderer)
        mock_renderer.__exit__ = MagicMock(return_value=False)
        mock_renderer.render_text_to_image.return_value = None
        mock_renderer_cls.return_value = mock_renderer

        result = SubtitleTextClipCreator._create_clip_candidate(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result is None

    @patch("src.subtitles.BrowserSubtitleRenderer")
    def test_create_clip_candidate_exception(self, mock_renderer_cls):
        mock_renderer_cls.side_effect = RuntimeError("browser fail")

        result = SubtitleTextClipCreator._create_clip_candidate(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result is None

    @patch("src.subtitles.BrowserSubtitleRenderer")
    @patch("src.subtitles.ImageClip")
    def test_create_clip_candidate_with_style_options(self, mock_imageclip, mock_renderer_cls):
        mock_renderer = MagicMock()
        mock_renderer.__enter__ = MagicMock(return_value=mock_renderer)
        mock_renderer.__exit__ = MagicMock(return_value=False)
        mock_renderer.render_text_to_image.return_value = Path("/fake/image.png")
        mock_renderer_cls.return_value = mock_renderer

        mock_clip = MagicMock()
        mock_imageclip.return_value = mock_clip

        style = {
            "stroke_width": 2,
            "stroke_color": "white",
            "shadow_color": "gray",
            "shadow_offset": 3,
            "text_transform": "uppercase",
            "font_weight": "normal",
        }

        result = SubtitleTextClipCreator._create_clip_candidate(
            "hello", "/font.ttf", 24, "#FFFFFF", 500, style
        )
        assert result == mock_clip

    # -----------------------------------------------------------------------
    # SubtitleTextClipCreator.create_text_clip (lines 161-209)
    # -----------------------------------------------------------------------
    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_success_first_attempt(self, mock_create):
        mock_clip = MagicMock()
        mock_clip.size = (400, 30)  # Small enough: 30 / (24*1.5) = 0.83 lines < 2
        mock_clip.with_effects.return_value = mock_clip
        mock_create.return_value = mock_clip

        result = SubtitleTextClipCreator.create_text_clip(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result is not None

    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_none_returns_none(self, mock_create):
        mock_create.return_value = None

        result = SubtitleTextClipCreator.create_text_clip(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result is None

    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_reduces_font_size(self, mock_create):
        """Too many lines triggers font size reduction (lines 200-209)."""
        large_clip = MagicMock()
        large_clip.size = (400, 200)  # 200 / (24*1.5) = 5.55 lines > 2
        large_clip.with_effects.return_value = large_clip

        small_clip = MagicMock()
        small_clip.size = (400, 30)  # fits
        small_clip.with_effects.return_value = small_clip

        mock_create.side_effect = [large_clip, small_clip]

        result = SubtitleTextClipCreator.create_text_clip(
            "long text", "/font.ttf", 24, "#FFFFFF", 500
        )
        assert result == small_clip

    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_min_font_last_attempt(self, mock_create):
        """At min font size on last attempt, return what we have (lines 204-207)."""
        big_clip = MagicMock()
        big_clip.size = (400, 200)  # too tall
        big_clip.with_effects.return_value = big_clip

        # Make all 3 attempts return too-tall clips
        mock_create.side_effect = [big_clip, big_clip, big_clip]

        # Start with a font size that will reduce to below MIN_FONT_SIZE
        result = SubtitleTextClipCreator.create_text_clip(
            "text", "/font.ttf", 18, "#FFFFFF", 500
        )
        # On last attempt with font < MIN, should return the clip
        assert result is not None

    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_no_size_attr(self, mock_create):
        """Clip without size attribute uses default height 40 (line 192)."""
        mock_clip = MagicMock()
        mock_clip.size = None
        mock_clip.with_effects.return_value = mock_clip

        mock_create.return_value = mock_clip

        result = SubtitleTextClipCreator.create_text_clip(
            "hello", "/font.ttf", 24, "#FFFFFF", 500
        )
        # 40 / (24*1.5) = 1.11 < 2, so should return
        assert result is not None

    @patch.object(SubtitleTextClipCreator, "_create_clip_candidate")
    def test_create_text_clip_all_attempts_fail(self, mock_create):
        """All 3 attempts return None."""
        mock_create.return_value = None

        result = SubtitleTextClipCreator.create_text_clip(
            "hello", "/font.ttf", 40, "#FFFFFF", 500
        )
        assert result is None


# ---------------------------------------------------------------------------
# SubtitlePositioner (lines 234-257)
# ---------------------------------------------------------------------------
class TestSubtitlePositioner:
    def test_default_position(self):
        result = SubtitlePositioner.calculate_position(1080, 40)
        assert result[0] == "center"
        assert isinstance(result[1], int)

    def test_with_position_options_centered(self):
        options = {"x": 0.5, "y": 0.7, "alignment": "center"}
        result = SubtitlePositioner.calculate_position(1080, 40, 720, options)
        assert result[0] == "center"
        assert isinstance(result[1], int)

    def test_with_position_options_left(self):
        options = {"x": 0.2, "y": 0.7, "alignment": "left"}
        result = SubtitlePositioner.calculate_position(1080, 40, 720, options)
        # Non-center alignment with x != 0.5
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_with_position_options_no_x(self):
        """Position options without 'x' key (line 251)."""
        options = {"y": 0.7, "alignment": "left"}
        result = SubtitlePositioner.calculate_position(1080, 40, 720, options)
        assert result[0] == "center"

    def test_position_options_x_center_alignment_center(self):
        """x=0.5 and alignment=center => 'center' (line 252-253)."""
        options = {"x": 0.5, "y": 0.65, "alignment": "center"}
        result = SubtitlePositioner.calculate_position(1080, 40, 720, options)
        assert result[0] == "center"


# ---------------------------------------------------------------------------
# SubtitleClipBuilder (lines 292-334)
# ---------------------------------------------------------------------------
class TestSubtitleClipBuilder:
    @patch.object(SubtitleTextClipCreator, "create_text_clip")
    def test_build_clips_success(self, mock_create):
        mock_clip = MagicMock()
        mock_clip.size = (400, 40)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_create.return_value = mock_clip

        words = [
            {"text": "hello", "start": 0.0, "end": 0.5},
            {"text": "world", "start": 0.5, "end": 1.0},
        ]

        result = SubtitleClipBuilder.build_clips(
            words, "/font.ttf", 24, "#FFFFFF", 720, 1280
        )
        assert len(result) == 2

    @patch.object(SubtitleTextClipCreator, "create_text_clip")
    def test_build_clips_skip_short_word(self, mock_create):
        """Words shorter than 50ms are skipped (line 300)."""
        words = [
            {"text": "a", "start": 0.0, "end": 0.01},  # < 50ms
            {"text": "hello", "start": 0.5, "end": 1.0},
        ]

        mock_clip = MagicMock()
        mock_clip.size = (400, 40)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_create.return_value = mock_clip

        result = SubtitleClipBuilder.build_clips(
            words, "/font.ttf", 24, "#FFFFFF", 720, 1280
        )
        assert len(result) == 1  # Only "hello"

    @patch.object(SubtitleTextClipCreator, "create_text_clip")
    def test_build_clips_create_returns_none(self, mock_create):
        mock_create.return_value = None

        words = [{"text": "hello", "start": 0.0, "end": 0.5}]

        result = SubtitleClipBuilder.build_clips(
            words, "/font.ttf", 24, "#FFFFFF", 720, 1280
        )
        assert len(result) == 0

    @patch.object(SubtitleTextClipCreator, "create_text_clip")
    def test_build_clips_exception_continues(self, mock_create):
        """Exception creating clip for one word doesn't stop others (line 329-331)."""
        mock_create.side_effect = [RuntimeError("fail"), MagicMock()]

        # Configure second mock properly
        good_clip = MagicMock()
        good_clip.size = (400, 40)
        good_clip.with_duration.return_value = good_clip
        good_clip.with_start.return_value = good_clip
        good_clip.with_position.return_value = good_clip
        mock_create.side_effect = [RuntimeError("fail"), good_clip]

        words = [
            {"text": "hello", "start": 0.0, "end": 0.5},
            {"text": "world", "start": 0.5, "end": 1.0},
        ]

        result = SubtitleClipBuilder.build_clips(
            words, "/font.ttf", 24, "#FFFFFF", 720, 1280
        )
        assert len(result) == 1

    @patch.object(SubtitleTextClipCreator, "create_text_clip")
    def test_build_clips_with_style_and_position(self, mock_create):
        mock_clip = MagicMock()
        mock_clip.size = (400, 40)
        mock_clip.with_duration.return_value = mock_clip
        mock_clip.with_start.return_value = mock_clip
        mock_clip.with_position.return_value = mock_clip
        mock_create.return_value = mock_clip

        words = [{"text": "hello", "start": 0.0, "end": 0.5}]
        style = {"stroke_width": 2}
        position = {"x": 0.5, "y": 0.7}

        result = SubtitleClipBuilder.build_clips(
            words, "/font.ttf", 24, "#FFFFFF", 720, 1280, style, position
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# VideoProcessor
# ---------------------------------------------------------------------------
class TestVideoProcessor:
    @patch("src.subtitles.VideoProcessor.__init__", return_value=None)
    def test_get_optimal_encoding_high(self, mock_init):
        p = VideoProcessor.__new__(VideoProcessor)
        result = p.get_optimal_encoding_settings("high")
        assert result["codec"] == "libx264"
        assert result["bitrate"] == "8000k"

    @patch("src.subtitles.VideoProcessor.__init__", return_value=None)
    def test_get_optimal_encoding_medium(self, mock_init):
        p = VideoProcessor.__new__(VideoProcessor)
        result = p.get_optimal_encoding_settings("medium")
        assert result["bitrate"] == "4000k"

    @patch("src.subtitles.VideoProcessor.__init__", return_value=None)
    def test_get_optimal_encoding_unknown_defaults_high(self, mock_init):
        p = VideoProcessor.__new__(VideoProcessor)
        result = p.get_optimal_encoding_settings("ultra")
        assert result["bitrate"] == "8000k"


# ---------------------------------------------------------------------------
# create_subtitles (lines 428-429, 438-465)
# ---------------------------------------------------------------------------
class TestCreateSubtitles:
    @patch("src.subtitles.load_cached_transcript_data")
    def test_no_transcript_data(self, mock_load):
        mock_load.return_value = None
        result = create_subtitles(
            Path("/fake/video.mp4"), 0.0, 5.0, 720, 1280
        )
        assert result == []

    @patch("src.subtitles.load_cached_transcript_data")
    def test_empty_words(self, mock_load):
        mock_load.return_value = {"words": []}
        result = create_subtitles(
            Path("/fake/video.mp4"), 0.0, 5.0, 720, 1280
        )
        assert result == []

    @patch("src.subtitles.SubtitleClipBuilder.build_clips")
    @patch("src.subtitles.SubtitleWordFilter.get_relevant_words")
    @patch("src.subtitles.VideoProcessor")
    @patch("src.subtitles.load_cached_transcript_data")
    def test_successful_creation(self, mock_load, mock_processor_cls, mock_filter, mock_build):
        mock_load.return_value = {
            "words": [{"text": "hello", "start": 1000, "end": 1500}]
        }
        mock_filter.return_value = [
            {"text": "hello", "start": 1.0, "end": 1.5, "confidence": 0.9}
        ]

        mock_processor = MagicMock()
        mock_processor.font_path = "/font.ttf"
        mock_processor_cls.return_value = mock_processor

        mock_clip = MagicMock()
        mock_build.return_value = [mock_clip]

        result = create_subtitles(
            Path("/fake/video.mp4"), 0.0, 5.0, 720, 1280,
            font_family="TestFont", font_size=24, font_color="#FFF",
            subtitle_style={"stroke_width": 1},
            subtitle_position={"x": 0.5, "y": 0.7},
        )
        assert len(result) == 1

    @patch("src.subtitles.SubtitleWordFilter.get_relevant_words")
    @patch("src.subtitles.VideoProcessor")
    @patch("src.subtitles.load_cached_transcript_data")
    def test_no_relevant_words(self, mock_load, mock_processor_cls, mock_filter):
        mock_load.return_value = {
            "words": [{"text": "hello", "start": 1000, "end": 1500}]
        }
        mock_filter.return_value = []

        result = create_subtitles(
            Path("/fake/video.mp4"), 0.0, 5.0, 720, 1280
        )
        assert result == []

    @patch("src.subtitles.load_cached_transcript_data")
    def test_transcript_with_words_logged(self, mock_load):
        """Lines 428-429: words found in transcript data trigger logging."""
        mock_load.return_value = {
            "words": [{"text": "hello", "start": 1000, "end": 1500}]
        }
        # Even though words exist, SubtitleWordFilter may return empty,
        # but the log lines (428-429) are covered
        with patch("src.subtitles.SubtitleWordFilter.get_relevant_words", return_value=[]):
            result = create_subtitles(
                Path("/fake/video.mp4"), 0.0, 5.0, 720, 1280
            )
            assert result == []


# end tests/unit/test_subtitles.py
