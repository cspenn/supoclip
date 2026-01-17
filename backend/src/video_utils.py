"""
Utility functions for video-related operations.
Optimized for MoviePy v2, AssemblyAI integration, and high-quality output.
"""

from contextlib import suppress
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union
import logging
import json
import numpy as np
import cv2

from moviepy import (
    VideoFileClip,
    CompositeVideoClip,
    ImageClip,
)
from moviepy.video.fx import FadeIn, FadeOut, Margin


from .config import Config
from .subtitle_renderer import BrowserSubtitleRenderer
from .transcription_mlx import (
    transcribe_video_mlx,
)

logger = logging.getLogger(__name__)
config = Config()

# Resolution presets for 9:16 vertical format
# Format: (width, height) - maintains 9:16 aspect ratio
RESOLUTION_PRESETS = {
    "480p": (480, 854),  # SD quality - smallest file size
    "720p": (720, 1280),  # HD quality - balanced size/quality (default)
    "1080p": (1080, 1920),  # Full HD quality - best quality, largest file size
}

# Audio buffer in seconds to prevent cutting off words at clip boundaries
# Video starts buffer-seconds earlier, so subtitles must be offset by this amount
AUDIO_BUFFER_SECONDS: float = 0.15


def resolve_font_path(font_family: str) -> str:
    """
    Resolve font file path, checking bundled fonts first, then system fonts.

    This function handles font resolution in the following priority:
    1. Check if bundled font exists (backend/fonts/{font_family}.ttf)
    2. Try common font name variations (with hyphens, underscores, etc.)
    3. Fall back to default bundled font

    Args:
        font_family: Font name (e.g., "Barlow Condensed Semi Bold")

    Returns:
        Full path to .ttf file
    """
    # First, check if bundled font exists with exact name
    bundled_fonts_dir = Path(__file__).parent.parent / "fonts"
    font_path = bundled_fonts_dir / f"{font_family}.ttf"

    if font_path.exists():
        logger.debug(f"Found bundled font: {font_family}")
        return str(font_path)

    # Try common variations (replace spaces with hyphens/underscores)
    variations = [
        font_family.replace(" ", "-"),
        font_family.replace(" ", "_"),
        font_family.replace(" Semi ", "-Semi"),  # e.g., "Barlow Condensed Semi Bold"
    ]

    for variation in variations:
        font_path = bundled_fonts_dir / f"{variation}.ttf"
        if font_path.exists():
            logger.debug(f"Found bundled font with variation: {variation}")
            return str(font_path)

    # Try system fonts via database (synchronous lookup)
    try:
        import sqlite3

        db_url = config.database_url or "sqlite+aiosqlite:///./supoclip.db"
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite://", "")

        if Path(db_path).exists():
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path FROM system_fonts WHERE name = ? AND is_valid = 1",
                (font_family,),
            )
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                system_font_path = result[0]
                if Path(system_font_path).exists():
                    logger.info(
                        f"Found system font '{font_family}' at: {system_font_path}"
                    )
                    return system_font_path
                else:
                    logger.warning(f"System font file not found: {system_font_path}")
    except Exception as e:
        logger.debug(f"Could not query system fonts database: {e}")

    # Fall back to default font
    default_font = bundled_fonts_dir / "THEBOLDFONT-FREEVERSION.ttf"
    logger.warning(
        f"Font '{font_family}' not found. Using default font: {default_font}"
    )
    return str(default_font)


class VideoProcessor:
    """Handles video processing operations with optimized settings."""

    def __init__(
        self,
        font_family: str = "THEBOLDFONT-FREEVERSION",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ):
        self.font_family = font_family
        self.font_size = font_size
        self.font_color = font_color
        # Resolve font path using comprehensive lookup
        self.font_path = resolve_font_path(font_family)

    def get_optimal_encoding_settings(
        self, target_quality: str = "high"
    ) -> Dict[str, Any]:
        """Get optimal encoding settings for different quality levels."""
        settings = {
            "high": {
                "codec": "libx264",
                "audio_codec": "aac",
                "bitrate": "8000k",
                "audio_bitrate": "256k",
                "preset": "medium",
                "ffmpeg_params": [
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    "main",
                    "-level",
                    "4.1",
                ],
            },
            "medium": {
                "codec": "libx264",
                "audio_codec": "aac",
                "bitrate": "4000k",
                "audio_bitrate": "192k",
                "preset": "fast",
                "ffmpeg_params": ["-crf", "23", "-pix_fmt", "yuv420p"],
            },
        }
        return settings.get(target_quality, settings["high"])


def get_video_transcript(video_path: Path) -> str:
    """
    Get transcript using parakeet-mlx (offline, Apple Silicon optimized).

    Replaces AssemblyAI with local processing for privacy and offline capability.
    Formats transcript with precise word-level timestamps (SRT-style) for AI analysis.
    """
    logger.info(f"Getting transcript for: {video_path}")

    try:
        # Use parakeet-mlx for local transcription
        logger.info("Starting parakeet-mlx transcription (offline)")
        result = transcribe_video_mlx(video_path, model_id=config.parakeet_model)

        # Format transcript with precise word-level timing for AI analysis
        if result.get("words"):
            words = result["words"]
            logger.info(f"Processing {len(words)} words with precise timing")

            # Use SRT-style format with millisecond precision for AI analysis
            result_text = format_transcript_for_ai(result)
            logger.info(f"Transcript formatted with SRT: {len(result_text)} chars")
            return result_text
        else:
            logger.error("No words found in transcription result")
            return ""

    except Exception as e:
        logger.error(f"Error in transcription: {e}")
        raise


def cache_transcript_data(video_path: Path, transcript) -> None:
    """Cache AssemblyAI transcript data for subtitle generation."""
    cache_path = video_path.with_suffix(".transcript_cache.json")

    # Store word-level data
    words_data = []
    if transcript.words:
        for word in transcript.words:
            words_data.append(
                {
                    "text": word.text,
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.confidence
                    if hasattr(word, "confidence")
                    else 1.0,
                }
            )

    cache_data = {"words": words_data, "text": transcript.text}

    with cache_path.open("w") as f:
        json.dump(cache_data, f)

    logger.info(f"Cached {len(words_data)} words to {cache_path}")


def load_cached_transcript_data(video_path: Path) -> Optional[Dict]:
    """Load cached AssemblyAI transcript data."""
    cache_path = video_path.with_suffix(".transcript_cache.json")

    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load transcript cache: {e}")
        return None


def extract_text_from_cache(
    video_path: Path, start_time_seconds: float, end_time_seconds: float
) -> Optional[str]:
    """
    Extract verbatim text from transcript cache for a given time range.

    This ensures captions display the exact words spoken in the video,
    not the AI's summary or paraphrase.

    Args:
        video_path: Path to the video file (cache file shares the same stem)
        start_time_seconds: Start time in seconds
        end_time_seconds: End time in seconds

    Returns:
        Verbatim text from transcript, or None if cache unavailable
    """
    transcript_data = load_cached_transcript_data(video_path)
    if not transcript_data or "words" not in transcript_data:
        logger.warning(f"No transcript cache available for {video_path}")
        return None

    start_ms = int(start_time_seconds * 1000)
    end_ms = int(end_time_seconds * 1000)

    words_in_range = []
    for word in transcript_data["words"]:
        word_start = word.get("start", 0)
        word_text = word.get("text", "")

        # Include word ONLY if it STARTS at or after clip start time
        # This prevents "ghost words" where the transcript shows words
        # that the viewer doesn't hear (because they start before the clip)
        if word_start >= start_ms and word_start < end_ms:
            words_in_range.append(word_text)

    if words_in_range:
        extracted_text = " ".join(words_in_range)
        logger.info(
            f"Extracted {len(words_in_range)} words from cache for {start_time_seconds:.2f}s-{end_time_seconds:.2f}s"
        )
        return extracted_text

    logger.warning(
        f"No words found in cache for time range {start_time_seconds:.2f}s-{end_time_seconds:.2f}s"
    )
    return None


def format_ms_to_timestamp(ms: int) -> str:
    """Format milliseconds to MM:SS format."""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def format_ms_to_timestamp_precise(ms: int) -> str:
    """Format milliseconds to MM:SS.mmm format with millisecond precision."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds) // 60
    seconds = int(total_seconds) % 60
    milliseconds = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


class TargetDimensionCalculator:
    """Calculate target dimensions for video cropping."""

    @staticmethod
    def calculate(
        original_width: int, original_height: int, target_ratio: float
    ) -> Tuple[int, int]:
        """Calculate target width and height maintaining aspect ratio."""
        if original_width / original_height > target_ratio:
            new_width = round_to_even(int(original_height * target_ratio))
            new_height = round_to_even(original_height)
        else:
            new_width = round_to_even(original_width)
            new_height = round_to_even(int(original_width / target_ratio))
        return new_width, new_height


class FaceCenteredCropCalculator:
    """Calculate crop position based on detected faces."""

    @staticmethod
    def calculate(
        face_centers: List[Tuple[float, float, float, float]],
        new_width: int,
        new_height: int,
        original_width: int,
        original_height: int,
    ) -> Tuple[int, int]:
        """Calculate face-centered crop offsets."""
        total_weight = sum(area * confidence for _, _, area, confidence in face_centers)
        if total_weight == 0:
            return CenterCropCalculator.calculate(
                new_width, new_height, original_width, original_height
            )

        weighted_x = (
            sum(x * area * confidence for x, y, area, confidence in face_centers)
            / total_weight
        )
        weighted_y = (
            sum(y * area * confidence for x, y, area, confidence in face_centers)
            / total_weight
        )

        # Add slight bias towards upper portion for better face framing
        weighted_y = max(0, weighted_y - new_height * 0.1)

        x_offset = max(
            0, min(int(weighted_x - new_width // 2), original_width - new_width)
        )
        y_offset = max(
            0, min(int(weighted_y - new_height // 2), original_height - new_height)
        )

        return round_to_even(x_offset), round_to_even(y_offset)


class CenterCropCalculator:
    """Calculate center crop position."""

    @staticmethod
    def calculate(
        new_width: int, new_height: int, original_width: int, original_height: int
    ) -> Tuple[int, int]:
        """Calculate center crop offsets."""
        x_offset = (
            (original_width - new_width) // 2 if original_width > new_width else 0
        )
        y_offset = (
            (original_height - new_height) // 2 if original_height > new_height else 0
        )
        return round_to_even(x_offset), round_to_even(y_offset)


class TranscriptLineBreaker:
    """Determine when to break lines in transcripts."""

    MAX_WORDS_PER_LINE = 20
    BREAK_PUNCTUATION = {".", "!", "?"}

    @staticmethod
    def should_break_line(word_text: str, word_count: int) -> bool:
        """Determine if line should break at this word.

        Args:
            word_text: Text of current word
            word_count: Number of words in current line

        Returns:
            True if line should break, False otherwise
        """
        # Always break on strong punctuation (sentence boundaries)
        # Fix: strip whitespace to handle tokens like "word. "
        clean_text = word_text.strip()
        if clean_text and any(
            clean_text.endswith(punct)
            for punct in TranscriptLineBreaker.BREAK_PUNCTUATION
        ):
            return True

        # Break on commas only if line is getting long to avoid chopping phrases
        if clean_text and clean_text.endswith(",") and word_count > 15:
            return True

        # Hard limit to preventing extremely long lines
        if word_count >= TranscriptLineBreaker.MAX_WORDS_PER_LINE:
            return True

        return False


class TranscriptLineFormatter:
    """Format transcript lines with timing information."""

    def __init__(self):
        """Initialize formatter with empty state."""
        self.lines = []
        self.current_line = []
        self.current_start = None

    def add_word(self, word_data: Dict[str, Any]) -> None:
        """Add word to current line.

        Args:
            word_data: Dictionary with 'text', 'start', 'end' keys
        """
        word_text = word_data.get("text", "")
        start_ms = word_data.get("start", 0)
        end_ms = word_data.get("end", 0)

        if not word_text:
            return

        if self.current_start is None:
            self.current_start = start_ms

        self.current_line.append((word_text, start_ms, end_ms))

    def finalize_current_line(self) -> None:
        """Format and append current line to output."""
        if not self.current_line or self.current_start is None:
            return

        start_time = format_ms_to_timestamp_precise(self.current_start)
        end_time = format_ms_to_timestamp_precise(self.current_line[-1][2])
        line_text = " ".join(word[0] for word in self.current_line)
        formatted = f"[{start_time} - {end_time}] {line_text}"
        self.lines.append(formatted)

        self.current_line = []
        self.current_start = None

    def get_formatted_output(self) -> str:
        """Return all formatted lines joined by newlines.

        Returns:
            Formatted transcript string
        """
        return "\n".join(self.lines)


def format_transcript_for_ai(transcript_data: Dict[str, Any]) -> str:
    """
    Format transcript with SRT-style precise timing for AI analysis.

    Each line shows exact word timing for AI to select precise clip boundaries.
    Format: [MM:SS.mmm - MM:SS.mmm] word

    Args:
        transcript_data: Dictionary with 'words' array containing word objects with 'text', 'start', 'end' keys

    Returns:
        Formatted string with word-level timestamps for AI analysis
    """
    if not transcript_data or "words" not in transcript_data:
        return ""

    words = transcript_data["words"]
    if not words:
        return ""

    formatter = TranscriptLineFormatter()
    breaker = TranscriptLineBreaker()

    for word_data in words:
        word_text = word_data.get("text", "")
        if not word_text:
            continue

        formatter.add_word(word_data)

        if breaker.should_break_line(word_text, len(formatter.current_line)):
            formatter.finalize_current_line()

    # Handle remaining words
    formatter.finalize_current_line()

    return formatter.get_formatted_output()


def round_to_even(value: int) -> int:
    """Round integer to nearest even number for H.264 compatibility."""
    return value - (value % 2)


def detect_optimal_crop_region(
    video_clip: VideoFileClip,
    start_time: float,
    end_time: float,
    target_ratio: float = 9 / 16,
) -> Tuple[int, int, int, int]:
    """Detect optimal crop region using improved face detection."""
    try:
        original_width, original_height = video_clip.size

        # Calculate target dimensions
        new_width, new_height = TargetDimensionCalculator.calculate(
            original_width, original_height, target_ratio
        )

        # Detect faces and calculate crop position
        face_centers = detect_faces_in_clip(video_clip, start_time, end_time)

        if face_centers:
            # Convert face centers to float tuples for type compatibility
            face_centers_float = [
                (float(x), float(y), float(w), h) for x, y, w, h in face_centers
            ]
            x_offset, y_offset = FaceCenteredCropCalculator.calculate(
                face_centers_float,
                new_width,
                new_height,
                original_width,
                original_height,
            )
            logger.info(
                f"Face-centered crop: {len(face_centers)} faces detected with improved algorithm"
            )
        else:
            x_offset, y_offset = CenterCropCalculator.calculate(
                new_width, new_height, original_width, original_height
            )
            logger.info("Using center crop (no faces detected)")

        logger.info(
            f"Crop dimensions: {new_width}x{new_height} at offset ({x_offset}, {y_offset})"
        )
        return (x_offset, y_offset, new_width, new_height)

    except Exception as e:
        logger.error(f"Error in crop detection: {e}")
        # Fallback to center crop
        original_width, original_height = video_clip.size
        new_width, new_height = TargetDimensionCalculator.calculate(
            original_width, original_height, target_ratio
        )

        x_offset, y_offset = CenterCropCalculator.calculate(
            new_width, new_height, original_width, original_height
        )
        return (x_offset, y_offset, new_width, new_height)


class FaceDetector:
    """Abstract base class for face detectors."""

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces in frame.

        Args:
            frame: Video frame as numpy array

        Returns:
            List of (x, y, w, h, confidence) tuples
        """
        raise NotImplementedError


class MediaPipeFaceDetector(FaceDetector):
    """MediaPipe face detection."""

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

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using MediaPipe."""
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
    """OpenCV DNN face detection."""

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

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using OpenCV DNN."""
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
    """Haar Cascade face detection (fallback)."""

    def __init__(self):
        """Initialize Haar cascade detector."""
        self.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Detect faces using Haar cascade."""
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
    """Sample frames from video clips."""

    @staticmethod
    def generate_sample_times(start_time: float, end_time: float) -> List[float]:
        """Generate times to sample for face detection.

        Args:
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds

        Returns:
            List of sample times
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
        """Initialize detector chain."""
        self.detectors = [
            MediaPipeFaceDetector(),
            OpenCVDNNFaceDetector(),
            HaarCascadeFaceDetector(),
        ]

    def detect_in_frame(self, frame: np.ndarray) -> List[Tuple[int, int, int, float]]:
        """Detect faces in single frame using detector chain.

        Args:
            frame: Video frame

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
) -> List[Tuple[int, int, int, float]]:
    """
    Improved face detection using multiple methods and temporal consistency.
    Returns list of (x, y, area, confidence) tuples.
    """
    try:
        # Initialize face detection service
        service = FaceDetectionService()

        # Generate sample times
        sample_times = VideoFrameSampler.generate_sample_times(start_time, end_time)
        logger.info(f"Sampling {len(sample_times)} frames for face detection")

        # Detect faces in all sampled frames
        face_centers = []
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
    face_centers: List[Tuple[int, int, int, float]],
) -> List[Tuple[int, int, int, float]]:
    """Remove face detections that are outliers (likely false positives)."""
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


def parse_timestamp_to_seconds(timestamp_str: str) -> float:
    """Parse timestamp string to seconds."""
    try:
        timestamp_str = timestamp_str.strip()
        logger.info(f"Parsing timestamp: '{timestamp_str}'")  # Debug logging

        if ":" in timestamp_str:
            parts = timestamp_str.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = float(parts[1])
                result = minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result
            elif len(parts) == 3:  # HH:MM:SS format
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                result = hours * 3600 + minutes * 60 + seconds
                logger.info(f"Parsed '{timestamp_str}' -> {result}s")
                return result

        # Try parsing as pure seconds
        result = float(timestamp_str)
        logger.info(f"Parsed '{timestamp_str}' as seconds -> {result}s")
        return result

    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return 0.0


class SubtitleWordFilter:
    """Filter and prepare words for subtitle creation."""

    @staticmethod
    def get_relevant_words(
        transcript_data: Dict[str, Any], clip_start_ms: int, clip_end_ms: int
    ) -> List[Dict[str, Any]]:
        """Extract words that fall within clip timerange."""
        relevant_words = []
        for word_data in transcript_data.get("words", []):
            word_start = word_data["start"]
            word_end = word_data["end"]

            # STRICT rule: word must START within clip (matches extract_text_from_cache)
            if word_start >= clip_start_ms and word_start < clip_end_ms:
                relative_start = (word_start - clip_start_ms) / 1000.0
                relative_end = min(
                    (clip_end_ms - clip_start_ms) / 1000.0,
                    (word_end - clip_start_ms) / 1000.0,
                )

                if relative_end > relative_start:
                    relevant_words.append(
                        {
                            "text": word_data["text"],
                            "start": relative_start,
                            "end": relative_end,
                            "confidence": word_data.get("confidence", 1.0),
                        }
                    )
        if relevant_words:
            first_words = [(w["text"], round(w["start"], 2)) for w in relevant_words[:3]]
            logger.info(f"[SYNC_DIAG] First 3 words: {first_words}")
        return relevant_words


class SubtitleTextClipCreator:
    """Create text clips with automatic font size adjustment."""

    MAX_SUBTITLE_LINES = 2
    HORIZONTAL_PADDING = 0.1
    MIN_FONT_SIZE = 16
    FONT_SIZE_REDUCTION = 0.85
    STROKE_WIDTH = (
        1  # Stroke width for text outline - used in both TextClip and margin calc
    )

    @staticmethod
    def _create_clip_candidate(
        text: str,
        font_path: str,
        font_size: int,
        font_color: str,
        max_text_width: int,
        is_single_word: bool,
        style_options: Optional[Dict[str, Any]] = None,
    ) -> Optional[ImageClip]:
        """
        Create a subtitle clip using BrowserSubtitleRenderer.

        This replaces the old TextClip method. It renders the text to a PNG
        using Playwright and then loads it as an ImageClip.
        """
        style_options = style_options or {}

        try:
            # We use a context manager for the renderer to ensure browser starts/stops if needed
            # In a production env, instance persistence would be better, but for now this ensures safety
            with BrowserSubtitleRenderer() as renderer:
                # Extract font family from path or default to standard
                # Note: Playwright uses system fonts. If custom font path is provided,
                # we'd need to load it via @font-face in CSS.
                # For now, we assume the font name matches the file name or is standard.
                font_family = Path(font_path).stem

                image_path = renderer.render_text_to_image(
                    text=text,
                    font_family=font_family,
                    font_size=font_size,
                    color=font_color,
                    width=max_text_width,
                    stroke_width=style_options.get(
                        "stroke_width", SubtitleTextClipCreator.STROKE_WIDTH
                    ),
                    stroke_color=style_options.get("stroke_color", "black"),
                    shadow_color=style_options.get("shadow_color"),
                    shadow_offset=style_options.get("shadow_offset", 2),
                    text_transform=style_options.get("text_transform", "none"),
                    font_weight=style_options.get("font_weight", "bold"),
                )

                if image_path:
                    # Load the generated image as a clip
                    img_clip = ImageClip(str(image_path))
                    # Set duration placeholder (will be set by caller)
                    # We deleted the temp file in renderer but loading might need it to persist...
                    # Actually local ImageClip needs file to exist. BrowserRenderer creates temp file.
                    # We should rely on OS temp cleanup or explicitly manage it.
                    # For this implementation, we let Python/OS handle temp file lifecycle.
                    return img_clip

            return None

        except Exception as e:
            logger.error(f"Browser rendering failed in factory: {e}")
            return None

    @staticmethod
    def create_text_clip(
        text: str,
        font_path: str,
        font_size: int,
        font_color: str,
        video_width: int,
        style_options: Optional[Dict[str, Any]] = None,
    ) -> Optional[ImageClip]:
        """Create text clip with automatic size adjustment to fit lines."""
        max_text_width = int(
            video_width * (1 - 2 * SubtitleTextClipCreator.HORIZONTAL_PADDING)
        )
        current_font_size = font_size
        max_attempts = 3

        # Determine method based on content
        is_single_word = len(text.strip().split()) == 1

        for attempt in range(max_attempts):
            text_clip = SubtitleTextClipCreator._create_clip_candidate(
                text,
                font_path,
                current_font_size,
                font_color,
                max_text_width,
                is_single_word,
                style_options,
            )

            if not text_clip:
                return None

            # Add margin to prevent stroke and descenders from being cut off at edges
            bottom_margin = max(
                10, int(current_font_size * 0.60) + SubtitleTextClipCreator.STROKE_WIDTH
            )
            text_clip = text_clip.with_effects(
                [Margin(bottom=bottom_margin, top=5, left=3, right=3, opacity=0)]
            )

            # Check if it fits within max lines
            text_height = (
                text_clip.size[1]
                if hasattr(text_clip, "size") and text_clip.size
                else 40
            )
            estimated_line_height = current_font_size * 1.5
            estimated_lines = text_height / estimated_line_height

            if estimated_lines <= SubtitleTextClipCreator.MAX_SUBTITLE_LINES:
                return text_clip

            # Reduce font size and try again
            current_font_size = int(
                current_font_size * SubtitleTextClipCreator.FONT_SIZE_REDUCTION
            )
            if current_font_size < SubtitleTextClipCreator.MIN_FONT_SIZE:
                current_font_size = SubtitleTextClipCreator.MIN_FONT_SIZE
                # One last attempt at min font size will happen in next loop if range permits,
                # but if we are already at min, we might just have to accept it or break.
                # Logic below: loop wraps around. If we are at attempt 2 and hit min size, loop finishes.
                if attempt == max_attempts - 1:
                    return text_clip  # Return what we have at min font size

        # If loop exits without returning (shouldn't happen, but satisfies type checker)
        return None


def _find_closest_word_index(words: list[dict], target_ms: int) -> int:
    """Find the index of the word closest to the target timestamp.

    Args:
        words: List of word dictionaries with 'start' timestamps
        target_ms: Target timestamp in milliseconds

    Returns:
        Index of closest word, or -1 if no words found
    """
    closest_idx = -1
    min_diff = float("inf")

    for i, word in enumerate(words):
        word_start = word.get("start", 0)
        diff = abs(word_start - target_ms)
        if diff < min_diff:
            min_diff = diff
            closest_idx = i

    return closest_idx


def _is_sentence_start_word(words: list[dict], index: int) -> bool:
    """Check if the word at the given index is a valid sentence start.

    A word is a sentence start if:
    1. It's the first word (index 0), OR
    2. It starts with an uppercase letter AND the previous word ends with [.!?]

    Args:
        words: List of word dictionaries
        index: Index of the word to check

    Returns:
        True if the word is a valid sentence start
    """
    if index == 0:
        return True

    word_text = words[index].get("text", "").strip()
    if not word_text or not word_text[0].isupper():
        return False

    prev_text = words[index - 1].get("text", "").strip()
    return bool(prev_text and prev_text[-1] in (".", "!", "?"))


def _find_sentence_start_backwards(
    words: list[dict], start_idx: int, target_ms: int, window_ms: int
) -> int:
    """Search backwards from start_idx to find a sentence start within the window.

    Args:
        words: List of word dictionaries
        start_idx: Index to start searching from
        target_ms: Original target timestamp in milliseconds
        window_ms: Maximum window to search backwards in milliseconds

    Returns:
        Index of the sentence start word, or -1 if none found
    """
    for i in range(start_idx, -1, -1):
        curr_start = words[i].get("start", 0)

        # Stop if we've gone too far back from the target start time
        if (target_ms - curr_start) > window_ms:
            break

        # Skip if we've gone forward significantly (edge case)
        if (curr_start - target_ms) > 2000:
            continue

        if _is_sentence_start_word(words, i):
            return i

    return -1


def snap_segment_to_sentence_start(
    video_path: Path, start_time_seconds: float, search_window_seconds: float = 2.0
) -> Tuple[float, str, str]:
    """Find the nearest valid sentence start to the given timestamp.

    Strategies:
    1. Find the word corresponding to the start time.
    2. Search backwards (up to search_window_seconds) for a 'Sentence Starter'.
       - A word that starts with an Uppercase letter AND matches strict criteria.
       - Criteria: Previous word ends with [.!?] OR it's the very first word.

    Returns:
        Tuple(new_start_seconds, matched_word_text, conversion_reason)
        If no better start found, returns original start time.
    """
    transcript_data = load_cached_transcript_data(video_path)
    if not transcript_data or "words" not in transcript_data:
        return start_time_seconds, "", "No cache available"

    words = transcript_data["words"]
    start_ms = int(start_time_seconds * 1000)
    window_ms = int(search_window_seconds * 1000)

    # Find the word index closest to start_time
    closest_idx = _find_closest_word_index(words, start_ms)
    if closest_idx == -1:
        return start_time_seconds, "", "No words found"

    # Search backwards for sentence start within the window
    best_start_idx = _find_sentence_start_backwards(
        words, closest_idx, start_ms, window_ms
    )

    if best_start_idx != -1:
        new_word = words[best_start_idx]
        new_start_ms = new_word.get("start", 0)
        new_start_seconds = new_start_ms / 1000.0
        return (
            new_start_seconds,
            new_word.get("text", ""),
            f"Snapped to '{new_word.get('text', '')}'",
        )

    return start_time_seconds, "", "No better start found"


class SubtitlePositioner:
    """Calculate subtitle positioning on video."""

    @staticmethod
    def calculate_position(
        video_height: int,
        text_height: int,
        video_width: int = 0,  # Unused if centering, but needed for future absolute X
        position_options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Union[str, int], int]:
        """
        Calculate subtitle position based on provided options or defaults.

        Args:
            video_height: Height of video
            text_height: Height of subtitle clip
            video_width: Width of video
            position_options: Dict with 'x', 'y' (float 0-1) and 'alignment'

        Returns:
            Tuple (x_pos, y_pos) compatible with MoviePy
        """
        # Default options
        x_rel = 0.5  # Center
        y_rel = 0.65  # Lower third
        alignment = "center"

        if position_options:
            x_rel = position_options.get("x", x_rel)
            y_rel = position_options.get("y", y_rel)
            alignment = position_options.get("alignment", alignment)

        # Calculate Y position
        # If centering vertically at that point: y_px - height/2
        vertical_position = int(video_height * y_rel - text_height // 2)

        # Calculate X position
        if alignment == "center" and position_options is None:
            return ("center", vertical_position)

        # If explicit X provided
        horizontal_position: str | int = "center"  # Default
        if position_options and "x" in position_options:
            # For MoviePy, 'center' is magic string. If we use int, it's absolute.
            # Support 'center' string if x is 0.5 and alignment is center
            if x_rel == 0.5 and alignment == "center":
                horizontal_position = "center"
            else:
                horizontal_position = int(video_width * x_rel)

        return (horizontal_position, vertical_position)


class SubtitleClipBuilder:
    """Build subtitle clips with word-by-word synchronization (TikTok-style)."""

    @staticmethod
    def build_clips(
        relevant_words: List[Dict[str, Any]],
        font_path: str,
        font_size: int,
        font_color: str,
        video_width: int,
        video_height: int,
        words_per_subtitle: int = 1,
        style_options: Optional[Dict[str, Any]] = None,
        position_options: Optional[Dict[str, Any]] = None,
    ) -> List[ImageClip]:
        """Build individual subtitle clips for each word with exact timing.

        This creates TikTok/YouTube Shorts-style captions where each word appears
        exactly when spoken, ensuring perfect audio-caption synchronization.

        Args:
            relevant_words: List of word dictionaries with 'text', 'start', 'end' keys
            font_path: Path to font file
            font_size: Font size in pixels
            font_color: Font color (hex or name)
            video_width: Video width for text wrapping
            video_height: Video height for positioning
            words_per_subtitle: Number of words per caption (default: 1 for word-by-word)

        Returns:
            List of ImageClip objects with precise timing
        """
        subtitle_clips = []

        # Word-by-word mode: create one clip per word
        for word_data in relevant_words:
            word_start = word_data["start"]
            word_end = word_data["end"]
            word_duration = word_end - word_start

            # Skip very short words (< 50ms) - likely transcription errors
            if word_duration < 0.05:
                logger.debug(
                    f"Skipping very short word '{word_data.get('text')}' (duration: {word_duration:.3f}s)"
                )
                continue

            text = word_data["text"]

            try:
                # Create text clip for this single word
                text_clip = SubtitleTextClipCreator.create_text_clip(
                    text, font_path, font_size, font_color, video_width, style_options
                )

                if text_clip:
                    # Set exact timing for this word
                    text_clip = text_clip.with_duration(word_duration).with_start(
                        word_start
                    )

                    # Calculate position
                    text_height = text_clip.size[1] if text_clip.size else 40
                    position = SubtitlePositioner.calculate_position(
                        video_height, text_height, video_width, position_options
                    )
                    text_clip = text_clip.with_position(position)
                    subtitle_clips.append(text_clip)

                    logger.debug(
                        f"Created caption for '{text}' at {word_start:.2f}s-{word_end:.2f}s"
                    )

            except Exception as e:
                logger.warning(f"Failed to create subtitle for '{text}': {e}")
                continue

        logger.info(f"Created {len(subtitle_clips)} word-by-word caption clips")
        return subtitle_clips


def create_assemblyai_subtitles(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_width: int,
    video_height: int,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    subtitle_style: Optional[Dict[str, Any]] = None,
    subtitle_position: Optional[Dict[str, Any]] = None,
) -> List[ImageClip]:
    """
    Create subtitles using parakeet-mlx's precise word timing.

    Legacy function name kept for backward compatibility.
    Uses cached transcript data from parakeet-mlx transcription.
    """
    transcript_data = load_cached_transcript_data(video_path)
    if transcript_data:
        words = transcript_data.get("words", [])
        logger.info(f"[SYNC_DIAG] Cache: {len(words)} words, clip_range={clip_start:.2f}-{clip_end:.2f}s")

    if not transcript_data or not transcript_data.get("words"):
        logger.warning("No cached transcript data available for subtitles")
        return []

    # Convert clip timing to milliseconds and get relevant words
    clip_start_ms = int(clip_start * 1000)
    clip_end_ms = int(clip_end * 1000)
    relevant_words = SubtitleWordFilter.get_relevant_words(
        transcript_data, clip_start_ms, clip_end_ms
    )

    if not relevant_words:
        logger.warning("No words found in clip timerange")
        return []

    # Setup processor and font size
    processor = VideoProcessor(font_family, font_size, font_color)
    calculated_font_size = max(20, min(40, int(font_size * (video_width / 720))))

    # Build subtitle clips
    subtitle_clips = SubtitleClipBuilder.build_clips(
        relevant_words,
        processor.font_path,
        calculated_font_size,
        font_color,
        video_width,
        video_height,
        1,  # words_per_subtitle
        subtitle_style,
        subtitle_position,
    )

    logger.info(f"Created {len(subtitle_clips)} subtitle elements from AssemblyAI data")
    return subtitle_clips


def _add_logo_overlay(
    final_clips: list,
    logo_path: Optional[str],
    logo_position: str,
    video_width: int,
    video_height: int,
    clip_duration: float,
) -> None:
    """Add logo overlay to clip if provided.

    Modifies final_clips list in-place by appending logo clip if successful.

    Args:
        final_clips: List of clips to composite (modified in-place)
        logo_path: Path to logo image file
        logo_position: Corner position ("top-left", "top-right", etc.)
        video_width: Width of the video for positioning
        video_height: Height of the video for positioning
        clip_duration: Duration of the clip
    """
    if not logo_path:
        return

    logger.info(f"VIDEO_UTILS: Processing logo_path='{logo_path}'")

    # Convert string to Path if needed
    logo_path_obj = Path(logo_path) if isinstance(logo_path, str) else logo_path
    logger.info(f"VIDEO_UTILS: Exists on disk? {logo_path_obj.exists()}")

    # Ensure absolute path
    if not logo_path_obj.is_absolute():
        logo_path_obj = logo_path_obj.resolve()
        logger.info(f"Converted to absolute path: {logo_path_obj}")

    if not logo_path_obj.exists():
        logger.warning(f"Logo file NOT found at: {logo_path_obj}")
        return

    logger.info(f"Logo file found, adding overlay from: {logo_path_obj}")
    try:
        from moviepy import ImageClip

        logo_clip = ImageClip(str(logo_path_obj))

        # Calculate logo position based on corner
        logo_width, logo_height = logo_clip.size
        padding = 20  # pixels from edge

        position_map = {
            "top-left": (padding, padding),
            "top-right": (video_width - logo_width - padding, padding),
            "bottom-left": (padding, video_height - logo_height - padding),
            "bottom-right": (
                video_width - logo_width - padding,
                video_height - logo_height - padding,
            ),
        }

        logo_position_coords = position_map.get(
            logo_position, position_map["top-right"]
        )
        logo_clip = logo_clip.with_duration(clip_duration).with_position(
            logo_position_coords
        )
        final_clips.append(logo_clip)

        logger.info(
            f"Added logo overlay at {logo_position} with coords: {logo_position_coords}"
        )
        logger.info(
            f"Logo size: {logo_width}x{logo_height}, Video size: {video_width}x{video_height}"
        )

    except Exception as e:
        logger.warning(f"Failed to add logo overlay: {e}")


def create_optimized_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    add_subtitles: bool = True,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: Optional[str] = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: Optional[Dict[str, Any]] = None,
    subtitle_position: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Create optimized 9:16 clip with AssemblyAI subtitles.

    Args:
        output_resolution: Target resolution ("480p", "720p", or "1080p")
    """
    # Initialize resources for cleanup in finally block
    video = None
    clip = None
    cropped_clip = None
    final_clip = None

    try:
        duration = end_time - start_time
        if duration <= 0:
            logger.error(f"Invalid clip duration: {duration:.1f}s")
            return False

        logger.info(
            f"Creating clip: {start_time:.1f}s - {end_time:.1f}s ({duration:.1f}s)"
        )

        # Load and process video
        video = VideoFileClip(str(video_path))
        logger.info(f"[SYNC_DIAG] Video: duration={video.duration:.2f}s, fps={video.fps}")

        if start_time >= video.duration:
            logger.error(
                f"Start time {start_time}s exceeds video duration {video.duration:.1f}s"
            )
            return False  # finally block will cleanup video

        # Preserve original times for subtitle alignment
        original_start_time: float = start_time
        original_end_time: float = end_time

        # Add audio buffer to prevent cutting off words at clip boundaries
        start_time = max(0, start_time - AUDIO_BUFFER_SECONDS)
        end_time = min(video.duration, end_time + AUDIO_BUFFER_SECONDS)

        clip = video.subclipped(start_time, end_time)

        # Get optimal crop
        x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
            video, start_time, end_time, target_ratio=9 / 16
        )

        cropped_clip = clip.cropped(
            x1=x_offset, y1=y_offset, x2=x_offset + new_width, y2=y_offset + new_height
        )

        # Scale to target resolution
        target_width, target_height = RESOLUTION_PRESETS.get(
            output_resolution, RESOLUTION_PRESETS["720p"]
        )

        if (new_width, new_height) != (target_width, target_height):
            logger.info(
                f"Scaling from {new_width}x{new_height} to {target_width}x{target_height} ({output_resolution})"
            )
            cropped_clip = cropped_clip.resized(new_size=(target_width, target_height))
            # Update dimensions for subtitle/logo positioning
            new_width, new_height = target_width, target_height
        else:
            logger.info(
                f"Using native resolution {new_width}x{new_height} (matches {output_resolution})"
            )

        # Add AssemblyAI subtitles
        final_clips = [cropped_clip]

        if add_subtitles:
            subtitle_clips = create_assemblyai_subtitles(
                video_path,
                original_start_time,
                original_end_time,
                new_width,
                new_height,
                font_family,
                font_size,
                font_color,
                subtitle_style,
                subtitle_position,
            )
            # Offset subtitles by buffer amount (video starts earlier than segment)
            adjusted_subtitle_clips = [
                clip.with_start(clip.start + AUDIO_BUFFER_SECONDS)
                for clip in subtitle_clips
            ]
            final_clips.extend(adjusted_subtitle_clips)

        # Add logo overlay if provided
        _add_logo_overlay(
            final_clips,
            logo_path,
            logo_position,
            new_width,
            new_height,
            cropped_clip.duration,
        )

        # Compose and encode
        final_clip = (
            CompositeVideoClip(final_clips) if len(final_clips) > 1 else cropped_clip
        )

        processor = VideoProcessor(font_family, font_size, font_color)
        encoding_settings = processor.get_optimal_encoding_settings("high")

        final_clip.write_videofile(
            str(output_path),
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None,
            **encoding_settings,
        )

        logger.info(f"Successfully created clip: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create clip: {e}")
        return False

    finally:
        # Always cleanup resources, even on exception
        for resource in (final_clip, cropped_clip, clip, video):
            if resource is not None:
                with suppress(Exception):
                    resource.close()


def create_clips_from_segments(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: Optional[str] = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: Optional[Dict[str, Any]] = None,
    subtitle_position: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Create optimized video clips from segments."""
    logger.info(f"Creating {len(segments)} clips")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_info = []

    for i, segment in enumerate(segments):
        try:
            logger.info(f"[CLIP_DIAG] Starting clip {i + 1}/{len(segments)}")
            # Debug log the segment data
            logger.info(
                f"Processing segment {i + 1}: start='{segment.get('start_time')}', end='{segment.get('end_time')}'"
            )

            start_seconds = parse_timestamp_to_seconds(segment["start_time"])
            end_seconds = parse_timestamp_to_seconds(segment["end_time"])

            # Note: Snapping done upstream in video_service_async._apply_verbatim_text_to_segment()

            duration = end_seconds - start_seconds
            logger.info(
                f"Segment {i + 1} duration: {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
            )

            if duration <= 0:
                logger.warning(
                    f"Skipping clip {i + 1}: invalid duration {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
                )
                continue

            clip_filename = f"clip_{i + 1}_{segment['start_time'].replace(':', '')}-{segment['end_time'].replace(':', '')}.mp4"
            clip_path = output_dir / clip_filename

            success = create_optimized_clip(
                video_path,
                start_seconds,
                end_seconds,
                clip_path,
                True,
                font_family,
                font_size,
                font_color,
                logo_path,
                logo_position,
                output_resolution,
                subtitle_style,
                subtitle_position,
            )

            if success:
                logger.info(f"[CLIP_DIAG] Clip {i + 1} created successfully: {clip_path}")
                clip_info = {
                    "clip_id": i + 1,
                    "filename": clip_filename,
                    "path": str(clip_path),
                    "start_time": segment["start_time"],
                    "end_time": segment["end_time"],
                    "duration": duration,
                    "text": segment["text"],
                    "relevance_score": segment["relevance_score"],
                    "reasoning": segment["reasoning"],
                }
                clips_info.append(clip_info)
                logger.info(f"Created clip {i + 1}: {duration:.1f}s")
            else:
                logger.error(f"[CLIP_DIAG] Clip {i + 1} FAILED - check resource cleanup")
                logger.error(f"Failed to create clip {i + 1}")

        except Exception as e:
            logger.error(f"[CLIP_DIAG] Clip {i + 1} exception: {e}")
            logger.error(f"Error processing clip {i + 1}: {e}")

        logger.info(f"[CLIP_DIAG] Completed iteration {i + 1}, proceeding to next")

    logger.info(f"Successfully created {len(clips_info)}/{len(segments)} clips")
    return clips_info


def get_available_transitions() -> List[str]:
    """Get list of available transition video files."""
    transitions_dir = Path(__file__).parent.parent / "transitions"
    if not transitions_dir.exists():
        logger.warning("Transitions directory not found")
        return []

    transition_files = [str(file_path) for file_path in transitions_dir.glob("*.mp4")]

    logger.info(f"Found {len(transition_files)} transition files")
    return transition_files


def apply_transition_effect(
    clip1_path: Path, clip2_path: Path, transition_path: Path, output_path: Path
) -> bool:
    """Apply transition effect between two clips using a transition video."""
    try:
        from moviepy import VideoFileClip, concatenate_videoclips

        # Load clips
        clip1 = VideoFileClip(str(clip1_path))
        clip2 = VideoFileClip(str(clip2_path))
        transition = VideoFileClip(str(transition_path))

        # Ensure transition duration is reasonable (max 1.5 seconds)
        transition_duration = min(1.5, transition.duration)
        transition = transition.subclipped(0, transition_duration)

        # Resize transition to match clip dimensions
        clip_size = clip1.size
        transition = transition.resized(new_size=clip_size)

        # Create fade effect with transition
        fade_duration = 0.5  # Half second fade

        # Fade out clip1
        clip1_faded = clip1.with_effects([FadeOut(duration=fade_duration)])

        # Fade in clip2
        clip2_faded = clip2.with_effects([FadeIn(duration=fade_duration)])

        # Combine: clip1 -> transition -> clip2
        final_clip = concatenate_videoclips(
            [clip1_faded, transition, clip2_faded], method="compose"
        )

        # Write output
        processor = VideoProcessor()
        encoding_settings = processor.get_optimal_encoding_settings("high")

        final_clip.write_videofile(
            str(output_path),
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None,
            **encoding_settings,
        )

        # Cleanup
        final_clip.close()
        clip1.close()
        clip2.close()
        transition.close()

        logger.info(f"Applied transition effect: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error applying transition effect: {e}")
        return False


def create_clips_with_transitions(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: Optional[str] = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: Optional[Dict[str, Any]] = None,
    subtitle_position: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Create video clips with transition effects between them."""
    logger.info(
        f"Creating {len(segments)} clips with transitions at {output_resolution}"
    )

    # First create individual clips
    clips_info = create_clips_from_segments(
        video_path,
        segments,
        output_dir,
        font_family,
        font_size,
        font_color,
        logo_path,
        logo_position,
        output_resolution,
        subtitle_style,
        subtitle_position,
    )

    if len(clips_info) < 2:
        logger.info("Not enough clips to apply transitions")
        return clips_info

    # Get available transitions
    transitions = get_available_transitions()
    if not transitions:
        logger.warning("No transition files found, returning clips without transitions")
        return clips_info

    # Create clips with transitions
    transition_output_dir = output_dir / "with_transitions"
    transition_output_dir.mkdir(parents=True, exist_ok=True)

    enhanced_clips = []

    for i, clip_info in enumerate(clips_info):
        if i == 0:
            # First clip - no transition before
            enhanced_clips.append(clip_info)
        else:
            # Apply transition before this clip
            prev_clip_path = Path(clips_info[i - 1]["path"])
            current_clip_path = Path(clip_info["path"])

            # Select transition (cycle through available transitions)
            transition_path = Path(transitions[i % len(transitions)])

            # Create output path for clip with transition
            transition_filename = f"transition_{i}_{clip_info['filename']}"
            transition_output_path = transition_output_dir / transition_filename

            success = apply_transition_effect(
                prev_clip_path,
                current_clip_path,
                transition_path,
                transition_output_path,
            )

            if success:
                # Update clip info with transition version
                enhanced_clip_info = clip_info.copy()
                enhanced_clip_info["filename"] = transition_filename
                enhanced_clip_info["path"] = str(transition_output_path)
                enhanced_clip_info["has_transition"] = True
                enhanced_clips.append(enhanced_clip_info)
                logger.info(f"Added transition to clip {i + 1}")
            else:
                # Fallback to original clip if transition fails
                enhanced_clips.append(clip_info)
                logger.warning(
                    f"Failed to add transition to clip {i + 1}, using original"
                )

    logger.info(f"Successfully created {len(enhanced_clips)} clips with transitions")
    return enhanced_clips


# Backward compatibility functions
def get_video_transcript_with_assemblyai(path: Path) -> str:
    """
    Backward compatibility wrapper for old API.

    Uses parakeet-mlx instead of AssemblyAI.
    """
    return get_video_transcript(path)


def create_9_16_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    subtitle_text: str = "",
) -> bool:
    """Backward compatibility wrapper."""
    return create_optimized_clip(
        video_path, start_time, end_time, output_path, add_subtitles=bool(subtitle_text)
    )
