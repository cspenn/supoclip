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

# Maximum number of words shown together as a karaoke/context window. Consecutive
# words are grouped into windows of this size; within a window the active word is
# highlighted while its neighbors provide dimmed context (spec 9.2).
_WINDOW_SIZE: int = 6


@dataclass(slots=True)
class SubtitleStyle:
    """Subtitle style configuration.

    Attributes:
        font_family: Font family name matching the internal name in the TTF file.
        font_size: Font size in points.
        font_color: Primary (active word) text color as #RRGGBB hex string.
        secondary_color: Dim color for context (neighbor) words as #RRGGBB hex string.
        outline_color: Outline/stroke color as #RRGGBB hex string. Also used as the
            drop-shadow (BackColour) color.
        outline_width: Outline thickness in pixels.
        shadow_depth: Drop shadow depth in pixels.
        position_y_pct: Vertical position as percentage from top of video (0=top, 100=bottom).
        video_height: Video height in pixels, used to compute MarginV.
        uppercase: When True, all word text is uppercased before writing.
        bold: When True, the subtitle style is rendered bold.
    """

    font_family: str = "Arial"
    font_size: int = 24
    font_color: str = "#FFFFFF"
    secondary_color: str = "#888888"
    outline_color: str = "#000000"
    outline_width: float = 2.0
    shadow_depth: float = 1.0
    position_y_pct: int = 75
    video_height: int = 1920
    uppercase: bool = False
    bold: bool = True


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
    # pysubs2 exposes the ASS BackColour (the drop-shadow color) as ``backcolor``.
    ssa_style.backcolor = hex_to_bgr_color(style.outline_color)
    ssa_style.outline = style.outline_width
    ssa_style.shadow = style.shadow_depth
    ssa_style.bold = style.bold
    ssa_style.alignment = pysubs2.Alignment.BOTTOM_CENTER
    ssa_style.marginv = calculate_margin_v(style.position_y_pct, style.video_height)
    return ssa_style


def _escape_ass_text(text: str) -> str:
    """Escape ASS-special characters so word text renders literally.

    Prevents a word containing override syntax (``{``, ``}``, ``\\``, or a literal
    ``\\N``) from corrupting the markup or injecting override tags. libass honors
    ``\\{`` / ``\\}`` as literal braces and ``\\\\`` as a literal backslash, so an
    escaped word can never open an override block. Real newline characters are
    collapsed to spaces to keep each dialogue line intact.

    Args:
        text: Raw word text to escape.

    Returns:
        Escaped text safe to embed in an ASS dialogue event.
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _hex_to_ass_override(hex_color: str) -> str:
    """Convert a #RRGGBB hex string to an ASS inline color override value.

    ASS inline color overrides use the ``&HBBGGRR&`` byte order (reversed RGB),
    e.g. ``\\c&HBBGGRR&``. Validation is delegated to hex_to_bgr_color.

    Args:
        hex_color: Hex color string in #RRGGBB format.

    Returns:
        The ``&HBBGGRR&`` override value (without the leading ``\\c`` tag).

    Raises:
        ValueError: If hex_color is not a valid #RRGGBB string.
    """
    color = hex_to_bgr_color(hex_color)
    return f"&H{color.b:02X}{color.g:02X}{color.r:02X}&"


def _collect_valid_words(words: list[dict]) -> tuple[list[dict], int]:
    """Filter out words shorter than the minimum render duration.

    Args:
        words: Word dicts with text/start_ms/end_ms keys.

    Returns:
        A tuple of (kept words in original order, number skipped).
    """
    valid: list[dict] = []
    skipped = 0
    for word_data in words:
        duration_ms = int(word_data["end_ms"]) - int(word_data["start_ms"])
        if duration_ms < _MIN_WORD_DURATION_MS:
            logger.debug(
                "skipping short word",
                text=word_data.get("text"),
                duration_ms=duration_ms,
            )
            skipped += 1
            continue
        valid.append(word_data)
    return valid, skipped


def _render_word(text: str, uppercase: bool) -> str:
    """Apply casing and ASS escaping to a single word's display text.

    Args:
        text: Raw word text.
        uppercase: When True, uppercase the word before escaping.

    Returns:
        Escaped, casing-applied word text.
    """
    if uppercase:
        text = text.upper()
    return _escape_ass_text(text)


def _build_window_text(
    window: list[dict],
    active_index: int,
    style: SubtitleStyle,
    secondary_override: str,
) -> str:
    """Render a phrase window with one active word and dimmed neighbors.

    The active word is shown in the style's primary color; every other word in
    the window is wrapped in a secondary-color override (``\\c``) and reset with
    ``\\r`` so the context words appear dimmed.

    Args:
        window: The group of consecutive words forming the context line.
        active_index: Index within ``window`` of the currently spoken word.
        style: Subtitle style (supplies the uppercase flag).
        secondary_override: Pre-computed ``&HBBGGRR&`` value for dimmed words.

    Returns:
        The space-joined ASS dialogue text for this window state.
    """
    parts: list[str] = []
    for idx, word_data in enumerate(window):
        rendered = _render_word(str(word_data["text"]), style.uppercase)
        if idx == active_index:
            parts.append(rendered)
        else:
            parts.append(f"{{\\c{secondary_override}}}{rendered}{{\\r}}")
    return " ".join(parts)


def _emit_window_events(
    window: list[dict],
    style: SubtitleStyle,
    secondary_override: str,
) -> list[pysubs2.SSAEvent]:
    """Build one timed event per active word in a phrase window.

    Each event spans exactly its active word's [start_ms, end_ms] (timing is
    never altered) while displaying the whole window with that word highlighted.

    Args:
        window: The group of consecutive words forming the context line.
        style: Subtitle style configuration.
        secondary_override: Pre-computed ``&HBBGGRR&`` value for dimmed words.

    Returns:
        One SSAEvent per word in the window, in window order.
    """
    events: list[pysubs2.SSAEvent] = []
    for active_index, word_data in enumerate(window):
        event = pysubs2.SSAEvent()
        event.start = int(word_data["start_ms"])
        event.end = int(word_data["end_ms"])
        event.text = _build_window_text(window, active_index, style, secondary_override)
        events.append(event)
    return events


def generate_ass_subtitles(
    words: list[dict],
    style: SubtitleStyle | None = None,
) -> str:
    """Generate ASS subtitle file content with karaoke phrase windows.

    Consecutive words are grouped into context windows of up to ``_WINDOW_SIZE``
    words (spec 9.2). Each active word emits exactly one SSAEvent timed to that
    word's [start_ms, end_ms], displaying the whole window with the active word in
    the primary color and the neighbor words dimmed via inline color overrides.
    Per-word timing is preserved exactly, keeping captions frame-accurately synced.

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
    # Pin the script resolution to the real clip dimensions. Without PlayResX/Y
    # libass falls back to the legacy 384x288 coordinate space, so a MarginV
    # computed for a 1080x1920 clip lands far below the frame and every caption
    # renders off-screen (invisible). 9:16 width derives from the height.
    subs.info["PlayResY"] = str(resolved_style.video_height)
    subs.info["PlayResX"] = str(round(resolved_style.video_height * 9 / 16))
    subs.styles["Default"] = _build_style(resolved_style)

    valid_words, skipped = _collect_valid_words(words)
    secondary_override = _hex_to_ass_override(resolved_style.secondary_color)
    for start in range(0, len(valid_words), _WINDOW_SIZE):
        window = valid_words[start : start + _WINDOW_SIZE]
        subs.events.extend(_emit_window_events(window, resolved_style, secondary_override))

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
