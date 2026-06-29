# start tests/unit/test_face_detect.py
"""Unit tests for src/pipeline/face_detect.py.

Tests cover:
- round_to_even with odd/even integers
- calculate_crop_box with face center, center fallback, clamping, and the
  positive-dimension guard (L-4)
- detect_face_center filtering/selection logic (raw detection boundary mocked)
- _detect_raw parsing of MediaPipe Tasks output (mediapipe I/O mocked)
- _get_face_detector / _resolve_face_model graceful unavailability
- a REAL detection run against the committed sample_video.mp4 fixture that must
  return None or a valid center without raising
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.pipeline.face_detect import (
    _FACE_MODEL_FILENAME,
    _detect_raw,
    _get_face_detector,
    _resolve_face_model,
    _segment_sample_timestamps,
    calculate_crop_box,
    detect_face_center,
    detect_face_center_multi,
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
# calculate_crop_box — positive-dimension guard (L-4)
# ---------------------------------------------------------------------------
class TestCalculateCropBoxGuards:
    def test_zero_frame_width_raises(self) -> None:
        with pytest.raises(ValueError):
            calculate_crop_box(0, 1080, None)

    def test_zero_frame_height_raises(self) -> None:
        """A zero height must raise before the ratio division (no ZeroDivision)."""
        with pytest.raises(ValueError):
            calculate_crop_box(1920, 0, None)

    def test_negative_frame_dimension_raises(self) -> None:
        with pytest.raises(ValueError):
            calculate_crop_box(-100, 200, None)

    def test_zero_target_width_raises(self) -> None:
        with pytest.raises(ValueError):
            calculate_crop_box(1920, 1080, None, target_width=0)

    def test_negative_target_height_raises(self) -> None:
        with pytest.raises(ValueError):
            calculate_crop_box(1920, 1080, None, target_height=-1)


# ---------------------------------------------------------------------------
# detect_face_center — raw-detection boundary mocked
# ---------------------------------------------------------------------------
class TestDetectFaceCenter:
    """Verifies filtering/selection logic over absolute-pixel detections."""

    def test_returns_face_center(self) -> None:
        """A 60×60 box at (70,70) on a 200×200 frame yields center (100, 100)."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # relative_area = 3600 / 40000 = 0.09 → within (0.005, 0.3)
        with patch(
            "src.pipeline.face_detect._detect_raw",
            return_value=[(70, 70, 60, 60, 0.9)],
        ):
            result = detect_face_center(frame)

        assert result is not None
        cx, cy = result
        assert abs(cx - 100) <= 2
        assert abs(cy - 100) <= 2

    def test_returns_none_when_no_detections(self) -> None:
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        with patch("src.pipeline.face_detect._detect_raw", return_value=[]):
            assert detect_face_center(frame) is None

    def test_returns_none_when_detection_unavailable(self) -> None:
        """_detect_raw returning None (model/mediapipe absent) → None, no raise."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        with patch("src.pipeline.face_detect._detect_raw", return_value=None):
            assert detect_face_center(frame) is None

    def test_small_face_ignored(self) -> None:
        """Faces with an edge ≤ 30 px are filtered out."""
        frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
        with patch(
            "src.pipeline.face_detect._detect_raw",
            return_value=[(0, 0, 20, 20, 0.99)],
        ):
            assert detect_face_center(frame) is None

    def test_picks_highest_confidence_face(self) -> None:
        """When multiple faces qualify, the highest-confidence one wins."""
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        # Both boxes are 100×100 → area 10000/250000 = 0.04 (in bounds).
        boxes = [(50, 50, 100, 100, 0.6), (250, 250, 100, 100, 0.95)]
        with patch("src.pipeline.face_detect._detect_raw", return_value=boxes):
            result = detect_face_center(frame)

        assert result is not None
        cx, _ = result
        # High-confidence box: x=250, w=100 → center 300.
        assert abs(cx - 300) <= 2

    def test_face_outside_relative_area_bounds_ignored(self) -> None:
        """A face larger than _MAX_RELATIVE_AREA (0.3) of the frame is dropped."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # 160×160 → relative_area 0.64 > 0.3
        with patch(
            "src.pipeline.face_detect._detect_raw",
            return_value=[(20, 20, 160, 160, 0.99)],
        ):
            assert detect_face_center(frame) is None

    def test_zero_area_frame_returns_none(self) -> None:
        """A degenerate empty frame returns None without raising."""
        frame = np.zeros((0, 0, 3), dtype=np.uint8)
        assert detect_face_center(frame) is None

    def test_keeps_first_when_later_face_has_lower_confidence(self) -> None:
        """A later, lower-confidence qualifying face does not displace the best."""
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        # High-confidence box FIRST, lower-confidence box second.
        boxes = [(50, 50, 100, 100, 0.95), (250, 250, 100, 100, 0.6)]
        with patch("src.pipeline.face_detect._detect_raw", return_value=boxes):
            result = detect_face_center(frame)

        assert result is not None
        cx, _ = result
        # First (higher-confidence) box: x=50, w=100 → center 100.
        assert abs(cx - 100) <= 2


class TestGetFaceDetector:
    """Covers the FaceDetector construction error path."""

    def test_init_failure_returns_none(self) -> None:
        """When FaceDetector creation raises, _get_face_detector returns None."""
        import src.pipeline.face_detect as fd

        fd._get_face_detector.cache_clear()
        try:
            with (
                patch.object(fd, "_resolve_face_model", return_value=Path("/fake/model.tflite")),
                patch(
                    "mediapipe.tasks.python.vision.FaceDetector.create_from_options",
                    side_effect=RuntimeError("init boom"),
                ),
            ):
                assert fd._get_face_detector() is None
        finally:
            fd._get_face_detector.cache_clear()


# ---------------------------------------------------------------------------
# _detect_raw — MediaPipe Tasks output parsing (mediapipe I/O mocked)
# ---------------------------------------------------------------------------
class TestDetectRaw:
    def test_returns_none_when_detector_unavailable(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("src.pipeline.face_detect._get_face_detector", return_value=None):
            assert _detect_raw(frame) is None

    def test_parses_detector_output_to_pixel_tuples(self) -> None:
        """Tasks bounding boxes (absolute pixels) + score become int tuples."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        bbox = MagicMock(origin_x=10, origin_y=20, width=30, height=40)
        category = MagicMock(score=0.88)
        detection = MagicMock(bounding_box=bbox, categories=[category])
        detector = MagicMock()
        detector.detect.return_value = MagicMock(detections=[detection])

        with (
            patch(
                "src.pipeline.face_detect._get_face_detector",
                return_value=detector,
            ),
            patch.dict("sys.modules", {"mediapipe": MagicMock()}),
        ):
            boxes = _detect_raw(frame)

        assert boxes == [(10, 20, 30, 40, 0.88)]

    def test_returns_none_when_detect_raises(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        detector = MagicMock()
        detector.detect.side_effect = RuntimeError("inference crash")

        with (
            patch(
                "src.pipeline.face_detect._get_face_detector",
                return_value=detector,
            ),
            patch.dict("sys.modules", {"mediapipe": MagicMock()}),
        ):
            assert _detect_raw(frame) is None


# ---------------------------------------------------------------------------
# _get_face_detector / _resolve_face_model — graceful unavailability
# ---------------------------------------------------------------------------
class TestFaceDetectorAvailability:
    def test_detector_none_when_model_unavailable(self) -> None:
        _get_face_detector.cache_clear()
        try:
            with patch("src.pipeline.face_detect._resolve_face_model", return_value=None):
                assert _get_face_detector() is None
        finally:
            _get_face_detector.cache_clear()

    def test_detector_none_when_mediapipe_missing(self, tmp_path: Path) -> None:
        """Missing mediapipe import yields None (clean fallback), not an error."""
        _get_face_detector.cache_clear()
        fake_model = tmp_path / _FACE_MODEL_FILENAME
        fake_model.write_bytes(b"stub")
        try:
            with (
                patch(
                    "src.pipeline.face_detect._resolve_face_model",
                    return_value=fake_model,
                ),
                patch.dict("sys.modules", {"mediapipe.tasks.python": None}),
            ):
                assert _get_face_detector() is None
        finally:
            _get_face_detector.cache_clear()

    def test_resolve_returns_cached_model_when_present(self, tmp_path: Path) -> None:
        model = tmp_path / "models" / _FACE_MODEL_FILENAME
        model.parent.mkdir(parents=True)
        model.write_bytes(b"cached-model-bytes")
        with patch("src.pipeline.face_detect._face_model_cache_path", return_value=model):
            assert _resolve_face_model() == model

    def test_resolve_downloads_and_caches_when_absent(self, tmp_path: Path) -> None:
        """When no cached model exists, it is downloaded and written to disk."""
        model = tmp_path / "models" / _FACE_MODEL_FILENAME

        response = MagicMock()
        response.content = b"downloaded-model-bytes"
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.get.return_value = response

        with (
            patch(
                "src.pipeline.face_detect._face_model_cache_path",
                return_value=model,
            ),
            patch("httpx.Client", return_value=client),
        ):
            result = _resolve_face_model()

        assert result == model
        # Real assertion: the model bytes were persisted to the cache path.
        assert model.read_bytes() == b"downloaded-model-bytes"

    def test_resolve_returns_none_on_download_failure(self, tmp_path: Path) -> None:
        """A network error during download degrades to None (logged), not raise."""
        import httpx

        model = tmp_path / "models" / _FACE_MODEL_FILENAME

        def boom(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("no network")

        with (
            patch(
                "src.pipeline.face_detect._face_model_cache_path",
                return_value=model,
            ),
            patch("httpx.Client.get", boom),
        ):
            assert _resolve_face_model() is None


# ---------------------------------------------------------------------------
# detect_face_center — REAL run against the committed fixture
# ---------------------------------------------------------------------------
class TestDetectFaceCenterReal:
    """Ground-truth test: real frame → None or a valid center, never a raise."""

    def test_real_frame_returns_none_or_valid_center(self) -> None:
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"
        frame = get_representative_frame(fixture, timestamp_s=0.2)
        if frame is None:
            pytest.skip("could not extract a frame from the fixture")

        _get_face_detector.cache_clear()
        try:
            result = detect_face_center(frame)
        finally:
            _get_face_detector.cache_clear()

        height, width = frame.shape[:2]
        assert result is None or (isinstance(result, tuple) and len(result) == 2 and 0 <= result[0] < width and 0 <= result[1] < height)


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


# ---------------------------------------------------------------------------
# _segment_sample_timestamps — even spacing and degenerate inputs
# ---------------------------------------------------------------------------
class TestSegmentSampleTimestamps:
    def test_even_spacing_includes_endpoints(self) -> None:
        ts = _segment_sample_timestamps(0.0, 9.0, samples=10)
        assert len(ts) == 10
        assert ts[0] == 0.0
        assert ts[-1] == pytest.approx(9.0)
        # Uniform spacing of 1.0s between consecutive samples.
        diffs = [b - a for a, b in zip(ts, ts[1:], strict=False)]
        assert all(d == pytest.approx(1.0) for d in diffs)

    def test_zero_length_segment_collapses_to_single(self) -> None:
        assert _segment_sample_timestamps(5.0, 5.0, samples=10) == [5.0]

    def test_end_before_start_collapses_to_single(self) -> None:
        assert _segment_sample_timestamps(8.0, 3.0, samples=10) == [8.0]

    def test_single_sample_returns_start(self) -> None:
        assert _segment_sample_timestamps(2.0, 6.0, samples=1) == [2.0]

    def test_non_positive_samples_collapses_to_single(self) -> None:
        assert _segment_sample_timestamps(2.0, 6.0, samples=0) == [2.0]


# ---------------------------------------------------------------------------
# detect_face_center_multi — median aggregation, fallback, outlier robustness
# ---------------------------------------------------------------------------
class TestDetectFaceCenterMulti:
    """Aggregates per-frame detections via median (frame/detect boundaries mocked)."""

    def test_median_of_successful_detections(self) -> None:
        """Median x and y of all qualifying frames are returned."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        centers = [(100, 110), (120, 130), (140, 150)]
        with (
            patch("src.pipeline.face_detect.get_representative_frame", return_value=frame),
            patch("src.pipeline.face_detect.detect_face_center", side_effect=centers),
        ):
            result = detect_face_center_multi("/fake.mp4", 0.0, 2.0, samples=3)
        assert result == (120, 130)

    def test_outlier_frame_does_not_skew_result(self) -> None:
        """A single wild misdetection is rejected by the median, not averaged in."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Four tightly-clustered centers plus one far outlier.
        centers = [(100, 100), (102, 100), (104, 100), (98, 100), (900, 100)]
        with (
            patch("src.pipeline.face_detect.get_representative_frame", return_value=frame),
            patch("src.pipeline.face_detect.detect_face_center", side_effect=centers),
        ):
            result = detect_face_center_multi("/fake.mp4", 0.0, 4.0, samples=5)
        assert result is not None
        cx, _ = result
        # Median x is 102, nowhere near the 900 outlier.
        assert cx == 102

    def test_frames_without_face_are_ignored(self) -> None:
        """Frames whose detection is None are skipped; the rest are aggregated."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        detections = [None, (100, 100), None, (200, 200)]
        with (
            patch("src.pipeline.face_detect.get_representative_frame", return_value=frame),
            patch("src.pipeline.face_detect.detect_face_center", side_effect=detections),
        ):
            result = detect_face_center_multi("/fake.mp4", 0.0, 3.0, samples=4)
        # Even-count median of [100, 200] -> 150 (int).
        assert result == (150, 150)

    def test_undecodable_frames_are_skipped(self) -> None:
        """A frame that fails to decode (None) is skipped without calling detect."""
        good_frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frames = [None, good_frame, None]
        with (
            patch("src.pipeline.face_detect.get_representative_frame", side_effect=frames),
            patch("src.pipeline.face_detect.detect_face_center", return_value=(150, 160)) as det,
        ):
            result = detect_face_center_multi("/fake.mp4", 0.0, 2.0, samples=3)
        assert result == (150, 160)
        # detect only invoked for the one decodable frame.
        assert det.call_count == 1

    def test_no_face_anywhere_returns_none(self) -> None:
        """When no sampled frame yields a face, return None (center-crop fallback)."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        with (
            patch("src.pipeline.face_detect.get_representative_frame", return_value=frame),
            patch("src.pipeline.face_detect.detect_face_center", return_value=None),
        ):
            assert detect_face_center_multi("/fake.mp4", 0.0, 2.0, samples=4) is None

    def test_all_frames_undecodable_returns_none(self) -> None:
        """When every frame fails to decode, return None without raising."""
        with patch("src.pipeline.face_detect.get_representative_frame", return_value=None):
            assert detect_face_center_multi("/fake.mp4", 0.0, 2.0, samples=4) is None


class TestDetectFaceCenterMultiReal:
    """Ground-truth: real multi-frame run over the fixture, None or valid center."""

    def test_real_segment_returns_none_or_valid_center(self) -> None:
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"
        probe = get_representative_frame(fixture, timestamp_s=0.2)
        if probe is None:
            pytest.skip("could not extract a frame from the fixture")
        height, width = probe.shape[:2]

        _get_face_detector.cache_clear()
        try:
            result = detect_face_center_multi(fixture, 0.0, 2.5, samples=5)
        finally:
            _get_face_detector.cache_clear()

        assert result is None or (isinstance(result, tuple) and len(result) == 2 and 0 <= result[0] < width and 0 <= result[1] < height)


# end tests/unit/test_face_detect.py
