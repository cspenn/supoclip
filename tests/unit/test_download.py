# start tests/unit/test_download.py
"""Unit tests for src/pipeline/download.py.

Covers:
- validate_youtube_url with valid and invalid URLs
- find_downloaded_file with various directory states
- download_youtube_video with mocked yt-dlp
- get_video_info with mocked yt-dlp
- DownloadError raised on yt-dlp failure
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp  # type: ignore

from src.pipeline.download import (
    DownloadError,
    _extract_video_id,
    _run_ydl_download,
    _run_ydl_info,
    find_downloaded_file,
    validate_youtube_url,
)

# ---------------------------------------------------------------------------
# validate_youtube_url
# ---------------------------------------------------------------------------


class TestValidateYouTubeUrl:
    """Tests for validate_youtube_url."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/live/jWFPN4bAFnA",
        ],
    )
    def test_valid_youtube_urls(self, url: str) -> None:
        """Returns True for all standard YouTube URL formats."""
        assert validate_youtube_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "https://vimeo.com/12345678",
            "https://www.youtube.com/watch",  # no v param
            "https://www.youtube.com/watch?v=short",  # too short
            "   ",
        ],
    )
    def test_invalid_youtube_urls(self, url: str) -> None:
        """Returns False for non-YouTube or malformed URLs."""
        assert validate_youtube_url(url) is False

    def test_non_string_input(self) -> None:
        """Returns False when a non-string is passed."""
        assert validate_youtube_url(None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _extract_video_id
# ---------------------------------------------------------------------------


class TestExtractVideoId:
    """Tests for _extract_video_id (internal helper)."""

    def test_standard_url(self) -> None:
        """Extracts ID from standard watch URL."""
        result = _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_short_url(self) -> None:
        """Extracts ID from youtu.be short URL."""
        result = _extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self) -> None:
        """Extracts ID even when URL has extra query parameters."""
        result = _extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s&list=PL123"
        )
        assert result == "dQw4w9WgXcQ"

    def test_returns_none_for_empty(self) -> None:
        """Returns None for empty string."""
        assert _extract_video_id("") is None

    def test_returns_none_for_non_youtube(self) -> None:
        """Returns None for non-YouTube URLs."""
        assert _extract_video_id("https://example.com/video") is None

    def test_extract_video_id_live_url(self) -> None:
        """Extracts ID from youtube.com/live/<id> URL."""
        result = _extract_video_id("https://www.youtube.com/live/jWFPN4bAFnA")
        assert result == "jWFPN4bAFnA"


# ---------------------------------------------------------------------------
# find_downloaded_file
# ---------------------------------------------------------------------------


class TestFindDownloadedFile:
    """Tests for find_downloaded_file."""

    def test_finds_mp4_by_stem(self, tmp_path: Path) -> None:
        """Returns the mp4 path when searching by exact stem."""
        video = tmp_path / "abc123defgh.mp4"
        video.write_bytes(b"fake video data")

        result = find_downloaded_file(tmp_path, base_stem="abc123defgh")
        assert result == video

    def test_finds_mkv_by_stem(self, tmp_path: Path) -> None:
        """Returns the mkv path when an mp4 is absent but mkv exists."""
        video = tmp_path / "abc123defgh.mkv"
        video.write_bytes(b"fake video data")

        result = find_downloaded_file(tmp_path, base_stem="abc123defgh")
        assert result == video

    def test_finds_webm_by_stem(self, tmp_path: Path) -> None:
        """Returns the webm path when only webm is present."""
        video = tmp_path / "abc123defgh.webm"
        video.write_bytes(b"fake video data")

        result = find_downloaded_file(tmp_path, base_stem="abc123defgh")
        assert result == video

    def test_returns_none_for_empty_directory(self, tmp_path: Path) -> None:
        """Returns None when the directory has no video files."""
        result = find_downloaded_file(tmp_path)
        assert result is None

    def test_returns_none_when_stem_not_found(self, tmp_path: Path) -> None:
        """Returns None when the specific stem has no matching file."""
        (tmp_path / "other_video.mp4").write_bytes(b"other")
        result = find_downloaded_file(tmp_path, base_stem="missing_stem")
        assert result is None

    def test_returns_most_recent_without_stem(self, tmp_path: Path) -> None:
        """Returns the most recently modified file when no stem provided."""
        import time

        old_file = tmp_path / "old.mp4"
        old_file.write_bytes(b"old video")
        time.sleep(0.01)
        new_file = tmp_path / "new.mp4"
        new_file.write_bytes(b"new video")

        result = find_downloaded_file(tmp_path)
        assert result == new_file

    def test_ignores_non_video_files(self, tmp_path: Path) -> None:
        """Ignores files with non-video extensions."""
        (tmp_path / "notes.txt").write_bytes(b"not a video")
        (tmp_path / "thumb.jpg").write_bytes(b"not a video")
        result = find_downloaded_file(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# download_youtube_video (mocked)
# ---------------------------------------------------------------------------


class TestDownloadYoutubeVideo:
    """Tests for download_youtube_video with mocked yt-dlp."""

    @pytest.mark.asyncio
    async def test_successful_download(self, tmp_path: Path) -> None:
        """Returns the path of the downloaded file on success."""
        video_file = tmp_path / "dQw4w9WgXcQ.mp4"

        def fake_download(_url: str, _opts: dict) -> None:
            video_file.write_bytes(b"fake video")

        with patch("src.pipeline.download._run_ydl_download", side_effect=fake_download):
            from src.pipeline.download import download_youtube_video

            result = await download_youtube_video(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_dir=tmp_path,
            )

        assert result == video_file

    @pytest.mark.asyncio
    async def test_raises_download_error_on_invalid_url(self, tmp_path: Path) -> None:
        """Raises DownloadError for a URL with no valid video ID."""
        from src.pipeline.download import download_youtube_video

        with pytest.raises(DownloadError, match="Could not extract video ID"):
            await download_youtube_video("https://example.com/not-youtube", tmp_path)

    @pytest.mark.asyncio
    async def test_raises_download_error_when_yt_dlp_fails(self, tmp_path: Path) -> None:
        """Raises DownloadError when yt-dlp itself raises."""
        with patch(
            "src.pipeline.download._run_ydl_download",
            side_effect=DownloadError("yt-dlp error"),
        ):
            from src.pipeline.download import download_youtube_video

            with pytest.raises(DownloadError):
                await download_youtube_video(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    output_dir=tmp_path,
                )

    @pytest.mark.asyncio
    async def test_raises_when_no_file_after_download(self, tmp_path: Path) -> None:
        """Raises DownloadError when yt-dlp succeeds but no file is found."""
        with patch("src.pipeline.download._run_ydl_download", return_value=None):
            from src.pipeline.download import download_youtube_video

            with pytest.raises(DownloadError, match="No video file found"):
                await download_youtube_video(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    output_dir=tmp_path,
                )


# ---------------------------------------------------------------------------
# get_video_info (mocked)
# ---------------------------------------------------------------------------


class TestGetVideoInfo:
    """Tests for get_video_info with mocked yt-dlp."""

    @pytest.mark.asyncio
    async def test_returns_metadata_dict(self) -> None:
        """Returns a dict with expected keys on success."""
        fake_raw = {
            "id": "dQw4w9WgXcQ",
            "title": "Never Gonna Give You Up",
            "description": "Official music video",
            "duration": 212,
            "uploader": "Rick Astley",
            "upload_date": "20091024",
            "view_count": 1_000_000_000,
            "like_count": 15_000_000,
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
            "format_id": "22",
            "resolution": "1280x720",
            "fps": 30,
            "filesize": None,
        }

        with patch("src.pipeline.download._run_ydl_info", return_value=fake_raw):
            from src.pipeline.download import get_video_info

            result = await get_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result["title"] == "Never Gonna Give You Up"
        assert result["duration"] == 212
        assert result["id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_raises_download_error_on_failure(self) -> None:
        """Raises DownloadError when yt-dlp info extraction fails."""
        with patch(
            "src.pipeline.download._run_ydl_info",
            side_effect=DownloadError("network error"),
        ):
            from src.pipeline.download import get_video_info

            with pytest.raises(DownloadError):
                await get_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


# ---------------------------------------------------------------------------
# DownloadError
# ---------------------------------------------------------------------------


class TestDownloadError:
    """Tests for DownloadError exception class."""

    def test_is_exception(self) -> None:
        """DownloadError is an Exception subclass."""
        assert issubclass(DownloadError, Exception)

    def test_message_preserved(self) -> None:
        """DownloadError preserves the message string."""
        err = DownloadError("something went wrong")
        assert str(err) == "something went wrong"


# ---------------------------------------------------------------------------
# _extract_video_id — urlparse fallback path (lines 119-122)
# ---------------------------------------------------------------------------


class TestExtractVideoIdUrlparseFallback:
    """Tests for the urlparse ?v= fallback in _extract_video_id."""

    def test_extracts_id_via_urlparse_fallback(self) -> None:
        """Returns ID from ?v= param when none of the regex patterns match.

        A URL with no path (only a bare domain and ?v= query) bypasses all
        compiled regex patterns and executes the urlparse fallback (lines 114-122).
        """
        # No path component means pattern 0's `.*v=` path group cannot match
        # (requires `youtube.com/<path>` before `v=`), and other patterns also
        # require a specific path prefix.
        url = "https://youtube.com?v=dQw4w9WgXcQ"
        result = _extract_video_id(url)
        assert result == "dQw4w9WgXcQ"

    def test_urlparse_fallback_returns_none_when_v_too_short(self) -> None:
        """Returns None when ?v= param exists but is shorter than 11 chars."""
        url = "https://youtube.com?v=short"
        result = _extract_video_id(url)
        assert result is None

    def test_urlparse_exception_logs_warning_and_returns_none(self) -> None:
        """Returns None and logs a warning when parse_qs raises an unexpected error.

        Uses a URL that reaches the urlparse fallback (no regex match) and then
        triggers the except branch by making parse_qs raise.
        """
        with patch("src.pipeline.download.parse_qs", side_effect=ValueError("boom")):
            # URL with no path bypasses all compiled regexes, falls through to
            # the urlparse block, where parse_qs will raise.
            result = _extract_video_id("https://youtube.com?v=dQw4w9WgXcQ")
        assert result is None


# ---------------------------------------------------------------------------
# _run_ydl_download — internal sync wrapper (lines 184-188)
# ---------------------------------------------------------------------------


class TestRunYdlDownload:
    """Tests for _run_ydl_download, the synchronous yt-dlp download wrapper."""

    def test_raises_download_error_on_yt_dlp_download_error(self) -> None:
        """Converts yt_dlp.utils.DownloadError into DownloadError (lines 184-188)."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.download.side_effect = yt_dlp.utils.DownloadError("403 Forbidden")

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl), pytest.raises(DownloadError, match="403 Forbidden"):
            _run_ydl_download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {})


# ---------------------------------------------------------------------------
# _run_ydl_info — internal sync wrapper (lines 204-211)
# ---------------------------------------------------------------------------


class TestRunYdlInfo:
    """Tests for _run_ydl_info, the synchronous yt-dlp metadata wrapper."""

    def test_raises_download_error_when_extract_info_returns_none(self) -> None:
        """Raises DownloadError when extract_info returns None (line 207-208)."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl), pytest.raises(DownloadError, match="No metadata returned"):
            _run_ydl_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {})

    def test_raises_download_error_on_yt_dlp_download_error(self) -> None:
        """Converts yt_dlp.utils.DownloadError into DownloadError (lines 210-211)."""
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("private video")

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl), pytest.raises(DownloadError, match="private video"):
            _run_ydl_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {})

    def test_returns_dict_on_success(self) -> None:
        """Returns a dict when extract_info returns valid data (lines 204-209)."""
        fake_info = {"id": "dQw4w9WgXcQ", "title": "Test Video"}
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = fake_info

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = _run_ydl_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {})

        assert result == fake_info


# end tests/unit/test_download.py
