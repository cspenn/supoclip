# start tests/unit/test_vision.py
"""Unit tests for src/pipeline/vision.py — deterministic core + seam construction.

The live VLM network call is exercised in the e2e tier; here the seam
(:func:`_vlm_chat`) is tested with a patched transport (request construction +
error handling), and orchestration is tested by injecting real-shaped replies.
No test fakes a real-output assertion via mocks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.config import Config
from src.pipeline import vision
from src.pipeline.vision import (
    ActiveSpeaker,
    build_vlm_payload,
    detect_active_speaker,
    extract_frame_b64,
    extract_json,
    parse_active_speaker,
    parse_engagement,
    sample_timestamps,
    score_engagement,
)

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_video.mp4"

# A realistic reasoning-laden Qwen reply (chain-of-thought, then fenced JSON).
_REAL_SPEAKER_REPLY = (
    "The user wants the active speaker.\n"
    "1. Left feed: a man, mouth open, gesturing.\n"
    "2. Right feed: a woman, mouth closed.\n\n"
    '{"active_speaker": "left", "confidence": 0.9}'
)
_REAL_ENGAGEMENT_REPLY = 'Thinking... lots of motion.\nFINAL:\n{"engagement": 0.85}'


def _cfg(**kw: object) -> Config:
    """Build a Config with VLM enabled by default for orchestration tests."""
    base: dict[str, object] = {
        "VLM_ENABLED": True,
        "VLM_MODEL": "Qwen3.6-35B-A3B-Mixed-4-8",
        "VLM_FRAMES_PER_CLIP": 3,
    }
    base.update(kw)
    return Config(**base)  # type: ignore[arg-type]


class TestSampleTimestamps:
    def test_single_sample(self) -> None:
        assert sample_timestamps(10.0, 20.0, 1) == [10.0]

    def test_zero_length_segment_collapses(self) -> None:
        assert sample_timestamps(5.0, 5.0, 4) == [5.0]

    def test_end_before_start_collapses(self) -> None:
        assert sample_timestamps(8.0, 2.0, 4) == [8.0]

    def test_even_spacing_includes_endpoints(self) -> None:
        ts = sample_timestamps(0.0, 10.0, 3)
        assert ts == [0.0, 5.0, 10.0]

    def test_non_positive_samples_collapses(self) -> None:
        assert sample_timestamps(0.0, 10.0, 0) == [0.0]


class TestExtractFrame:
    def test_real_fixture_frame(self) -> None:
        """A real frame extracts to a non-trivial base64 JPEG."""
        b64 = extract_frame_b64(_FIXTURE, 1.0, 256)
        assert b64 is not None
        assert len(b64) > 100

    def test_missing_file_returns_none(self) -> None:
        assert extract_frame_b64("/no/such/video.mp4", 1.0, 256) is None

    def test_subprocess_error_returns_none(self) -> None:
        with patch("src.pipeline.vision.subprocess.run", side_effect=OSError("boom")):
            assert extract_frame_b64(_FIXTURE, 1.0, 256) is None


class TestExtractJson:
    def test_returns_last_object(self) -> None:
        assert extract_json('{"a": 1} noise {"b": 2}') == {"b": 2}

    def test_reasoning_then_json(self) -> None:
        assert extract_json(_REAL_SPEAKER_REPLY) == {"active_speaker": "left", "confidence": 0.9}

    def test_no_json_returns_none(self) -> None:
        assert extract_json("no json here") is None

    def test_invalid_json_skipped(self) -> None:
        # The trailing {...} is invalid; falls back to the earlier valid one.
        assert extract_json('{"ok": 1} then {bad json}') == {"ok": 1}


class TestParseActiveSpeaker:
    def test_valid(self) -> None:
        res = parse_active_speaker(_REAL_SPEAKER_REPLY)
        assert res == ActiveSpeaker(side="left", confidence=0.9)

    def test_invalid_side_returns_none(self) -> None:
        assert parse_active_speaker('{"active_speaker": "middle"}') is None

    def test_no_json_returns_none(self) -> None:
        assert parse_active_speaker("nothing") is None

    def test_confidence_clamped_and_defaulted(self) -> None:
        assert parse_active_speaker('{"active_speaker": "right", "confidence": 5}').confidence == 1.0
        assert parse_active_speaker('{"active_speaker": "right", "confidence": -1}').confidence == 0.0
        assert parse_active_speaker('{"active_speaker": "right", "confidence": "x"}').confidence == 0.0
        assert parse_active_speaker('{"active_speaker": "right"}').confidence == 0.0


class TestParseEngagement:
    def test_valid(self) -> None:
        assert parse_engagement(_REAL_ENGAGEMENT_REPLY) == pytest.approx(0.85)

    def test_missing_key_returns_none(self) -> None:
        assert parse_engagement('{"other": 1}') is None

    def test_no_json_returns_none(self) -> None:
        assert parse_engagement("none") is None


class TestBuildPayload:
    def test_payload_structure(self) -> None:
        payload = build_vlm_payload(["AAA", "BBB"], "prompt?", _cfg(VLM_MAX_TOKENS=321))
        assert payload["model"] == "Qwen3.6-35B-A3B-Mixed-4-8"
        assert payload["max_tokens"] == 321
        content = payload["messages"][0]["content"]
        images = [p for p in content if p["type"] == "image_url"]
        texts = [p for p in content if p["type"] == "text"]
        assert len(images) == 2
        assert images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,AAA")
        assert texts[0]["text"] == "prompt?"


class TestVlmChatSeam:
    def test_success_returns_content(self) -> None:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}
        with patch("src.pipeline.vision.httpx.post", return_value=resp) as mock_post:
            out = vision._vlm_chat(["AAA"], "p", _cfg(VLM_BASE_URL="http://x/v1", VLM_API_KEY="k"))
        assert out == "hi"
        # request construction: correct URL, auth header, and JSON body.
        args, kwargs = mock_post.call_args
        assert args[0] == "http://x/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer k"
        assert kwargs["json"]["model"] == "Qwen3.6-35B-A3B-Mixed-4-8"

    def test_http_error_returns_none(self) -> None:
        with patch("src.pipeline.vision.httpx.post", side_effect=httpx.ConnectError("down")):
            assert vision._vlm_chat(["AAA"], "p", _cfg()) is None

    def test_malformed_response_returns_none(self) -> None:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"unexpected": True}
        with patch("src.pipeline.vision.httpx.post", return_value=resp):
            assert vision._vlm_chat(["AAA"], "p", _cfg()) is None


class TestDetectActiveSpeaker:
    def test_disabled_returns_none(self) -> None:
        assert detect_active_speaker(_FIXTURE, 0.0, 2.0, Config(VLM_ENABLED=False)) is None

    def test_enabled_without_model_returns_none(self) -> None:
        assert detect_active_speaker(_FIXTURE, 0.0, 2.0, _cfg(VLM_MODEL="")) is None

    def test_frame_extract_failure_returns_none(self) -> None:
        with patch("src.pipeline.vision.extract_frame_b64", return_value=None):
            assert detect_active_speaker(_FIXTURE, 0.0, 2.0, _cfg()) is None

    def test_vlm_failure_returns_none(self) -> None:
        with (
            patch("src.pipeline.vision.extract_frame_b64", return_value="AAA"),
            patch("src.pipeline.vision._vlm_chat", return_value=None),
        ):
            assert detect_active_speaker(_FIXTURE, 0.0, 2.0, _cfg()) is None

    def test_success_parses_injected_reply(self) -> None:
        with (
            patch("src.pipeline.vision.extract_frame_b64", return_value="AAA"),
            patch("src.pipeline.vision._vlm_chat", return_value=_REAL_SPEAKER_REPLY),
        ):
            res = detect_active_speaker(_FIXTURE, 0.0, 2.0, _cfg())
        assert res == ActiveSpeaker(side="left", confidence=0.9)

    def test_uses_default_config_when_none(self) -> None:
        with patch("src.pipeline.vision.get_config", return_value=Config(VLM_ENABLED=False)):
            assert detect_active_speaker(_FIXTURE, 0.0, 2.0) is None


class TestScoreEngagement:
    def test_disabled_returns_none(self) -> None:
        assert score_engagement(_FIXTURE, 0.0, 2.0, Config(VLM_ENABLED=False)) is None

    def test_no_frames_returns_none(self) -> None:
        with patch("src.pipeline.vision.extract_frame_b64", return_value=None):
            assert score_engagement(_FIXTURE, 0.0, 2.0, _cfg()) is None

    def test_vlm_failure_returns_none(self) -> None:
        with (
            patch("src.pipeline.vision.extract_frame_b64", return_value="AAA"),
            patch("src.pipeline.vision._vlm_chat", return_value=None),
        ):
            assert score_engagement(_FIXTURE, 0.0, 2.0, _cfg()) is None

    def test_success_parses_injected_reply(self) -> None:
        with (
            patch("src.pipeline.vision.extract_frame_b64", return_value="AAA"),
            patch("src.pipeline.vision._vlm_chat", return_value=_REAL_ENGAGEMENT_REPLY),
        ):
            assert score_engagement(_FIXTURE, 0.0, 2.0, _cfg()) == pytest.approx(0.85)


# end tests/unit/test_vision.py
