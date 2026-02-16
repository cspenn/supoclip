# start tests/unit/test_cropping.py
"""
Unit tests for backend/src/cropping.py

Covers: round_to_even, TargetDimensionCalculator, FaceCenteredCropCalculator,
CenterCropCalculator, detect_optimal_crop_region
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

backend_root = Path(__file__).parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from src.cropping import (
    round_to_even,
    TargetDimensionCalculator,
    FaceCenteredCropCalculator,
    CenterCropCalculator,
    detect_optimal_crop_region,
)


# ---------------------------------------------------------------------------
# round_to_even
# ---------------------------------------------------------------------------
class TestRoundToEven:
    def test_even_stays_even(self):
        assert round_to_even(10) == 10

    def test_odd_rounds_down(self):
        assert round_to_even(11) == 10

    def test_zero(self):
        assert round_to_even(0) == 0

    def test_one(self):
        assert round_to_even(1) == 0


# ---------------------------------------------------------------------------
# TargetDimensionCalculator (lines 48-49)
# ---------------------------------------------------------------------------
class TestTargetDimensionCalculator:
    def test_wide_video(self):
        """16:9 video -> 9:16 target = height-constrained."""
        w, h = TargetDimensionCalculator.calculate(1920, 1080, 9 / 16)
        assert w == round_to_even(int(1080 * 9 / 16))
        assert h == round_to_even(1080)

    def test_narrow_video(self):
        """Already narrow -> width-constrained (lines 48-49)."""
        # If w/h < target_ratio, we use width-constrained path
        w, h = TargetDimensionCalculator.calculate(100, 1000, 9 / 16)
        assert w == round_to_even(100)
        assert h == round_to_even(int(100 / (9 / 16)))

    def test_square_video(self):
        w, h = TargetDimensionCalculator.calculate(1000, 1000, 9 / 16)
        # 1000/1000 = 1.0 > 9/16 = 0.5625 => height-constrained
        assert w == round_to_even(int(1000 * 9 / 16))
        assert h == round_to_even(1000)


# ---------------------------------------------------------------------------
# FaceCenteredCropCalculator (lines 79-104)
# ---------------------------------------------------------------------------
class TestFaceCenteredCropCalculator:
    def test_basic_face_centering(self):
        """Test normal face-centered crop."""
        faces = [(300.0, 300.0, 10000.0, 0.9)]
        x, y = FaceCenteredCropCalculator.calculate(
            faces, 200, 400, 600, 800
        )
        # Should be centered around face, clamped to valid range
        assert x % 2 == 0  # Even
        assert y % 2 == 0  # Even
        assert 0 <= x <= 600 - 200
        assert 0 <= y <= 800 - 400

    def test_zero_total_weight_falls_back_to_center(self):
        """When all areas * confidence = 0, fallback to center crop (line 80-83)."""
        faces = [(100.0, 100.0, 0.0, 0.9)]  # area=0 => weight=0
        x, y = FaceCenteredCropCalculator.calculate(
            faces, 200, 400, 600, 800
        )
        # Should be center crop
        expected_x, expected_y = CenterCropCalculator.calculate(200, 400, 600, 800)
        assert x == expected_x
        assert y == expected_y

    def test_multiple_faces_weighted(self):
        """Multiple faces are weighted by area * confidence."""
        faces = [
            (100.0, 100.0, 5000.0, 0.8),
            (400.0, 400.0, 10000.0, 0.9),
        ]
        x, y = FaceCenteredCropCalculator.calculate(
            faces, 200, 400, 600, 800
        )
        assert x % 2 == 0
        assert y % 2 == 0

    def test_offset_clamped_to_bounds(self):
        """Face at edge should clamp offset."""
        faces = [(10.0, 10.0, 5000.0, 0.9)]  # Very top-left
        x, y = FaceCenteredCropCalculator.calculate(
            faces, 200, 400, 600, 800
        )
        assert x >= 0
        assert y >= 0

    def test_face_at_bottom_right(self):
        faces = [(580.0, 780.0, 5000.0, 0.9)]
        x, y = FaceCenteredCropCalculator.calculate(
            faces, 200, 400, 600, 800
        )
        assert x <= 600 - 200
        assert y <= 800 - 400


# ---------------------------------------------------------------------------
# CenterCropCalculator
# ---------------------------------------------------------------------------
class TestCenterCropCalculator:
    def test_normal_center(self):
        x, y = CenterCropCalculator.calculate(200, 400, 600, 800)
        assert x == round_to_even((600 - 200) // 2)
        assert y == round_to_even((800 - 400) // 2)

    def test_crop_size_equals_original(self):
        x, y = CenterCropCalculator.calculate(600, 800, 600, 800)
        assert x == 0
        assert y == 0

    def test_crop_larger_than_original(self):
        x, y = CenterCropCalculator.calculate(1000, 1200, 600, 800)
        assert x == 0
        assert y == 0


# ---------------------------------------------------------------------------
# detect_optimal_crop_region (lines 164-174, 188-199)
# ---------------------------------------------------------------------------
class TestDetectOptimalCropRegion:
    @patch("src.cropping.detect_faces_in_clip")
    def test_with_faces(self, mock_detect):
        """Face detection path (lines 164-174)."""
        mock_detect.return_value = [
            (300, 300, 5000, 0.9),
        ]

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)

        x, y, w, h = detect_optimal_crop_region(mock_clip, 0.0, 5.0)
        assert w % 2 == 0
        assert h % 2 == 0
        assert w > 0
        assert h > 0

    @patch("src.cropping.detect_faces_in_clip")
    def test_no_faces_center_crop(self, mock_detect):
        mock_detect.return_value = []

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)

        x, y, w, h = detect_optimal_crop_region(mock_clip, 0.0, 5.0)
        assert w > 0
        assert h > 0

    @patch("src.cropping.detect_faces_in_clip")
    def test_exception_fallback(self, mock_detect):
        """Exception path falls back to center crop (lines 188-199)."""
        mock_detect.side_effect = RuntimeError("detection failed")

        mock_clip = MagicMock()
        mock_clip.size = (1920, 1080)

        x, y, w, h = detect_optimal_crop_region(mock_clip, 0.0, 5.0)
        # Should still return valid dimensions
        assert w > 0
        assert h > 0
        assert w % 2 == 0
        assert h % 2 == 0


# end tests/unit/test_cropping.py
