# start backend/src/subtitles.py
"""
Subtitle creation: word filtering, text clip rendering, positioning,
and TikTok-style word-by-word subtitle assembly.
"""

from pathlib import Path
from typing import Any
import logging

from moviepy import ImageClip
from moviepy.video.fx import Margin

from .config import Config
from .subtitle_renderer import BrowserSubtitleRenderer
from .transcript import load_cached_transcript_data

logger = logging.getLogger(__name__)
config = Config()


class SubtitleWordFilter:
    """Filter and prepare words for subtitle creation."""

    @staticmethod
    def get_relevant_words(
        transcript_data: dict[str, Any], clip_start_ms: int, clip_end_ms: int
    ) -> list[dict[str, Any]]:
        """Extract words that fall within clip timerange.

        Args:
            transcript_data: Cached transcript data with 'words' list
            clip_start_ms: Clip start time in milliseconds
            clip_end_ms: Clip end time in milliseconds

        Returns:
            List of word dictionaries with relative timing
        """
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
            first_words = [
                (w["text"], round(w["start"], 2)) for w in relevant_words[:3]
            ]
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
        style_options: dict[str, Any] | None = None,
    ) -> ImageClip | None:
        """Create a subtitle clip using BrowserSubtitleRenderer.

        Renders the text to a PNG using Playwright and loads it as an ImageClip.

        Args:
            text: Subtitle text to render
            font_path: Path to font file
            font_size: Font size in pixels
            font_color: Font color (hex or name)
            max_text_width: Maximum text width in pixels
            style_options: Additional style options (stroke, shadow, etc.)

        Returns:
            ImageClip with rendered text, or None on failure
        """
        style_options = style_options or {}

        try:
            with BrowserSubtitleRenderer() as renderer:
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
                    img_clip = ImageClip(str(image_path))
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
        style_options: dict[str, Any] | None = None,
    ) -> ImageClip | None:
        """Create text clip with automatic size adjustment to fit lines.

        Tries up to 3 times with decreasing font sizes to fit within
        MAX_SUBTITLE_LINES.

        Args:
            text: Subtitle text to render
            font_path: Path to font file
            font_size: Font size in pixels
            font_color: Font color (hex or name)
            video_width: Video width for text wrapping
            style_options: Additional style options

        Returns:
            ImageClip with rendered text, or None on failure
        """
        max_text_width = int(
            video_width * (1 - 2 * SubtitleTextClipCreator.HORIZONTAL_PADDING)
        )
        current_font_size = font_size
        max_attempts = 3

        for attempt in range(max_attempts):
            text_clip = SubtitleTextClipCreator._create_clip_candidate(
                text,
                font_path,
                current_font_size,
                font_color,
                max_text_width,
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
                if attempt == max_attempts - 1:
                    return text_clip  # Return what we have at min font size

        return None


class SubtitlePositioner:
    """Calculate subtitle positioning on video."""

    @staticmethod
    def calculate_position(
        video_height: int,
        text_height: int,
        video_width: int = 0,
        position_options: dict[str, Any] | None = None,
    ) -> tuple[str | int, int]:
        """Calculate subtitle position based on provided options or defaults.

        Args:
            video_height: Height of video
            text_height: Height of subtitle clip
            video_width: Width of video
            position_options: dict with 'x', 'y' (float 0-1) and 'alignment'

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
        vertical_position = int(video_height * y_rel - text_height // 2)

        # Calculate X position
        if alignment == "center" and position_options is None:
            return ("center", vertical_position)

        horizontal_position: str | int = "center"
        if position_options and "x" in position_options:
            if x_rel == 0.5 and alignment == "center":
                horizontal_position = "center"
            else:
                horizontal_position = int(video_width * x_rel)

        return (horizontal_position, vertical_position)


class SubtitleClipBuilder:
    """Build subtitle clips with word-by-word synchronization (TikTok-style)."""

    @staticmethod
    def build_clips(
        relevant_words: list[dict[str, Any]],
        font_path: str,
        font_size: int,
        font_color: str,
        video_width: int,
        video_height: int,
        style_options: dict[str, Any] | None = None,
        position_options: dict[str, Any] | None = None,
    ) -> list[ImageClip]:
        """Build individual subtitle clips for each word with exact timing.

        Creates TikTok/YouTube Shorts-style captions where each word appears
        exactly when spoken, ensuring perfect audio-caption synchronization.

        Args:
            relevant_words: List of word dicts with 'text', 'start', 'end' keys
            font_path: Path to font file
            font_size: Font size in pixels
            font_color: Font color (hex or name)
            video_width: Video width for text wrapping
            video_height: Video height for positioning
            style_options: Additional style options
            position_options: Subtitle position configuration

        Returns:
            List of ImageClip objects with precise timing
        """
        subtitle_clips = []

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
                text_clip = SubtitleTextClipCreator.create_text_clip(
                    text, font_path, font_size, font_color, video_width, style_options
                )

                if text_clip:
                    text_clip = text_clip.with_duration(word_duration).with_start(
                        word_start
                    )

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


class VideoProcessor:
    """Handles video processing operations with optimized settings."""

    def __init__(
        self,
        font_family: str = "THEBOLDFONT-FREEVERSION",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ):
        from .video_utils import resolve_font_path

        self.font_family = font_family
        self.font_size = font_size
        self.font_color = font_color
        self.font_path = resolve_font_path(font_family)

    def get_optimal_encoding_settings(
        self, target_quality: str = "high"
    ) -> dict[str, Any]:
        """Get optimal encoding settings for different quality levels.

        Args:
            target_quality: Quality preset ("high" or "medium")

        Returns:
            Dictionary of ffmpeg encoding settings
        """
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


def create_subtitles(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    video_width: int,
    video_height: int,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    subtitle_style: dict[str, Any] | None = None,
    subtitle_position: dict[str, Any] | None = None,
) -> list[ImageClip]:
    """Create subtitles using parakeet-mlx's precise word timing.

    Uses cached transcript data from parakeet-mlx transcription to create
    word-by-word synchronized subtitle clips.

    Args:
        video_path: Path to the video file
        clip_start: Clip start time in seconds
        clip_end: Clip end time in seconds
        video_width: Video width in pixels
        video_height: Video height in pixels
        font_family: Font family name
        font_size: Base font size in pixels
        font_color: Font color (hex or name)
        subtitle_style: Style options (stroke, shadow, etc.)
        subtitle_position: Position options (x, y, alignment)

    Returns:
        List of ImageClip subtitle elements
    """
    transcript_data = load_cached_transcript_data(video_path)
    if transcript_data:
        words = transcript_data.get("words", [])
        logger.info(
            f"[SYNC_DIAG] Cache: {len(words)} words, clip_range={clip_start:.2f}-{clip_end:.2f}s"
        )

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
        subtitle_style,
        subtitle_position,
    )

    logger.info(f"Created {len(subtitle_clips)} subtitle elements from transcript data")
    return subtitle_clips


# end backend/src/subtitles.py
