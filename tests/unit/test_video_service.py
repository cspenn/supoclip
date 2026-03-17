# start tests/unit/test_video_service.py
"""Unit tests for src/services/video_service.py — pipeline orchestration.

Covers:
- ProcessingRequest / ProcessingResult dataclass construction and defaults
- process_video full happy-path flow with mocked pipeline modules
- Progress callback called at expected percentages
- Clip failures handled gracefully (individual clips skipped, task not failed)
- All-clips-fail scenario sets task to 'failed'
- Task status is updated in the DB at each stage
- YouTube URL triggers download; local path skips download
- Missing/non-existent local file returns error in result
- Download failure returns error in result
- Transcription failure returns error in result
- AI analysis failure returns error in result
- Broken progress callback does not abort the pipeline
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.analyze import TranscriptSegment
from src.services.video_service import (
    ProcessingRequest,
    ProcessingResult,
    _generate_clips_concurrently,
    _update_task_status,
    process_video,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

LONG_TRANSCRIPT = (
    "This is a much longer transcript that easily exceeds "
    "the fifty character minimum requirement. " * 3
)


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
    return TranscriptSegment(
        start_time=start, end_time=end, text=text, score=score, title=title
    )


def _make_request(
    source: str = YOUTUBE_URL,
    task_id: str = "task-001",
    **kwargs,
) -> ProcessingRequest:
    """Return a ProcessingRequest with sensible defaults."""
    return ProcessingRequest(source=source, task_id=task_id, **kwargs)


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

        with patch(
            "src.services.video_service.get_session", new=mock_session
        ):
            await _update_task_status("t1", "processing", 50, "Half done")

        assert mock_task.status == "processing"
        assert mock_task.progress == 50
        assert mock_task.progress_message == "Half done"

    @pytest.mark.asyncio
    async def test_noop_when_task_not_found(self) -> None:
        """When task does not exist, function returns without committing."""
        # Pass None so session.get() returns None (no task found).
        mock_session_factory = _make_mock_session(None)

        with patch(
            "src.services.video_service.get_session", new=mock_session_factory
        ):
            await _update_task_status("missing", "processing", 50)
        # No assertion on commit — test just verifies no exception is raised.

    @pytest.mark.asyncio
    async def test_error_stored_in_progress_message(self) -> None:
        """When error kwarg is provided, it is stored in progress_message."""
        mock_task = MagicMock()
        mock_session = _make_mock_session(mock_task)

        with patch(
            "src.services.video_service.get_session", new=mock_session
        ):
            await _update_task_status(
                "t1", "failed", 0, error="Download failed badly"
            )

        assert mock_task.status == "failed"
        assert mock_task.progress_message == "Download failed badly"


# ---------------------------------------------------------------------------
# _generate_clips_concurrently
# ---------------------------------------------------------------------------


class TestGenerateClipsConcurrently:
    """Tests for _generate_clips_concurrently()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_pipeline_clip_missing(
        self, tmp_path: Path
    ) -> None:
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

        with patch.dict("sys.modules", {"src.pipeline.clip": mock_module}):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg1, seg2],
                words=[],
                task_id="t1",
                clip_options=object(),
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
            if segment.start_time == 10.0:
                raise _ClipErr("bad segment")
            output_path.touch()

        mock_module = MagicMock()
        mock_module.generate_clip = partial_fail
        mock_module.ClipGenerationError = _ClipErr

        with patch.dict("sys.modules", {"src.pipeline.clip": mock_module}):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg1, seg2],
                words=[],
                task_id="t1",
                clip_options=object(),
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

        def cb(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        with patch.dict("sys.modules", {"src.pipeline.clip": mock_module}):
            await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg],
                words=[],
                task_id="t1",
                clip_options=object(),
                clips_dir=tmp_path,
                progress_callback=cb,
            )

        assert len(progress_calls) == 1
        pct, msg = progress_calls[0]
        assert 50 <= pct <= 100
        assert "1/1" in msg

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_clip_is_skipped(
        self, tmp_path: Path
    ) -> None:
        """Unexpected exceptions (not ClipGenerationError) are also swallowed."""
        seg = _make_segment()

        async def always_raises(source_video, segment, words, output_path, options):
            raise OSError("disk full")

        mock_module = MagicMock()
        mock_module.generate_clip = always_raises
        mock_module.ClipGenerationError = ValueError  # different from OSError

        with patch.dict("sys.modules", {"src.pipeline.clip": mock_module}):
            result = await _generate_clips_concurrently(
                source_video=tmp_path / "video.mp4",
                segments=[seg],
                words=[],
                task_id="t1",
                clip_options=object(),
                clips_dir=tmp_path,
            )

        assert result == []


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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=True
            ),
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=YOUTUBE_URL, task_id="t1")
            )

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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t2")
            )

        assert result.error is None
        assert len(result.clips) == 1

    # ---- Progress callback ----

    @pytest.mark.asyncio
    async def test_progress_callback_called_at_key_stages(
        self, tmp_path: Path
    ) -> None:
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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        def cb(pct: int, msg: str) -> None:
            progress_events.append((pct, msg))

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=True
            ),
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

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
            patch(
                "src.services.video_service.validate_youtube_url", return_value=True
            ),
            patch(
                "src.services.video_service.download_youtube_video",
                new_callable=AsyncMock,
                side_effect=DownloadError("Network timeout"),
            ),
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=YOUTUBE_URL, task_id="t4")
            )

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
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
            ),
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=missing, task_id="t5")
            )

        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_transcription_failure_returns_error(self, tmp_path: Path) -> None:
        """Transcription error is caught and returned in result.error."""
        fake_video = tmp_path / "video.mp4"
        fake_video.touch()
        mock_session = _make_mock_session()

        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(
            side_effect=RuntimeError("parakeet OOM")
        )
        mock_transcribe.format_transcript_text = MagicMock(return_value="")

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
            ),
            patch.dict("sys.modules", {"src.pipeline.transcribe": mock_transcribe}),
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t6")
            )

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
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
            ),
            patch(
                "src.services.video_service.analyze_transcript",
                new_callable=AsyncMock,
                side_effect=AnalysisError("No segments found"),
            ),
            patch.dict("sys.modules", {"src.pipeline.transcribe": mock_transcribe}),
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t7")
            )

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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t8")
            )

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
            if segment.start_time == 10.0:
                raise _ClipErr("bad segment")
            output_path.touch()

        mock_clip_module = MagicMock()
        mock_clip_module.generate_clip = partial_fail
        mock_clip_module.ClipGenerationError = _ClipErr
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t9")
            )

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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t10")
            )

        assert result.error is None
        # task.status is set to 'completed' by the last _update_task_status call.
        assert mock_task.status == "completed"

    # ---- Defensive callback handling ----

    @pytest.mark.asyncio
    async def test_broken_progress_callback_does_not_abort_pipeline(
        self, tmp_path: Path
    ) -> None:
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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

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
        mock_clip_module.ClipOptions = MagicMock(return_value=object())

        mock_transcription = []
        mock_transcribe = MagicMock()
        mock_transcribe.transcribe_video = AsyncMock(return_value=mock_transcription)
        mock_transcribe.format_transcript_text = MagicMock(return_value=LONG_TRANSCRIPT)

        with (
            patch(
                "src.services.video_service.get_session",
                new=mock_session,
            ),
            patch(
                "src.services.video_service.validate_youtube_url", return_value=False
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
            patch("src.services.video_service.Config") as mock_cfg_cls,
        ):
            mock_cfg = MagicMock()
            mock_cfg.temp_dir = str(tmp_path)
            mock_cfg_cls.return_value = mock_cfg

            result = await process_video(
                _make_request(source=str(fake_video), task_id="t12")
            )

        assert result.error is None
        meta = result.clip_metadata[0]
        assert meta["start_time"] == 5.0
        assert meta["end_time"] == 25.0
        assert meta["text"] == "Key insight."
        assert meta["score"] == 0.88
        assert meta["title"] == "Insight"


# end tests/unit/test_video_service.py
