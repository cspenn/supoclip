# start tests/unit/test_subtitles.py
"""Unit tests for src/pipeline/subtitles.py."""

import tempfile
from pathlib import Path

import pysubs2
import pytest

from src.pipeline.subtitles import (
    SubtitleStyle,
    _escape_ass_text,
    _hex_to_ass_override,
    calculate_margin_v,
    generate_ass_subtitles,
    hex_to_bgr_color,
    write_ass_file,
)

# ---------------------------------------------------------------------------
# hex_to_bgr_color
# ---------------------------------------------------------------------------


class TestHexToBgrColor:
    """Tests for hex_to_bgr_color."""

    def test_white(self) -> None:
        """#FFFFFF converts to fully-opaque white."""
        color = hex_to_bgr_color("#FFFFFF")
        assert color.r == 255
        assert color.g == 255
        assert color.b == 255
        assert color.a == 0  # 0 = fully opaque in ASS

    def test_black(self) -> None:
        """#000000 converts to fully-opaque black."""
        color = hex_to_bgr_color("#000000")
        assert color.r == 0
        assert color.g == 0
        assert color.b == 0
        assert color.a == 0

    def test_mixed_color(self) -> None:
        """#FF8800 converts to correct RGB components."""
        color = hex_to_bgr_color("#FF8800")
        assert color.r == 0xFF
        assert color.g == 0x88
        assert color.b == 0x00
        assert color.a == 0

    def test_lowercase_hex(self) -> None:
        """Lowercase hex digits are accepted."""
        color = hex_to_bgr_color("#ff8800")
        assert color.r == 0xFF
        assert color.g == 0x88
        assert color.b == 0x00

    def test_invalid_hex_raises(self) -> None:
        """Non-#RRGGBB strings raise ValueError."""
        with pytest.raises(ValueError):
            hex_to_bgr_color("#FFF")


# ---------------------------------------------------------------------------
# calculate_margin_v
# ---------------------------------------------------------------------------


class TestCalculateMarginV:
    """Tests for calculate_margin_v."""

    def test_75pct_from_top_is_25pct_from_bottom(self) -> None:
        """75% from top = 25% from bottom on a 1920px tall video."""
        margin = calculate_margin_v(75, 1920)
        assert margin == 480  # 1920 * 0.25

    def test_50pct_from_top_is_50pct_from_bottom(self) -> None:
        """50% from top = 50% from bottom."""
        margin = calculate_margin_v(50, 1000)
        assert margin == 500

    def test_100pct_from_top_is_zero_margin(self) -> None:
        """100% from top = 0% from bottom (margin = 0)."""
        margin = calculate_margin_v(100, 1920)
        assert margin == 0

    def test_0pct_from_top_is_full_height_margin(self) -> None:
        """0% from top = 100% from bottom (margin = full height)."""
        margin = calculate_margin_v(0, 1920)
        assert margin == 1920

    def test_result_is_int(self) -> None:
        """Return type is always int."""
        margin = calculate_margin_v(33, 1080)
        assert isinstance(margin, int)


# ---------------------------------------------------------------------------
# generate_ass_subtitles
# ---------------------------------------------------------------------------

_SAMPLE_WORDS = [
    {"text": "Hello", "start_ms": 1000, "end_ms": 1400},
    {"text": "world", "start_ms": 1400, "end_ms": 1900},
    {"text": "foo", "start_ms": 2000, "end_ms": 2500},
]


class TestGenerateAssSubtitles:
    """Tests for generate_ass_subtitles."""

    def test_returns_string(self) -> None:
        """Output is a non-empty string."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_is_parseable_ass(self) -> None:
        """pysubs2 can round-trip the generated content."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == len(_SAMPLE_WORDS)

    def test_timing_preserved(self) -> None:
        """Event start/end times match source word timestamps."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        assert subs.events[0].start == 1000
        assert subs.events[0].end == 1400
        assert subs.events[1].start == 1400
        assert subs.events[1].end == 1900

    def test_font_name_in_output(self) -> None:
        """Custom font family name appears in the .ass output."""
        style = SubtitleStyle(font_family="TikTokSans-Regular")
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        assert "TikTokSans-Regular" in result

    def test_default_style_applied(self) -> None:
        """No style arg uses SubtitleStyle defaults without error."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        assert "Arial" in result  # default font

    def test_uppercase_option(self) -> None:
        """Visible words are uppercased when SubtitleStyle.uppercase is True.

        The override tags (e.g. ``\\c``) are intentionally lowercase, so the
        assertion targets the visible word text via plaintext, which strips the
        ``{...}`` override blocks.
        """
        style = SubtitleStyle(uppercase=True)
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        subs = pysubs2.SSAFile.from_string(result)
        for event in subs.events:
            assert event.plaintext == event.plaintext.upper()
            assert "HELLO" in event.plaintext

    def test_lowercase_unchanged_without_uppercase(self) -> None:
        """Words keep original casing when uppercase=False (default)."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        plaintexts = [e.plaintext for e in subs.events]
        assert any("Hello" in p for p in plaintexts)
        assert any("world" in p for p in plaintexts)

    def test_short_words_skipped(self) -> None:
        """Words with duration < 50ms are omitted from output."""
        words = [
            {"text": "good", "start_ms": 0, "end_ms": 500},
            {"text": "skip", "start_ms": 600, "end_ms": 620},  # 20ms — too short
        ]
        result = generate_ass_subtitles(words)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == 1
        assert subs.events[0].text == "good"

    def test_empty_word_list(self) -> None:
        """Empty word list returns valid (event-free) ASS file."""
        result = generate_ass_subtitles([])
        assert isinstance(result, str)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == 0


def _strip_tags(text: str) -> str:
    """Remove ASS ``{...}`` override blocks, leaving only visible text."""
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Karaoke phrase windows
# ---------------------------------------------------------------------------


class TestKaraokeWindows:
    """Tests for phrase-window (context line) karaoke grouping."""

    def test_one_event_per_word(self) -> None:
        """Each active word still emits exactly one event (sync preserved)."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == len(_SAMPLE_WORDS)

    def test_window_shows_all_neighbor_words(self) -> None:
        """A small word list forms one window: every event shows all words."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        for event in subs.events:
            visible = _strip_tags(event.text)
            assert "Hello" in visible
            assert "world" in visible
            assert "foo" in visible

    def test_active_word_not_dimmed(self) -> None:
        """The active word is rendered without a secondary-color override."""
        style = SubtitleStyle(secondary_color="#888888")
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        subs = pysubs2.SSAFile.from_string(result)
        events = sorted(subs.events, key=lambda e: e.start)
        secondary = _hex_to_ass_override("#888888")
        # First event: "Hello" is active. It must appear NOT wrapped by the dim
        # override, while its neighbors carry the override.
        first = events[0].text
        assert f"{{\\c{secondary}}}Hello" not in first
        assert f"{{\\c{secondary}}}world" in first

    def test_active_word_advances_with_time(self) -> None:
        """The un-dimmed (active) word changes from event to event."""
        style = SubtitleStyle(secondary_color="#888888")
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        subs = pysubs2.SSAFile.from_string(result)
        events = sorted(subs.events, key=lambda e: e.start)
        secondary = _hex_to_ass_override("#888888")
        # Second event: "world" is active (not dimmed), "Hello" is dimmed.
        second = events[1].text
        assert f"{{\\c{secondary}}}world" not in second
        assert f"{{\\c{secondary}}}Hello" in second

    def test_window_splits_beyond_six_words(self) -> None:
        """More than six words split into multiple windows of <=6 words."""
        words = [{"text": f"w{i}", "start_ms": i * 500, "end_ms": i * 500 + 400} for i in range(8)]
        result = generate_ass_subtitles(words)
        subs = pysubs2.SSAFile.from_string(result)
        events = sorted(subs.events, key=lambda e: e.start)
        # 8 words => 8 events (one per active word) across two windows.
        assert len(events) == 8
        # The 7th word starts a new window, so its event must NOT contain w0.
        seventh_visible = _strip_tags(events[6].text)
        assert "w0" not in seventh_visible
        assert "w6" in seventh_visible

    def test_timing_locked_to_active_word(self) -> None:
        """Each event's start/end equal its active word's timing exactly."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        events = sorted(subs.events, key=lambda e: e.start)
        assert (events[0].start, events[0].end) == (1000, 1400)
        assert (events[1].start, events[1].end) == (1400, 1900)
        assert (events[2].start, events[2].end) == (2000, 2500)


# ---------------------------------------------------------------------------
# ASS escaping (S6)
# ---------------------------------------------------------------------------


class TestEscapeAssText:
    """Tests for _escape_ass_text."""

    def test_escapes_braces(self) -> None:
        """Curly braces are backslash-escaped so they cannot open overrides."""
        assert _escape_ass_text("{x}") == "\\{x\\}"

    def test_escapes_backslash(self) -> None:
        """A literal backslash is doubled."""
        assert _escape_ass_text("a\\Nb") == "a\\\\Nb"

    def test_newlines_become_spaces(self) -> None:
        """Real newlines collapse to spaces to keep one dialogue line."""
        assert _escape_ass_text("a\r\nb\nc\rd") == "a b c d"

    def test_plain_text_unchanged(self) -> None:
        """Ordinary text passes through untouched."""
        assert _escape_ass_text("hello") == "hello"


class TestEscapingInEvents:
    """Word text with ASS-special characters cannot corrupt the markup."""

    def test_injection_word_is_escaped(self) -> None:
        """A word like ``{\\an7}`` is neutralized to literal escaped braces."""
        words = [{"text": "{\\an7}X", "start_ms": 0, "end_ms": 500}]
        result = generate_ass_subtitles(words)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == 1
        text = subs.events[0].text
        # The user's brace appears escaped; no bare unescaped user override.
        assert "\\{\\\\an7\\}X" in text
        # Timing is unaffected by escaping.
        assert subs.events[0].start == 0
        assert subs.events[0].end == 500

    def test_escaped_word_keeps_file_parseable(self) -> None:
        """A hostile word does not break round-trip parsing."""
        words = [{"text": "}}}{{{", "start_ms": 0, "end_ms": 500}]
        result = generate_ass_subtitles(words)
        subs = pysubs2.SSAFile.from_string(result)
        assert len(subs.events) == 1


# ---------------------------------------------------------------------------
# _hex_to_ass_override
# ---------------------------------------------------------------------------


class TestHexToAssOverride:
    """Tests for _hex_to_ass_override."""

    def test_reverses_rgb_to_bgr(self) -> None:
        """#RRGGBB maps to the ASS &HBBGGRR& byte order."""
        assert _hex_to_ass_override("#112233") == "&H332211&"

    def test_gray_default(self) -> None:
        """The default secondary gray converts correctly."""
        assert _hex_to_ass_override("#888888") == "&H888888&"

    def test_invalid_raises(self) -> None:
        """Invalid hex raises ValueError (delegated to hex_to_bgr_color)."""
        with pytest.raises(ValueError):
            _hex_to_ass_override("#FFF")


# ---------------------------------------------------------------------------
# SubtitleStyle new fields (bold, secondary_color, shadow back color)
# ---------------------------------------------------------------------------


class TestStyleFields:
    """Tests for bold, secondary_color, and shadow/back color in the style."""

    def test_bold_default_true(self) -> None:
        """The default style is bold."""
        assert SubtitleStyle().bold is True

    def test_secondary_color_default(self) -> None:
        """The default secondary (dim) color is gray."""
        assert SubtitleStyle().secondary_color == "#888888"

    def test_bold_reflected_in_style(self) -> None:
        """Bold flag drives the built SSAStyle bold attribute."""
        result_bold = generate_ass_subtitles(_SAMPLE_WORDS, SubtitleStyle(bold=True))
        result_plain = generate_ass_subtitles(_SAMPLE_WORDS, SubtitleStyle(bold=False))
        assert pysubs2.SSAFile.from_string(result_bold).styles["Default"].bold is True
        assert pysubs2.SSAFile.from_string(result_plain).styles["Default"].bold is False

    def test_shadow_back_color_applied(self) -> None:
        """Outline color is also written as the BackColour (shadow) color."""
        style = SubtitleStyle(outline_color="#123456")
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        subs = pysubs2.SSAFile.from_string(result)
        back = subs.styles["Default"].backcolor
        assert (back.r, back.g, back.b) == (0x12, 0x34, 0x56)

    def test_secondary_color_in_dim_override(self) -> None:
        """A custom secondary color appears as the dim override in output."""
        style = SubtitleStyle(secondary_color="#00FF00")
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        assert _hex_to_ass_override("#00FF00") in result


# ---------------------------------------------------------------------------
# write_ass_file
# ---------------------------------------------------------------------------


class TestWriteAssFile:
    """Tests for write_ass_file."""

    def test_writes_file(self) -> None:
        """File is created at the specified path."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subs.ass"
            result = write_ass_file(_SAMPLE_WORDS, out)
            assert result == out
            assert out.exists()

    def test_file_contains_events(self) -> None:
        """Written file is valid ASS with the expected events."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subs.ass"
            write_ass_file(_SAMPLE_WORDS, out)
            content = out.read_text(encoding="utf-8")
            subs = pysubs2.SSAFile.from_string(content)
            assert len(subs.events) == len(_SAMPLE_WORDS)

    def test_creates_parent_dirs(self) -> None:
        """Intermediate directories are created automatically."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "deep" / "subs.ass"
            write_ass_file(_SAMPLE_WORDS, out)
            assert out.exists()

    def test_accepts_string_path(self) -> None:
        """output_path can be a plain string."""
        with tempfile.TemporaryDirectory() as tmp:
            out_str = str(Path(tmp) / "subs.ass")
            result = write_ass_file(_SAMPLE_WORDS, out_str)
            assert result.exists()

    def test_returns_path_object(self) -> None:
        """Return value is always a Path instance."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subs.ass"
            result = write_ass_file(_SAMPLE_WORDS, out)
            assert isinstance(result, Path)

    def test_custom_style_written(self) -> None:
        """Custom font family is reflected in the written file."""
        style = SubtitleStyle(font_family="Roboto-Bold")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subs.ass"
            write_ass_file(_SAMPLE_WORDS, out, style)
            content = out.read_text(encoding="utf-8")
            assert "Roboto-Bold" in content


# end tests/unit/test_subtitles.py
