# start backend/src/clip_assembly.py
"""
Clip assembly: creating optimized 9:16 clips with subtitles, logos,
and transition effects.
"""

from contextlib import suppress
from pathlib import Path
from typing import Any
import logging

from moviepy import (
    VideoFileClip,
    CompositeVideoClip,
    ImageClip,
)
from moviepy.video.fx import FadeIn, FadeOut

from .cropping import detect_optimal_crop_region
from .subtitles import create_subtitles, VideoProcessor
from .transcript import parse_timestamp_to_seconds

logger = logging.getLogger(__name__)

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


def _add_logo_overlay(
    final_clips: list,
    logo_path: str | None,
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


def _validate_clip_timing(
    start_time: float, end_time: float, video_duration: float
) -> str | None:
    """Validate clip timing parameters.

    Args:
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds
        video_duration: Total video duration in seconds

    Returns:
        Error message string if invalid, None if valid
    """
    duration = end_time - start_time
    if duration <= 0:
        return f"Invalid clip duration: {duration:.1f}s"
    if start_time >= video_duration:
        return f"Start time {start_time}s exceeds video duration {video_duration:.1f}s"
    return None


def _prepare_cropped_clip(
    video: VideoFileClip,
    start_time: float,
    end_time: float,
    output_resolution: str,
) -> tuple[Any, int, int, float, float]:
    """Load video, apply audio buffer, crop to 9:16, and scale to target resolution.

    Args:
        video: Loaded VideoFileClip
        start_time: Original clip start time in seconds
        end_time: Original clip end time in seconds
        output_resolution: Target resolution preset ("480p", "720p", "1080p")

    Returns:
        Tuple of (cropped_clip, width, height, buffered_start, buffered_end)
    """
    # Add audio buffer to prevent cutting off words at clip boundaries
    buffered_start = max(0, start_time - AUDIO_BUFFER_SECONDS)
    buffered_end = min(video.duration, end_time + AUDIO_BUFFER_SECONDS)

    clip = video.subclipped(buffered_start, buffered_end)

    # Get optimal crop region
    x_offset, y_offset, new_width, new_height = detect_optimal_crop_region(
        video, buffered_start, buffered_end, target_ratio=9 / 16
    )

    cropped = clip.cropped(
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
        cropped = cropped.resized(new_size=(target_width, target_height))
        new_width, new_height = target_width, target_height
    else:
        logger.info(
            f"Using native resolution {new_width}x{new_height} (matches {output_resolution})"
        )

    return cropped, new_width, new_height, buffered_start, buffered_end


def _build_subtitle_overlays(
    video_path: Path,
    original_start: float,
    original_end: float,
    width: int,
    height: int,
    font_family: str,
    font_size: int,
    font_color: str,
    subtitle_style: dict[str, Any] | None,
    subtitle_position: dict[str, Any] | None,
) -> list:
    """Create subtitle clips with audio buffer offset applied.

    Args:
        video_path: Path to video file for transcript cache lookup
        original_start: Original (unbuffered) start time in seconds
        original_end: Original (unbuffered) end time in seconds
        width: Video width for subtitle sizing
        height: Video height for subtitle positioning
        font_family: Font family name
        font_size: Font size in pixels
        font_color: Font color
        subtitle_style: Style options
        subtitle_position: Position options

    Returns:
        List of subtitle ImageClip objects with timing adjusted for audio buffer
    """
    subtitle_clips = create_subtitles(
        video_path,
        original_start,
        original_end,
        width,
        height,
        font_family,
        font_size,
        font_color,
        subtitle_style,
        subtitle_position,
    )
    # Offset subtitles by buffer amount (video starts earlier than segment)
    return [
        clip.with_start(clip.start + AUDIO_BUFFER_SECONDS) for clip in subtitle_clips
    ]


def _compose_and_encode(
    final_clips: list,
    cropped_clip: Any,
    output_path: Path,
    font_family: str,
    font_size: int,
    font_color: str,
) -> None:
    """Composite clips and encode to output file.

    Args:
        final_clips: List of all clips (base + overlays)
        cropped_clip: Base cropped video clip
        output_path: Output file path
        font_family: Font family for VideoProcessor
        font_size: Font size for VideoProcessor
        font_color: Font color for VideoProcessor
    """
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


def create_optimized_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    add_subtitles: bool = True,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: str | None = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: dict[str, Any] | None = None,
    subtitle_position: dict[str, Any] | None = None,
) -> bool:
    """Create optimized 9:16 clip with face-centered cropping and subtitles.

    Pipeline: load video -> validate timing -> crop to 9:16 -> scale ->
    add subtitles -> add logo -> composite -> encode.

    Args:
        video_path: Path to source video file
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds
        output_path: Path for output clip file
        add_subtitles: Whether to add word-by-word subtitles
        font_family: Font family name for subtitles
        font_size: Font size in pixels
        font_color: Font color (hex or name)
        logo_path: Optional path to logo overlay image
        logo_position: Logo corner position
        output_resolution: Target resolution preset
        subtitle_style: Subtitle style options
        subtitle_position: Subtitle position options

    Returns:
        True if clip was created successfully, False otherwise
    """
    video = None
    cropped_clip = None
    final_clips: list = []

    try:
        logger.info(
            f"Creating clip: {start_time:.1f}s - {end_time:.1f}s "
            f"({end_time - start_time:.1f}s)"
        )

        video = VideoFileClip(str(video_path))
        logger.info(
            f"[SYNC_DIAG] Video: duration={video.duration:.2f}s, fps={video.fps}"
        )

        # Validate timing
        error = _validate_clip_timing(start_time, end_time, video.duration)
        if error:
            logger.error(error)
            return False

        # Crop and scale
        cropped_clip, width, height, _, _ = _prepare_cropped_clip(
            video, start_time, end_time, output_resolution
        )

        final_clips = [cropped_clip]

        # Add subtitles
        if add_subtitles:
            subtitle_overlays = _build_subtitle_overlays(
                video_path,
                start_time,
                end_time,
                width,
                height,
                font_family,
                font_size,
                font_color,
                subtitle_style,
                subtitle_position,
            )
            final_clips.extend(subtitle_overlays)

        # Add logo
        _add_logo_overlay(
            final_clips,
            logo_path,
            logo_position,
            width,
            height,
            cropped_clip.duration,
        )

        # Compose and encode
        _compose_and_encode(
            final_clips,
            cropped_clip,
            output_path,
            font_family,
            font_size,
            font_color,
        )

        logger.info(f"Successfully created clip: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create clip: {e}")
        return False

    finally:
        # Close subtitle and logo clips (skip base cropped_clip at index 0)
        if final_clips:
            for overlay_clip in final_clips[1:]:
                if overlay_clip is not None:
                    with suppress(Exception):
                        overlay_clip.close()

        # Close main video clips
        for resource in (cropped_clip, video):
            if resource is not None:
                with suppress(Exception):
                    resource.close()


def create_clips_from_segments(
    video_path: Path,
    segments: list[dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: str | None = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: dict[str, Any] | None = None,
    subtitle_position: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create optimized video clips from AI-selected segments.

    Args:
        video_path: Path to source video file
        segments: List of segment dicts with start_time, end_time, text, etc.
        output_dir: Directory for output clip files
        font_family: Font family name for subtitles
        font_size: Font size in pixels
        font_color: Font color (hex or name)
        logo_path: Optional path to logo overlay image
        logo_position: Logo corner position
        output_resolution: Target resolution preset
        subtitle_style: Subtitle style options
        subtitle_position: Subtitle position options

    Returns:
        List of clip info dicts for successfully created clips
    """
    logger.info(f"Creating {len(segments)} clips")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_info = []

    for i, segment in enumerate(segments):
        try:
            logger.info(f"[CLIP_DIAG] Starting clip {i + 1}/{len(segments)}")
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
                logger.info(
                    f"[CLIP_DIAG] Clip {i + 1} created successfully: {clip_path}"
                )
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
                logger.error(
                    f"[CLIP_DIAG] Clip {i + 1} FAILED - check resource cleanup"
                )
                logger.error(f"Failed to create clip {i + 1}")

        except Exception as e:
            logger.error(f"[CLIP_DIAG] Clip {i + 1} exception: {e}")
            logger.error(f"Error processing clip {i + 1}: {e}")

        logger.info(f"[CLIP_DIAG] Completed iteration {i + 1}, proceeding to next")

    logger.info(f"Successfully created {len(clips_info)}/{len(segments)} clips")
    return clips_info


def get_available_transitions() -> list[str]:
    """Get list of available transition video files.

    Returns:
        List of file paths to transition .mp4 files
    """
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
    """Apply transition effect between two clips using a transition video.

    Args:
        clip1_path: Path to first clip
        clip2_path: Path to second clip
        transition_path: Path to transition video
        output_path: Path for output file

    Returns:
        True if transition was applied successfully
    """
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

        clip1_faded = clip1.with_effects([FadeOut(duration=fade_duration)])
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
    segments: list[dict[str, Any]],
    output_dir: Path,
    font_family: str = "THEBOLDFONT-FREEVERSION",
    font_size: int = 24,
    font_color: str = "#FFFFFF",
    logo_path: str | None = None,
    logo_position: str = "top-right",
    output_resolution: str = "720p",
    subtitle_style: dict[str, Any] | None = None,
    subtitle_position: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Create video clips with transition effects between them.

    Args:
        video_path: Path to source video file
        segments: List of segment dicts
        output_dir: Directory for output files
        font_family: Font family name
        font_size: Font size in pixels
        font_color: Font color
        logo_path: Optional logo overlay path
        logo_position: Logo corner position
        output_resolution: Target resolution preset
        subtitle_style: Subtitle style options
        subtitle_position: Subtitle position options

    Returns:
        List of clip info dicts (with transition versions where applicable)
    """
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
            enhanced_clips.append(clip_info)
        else:
            prev_clip_path = Path(clips_info[i - 1]["path"])
            current_clip_path = Path(clip_info["path"])

            # Select transition (cycle through available transitions)
            transition_path = Path(transitions[i % len(transitions)])

            transition_filename = f"transition_{i}_{clip_info['filename']}"
            transition_output_path = transition_output_dir / transition_filename

            success = apply_transition_effect(
                prev_clip_path,
                current_clip_path,
                transition_path,
                transition_output_path,
            )

            if success:
                enhanced_clip_info = clip_info.copy()
                enhanced_clip_info["filename"] = transition_filename
                enhanced_clip_info["path"] = str(transition_output_path)
                enhanced_clip_info["has_transition"] = True
                enhanced_clips.append(enhanced_clip_info)
                logger.info(f"Added transition to clip {i + 1}")
            else:
                enhanced_clips.append(clip_info)
                logger.warning(
                    f"Failed to add transition to clip {i + 1}, using original"
                )

    logger.info(f"Successfully created {len(enhanced_clips)} clips with transitions")
    return enhanced_clips


# end backend/src/clip_assembly.py
