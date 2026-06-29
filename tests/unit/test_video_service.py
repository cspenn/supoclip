# start tests/unit/test_video_service.py
"""Unit tests for src/services/video_service.py — pipeline orchestration.

Covers:
- ProcessingRequest / ProcessingResult dataclass construction and defaults
- process_video full happy-path flow with mocked pipeline modules
- Progress callback called at expected percentages
- Clip failures handled gracefully (individual clips skipped, task not failed)
- All-clips-fail scenario sets task to 'failed'
- Task status is updated in the DB at each stage
- error_message column is populated on failure
- YouTube URL triggers download; local path skips download
- Missing/non-existent local file returns error in result
- Download failure returns error in result
- Transcription failure returns error in result
- AI analysis failure returns error in result
- Broken progress callback does not abort the pipeline
- Clip generation concurrency is bounded by max_workers
- Re-processing a task does not create duplicate clip rows
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.analyze import TranscriptSegment
from src.pipeline.clip import ClipOptions
from src.pipeline.clip import TranscriptSegment as ClipTranscriptSegment
from src.services.video_service import (
    ProcessingRequest,
    ProcessingResult,
    _delete_existing_clips,
    _generate_clips_concurrently,
    _list_transition_files,
    _options_for_clip,
    _positive_number,
    _rerank_by_engagement,
    _resolve_active_speaker_side,
    _save_generated_clip,
    _select_transition,
    _transition_pool,
    _update_task_status,
    process_video,
)


class TestResolveActiveSpeakerSide:
    """Tests for the per-segment active-speaker side resolution (duo/multi)."""

    @pytest.mark.asyncio
    async def test_single_mode_skips_vlm(self) -> None:
        """single content never invokes the VLM and returns None."""
        with patch("src.pipeline.vision.detect_active_speaker") as mock_detect:
            side = await _resolve_active_speaker_side(Path("/v.mp4"), 0.0, 2.0, "single")
        assert side is None
        mock_detect.assert_not_called()

    @pytest.mark.asyncio
    async def test_duo_mode_returns_detected_side(self) -> None:
        """duo content threads the VLM-detected side through."""
        from src.pipeline.vision import ActiveSpeaker

        with patch(
            "src.pipeline.vision.detect_active_speaker",
            return_value=ActiveSpeaker(side="right", confidence=0.9),
        ):
            side = await _resolve_active_speaker_side(Path("/v.mp4"), 0.0, 2.0, "duo")
        assert side == "right"

    @pytest.mark.asyncio
    async def test_duo_mode_none_when_unavailable(self) -> None:
        """When detection returns None (disabled/failed), the side is None."""
        with patch("src.pipeline.vision.detect_active_speaker", return_value=None):
            side = await _resolve_active_speaker_side(Path("/v.mp4"), 0.0, 2.0, "multi")
        assert side is None


class TestOptionsForClipActiveSpeaker:
    """Tests for _options_for_clip's active-speaker-side assignment."""

    def test_side_applied_to_options(self) -> None:
        """A detected side is written onto the per-clip options copy."""
        base = ClipOptions()
        result = _options_for_clip(base, 0, [], active_speaker_side="left")
        assert result is not base
        assert result.active_speaker_side == "left"  # type: ignore[union-attr]


class TestRerankByEngagement:
    """Tests for engagement-based segment re-ranking."""

    @pytest.mark.asyncio
    async def test_disabled_returns_unchanged(self) -> None:
        """With re-ranking off, segment order is untouched."""
        segs = [_make_segment(start=0.0), _make_segment(start=10.0)]
        cfg = SimpleNamespace(vlm_rerank_enabled=False)
        with patch("src.services.video_service.get_config", return_value=cfg):
            out = await _rerank_by_engagement(Path("/v.mp4"), segs)
        assert out == segs

    @pytest.mark.asyncio
    async def test_empty_returns_unchanged(self) -> None:
        """No segments → nothing to do."""
        cfg = SimpleNamespace(vlm_rerank_enabled=True)
        with patch("src.services.video_service.get_config", return_value=cfg):
            assert await _rerank_by_engagement(Path("/v.mp4"), []) == []

    @pytest.mark.asyncio
    async def test_orders_by_visual_engagement(self) -> None:
        """With pure visual weight, the most engaging segment sorts first."""
        first = _make_segment(start=0.0, score=0.5)
        second = _make_segment(start=10.0, score=0.6)
        cfg = SimpleNamespace(vlm_rerank_enabled=True, vlm_transcript_weight=0.0, vlm_visual_weight=1.0)

        def fake_score(_video: object, start: float, _end: float, *a: object) -> float:
            return 0.9 if start == 0.0 else 0.1

        with (
            patch("src.services.video_service.get_config", return_value=cfg),
            patch("src.pipeline.vision.score_engagement", side_effect=fake_score),
        ):
            out = await _rerank_by_engagement(Path("/v.mp4"), [second, first])
        assert out[0] is first  # higher engagement despite lower transcript score

    @pytest.mark.asyncio
    async def test_falls_back_to_transcript_when_no_visual(self) -> None:
        """When the VLM yields no engagement, the transcript score orders segments."""
        low = _make_segment(start=0.0, score=0.3)
        high = _make_segment(start=10.0, score=0.8)
        cfg = SimpleNamespace(vlm_rerank_enabled=True, vlm_transcript_weight=1.0, vlm_visual_weight=0.0)
        with (
            patch("src.services.video_service.get_config", return_value=cfg),
            patch("src.pipeline.vision.score_engagement", return_value=None),
        ):
            out = await _rerank_by_engagement(Path("/v.mp4"), [low, high])
        assert out[0] is high


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

LONG_TRANSCRIPT = "This is a much longer transcript that easily exceeds the fifty character minimum requirement. " * 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(
    start: float = 10.0,
    end: float = 30.0,
    text: str = "The main insight here is genuinely valuable.",
    score: float = 0.9,
    title: str = "Great Clip",
) -> TranscriptSegment:
    """Return a TranscriptSegment with sensible defaults."""
    return TranscriptSegment(start_time=start, end_time=end, text=text, score=score, title=title)


def _make_request(
    source: str = YOUTUBE_URL,
    task_id: str = "task-001",
    **kwargs,
) -> ProcessingRequest:
    """Return a ProcessingRequest with sensible defaults."""
    return ProcessingRequest(source=source, task_id=task_id, **kwargs)


def _make_cfg(tmp_path: Path, max_workers: int = 4) -> MagicMock:
    """Return a mock config exposing temp_dir and max_workers.

    Used to patch ``src.services.video_service.get_config``. ``max_workers``
    must be a real int so the bounding semaphore can be constructed.

    Args:
        tmp_path: Directory used as the configured temp_dir.
        max_workers: Concurrency bound surfaced to the service.

    Returns:
        A MagicMock standing in for the Config singleton.
    """
    cfg = MagicMock()
    cfg.temp_dir = str(tmp_path)
    cfg.max_workers = max_workers
    # Vision features default OFF so process_video tests exercise the deterministic
    # path (the VLM seam is covered separately and in the e2e tier).
    cfg.vlm_rerank_enabled = False
    return cfg


_SENTINEL = object()


def _make_mock_session(task: object = _SENTINEL):
    """Return an asynccontextmanager factory that yields a mock AsyncSession.

    Used to patch ``src.services.video_service.get_session``.  The returned
    callable is decorated with ``@asynccontextmanager`` so it can be used
    directly as a ``patch`` target replacement.

    Args:
        task: The object returned by session.get(). Pass ``None`` to simulate
              a missing task. Defaults to a fresh MagicMock.

    Returns:
        An async context manager factory suitable for patching get_session.
    """
    from contextlib import asynccontextmanager

    resolved_task = MagicMock() if task is _SENTINEL else task
    session = AsyncMock()
    session.get = AsyncMock(return_value=resolved_task)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


# ---------------------------------------------------------------------------
# ProcessingRequest dataclass
# ---------------------------------------------------------------------------


class TestProcessingRequest:
    """Tests for ProcessingRequest dataclass."""

    def test_required_fields_stored(self) -> None:
        """source and task_id are stored correctly."""
        req = ProcessingRequest(source=YOUTUBE_URL, task_id="t1")
        assert req.source == YOUTUBE_URL
        assert req.task_id == "t1"

    def test_default_min_clip_length(self) -> None:
        """Default min_clip_length is 15."""
        req = ProcessingRequest(source=YOUTUBE_URL, task_id="t1")
        assert req.min_clip_length == 15

    def test_default_max_clip_length(self) -> None:
        """Default max_clip_length is 45."""
        req = ProcessingRequest(source=YOUTUBE_URL, task_id="t1")
        assert req.max_clip_length == 45

    def test_default_output_resolution(self) -> None:
        """Default output_resolution is '1080p'."""
        req = ProcessingRequest(source=YOUTUBE_URL, task_id="t1")
        assert req.output_resolution == "1080p"

    def test_default_optional_fields_are_none(self) -> None:
        """subtitle_style, logo_path, and custom_prompt default to None."""
        req = ProcessingRequest(source=YOUTUBE_URL, task_id="t1")
        assert req.subtitle_style is None
        assert req.logo_path is None
        assert req.custom_prompt is None

    def test_custom_values_accepted(self) -> None:
        """All fields accept non-default values."""
        req = ProcessingRequest(
            source="/local/video.mp4",
            task_id="t2",
            min_clip_length=20,
            max_clip_length=60,
            output_resolution="720p",
            logo_path=Path("/logo.png"),
            custom_prompt="Focus on comedy.",
        )
        assert req.min_clip_length == 20
        assert req.max_clip_length == 60
        assert req.output_resolution == "720p"
        assert req.logo_path == Path("/logo.png")
        assert req.custom_prompt == "Focus on comedy."


# ---------------------------------------------------------------------------
# ProcessingResult dataclass
# ---------------------------------------------------------------------------


class TestProcessingResult:
    """Tests for ProcessingResult dataclass."""

    def test_minimal_construction(self) -> None:
        """Only task_id is required; clips and clip_metadata default to empty lists."""
        result = ProcessingResult(task_id="t1")
        assert result.task_id == "t1"
        assert result.clips == []
        assert result.clip_metadata == []
        assert result.error is None

    def test_error_field_stored(self) -> None:
        """Error field stores the failure message."""
        result = ProcessingResult(task_id="t1", error="Something went wrong")
        assert result.error == "Something went wrong"

    def test_clips_and_metadata_stored(self) -> None:
        """clips and clip_metadata are populated correctly."""
        clips = [Path("/tmp/clip_01.mp4"), Path("/tmp/clip_02.mp4")]
        metadata = [{"start_time": 10.0, "end_time": 30.0}]
        result = ProcessingResult(task_id="t1", clips=clips, clip_metadata=metadata)
        assert len(result.clips) == 2
        assert result.clip_metadata[0]["start_time"] == 10.0

    def test_independent_default_lists(self) -> None:
        """Two separate instances have independent default lists (no shared mutable default)."""
        r1 = ProcessingResult(task_id="a")
        r2 = ProcessingResult(task_id="b")
        r1.clips.append(Path("/tmp/x.mp4"))
        assert r2.clips == []


# ---------------------------------------------------------------------------
# _update_task_status
# ---------------------------------------------------------------------------


class TestUpdateTaskStatus:
    """Tests for _update_task_status()."""

    @pytest.mark.asyncio
    async def test_updates_existing_task(self) -> None:
        """When task exists, its status / progress / message are updated."""
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        with patch("src.services.video_service.get_session", new=mock_session):
            await _update_task_status("t1", "processing", 50, "Half done")

        assert mock_task.status == "processing"
        assert mock_task.progress == 50
        assert mock_task.progress_message == "Half done"

    @pytest.mark.asyncio
    async def test_noop_when_task_not_found(self) -> None:
        """When task does not exist, function returns without committing."""
        # Pass None so session.get() returns None (no task found).
        mock_session_factory = _make_mock_session(None)

        with patch("src.services.video_service.get_session", new=mock_session_factory):
            await _update_task_status("missing", "processing", 50)
        # No assertion on commit — test just verifies no exception is raised.

    @pytest.mark.asyncio
    async def test_error_stored_in_progress_message(self) -> None:
        """When error kwarg is provided, it is mirrored into progress_message."""
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        with patch("src.services.video_service.get_session", new=mock_session):
            await _update_task_status("t1", "failed", 0, error="Download failed badly")

        assert mock_task.status == "failed"
        assert mock_task.progress_message == "Download failed badly"

    @pytest.mark.asyncio
    async def test_error_written_to_error_message_column(self) -> None:
        """When error kwarg is provided, it is persisted to error_message (H-7)."""
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        with patch("src.services.video_service.get_session", new=mock_session):
            await _update_task_status("t1", "failed", 0, error="ffmpeg exploded")

        assert mock_task.error_message == "ffmpeg exploded"

    @pytest.mark.asyncio
    async def test_error_message_not_touched_on_success(self) -> None:
        """A successful (no error) update never writes to error_message."""
        mock_task = MagicMock()
        # Start from a known sentinel so we can detect any unintended write.
        mock_task.error_message = None
        mock_session = _make_mock_session(mock_task)

        with patch("src.services.video_service.get_session", new=mock_session):
            await _update_task_status("t1", "completed", 100, "Complete")

        assert mock_task.error_message is None
        assert mock_task.progress_message == "Complete"


# ---------------------------------------------------------------------------
# _generate_clips_concurrently
# ---------------------------------------------------------------------------


class TestGenerateClipsConcurrently:
    """Tests for _generate_clips_concurrently()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_pipeline_clip_missing(self, tmp_path: Path) -> None:
        """Returns empty list when src.pipeline.clip is not importable."""
        with patch.dict("sys.modules", {"src.pipeline.clip": None}):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[_make_segment()],
                words=[],
                task_id="t1",
                clip_options=object(),
                clips_dir=tmp_path,
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_successful_clip_generation(self, tmp_path: Path) -> None:
        """Returns (path, segment) tuples for all successfully generated clips."""
        seg1 = _make_segment(start=10.0, end=30.0)
        seg2 = _make_segment(start=60.0, end=90.0)

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = fake_generate
        mock_module.ClipGenerationError = Exception
        mock_module.TranscriptSegment = ClipTranscriptSegment

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg1, seg2],
                words=[],
                task_id="t1",
                clip_options=None,
                clips_dir=tmp_path,
            )

        assert len(result) == 2
        # Sorted by start_time ascending.
        assert result[0][1].start_time == 10.0
        assert result[1][1].start_time == 60.0

    @pytest.mark.asyncio
    async def test_failed_clip_is_skipped(self, tmp_path: Path) -> None:
        """A clip that fails is skipped; remaining clips still returned."""
        seg1 = _make_segment(start=10.0, end=30.0)
        seg2 = _make_segment(start=60.0, end=90.0)

        class _ClipErr(Exception):
            pass

        async def partial_fail(source_video, segment, words, output_path, options):
            if segment.start_s == 10.0:
                raise _ClipErr("bad segment")
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = partial_fail
        mock_module.ClipGenerationError = _ClipErr
        mock_module.TranscriptSegment = ClipTranscriptSegment

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg1, seg2],
                words=[],
                task_id="t1",
                clip_options=None,
                clips_dir=tmp_path,
            )

        assert len(result) == 1
        assert result[0][1].start_time == 60.0

    @pytest.mark.asyncio
    async def test_progress_callback_called_per_clip(self, tmp_path: Path) -> None:
        """Progress callback is called once for each successfully generated clip."""
        seg = _make_segment()
        progress_calls: list[tuple[int, str]] = []

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = fake_generate
        mock_module.ClipGenerationError = Exception
        mock_module.TranscriptSegment = ClipTranscriptSegment

        def cb(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg],
                words=[],
                task_id="t1",
                clip_options=None,
                clips_dir=tmp_path,
                progress_callback=cb,
            )

        assert len(progress_calls) == 1
        pct, msg = progress_calls[0]
        assert 50 <= pct <= 100
        assert "1/1" in msg

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_clip_is_skipped(self, tmp_path: Path) -> None:
        """Unexpected exceptions (not ClipGenerationError) are also swallowed."""
        seg = _make_segment()

        async def always_raises(source_video, segment, words, output_path, options):
            raise OSError("disk full")

        mock_module = MagicMock()
        mock_module.generate_clip = always_raises
        mock_module.ClipGenerationError = ValueError  # different from OSError
        mock_module.TranscriptSegment = ClipTranscriptSegment

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg],
                words=[],
                task_id="t1",
                clip_options=None,
                clips_dir=tmp_path,
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_concurrency_is_bounded_by_max_workers(self, tmp_path: Path) -> None:
        """No more than max_workers clips run generate_clip concurrently (H-10)."""
        max_workers = 2
        seg_count = 6
        segments = [_make_segment(start=float(i * 100), end=float(i * 100 + 20)) for i in range(seg_count)]

        current = 0
        peak = 0
        counter_lock = asyncio.Lock()

        async def slow_generate(source_video, segment, words, output_path, options):
            nonlocal current, peak
            async with counter_lock:
                current += 1
                peak = max(peak, current)
            # Hold the slot long enough that, if unbounded, all would overlap.
            await asyncio.sleep(0.02)
            async with counter_lock:
                current -= 1
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = slow_generate
        mock_module.ClipGenerationError = Exception
        mock_module.TranscriptSegment = ClipTranscriptSegment

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path, max_workers=max_workers),
            ),
        ):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=segments,
                words=[],
                task_id="t1",
                clip_options=None,
                clips_dir=tmp_path,
            )

        assert len(result) == seg_count
        assert peak <= max_workers, f"peak concurrency {peak} exceeded {max_workers}"
        # Sanity: with 6 segments and a real semaphore, concurrency must have
        # actually reached the bound (otherwise the test proves nothing).
        assert peak == max_workers


# ---------------------------------------------------------------------------
# Clip persistence idempotency
# ---------------------------------------------------------------------------


class TestClipPersistenceIdempotency:
    """Tests for idempotent clip persistence (M-13) against a real database."""

    @pytest.mark.asyncio
    async def test_reprocessing_does_not_duplicate_clips(self, tmp_path: Path) -> None:
        """Re-running delete+save for a task leaves exactly one clip row."""
        from sqlalchemy import select

        from src.database import close_db, get_session, init_db
        from src.models import GeneratedClip, Task

        db_url = f"sqlite+aiosqlite:///{tmp_path / 'idempotency.db'}"
        await close_db()
        await init_db(db_url)
        try:
            async with get_session() as session:
                session.add(
                    Task(
                        id="dup-task",
                        source_url="https://example.com/v",
                        source_type="youtube",
                    )
                )

            seg = _make_segment()
            clip_path = Path("dup-task_clip_01.mp4")

            # Two full processing passes for the same task.
            for _ in range(2):
                await _delete_existing_clips("dup-task")
                await _save_generated_clip("dup-task", clip_path, seg, 0)

            async with get_session() as session:
                rows = (await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == "dup-task"))).scalars().all()

            assert len(rows) == 1
            assert rows[0].filename == "dup-task_clip_01.mp4"
        finally:
            await close_db()


# ---------------------------------------------------------------------------
# process_video — full pipeline
# ---------------------------------------------------------------------------


class TestProcessVideo:
    """Integration-style unit tests for process_video() with mocked pipeline."""

    # ---- Happy paths ----

    @pytest.mark.asyncio
    async def test_happy_path_youtube_two_clips(self, tmp_path: Path) -> None:
        """Full pipeline succeeds for a YouTube URL with two clips."""
        fake_video = tmp_path / "dQw4w9WgXcQ.mp4"
        fake_video.touch()
        seg1 = _make_segment(start=10.0, end=30.0)
        seg2 = _make_segment(start=60.0, end=90.0)
        mock_session = _make_mock_session()

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=True),
            patch(
                "src.services.video_service.download_youtube_video",
                new_callable=AsyncMock,
                return_value=fake_video,
            ),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg1, seg2],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=YOUTUBE_URL, task_id="t1"))

        assert result.error is None
        assert len(result.clips) == 2
        assert len(result.clip_metadata) == 2

    @pytest.mark.asyncio
    async def test_happy_path_local_file(self, tmp_path: Path) -> None:
        """Full pipeline succeeds for a local file path (no download step)."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()
        mock_session = _make_mock_session()

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t2"))

        assert result.error is None
        assert len(result.clips) == 1

    # ---- Progress callback ----

    @pytest.mark.asyncio
    async def test_progress_callback_called_at_key_stages(self, tmp_path: Path) -> None:
        """Progress callback is called with 0, 10, 20, 40, 50 and 100."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()
        mock_session = _make_mock_session()
        progress_events: list[tuple[int, str]] = []

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        def cb(pct: int, msg: str) -> None:
            progress_events.append((pct, msg))

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=True),
            patch(
                "src.services.video_service.download_youtube_video",
                new_callable=AsyncMock,
                return_value=fake_video,
            ),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            await process_video(
                _make_request(source=YOUTUBE_URL, task_id="t3"),
                progress_callback=cb,
            )

        pcts = [p for p, _ in progress_events]
        assert 0 in pcts, "Expected 0% (Preparing)"
        assert 10 in pcts, "Expected 10% (Downloading)"
        assert 20 in pcts, "Expected 20% (Transcribing)"
        assert 40 in pcts, "Expected 40% (Analyzing)"
        assert 50 in pcts, "Expected 50% (Generating clips)"
        assert 100 in pcts, "Expected 100% (Complete)"

    # ---- Failure cases ----

    @pytest.mark.asyncio
    async def test_download_failure_returns_error(self, tmp_path: Path) -> None:
        """DownloadError is caught and returned in result.error."""
        from src.pipeline.download import DownloadError

        mock_session = _make_mock_session()

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=True),
            patch(
                "src.services.video_service.download_youtube_video",
                new_callable=AsyncMock,
                side_effect=DownloadError("Network timeout"),
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=YOUTUBE_URL, task_id="t4"))

        assert result.error is not None
        assert "Network timeout" in result.error
        assert result.clips == []

    @pytest.mark.asyncio
    async def test_local_file_not_found_returns_error(self, tmp_path: Path) -> None:
        """Missing local file path returns an error in result.error."""
        mock_session = _make_mock_session()
        missing = str(tmp_path / "does_not_exist.mp4")

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=missing, task_id="t5"))

        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_transcription_failure_returns_error(self, tmp_path: Path) -> None:
        """Transcription error is caught and returned in result.error."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        mock_session = _make_mock_session()

        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(side_effect=RuntimeError("parakeet OOM"))
        mock_transcribe.format_transcript_text = MagicMock(return_value="")

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch.dict("sys.modules", {"src.pipeline.transcribe": mock_transcribe}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t6"))

        assert result.error is not None
        assert "parakeet OOM" in result.error

    @pytest.mark.asyncio
    async def test_analysis_failure_returns_error(self, tmp_path: Path) -> None:
        """AnalysisError is caught and returned in result.error."""
        from src.pipeline.analyze import AnalysisError

        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        mock_session = _make_mock_session()

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                side_effect=AnalysisError("No segments found"),
            ),
            patch.dict("sys.modules", {"src.pipeline.transcribe": mock_transcribe}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t7"))

        assert result.error is not None
        assert "No segments found" in result.error

    @pytest.mark.asyncio
    async def test_all_clips_fail_returns_error(self, tmp_path: Path) -> None:
        """When all clips fail to generate, result.error is set."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()
        mock_session = _make_mock_session()

        class _ClipErr(Exception):
            pass

        async def always_fail(source_video, segment, words, output_path, options):
            raise _ClipErr("ffmpeg crashed")

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = always_fail
        mock_clip_module.ClipGenerationError = _ClipErr
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t8"))

        assert result.error is not None
        assert result.clips == []

    @pytest.mark.asyncio
    async def test_partial_clip_failure_task_completes(self, tmp_path: Path) -> None:
        """When one clip fails but another succeeds, the task completes normally."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg1 = _make_segment(start=10.0, end=30.0)
        seg2 = _make_segment(start=60.0, end=90.0)
        mock_session = _make_mock_session()

        class _ClipErr(Exception):
            pass

        async def partial_fail(source_video, segment, words, output_path, options):
            if segment.start_s == 10.0:
                raise _ClipErr("bad segment")
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = partial_fail
        mock_clip_module.ClipGenerationError = _ClipErr
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg1, seg2],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t9"))

        assert result.error is None
        assert len(result.clips) == 1

    # ---- DB interactions ----

    @pytest.mark.asyncio
    async def test_task_status_set_to_completed_in_db(self, tmp_path: Path) -> None:
        """Task status is set to 'completed' in the database on success."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()

        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t10"))

        assert result.error is None
        # task.status is set to 'completed' by the last _update_task_status call.
        assert mock_task.status == "completed"

    # ---- Defensive callback handling ----

    @pytest.mark.asyncio
    async def test_broken_progress_callback_does_not_abort_pipeline(self, tmp_path: Path) -> None:
        """A progress callback that raises does not abort the pipeline."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()
        mock_session = _make_mock_session()

        def bad_cb(pct: int, msg: str) -> None:
            raise ValueError("callback crashed")

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            # Must not raise despite bad_cb raising ValueError on every call.
            result = await process_video(
                _make_request(source=str(fake_video), task_id="t11"),
                progress_callback=bad_cb,
            )

        assert result.error is None

    # ---- Result metadata ----

    @pytest.mark.asyncio
    async def test_clip_metadata_contains_expected_keys(self, tmp_path: Path) -> None:
        """Each item in clip_metadata has start_time, end_time, text, score, title."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment(start=5.0, end=25.0, text="Key insight.", score=0.88, title="Insight")
        mock_session = _make_mock_session()

        async def fake_generate(source_video, segment, words, output_path, options):
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = fake_generate
        mock_clip_module.ClipGenerationError = Exception
        mock_clip_module.ClipOptions = MagicMock(return_value=None)
        mock_clip_module.TranscriptSegment = ClipTranscriptSegment

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": mock_clip_module,
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t12"))

        assert result.error is None
        meta = result.clip_metadata[0]
        assert meta["start_time"] == 5.0
        assert meta["end_time"] == 25.0
        assert meta["text"] == "Key insight."
        assert meta["score"] == 0.88
        assert meta["title"] == "Insight"

    # ---- ImportError fallback paths (lazy imports) ----

    @pytest.mark.asyncio
    async def test_transcribe_import_error_returns_error_in_result(self, tmp_path: Path) -> None:
        """When src.pipeline.transcribe cannot be imported, error is returned.

        The ImportError from the transcribe module import is converted to a
        RuntimeError and surfaced in the result. This test verifies that:
        1. The error message is set correctly in the task status
        2. The result contains the error message
        3. No clips are generated
        4. error_message is persisted on the failing task (H-7)
        """
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        # Simulate src.pipeline.transcribe being unavailable by mocking it as None.
        # This will cause the import to fail with ImportError.
        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch.dict("sys.modules", {"src.pipeline.transcribe": None}),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t_transcribe_err"))

        assert result.error is not None
        assert "Transcription pipeline module not available" in result.error
        assert result.clips == []
        # Verify task status was updated to "failed" at 20% progress.
        assert mock_task.status == "failed"
        assert mock_task.progress == 20
        assert mock_task.progress_message == "Transcription pipeline module not available"
        assert mock_task.error_message == "Transcription pipeline module not available"

    @pytest.mark.asyncio
    async def test_clip_import_error_uses_none_options_fallback(self, tmp_path: Path) -> None:
        """When src.pipeline.clip cannot be imported, generation yields no clips.

        When the clip module is unavailable, ``ClipOptions`` resolves to None
        and ``_generate_clips_concurrently`` returns ``[]`` (it also fails to
        import the clip module). With segments present but no clips generated,
        the pipeline fails with "All clip generations failed".
        """
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        seg = _make_segment()
        mock_session = _make_mock_session()

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                return_value=[seg],
            ),
            patch.dict(
                "sys.modules",
                {
                    "src.pipeline.transcribe": mock_transcribe,
                    "src.pipeline.clip": None,  # Simulate import failure
                },
            ),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t_clip_err"))

        assert result.error is not None
        assert "All clip generations failed" in result.error
        assert result.clips == []


# ---------------------------------------------------------------------------
# Transition helpers (M-4: round-robin fade transitions)
# ---------------------------------------------------------------------------


class TestPositiveNumber:
    """Tests for the _positive_number defensive coercion helper."""

    def test_non_number_returns_default(self) -> None:
        """A non-numeric value (e.g. a mock attribute) falls back to default."""
        assert _positive_number(object(), 1800) == 1800.0

    def test_zero_or_negative_returns_default(self) -> None:
        """Zero and negatives are not positive, so the default is used."""
        assert _positive_number(0, 5.0) == 5.0
        assert _positive_number(-3, 5.0) == 5.0

    def test_positive_number_is_returned_as_float(self) -> None:
        """A positive int/float is returned as a float."""
        assert _positive_number(2, 9.0) == 2.0
        assert _positive_number(1.5, 9.0) == 1.5


class TestListTransitionFiles:
    """Tests for _list_transition_files directory scanning."""

    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        """A non-existent directory yields an empty list."""
        assert _list_transition_files(tmp_path / "nope") == []

    def test_returns_sorted_mp4_only(self, tmp_path: Path) -> None:
        """Only .mp4 files are returned, sorted by name."""
        (tmp_path / "b.mp4").touch()
        (tmp_path / "a.mp4").touch()
        (tmp_path / "notes.txt").touch()
        result = _list_transition_files(tmp_path)
        assert [p.name for p in result] == ["a.mp4", "b.mp4"]


class TestSelectTransition:
    """Tests for the round-robin _select_transition helper."""

    def test_empty_pool_returns_none(self) -> None:
        """No transitions available yields None."""
        assert _select_transition(0, []) is None

    def test_round_robin_cycles(self) -> None:
        """Selection cycles through the pool by clip index (N clips, M files)."""
        files = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
        assigned = [_select_transition(i, files) for i in range(7)]
        assert assigned == [
            files[0],
            files[1],
            files[2],
            files[0],
            files[1],
            files[2],
            files[0],
        ]


class TestTransitionPool:
    """Tests for _transition_pool config resolution."""

    def test_empty_when_no_dir(self) -> None:
        """A config without a transitions directory yields an empty pool."""
        assert _transition_pool(SimpleNamespace(TRANSITIONS_DIR=Path("/nope/here"))) == []

    def test_lists_transitions_from_dir(self, tmp_path: Path) -> None:
        """Every .mp4 in TRANSITIONS_DIR joins the round-robin pool."""
        (tmp_path / "b.mp4").touch()
        (tmp_path / "a.mp4").touch()
        cfg = SimpleNamespace(TRANSITIONS_DIR=tmp_path)
        assert [p.name for p in _transition_pool(cfg)] == ["a.mp4", "b.mp4"]


class TestOptionsForClip:
    """Tests for the per-clip _options_for_clip transition assignment."""

    def test_none_base_returns_none(self) -> None:
        """A None base (clip module unavailable) passes through unchanged."""
        assert _options_for_clip(None, 0, [Path("a.mp4")]) is None

    def test_no_transitions_returns_base_unchanged(self) -> None:
        """An empty transition pool leaves the base options unchanged."""
        base = ClipOptions()
        assert _options_for_clip(base, 0, []) is base

    def test_assigns_transition_when_selected(self) -> None:
        """When a transition is selected, a copy carrying its path is returned."""
        base = ClipOptions(output_resolution="720p")
        result = _options_for_clip(base, 0, [Path("a.mp4")])
        assert result is not base
        assert result is not None
        assert result.transition_path == Path("a.mp4")
        # Other fields are preserved.
        assert result.output_resolution == "720p"

    def test_round_robin_assigns_per_index(self) -> None:
        """Different clip indices receive transitions cycling through the pool."""
        base = ClipOptions()
        pool = [Path("a.mp4"), Path("b.mp4")]
        paths = [_options_for_clip(base, i, pool).transition_path for i in range(3)]  # type: ignore[union-attr]
        assert paths == [Path("a.mp4"), Path("b.mp4"), Path("a.mp4")]


class TestConcurrentTransitionWiring:
    """The round-robin transition reaches generate_clip via _generate_clips_concurrently."""

    @pytest.mark.asyncio
    async def test_transition_assigned_to_each_clip(self, tmp_path: Path) -> None:
        """With transitions configured, each clip receives a transition path."""
        (tmp_path / "t.mp4").touch()
        seg = _make_segment()
        captured_transitions: list[object] = []

        async def fake_generate(source_video, segment, words, output_path, options):
            captured_transitions.append(options.transition_path)
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = fake_generate
        mock_module.ClipGenerationError = Exception
        mock_module.TranscriptSegment = ClipTranscriptSegment

        cfg = SimpleNamespace(
            temp_dir=str(tmp_path),
            max_workers=2,
            TRANSITIONS_DIR=tmp_path,
        )

        with (
            patch.dict("sys.modules", {"src.pipeline.clip": mock_module}),
            patch("src.services.video_service.get_config", return_value=cfg),
        ):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg],
                words=[],
                task_id="t1",
                clip_options=ClipOptions(),
                clips_dir=tmp_path,
            )

        assert len(result) == 1
        assert captured_transitions == [tmp_path / "t.mp4"]


# ---------------------------------------------------------------------------
# Transcription timeout (M-3)
# ---------------------------------------------------------------------------


class TestTranscriptionTimeout:
    """Tests for the transcription wall-clock timeout."""

    @pytest.mark.asyncio
    async def test_transcription_timeout_fails_loudly(self, tmp_path: Path) -> None:
        """A transcription timeout surfaces a clear error and fails the task."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = MagicMock(return_value=[])
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        def _raise_timeout(coro, timeout=None):
            # Close the wrapped coroutine to avoid "never awaited" warnings.
            coro.close()
            raise TimeoutError

        with (
            patch("src.services.video_service.get_session", new=mock_session),
            patch("src.services.video_service.validate_youtube_url", return_value=False),
            patch.dict("sys.modules", {"src.pipeline.transcribe": mock_transcribe}),
            patch("asyncio.wait_for", side_effect=_raise_timeout),
            patch(
                "src.services.video_service.get_config",
                return_value=_make_cfg(tmp_path),
            ),
        ):
            result = await process_video(_make_request(source=str(fake_video), task_id="t_timeout"))

        assert result.error is not None
        assert "Transcription timed out" in result.error
        assert mock_task.status == "failed"
        assert mock_task.progress == 20


# end tests/unit/test_video_service.py
