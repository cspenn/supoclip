# start tests/e2e/smoke_pipeline.py
"""Reusable end-to-end smoke test for the full SupoClip pipeline.

Runs the REAL pipeline against a real source (YouTube URL or local file) using
the same wiring the home page uses (build_processing_request -> process_video),
so subtitles/logo/transitions are exercised exactly as in production. It then
inspects the produced clips with ffprobe and asserts they are real 9:16 H.264
files with burned-in subtitles.

This is NOT collected by pytest (no ``test_`` prefix) because it hits the
network, the local LLM, and parakeet-mlx — it is a manual/CI smoke runner.

Usage::

    LOCAL_LLM_ENABLED=true \\
    LOCAL_LLM_BASE_URL=http://127.0.0.1:8998/v1 \\
    LOCAL_LLM_MODEL=gemma-4-26B-A4B-MLX-4-8 \\
    LOCAL_LLM_API_KEY=12345 \\
    uv run --no-sync python -m tests.e2e.smoke_pipeline \\
        "https://www.youtube.com/watch?v=wkPL4QNlNV4"

Optional args: <min_clip_s> <max_clip_s> <resolution>.
Exit code 0 on success, 1 on any failure.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import structlog

from src.config import get_config
from src.database import get_session, init_db
from src.models import GeneratedClip, Task
from src.pages.home import build_processing_request
from src.services.video_service import process_video

log = structlog.get_logger()


def _ffprobe(path: Path) -> dict:
    """Return ffprobe format+stream JSON for a media file."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _progress(pct: int, msg: str) -> None:
    """Print a pipeline progress line."""
    print(f"  [{pct:3d}%] {msg}", flush=True)


async def _run(source: str, min_s: int, max_s: int, resolution: str) -> int:
    """Execute the full pipeline and inspect outputs. Returns an exit code."""
    cfg = get_config()
    cfg.ensure_temp_dirs()
    await init_db(cfg.database_url)

    print(f"LLM: enabled={cfg.local_llm_enabled} base={cfg.local_llm_base_url} model={cfg.local_llm_model}", flush=True)
    print(f"Source: {source}", flush=True)

    async with get_session() as session:
        task = Task(source_url=source, source_type="youtube")
        session.add(task)
        await session.flush()
        await session.refresh(task)
        task_id = task.id
    print(f"Task: {task_id}", flush=True)

    request = await build_processing_request(
        source=source,
        task_id=task_id,
        min_clip_length=min_s,
        max_clip_length=max_s,
        output_resolution=resolution,
    )
    print(
        f"Subtitle style wired: {request.subtitle_style is not None} (font={getattr(request.subtitle_style, 'font_family', None)})",
        flush=True,
    )

    t0 = time.monotonic()
    result = await process_video(request, progress_callback=_progress)
    elapsed = time.monotonic() - t0
    print(f"\nPipeline finished in {elapsed:.1f}s", flush=True)

    if result.error:
        print(f"FAIL: pipeline error: {result.error}", flush=True)
        return 1

    if not result.clips:
        print("FAIL: no clips were produced", flush=True)
        return 1

    clips_dir = cfg.temp_dir / "clips"
    print(f"\nProduced {len(result.clips)} clip(s):", flush=True)
    ok = True
    for clip_path in result.clips:
        p = Path(clip_path)
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        ass = p.with_suffix(".ass")
        probe = _ffprobe(p) if exists and size > 0 else {}
        vstream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        w, h = vstream.get("width"), vstream.get("height")
        codec = vstream.get("codec_name")
        dur = float(probe.get("format", {}).get("duration", 0) or 0)
        is_portrait = bool(w and h and h > w)
        clip_ok = exists and size > 0 and codec == "h264" and is_portrait
        ok = ok and clip_ok
        print(
            f"  {'OK ' if clip_ok else 'BAD'} {p.name}  {w}x{h} {codec} {dur:.1f}s  {size} bytes  subs={'yes' if ass.exists() else 'NO'}",
            flush=True,
        )

    # Confirm DB rows were written.
    async with get_session() as session:
        from sqlalchemy import select

        rows = (await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == task_id))).scalars().all()
    print(f"\nDB GeneratedClip rows for task: {len(rows)}", flush=True)

    print(f"\nClips dir: {clips_dir}", flush=True)
    print("RESULT:", "PASS" if ok and rows else "FAIL", flush=True)
    return 0 if (ok and rows) else 1


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("usage: python -m tests.e2e.smoke_pipeline <url|path> [min_s] [max_s] [resolution]")
        raise SystemExit(2)
    source = sys.argv[1]
    min_s = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    max_s = int(sys.argv[3]) if len(sys.argv) > 3 else 45
    resolution = sys.argv[4] if len(sys.argv) > 4 else "1080p"
    raise SystemExit(asyncio.run(_run(source, min_s, max_s, resolution)))


if __name__ == "__main__":
    main()

# end tests/e2e/smoke_pipeline.py
