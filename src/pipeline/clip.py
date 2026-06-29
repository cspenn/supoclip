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
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from src.config import get_config
from src.exceptions import ClipGenerationError
from src.pipeline.face_detect import (
    calculate_crop_box,
    detect_face_center,
    get_representative_frame,
)
from src.pipeline.subtitles import SubtitleStyle, write_ass_file

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Resolution presets — 9:16 vertical format, (width, height)
#
# CANONICAL SOURCE OF TRUTH for output resolutions (M-11). The UI surfaces
# (src/pages/home.py and src/pages/settings.py) expose exactly this key set
# (720p / 1080p) with 1080p as the default. Keep those non-owned UI files in
# sync with the keys defined here. 480p was dropped because no UI surface
# offered it; an unknown key falls back to _DEFAULT_RESOLUTION below.
# ---------------------------------------------------------------------------
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "720p": (720, 1280),
    "1080p": (1080, 1920),
}

_DEFAULT_RESOLUTION: str = "1080p"

# Representative frame timestamp used for face detection (seconds into segment)
_FACE_DETECT_OFFSET_S: float = 1.0

# ffprobe invocation prefix for probing the first video stream's dimensions.
_FFPROBE_DIMENSION_ARGS: tuple[str, ...] = (
    "ffprobe",
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=width,height",
    "-of",
    "json",
)


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
        output_resolution: Target resolution preset key ("720p", "1080p").
        subtitle_style: Subtitle styling; None disables subtitle burn-in.
        logo_path: Path to a logo image overlaid at the top-right of the clip.
            When the file is missing the overlay is silently skipped.
        transition_path: Path to a transition ``.mp4`` whose **content** is
            prepended to the generated clip so the output is
            ``[transition][main clip]``. ``None`` (the default) is a clean no-op
            that leaves output byte-identical to the no-transition pipeline.
            When the file is missing the transition is silently skipped. The
            orchestration layer sets this per clip via round-robin selection over
            the configured transitions directory.
    """

    output_resolution: str = _DEFAULT_RESOLUTION
    subtitle_style: SubtitleStyle | None = None
    logo_path: str | Path | None = None
    transition_path: str | Path | None = None


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


# Logo overlay sizing — fraction of the output width and pixel margin.
_LOGO_WIDTH_FRACTION: float = 0.18
_LOGO_MARGIN_PX: int = 20

# Encode arguments shared by every clip (codec, preset, faststart).
_ENCODE_ARGS: tuple[str, ...] = (
    "-c:v",
    "libx264",
    "-preset",
    "fast",
    "-crf",
    "23",
    "-c:a",
    "aac",
    "-b:a",
    "128k",
    "-movflags",
    "+faststart",
)

# lavfi source generating silent stereo audio. Used to give a transition (or a
# main clip whose source had no audio track) a concat-compatible audio stream,
# since the concat filter requires every segment to expose the same streams.
_SILENT_AUDIO_SOURCE: str = "anullsrc=channel_layout=stereo:sample_rate=44100"


def _build_main_video_filter(
    crop_box: tuple[int, int, int, int],
    out_width: int,
    out_height: int,
    ass_path: str | Path | None,
    fonts_dir: str | Path | None,
) -> str:
    """Build the comma-joined filter chain applied to the main video stream.

    The chain is crop → scale → optional ASS burn-in. It is identical whether
    the clip is rendered via ``-vf`` (no logo) or as the base branch of a
    ``-filter_complex`` overlay graph (logo present), so the no-logo output
    stays byte-identical to the legacy pipeline.

    Args:
        crop_box: ``(x, y, width, height)`` crop rectangle.
        out_width: Desired output width in pixels.
        out_height: Desired output height in pixels.
        ass_path: Path to an ``.ass`` subtitle file, or ``None`` to skip.
        fonts_dir: Directory of TTF fonts for libass (used only with ass_path).

    Returns:
        The filtergraph chain as a single comma-joined string.
    """
    x, y, crop_w, crop_h = crop_box
    parts: list[str] = [
        f"crop={crop_w}:{crop_h}:{x}:{y}",
        f"scale={out_width}:{out_height}",
    ]

    if ass_path is not None:
        ass_filter = f"ass={_escape_filter_path(ass_path)}"
        if fonts_dir is not None:
            ass_filter += f":fontsdir={_escape_filter_path(fonts_dir)}"
        parts.append(ass_filter)

    return ",".join(parts)


def _build_logo_overlay_graph(main_chain: str, out_width: int) -> str:
    """Build a ``-filter_complex`` graph that overlays a logo on the main video.

    The main video (input ``0``) runs through ``main_chain`` to produce a
    ``[base]`` stream; the logo (input ``1``) is scaled to ~18% of the output
    width preserving aspect ratio, then overlaid at the top-right with a small
    margin. The final stream is labelled ``[vout]`` for explicit mapping.

    Args:
        main_chain: The crop/scale/fade/ass chain from
            :func:`_build_main_video_filter`.
        out_width: Output width in pixels, used to size the logo.

    Returns:
        The full ``filter_complex`` graph string.
    """
    logo_w = max(1, int(out_width * _LOGO_WIDTH_FRACTION))
    margin = _LOGO_MARGIN_PX
    return f"[0:v]{main_chain}[base];[1:v]scale={logo_w}:-1[logo];[base][logo]overlay=main_w-overlay_w-{margin}:{margin}[vout]"


def build_concat_command(
    transition_path: str | Path,
    main_path: str | Path,
    output_path: str | Path,
    *,
    out_width: int,
    out_height: int,
    fps: float,
    transition_silence_s: float | None,
    main_silence_s: float | None,
) -> list[str]:
    """Build the ffmpeg command that prepends a transition to the main clip.

    The transition video is normalised to the main clip's exact geometry — width,
    height, fps, square pixel aspect ratio and ``yuv420p`` pixel format — then the
    two segments are joined with the ``concat`` filter so the output is
    ``[transition][main clip]``. The concat filter requires every segment to
    expose the same streams, so a silent stereo audio track is synthesised for
    any segment whose source lacks audio.

    Args:
        transition_path: Source transition ``.mp4`` (input ``0``).
        main_path: Already-rendered main clip (input ``1``), carrying its crop,
            scale, subtitle burn-in and logo overlay.
        output_path: Destination path for the concatenated ``.mp4``.
        out_width: Main clip width in pixels (transition is scaled to match).
        out_height: Main clip height in pixels (transition is scaled to match).
        fps: Target frame rate; the transition is retimed to it so both segments
            share a frame rate. ``fps`` filtering preserves duration.
        transition_silence_s: When set, synthesise a silent audio track of this
            many seconds for the transition (its source had no audio). When
            ``None`` the transition's own audio stream (``0:a``) is used.
        main_silence_s: When set, synthesise a silent audio track of this many
            seconds for the main clip (its source had no audio). When ``None``
            the main clip's own audio stream (``1:a``) is used.

    Returns:
        List of string arguments suitable for ``subprocess.run(cmd, shell=False)``.
    """
    cmd: list[str] = ["ffmpeg", "-y", "-i", str(transition_path), "-i", str(main_path)]
    next_input = 2

    if transition_silence_s is None:
        transition_audio = "[0:a]"
    else:
        cmd += ["-f", "lavfi", "-t", str(transition_silence_s), "-i", _SILENT_AUDIO_SOURCE]
        transition_audio = f"[{next_input}:a]"
        next_input += 1

    if main_silence_s is None:
        main_audio = "[1:a]"
    else:
        cmd += ["-f", "lavfi", "-t", str(main_silence_s), "-i", _SILENT_AUDIO_SOURCE]
        main_audio = f"[{next_input}:a]"
        next_input += 1

    graph = (
        f"[0:v]scale={out_width}:{out_height},setsar=1,fps={fps},format=yuv420p[tv];"
        f"[1:v]setsar=1,format=yuv420p[mv];"
        f"[tv]{transition_audio}[mv]{main_audio}concat=n=2:v=1:a=1[v][a]"
    )

    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", *_ENCODE_ARGS, str(output_path)]
    return cmd


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
    logo_path: str | Path | None = None,
) -> list[str]:
    """Build the ffmpeg argument list for clip generation.

    Constructs a command that: fast-seeks before the input (``-ss``
    before ``-i``), trims to the segment duration (``-to``), applies
    a video-filter chain of crop → scale → optional ASS subtitle burn-in,
    optionally overlays a logo via a second input, and encodes with
    libx264/aac.

    When ``logo_path`` is ``None`` the command uses a single-input ``-vf``
    chain (byte-identical to the legacy pipeline). When a logo is supplied a
    second ``-i`` input plus ``-filter_complex`` overlay graph is used, and the
    output video/audio are explicitly mapped (``-map [vout] -map 0:a?``).

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
        logo_path: Path to a logo image overlaid at the top-right. ``None``
            keeps the simple ``-vf`` path with no behaviour change.

    Returns:
        List of string arguments suitable for
        ``subprocess.run(cmd, shell=False)``.

    Note:
        ``-ss`` before ``-i`` enables fast keyframe seek; ``-to`` is then
        the clip *duration* (not the absolute end time), because the seek
        has already advanced the stream.
    """
    duration_s = end_s - start_s
    main_chain = _build_main_video_filter(
        crop_box,
        out_width,
        out_height,
        ass_path,
        fonts_dir,
    )

    cmd: list[str] = [
        "ffmpeg",
        "-y",  # overwrite output without prompting
        "-ss",
        str(start_s),
        "-i",
        str(input_path),
    ]

    if logo_path is not None:
        cmd += ["-i", str(logo_path)]
        graph = _build_logo_overlay_graph(main_chain, out_width)
        # Map the overlaid video and pass through source audio if present.
        video_args = ["-filter_complex", graph, "-map", "[vout]", "-map", "0:a?"]
    else:
        video_args = ["-vf", main_chain]

    cmd += ["-to", str(duration_s), *video_args, *_ENCODE_ARGS, str(output_path)]
    return cmd


def _prepare_subtitle_file(
    out: Path,
    segment: TranscriptSegment,
    words: list[dict],
    style: SubtitleStyle | None,
) -> Path | None:
    """Write an ``.ass`` subtitle file for the segment, or return ``None``.

    Args:
        out: Final clip output path (the ``.ass`` is named from its stem).
        segment: Segment whose time range bounds the included words.
        words: Full word-level transcript (filtered to the segment range).
        style: Subtitle styling; ``None`` disables subtitle burn-in.

    Returns:
        Path to the written ``.ass`` file, or ``None`` when burn-in is disabled
        or no words fall within the segment.
    """
    if style is None:
        return None
    segment_words = filter_words_for_segment(words, segment.start_s, segment.end_s)
    if not segment_words:
        return None
    ass_path = out.parent / (out.stem + ".ass")
    write_ass_file(segment_words, ass_path, style=style)
    log.info("subtitle_file_written", path=str(ass_path), words=len(segment_words))
    return ass_path


def _resolve_logo(logo_path: str | Path | None) -> str | Path | None:
    """Return the logo path only when it points at an existing file.

    Args:
        logo_path: Candidate logo path from :class:`ClipOptions`.

    Returns:
        The path when configured and the file exists; ``None`` otherwise so a
        misconfigured path degrades to a clean no-overlay clip.
    """
    if logo_path is not None and Path(logo_path).exists():
        return logo_path
    return None


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
    out_width, out_height = RESOLUTIONS.get(opts.output_resolution, RESOLUTIONS[_DEFAULT_RESOLUTION])

    # --- Step 1: face detection ----------------------------------------
    face_ts = segment.start_s + _FACE_DETECT_OFFSET_S
    frame = get_representative_frame(source, timestamp_s=face_ts)
    face_center = detect_face_center(frame) if frame is not None else None

    # --- Step 2: crop box -------------------------------------------------
    # We need the source video's frame dimensions.  Probe them with ffprobe
    # (the project's mandated tool); this fails loudly rather than guessing.
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
    ass_path = _prepare_subtitle_file(out, segment, words, opts.subtitle_style)

    # Locate fonts directory relative to the project.
    fonts_dir: Path | None = _find_fonts_dir()

    # Resolve the logo overlay: only pass it through when the file exists, so a
    # misconfigured path degrades to a clean no-overlay clip instead of failing.
    logo_path = _resolve_logo(opts.logo_path)

    # Resolve the transition: only mux it when the file exists, so a misconfigured
    # path degrades to a clean no-transition clip. When active, the main clip is
    # rendered to an intermediate file first and the transition is prepended in a
    # second pass; otherwise we render straight to ``out`` (byte-identical no-op).
    transition = _resolve_transition(opts.transition_path)
    main_target = out if transition is None else out.parent / f"{out.stem}.main{out.suffix}"

    # --- Step 4: ffmpeg ---------------------------------------------------
    cmd = build_ffmpeg_command(
        input_path=source,
        output_path=main_target,
        start_s=segment.start_s,
        end_s=segment.end_s,
        crop_box=crop_box,
        out_width=out_width,
        out_height=out_height,
        ass_path=ass_path,
        fonts_dir=fonts_dir,
        logo_path=logo_path,
    )

    log.info("ffmpeg_start", cmd=" ".join(cmd))
    result = await asyncio.to_thread(_run_ffmpeg, cmd)

    if result.returncode != 0:
        stderr = result.stderr or b""
        raise ClipGenerationError(f"ffmpeg failed (exit {result.returncode}): " + stderr.decode(errors="replace").strip())

    # --- Step 5: prepend transition content (when configured) -------------
    if transition is not None:
        await asyncio.to_thread(
            _prepend_transition,
            transition,
            main_target,
            out,
            out_width,
            out_height,
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

    A hard wall-clock timeout (``ffmpeg_timeout_s`` config, default 300s) guards
    against a hung encode pinning a worker forever. A timeout fails loudly as a
    :class:`ClipGenerationError` rather than blocking indefinitely (M-3).

    Args:
        cmd: Full argument list as returned by :func:`build_ffmpeg_command`.

    Returns:
        :class:`subprocess.CompletedProcess` with captured stderr.

    Raises:
        ClipGenerationError: If ffmpeg does not finish within the timeout.
    """
    timeout_s = getattr(get_config(), "ffmpeg_timeout_s", 300)
    try:
        return subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClipGenerationError(f"ffmpeg timed out after {timeout_s}s") from exc


def _resolve_transition(transition_path: str | Path | None) -> Path | None:
    """Resolve a configured transition path to an existing file, or ``None``.

    Args:
        transition_path: Candidate transition path from :class:`ClipOptions`.

    Returns:
        The :class:`~pathlib.Path` when a path is configured and the file
        exists; ``None`` when unset or missing (a clean no-op).
    """
    if transition_path is None:
        return None
    candidate = Path(transition_path)
    return candidate if candidate.exists() else None


def _prepend_transition(
    transition_path: Path,
    main_path: Path,
    output_path: Path,
    out_width: int,
    out_height: int,
) -> None:
    """Mux a transition clip's content in front of the rendered main clip.

    Probes the main clip's frame rate and both clips' audio presence, then runs a
    concat pass producing ``[transition][main clip]`` at ``output_path``. The
    intermediate ``main_path`` is always removed afterwards. Fails loudly so a
    broken concat never silently yields a transition-less clip.

    Args:
        transition_path: Existing transition ``.mp4`` to prepend.
        main_path: Intermediate main clip (crop/scale/subtitles/logo already
            applied); removed once muxing finishes.
        output_path: Destination for the concatenated clip.
        out_width: Main clip width in pixels.
        out_height: Main clip height in pixels.

    Raises:
        ClipGenerationError: If any probe fails or the concat ffmpeg pass exits
            non-zero.
    """
    fps = _probe_video_fps(main_path)
    transition_silence_s = None if _video_has_audio(transition_path) else _probe_duration(transition_path)
    main_silence_s = None if _video_has_audio(main_path) else _probe_duration(main_path)

    cmd = build_concat_command(
        transition_path,
        main_path,
        output_path,
        out_width=out_width,
        out_height=out_height,
        fps=fps,
        transition_silence_s=transition_silence_s,
        main_silence_s=main_silence_s,
    )

    log.info("ffmpeg_transition_start", cmd=" ".join(cmd))
    try:
        result = _run_ffmpeg(cmd)
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode(errors="replace").strip()
            raise ClipGenerationError(f"ffmpeg transition concat failed (exit {result.returncode}): {stderr}")
    finally:
        main_path.unlink(missing_ok=True)


def _run_ffprobe(cmd: list[str]) -> bytes:
    """Execute an ffprobe command and return its stdout, failing loudly.

    Args:
        cmd: Full ffprobe argument list.

    Returns:
        Raw stdout bytes from ffprobe.

    Raises:
        ClipGenerationError: If ffprobe cannot be executed or exits non-zero.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except OSError as exc:
        raise ClipGenerationError(f"ffprobe could not be executed: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace").strip()
        raise ClipGenerationError(f"ffprobe failed (exit {result.returncode}): {stderr}")

    return result.stdout or b""


def _probe_duration(video_path: Path) -> float:
    """Return the container duration of *video_path* in seconds via ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds.

    Raises:
        ClipGenerationError: If ffprobe fails or the duration cannot be parsed.
    """
    stdout = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    text = stdout.decode(errors="replace").strip()
    try:
        return float(text)
    except ValueError as exc:
        raise ClipGenerationError(f"could not parse ffprobe duration for {video_path}: {text!r}") from exc


def _video_has_audio(video_path: Path) -> bool:
    """Return ``True`` when *video_path* exposes at least one audio stream.

    Args:
        video_path: Path to the video file.

    Returns:
        ``True`` if an audio stream is present, else ``False``.

    Raises:
        ClipGenerationError: If ffprobe fails.
    """
    stdout = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
    )
    return bool(stdout.strip())


def _probe_video_fps(video_path: Path) -> float:
    """Return the first video stream's frame rate of *video_path* via ffprobe.

    ffprobe reports ``r_frame_rate`` as a ``num/den`` rational (e.g. ``24/1``).

    Args:
        video_path: Path to the video file.

    Returns:
        Frame rate in frames per second.

    Raises:
        ClipGenerationError: If ffprobe fails, the value cannot be parsed, or the
            denominator is zero.
    """
    stdout = _run_ffprobe(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    text = stdout.decode(errors="replace").strip()
    numerator_text, _, denominator_text = text.partition("/")
    try:
        numerator = float(numerator_text)
        denominator = float(denominator_text) if denominator_text else 1.0
    except ValueError as exc:
        raise ClipGenerationError(f"could not parse ffprobe fps for {video_path}: {text!r}") from exc

    if denominator == 0:
        raise ClipGenerationError(f"ffprobe reported zero fps denominator for {video_path}: {text!r}")
    return numerator / denominator


def _parse_ffprobe_dimensions(stdout: bytes) -> tuple[int, int]:
    """Parse (width, height) from ffprobe JSON output.

    Args:
        stdout: Raw ffprobe stdout containing a JSON ``streams`` array.

    Returns:
        ``(width, height)`` in pixels.

    Raises:
        ClipGenerationError: If the JSON is malformed, missing the expected
            keys, or reports non-positive dimensions.
    """
    try:
        data = json.loads(stdout or b"{}")
        stream = data["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ClipGenerationError(f"could not parse ffprobe dimension output: {exc}") from exc

    if width <= 0 or height <= 0:
        raise ClipGenerationError(f"ffprobe reported invalid dimensions {width}x{height}")
    return (width, height)


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return (width, height) of the video's first stream via ffprobe.

    Uses ffprobe (bundled with ffmpeg, the project's mandated tool) instead of
    cv2 so dimension probing never silently guesses. Fails loudly on any probe
    error rather than returning a hardcoded fallback that would corrupt crops.

    Args:
        video_path: Path to the video file.

    Returns:
        ``(width, height)`` tuple in pixels.

    Raises:
        ClipGenerationError: If ffprobe cannot be executed, exits non-zero, or
            returns output that cannot be parsed into positive dimensions.
    """
    cmd = [*_FFPROBE_DIMENSION_ARGS, str(video_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
    except OSError as exc:
        raise ClipGenerationError(f"ffprobe could not be executed for {video_path}: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace").strip()
        raise ClipGenerationError(f"ffprobe failed (exit {result.returncode}) for {video_path}: {stderr}")

    return _parse_ffprobe_dimensions(result.stdout or b"")


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
