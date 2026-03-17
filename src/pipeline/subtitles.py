# start src/pipeline/subtitles.py
"""ASS subtitle generation using pysubs2.

Generates .ass subtitle files with per-word timing for ffmpeg burn-in.
ffmpeg command: -vf "ass=subs.ass:fontsdir=fonts/"

Custom TTF fonts are supported via the fontsdir parameter in ffmpeg.
The font_family name must match the internal font family name in the TTF file.
Google Fonts are supported -- download the TTF to fonts/ and use the font family name.
"""

from dataclasses import dataclass
from pathlib import Path

import pysubs2
import structlog

logger = structlog.get_logger(__name__)

# Minimum word duration in milliseconds; shorter words are skipped as likely errors.
_MIN_WORD_DURATION_MS: int = 50


@dataclass(slots=True)
class SubtitleStyle:
    """Subtitle style configuration.

    Attributes:
        font_family: Font family name matching the internal name in the TTF file.
        font_size: Font size in points.
        font_color: Primary text color as #RRGGBB hex string.
        outline_color: Outline/stroke color as #RRGGBB hex string.
        outline_width: Outline thickness in pixels.
        shadow_depth: Drop shadow depth in pixels.
        position_y_pct: Vertical position as percentage from top of video (0=top, 100=bottom).
        video_height: Video height in pixels, used to compute MarginV.
        uppercase: When True, all word text is uppercased before writing.
    """

    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: float = 2.0
    shadow_depth: float = 1.0
    position_y_pct: int = 75
    video_height: int = 1920
    uppercase: bool = False


def hex_to_bgr_color(hex_color: str) -> pysubs2.Color:
    """Convert a #RRGGBB hex string to a pysubs2 Color.

    pysubs2's Color constructor takes (Blue, Green, Red, Alpha) -- note
    the reversed RGB order compared to standard HTML notation.
    Alpha 0 means fully opaque.

    Args:
        hex_color: Hex color string in #RRGGBB format (e.g. "#FFFFFF").

    Returns:
        A pysubs2.Color instance with alpha set to 0 (fully opaque).

    Raises:
        ValueError: If hex_color is not a valid #RRGGBB string.

    Example:
        >>> hex_to_bgr_color("#FF8800")
        Color(r=255, g=136, b=0, a=0)  # stored as BGR internally by pysubs2
    """
    cleaned = hex_color.lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"Expected #RRGGBB format, got: {hex_color!r}")
    r = int(cleaned[0:2], 16)
    g = int(cleaned[2:4], 16)
    b = int(cleaned[4:6], 16)
    # pysubs2.Color(r, g, b, a) — despite the confusing internal BGR storage,
    # the constructor takes r, g, b, a in that order.
    return pysubs2.Color(r, g, b, 0)


def calculate_margin_v(position_y_pct: int, video_height: int) -> int:
    """Calculate the MarginV value (pixels from bottom) for a given y position.

    pysubs2 MarginV is measured from the BOTTOM of the video frame.
    A position_y_pct of 75 means 75% down from the top, which is 25% from
    the bottom, so MarginV = 0.25 * video_height.

    Args:
        position_y_pct: Vertical position as a percentage from the top (0-100).
        video_height: Video height in pixels.

    Returns:
        MarginV in pixels (distance from the bottom of the frame).

    Example:
        >>> calculate_margin_v(75, 1920)
        480
    """
    pct_from_bottom = 100 - position_y_pct
    return int(video_height * pct_from_bottom / 100)


def _build_style(style: SubtitleStyle) -> pysubs2.SSAStyle:
    """Construct a pysubs2 SSAStyle from a SubtitleStyle dataclass.

    Args:
        style: Subtitle style configuration.

    Returns:
        Configured pysubs2.SSAStyle instance.
    """
    ssa_style = pysubs2.SSAStyle()
    ssa_style.fontname = style.font_family
    ssa_style.fontsize = style.font_size
    ssa_style.primarycolor = hex_to_bgr_color(style.font_color)
    ssa_style.outlinecolor = hex_to_bgr_color(style.outline_color)
    ssa_style.outline = style.outline_width
    ssa_style.shadow = style.shadow_depth
    ssa_style.alignment = pysubs2.Alignment.BOTTOM_CENTER
    ssa_style.marginv = calculate_margin_v(style.position_y_pct, style.video_height)
    return ssa_style


def generate_ass_subtitles(
    words: list[dict],
    style: SubtitleStyle | None = None,
) -> str:
    """Generate ASS subtitle file content with per-word timing.

    Creates one SSAEvent per word, enabling frame-accurate word-by-word
    caption display when burned in via ffmpeg's ass filter.

    Args:
        words: List of word dicts with keys:
            - text (str): The word string.
            - start_ms (int): Word start time in milliseconds.
            - end_ms (int): Word end time in milliseconds.
        style: Subtitle styling options. Uses defaults if None.

    Returns:
        Complete .ass file content as a string.

    Example:
        >>> words = [
        ...     {"text": "Hello", "start_ms": 1000, "end_ms": 1400},
        ...     {"text": "world", "start_ms": 1400, "end_ms": 1900},
        ... ]
        >>> ass_content = generate_ass_subtitles(words)
        >>> Path("subs.ass").write_text(ass_content)
        # ffmpeg: -vf "ass=subs.ass:fontsdir=fonts/"
    """
    resolved_style = style or SubtitleStyle()
    subs = pysubs2.SSAFile()
    subs.styles["Default"] = _build_style(resolved_style)

    skipped = 0
    for word_data in words:
        start_ms: int = int(word_data["start_ms"])
        end_ms: int = int(word_data["end_ms"])
        duration_ms = end_ms - start_ms

        if duration_ms < _MIN_WORD_DURATION_MS:
            logger.debug(
                "skipping short word",
                text=word_data.get("text"),
                duration_ms=duration_ms,
            )
            skipped += 1
            continue

        text: str = str(word_data["text"])
        if resolved_style.uppercase:
            text = text.upper()

        event = pysubs2.SSAEvent()
        event.start = start_ms
        event.end = end_ms
        event.text = text
        subs.events.append(event)

    logger.info(
        "generated ass subtitles",
        total_words=len(words),
        events=len(subs.events),
        skipped=skipped,
    )
    return subs.to_string("ass")


def write_ass_file(
    words: list[dict],
    output_path: str | Path,
    style: SubtitleStyle | None = None,
) -> Path:
    """Write an .ass subtitle file to disk.

    Generates the ASS subtitle content via generate_ass_subtitles and writes
    it to the specified path, creating parent directories as needed.

    Args:
        words: Word timing data in the same format as generate_ass_subtitles:
            list of dicts with text (str), start_ms (int), end_ms (int).
        output_path: Destination path for the .ass file.
        style: Subtitle style options. Uses defaults if None.

    Returns:
        Path to the written .ass file.

    Raises:
        OSError: If the file cannot be written.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ass_content = generate_ass_subtitles(words, style)
    path.write_text(ass_content, encoding="utf-8")
    logger.info("wrote ass file", path=str(path), size_bytes=len(ass_content))
    return path


# end src/pipeline/subtitles.py
