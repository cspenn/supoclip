# start tests/unit/test_quality.py
"""Unit tests for src/pipeline/quality.py — deterministic ffmpeg quality utils.

These use REAL ffmpeg over synthesized lavfi clips (black/white/cut), matching
the project convention of testing ffmpeg helpers against real output.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pipeline.quality import (
    detect_scene_timestamps,
    frame_brightness,
    is_segment_too_dark,
    segment_mean_brightness,
    snap_start_to_scene,
)

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"


def _synth(dest: Path, color: str, duration: float = 1.0) -> Path:
    """Render a solid-color clip via ffmpeg lavfi."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            str(duration),
            "-i",
            f"color=c={color}:s=320x240:r=10",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        capture_output=True,
        check=True,
    )
    return dest


def _synth_cut(dest: Path, tmp: Path) -> Path:
    """Render a 2s clip that hard-cuts from black to white at 1s."""
    black = _synth(tmp / "b.mp4", "black")
    white = _synth(tmp / "w.mp4", "white")
    listing = tmp / "list.txt"
    listing.write_text(f"file '{black}'\nfile '{white}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)],
        capture_output=True,
        check=True,
    )
    return dest


class TestFrameBrightness:
    def test_black_is_dark(self, tmp_path: Path) -> None:
        assert frame_brightness(_synth(tmp_path / "k.mp4", "black"), 0.5, 160) < 16

    def test_white_is_bright(self, tmp_path: Path) -> None:
        assert frame_brightness(_synth(tmp_path / "w.mp4", "white"), 0.5, 160) > 200

    def test_missing_returns_none(self) -> None:
        assert frame_brightness("/no/such.mp4", 0.5, 160) is None


class TestSegmentBrightness:
    def test_mean_over_samples(self, tmp_path: Path) -> None:
        assert segment_mean_brightness(_synth(tmp_path / "k.mp4", "black"), 0.0, 1.0, 3, 160) < 16

    def test_all_unreadable_returns_none(self, tmp_path: Path) -> None:
        with patch("src.pipeline.quality.frame_brightness", return_value=None):
            assert segment_mean_brightness(tmp_path / "x.mp4", 0.0, 1.0, 3, 160) is None


class TestIsSegmentTooDark:
    def test_black_segment_too_dark(self, tmp_path: Path) -> None:
        assert is_segment_too_dark(_synth(tmp_path / "k.mp4", "black"), 0.0, 1.0, 3, 160, 16.0) is True

    def test_white_segment_not_dark(self, tmp_path: Path) -> None:
        assert is_segment_too_dark(_synth(tmp_path / "w.mp4", "white"), 0.0, 1.0, 3, 160, 16.0) is False

    def test_unreadable_fails_open(self, tmp_path: Path) -> None:
        with patch("src.pipeline.quality.segment_mean_brightness", return_value=None):
            assert is_segment_too_dark(tmp_path / "x.mp4", 0.0, 1.0, 3, 160, 16.0) is False


class TestSceneDetection:
    def test_finds_cut(self, tmp_path: Path) -> None:
        video = _synth_cut(tmp_path / "cut.mp4", tmp_path)
        cuts = detect_scene_timestamps(video, 0.0, 2.0, 0.3)
        assert any(0.8 <= c <= 1.2 for c in cuts), cuts

    def test_no_cut_in_solid_clip(self, tmp_path: Path) -> None:
        assert detect_scene_timestamps(_synth(tmp_path / "k.mp4", "black"), 0.0, 1.0, 0.3) == []

    def test_subprocess_error_returns_empty(self) -> None:
        with patch("src.pipeline.quality.subprocess.run", side_effect=OSError("boom")):
            assert detect_scene_timestamps(_FIXTURE, 0.0, 1.0, 0.3) == []


class TestSnapStartToScene:
    def test_snaps_to_cut_in_window(self) -> None:
        with patch("src.pipeline.quality.detect_scene_timestamps", return_value=[1.0]):
            assert snap_start_to_scene("/v.mp4", 1.2, 3.0, 0.3, 0.5) == pytest.approx(1.0)

    def test_no_cut_returns_start(self) -> None:
        with patch("src.pipeline.quality.detect_scene_timestamps", return_value=[]):
            assert snap_start_to_scene("/v.mp4", 1.2, 3.0, 0.3, 0.5) == pytest.approx(1.2)

    def test_cut_outside_window_ignored(self) -> None:
        # A cut at 0.2 is outside [0.7, 1.2]; start is unchanged.
        with patch("src.pipeline.quality.detect_scene_timestamps", return_value=[0.2]):
            assert snap_start_to_scene("/v.mp4", 1.2, 3.0, 0.3, 0.5) == pytest.approx(1.2)


# end tests/unit/test_quality.py
