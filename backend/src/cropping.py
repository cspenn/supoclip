# start backend/src/cropping.py
"""
Video cropping: dimension calculation, face-centered and center crop positioning.
"""

import logging

from moviepy import VideoFileClip

from .face_detection import detect_faces_in_clip

logger = logging.getLogger(__name__)


def round_to_even(value: int) -> int:
    """Round integer to nearest even number for H.264 compatibility.

    Args:
        value: Integer to round

    Returns:
        Nearest even integer
    """
    return value - (value % 2)


class TargetDimensionCalculator:
    """Calculate target dimensions for video cropping."""

    @staticmethod
    def calculate(
        original_width: int, original_height: int, target_ratio: float
    ) -> tuple[int, int]:
        """Calculate target width and height maintaining aspect ratio.

        Args:
            original_width: Original video width
            original_height: Original video height
            target_ratio: Target width/height ratio (e.g. 9/16)

        Returns:
            Tuple of (new_width, new_height) rounded to even numbers
        """
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
        face_centers: list[tuple[float, float, float, float]],
        new_width: int,
        new_height: int,
        original_width: int,
        original_height: int,
    ) -> tuple[int, int]:
        """Calculate face-centered crop offsets.

        Uses weighted average of face positions (weighted by area * confidence)
        with slight upward bias for better face framing.

        Args:
            face_centers: List of (x, y, area, confidence) tuples
            new_width: Target crop width
            new_height: Target crop height
            original_width: Original video width
            original_height: Original video height

        Returns:
            Tuple of (x_offset, y_offset) for cropping
        """
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
    ) -> tuple[int, int]:
        """Calculate center crop offsets.

        Args:
            new_width: Target crop width
            new_height: Target crop height
            original_width: Original video width
            original_height: Original video height

        Returns:
            Tuple of (x_offset, y_offset) for cropping
        """
        x_offset = (
            (original_width - new_width) // 2 if original_width > new_width else 0
        )
        y_offset = (
            (original_height - new_height) // 2 if original_height > new_height else 0
        )
        return round_to_even(x_offset), round_to_even(y_offset)


def detect_optimal_crop_region(
    video_clip: VideoFileClip,
    start_time: float,
    end_time: float,
    target_ratio: float = 9 / 16,
) -> tuple[int, int, int, int]:
    """Detect optimal crop region using face detection with center-crop fallback.

    Args:
        video_clip: MoviePy VideoFileClip object
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds
        target_ratio: Target width/height ratio (default 9:16)

    Returns:
        Tuple of (x_offset, y_offset, width, height) for cropping
    """
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


# end backend/src/cropping.py
