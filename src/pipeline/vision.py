# start src/pipeline/vision.py
"""Vision-aware clipping via a multimodal LLM (VLM).

Adds visual signal to the otherwise transcript-only pipeline: who is the active
speaker in a `duo`/`multi` clip (for framing) and how visually engaging a segment
is (for re-ranking). See docs/plans/vlm-enhancement.md.

Determinism boundary (plan §2 — the regression guard):
- The **deterministic core** — sample-timestamp math, ffmpeg frame extraction,
  JSON/response parsing, and the disabled/error → ``None`` fallback — is ordinary
  code, unit-tested in the gate.
- The **raw VLM chat call** (:func:`_vlm_chat`) is a thin seam: its request
  construction is unit-tested (patched transport), but the live network call is
  exercised only in the e2e tier (``tests/e2e/vision_spike.py`` + e2e tests).
- The VLM is **off by default** (``Config.vlm_enabled``). When disabled, every
  public entry point returns ``None`` so callers keep today's behavior.

Every tunable comes from :class:`src.config.Config` — no magic numbers here.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx
import structlog

from src.config import Config, get_config

log = structlog.get_logger(__name__)

# Sides a clip can be framed toward, in the order they appear left-to-right.
_VALID_SIDES: tuple[str, ...] = ("left", "right", "center")

_ACTIVE_SPEAKER_PROMPT: str = (
    "The image is a split-screen with people side by side. Who is currently "
    "SPEAKING? Judge by mouth open/movement and gestures. Reply with strict JSON "
    'only: {"active_speaker": "left|right|center", "confidence": 0-1}. '
    "Think briefly if needed, but end your reply with that JSON object."
)

_ENGAGEMENT_PROMPT: str = (
    "Rate how visually engaging this video frame is for a short-form clip "
    "(motion, expression, on-screen text, demonstration, visual interest). Reply "
    'with strict JSON only: {"engagement": 0-1}. End your reply with that JSON.'
)


@dataclass(slots=True)
class ActiveSpeaker:
    """Result of active-speaker detection for a clip.

    Attributes:
        side: ``"left"``, ``"right"`` or ``"center"`` — the framing focus.
        confidence: Model confidence in range [0.0, 1.0].
    """

    side: str
    confidence: float


# ---------------------------------------------------------------------------
# Deterministic core (gate-tested)
# ---------------------------------------------------------------------------


def sample_timestamps(start_s: float, end_s: float, samples: int) -> list[float]:
    """Return evenly spaced sample timestamps across ``[start_s, end_s]``.

    Args:
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        samples: Number of timestamps to produce (>= 1).

    Returns:
        A list of timestamps. A single sample (or a zero/negative-length
        segment) collapses to ``[start_s]``; otherwise endpoints are included.
    """
    count = max(1, samples)
    if count == 1 or end_s <= start_s:
        return [start_s]
    step = (end_s - start_s) / (count - 1)
    return [start_s + step * i for i in range(count)]


def extract_frame_b64(video_path: str | Path, timestamp_s: float, max_dim: int) -> str | None:
    """Extract one frame as a base64-encoded JPEG, scaled to ``max_dim`` wide.

    Args:
        video_path: Path to the source video.
        timestamp_s: Seek position in seconds.
        max_dim: Target width in pixels (height auto, aspect preserved).

    Returns:
        Base64 JPEG string, or ``None`` if extraction fails (logged).
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp_s),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={max_dim}:-1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("vision.frame_extract_failed", timestamp=timestamp_s, error=str(exc))
        return None
    if result.returncode != 0 or not result.stdout:
        log.warning("vision.frame_extract_empty", timestamp=timestamp_s, rc=result.returncode)
        return None
    return base64.b64encode(result.stdout).decode()


def extract_json(content: str) -> dict | None:  # type: ignore[type-arg]
    """Extract the LAST JSON object from a (possibly reasoning-laden) reply.

    Reasoning VLMs emit chain-of-thought before the answer and may fence the
    final JSON; this returns the last parseable ``{...}`` object found.

    Args:
        content: Raw model reply text.

    Returns:
        The parsed JSON object, or ``None`` if none is found / parseable.
    """
    candidates = re.findall(r"\{[^{}]*\}", content)
    for blob in reversed(candidates):
        try:
            # A regex-matched ``{...}`` that parses is always a JSON object (dict).
            return dict(json.loads(blob))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _coerce_confidence(value: object) -> float:
    """Coerce a model-supplied confidence into a clamped [0,1] float."""
    try:
        conf = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, conf))


def parse_active_speaker(content: str) -> ActiveSpeaker | None:
    """Parse an active-speaker JSON reply into an :class:`ActiveSpeaker`.

    Args:
        content: Raw VLM reply text.

    Returns:
        An :class:`ActiveSpeaker` when a valid side is present, else ``None``.
    """
    data = extract_json(content)
    if data is None:
        return None
    side = str(data.get("active_speaker", "")).strip().lower()
    if side not in _VALID_SIDES:
        return None
    return ActiveSpeaker(side=side, confidence=_coerce_confidence(data.get("confidence")))


def parse_engagement(content: str) -> float | None:
    """Parse an engagement JSON reply into a clamped [0,1] score, or ``None``."""
    data = extract_json(content)
    if data is None or "engagement" not in data:
        return None
    return _coerce_confidence(data.get("engagement"))


def fuse_scores(
    transcript_score: float,
    engagement: float,
    transcript_weight: float,
    visual_weight: float,
) -> float:
    """Fuse a transcript relevance score with a visual engagement score.

    Computes a weighted average so the result stays on the same [0,1] scale
    regardless of the absolute weights. When both weights are zero, the
    transcript score is returned unchanged (a safe identity).

    Args:
        transcript_score: LLM relevance score in [0,1].
        engagement: VLM visual-engagement score in [0,1].
        transcript_weight: Weight for the transcript score (>= 0).
        visual_weight: Weight for the visual score (>= 0).

    Returns:
        The fused score in [0,1].
    """
    total = transcript_weight + visual_weight
    if total <= 0:
        return transcript_score
    return (transcript_weight * transcript_score + visual_weight * engagement) / total


# ---------------------------------------------------------------------------
# VLM seam (e2e-tested; request construction is gate-tested with patched transport)
# ---------------------------------------------------------------------------


def build_vlm_payload(frames_b64: list[str], prompt: str, cfg: Config) -> dict:  # type: ignore[type-arg]
    """Build the OpenAI-compatible vision chat-completion request body.

    Args:
        frames_b64: Base64 JPEG frames to attach as ``image_url`` parts.
        prompt: The instruction text.
        cfg: Application config (model + token budget).

    Returns:
        A JSON-serializable request payload dict.
    """
    image_parts = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f}"}} for f in frames_b64]
    return {
        "model": cfg.vlm_model,
        "messages": [{"role": "user", "content": [*image_parts, {"type": "text", "text": prompt}]}],
        "max_tokens": cfg.vlm_max_tokens,
        "temperature": 0,
    }


def _vlm_chat(frames_b64: list[str], prompt: str, cfg: Config) -> str | None:
    """Call the VLM chat endpoint and return the reply text, or ``None`` on failure.

    This is the determinism-boundary seam: the live HTTP call runs only in the
    e2e tier. Gate tests patch ``httpx.post`` to assert request construction.
    """
    try:
        resp = httpx.post(
            f"{cfg.get_vlm_base_url().rstrip('/')}/chat/completions",
            json=build_vlm_payload(frames_b64, prompt, cfg),
            headers={"Authorization": f"Bearer {cfg.get_vlm_api_key()}"},
            timeout=cfg.vlm_timeout_s,
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("vision.vlm_call_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Orchestration (deterministic except the _vlm_chat seam; gate-tested via injection)
# ---------------------------------------------------------------------------


def _gather_frames(video_path: str | Path, start_s: float, end_s: float, cfg: Config) -> list[str]:
    """Sample and extract frames across a segment; drop any that fail."""
    timestamps = sample_timestamps(start_s, end_s, cfg.vlm_frames_per_clip)
    frames = [extract_frame_b64(video_path, ts, cfg.vlm_image_max_dim) for ts in timestamps]
    return [f for f in frames if f is not None]


def detect_active_speaker(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    config: Config | None = None,
) -> ActiveSpeaker | None:
    """Detect the active speaker for a clip via the VLM (``None`` when disabled).

    Samples the middle frame of the segment (the most representative single
    moment) and asks the VLM which side is speaking. Returns ``None`` when the
    VLM is disabled, frames cannot be extracted, the call fails, or the reply is
    unparseable — so callers fall back to deterministic framing.

    Args:
        video_path: Source video path.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        config: Optional config override (defaults to :func:`get_config`).

    Returns:
        An :class:`ActiveSpeaker`, or ``None``.
    """
    cfg = config or get_config()
    if not cfg.vlm_enabled or not cfg.vlm_model:
        return None
    midpoint = start_s + (end_s - start_s) / 2
    frame = extract_frame_b64(video_path, midpoint, cfg.vlm_image_max_dim)
    if frame is None:
        return None
    reply = _vlm_chat([frame], _ACTIVE_SPEAKER_PROMPT, cfg)
    if reply is None:
        return None
    return parse_active_speaker(reply)


def score_engagement(
    video_path: str | Path,
    start_s: float,
    end_s: float,
    config: Config | None = None,
) -> float | None:
    """Score a segment's visual engagement in [0,1] via the VLM (``None`` if off).

    Args:
        video_path: Source video path.
        start_s: Segment start in seconds.
        end_s: Segment end in seconds.
        config: Optional config override (defaults to :func:`get_config`).

    Returns:
        A clamped [0,1] engagement score, or ``None`` when disabled / unavailable.
    """
    cfg = config or get_config()
    if not cfg.vlm_enabled or not cfg.vlm_model:
        return None
    frames = _gather_frames(video_path, start_s, end_s, cfg)
    if not frames:
        return None
    reply = _vlm_chat(frames, _ENGAGEMENT_PROMPT, cfg)
    if reply is None:
        return None
    return parse_engagement(reply)


# end src/pipeline/vision.py
