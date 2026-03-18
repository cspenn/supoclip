# start src/pipeline/face_detect.py
"""Face detection using MediaPipe with center-crop fallback.

Provides simple functions for detecting a face center in a video frame and
calculating a 9:16 crop box. The 3-tier fallback chain (MediaPipe → OpenCV
DNN → Haar cascade) is replaced with MediaPipe only; if no face is found the
crop defaults to frame center.
"""

from pathlib import Path

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# Relative face area thresholds — ignore detections that are implausibly
# small (noise) or implausibly large (framing error).
_MIN_RELATIVE_AREA: float = 0.005
_MAX_RELATIVE_AREA: float = 0.3


def round_to_even(n: int) -> int:
    """Round n down to the nearest even integer (required by H.264 encoding).

    Args:
        n: Integer to round down to nearest even.

    Returns:
        n if already even, otherwise n - 1.
    """
    return n if n % 2 == 0 else n - 1


def detect_face_center(frame: np.ndarray) -> tuple[int, int] | None:
    """Detect the center (x, y) of the most prominent face in the frame.

    Uses MediaPipe face detection. Picks the highest-confidence detection
    whose relative area falls within plausible bounds. Returns None if
    MediaPipe is unavailable or no qualifying face is found.

    Args:
        frame: BGR numpy array from a video frame.

    Returns:
        (x, y) pixel coordinates of the face center, or None if not detected.
    """
    try:
        import mediapipe as mp  # type: ignore[import-untyped]
    except ImportError:
        log.warning("mediapipe_unavailable", reason="import failed")
        return None

    height, width = frame.shape[:2]
    frame_area = width * height

    try:
        detector = mp.solutions.face_detection.FaceDetection(  # type: ignore[reportAttributeAccessIssue]
            model_selection=0, min_detection_confidence=0.5
        )
        with detector:
            results = detector.process(frame)
    except Exception as exc:
        log.warning("mediapipe_detection_failed", error=str(exc))
        return None

    if not results.detections:
        return None

    best_face: tuple[int, int] | None = None
    best_confidence: float = -1.0

    for detection in results.detections:
        bbox = detection.location_data.relative_bounding_box
        confidence: float = detection.score[0]

        x = int(bbox.xmin * width)
        y = int(bbox.ymin * height)
        w = int(bbox.width * width)
        h = int(bbox.height * height)

        # Skip faces that are too small to be reliable detections.
        if w <= 30 or h <= 30:
            continue

        relative_area = (w * h) / frame_area
        if not (_MIN_RELATIVE_AREA < relative_area < _MAX_RELATIVE_AREA):
            continue

        if confidence > best_confidence:
            best_confidence = confidence
            best_face = (x + w // 2, y + h // 2)

    return best_face


def calculate_crop_box(
    frame_width: int,
    frame_height: int,
    face_center: tuple[int, int] | None,
    target_width: int = 1080,
    target_height: int = 1920,
) -> tuple[int, int, int, int]:
    """Calculate the crop box for 9:16 vertical format.

    Centers the crop on the detected face, or on the frame center if no face
    is provided. When the requested 9:16 crop would exceed the source frame
    size, the crop dimensions are scaled down to fit while preserving the
    target aspect ratio. All output dimensions are rounded down to even
    integers for H.264 compatibility.

    Args:
        frame_width: Original frame width in pixels.
        frame_height: Original frame height in pixels.
        face_center: (x, y) center of detected face, or None.
        target_width: Desired output width (default 1080).
        target_height: Desired output height (default 1920).

    Returns:
        (x, y, width, height) crop box where (x, y) is the top-left corner
        and (width, height) are the crop dimensions.
    """
    target_ratio: float = target_width / target_height

    # Scale crop dimensions to fit within the source frame.
    if frame_width / frame_height > target_ratio:
        # Frame is wider than needed — constrain by height.
        crop_height = round_to_even(frame_height)
        crop_width = round_to_even(int(frame_height * target_ratio))
    else:
        # Frame is taller than needed — constrain by width.
        crop_width = round_to_even(frame_width)
        crop_height = round_to_even(int(frame_width / target_ratio))

    # Determine crop anchor: face center or frame center.
    if face_center is not None:
        anchor_x, anchor_y = face_center
        # Apply a slight upward bias (10% of crop height) for better framing.
        anchor_y = max(0, anchor_y - int(crop_height * 0.1))
    else:
        anchor_x = frame_width // 2
        anchor_y = frame_height // 2

    # Compute top-left corner, then clamp to stay within frame bounds.
    x = anchor_x - crop_width // 2
    y = anchor_y - crop_height // 2

    x = max(0, min(x, frame_width - crop_width))
    y = max(0, min(y, frame_height - crop_height))

    return round_to_even(x), round_to_even(y), crop_width, crop_height


def get_representative_frame(
    video_path: str | Path, timestamp_s: float = 1.0
) -> np.ndarray | None:
    """Extract a single frame from a video file for face detection.

    Attempts to use opencv-python (cv2) to read the frame. If cv2 is not
    available or extraction fails for any reason, returns None so callers
    can fall back to center crop.

    Args:
        video_path: Path to the video file.
        timestamp_s: Timestamp in seconds to extract the frame from.

    Returns:
        BGR numpy array, or None if extraction failed.
    """
    try:
        import cv2  # type: ignore[import-untyped]  # optional dependency
    except ImportError:
        log.warning("cv2_unavailable", reason="opencv-python not installed")
        return None

    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        target_frame = int(timestamp_s * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ok, frame = cap.read()
        if not ok or frame is None:
            log.warning("frame_read_failed", path=str(video_path), ts=timestamp_s)
            return None
        return frame  # type: ignore[return-value]
    except Exception as exc:
        log.warning("frame_extraction_error", path=str(video_path), error=str(exc))
        return None
    finally:
        cap.release()


# end src/pipeline/face_detect.py
