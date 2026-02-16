# start backend/src/video_utils.py
"""
Video utilities facade — re-exports from focused modules for backward compatibility.

This file was split into focused modules:
- font_resolver.py: Font path resolution (bundled, variations, system DB)
- transcript.py: Transcription, caching, formatting, timestamp parsing
- face_detection.py: Face detection with MediaPipe/OpenCV/Haar cascade
- cropping.py: Dimension calculation and crop positioning
- subtitles.py: Subtitle creation, positioning, and rendering
- clip_assembly.py: Clip creation, encoding, and transition effects
"""

# Re-export resolve_font_path from font_resolver (extracted to break circular dep)
from .font_resolver import resolve_font_path  # noqa: E402


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
