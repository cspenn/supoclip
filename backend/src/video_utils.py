"""
Utility functions for video-related operations.
Optimized for MoviePy v2, AssemblyAI integration, and high-quality output.
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import logging
import numpy as np
import json

import cv2
from moviepy import VideoFileClip, CompositeVideoClip, TextClip  # type: ignore


from .config import Config
from .transcription_mlx import (
    transcribe_video_mlx,
)

logger = logging.getLogger(__name__)
config = Config()


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
        self.font_path = str(
            Path(__file__).parent.parent / "fonts" / f"{font_family}.ttf"
        )
        # Fallback to default font if custom font doesn't exist
        if not Path(self.font_path).exists():
            self.font_path = str(
                Path(__file__).parent.parent / "fonts" / "THEBOLDFONT-FREEVERSION.ttf"
            )

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

    with open(cache_path, "w") as f:
        json.dump(cache_data, f)

    logger.info(f"Cached {len(words_data)} words to {cache_path}")


def load_cached_transcript_data(video_path: Path) -> Optional[Dict]:
    """Load cached AssemblyAI transcript data."""
    cache_path = video_path.with_suffix(".transcript_cache.json")

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load transcript cache: {e}")
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

    MAX_WORDS_PER_LINE = 6
    BREAK_PUNCTUATION = {".", "!", "?", ","}

    @staticmethod
    def should_break_line(word_text: str, word_count: int) -> bool:
        """Determine if line should break at this word.

        Args:
            word_text: Text of current word
            word_count: Number of words in current line

        Returns:
            True if line should break, False otherwise
        """
        if word_count >= TranscriptLineBreaker.MAX_WORDS_PER_LINE:
            return True
        if word_text and any(
            word_text.endswith(punct)
            for punct in TranscriptLineBreaker.BREAK_PUNCTUATION
        ):
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
                (float(x), float(y), float(w), float(h)) for x, y, w, h in face_centers
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
            import os

            prototxt = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector.pbtxt"
            )
            model = cv2.data.haarcascades.replace(
                "haarcascades", "opencv_face_detector_uint8.pb"
            )

            if os.path.exists(prototxt) and os.path.exists(model):
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
        return (
            filtered_faces if filtered_faces else face_centers
        )  # Return original if all filtered

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

            if word_start < clip_end_ms and word_end > clip_start_ms:
                relative_start = max(0, (word_start - clip_start_ms) / 1000.0)
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
        return relevant_words


class SubtitleTextClipCreator:
    """Create text clips with automatic font size adjustment."""

    MAX_SUBTITLE_LINES = 2
    HORIZONTAL_PADDING = 0.1
    MIN_FONT_SIZE = 16
    FONT_SIZE_REDUCTION = 0.85

    @staticmethod
    def create_text_clip(
        text: str,
        font_path: str,
        font_size: int,
        font_color: str,
        video_width: int,
    ) -> Optional[TextClip]:
        """Create text clip with automatic size adjustment to fit lines."""
        max_text_width = int(
            video_width * (1 - 2 * SubtitleTextClipCreator.HORIZONTAL_PADDING)
        )
        current_font_size = font_size
        max_attempts = 3

        for attempt in range(max_attempts):
            text_clip = TextClip(
                text=text,
                font=font_path,
                font_size=current_font_size,
                color=font_color,
                stroke_color="black",
                stroke_width=1,
                method="caption",
                size=(max_text_width, None),
                text_align="center",
            )

            text_height = text_clip.size[1] if text_clip.size else 40
            estimated_line_height = current_font_size * 1.5
            estimated_lines = text_height / estimated_line_height

            if estimated_lines <= SubtitleTextClipCreator.MAX_SUBTITLE_LINES:
                return text_clip

            current_font_size = int(
                current_font_size * SubtitleTextClipCreator.FONT_SIZE_REDUCTION
            )
            if current_font_size < SubtitleTextClipCreator.MIN_FONT_SIZE:
                current_font_size = SubtitleTextClipCreator.MIN_FONT_SIZE
                break

        return text_clip


class SubtitlePositioner:
    """Calculate subtitle positioning on video."""

    @staticmethod
    def calculate_position(video_height: int, text_height: int) -> Tuple[str, int]:
        """Calculate subtitle position (lower middle of video)."""
        vertical_position = int(video_height * 0.75 - text_height // 2)
        return ("center", vertical_position)


class SubtitleClipBuilder:
    """Build subtitle clips from word groups."""

    @staticmethod
    def build_clips(
        relevant_words: List[Dict[str, Any]],
        font_path: str,
        font_size: int,
        font_color: str,
        video_width: int,
        video_height: int,
        words_per_subtitle: int = 3,
    ) -> List[TextClip]:
        """Build subtitle clips from grouped words."""
        subtitle_clips = []
        for i in range(0, len(relevant_words), words_per_subtitle):
            word_group = relevant_words[i : i + words_per_subtitle]
            if not word_group:
                continue

            segment_start = word_group[0]["start"]
            segment_end = word_group[-1]["end"]
            segment_duration = segment_end - segment_start

            if segment_duration < 0.1:
                continue

            text = " ".join(word["text"] for word in word_group)

            try:
                text_clip = SubtitleTextClipCreator.create_text_clip(
                    text, font_path, font_size, font_color, video_width
                )

                if text_clip:
                    text_clip = text_clip.with_duration(segment_duration).with_start(
                        segment_start
                    )
                    text_height = text_clip.size[1] if text_clip.size else 40
                    position = SubtitlePositioner.calculate_position(
                        video_height, text_height
                    )
                    text_clip = text_clip.with_position(position)
                    subtitle_clips.append(text_clip)

            except Exception as e:
                logger.warning(f"Failed to create subtitle for '{text}': {e}")
                continue

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
) -> List[TextClip]:
    """
    Create subtitles using parakeet-mlx's precise word timing.

    Legacy function name kept for backward compatibility.
    Uses cached transcript data from parakeet-mlx transcription.
    """
    transcript_data = load_cached_transcript_data(video_path)

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
    )

    logger.info(f"Created {len(subtitle_clips)} subtitle elements from AssemblyAI data")
    return subtitle_clips


def create_optimized_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    add_subtitles: bool = True,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: Optional[Path] = None,
    logo_position: str = "top-right",
) -> bool:
    """Create optimized 9:16 clip with AssemblyAI subtitles."""
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

        if start_time >= video.duration:
            logger.error(
                f"Start time {start_time}s exceeds video duration {video.duration:.1f}s"
            )
            video.close()
            return False

        end_time = min(end_time, video.duration)
        clip = video.subclipped(start_time, end_time)

        # Get optimal crop
        x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
            video, start_time, end_time, target_ratio=9 / 16
        )

        cropped_clip = clip.cropped(
            x1=x_offset, y1=y_offset, x2=x_offset + new_width, y2=y_offset + new_height
        )

        # Add AssemblyAI subtitles
        final_clips = [cropped_clip]

        if add_subtitles:
            subtitle_clips = create_assemblyai_subtitles(
                video_path,
                start_time,
                end_time,
                new_width,
                new_height,
                font_family,
                font_size,
                font_color,
            )
            final_clips.extend(subtitle_clips)

        # Add logo overlay if provided
        if logo_path and logo_path.exists():
            try:
                from moviepy import ImageClip

                logo_clip = ImageClip(str(logo_path))

                # Calculate logo position based on corner
                logo_width, logo_height = logo_clip.size
                padding = 20  # pixels from edge

                position_map = {
                    "top-left": (padding, padding),
                    "top-right": (new_width - logo_width - padding, padding),
                    "bottom-left": (padding, new_height - logo_height - padding),
                    "bottom-right": (
                        new_width - logo_width - padding,
                        new_height - logo_height - padding,
                    ),
                }

                logo_position_coords = position_map.get(
                    logo_position, position_map["top-right"]
                )

                logo_clip = logo_clip.with_duration(
                    cropped_clip.duration
                ).with_position(logo_position_coords)

                final_clips.append(logo_clip)

                logger.info(f"Added logo overlay at {logo_position}")

            except Exception as e:
                logger.warning(f"Failed to add logo overlay: {e}")

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

        # Cleanup
        final_clip.close()
        clip.close()
        video.close()

        logger.info(f"Successfully created clip: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create clip: {e}")
        return False


def create_clips_from_segments(
    video_path: Path,
    segments: List[Dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: Optional[Path] = None,
    logo_position: str = "top-right",
) -> List[Dict[str, Any]]:
    """Create optimized video clips from segments."""
    logger.info(f"Creating {len(segments)} clips")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_info = []

    for i, segment in enumerate(segments):
        try:
            # Debug log the segment data
            logger.info(
                f"Processing segment {i+1}: start='{segment.get('start_time')}', end='{segment.get('end_time')}'"
            )

            start_seconds = parse_timestamp_to_seconds(segment["start_time"])
            end_seconds = parse_timestamp_to_seconds(segment["end_time"])

            duration = end_seconds - start_seconds
            logger.info(
                f"Segment {i+1} duration: {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
            )

            if duration <= 0:
                logger.warning(
                    f"Skipping clip {i+1}: invalid duration {duration:.1f}s (start: {start_seconds}s, end: {end_seconds}s)"
                )
                continue

            clip_filename = f"clip_{i+1}_{segment['start_time'].replace(':', '')}-{segment['end_time'].replace(':', '')}.mp4"
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
            )

            if success:
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
                logger.info(f"Created clip {i+1}: {duration:.1f}s")
            else:
                logger.error(f"Failed to create clip {i+1}")

        except Exception as e:
            logger.error(f"Error processing clip {i+1}: {e}")

    logger.info(f"Successfully created {len(clips_info)}/{len(segments)} clips")
    return clips_info


def get_available_transitions() -> List[str]:
    """Get list of available transition video files."""
    transitions_dir = Path(__file__).parent.parent / "transitions"
    if not transitions_dir.exists():
        logger.warning("Transitions directory not found")
        return []

    transition_files = []
    for file_path in transitions_dir.glob("*.mp4"):
        transition_files.append(str(file_path))

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
        transition = transition.resized(clip_size)

        # Create fade effect with transition
        fade_duration = 0.5  # Half second fade

        # Fade out clip1
        clip1_faded = clip1.with_effects(["fadeout", fade_duration])

        # Fade in clip2
        clip2_faded = clip2.with_effects(["fadein", fade_duration])

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
    logo_path: Optional[Path] = None,
    logo_position: str = "top-right",
) -> List[Dict[str, Any]]:
    """Create video clips with transition effects between them."""
    logger.info(f"Creating {len(segments)} clips with transitions")

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
                logger.info(f"Added transition to clip {i+1}")
            else:
                # Fallback to original clip if transition fails
                enhanced_clips.append(clip_info)
                logger.warning(
                    f"Failed to add transition to clip {i+1}, using original"
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
