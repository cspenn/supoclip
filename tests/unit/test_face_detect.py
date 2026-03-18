# start tests/unit/test_face_detect.py
"""Unit tests for src/pipeline/face_detect.py.

Tests cover:
- round_to_even with odd/even integers
- calculate_crop_box with face center, center fallback, and clamping behaviour
- detect_face_center with MediaPipe mocked (no real inference)
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.pipeline.face_detect import (
    calculate_crop_box,
    detect_face_center,
    get_representative_frame,
    round_to_even,
)


# ---------------------------------------------------------------------------
# round_to_even
# ---------------------------------------------------------------------------
class TestRoundToEven:
    def test_even_number_unchanged(self) -> None:
        assert round_to_even(1080) == 1080

    def test_odd_number_decremented(self) -> None:
        assert round_to_even(1081) == 1080

    def test_zero_is_even(self) -> None:
        assert round_to_even(0) == 0

    def test_one_becomes_zero(self) -> None:
        assert round_to_even(1) == 0

    def test_small_even(self) -> None:
        assert round_to_even(4) == 4

    def test_small_odd(self) -> None:
        assert round_to_even(5) == 4


# ---------------------------------------------------------------------------
# calculate_crop_box — face center supplied
# ---------------------------------------------------------------------------
class TestCalculateCropBoxWithFace:
    def test_crop_centered_on_face(self) -> None:
        """Crop box x-midpoint should equal the face x coordinate."""
        x, y, w, h = calculate_crop_box(
            frame_width=1920,
            frame_height=1080,
            face_center=(960, 540),
        )
        crop_center_x = x + w // 2
        # Allow ±2 px for even-rounding adjustments.
        assert abs(crop_center_x - 960) <= 2

    def test_crop_aspect_ratio_is_9_16(self) -> None:
        """Output dimensions must satisfy 9:16 aspect ratio (within rounding)."""
        _, _, w, h = calculate_crop_box(
            frame_width=1920,
            frame_height=1080,
            face_center=(960, 540),
        )
        ratio = w / h
        assert pytest.approx(ratio, abs=0.01) == 9 / 16

    def test_all_dimensions_are_even(self) -> None:
        """All returned integers must be even for H.264 compatibility."""
        x, y, w, h = calculate_crop_box(
            frame_width=1920,
            frame_height=1080,
            face_center=(960, 540),
        )
        assert x % 2 == 0
        assert y % 2 == 0
        assert w % 2 == 0
        assert h % 2 == 0

    def test_custom_target_dimensions(self) -> None:
        """Custom target_width/target_height should be respected."""
        _, _, w, h = calculate_crop_box(
            frame_width=1920,
            frame_height=1080,
            face_center=(960, 540),
            target_width=540,
            target_height=960,
        )
        ratio = w / h
        assert pytest.approx(ratio, abs=0.01) == 9 / 16


# ---------------------------------------------------------------------------
# calculate_crop_box — no face (center fallback)
# ---------------------------------------------------------------------------
class TestCalculateCropBoxCenterFallback:
    def test_no_face_produces_center_crop(self) -> None:
        """Without a face center, the crop should be centred on the frame."""
        x, y, w, h = calculate_crop_box(
            frame_width=1920,
            frame_height=1080,
            face_center=None,
        )
        # For a 1920×1080 source the crop is 607×1080 (height-constrained),
        # centred horizontally.
        expected_x = (1920 - w) // 2
        assert abs(x - expected_x) <= 2

    def test_none_face_still_produces_valid_box(self) -> None:
        x, y, w, h = calculate_crop_box(1280, 720, None)
        assert w > 0
        assert h > 0
        assert x >= 0
        assert y >= 0


# ---------------------------------------------------------------------------
# calculate_crop_box — clamping to frame bounds
# ---------------------------------------------------------------------------
class TestCalculateCropBoxClamping:
    def test_x_clamped_when_face_near_left_edge(self) -> None:
        x, y, w, h = calculate_crop_box(1920, 1080, face_center=(10, 540))
        assert x >= 0

    def test_x_clamped_when_face_near_right_edge(self) -> None:
        x, y, w, h = calculate_crop_box(1920, 1080, face_center=(1910, 540))
        assert x + w <= 1920

    def test_y_clamped_when_face_near_top(self) -> None:
        x, y, w, h = calculate_crop_box(1920, 1080, face_center=(960, 5))
        assert y >= 0

    def test_y_clamped_when_face_near_bottom(self) -> None:
        x, y, w, h = calculate_crop_box(1920, 1080, face_center=(960, 1075))
        assert y + h <= 1080

    def test_portrait_source_frame(self) -> None:
        """Portrait source (already 9:16) should return the full frame."""
        x, y, w, h = calculate_crop_box(1080, 1920, face_center=None)
        assert w == 1080
        assert h == 1920
        assert x == 0
        assert y == 0


# ---------------------------------------------------------------------------
# detect_face_center — MediaPipe mocked
# ---------------------------------------------------------------------------
class TestDetectFaceCenter:
    def _make_detection(
        self,
        xmin: float,
        ymin: float,
        width: float,
        height: float,
        score: float,
    ) -> MagicMock:
        """Build a minimal mock that looks like a MediaPipe detection."""
        detection = MagicMock()
        detection.location_data.relative_bounding_box.xmin = xmin
        detection.location_data.relative_bounding_box.ymin = ymin
        detection.location_data.relative_bounding_box.width = width
        detection.location_data.relative_bounding_box.height = height
        detection.score = [score]
        return detection

    def _mock_mediapipe(self, detections: list[MagicMock]) -> MagicMock:
        """Return a mock mediapipe module with the given detections."""
        mp = MagicMock()
        detector_instance = MagicMock()
        results = MagicMock()
        results.detections = detections
        detector_instance.__enter__ = MagicMock(return_value=detector_instance)
        detector_instance.__exit__ = MagicMock(return_value=False)
        detector_instance.process.return_value = results
        mp.solutions.face_detection.FaceDetection.return_value = detector_instance
        return mp

    def test_returns_face_center(self) -> None:
        """A 30%-wide face centred at 50% should yield ~(100, 100) on a 200×200 frame."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        detection = self._make_detection(0.35, 0.35, 0.30, 0.30, 0.9)
        mp_mock = self._mock_mediapipe([detection])

        with patch.dict("sys.modules", {"mediapipe": mp_mock}):
            result = detect_face_center(frame)

        assert result is not None
        cx, cy = result
        # Face spans x: 70–130, y: 70–130 → centre at (100, 100)
        assert abs(cx - 100) <= 2
        assert abs(cy - 100) <= 2

    def test_returns_none_when_no_detections(self) -> None:
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        mp_mock = self._mock_mediapipe([])
        with patch.dict("sys.modules", {"mediapipe": mp_mock}):
            result = detect_face_center(frame)
        assert result is None

    def test_returns_none_when_mediapipe_missing(self) -> None:
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Setting sys.modules["mediapipe"] = None causes `import mediapipe`
        # inside the function to raise ImportError without touching builtins.
        with patch.dict("sys.modules", {"mediapipe": None}):
            result = detect_face_center(frame)
        assert result is None

    def test_small_face_ignored(self) -> None:
        """Faces smaller than 30 px should be filtered out."""
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        # 0.02 * 1000 = 20 px → below the 30 px threshold
        detection = self._make_detection(0.0, 0.0, 0.02, 0.02, 0.99)
        mp_mock = self._mock_mediapipe([detection])

        with patch.dict("sys.modules", {"mediapipe": mp_mock}):
            result = detect_face_center(frame)
        assert result is None

    def test_picks_highest_confidence_face(self) -> None:
        """When multiple faces qualify, the one with the highest score wins."""
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        low_conf = self._make_detection(0.1, 0.1, 0.2, 0.2, 0.6)
        high_conf = self._make_detection(0.5, 0.5, 0.2, 0.2, 0.95)
        mp_mock = self._mock_mediapipe([low_conf, high_conf])

        with patch.dict("sys.modules", {"mediapipe": mp_mock}):
            result = detect_face_center(frame)

        assert result is not None
        cx, _ = result
        # High-confidence face is at x=0.5*500=250, width=0.2*500=100 → cx=300
        assert abs(cx - 300) <= 2

    def test_face_outside_relative_area_bounds_ignored(self) -> None:
        """A face larger than _MAX_RELATIVE_AREA (0.3) of the frame is filtered out."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Face is 0.8 * 200 = 160 px wide/tall (> 30 px threshold) but
        # relative_area = 0.8 * 0.8 = 0.64, which exceeds _MAX_RELATIVE_AREA (0.3).
        detection = self._make_detection(0.1, 0.1, 0.8, 0.8, 0.99)
        mp_mock = self._mock_mediapipe([detection])

        with patch.dict("sys.modules", {"mediapipe": mp_mock}):
            result = detect_face_center(frame)
        assert result is None

    def test_detection_exception_returns_none(self) -> None:
        """If MediaPipe raises an exception, return None gracefully."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        mp = MagicMock()
        detector_instance = MagicMock()
        detector_instance.__enter__ = MagicMock(side_effect=RuntimeError("crash"))
        detector_instance.__exit__ = MagicMock(return_value=False)
        mp.solutions.face_detection.FaceDetection.return_value = detector_instance

        with patch.dict("sys.modules", {"mediapipe": mp}):
            result = detect_face_center(frame)
        assert result is None


# ---------------------------------------------------------------------------
# get_representative_frame
# ---------------------------------------------------------------------------
class TestGetRepresentativeFrame:
    def test_returns_none_when_cv2_missing(self) -> None:
        # Setting sys.modules["cv2"] = None causes `import cv2` to raise
        # ImportError without patching builtins globally.
        with patch.dict("sys.modules", {"cv2": None}):
            result = get_representative_frame("/fake/path.mp4")
        assert result is None

    def test_returns_frame_when_cv2_available(self) -> None:
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2_mock = MagicMock()
        cap_mock = MagicMock()
        cap_mock.get.return_value = 30.0
        cap_mock.read.return_value = (True, mock_frame)
        cv2_mock.VideoCapture.return_value = cap_mock

        with patch.dict("sys.modules", {"cv2": cv2_mock}):
            result = get_representative_frame("/fake/path.mp4", timestamp_s=1.0)

        assert result is not None
        assert result.shape == (480, 640, 3)
        cap_mock.release.assert_called_once()

    def test_returns_none_on_read_failure(self) -> None:
        cv2_mock = MagicMock()
        cap_mock = MagicMock()
        cap_mock.get.return_value = 25.0
        cap_mock.read.return_value = (False, None)
        cv2_mock.VideoCapture.return_value = cap_mock

        with patch.dict("sys.modules", {"cv2": cv2_mock}):
            result = get_representative_frame("/fake/path.mp4")

        assert result is None
        cap_mock.release.assert_called_once()

    def test_cap_released_on_exception(self) -> None:
        cv2_mock = MagicMock()
        cap_mock = MagicMock()
        cap_mock.get.side_effect = RuntimeError("boom")
        cv2_mock.VideoCapture.return_value = cap_mock

        with patch.dict("sys.modules", {"cv2": cv2_mock}):
            result = get_representative_frame("/fake/path.mp4")

        assert result is None
        cap_mock.release.assert_called_once()


# end tests/unit/test_face_detect.py
