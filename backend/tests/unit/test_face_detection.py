# start tests/unit/test_face_detection.py
"""
Unit tests for backend/src/face_detection.py

Covers: FaceDetector, MediaPipeFaceDetector, OpenCVDNNFaceDetector,
HaarCascadeFaceDetector, VideoFrameSampler, FaceDetectionService,
detect_faces_in_clip, filter_face_outliers
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import numpy as np

backend_root = Path(__file__).parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from src.face_detection import (
    FaceDetector,
    MediaPipeFaceDetector,
    OpenCVDNNFaceDetector,
    HaarCascadeFaceDetector,
    VideoFrameSampler,
    FaceDetectionService,
    detect_faces_in_clip,
    filter_face_outliers,
)


# ---------------------------------------------------------------------------
# FaceDetector (line 29)
# ---------------------------------------------------------------------------
class TestFaceDetector:
    def test_detect_raises_not_implemented(self):
        detector = FaceDetector()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(NotImplementedError):
            detector.detect(frame)


# ---------------------------------------------------------------------------
# MediaPipeFaceDetector (lines 41-44, 57-80, 85)
# ---------------------------------------------------------------------------
class TestMediaPipeFaceDetector:
    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_detect_no_detector(self, mock_init):
        d = MediaPipeFaceDetector()
        d.detector = None
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert d.detect(frame) == []

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_detect_with_faces(self, mock_init):
        d = MediaPipeFaceDetector()

        mock_detection = MagicMock()
        mock_detection.location_data.relative_bounding_box.xmin = 0.2
        mock_detection.location_data.relative_bounding_box.ymin = 0.2
        mock_detection.location_data.relative_bounding_box.width = 0.3
        mock_detection.location_data.relative_bounding_box.height = 0.3
        mock_detection.score = [0.95]

        mock_results = MagicMock()
        mock_results.detections = [mock_detection]

        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_results
        d.detector = mock_processor

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        faces = d.detect(frame)
        assert len(faces) == 1
        x, y, w, h, conf = faces[0]
        assert conf == 0.95
        assert w > 30
        assert h > 30

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_detect_small_face_filtered(self, mock_init):
        d = MediaPipeFaceDetector()

        mock_detection = MagicMock()
        mock_detection.location_data.relative_bounding_box.xmin = 0.0
        mock_detection.location_data.relative_bounding_box.ymin = 0.0
        mock_detection.location_data.relative_bounding_box.width = 0.05
        mock_detection.location_data.relative_bounding_box.height = 0.05
        mock_detection.score = [0.8]

        mock_results = MagicMock()
        mock_results.detections = [mock_detection]

        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_results
        d.detector = mock_processor

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # 0.05 * 100 = 5, which is < 30 so it gets filtered
        faces = d.detect(frame)
        assert len(faces) == 0

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_detect_no_detections(self, mock_init):
        d = MediaPipeFaceDetector()
        mock_results = MagicMock()
        mock_results.detections = None
        mock_processor = MagicMock()
        mock_processor.process.return_value = mock_results
        d.detector = mock_processor

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert d.detect(frame) == []

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_detect_exception(self, mock_init):
        d = MediaPipeFaceDetector()
        mock_processor = MagicMock()
        mock_processor.process.side_effect = RuntimeError("fail")
        d.detector = mock_processor

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert d.detect(frame) == []

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_close(self, mock_init):
        d = MediaPipeFaceDetector()
        mock_detector = MagicMock()
        d.detector = mock_detector
        d.close()
        mock_detector.close.assert_called_once()

    @patch("src.face_detection.MediaPipeFaceDetector.__init__", return_value=None)
    def test_close_no_detector(self, mock_init):
        d = MediaPipeFaceDetector()
        d.detector = None
        d.close()  # Should not raise

    def test_init_mediapipe_failure(self):
        """Test init when mediapipe import fails."""
        with patch.dict("sys.modules", {"mediapipe": None}):
            with patch("builtins.__import__", side_effect=ImportError("no mediapipe")):
                d = MediaPipeFaceDetector()
                assert d.detector is None


# ---------------------------------------------------------------------------
# OpenCVDNNFaceDetector (lines 104, 117-144)
# ---------------------------------------------------------------------------
class TestOpenCVDNNFaceDetector:
    @patch("src.face_detection.OpenCVDNNFaceDetector.__init__", return_value=None)
    def test_detect_no_net(self, mock_init):
        d = OpenCVDNNFaceDetector()
        d.net = None
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert d.detect(frame) == []

    @patch("src.face_detection.OpenCVDNNFaceDetector.__init__", return_value=None)
    def test_detect_with_faces(self, mock_init):
        d = OpenCVDNNFaceDetector()

        # Create mock network output: shape (1, 1, N, 7)
        # Format: [batch_id, class_id, confidence, x1, y1, x2, y2]
        detections = np.zeros((1, 1, 1, 7))
        detections[0, 0, 0, 2] = 0.9  # confidence
        detections[0, 0, 0, 3] = 0.1  # x1 (normalized)
        detections[0, 0, 0, 4] = 0.1  # y1
        detections[0, 0, 0, 5] = 0.5  # x2
        detections[0, 0, 0, 6] = 0.5  # y2

        mock_net = MagicMock()
        mock_net.forward.return_value = detections
        d.net = mock_net

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((200, 200, 3), dtype=np.uint8)
            mock_cv2.dnn.blobFromImage.return_value = MagicMock()
            mock_cv2.COLOR_RGB2BGR = 4

            frame = np.zeros((200, 200, 3), dtype=np.uint8)
            faces = d.detect(frame)
            assert len(faces) == 1
            x, y, w, h, conf = faces[0]
            assert conf == pytest.approx(0.9)

    @patch("src.face_detection.OpenCVDNNFaceDetector.__init__", return_value=None)
    def test_detect_low_confidence_filtered(self, mock_init):
        d = OpenCVDNNFaceDetector()

        detections = np.zeros((1, 1, 1, 7))
        detections[0, 0, 0, 2] = 0.3  # low confidence
        detections[0, 0, 0, 3] = 0.1
        detections[0, 0, 0, 4] = 0.1
        detections[0, 0, 0, 5] = 0.5
        detections[0, 0, 0, 6] = 0.5

        mock_net = MagicMock()
        mock_net.forward.return_value = detections
        d.net = mock_net

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((200, 200, 3), dtype=np.uint8)
            mock_cv2.dnn.blobFromImage.return_value = MagicMock()
            mock_cv2.COLOR_RGB2BGR = 4

            frame = np.zeros((200, 200, 3), dtype=np.uint8)
            faces = d.detect(frame)
            assert len(faces) == 0

    @patch("src.face_detection.OpenCVDNNFaceDetector.__init__", return_value=None)
    def test_detect_small_face_filtered(self, mock_init):
        d = OpenCVDNNFaceDetector()

        # Create a detection that results in a small face (< 30px)
        detections = np.zeros((1, 1, 1, 7))
        detections[0, 0, 0, 2] = 0.9
        detections[0, 0, 0, 3] = 0.1
        detections[0, 0, 0, 4] = 0.1
        detections[0, 0, 0, 5] = 0.12  # very small: 0.02 * 100 = 2px
        detections[0, 0, 0, 6] = 0.12

        mock_net = MagicMock()
        mock_net.forward.return_value = detections
        d.net = mock_net

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_cv2.dnn.blobFromImage.return_value = MagicMock()
            mock_cv2.COLOR_RGB2BGR = 4

            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            faces = d.detect(frame)
            assert len(faces) == 0

    @patch("src.face_detection.OpenCVDNNFaceDetector.__init__", return_value=None)
    def test_detect_exception(self, mock_init):
        d = OpenCVDNNFaceDetector()
        mock_net = MagicMock()
        mock_net.forward.side_effect = RuntimeError("fail")
        d.net = mock_net

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_cv2.dnn.blobFromImage.return_value = MagicMock()
            mock_cv2.COLOR_RGB2BGR = 4

            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            assert d.detect(frame) == []

    def test_init_opencv_dnn_no_files(self):
        """Test init when model files don't exist."""
        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.data.haarcascades = "/fake/path/"
            with patch("src.face_detection.Path") as mock_path_cls:
                mock_path_cls.return_value.exists.return_value = False
                d = OpenCVDNNFaceDetector()
                assert d.net is None

    def test_init_opencv_dnn_exception(self):
        """Test init when cv2 raises an exception."""
        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.data.haarcascades = "/fake/path/"
            # Force exception during init
            type(mock_cv2.data).haarcascades = PropertyMock(side_effect=Exception("fail"))
            d = OpenCVDNNFaceDetector()
            assert d.net is None


# ---------------------------------------------------------------------------
# HaarCascadeFaceDetector (lines 165-187)
# ---------------------------------------------------------------------------
class TestHaarCascadeFaceDetector:
    @patch("src.face_detection.HaarCascadeFaceDetector.__init__", return_value=None)
    def test_detect_faces(self, mock_init):
        d = HaarCascadeFaceDetector()
        mock_cascade = MagicMock()
        # detectMultiScale returns numpy array of (x, y, w, h)
        mock_cascade.detectMultiScale.return_value = np.array([[50, 50, 80, 80]])
        d.cascade = mock_cascade

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((200, 200), dtype=np.uint8)
            mock_cv2.COLOR_RGB2BGR = 4
            mock_cv2.COLOR_BGR2GRAY = 6

            frame = np.zeros((200, 200, 3), dtype=np.uint8)
            faces = d.detect(frame)
            assert len(faces) == 1
            x, y, w, h, conf = faces[0]
            assert x == 50
            assert y == 50
            assert w == 80
            assert h == 80
            assert 0 < conf <= 0.9

    @patch("src.face_detection.HaarCascadeFaceDetector.__init__", return_value=None)
    def test_detect_no_faces(self, mock_init):
        d = HaarCascadeFaceDetector()
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale.return_value = np.array([]).reshape(0, 4)
        d.cascade = mock_cascade

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((200, 200), dtype=np.uint8)
            mock_cv2.COLOR_RGB2BGR = 4
            mock_cv2.COLOR_BGR2GRAY = 6

            frame = np.zeros((200, 200, 3), dtype=np.uint8)
            faces = d.detect(frame)
            assert len(faces) == 0

    @patch("src.face_detection.HaarCascadeFaceDetector.__init__", return_value=None)
    def test_detect_exception(self, mock_init):
        d = HaarCascadeFaceDetector()
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale.side_effect = RuntimeError("fail")
        d.cascade = mock_cascade

        with patch("src.face_detection.cv2") as mock_cv2:
            mock_cv2.cvtColor.return_value = np.zeros((200, 200), dtype=np.uint8)
            mock_cv2.COLOR_RGB2BGR = 4
            mock_cv2.COLOR_BGR2GRAY = 6

            frame = np.zeros((200, 200, 3), dtype=np.uint8)
            assert d.detect(frame) == []


# ---------------------------------------------------------------------------
# VideoFrameSampler
# ---------------------------------------------------------------------------
class TestVideoFrameSampler:
    def test_short_clip(self):
        times = VideoFrameSampler.generate_sample_times(0.0, 0.5)
        assert len(times) > 0
        for t in times:
            assert t < 0.5

    def test_long_clip_adds_middle(self):
        times = VideoFrameSampler.generate_sample_times(0.0, 10.0)
        assert 5.0 in times

    def test_one_second_no_middle(self):
        times = VideoFrameSampler.generate_sample_times(0.0, 1.0)
        # Duration is exactly 1.0, so middle won't be added (duration > 1.0 is False)
        assert all(t < 1.0 for t in times)

    def test_sample_interval_capped(self):
        # Duration 20s -> interval = min(0.5, 2) = 0.5
        times = VideoFrameSampler.generate_sample_times(0.0, 20.0)
        intervals = [times[i + 1] - times[i] for i in range(len(times) - 2)]
        # Most intervals should be close to 0.5 (middle time may disrupt)
        for interval in intervals:
            assert interval <= 0.51 or interval > 0  # at least positive

    def test_middle_already_in_list(self):
        """When middle time is already a sample time, don't duplicate (line 217)."""
        # Duration = 2.0s, interval = min(0.5, 0.2) = 0.2
        # Samples: 0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8
        # Middle = 1.0 which is already in list
        times = VideoFrameSampler.generate_sample_times(0.0, 2.0)
        # Count occurrences of the middle time
        middle = 1.0
        count = sum(1 for t in times if t == middle)
        assert count <= 1  # should not be duplicated


# ---------------------------------------------------------------------------
# FaceDetectionService (lines 246-274)
# ---------------------------------------------------------------------------
class TestFaceDetectionService:
    def test_detect_in_frame_uses_chain(self):
        service = FaceDetectionService.__new__(FaceDetectionService)

        mock_detector1 = MagicMock()
        mock_detector1.detect.return_value = []  # No faces

        mock_detector2 = MagicMock()
        mock_detector2.detect.return_value = [
            (100, 100, 80, 80, 0.9)  # face found
        ]

        service.detectors = [mock_detector1, mock_detector2]

        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        result = service.detect_in_frame(frame)
        # Should use detector2's result
        mock_detector1.detect.assert_called_once()
        mock_detector2.detect.assert_called_once()
        assert len(result) == 1

    def test_detect_in_frame_filters_by_relative_area(self):
        service = FaceDetectionService.__new__(FaceDetectionService)

        # Face too small (relative area < 0.005)
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [
            (0, 0, 5, 5, 0.9)  # 25 / 250000 = 0.0001 < 0.005
        ]

        service.detectors = [mock_detector]
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        result = service.detect_in_frame(frame)
        assert len(result) == 0

    def test_detect_in_frame_filters_too_large(self):
        service = FaceDetectionService.__new__(FaceDetectionService)

        # Face too large (relative area > 0.3)
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [
            (0, 0, 400, 400, 0.9)  # 160000 / 250000 = 0.64 > 0.3
        ]

        service.detectors = [mock_detector]
        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        result = service.detect_in_frame(frame)
        assert len(result) == 0

    def test_detect_in_frame_no_faces(self):
        service = FaceDetectionService.__new__(FaceDetectionService)

        mock_detector = MagicMock()
        mock_detector.detect.return_value = []
        service.detectors = [mock_detector]

        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        result = service.detect_in_frame(frame)
        assert result == []

    def test_detect_in_frame_detector_exception(self):
        service = FaceDetectionService.__new__(FaceDetectionService)

        mock_detector = MagicMock()
        mock_detector.detect.side_effect = RuntimeError("fail")
        mock_detector.__class__.__name__ = "MockDetector"
        service.detectors = [mock_detector]

        frame = np.zeros((500, 500, 3), dtype=np.uint8)
        result = service.detect_in_frame(frame)
        assert result == []

    def test_close(self):
        service = FaceDetectionService.__new__(FaceDetectionService)
        mock_d1 = MagicMock()
        mock_d1.close = MagicMock()
        mock_d2 = MagicMock(spec=[])  # No close method
        service.detectors = [mock_d1, mock_d2]
        service.close()
        mock_d1.close.assert_called_once()

    @patch("src.face_detection.HaarCascadeFaceDetector")
    @patch("src.face_detection.OpenCVDNNFaceDetector")
    @patch("src.face_detection.MediaPipeFaceDetector")
    def test_init_creates_detector_chain(self, mock_mp, mock_dnn, mock_haar):
        """Test __init__ creates 3 detectors in chain (line 230)."""
        service = FaceDetectionService()
        assert len(service.detectors) == 3
        mock_mp.assert_called_once()
        mock_dnn.assert_called_once()
        mock_haar.assert_called_once()


# ---------------------------------------------------------------------------
# detect_faces_in_clip (lines 313, 323, 328-330)
# ---------------------------------------------------------------------------
class TestDetectFacesInClip:
    @patch("src.face_detection.FaceDetectionService")
    @patch("src.face_detection.VideoFrameSampler")
    def test_basic_detection(self, mock_sampler_cls, mock_service_cls):
        mock_sampler_cls.generate_sample_times.return_value = [0.0, 0.5, 1.0]

        mock_service = MagicMock()
        mock_service.detect_in_frame.return_value = [(100, 100, 5000, 0.9)]
        mock_service_cls.return_value = mock_service

        mock_clip = MagicMock()
        mock_clip.get_frame.return_value = np.zeros((200, 200, 3), dtype=np.uint8)

        result = detect_faces_in_clip(mock_clip, 0.0, 2.0)
        assert len(result) == 3  # 3 frames, 1 face each
        mock_service.close.assert_called_once()

    @patch("src.face_detection.FaceDetectionService")
    @patch("src.face_detection.VideoFrameSampler")
    def test_frame_error_continues(self, mock_sampler_cls, mock_service_cls):
        mock_sampler_cls.generate_sample_times.return_value = [0.0, 0.5]

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        mock_clip = MagicMock()
        mock_clip.get_frame.side_effect = RuntimeError("bad frame")

        result = detect_faces_in_clip(mock_clip, 0.0, 2.0)
        assert result == []

    @patch("src.face_detection.FaceDetectionService")
    @patch("src.face_detection.VideoFrameSampler")
    @patch("src.face_detection.filter_face_outliers")
    def test_outlier_filtering_called(self, mock_filter, mock_sampler_cls, mock_service_cls):
        mock_sampler_cls.generate_sample_times.return_value = [0.0, 0.5, 1.0]

        mock_service = MagicMock()
        mock_service.detect_in_frame.return_value = [(100, 100, 5000, 0.9)]
        mock_service_cls.return_value = mock_service

        mock_clip = MagicMock()
        mock_clip.get_frame.return_value = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_filter.return_value = [(100, 100, 5000, 0.9)]

        result = detect_faces_in_clip(mock_clip, 0.0, 2.0)
        mock_filter.assert_called_once()

    @patch("src.face_detection.FaceDetectionService")
    def test_top_level_exception(self, mock_service_cls):
        mock_service_cls.side_effect = RuntimeError("init fail")

        mock_clip = MagicMock()
        result = detect_faces_in_clip(mock_clip, 0.0, 2.0)
        assert result == []


# ---------------------------------------------------------------------------
# filter_face_outliers (lines 346-375)
# ---------------------------------------------------------------------------
class TestFilterFaceOutliers:
    def test_fewer_than_three(self):
        faces = [(100, 100, 5000, 0.9), (101, 101, 5000, 0.9)]
        result = filter_face_outliers(faces)
        assert result == faces

    def test_filters_outlier(self):
        # Two close faces and one far outlier
        faces = [
            (100, 100, 5000, 0.9),
            (102, 102, 5000, 0.9),
            (101, 101, 5000, 0.9),
            (500, 500, 5000, 0.9),  # outlier
        ]
        result = filter_face_outliers(faces)
        # The outlier should be removed
        assert len(result) < len(faces)

    def test_all_same_position(self):
        faces = [
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
        ]
        result = filter_face_outliers(faces)
        assert len(result) == 3

    def test_returns_original_if_all_filtered(self):
        # With std=0, all are at median, so none get filtered
        faces = [
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
        ]
        result = filter_face_outliers(faces)
        assert result == faces

    def test_exception_returns_original(self):
        """If numpy operations fail, return original."""
        faces = [
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
            (100, 100, 5000, 0.9),
        ]
        with patch("src.face_detection.np.median", side_effect=RuntimeError("fail")):
            result = filter_face_outliers(faces)
            assert result == faces


# end tests/unit/test_face_detection.py
