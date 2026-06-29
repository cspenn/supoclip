# start tests/e2e/vision_features.py
"""Live e2e exercise of the vision.py orchestration (active-speaker / engagement /
thumbnail selection) against a real VLM endpoint and a real video.

Unlike vision_spike.py (which probes the raw chat call), this drives the actual
public functions the pipeline uses, proving the wired feature end to end. It is
NOT pytest-collected (hits a live endpoint + ffmpeg).

Usage::

    VLM_ENABLED=true VLM_MODEL=Qwen3.6-35B-A3B-Mixed-4-8 \\
    LOCAL_LLM_BASE_URL=http://127.0.0.1:8998/v1 LOCAL_LLM_API_KEY=12345 \\
    uv run --no-sync python -m tests.e2e.vision_features <video> <start_s> <end_s>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from src.config import get_config
from src.pipeline.vision import (
    detect_active_speaker,
    score_engagement,
    select_best_frame_timestamp,
)


def main() -> None:
    """Run the three vision features over one segment and print the results."""
    if len(sys.argv) < 4:
        print("usage: python -m tests.e2e.vision_features <video> <start_s> <end_s>")
        raise SystemExit(2)
    video = Path(sys.argv[1])
    start_s, end_s = float(sys.argv[2]), float(sys.argv[3])

    get_config.cache_clear()
    cfg = get_config()
    print(f"VLM enabled={cfg.vlm_enabled} model={cfg.vlm_model} endpoint={cfg.get_vlm_base_url()}")
    print(f"Segment: {video.name} [{start_s}s, {end_s}s]")

    t0 = time.monotonic()
    speaker = detect_active_speaker(video, start_s, end_s)
    print(f"  active_speaker: {speaker}  ({time.monotonic() - t0:.1f}s)")

    t0 = time.monotonic()
    engagement = score_engagement(video, start_s, end_s)
    print(f"  engagement: {engagement}  ({time.monotonic() - t0:.1f}s)")

    t0 = time.monotonic()
    best = select_best_frame_timestamp(video, start_s, end_s)
    print(f"  best_thumbnail_ts: {best:.2f}s  ({time.monotonic() - t0:.1f}s)")

    ok = speaker is not None and engagement is not None
    print("RESULT:", "PASS" if ok else "PARTIAL (VLM off or unavailable)")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

# end tests/e2e/vision_features.py
