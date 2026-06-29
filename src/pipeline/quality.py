# start src/pipeline/quality.py
"""Deterministic visual-quality utilities (no VLM — pure ffmpeg/Pillow).

Implements the plan's E/F opportunities as cheap, deterministic, gate-testable
ffmpeg utilities rather than spending a VLM on them (docs/plans/vlm-enhancement.md,
P12 "never reinvent"):

- **Scene detection** — ffmpeg ``select='gt(scene,...)'`` finds visual cuts so a
  clip's start can be snapped to a cut instead of beginning mid-shot.
- **Brightness probing** — Pillow mean-luma over sampled frames flags segments
  that are too dark to be worth encoding.

Every threshold/tunable is a :class:`src.config.Config` field; nothing here is a
magic number, and every feature is off by default.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import structlog

from src.pipeline.vision import extract_frame_b64, sample_timestamps

log = structlog.get_logger(__name__)

_PTS_TIME_RE = re.compile(r"pts_time:([0-9.]+)")


def detect_scene_timestamps(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    threshold: float,
) -> list[float]:
    """Return absolute timestamps of visual scene cuts within ``[start_s, end_s]``.

    Runs ffmpeg's scene-detection filter over the segment and parses the cut
    times from ``showinfo``. ``-ss`` before ``-i`` re-bases the output to 0, so
    parsed ``pts_time`` values are offset by ``start_s`` to absolute time.

    Args:
        video_path: Source video path.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        threshold: Scene-change sensitivity in [0,1] (higher = fewer cuts).

    Returns:
        Sorted absolute cut timestamps; empty on failure or no cuts.
    """
    duration = max(0.0, end_s - start_s)
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-ss",
                str(start_s),
                "-i",
                str(video_path),
                "-t",
                str(duration),
                "-vf",
                f"select='gt(scene,{threshold})',showinfo",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("quality.scene_detect_failed", error=str(exc))
        return []
    stderr = result.stderr.decode(errors="replace")
    return sorted(start_s + float(m) for m in _PTS_TIME_RE.findall(stderr))


def snap_start_to_scene(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    threshold: float,
    window_s: float,
) -> float:
    """Snap a clip start back to the nearest scene cut within ``window_s``.

    Looks for a visual cut in ``[start_s - window_s, start_s]`` and, if found,
    returns the latest such cut so the clip begins on a clean shot boundary.
    Returns ``start_s`` unchanged when no cut is found in the window.

    Args:
        video_path: Source video path.
        start_s: Proposed clip start in seconds.
        end_s: Clip end in seconds (bounds the scan).
        threshold: Scene-change sensitivity in [0,1].
        window_s: How far before ``start_s`` to look for a cut.

    Returns:
        The snapped start time (<= ``start_s``).
    """
    scan_start = max(0.0, start_s - window_s)
    cuts = detect_scene_timestamps(video_path, scan_start, end_s, threshold)
    earlier = [c for c in cuts if scan_start <= c <= start_s]
    return max(earlier) if earlier else start_s


def frame_brightness(video_path: str | Path, timestamp_s: float, max_dim: int) -> float | None:
    """Return the mean luma (0–255) of one frame, or ``None`` on failure.

    Args:
        video_path: Source video path.
        timestamp_s: Frame timestamp in seconds.
        max_dim: Frame width used for the probe (smaller = faster).

    Returns:
        Mean brightness in [0,255], or ``None`` if the frame can't be read.
    """
    import base64
    import io

    from PIL import Image

    encoded = extract_frame_b64(video_path, timestamp_s, max_dim)
    if encoded is None:
        return None
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("L")
    pixels = image.tobytes()
    return sum(pixels) / len(pixels)


def segment_mean_brightness(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int,
    max_dim: int,
) -> float | None:
    """Return the mean brightness across sampled frames of a segment.

    Args:
        video_path: Source video path.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        samples: Number of frames to sample.
        max_dim: Frame width used for the probe.

    Returns:
        Average mean-luma across readable frames, or ``None`` if none could be
        read.
    """
    timestamps = sample_timestamps(start_s, end_s, samples)
    values = [frame_brightness(video_path, ts, max_dim) for ts in timestamps]
    readable = [v for v in values if v is not None]
    if not readable:
        return None
    return sum(readable) / len(readable)


def is_segment_too_dark(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    samples: int,
    max_dim: int,
    min_brightness: float,
) -> bool:
    """Return True when a segment's mean brightness is below ``min_brightness``.

    A segment whose frames cannot be read is treated as NOT too dark (fail open),
    so probing problems never silently drop content.

    Args:
        video_path: Source video path.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        samples: Number of frames to sample.
        max_dim: Frame width used for the probe.
        min_brightness: Mean-luma floor below which the segment is "too dark".

    Returns:
        ``True`` if too dark, else ``False``.
    """
    brightness = segment_mean_brightness(video_path, start_s, end_s, samples, max_dim)
    if brightness is None:
        return False
    return brightness < min_brightness


# end src/pipeline/quality.py
