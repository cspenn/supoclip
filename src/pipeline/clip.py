# start src/pipeline/clip.py
"""ffmpeg-based clip generation for 9:16 vertical short clips.

Replaces MoviePy (clip_assembly.py + cropping.py) with a single ffmpeg
subprocess per clip: seek → trim → crop → scale → subtitle burn-in → encode.

Usage::

    from src.pipeline.clip import generate_clip, ClipOptions
    from src.pipeline.subtitles import SubtitleStyle

    options = ClipOptions(
        output_resolution="1080p",
        subtitle_style=SubtitleStyle(font_family="TikTokSans-Regular"),
    )
    output = await generate_clip(
        source_video="input.mp4",
        segment=seg,
        words=words,
        output_path="out.mp4",
        options=options,
    )
"""

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from src.pipeline.face_detect import (
    calculate_crop_box,
    detect_face_center,
    get_representative_frame,
)
from src.pipeline.subtitles import SubtitleStyle, write_ass_file

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Resolution presets — 9:16 vertical format, (width, height)
# ---------------------------------------------------------------------------
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "480p": (480, 854),
    "720p": (720, 1280),
    "1080p": (1080, 1920),
}

_DEFAULT_RESOLUTION: str = "1080p"

# Representative frame timestamp used for face detection (seconds into segment)
_FACE_DETECT_OFFSET_S: float = 1.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TranscriptSegment:
    """Selected segment from the transcript analysis pipeline.

    Attributes:
        start_s: Segment start time in seconds (float).
        end_s: Segment end time in seconds (float).
        text: Verbatim transcript text for this segment.
        relevance_score: Confidence score in range [0.0, 1.0].
        reasoning: Explanation of why this segment was selected.
    """

    start_s: float
    end_s: float
    text: str = ""
    relevance_score: float = 1.0
    reasoning: str = ""


@dataclass(slots=True)
class ClipOptions:
    """Options controlling clip generation behaviour.

    Attributes:
        output_resolution: Target resolution preset key ("480p", "720p", "1080p").
        subtitle_style: Subtitle styling; None disables subtitle burn-in.
        logo_path: Path to a logo image for overlay (not yet implemented).
        add_transitions: Reserved for future fade-in/fade-out support.
        transitions_dir: Directory containing transition .mp4 files (reserved).
    """

    output_resolution: str = _DEFAULT_RESOLUTION
    subtitle_style: SubtitleStyle | None = None
    logo_path: str | Path | None = None
    add_transitions: bool = False
    transitions_dir: str | Path | None = None


class ClipGenerationError(Exception):
    """Raised when ffmpeg fails or clip generation cannot proceed."""


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def _escape_filter_path(path: str | Path) -> str:
    """Escape a filesystem path for safe use inside an ffmpeg filtergraph.

    The ``-vf`` filtergraph treats ``\\``, ``:``, ``'``, ``[``, ``]``, ``,``
    and ``;`` as special. A raw path containing a colon or space (e.g. a
    ``TEMP_DIR`` with a space) silently corrupts the ``ass=`` filter and the
    whole command fails (audit H-1, spec 10.4). We backslash-escape the special
    characters; backslash must be escaped first so we do not double-escape the
    escapes we add.

    Args:
        path: Path to embed in the filtergraph (e.g. an ``.ass`` file).

    Returns:
        The path string with filtergraph-special characters escaped.
    """
    text = str(path)
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("[", "\\[").replace("]", "\\]")
    text = text.replace(",", "\\,").replace(";", "\\;")
    return text


def filter_words_for_segment(
    words: list[dict],
    start_s: float,
    end_s: float,
) -> list[dict]:
    """Return only words that fall within the segment's time range.

    Adjusts word timestamps to be relative to the segment start so they
    can be passed directly to write_ass_file() for the trimmed clip.

    A word is included when its midpoint falls within [start_ms, end_ms].

    Args:
        words: Full word list; each dict must have ``start_ms`` and
            ``end_ms`` keys containing timestamps in **milliseconds**.
        start_s: Segment start time in **seconds**.
        end_s: Segment end time in **seconds**.

    Returns:
        Filtered word list with timestamps adjusted to be relative to
        ``start_s``.  A word at 30 s in a segment starting at 25 s will
        have ``start_ms = 5000``.

    Example:
        >>> words = [
        ...     {"text": "hi",   "start_ms": 25000, "end_ms": 25400},
        ...     {"text": "there","start_ms": 25400, "end_ms": 25900},
        ...     {"text": "bye",  "start_ms": 40000, "end_ms": 40500},
        ... ]
        >>> filter_words_for_segment(words, 25.0, 30.0)
        [
            {"text": "hi",    "start_ms": 0,   "end_ms": 400},
            {"text": "there", "start_ms": 400, "end_ms": 900},
        ]
    """
    start_ms = int(start_s * 1000)
    end_ms = int(end_s * 1000)
    offset_ms = start_ms

    filtered: list[dict] = []
    for word in words:
        w_start: int = int(word["start_ms"])
        w_end: int = int(word["end_ms"])
        midpoint = (w_start + w_end) // 2
        if start_ms <= midpoint <= end_ms:
            adjusted = dict(word)
            adjusted["start_ms"] = max(0, w_start - offset_ms)
            adjusted["end_ms"] = max(0, w_end - offset_ms)
            filtered.append(adjusted)

    return filtered


def build_ffmpeg_command(
    input_path: str | Path,
    output_path: str | Path,
    start_s: float,
    end_s: float,
    crop_box: tuple[int, int, int, int],
    out_width: int,
    out_height: int,
    ass_path: str | Path | None = None,
    fonts_dir: str | Path | None = None,
) -> list[str]:
    """Build the ffmpeg argument list for clip generation.

    Constructs a command that: fast-seeks before the input (``-ss``
    before ``-i``), trims to the segment duration (``-to``), applies
    a video-filter chain of crop → scale → optional ASS subtitle
    burn-in, and encodes with libx264/aac.

    Args:
        input_path: Source video file path.
        output_path: Destination .mp4 path.
        start_s: Seek position in seconds (placed before ``-i`` for speed).
        end_s: Segment end in seconds; duration = end_s - start_s.
        crop_box: ``(x, y, width, height)`` from
            :func:`src.pipeline.face_detect.calculate_crop_box`.
        out_width: Desired output width in pixels.
        out_height: Desired output height in pixels.
        ass_path: Path to an ``.ass`` subtitle file.  When provided the
            ``ass=`` filter is appended to the chain.
        fonts_dir: Directory containing TTF font files for libass.  Only
            used when ``ass_path`` is also provided.

    Returns:
        List of string arguments suitable for
        ``subprocess.run(cmd, shell=False)``.

    Note:
        ``-ss`` before ``-i`` enables fast keyframe seek; ``-to`` is then
        the clip *duration* (not the absolute end time), because the seek
        has already advanced the stream.
    """
    x, y, crop_w, crop_h = crop_box
    duration_s = end_s - start_s

    # Build the video filter chain progressively.
    vf_parts: list[str] = [
        f"crop={crop_w}:{crop_h}:{x}:{y}",
        f"scale={out_width}:{out_height}",
    ]

    if ass_path is not None:
        ass_filter = f"ass={_escape_filter_path(ass_path)}"
        if fonts_dir is not None:
            ass_filter += f":fontsdir={_escape_filter_path(fonts_dir)}"
        vf_parts.append(ass_filter)

    video_filter = ",".join(vf_parts)

    return [
        "ffmpeg",
        "-y",  # overwrite output without prompting
        "-ss", str(start_s),
        "-i", str(input_path),
        "-to", str(duration_s),
        "-vf", video_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------


async def generate_clip(
    source_video: str | Path,
    segment: TranscriptSegment,
    words: list[dict],
    output_path: str | Path,
    options: ClipOptions | None = None,
) -> Path:
    """Generate a 9:16 vertical clip from a video segment.

    Pipeline:

    1. Detect the face center from a representative frame of the segment.
    2. Calculate the 9:16 crop box (face-centred or frame-centred fallback).
    3. Generate a ``.ass`` subtitle file from the words in this segment's
       time range (skipped when ``options.subtitle_style`` is ``None``).
    4. Run ffmpeg in a thread: seek → trim → crop → scale → subtitle
       burn-in → H.264/AAC encode.

    Args:
        source_video: Path to the source video file.
        segment: Selected segment with ``start_s`` / ``end_s`` in seconds.
        words: Full word-level transcript (filtered internally to the
            segment range).  Each dict must have ``start_ms``, ``end_ms``
            (milliseconds), and ``text`` keys.
        output_path: Destination path for the output ``.mp4``.
        options: Clip generation options.  Uses defaults when ``None``.

    Returns:
        :class:`pathlib.Path` to the written clip file.

    Raises:
        ClipGenerationError: If ffmpeg exits with a non-zero return code.
    """
    opts = options or ClipOptions()
    out = Path(output_path)
    source = Path(source_video)

    out.parent.mkdir(parents=True, exist_ok=True)

    # Resolve output resolution.
    out_width, out_height = RESOLUTIONS.get(
        opts.output_resolution, RESOLUTIONS[_DEFAULT_RESOLUTION]
    )

    # --- Step 1: face detection ----------------------------------------
    face_ts = segment.start_s + _FACE_DETECT_OFFSET_S
    frame = get_representative_frame(source, timestamp_s=face_ts)
    face_center = detect_face_center(frame) if frame is not None else None

    # --- Step 2: crop box -------------------------------------------------
    # We need the source video's frame dimensions.  Read via cv2 if available;
    # fall back to the target resolution (produces a valid but unoptimised crop).
    frame_width, frame_height = _get_video_dimensions(source)
    crop_box = calculate_crop_box(
        frame_width=frame_width,
        frame_height=frame_height,
        face_center=face_center,
        target_width=out_width,
        target_height=out_height,
    )
    log.info(
        "clip_crop_box",
        crop_box=crop_box,
        face_detected=face_center is not None,
        resolution=opts.output_resolution,
    )

    # --- Step 3: subtitle file --------------------------------------------
    ass_path: Path | None = None
    if opts.subtitle_style is not None:
        segment_words = filter_words_for_segment(words, segment.start_s, segment.end_s)
        if segment_words:
            tmp_dir = out.parent
            ass_path = tmp_dir / (out.stem + ".ass")
            write_ass_file(
                segment_words,
                ass_path,
                style=opts.subtitle_style,
            )
            log.info("subtitle_file_written", path=str(ass_path), words=len(segment_words))

    # Locate fonts directory relative to the project.
    fonts_dir: Path | None = _find_fonts_dir()

    # --- Step 4: ffmpeg ---------------------------------------------------
    cmd = build_ffmpeg_command(
        input_path=source,
        output_path=out,
        start_s=segment.start_s,
        end_s=segment.end_s,
        crop_box=crop_box,
        out_width=out_width,
        out_height=out_height,
        ass_path=ass_path,
        fonts_dir=fonts_dir,
    )

    log.info("ffmpeg_start", cmd=" ".join(cmd))
    result = await asyncio.to_thread(_run_ffmpeg, cmd)

    if result.returncode != 0:
        stderr = result.stderr or b""
        raise ClipGenerationError(
            f"ffmpeg failed (exit {result.returncode}): "
            + stderr.decode(errors="replace").strip()
        )

    log.info(
        "clip_generated",
        output=str(out),
        segment_start=segment.start_s,
        segment_end=segment.end_s,
    )
    return out


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _run_ffmpeg(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    """Execute ffmpeg subprocess (blocking; call via asyncio.to_thread).

    Args:
        cmd: Full argument list as returned by :func:`build_ffmpeg_command`.

    Returns:
        :class:`subprocess.CompletedProcess` with captured stderr.
    """
    return subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        check=False,
    )


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return (width, height) of the video, falling back to 1920×1080.

    Uses cv2 when available.  Falls back gracefully so that the rest of
    the pipeline can continue with a sensible default even on machines
    without opencv.

    Args:
        video_path: Path to the video file.

    Returns:
        ``(width, height)`` tuple in pixels.
    """
    try:
        import cv2  # type: ignore[import-untyped]  # optional dependency
    except ImportError:
        log.warning("cv2_unavailable_for_dimensions", path=str(video_path))
        return (1920, 1080)

    cap = cv2.VideoCapture(str(video_path))
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width > 0 and height > 0:
            return (width, height)
        log.warning("invalid_video_dimensions", width=width, height=height)
        return (1920, 1080)
    except Exception as exc:
        log.warning("video_dimension_error", error=str(exc))
        return (1920, 1080)
    finally:
        cap.release()


def _find_fonts_dir() -> Path | None:
    """Locate the project fonts directory.

    Searches upward from this file's location for a ``fonts/`` directory.
    Returns ``None`` if not found so the caller can omit the ``fontsdir``
    argument to libass.

    Returns:
        Path to the ``fonts/`` directory, or ``None`` if not found.
    """
    candidate = Path(__file__).parent
    for _ in range(6):
        fonts = candidate / "fonts"
        if fonts.is_dir():
            return fonts
        candidate = candidate.parent
    return None


# end src/pipeline/clip.py
