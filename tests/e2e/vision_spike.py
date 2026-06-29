# start tests/e2e/vision_spike.py
"""VLM vision-capability probe (Phase 0 entry gate for the VLM enhancement plan).

Verifies that the configured multimodal endpoint actually *perceives* image
content via the OpenAI-compatible vision message format — not merely that it
accepts the request shape. This is the go/no-go check that must PASS before any
VLM-vision feature (engagement re-ranking, thumbnails, salient framing) is built;
see docs/plans/vlm-enhancement.md.

It is NOT a pytest test (no ``test_`` prefix): it hits a live local endpoint.

Method: send an unambiguous synthetic solid-RED image and assert the model
reports "red". A correct answer proves real pixels reach the model; a wrong
answer (e.g. "gray") proves the vision path is broken regardless of token counts.
Optionally also probes a real video frame for a sanity description.

Config (all from env / src.config, no magic constants):
    LOCAL_LLM_BASE_URL, LOCAL_LLM_API_KEY  — endpoint + key (src.config.Config)
    VLM_MODEL                              — model id to probe (defaults to LOCAL_LLM_MODEL)
    VLM_PROBE_TIMEOUT_S                    — request timeout (default 180)
    VLM_PROBE_MAX_TOKENS                   — max output tokens (default 512; raise for
                                             reasoning VLMs that emit chain-of-thought)

Usage::

    VLM_MODEL=gemma-4-26B-A4B-MLX-4-8 \\
    uv run --no-sync python -m tests.e2e.vision_spike [optional_video_path]

Exit code 0 if vision works (red correctly identified), 1 otherwise.
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

from src.config import get_config

_DEFAULT_TIMEOUT_S = 180.0
# Generous default so reasoning VLMs (e.g. Qwen3.x) aren't cut off mid-chain-of-
# thought before they emit the answer; overridable via VLM_PROBE_MAX_TOKENS.
_DEFAULT_MAX_TOKENS = 512
_PROBE_IMAGE_SIZE = 512
_RED = (220, 20, 20)


def _b64_jpeg(image: Image.Image) -> str:
    """Return a base64-encoded JPEG of an image."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def _ask(base_url: str, api_key: str, model: str, b64: str, prompt: str, timeout: float, max_tokens: int) -> tuple[str, float, int]:
    """Send one vision chat-completion; return (reply_text, latency_s, prompt_tokens)."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    t0 = time.monotonic()
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    latency = time.monotonic() - t0
    text = data["choices"][0]["message"]["content"]
    ptok = int(data.get("usage", {}).get("prompt_tokens", 0))
    return text, latency, ptok


def _frame_b64(video: Path, timestamp_s: float) -> str | None:
    """Extract a frame from a video as base64 JPEG, or None on failure."""
    try:
        out = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp_s),
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={_PROBE_IMAGE_SIZE}:-1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        return base64.b64encode(out.stdout).decode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def main() -> None:
    """Run the vision probe; exit 0 if the endpoint truly sees images."""
    cfg = get_config()
    base_url = cfg.local_llm_base_url
    api_key = cfg.local_llm_api_key
    model = os.environ.get("VLM_MODEL", cfg.local_llm_model)
    timeout = float(os.environ.get("VLM_PROBE_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
    max_tokens = int(os.environ.get("VLM_PROBE_MAX_TOKENS", _DEFAULT_MAX_TOKENS))

    print(f"VLM probe -> endpoint={base_url} model={model}", flush=True)

    red = Image.new("RGB", (_PROBE_IMAGE_SIZE, _PROBE_IMAGE_SIZE), _RED)
    reply, latency, ptok = _ask(
        base_url,
        api_key,
        model,
        _b64_jpeg(red),
        "What is the dominant color of this image? Think briefly, then end with 'FINAL: <color>'.",
        timeout,
        max_tokens,
    )
    print(f"  solid-RED test: {latency:.1f}s, {ptok} prompt tokens -> {reply!r}", flush=True)
    vision_ok = "red" in reply.strip().lower()

    if len(sys.argv) > 1:
        video = Path(sys.argv[1])
        if video.exists():
            fb = _frame_b64(video, 180.0)
            if fb:
                rep2, lat2, ptok2 = _ask(
                    base_url,
                    api_key,
                    model,
                    fb,
                    "How many people are visible and what is the setting? One sentence.",
                    timeout,
                    max_tokens,
                )
                print(f"  real-frame test: {lat2:.1f}s, {ptok2} prompt tokens -> {rep2!r}", flush=True)

    print(
        "\nRESULT:",
        "PASS — endpoint perceives images; VLM-vision features are unblocked."
        if vision_ok
        else "FAIL — endpoint does NOT perceive images (vision broken). Do NOT build VLM-vision features until this passes.",
        flush=True,
    )
    raise SystemExit(0 if vision_ok else 1)


if __name__ == "__main__":
    main()

# end tests/e2e/vision_spike.py
