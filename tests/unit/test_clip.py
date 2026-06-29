# start tests/unit/test_clip.py
"""Unit tests for src/pipeline/clip.py."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import ClipGenerationError
from src.pipeline.clip import (
    ClipOptions,
    TranscriptSegment,
    _find_fonts_dir,
    _get_video_dimensions,
    _parse_ffprobe_dimensions,
    _prepend_transition,
    _probe_duration,
    _probe_video_fps,
    _resolve_face_center,
    _resolve_transition,
    _run_ffmpeg,
    _run_ffprobe,
    _side_face_center,
    _video_has_audio,
    build_concat_command,
    build_ffmpeg_command,
    filter_words_for_segment,
    generate_clip,
)
from src.pipeline.subtitles import SubtitleStyle


class TestActiveSpeakerFraming:
    """Tests for side-biased crop focus (duo/multi active-speaker framing)."""

    def test_side_face_center_left_right_center(self) -> None:
        """Each side maps to its horizontal focus fraction at mid-height."""
        assert _side_face_center("left", 1920, 1080) == (480, 540)
        assert _side_face_center("right", 1920, 1080) == (1440, 540)
        assert _side_face_center("center", 1920, 1080) == (960, 540)

    def test_side_face_center_unknown_returns_none(self) -> None:
        """An unrecognized side returns None so the caller falls back."""
        assert _side_face_center("top", 1920, 1080) is None

    def test_resolve_face_center_uses_side_when_set(self) -> None:
        """An active_speaker_side biases the focus without face detection."""
        seg = TranscriptSegment(start_s=0.0, end_s=2.0)
        opts = ClipOptions(active_speaker_side="right")
        with patch("src.pipeline.clip.detect_face_center") as mock_detect:
            center = _resolve_face_center(Path("/v.mp4"), seg, opts, 1920, 1080)
        assert center == (1440, 540)
        mock_detect.assert_not_called()

    def test_resolve_face_center_falls_back_to_detection(self) -> None:
        """Without a side, it face-detects a representative frame."""
        seg = TranscriptSegment(start_s=5.0, end_s=8.0)
        opts = ClipOptions(active_speaker_side=None)
        with (
            patch("src.pipeline.clip.get_representative_frame", return_value="frame"),
            patch("src.pipeline.clip.detect_face_center", return_value=(100, 200)) as mock_detect,
        ):
            center = _resolve_face_center(Path("/v.mp4"), seg, opts, 1920, 1080)
        assert center == (100, 200)
        mock_detect.assert_called_once()

    def test_resolve_face_center_unknown_side_falls_back(self) -> None:
        """An unrecognized side still falls through to face detection."""
        seg = TranscriptSegment(start_s=0.0, end_s=2.0)
        opts = ClipOptions(active_speaker_side="bogus")
        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
        ):
            assert _resolve_face_center(Path("/v.mp4"), seg, opts, 1920, 1080) is None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_WORDS: list[dict] = [
    {"text": "Hello", "start_ms": 10000, "end_ms": 10400},
    {"text": "world", "start_ms": 10400, "end_ms": 10900},
    {"text": "foo", "start_ms": 20000, "end_ms": 20500},
    {"text": "bar", "start_ms": 30000, "end_ms": 30500},
]


# ---------------------------------------------------------------------------
# filter_words_for_segment
# ---------------------------------------------------------------------------


class TestFilterWordsForSegment:
    """Tests for filter_words_for_segment."""

    def test_includes_words_within_range(self) -> None:
        """Words whose midpoint falls in [start_s, end_s] are kept."""
        result = filter_words_for_segment(_SAMPLE_WORDS, start_s=10.0, end_s=15.0)
        texts = [w["text"] for w in result]
        assert "Hello" in texts
        assert "world" in texts

    def test_excludes_words_outside_range(self) -> None:
        """Words outside the segment are not included."""
        result = filter_words_for_segment(_SAMPLE_WORDS, start_s=10.0, end_s=15.0)
        texts = [w["text"] for w in result]
        assert "foo" not in texts
        assert "bar" not in texts

    def test_timestamps_adjusted_relative_to_start(self) -> None:
        """start_ms values are offset to be relative to segment start."""
        result = filter_words_for_segment(_SAMPLE_WORDS, start_s=10.0, end_s=15.0)
        # "Hello" at 10000 ms absolute; segment starts at 10000 ms → should be 0
        hello = next(w for w in result if w["text"] == "Hello")
        assert hello["start_ms"] == 0
        assert hello["end_ms"] == 400

    def test_world_timestamp_adjusted(self) -> None:
        """Second word timestamps are also relative to segment start."""
        result = filter_words_for_segment(_SAMPLE_WORDS, start_s=10.0, end_s=15.0)
        world = next(w for w in result if w["text"] == "world")
        assert world["start_ms"] == 400
        assert world["end_ms"] == 900

    def test_empty_word_list_returns_empty(self) -> None:
        """Empty input produces empty output."""
        result = filter_words_for_segment([], 0.0, 60.0)
        assert result == []

    def test_no_words_in_range_returns_empty(self) -> None:
        """When no words fall in range, result is empty."""
        result = filter_words_for_segment(_SAMPLE_WORDS, start_s=50.0, end_s=55.0)
        assert result == []

    def test_original_words_not_mutated(self) -> None:
        """Original word dicts are not modified in place."""
        original_start = _SAMPLE_WORDS[0]["start_ms"]
        filter_words_for_segment(_SAMPLE_WORDS, 10.0, 15.0)
        assert _SAMPLE_WORDS[0]["start_ms"] == original_start

    def test_start_ms_never_negative(self) -> None:
        """Adjusted timestamps are clamped to zero."""
        # Word starts exactly at segment start — offset yields 0 not negative.
        words = [{"text": "hi", "start_ms": 5000, "end_ms": 5500}]
        result = filter_words_for_segment(words, 5.2, 10.0)
        # midpoint = 5250 ms, which is within [5200, 10000]
        assert result[0]["start_ms"] >= 0
        assert result[0]["end_ms"] >= 0

    def test_full_segment_words_included(self) -> None:
        """All words in the full range of sample words are returned."""
        result = filter_words_for_segment(_SAMPLE_WORDS, 0.0, 60.0)
        assert len(result) == len(_SAMPLE_WORDS)


# ---------------------------------------------------------------------------
# build_ffmpeg_command
# ---------------------------------------------------------------------------


class TestBuildFfmpegCommand:
    """Tests for build_ffmpeg_command."""

    def _base_cmd(self, **kwargs) -> list[str]:  # type: ignore[no-untyped-def]
        defaults = dict(
            input_path="/src/video.mp4",
            output_path="/out/clip.mp4",
            start_s=10.0,
            end_s=40.0,
            crop_box=(0, 0, 607, 1080),
            out_width=1080,
            out_height=1920,
        )
        defaults.update(kwargs)
        return build_ffmpeg_command(**defaults)  # type: ignore[arg-type]

    def test_starts_with_ffmpeg(self) -> None:
        """Command must start with 'ffmpeg'."""
        assert self._base_cmd()[0] == "ffmpeg"

    def test_overwrite_flag_present(self) -> None:
        """-y flag is present to allow overwriting output."""
        assert "-y" in self._base_cmd()

    def test_seek_before_input(self) -> None:
        """-ss appears before -i in the command."""
        cmd = self._base_cmd()
        ss_idx = cmd.index("-ss")
        i_idx = cmd.index("-i")
        assert ss_idx < i_idx

    def test_start_time_value(self) -> None:
        """-ss value matches start_s."""
        cmd = self._base_cmd(start_s=15.5)
        ss_val = cmd[cmd.index("-ss") + 1]
        assert float(ss_val) == pytest.approx(15.5)

    def test_duration_not_end_time(self) -> None:
        """-to value is duration (end_s - start_s), not the absolute end time."""
        cmd = self._base_cmd(start_s=10.0, end_s=40.0)
        to_val = float(cmd[cmd.index("-to") + 1])
        assert to_val == pytest.approx(30.0)

    def test_input_path_present(self) -> None:
        """Input video path follows -i."""
        cmd = self._base_cmd(input_path="/videos/source.mp4")
        i_idx = cmd.index("-i")
        assert cmd[i_idx + 1] == "/videos/source.mp4"

    def test_output_path_is_last_argument(self) -> None:
        """Output path is the last element of the command."""
        cmd = self._base_cmd(output_path="/out/result.mp4")
        assert cmd[-1] == "/out/result.mp4"

    def test_video_codec_libx264(self) -> None:
        """Video codec is set to libx264."""
        cmd = self._base_cmd()
        assert cmd[cmd.index("-c:v") + 1] == "libx264"

    def test_audio_codec_aac(self) -> None:
        """Audio codec is set to aac."""
        cmd = self._base_cmd()
        assert cmd[cmd.index("-c:a") + 1] == "aac"

    def test_movflags_faststart(self) -> None:
        """+faststart movflags are present for streaming-friendly output."""
        cmd = self._base_cmd()
        assert "+faststart" in cmd

    def test_crop_in_vf_without_ass(self) -> None:
        """Video filter includes crop and scale, no ass filter when ass_path=None."""
        cmd = self._base_cmd(crop_box=(10, 20, 607, 1080))
        vf = cmd[cmd.index("-vf") + 1]
        assert "crop=607:1080:10:20" in vf
        assert "scale=1080:1920" in vf
        assert "ass=" not in vf

    def test_vf_with_ass_path(self) -> None:
        """When ass_path is provided, ass= filter is appended to -vf chain."""
        cmd = self._base_cmd(ass_path="/tmp/subs.ass")
        vf = cmd[cmd.index("-vf") + 1]
        assert "ass=/tmp/subs.ass" in vf

    def test_vf_with_ass_and_fonts_dir(self) -> None:
        """When both ass_path and fonts_dir are given, fontsdir= is appended."""
        cmd = self._base_cmd(ass_path="/tmp/subs.ass", fonts_dir="/fonts")
        vf = cmd[cmd.index("-vf") + 1]
        assert "ass=/tmp/subs.ass:fontsdir=/fonts" in vf

    def test_vf_without_ass_no_fontsdir(self) -> None:
        """fonts_dir alone (without ass_path) does not add any subtitle filter."""
        cmd = self._base_cmd(fonts_dir="/fonts")
        vf = cmd[cmd.index("-vf") + 1]
        assert "ass=" not in vf
        assert "fontsdir" not in vf

    def test_returns_list_of_strings(self) -> None:
        """All elements must be plain str, not Path objects."""
        cmd = self._base_cmd()
        for arg in cmd:
            assert isinstance(arg, str)

    def test_path_objects_converted_to_str(self) -> None:
        """Path objects for input/output are stringified."""
        cmd = build_ffmpeg_command(
            input_path=Path("/src/video.mp4"),
            output_path=Path("/out/clip.mp4"),
            start_s=0.0,
            end_s=10.0,
            crop_box=(0, 0, 608, 1080),
            out_width=1080,
            out_height=1920,
        )
        i_idx = cmd.index("-i")
        assert cmd[i_idx + 1] == "/src/video.mp4"
        assert cmd[-1] == "/out/clip.mp4"

    def test_no_fade_filter_emitted(self) -> None:
        """The crop/scale chain carries no fade filter (transitions mux content)."""
        cmd = self._base_cmd()
        vf = cmd[cmd.index("-vf") + 1]
        assert "fade=" not in vf

    # ---- logo overlay (M-4) ----

    def test_logo_uses_filter_complex_not_vf(self) -> None:
        """With a logo, the command switches to -filter_complex and a 2nd input."""
        cmd = self._base_cmd(logo_path="/brand/logo.png")
        assert "-filter_complex" in cmd
        assert "-vf" not in cmd
        # Two -i inputs: source then logo.
        assert cmd.count("-i") == 2
        i_indices = [j for j, a in enumerate(cmd) if a == "-i"]
        assert cmd[i_indices[1] + 1] == "/brand/logo.png"

    def test_logo_maps_video_and_optional_audio(self) -> None:
        """The overlaid video [vout] and optional source audio are mapped."""
        cmd = self._base_cmd(logo_path="/brand/logo.png")
        assert "-map" in cmd
        assert "[vout]" in cmd
        assert "0:a?" in cmd

    def test_logo_overlay_graph_top_right_and_scaled(self) -> None:
        """Logo is scaled to ~18% of out_width and overlaid at top-right."""
        cmd = self._base_cmd(logo_path="/brand/logo.png", out_width=1000)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "scale=180:-1" in graph  # 0.18 * 1000
        assert "overlay=main_w-overlay_w-20:20" in graph

    def test_logo_base_chain_includes_crop_scale_and_ass(self) -> None:
        """The overlay base chain still carries crop, scale and the ass burn-in."""
        cmd = self._base_cmd(logo_path="/brand/logo.png", ass_path="/tmp/subs.ass")
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "crop=607:1080:0:0" in graph
        assert "scale=1080:1920" in graph
        assert "ass=/tmp/subs.ass" in graph
        assert "[base]" in graph


# ---------------------------------------------------------------------------
# generate_clip — mocked ffmpeg
# ---------------------------------------------------------------------------


class TestGenerateClip:
    """Tests for generate_clip using mocked subprocess."""

    def _make_segment(self, start_s: float = 10.0, end_s: float = 40.0) -> TranscriptSegment:
        return TranscriptSegment(start_s=start_s, end_s=end_s, text="test segment")

    def _success_proc(self) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = 0
        proc.stderr = b""
        return proc

    def _failure_proc(self, exit_code: int = 1) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = exit_code
        proc.stderr = b"error: invalid input\n"
        return proc

    @pytest.mark.asyncio
    async def test_returns_output_path_on_success(self, tmp_path: Path) -> None:
        """generate_clip returns a Path to the output file when ffmpeg succeeds."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._success_proc()),
        ):
            result = await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
            )

        assert result == out

    @pytest.mark.asyncio
    async def test_raises_on_ffmpeg_failure(self, tmp_path: Path) -> None:
        """ClipGenerationError is raised when ffmpeg returns non-zero exit code."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._failure_proc(1)),
            pytest.raises(ClipGenerationError),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
            )

    @pytest.mark.asyncio
    async def test_error_message_includes_ffmpeg_stderr(self, tmp_path: Path) -> None:
        """ClipGenerationError message contains the ffmpeg stderr output."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()
        failure = self._failure_proc(1)
        failure.stderr = b"error: codec not found"

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", return_value=failure),
            pytest.raises(ClipGenerationError, match="codec not found"),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
            )

    @pytest.mark.asyncio
    async def test_subtitles_written_when_style_provided(self, tmp_path: Path) -> None:
        """write_ass_file is called when subtitle_style is set in ClipOptions."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment(start_s=10.0, end_s=15.0)
        words = [
            {"text": "Hi", "start_ms": 10100, "end_ms": 10500},
        ]
        opts = ClipOptions(subtitle_style=SubtitleStyle())

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip.write_ass_file") as mock_write_ass,
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._success_proc()),
        ):
            mock_write_ass.return_value = tmp_path / "clip.ass"
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=words,
                output_path=out,
                options=opts,
            )

        mock_write_ass.assert_called_once()

    @pytest.mark.asyncio
    async def test_subtitles_not_written_when_no_style(self, tmp_path: Path) -> None:
        """write_ass_file is NOT called when subtitle_style is None."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip.write_ass_file") as mock_write_ass,
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._success_proc()),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
                options=ClipOptions(subtitle_style=None),
            )

        mock_write_ass.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_ass_when_style_set_but_no_words_in_segment(self, tmp_path: Path) -> None:
        """With a style but zero words overlapping the segment, no .ass is written."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment(start_s=10.0, end_s=15.0)
        # Word sits far outside the segment window, so filtering yields nothing.
        words = [{"text": "later", "start_ms": 90000, "end_ms": 90500}]

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip.write_ass_file") as mock_write_ass,
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._success_proc()),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=words,
                output_path=out,
                options=ClipOptions(subtitle_style=SubtitleStyle()),
            )

        mock_write_ass.assert_not_called()

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_raises(self, tmp_path: Path) -> None:
        """Any non-zero return code (e.g. 2, 127) raises ClipGenerationError."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()

        for exit_code in (2, 127, -1):
            with (
                patch("src.pipeline.clip.get_representative_frame", return_value=None),
                patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
                patch("src.pipeline.clip._find_fonts_dir", return_value=None),
                patch(
                    "src.pipeline.clip._run_ffmpeg",
                    return_value=self._failure_proc(exit_code),
                ),
                pytest.raises(ClipGenerationError),
            ):
                await generate_clip(
                    source_video="/fake/video.mp4",
                    segment=segment,
                    words=[],
                    output_path=out,
                )

    @pytest.mark.asyncio
    async def test_logo_passed_through_when_file_exists(self, tmp_path: Path) -> None:
        """An existing logo file flows into the ffmpeg command as an overlay."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()
        logo = Path(__file__).parent.parent / "fixtures" / "sample_logo.png"
        assert logo.exists()
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
                options=ClipOptions(logo_path=logo),
            )

        cmd = captured["cmd"]
        assert "-filter_complex" in cmd
        assert str(logo) in cmd

    @pytest.mark.asyncio
    async def test_logo_skipped_when_file_missing(self, tmp_path: Path) -> None:
        """A non-existent logo path is ignored; the simple -vf path is used."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
                options=ClipOptions(logo_path=tmp_path / "missing_logo.png"),
            )

        cmd = captured["cmd"]
        assert "-vf" in cmd
        assert "-filter_complex" not in cmd

    @pytest.mark.asyncio
    async def test_output_parent_dirs_created(self, tmp_path: Path) -> None:
        """Nested output directories are created automatically."""
        out = tmp_path / "nested" / "deep" / "clip.mp4"
        segment = self._make_segment()

        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._success_proc()),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
            )

        assert out.parent.exists()


# ---------------------------------------------------------------------------
# TranscriptSegment dataclass
# ---------------------------------------------------------------------------


class TestTranscriptSegment:
    """Sanity tests for the TranscriptSegment dataclass."""

    def test_required_fields(self) -> None:
        """start_s and end_s are mandatory positional fields."""
        seg = TranscriptSegment(start_s=5.0, end_s=30.0)
        assert seg.start_s == 5.0
        assert seg.end_s == 30.0

    def test_defaults(self) -> None:
        """Optional fields default correctly."""
        seg = TranscriptSegment(start_s=0.0, end_s=10.0)
        assert seg.text == ""
        assert seg.relevance_score == 1.0
        assert seg.reasoning == ""

    def test_slots_prevents_dynamic_attributes(self) -> None:
        """slots=True prevents arbitrary attribute assignment."""
        seg = TranscriptSegment(start_s=0.0, end_s=10.0)
        with pytest.raises(AttributeError):
            seg.new_field = "unexpected"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _run_ffmpeg — line 371
# ---------------------------------------------------------------------------


class TestRunFfmpeg:
    """Tests for the _run_ffmpeg private helper."""

    def test_calls_subprocess_run_and_returns_result(self) -> None:
        """_run_ffmpeg delegates to subprocess.run and returns its result."""
        fake_proc = MagicMock(spec=subprocess.CompletedProcess)
        fake_proc.returncode = 0
        fake_proc.stderr = b""

        with patch("subprocess.run", return_value=fake_proc) as mock_run:
            result = _run_ffmpeg(["ffmpeg", "-version"])

        mock_run.assert_called_once_with(
            ["ffmpeg", "-version"],
            shell=False,
            capture_output=True,
            check=False,
            timeout=300,
        )
        assert result is fake_proc

    def test_timeout_raises_clip_generation_error(self) -> None:
        """A ffmpeg timeout is converted into a loud ClipGenerationError (M-3)."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=300),
            ),
            pytest.raises(ClipGenerationError, match="timed out"),
        ):
            _run_ffmpeg(["ffmpeg", "-i", "in.mp4", "out.mp4"])


# ---------------------------------------------------------------------------
# _parse_ffprobe_dimensions
# ---------------------------------------------------------------------------


class TestParseFfprobeDimensions:
    """Tests for parsing ffprobe JSON into (width, height)."""

    def test_parses_valid_json(self) -> None:
        """Well-formed ffprobe JSON yields the integer dimensions."""
        out = b'{"streams":[{"width":1280,"height":720}]}'
        assert _parse_ffprobe_dimensions(out) == (1280, 720)

    def test_raises_on_malformed_json(self) -> None:
        """Non-JSON output fails loudly with ClipGenerationError."""
        with pytest.raises(ClipGenerationError):
            _parse_ffprobe_dimensions(b"not json at all")

    def test_raises_on_empty_streams(self) -> None:
        """An empty streams array (no video stream) fails loudly."""
        with pytest.raises(ClipGenerationError):
            _parse_ffprobe_dimensions(b'{"streams":[]}')

    def test_raises_on_missing_keys(self) -> None:
        """Missing width/height keys fail loudly."""
        with pytest.raises(ClipGenerationError):
            _parse_ffprobe_dimensions(b'{"streams":[{"width":1280}]}')

    def test_raises_on_zero_dimensions(self) -> None:
        """Zero dimensions are rejected (no silent bad crop)."""
        with pytest.raises(ClipGenerationError):
            _parse_ffprobe_dimensions(b'{"streams":[{"width":0,"height":0}]}')


# ---------------------------------------------------------------------------
# _get_video_dimensions — ffprobe-backed
# ---------------------------------------------------------------------------


class TestGetVideoDimensions:
    """Tests for the ffprobe-backed _get_video_dimensions helper."""

    def _proc(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    def test_returns_dimensions_from_ffprobe(self, tmp_path: Path) -> None:
        """Parses (width, height) from a successful ffprobe call."""
        video = tmp_path / "video.mp4"
        video.touch()
        proc = self._proc(0, stdout=b'{"streams":[{"width":640,"height":480}]}')

        with patch("subprocess.run", return_value=proc):
            assert _get_video_dimensions(video) == (640, 480)

    def test_raises_when_ffprobe_nonzero(self, tmp_path: Path) -> None:
        """A non-zero ffprobe exit raises ClipGenerationError (no fallback)."""
        video = tmp_path / "video.mp4"
        video.touch()
        proc = self._proc(1, stderr=b"corrupt file")

        with (
            patch("subprocess.run", return_value=proc),
            pytest.raises(ClipGenerationError, match="ffprobe failed"),
        ):
            _get_video_dimensions(video)

    def test_raises_when_ffprobe_not_installed(self, tmp_path: Path) -> None:
        """A missing ffprobe binary raises ClipGenerationError."""
        video = tmp_path / "video.mp4"
        video.touch()

        with (
            patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe")),
            pytest.raises(ClipGenerationError, match="could not be executed"),
        ):
            _get_video_dimensions(video)

    @pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not installed")
    def test_real_sample_video_dimensions(self) -> None:
        """The committed fixture is a real 720x1280 portrait clip."""
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"
        assert _get_video_dimensions(fixture) == (720, 1280)


# ---------------------------------------------------------------------------
# _find_fonts_dir — lines 423-429
# ---------------------------------------------------------------------------


class TestFindFontsDir:
    """Tests for _find_fonts_dir private helper."""

    def test_returns_none_when_no_fonts_dir_exists(self, tmp_path: Path) -> None:
        """Returns None when no 'fonts' directory is found within 6 levels."""
        # Use a deeply nested fake path with no fonts/ anywhere
        fake_file = tmp_path / "a" / "b" / "c" / "clip.py"
        fake_file.parent.mkdir(parents=True)
        fake_file.touch()

        with patch("src.pipeline.clip.__file__", str(fake_file)):
            result = _find_fonts_dir()

        assert result is None

    def test_returns_fonts_dir_when_present(self, tmp_path: Path) -> None:
        """Returns Path to fonts/ directory when found in the ancestor tree."""
        # Create structure: tmp_path/src/pipeline/clip.py and tmp_path/fonts/
        pipeline_dir = tmp_path / "src" / "pipeline"
        pipeline_dir.mkdir(parents=True)
        fake_file = pipeline_dir / "clip.py"
        fake_file.touch()

        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()

        with patch("src.pipeline.clip.__file__", str(fake_file)):
            result = _find_fonts_dir()

        assert result == fonts_dir


# ---------------------------------------------------------------------------
# build_concat_command — transition muxing
# ---------------------------------------------------------------------------


class TestBuildConcatCommand:
    """Tests for the transition+main concat command builder."""

    def _cmd(self, **kwargs) -> list[str]:  # type: ignore[no-untyped-def]
        defaults = dict(
            transition_path="/t/trans.mp4",
            main_path="/c/clip.main.mp4",
            output_path="/c/clip.mp4",
            out_width=720,
            out_height=1280,
            fps=24.0,
            transition_silence_s=None,
            main_silence_s=None,
        )
        defaults.update(kwargs)
        return build_concat_command(**defaults)  # type: ignore[arg-type]

    def test_two_inputs_transition_then_main(self) -> None:
        """The first two -i inputs are the transition then the main clip."""
        cmd = self._cmd()
        i_indices = [j for j, a in enumerate(cmd) if a == "-i"]
        assert cmd[i_indices[0] + 1] == "/t/trans.mp4"
        assert cmd[i_indices[1] + 1] == "/c/clip.main.mp4"

    def test_output_is_last_argument(self) -> None:
        """The destination path is the final argument."""
        assert self._cmd(output_path="/c/final.mp4")[-1] == "/c/final.mp4"

    def test_normalises_transition_to_main_geometry(self) -> None:
        """The transition is scaled to WxH, given square SAR, fps and yuv420p."""
        cmd = self._cmd(out_width=1080, out_height=1920, fps=30.0)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "[0:v]scale=1080:1920,setsar=1,fps=30.0,format=yuv420p[tv]" in graph
        assert "[1:v]setsar=1,format=yuv420p[mv]" in graph
        assert "concat=n=2:v=1:a=1[v][a]" in graph

    def test_maps_concatenated_streams(self) -> None:
        """The concatenated video and audio outputs are explicitly mapped."""
        cmd = self._cmd()
        assert "-map" in cmd
        assert "[v]" in cmd
        assert "[a]" in cmd

    def test_real_audio_used_when_no_silence(self) -> None:
        """With both silence durations None, the source audio streams are used."""
        cmd = self._cmd(transition_silence_s=None, main_silence_s=None)
        graph = cmd[cmd.index("-filter_complex") + 1]
        # No extra lavfi silent inputs beyond the two real videos.
        assert "anullsrc" not in cmd
        assert "[tv][0:a][mv][1:a]concat" in graph

    def test_silent_audio_synthesised_for_both_when_requested(self) -> None:
        """When both clips lack audio, two silent lavfi inputs are appended."""
        cmd = self._cmd(transition_silence_s=0.5, main_silence_s=2.0)
        # Two extra lavfi inputs (inputs 2 and 3).
        assert cmd.count("lavfi") == 2
        assert cmd.count("anullsrc=channel_layout=stereo:sample_rate=44100") == 2
        # Durations are bound to the correct inputs.
        assert "-t" in cmd
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "[tv][2:a][mv][3:a]concat" in graph

    def test_silent_transition_real_main_audio(self) -> None:
        """A silent transition + audio-bearing main uses input 2 then main's 1:a."""
        cmd = self._cmd(transition_silence_s=0.5, main_silence_s=None)
        assert cmd.count("lavfi") == 1
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "[tv][2:a][mv][1:a]concat" in graph


# ---------------------------------------------------------------------------
# _resolve_transition
# ---------------------------------------------------------------------------


class TestResolveTransition:
    """Tests for resolving a configured transition path."""

    def test_none_returns_none(self) -> None:
        """An unset transition path resolves to None."""
        assert _resolve_transition(None) is None

    def test_existing_file_returns_path(self, tmp_path: Path) -> None:
        """An existing transition file resolves to its Path."""
        trans = tmp_path / "swoosh.mp4"
        trans.touch()
        assert _resolve_transition(trans) == trans

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """A configured-but-missing transition file resolves to None (no-op)."""
        assert _resolve_transition(tmp_path / "missing.mp4") is None


# ---------------------------------------------------------------------------
# ffprobe-backed probe helpers
# ---------------------------------------------------------------------------


class TestRunFfprobe:
    """Tests for the shared _run_ffprobe error-handling helper."""

    def _proc(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    def test_returns_stdout_on_success(self) -> None:
        """A zero-exit ffprobe returns its stdout bytes."""
        with patch("subprocess.run", return_value=self._proc(0, stdout=b"data")):
            assert _run_ffprobe(["ffprobe", "-version"]) == b"data"

    def test_raises_on_nonzero_exit(self) -> None:
        """A non-zero ffprobe exit fails loudly."""
        with (
            patch("subprocess.run", return_value=self._proc(1, stderr=b"boom")),
            pytest.raises(ClipGenerationError, match="ffprobe failed"),
        ):
            _run_ffprobe(["ffprobe", "x"])

    def test_raises_when_not_installed(self) -> None:
        """A missing ffprobe binary fails loudly."""
        with (
            patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe")),
            pytest.raises(ClipGenerationError, match="could not be executed"),
        ):
            _run_ffprobe(["ffprobe", "x"])


class TestProbeDuration:
    """Tests for _probe_duration parsing."""

    def test_parses_duration(self, tmp_path: Path) -> None:
        """Well-formed ffprobe output yields a float duration."""
        with patch("src.pipeline.clip._run_ffprobe", return_value=b"2.500000\n"):
            assert _probe_duration(tmp_path / "v.mp4") == pytest.approx(2.5)

    def test_raises_on_unparseable_duration(self, tmp_path: Path) -> None:
        """Non-numeric duration output fails loudly."""
        with (
            patch("src.pipeline.clip._run_ffprobe", return_value=b"N/A"),
            pytest.raises(ClipGenerationError, match="could not parse ffprobe duration"),
        ):
            _probe_duration(tmp_path / "v.mp4")


class TestVideoHasAudio:
    """Tests for _video_has_audio detection."""

    def test_true_when_audio_stream_present(self, tmp_path: Path) -> None:
        """Non-empty ffprobe output means an audio stream exists."""
        with patch("src.pipeline.clip._run_ffprobe", return_value=b"1\n"):
            assert _video_has_audio(tmp_path / "v.mp4") is True

    def test_false_when_no_audio_stream(self, tmp_path: Path) -> None:
        """Empty ffprobe output means no audio stream."""
        with patch("src.pipeline.clip._run_ffprobe", return_value=b"\n"):
            assert _video_has_audio(tmp_path / "v.mp4") is False


class TestProbeVideoFps:
    """Tests for _probe_video_fps parsing of r_frame_rate."""

    def test_parses_rational(self, tmp_path: Path) -> None:
        """A num/den rational is divided into frames per second."""
        with patch("src.pipeline.clip._run_ffprobe", return_value=b"24/1\n"):
            assert _probe_video_fps(tmp_path / "v.mp4") == pytest.approx(24.0)

    def test_parses_bare_integer(self, tmp_path: Path) -> None:
        """A value with no denominator is treated as /1."""
        with patch("src.pipeline.clip._run_ffprobe", return_value=b"30\n"):
            assert _probe_video_fps(tmp_path / "v.mp4") == pytest.approx(30.0)

    def test_raises_on_unparseable_fps(self, tmp_path: Path) -> None:
        """A non-numeric rational fails loudly."""
        with (
            patch("src.pipeline.clip._run_ffprobe", return_value=b"x/y"),
            pytest.raises(ClipGenerationError, match="could not parse ffprobe fps"),
        ):
            _probe_video_fps(tmp_path / "v.mp4")

    def test_raises_on_zero_denominator(self, tmp_path: Path) -> None:
        """A zero denominator (e.g. 0/0) fails loudly instead of dividing by zero."""
        with (
            patch("src.pipeline.clip._run_ffprobe", return_value=b"24/0"),
            pytest.raises(ClipGenerationError, match="zero fps denominator"),
        ):
            _probe_video_fps(tmp_path / "v.mp4")


# ---------------------------------------------------------------------------
# _prepend_transition — concat orchestration
# ---------------------------------------------------------------------------


class TestPrependTransition:
    """Tests for the _prepend_transition concat orchestrator."""

    def _success_proc(self) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = 0
        proc.stderr = b""
        return proc

    def _failure_proc(self) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = 1
        proc.stderr = b"concat blew up"
        return proc

    def test_silent_branch_probes_durations_and_unlinks(self, tmp_path: Path) -> None:
        """When both clips lack audio, durations are probed and the main removed."""
        transition = tmp_path / "trans.mp4"
        transition.touch()
        main = tmp_path / "clip.main.mp4"
        main.touch()
        out = tmp_path / "clip.mp4"
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        with (
            patch("src.pipeline.clip._probe_video_fps", return_value=24.0),
            patch("src.pipeline.clip._video_has_audio", side_effect=[False, False]),
            patch("src.pipeline.clip._probe_duration", side_effect=[0.5, 2.0]) as mock_dur,
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
        ):
            _prepend_transition(transition, main, out, 720, 1280)

        assert mock_dur.call_count == 2
        # Two synthesised silent inputs (both clips lacked audio).
        assert captured["cmd"].count("lavfi") == 2
        assert not main.exists(), "intermediate main clip should be removed"

    def test_audio_branch_skips_duration_probe(self, tmp_path: Path) -> None:
        """When both clips have audio, no silence durations are probed."""
        transition = tmp_path / "trans.mp4"
        transition.touch()
        main = tmp_path / "clip.main.mp4"
        main.touch()
        out = tmp_path / "clip.mp4"
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        with (
            patch("src.pipeline.clip._probe_video_fps", return_value=24.0),
            patch("src.pipeline.clip._video_has_audio", side_effect=[True, True]),
            patch("src.pipeline.clip._probe_duration") as mock_dur,
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
        ):
            _prepend_transition(transition, main, out, 720, 1280)

        mock_dur.assert_not_called()
        assert "lavfi" not in captured["cmd"]

    def test_failure_raises_and_still_unlinks(self, tmp_path: Path) -> None:
        """A non-zero concat exit raises ClipGenerationError and removes the main."""
        transition = tmp_path / "trans.mp4"
        transition.touch()
        main = tmp_path / "clip.main.mp4"
        main.touch()
        out = tmp_path / "clip.mp4"

        with (
            patch("src.pipeline.clip._probe_video_fps", return_value=24.0),
            patch("src.pipeline.clip._video_has_audio", side_effect=[True, True]),
            patch("src.pipeline.clip._run_ffmpeg", return_value=self._failure_proc()),
            pytest.raises(ClipGenerationError, match="transition concat failed"),
        ):
            _prepend_transition(transition, main, out, 720, 1280)

        assert not main.exists(), "intermediate main clip should be removed even on failure"


# ---------------------------------------------------------------------------
# generate_clip — transition wiring
# ---------------------------------------------------------------------------


class TestGenerateClipTransition:
    """Tests for the transition branch of generate_clip."""

    def _make_segment(self, start_s: float = 10.0, end_s: float = 40.0) -> TranscriptSegment:
        return TranscriptSegment(start_s=start_s, end_s=end_s, text="test segment")

    def _success_proc(self) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        proc = MagicMock(spec=subprocess.CompletedProcess)
        proc.returncode = 0
        proc.stderr = b""
        return proc

    @pytest.mark.asyncio
    async def test_transition_renders_main_intermediate_then_muxes(self, tmp_path: Path) -> None:
        """An existing transition renders to a .main intermediate then is prepended."""
        out = tmp_path / "clip.mp4"
        transition = tmp_path / "swoosh.mp4"
        transition.touch()
        segment = self._make_segment()
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        mux = MagicMock()
        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
            patch("src.pipeline.clip._prepend_transition", mux),
        ):
            result = await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
                options=ClipOptions(transition_path=transition),
            )

        assert result == out
        # The main pass writes to the intermediate file, not the final output.
        intermediate = tmp_path / "clip.main.mp4"
        assert captured["cmd"][-1] == str(intermediate)
        mux.assert_called_once_with(transition, intermediate, out, 1080, 1920)

    @pytest.mark.asyncio
    async def test_missing_transition_is_single_pass_no_op(self, tmp_path: Path) -> None:
        """A missing transition file renders straight to the output with no mux."""
        out = tmp_path / "clip.mp4"
        segment = self._make_segment()
        captured: dict[str, list[str]] = {}

        def capture(cmd: list[str]) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
            captured["cmd"] = cmd
            return self._success_proc()

        mux = MagicMock()
        with (
            patch("src.pipeline.clip.get_representative_frame", return_value=None),
            patch("src.pipeline.clip._get_video_dimensions", return_value=(1920, 1080)),
            patch("src.pipeline.clip._find_fonts_dir", return_value=None),
            patch("src.pipeline.clip._run_ffmpeg", side_effect=capture),
            patch("src.pipeline.clip._prepend_transition", mux),
        ):
            await generate_clip(
                source_video="/fake/video.mp4",
                segment=segment,
                words=[],
                output_path=out,
                options=ClipOptions(transition_path=tmp_path / "missing.mp4"),
            )

        assert captured["cmd"][-1] == str(out)
        mux.assert_not_called()


# end tests/unit/test_clip.py
