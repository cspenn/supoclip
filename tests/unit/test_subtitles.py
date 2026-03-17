# start tests/unit/test_subtitles.py
"""Unit tests for src/pipeline/subtitles.py."""

import tempfile
from pathlib import Path

import pysubs2
import pytest

from src.pipeline.subtitles import (
    SubtitleStyle,
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
        """Words are uppercased when SubtitleStyle.uppercase is True."""
        style = SubtitleStyle(uppercase=True)
        result = generate_ass_subtitles(_SAMPLE_WORDS, style)
        subs = pysubs2.SSAFile.from_string(result)
        for event in subs.events:
            assert event.text == event.text.upper()

    def test_lowercase_unchanged_without_uppercase(self) -> None:
        """Words are not modified when uppercase=False (default)."""
        result = generate_ass_subtitles(_SAMPLE_WORDS)
        subs = pysubs2.SSAFile.from_string(result)
        texts = [e.text for e in subs.events]
        assert "Hello" in texts
        assert "world" in texts

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
