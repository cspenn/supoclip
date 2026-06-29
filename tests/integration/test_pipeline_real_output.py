# start tests/integration/test_pipeline_real_output.py
"""Real-output integration tests — the oracle that catches output-correctness bugs.

These tests deliberately DO NOT mock ffmpeg. They produce real ``.mp4`` and
``.ass`` artifacts from the committed ``sample_video.mp4`` fixture and assert
against the actual files (dimensions, codec, burned-in pixels, caption sync).

Why this exists (read against the git history): subtitle/caption/sync churned
across 47 commits and a *mocked* sync suite (232ecf4) failed to stop the
regressions because it never produced or inspected a real artifact. A
presence-only assertion is insufficient — test #3 asserts caption event timings
align to the source word timestamps within tolerance, which is the property
that regressed 29 times.

Coverage note: these are REAL-OUTPUT tests, not line-coverage filler. Do not
replace the ffmpeg call with a mock to "make coverage pass" — that recreates
the exact failure mode this suite exists to prevent.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pysubs2
import pytest

from src.pipeline.clip import ClipOptions, TranscriptSegment, generate_clip
from src.pipeline.subtitles import SubtitleStyle

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"
_LOGO = Path(__file__).parent.parent / "fixtures" / "sample_logo.png"

_HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed (must run in CI/gate)"),
]


def _ffprobe_video_stream(path: Path) -> dict[str, str]:
    """Return codec_name/width/height for the first video stream via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    info: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            info[key] = value
    return info


def _extract_frame(video: Path, timestamp_s: float, dest: Path) -> Path:
    """Extract a single PNG frame from *video* at *timestamp_s*."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(timestamp_s),
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(dest),
        ],
        capture_output=True,
        check=True,
    )
    return dest


@pytest.mark.asyncio
async def test_real_clip_has_correct_dimensions_and_codec(tmp_path: Path) -> None:
    """A real generated clip is 9:16, H.264, and non-empty."""
    out = tmp_path / "clip.mp4"
    segment = TranscriptSegment(start_s=0.0, end_s=2.0, text="hello world")

    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=[],
        output_path=out,
        options=ClipOptions(output_resolution="1080p"),
    )

    assert out.exists(), "clip file was not produced"
    assert out.stat().st_size > 0, "clip file is empty"

    info = _ffprobe_video_stream(out)
    assert info.get("codec_name") == "h264", info
    assert int(info["width"]) == 1080, info
    assert int(info["height"]) == 1920, info
    # 9:16 aspect ratio.
    assert int(info["height"]) / int(info["width"]) == pytest.approx(16 / 9, rel=1e-6)


@pytest.mark.asyncio
async def test_real_clip_burns_in_captions(tmp_path: Path) -> None:
    """Burning subtitles actually changes pixels vs. an unsubtitled clip.

    This is the presence assertion: a frame from the captioned clip must differ
    materially from the same frame of an identical clip rendered without
    subtitles. A no-op subtitle pipeline (the current bug) makes the two frames
    identical and fails this test.
    """
    pil_image = pytest.importorskip("PIL.Image")

    words = [
        {"text": "HELLO", "start_ms": 200, "end_ms": 900},
        {"text": "WORLD", "start_ms": 1000, "end_ms": 1800},
    ]
    segment = TranscriptSegment(start_s=0.0, end_s=2.5, text="hello world")

    plain = tmp_path / "plain.mp4"
    captioned = tmp_path / "captioned.mp4"

    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=words,
        output_path=plain,
        options=ClipOptions(output_resolution="720p", subtitle_style=None),
    )
    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=words,
        output_path=captioned,
        options=ClipOptions(
            output_resolution="720p",
            subtitle_style=SubtitleStyle(font_size=48, position_y_pct=75),
        ),
    )

    # Frame at t=1.2s — "WORLD" is on screen (re-based 1000-1800ms).
    f_plain = _extract_frame(plain, 1.2, tmp_path / "plain.png")
    f_caption = _extract_frame(captioned, 1.2, tmp_path / "caption.png")

    img_a = pil_image.open(f_plain).convert("RGB")
    img_b = pil_image.open(f_caption).convert("RGB")
    assert img_a.size == img_b.size

    # Count materially-different pixels from the raw RGB bytes.
    bytes_a = img_a.tobytes()
    bytes_b = img_b.tobytes()
    diff_pixels = sum(
        1
        for i in range(0, len(bytes_a), 3)
        if abs(bytes_a[i] - bytes_b[i]) + abs(bytes_a[i + 1] - bytes_b[i + 1]) + abs(bytes_a[i + 2] - bytes_b[i + 2]) > 40
    )
    assert diff_pixels > 500, f"captioned frame differs from plain frame in only {diff_pixels} pixels — subtitles were not burned in"


@pytest.mark.asyncio
async def test_real_clip_overlays_logo(tmp_path: Path) -> None:
    """Overlaying a logo actually changes top-right pixels vs. a logo-less clip.

    This proves the M-4 overlay filtergraph renders the second input: the only
    difference between the two clips is the logo, so the same extracted frame
    must differ materially in the top-right region where the logo is placed.
    """
    pil_image = pytest.importorskip("PIL.Image")
    assert _LOGO.exists(), "sample_logo.png fixture missing"

    segment = TranscriptSegment(start_s=0.0, end_s=2.0, text="logo test")

    plain = tmp_path / "plain.mp4"
    branded = tmp_path / "branded.mp4"

    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=[],
        output_path=plain,
        options=ClipOptions(output_resolution="720p"),
    )
    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=[],
        output_path=branded,
        options=ClipOptions(output_resolution="720p", logo_path=_LOGO),
    )

    f_plain = _extract_frame(plain, 0.5, tmp_path / "plain.png")
    f_brand = _extract_frame(branded, 0.5, tmp_path / "brand.png")

    img_a = pil_image.open(f_plain).convert("RGB")
    img_b = pil_image.open(f_brand).convert("RGB")
    assert img_a.size == img_b.size

    # Crop the top-right quadrant where the logo is overlaid (margin 20px).
    width, height = img_a.size
    box = (width // 2, 0, width, height // 2)
    region_a = img_a.crop(box).tobytes()
    region_b = img_b.crop(box).tobytes()

    diff_pixels = sum(
        1
        for i in range(0, len(region_a), 3)
        if abs(region_a[i] - region_b[i]) + abs(region_a[i + 1] - region_b[i + 1]) + abs(region_a[i + 2] - region_b[i + 2]) > 40
    )
    assert diff_pixels > 100, f"branded frame differs from plain frame in only {diff_pixels} top-right pixels — logo was not overlaid"


@pytest.mark.asyncio
async def test_caption_event_timings_match_word_timestamps(tmp_path: Path) -> None:
    """Caption events are re-based to the clip and stay synced to the words.

    The segment starts at 0.5s, so a word at absolute 600ms must appear at
    re-based 100ms in the ASS file. Words outside the segment must be dropped.
    This locks caption SYNC (the 29-times-regressed property), not mere presence.
    """
    words = [
        {"text": "alpha", "start_ms": 600, "end_ms": 1000},
        {"text": "bravo", "start_ms": 1100, "end_ms": 1600},
        {"text": "charlie", "start_ms": 1700, "end_ms": 2200},
        {"text": "delta", "start_ms": 4000, "end_ms": 4500},  # outside segment
    ]
    segment = TranscriptSegment(start_s=0.5, end_s=2.5, text="alpha bravo charlie")
    out = tmp_path / "synced.mp4"

    await generate_clip(
        source_video=_FIXTURE,
        segment=segment,
        words=words,
        output_path=out,
        options=ClipOptions(output_resolution="720p", subtitle_style=SubtitleStyle()),
    )

    ass_path = out.with_suffix(".ass")
    assert ass_path.exists(), "no .ass file was written alongside the clip"

    subs = pysubs2.load(str(ass_path))
    events = sorted(subs.events, key=lambda e: e.start)

    # Karaoke phrase windows (spec 9.2): the three in-segment words form one
    # context window, so each active word emits one event whose visible text
    # contains that word (others are dimmed context). Out-of-segment "delta" is
    # dropped during re-basing. Each event's timing stays locked to its active
    # word -- the 29-times-regressed SYNC property is non-negotiable.
    assert len(events) == 3, f"expected 3 caption events (one per active word); got {len(events)}"

    expected_words = ["alpha", "bravo", "charlie"]
    expected = [(100, 500), (600, 1100), (1200, 1700)]
    tol_ms = 15
    for event, word, (exp_start, exp_end) in zip(events, expected_words, expected, strict=True):
        visible = event.plaintext  # strips ASS override tags
        assert word in visible, f"event at {event.start}ms missing active word {word!r}; visible={visible!r}"
        assert abs(event.start - exp_start) <= tol_ms, f"{word}: start {event.start}ms drifted from {exp_start}ms"
        assert abs(event.end - exp_end) <= tol_ms, f"{word}: end {event.end}ms drifted from {exp_end}ms"


# end tests/integration/test_pipeline_real_output.py
