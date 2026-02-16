# start backend/src/video_utils.py
"""
Video utilities facade — re-exports from focused modules for backward compatibility.

This file was split into focused modules:
- transcript.py: Transcription, caching, formatting, timestamp parsing
- face_detection.py: Face detection with MediaPipe/OpenCV/Haar cascade
- cropping.py: Dimension calculation and crop positioning
- subtitles.py: Subtitle creation, positioning, and rendering
- clip_assembly.py: Clip creation, encoding, and transition effects
"""

from pathlib import Path
import logging

from .config import Config

logger = logging.getLogger(__name__)
config = Config()


def resolve_font_path(font_family: str) -> str:
    """Resolve font file path, checking bundled fonts first, then system fonts.

    Priority:
    1. Bundled font (backend/fonts/{font_family}.ttf)
    2. Common name variations (hyphens, underscores)
    3. System fonts database
    4. Default bundled font

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

    # Try system fonts via database (synchronous lookup using SQLAlchemy)
    try:
        from sqlalchemy import create_engine, text

        db_url = config.database_url or "sqlite+aiosqlite:///./supoclip.db"
        sync_url = db_url.replace("sqlite+aiosqlite:", "sqlite:")

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT file_path FROM system_fonts "
                    "WHERE name = :name AND is_valid = 1"
                ),
                {"name": font_family},
            ).fetchone()

        engine.dispose()

        if result and result[0]:
            system_font_path = result[0]
            if Path(system_font_path).exists():
                logger.info(f"Found system font '{font_family}' at: {system_font_path}")
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


# Re-export from transcript module
from .transcript import (  # noqa: E402
    format_ms_to_timestamp,
    format_ms_to_timestamp_precise,
    format_transcript_for_ai,
    get_video_transcript,
    cache_transcript_data,
    load_cached_transcript_data,
    extract_text_from_cache,
    parse_timestamp_to_seconds,
    snap_segment_to_sentence_start,
    TranscriptLineBreaker,
    TranscriptLineFormatter,
)

# Re-export from face_detection module
from .face_detection import (  # noqa: E402
    FaceDetector,
    MediaPipeFaceDetector,
    OpenCVDNNFaceDetector,
    HaarCascadeFaceDetector,
    VideoFrameSampler,
    FaceDetectionService,
    detect_faces_in_clip,
    filter_face_outliers,
)

# Re-export from cropping module
from .cropping import (  # noqa: E402
    round_to_even,
    TargetDimensionCalculator,
    FaceCenteredCropCalculator,
    CenterCropCalculator,
    detect_optimal_crop_region,
)

# Re-export from subtitles module
from .subtitles import (  # noqa: E402
    SubtitleWordFilter,
    SubtitleTextClipCreator,
    SubtitlePositioner,
    SubtitleClipBuilder,
    VideoProcessor,
    create_subtitles,
)

# Re-export from clip_assembly module
from .clip_assembly import (  # noqa: E402
    RESOLUTION_PRESETS,
    AUDIO_BUFFER_SECONDS,
    create_optimized_clip,
    create_clips_from_segments,
    get_available_transitions,
    apply_transition_effect,
    create_clips_with_transitions,
)

# Expose all public names for backward compatibility
__all__ = [
    # video_utils.py (this file)
    "resolve_font_path",
    # transcript.py
    "format_ms_to_timestamp",
    "format_ms_to_timestamp_precise",
    "format_transcript_for_ai",
    "get_video_transcript",
    "cache_transcript_data",
    "load_cached_transcript_data",
    "extract_text_from_cache",
    "parse_timestamp_to_seconds",
    "snap_segment_to_sentence_start",
    "TranscriptLineBreaker",
    "TranscriptLineFormatter",
    # face_detection.py
    "FaceDetector",
    "MediaPipeFaceDetector",
    "OpenCVDNNFaceDetector",
    "HaarCascadeFaceDetector",
    "VideoFrameSampler",
    "FaceDetectionService",
    "detect_faces_in_clip",
    "filter_face_outliers",
    # cropping.py
    "round_to_even",
    "TargetDimensionCalculator",
    "FaceCenteredCropCalculator",
    "CenterCropCalculator",
    "detect_optimal_crop_region",
    # subtitles.py
    "SubtitleWordFilter",
    "SubtitleTextClipCreator",
    "SubtitlePositioner",
    "SubtitleClipBuilder",
    "VideoProcessor",
    "create_subtitles",
    # clip_assembly.py
    "RESOLUTION_PRESETS",
    "AUDIO_BUFFER_SECONDS",
    "create_optimized_clip",
    "create_clips_from_segments",
    "get_available_transitions",
    "apply_transition_effect",
    "create_clips_with_transitions",
]

# end backend/src/video_utils.py
