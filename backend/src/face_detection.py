# start backend/src/face_detection.py
"""
Face detection: MediaPipe, OpenCV DNN, and Haar cascade detectors with
temporal consistency and outlier filtering.
"""

from pathlib import Path
import logging

import numpy as np
import cv2
from moviepy import VideoFileClip

logger = logging.getLogger(__name__)


class FaceDetector:
    """Abstract base class for face detectors."""

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Detect faces in frame.

        Args:
            frame: Video frame as numpy array (RGB)

        Returns:
            List of (x, y, w, h, confidence) tuples
        """
        raise NotImplementedError


class MediaPipeFaceDetector(FaceDetector):
    """MediaPipe face detection (primary detector)."""

    def __init__(self):
        """Initialize MediaPipe detector."""
        self.detector = None
        try:
            import mediapipe as mp  # type: ignore

            self.detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.5
            )
            logger.info("Using MediaPipe face detector")
        except Exception as e:
            logger.warning(f"MediaPipe initialization failed: {e}")

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Detect faces using MediaPipe.

        Args:
            frame: Video frame as numpy array

        Returns:
            List of (x, y, w, h, confidence) tuples
        """
        if self.detector is None:
            return []

        try:
            height, width = frame.shape[:2]
            results = self.detector.process(frame)

            faces = []
            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    confidence = detection.score[0]

                    x = int(bbox.xmin * width)
                    y = int(bbox.ymin * height)
                    w = int(bbox.width * width)
                    h = int(bbox.height * height)

                    if w > 30 and h > 30:
                        faces.append((x, y, w, h, confidence))
            return faces
        except Exception as e:
            logger.warning(f"MediaPipe detection failed: {e}")
            return []

    def close(self):
        """Clean up detector resources."""
        if self.detector is not None:
            self.detector.close()


class OpenCVDNNFaceDetector(FaceDetector):
    """OpenCV DNN face detection (first fallback)."""

    def __init__(self):
        """Initialize OpenCV DNN detector."""
        self.net = None
        try:
            prototxt = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector.pbtxt"
            )
            model = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector_uint8.pb"
            )

            if Path(prototxt).exists() and Path(model).exists():
                self.net = cv2.dnn.readNetFromTensorflow(model, prototxt)
                logger.info("OpenCV DNN detector loaded")
        except Exception as e:
            logger.info(f"OpenCV DNN detector not available: {e}")

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Detect faces using OpenCV DNN.

        Args:
            frame: Video frame as numpy array

        Returns:
            List of (x, y, w, h, confidence) tuples
        """
        if self.net is None:
            return []

        try:
            height, width = frame.shape[:2]
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            blob = cv2.dnn.blobFromImage(frame_bgr, 1.0, (300, 300), [104, 117, 123])
            self.net.setInput(blob)
            detections = self.net.forward()

            faces = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    x1 = int(detections[0, 0, i, 3] * width)
                    y1 = int(detections[0, 0, i, 4] * height)
                    x2 = int(detections[0, 0, i, 5] * width)
                    y2 = int(detections[0, 0, i, 6] * height)

                    w = x2 - x1
                    h = y2 - y1

                    if w > 30 and h > 30:
                        faces.append((x1, y1, w, h, confidence))
            return faces
        except Exception as e:
            logger.warning(f"DNN detection failed: {e}")
            return []


class HaarCascadeFaceDetector(FaceDetector):
    """Haar Cascade face detection (last resort fallback)."""

    def __init__(self):
        """Initialize Haar cascade detector."""
        self.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Detect faces using Haar cascade.

        Args:
            frame: Video frame as numpy array

        Returns:
            List of (x, y, w, h, confidence) tuples
        """
        try:
            height, width = frame.shape[:2]
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            faces_raw = self.cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(40, 40),
                maxSize=(int(width * 0.7), int(height * 0.7)),
            )

            faces = []
            for x, y, w, h in faces_raw:
                face_area = w * h
                relative_size = face_area / (width * height)
                confidence = min(0.9, 0.3 + relative_size * 2)
                faces.append((x, y, w, h, confidence))
            return faces
        except Exception as e:
            logger.warning(f"Haar cascade detection failed: {e}")
            return []


class VideoFrameSampler:
    """Sample frames from video clips for face detection."""

    @staticmethod
    def generate_sample_times(start_time: float, end_time: float) -> list[float]:
        """Generate times to sample for face detection.

        Args:
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds

        Returns:
            List of sample times in seconds
        """
        duration = end_time - start_time
        sample_interval = min(0.5, duration / 10)

        sample_times = []
        current = start_time
        while current < end_time:
            sample_times.append(current)
            current += sample_interval

        # Add middle time if duration > 1s
        if duration > 1.0:
            middle = start_time + duration / 2
            if middle not in sample_times:
                sample_times.append(middle)

        return [t for t in sample_times if t < end_time]


class FaceDetectionService:
    """Orchestrate face detection with fallback chain."""

    MIN_RELATIVE_AREA = 0.005
    MAX_RELATIVE_AREA = 0.3

    def __init__(self):
        """Initialize detector chain: MediaPipe -> OpenCV DNN -> Haar cascade."""
        self.detectors: list[FaceDetector] = [
            MediaPipeFaceDetector(),
            OpenCVDNNFaceDetector(),
            HaarCascadeFaceDetector(),
        ]

    def detect_in_frame(self, frame: np.ndarray) -> list[tuple[int, int, int, float]]:
        """Detect faces in single frame using detector chain.

        Args:
            frame: Video frame as numpy array

        Returns:
            List of (center_x, center_y, area, confidence) tuples
        """
        height, width = frame.shape[:2]
        frame_area = width * height

        # Try detectors in order until faces found
        for detector in self.detectors:
            try:
                detected = detector.detect(frame)
                if detected:
                    # Convert to face centers and filter
                    face_centers = []
                    for x, y, w, h, conf in detected:
                        center_x = x + w // 2
                        center_y = y + h // 2
                        area = w * h
                        relative_area = area / frame_area

                        if (
                            self.MIN_RELATIVE_AREA
                            < relative_area
                            < self.MAX_RELATIVE_AREA
                        ):
                            face_centers.append((center_x, center_y, area, conf))

                    if face_centers:
                        return face_centers
            except Exception as e:
                logger.warning(f"Detector {detector.__class__.__name__} failed: {e}")
                continue

        return []

    def close(self):
        """Clean up detector resources."""
        for detector in self.detectors:
            if hasattr(detector, "close"):
                detector.close()


def detect_faces_in_clip(
    video_clip: VideoFileClip, start_time: float, end_time: float
) -> list[tuple[int, int, int, float]]:
    """Detect faces across multiple frames with temporal consistency.

    Samples frames throughout the clip and aggregates face detections,
    filtering outliers for stable crop positioning.

    Args:
        video_clip: MoviePy VideoFileClip object
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds

    Returns:
        List of (x, y, area, confidence) tuples representing detected faces
    """
    try:
        # Initialize face detection service
        service = FaceDetectionService()

        # Generate sample times
        sample_times = VideoFrameSampler.generate_sample_times(start_time, end_time)
        logger.info(f"Sampling {len(sample_times)} frames for face detection")

        # Detect faces in all sampled frames
        face_centers: list[tuple[int, int, int, float]] = []
        for sample_time in sample_times:
            try:
                frame = video_clip.get_frame(sample_time)
                centers = service.detect_in_frame(frame)
                face_centers.extend(centers)
            except Exception as e:
                logger.warning(f"Error detecting faces at {sample_time}s: {e}")
                continue

        # Clean up detector resources
        service.close()

        # Remove outliers
        if len(face_centers) > 2:
            face_centers = filter_face_outliers(face_centers)

        logger.info(f"Detected {len(face_centers)} reliable face centers")
        return face_centers

    except Exception as e:
        logger.error(f"Error in face detection: {e}")
        return []


def filter_face_outliers(
    face_centers: list[tuple[int, int, int, float]],
) -> list[tuple[int, int, int, float]]:
    """Remove face detections that are outliers (likely false positives).

    Uses median + 2 standard deviations to identify outliers.

    Args:
        face_centers: List of (x, y, area, confidence) tuples

    Returns:
        Filtered list with outliers removed
    """
    if len(face_centers) < 3:
        return face_centers

    try:
        # Calculate median position
        x_positions = [x for x, y, area, conf in face_centers]
        y_positions = [y for x, y, area, conf in face_centers]

        median_x = np.median(x_positions)
        median_y = np.median(y_positions)

        # Calculate standard deviation
        std_x = np.std(x_positions)
        std_y = np.std(y_positions)

        # Filter out faces that are more than 2 standard deviations away
        filtered_faces = []
        for face in face_centers:
            x, y, area, conf = face
            if abs(x - median_x) <= 2 * std_x and abs(y - median_y) <= 2 * std_y:
                filtered_faces.append(face)

        logger.info(
            f"Filtered {len(face_centers)} -> {len(filtered_faces)} faces (removed outliers)"
        )
        return filtered_faces or face_centers  # Return original if all filtered

    except Exception as e:
        logger.warning(f"Error filtering face outliers: {e}")
        return face_centers


# end backend/src/face_detection.py
