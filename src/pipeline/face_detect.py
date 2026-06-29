# start src/pipeline/face_detect.py
"""Face detection using the MediaPipe Tasks API with center-crop fallback.

Provides simple functions for detecting a face center in a video frame and
calculating a 9:16 crop box. MediaPipe 0.10.x no longer exposes the legacy
``mediapipe.solutions.face_detection`` module, so detection uses the Tasks API
(``mediapipe.tasks.python.vision.FaceDetector``) backed by the BlazeFace
short-range ``.tflite`` model. The model is downloaded once and cached on disk;
if it cannot be obtained (or MediaPipe is unavailable) detection degrades
cleanly to a center crop and the reason is logged — never a spurious
``AttributeError``.
"""

from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger(__name__)

# Relative face area thresholds — ignore detections that are implausibly
# small (noise) or implausibly large (framing error).
_MIN_RELATIVE_AREA: float = 0.005
_MAX_RELATIVE_AREA: float = 0.3

# Minimum face bounding-box edge (pixels) to treat a detection as reliable.
_MIN_FACE_PIXELS: int = 30

# Default number of frames sampled across a segment for multi-frame face
# aggregation (spec 4.14). More samples smooth out per-frame jitter/misses at
# the cost of additional decode/inference work.
_DEFAULT_FRAME_SAMPLES: int = 10

# MediaPipe Tasks face-detection model (BlazeFace short-range). Downloaded once
# and cached on disk under the configured temp dir.
_FACE_MODEL_URL: str = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
_FACE_MODEL_FILENAME: str = "blaze_face_short_range.tflite"
_MODEL_DOWNLOAD_TIMEOUT_S: float = 30.0


def round_to_even(n: int) -> int:
    """Round n down to the nearest even integer (required by H.264 encoding).

    Args:
        n: Integer to round down to nearest even.

    Returns:
        n if already even, otherwise n - 1.
    """
    return n if n % 2 == 0 else n - 1


def _face_model_cache_path() -> Path:
    """Return the absolute on-disk cache path for the face-detection model.

    The path lives under the configured ``temp_dir`` (read defensively so a
    missing config field falls back to ``./temp``) and is resolved to an
    absolute path so a different working directory cannot bypass the cache.

    Returns:
        Absolute path to the cached ``.tflite`` model file.
    """
    from src.config import get_config

    temp_dir = Path(getattr(get_config(), "temp_dir", Path("./temp")))
    return (temp_dir / "models" / _FACE_MODEL_FILENAME).resolve()


def _resolve_face_model() -> Path | None:
    """Return a path to the face model, downloading and caching it if needed.

    Returns ``None`` (logged) when the model cannot be obtained — for example
    when the host is offline — so callers fall back to a center crop instead of
    raising.

    Returns:
        Path to the cached model file, or ``None`` if unavailable.
    """
    path = _face_model_cache_path()
    if path.is_file() and path.stat().st_size > 0:
        return path

    try:
        import httpx

        path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=_MODEL_DOWNLOAD_TIMEOUT_S) as client:
            response = client.get(_FACE_MODEL_URL)
            response.raise_for_status()
        path.write_bytes(response.content)
    except Exception as exc:
        log.warning("face_model_download_failed", error=str(exc))
        return None

    log.info("face_model_downloaded", path=str(path), bytes=len(response.content))
    return path


@lru_cache(maxsize=1)
def _get_face_detector() -> Any | None:
    """Return a cached MediaPipe Tasks FaceDetector, or ``None`` if unavailable.

    The detector is created once per process (subsequent calls reuse it, which
    avoids re-initialising the GL/XNNPACK context for every clip). Returns
    ``None`` (logged) when MediaPipe or its model asset cannot be loaded,
    signalling callers to use the center-crop fallback.

    Returns:
        A ``vision.FaceDetector`` instance, or ``None`` if it cannot be built.
    """
    model_path = _resolve_face_model()
    if model_path is None:
        log.warning("face_model_unavailable", reason="model could not be resolved")
        return None

    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except ImportError:
        log.warning("mediapipe_unavailable", reason="import failed")
        return None

    try:
        options = vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            min_detection_confidence=0.5,
        )
        return vision.FaceDetector.create_from_options(options)
    except Exception as exc:
        log.warning("face_detector_init_failed", error=str(exc))
        return None


def _detect_raw(frame: np.ndarray) -> list[tuple[int, int, int, int, float]] | None:
    """Run MediaPipe face detection on a BGR frame.

    Converts the frame BGR->RGB (cv2 yields BGR; MediaPipe expects RGB), runs
    the cached detector, and returns each detection as an absolute-pixel
    ``(x, y, width, height, confidence)`` tuple.

    Args:
        frame: BGR numpy array from a video frame.

    Returns:
        List of detection tuples, or ``None`` if detection is unavailable or
        fails (both cases are logged where appropriate).
    """
    detector = _get_face_detector()
    if detector is None:
        return None

    try:
        import mediapipe as mp

        rgb_frame = np.ascontiguousarray(frame[:, :, ::-1])
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = detector.detect(mp_image)
    except Exception as exc:
        log.warning("face_detection_failed", error=str(exc))
        return None

    boxes: list[tuple[int, int, int, int, float]] = []
    for detection in result.detections:
        bbox = detection.bounding_box
        score = float(detection.categories[0].score) if detection.categories else 0.0
        boxes.append(
            (
                int(bbox.origin_x),
                int(bbox.origin_y),
                int(bbox.width),
                int(bbox.height),
                score,
            )
        )
    return boxes


def detect_face_center(frame: np.ndarray) -> tuple[int, int] | None:
    """Detect the center (x, y) of the most prominent face in the frame.

    Uses the MediaPipe Tasks FaceDetector. Picks the highest-confidence
    detection whose relative area falls within plausible bounds. Returns
    ``None`` if detection is unavailable or no qualifying face is found.

    Args:
        frame: BGR numpy array from a video frame.

    Returns:
        (x, y) pixel coordinates of the face center, or ``None`` if not
        detected.
    """
    height, width = frame.shape[:2]
    frame_area = width * height
    if frame_area <= 0:
        return None

    detections = _detect_raw(frame)
    if not detections:
        return None

    best_face: tuple[int, int] | None = None
    best_confidence: float = -1.0

    for x, y, w, h, confidence in detections:
        # Skip faces that are too small to be reliable detections.
        if w <= _MIN_FACE_PIXELS or h <= _MIN_FACE_PIXELS:
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
        frame_width: Original frame width in pixels (must be positive).
        frame_height: Original frame height in pixels (must be positive).
        face_center: (x, y) center of detected face, or None.
        target_width: Desired output width (default 1080, must be positive).
        target_height: Desired output height (default 1920, must be positive).

    Returns:
        (x, y, width, height) crop box where (x, y) is the top-left corner
        and (width, height) are the crop dimensions.

    Raises:
        ValueError: If any of the frame or target dimensions is not positive.
    """
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError(f"frame dimensions must be positive, got {frame_width}x{frame_height}")
    if target_width <= 0 or target_height <= 0:
        raise ValueError(f"target dimensions must be positive, got {target_width}x{target_height}")

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


def get_representative_frame(video_path: str | Path, timestamp_s: float = 1.0) -> np.ndarray | None:
    """Extract a single frame from a video file for face detection.

    Attempts to use opencv-python (cv2) to decode the frame. If cv2 is not
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


def _segment_sample_timestamps(start_s: float, end_s: float, samples: int) -> list[float]:
    """Return up to ``samples`` evenly spaced timestamps across a segment.

    The first and last timestamps coincide with ``start_s`` and ``end_s``;
    interior points are spread uniformly between them. Degenerate inputs are
    handled defensively: a non-positive ``samples`` count or a zero-length
    segment collapses to a single timestamp at ``start_s``.

    Args:
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        samples: Desired number of sample timestamps.

    Returns:
        A list of timestamps (seconds) in ascending order, length >= 1.
    """
    count = max(1, samples)
    if end_s <= start_s:
        return [start_s]
    if count == 1:
        return [start_s]
    step = (end_s - start_s) / (count - 1)
    return [start_s + step * i for i in range(count)]


def detect_face_center_multi(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int = _DEFAULT_FRAME_SAMPLES,
) -> tuple[int, int] | None:
    """Aggregate face centers across several frames of a segment (spec 4.14).

    Samples up to ``samples`` frames evenly spaced across ``[start_s, end_s]``,
    runs single-frame detection on each, and aggregates the successful results
    by taking the median x and median y center. The median is robust to a small
    number of outlier frames (e.g. a brief misdetection) that would otherwise
    skew a mean. Frames that fail to decode or that yield no face are ignored.
    Returns ``None`` when no sampled frame yields a face, signalling callers to
    fall back to a center crop.

    This is an additive capability layered on :func:`detect_face_center`; the
    single-frame signature is unchanged.

    Args:
        video_path: Path to the source video file.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        samples: Maximum number of frames to sample across the segment.

    Returns:
        (x, y) median pixel center of detected faces, or ``None`` if no frame
        produced a qualifying face.
    """
    timestamps = _segment_sample_timestamps(start_s, end_s, samples)

    centers: list[tuple[int, int]] = []
    for timestamp_s in timestamps:
        frame = get_representative_frame(video_path, timestamp_s=timestamp_s)
        if frame is None:
            continue
        center = detect_face_center(frame)
        if center is not None:
            centers.append(center)

    if not centers:
        log.info(
            "face_multi_no_detections",
            path=str(video_path),
            sampled=len(timestamps),
        )
        return None

    median_x = int(median([c[0] for c in centers]))
    median_y = int(median([c[1] for c in centers]))
    log.info(
        "face_multi_aggregated",
        detections=len(centers),
        sampled=len(timestamps),
        center=(median_x, median_y),
    )
    return median_x, median_y


# end src/pipeline/face_detect.py
