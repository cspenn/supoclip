# start backend/tests/unit/test_youtube_utils_coverage.py
"""Comprehensive tests for youtube_utils.py to achieve 100% line coverage.

Covers:
- DownloadedFileLocator.find_video_file
- DownloadRetryHandler.should_retry / wait_before_retry
- YouTubeDownloader.__init__ / get_optimal_download_options
- get_youtube_video_id (all branches including fallback URL parsing)
- validate_youtube_url
- get_youtube_video_info (success + error)
- get_youtube_video_title
- _perform_download_attempt (success + no-file)
- download_youtube_video (success, retry on DownloadError, retry on generic error, exhausted retries)
- get_video_duration
- is_video_suitable_for_processing
- cleanup_downloaded_files
"""

import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.youtube_utils import (
    DownloadedFileLocator,
    DownloadRetryHandler,
    YouTubeDownloader,
    get_youtube_video_id,
    validate_youtube_url,
    get_youtube_video_info,
    get_youtube_video_title,
    _perform_download_attempt,
    download_youtube_video,
    get_video_duration,
    is_video_suitable_for_processing,
    cleanup_downloaded_files,
)


# ---------------------------------------------------------------------------
# DownloadedFileLocator
# ---------------------------------------------------------------------------


class TestDownloadedFileLocator:
    """Tests for DownloadedFileLocator.find_video_file."""

    def test_find_video_file_mp4(self, tmp_path: Path) -> None:
        """Returns path when a matching .mp4 file exists."""
        video = tmp_path / "abc123.mp4"
        video.write_bytes(b"\x00" * 1024 * 1024)  # 1 MB
        result = DownloadedFileLocator.find_video_file(tmp_path, "abc123")
        assert result == video

    def test_find_video_file_mkv(self, tmp_path: Path) -> None:
        """Returns path when a matching .mkv file exists."""
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * 2 * 1024 * 1024)
        result = DownloadedFileLocator.find_video_file(tmp_path, "abc123")
        assert result == video

    def test_find_video_file_webm(self, tmp_path: Path) -> None:
        """Returns path when a matching .webm file exists."""
        video = tmp_path / "abc123.webm"
        video.write_bytes(b"\x00" * 1024 * 1024)
        result = DownloadedFileLocator.find_video_file(tmp_path, "abc123")
        assert result == video

    def test_find_video_file_no_match(self, tmp_path: Path) -> None:
        """Returns None when no matching file exists."""
        result = DownloadedFileLocator.find_video_file(tmp_path, "noexist")
        assert result is None

    def test_find_video_file_wrong_extension(self, tmp_path: Path) -> None:
        """Returns None when file has unsupported extension."""
        txt = tmp_path / "abc123.txt"
        txt.write_text("not a video")
        result = DownloadedFileLocator.find_video_file(tmp_path, "abc123")
        assert result is None

    def test_find_video_file_directory_ignored(self, tmp_path: Path) -> None:
        """Directories matching the glob are skipped."""
        (tmp_path / "abc123.mp4").mkdir()
        result = DownloadedFileLocator.find_video_file(tmp_path, "abc123")
        assert result is None


# ---------------------------------------------------------------------------
# DownloadRetryHandler
# ---------------------------------------------------------------------------


class TestDownloadRetryHandler:
    """Tests for DownloadRetryHandler."""

    def test_should_retry_true(self) -> None:
        assert DownloadRetryHandler.should_retry(0, 3) is True

    def test_should_retry_false_last_attempt(self) -> None:
        assert DownloadRetryHandler.should_retry(2, 3) is False

    @patch("src.youtube_utils.time.sleep")
    def test_wait_before_retry(self, mock_sleep: MagicMock) -> None:
        """Wait uses exponential backoff."""
        DownloadRetryHandler.wait_before_retry(0)
        mock_sleep.assert_called_once_with(1)  # 2**0 = 1

        mock_sleep.reset_mock()
        DownloadRetryHandler.wait_before_retry(2)
        mock_sleep.assert_called_once_with(4)  # 2**2 = 4


# ---------------------------------------------------------------------------
# YouTubeDownloader
# ---------------------------------------------------------------------------


class TestYouTubeDownloader:
    """Tests for YouTubeDownloader."""

    @patch("src.youtube_utils.config")
    def test_init_creates_temp_dir(self, mock_config: MagicMock, tmp_path: Path) -> None:
        """__init__ creates the temp directory."""
        target = tmp_path / "yt_temp"
        mock_config.temp_dir = str(target)
        dl = YouTubeDownloader()
        assert dl.temp_dir == target
        assert target.is_dir()

    @patch("src.youtube_utils.config")
    def test_get_optimal_download_options(self, mock_config: MagicMock, tmp_path: Path) -> None:
        """Returns dict with expected keys."""
        mock_config.temp_dir = str(tmp_path)
        dl = YouTubeDownloader()
        opts = dl.get_optimal_download_options("dQw4w9WgXcQ")
        assert "outtmpl" in opts
        assert "format" in opts
        assert "dQw4w9WgXcQ" in opts["outtmpl"]


# ---------------------------------------------------------------------------
# get_youtube_video_id
# ---------------------------------------------------------------------------


class TestGetYoutubeVideoId:
    """Tests for get_youtube_video_id (all branches)."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
        ],
    )
    def test_valid_urls(self, url: str, expected: str) -> None:
        assert get_youtube_video_id(url) == expected

    def test_none_input(self) -> None:
        assert get_youtube_video_id(None) is None  # type: ignore[arg-type]

    def test_empty_string(self) -> None:
        assert get_youtube_video_id("") is None

    def test_whitespace_only(self) -> None:
        assert get_youtube_video_id("   ") is None

    def test_non_youtube_url(self) -> None:
        assert get_youtube_video_id("https://vimeo.com/12345") is None

    def test_fallback_query_param(self) -> None:
        """Fallback URL parsing via query parameters (covers lines 146-152)."""
        # This URL won't match any regex (no path segment like watch/embed/v/shorts)
        # but will match the fallback urlparse query parameter check
        # Regex patterns require path-based patterns; bare ?v= on root URL bypasses them
        # Actually the first regex matches youtube.com/.*v= which covers ?v=
        # We need to force regex to fail - mock re.search to return None
        url = "https://www.youtube.com/page?v=dQw4w9WgXcQ"
        with patch("src.youtube_utils.re.search", return_value=None):
            result = get_youtube_video_id(url)
        assert result == "dQw4w9WgXcQ"

    def test_fallback_query_param_wrong_length(self) -> None:
        """Fallback returns None when v param is not 11 chars."""
        url = "https://www.youtube.com/?v=short"
        with patch("src.youtube_utils.re.search", return_value=None):
            result = get_youtube_video_id(url)
        assert result is None

    def test_fallback_no_v_param(self) -> None:
        """Fallback returns None when no v param exists."""
        url = "https://www.youtube.com/?q=hello"
        with patch("src.youtube_utils.re.search", return_value=None):
            result = get_youtube_video_id(url)
        assert result is None

    def test_fallback_non_youtube_domain(self) -> None:
        """Fallback returns None for non-youtube domain."""
        url = "https://www.example.com/?v=dQw4w9WgXcQ"
        with patch("src.youtube_utils.re.search", return_value=None):
            result = get_youtube_video_id(url)
        assert result is None

    def test_non_string_input(self) -> None:
        assert get_youtube_video_id(12345) is None  # type: ignore[arg-type]

    def test_fallback_urlparse_exception(self) -> None:
        """Covers except branch in fallback URL parsing (lines 153-154)."""
        # Force urlparse to raise by patching it, while ensuring regex won't match
        with patch("src.youtube_utils.re.search", return_value=None), \
             patch("src.youtube_utils.urlparse", side_effect=ValueError("bad url")):
            result = get_youtube_video_id("https://www.youtube.com/?v=dQw4w9WgXcQ")
        assert result is None


# ---------------------------------------------------------------------------
# validate_youtube_url
# ---------------------------------------------------------------------------


class TestValidateYoutubeUrl:
    """Tests for validate_youtube_url."""

    def test_valid_url(self) -> None:
        assert validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_invalid_url(self) -> None:
        assert validate_youtube_url("not-a-url") is False


# ---------------------------------------------------------------------------
# get_youtube_video_info
# ---------------------------------------------------------------------------


class TestGetYoutubeVideoInfo:
    """Tests for get_youtube_video_info."""

    @patch("src.youtube_utils.yt_dlp.YoutubeDL")
    def test_success(self, mock_ytdl_cls: MagicMock) -> None:
        """Returns metadata dict on success."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "A test",
            "duration": 120,
            "uploader": "TestUser",
            "upload_date": "20210101",
            "view_count": 100,
            "like_count": 10,
            "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
            "format_id": "137+140",
            "resolution": "1080p",
            "fps": 30,
            "filesize": 50000000,
        }
        mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = get_youtube_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result is not None
        assert result["title"] == "Test Video"
        assert result["duration"] == 120

    def test_invalid_url(self) -> None:
        """Returns None for invalid URL (no video id)."""
        result = get_youtube_video_info("not-a-url")
        assert result is None

    @patch("src.youtube_utils.yt_dlp.YoutubeDL")
    def test_exception(self, mock_ytdl_cls: MagicMock) -> None:
        """Returns None when extraction raises an exception."""
        mock_ytdl_cls.return_value.__enter__ = MagicMock(
            side_effect=Exception("API error")
        )
        mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = get_youtube_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result is None


# ---------------------------------------------------------------------------
# get_youtube_video_title
# ---------------------------------------------------------------------------


class TestGetYoutubeVideoTitle:
    """Tests for get_youtube_video_title."""

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_returns_title(self, mock_info: MagicMock) -> None:
        mock_info.return_value = {"title": "My Title"}
        assert get_youtube_video_title("https://youtube.com/watch?v=dQw4w9WgXcQ") == "My Title"

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_returns_none_when_info_is_none(self, mock_info: MagicMock) -> None:
        mock_info.return_value = None
        assert get_youtube_video_title("https://youtube.com/watch?v=dQw4w9WgXcQ") is None


# ---------------------------------------------------------------------------
# _perform_download_attempt
# ---------------------------------------------------------------------------


class TestPerformDownloadAttempt:
    """Tests for _perform_download_attempt."""

    @patch("src.youtube_utils.yt_dlp.YoutubeDL")
    @patch("src.youtube_utils.DownloadedFileLocator.find_video_file")
    @patch("src.youtube_utils.config")
    def test_success(
        self,
        mock_config: MagicMock,
        mock_find: MagicMock,
        mock_ytdl_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_config.temp_dir = str(tmp_path)
        mock_ydl = MagicMock()
        mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)
        expected_path = tmp_path / "dQw4w9WgXcQ.mp4"
        mock_find.return_value = expected_path

        dl = YouTubeDownloader()
        result = _perform_download_attempt(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", dl, 0
        )
        assert result == expected_path

    @patch("src.youtube_utils.yt_dlp.YoutubeDL")
    @patch("src.youtube_utils.DownloadedFileLocator.find_video_file")
    @patch("src.youtube_utils.config")
    def test_no_file_found(
        self,
        mock_config: MagicMock,
        mock_find: MagicMock,
        mock_ytdl_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_config.temp_dir = str(tmp_path)
        mock_ydl = MagicMock()
        mock_ytdl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ytdl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_find.return_value = None

        dl = YouTubeDownloader()
        result = _perform_download_attempt(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", dl, 0
        )
        assert result is None


# ---------------------------------------------------------------------------
# download_youtube_video
# ---------------------------------------------------------------------------


class TestDownloadYoutubeVideo:
    """Tests for download_youtube_video."""

    def test_invalid_url(self) -> None:
        """Returns None for invalid URL."""
        result = download_youtube_video("not-a-url")
        assert result is None

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_no_video_info(self, mock_info: MagicMock) -> None:
        """Returns None when video info cannot be retrieved."""
        mock_info.return_value = None
        result = download_youtube_video("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert result is None

    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_success_first_attempt(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns path on successful first attempt."""
        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Test", "duration": 120}
        expected = tmp_path / "dQw4w9WgXcQ.mp4"
        mock_download.return_value = expected

        result = download_youtube_video(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=1
        )
        assert result == expected

    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_long_video_warning(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs warning for videos over 1 hour."""
        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Long Video", "duration": 7200}
        expected = tmp_path / "dQw4w9WgXcQ.mp4"
        mock_download.return_value = expected

        with caplog.at_level(logging.WARNING):
            result = download_youtube_video(
                "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=1
            )
        assert result == expected
        assert "exceeds recommended limit" in caplog.text

    @patch("src.youtube_utils.DownloadRetryHandler.wait_before_retry")
    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_download_error_retry(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        mock_wait: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Retries on yt_dlp DownloadError then succeeds."""
        import yt_dlp

        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Test", "duration": 120}
        expected = tmp_path / "dQw4w9WgXcQ.mp4"
        mock_download.side_effect = [
            yt_dlp.utils.DownloadError("403 Forbidden"),
            expected,
        ]

        result = download_youtube_video(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=2
        )
        assert result == expected
        mock_wait.assert_called_once()

    @patch("src.youtube_utils.DownloadRetryHandler.wait_before_retry")
    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_download_error_all_retries_exhausted(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        mock_wait: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns None when all retries fail with DownloadError."""
        import yt_dlp

        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Test", "duration": 120}
        mock_download.side_effect = yt_dlp.utils.DownloadError("fail")

        result = download_youtube_video(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=2
        )
        assert result is None

    @patch("src.youtube_utils.DownloadRetryHandler.wait_before_retry")
    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_generic_error_retry(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        mock_wait: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Retries on generic exception then succeeds."""
        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Test", "duration": 120}
        expected = tmp_path / "dQw4w9WgXcQ.mp4"
        mock_download.side_effect = [
            RuntimeError("network blip"),
            expected,
        ]

        result = download_youtube_video(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=2
        )
        assert result == expected

    @patch("src.youtube_utils.DownloadRetryHandler.wait_before_retry")
    @patch("src.youtube_utils._perform_download_attempt")
    @patch("src.youtube_utils.get_youtube_video_info")
    @patch("src.youtube_utils.config")
    def test_generic_error_all_retries_exhausted(
        self,
        mock_config: MagicMock,
        mock_info: MagicMock,
        mock_download: MagicMock,
        mock_wait: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns None when all retries fail with generic exception."""
        mock_config.temp_dir = str(tmp_path)
        mock_info.return_value = {"title": "Test", "duration": 120}
        mock_download.side_effect = RuntimeError("persistent failure")

        result = download_youtube_video(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", max_retries=2
        )
        assert result is None


# ---------------------------------------------------------------------------
# get_video_duration
# ---------------------------------------------------------------------------


class TestGetVideoDuration:
    """Tests for get_video_duration."""

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_returns_duration(self, mock_info: MagicMock) -> None:
        mock_info.return_value = {"duration": 300}
        assert get_video_duration("https://youtube.com/watch?v=dQw4w9WgXcQ") == 300

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_returns_none(self, mock_info: MagicMock) -> None:
        mock_info.return_value = None
        assert get_video_duration("https://youtube.com/watch?v=dQw4w9WgXcQ") is None


# ---------------------------------------------------------------------------
# is_video_suitable_for_processing
# ---------------------------------------------------------------------------


class TestIsVideoSuitableForProcessing:
    """Tests for is_video_suitable_for_processing."""

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_suitable(self, mock_info: MagicMock) -> None:
        mock_info.return_value = {"duration": 300}
        assert (
            is_video_suitable_for_processing("https://youtube.com/watch?v=dQw4w9WgXcQ")
            is True
        )

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_no_info(self, mock_info: MagicMock) -> None:
        mock_info.return_value = None
        assert (
            is_video_suitable_for_processing("https://youtube.com/watch?v=dQw4w9WgXcQ")
            is False
        )

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_too_short(self, mock_info: MagicMock) -> None:
        mock_info.return_value = {"duration": 10}
        assert (
            is_video_suitable_for_processing("https://youtube.com/watch?v=dQw4w9WgXcQ")
            is False
        )

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_too_long(self, mock_info: MagicMock) -> None:
        mock_info.return_value = {"duration": 99999}
        assert (
            is_video_suitable_for_processing("https://youtube.com/watch?v=dQw4w9WgXcQ")
            is False
        )

    @patch("src.youtube_utils.get_youtube_video_info")
    def test_within_range(self, mock_info: MagicMock) -> None:
        """Video within custom min/max is suitable."""
        mock_info.return_value = {"duration": 300}
        assert (
            is_video_suitable_for_processing(
                "https://youtube.com/watch?v=dQw4w9WgXcQ",
                min_duration=100,
                max_duration=600,
            )
            is True
        )


# ---------------------------------------------------------------------------
# cleanup_downloaded_files
# ---------------------------------------------------------------------------


class TestCleanupDownloadedFiles:
    """Tests for cleanup_downloaded_files."""

    @patch("src.youtube_utils.config")
    def test_cleanup_existing_files(self, mock_config: MagicMock, tmp_path: Path) -> None:
        mock_config.temp_dir = str(tmp_path)
        f1 = tmp_path / "dQw4w9WgXcQ.mp4"
        f1.write_bytes(b"data")
        f2 = tmp_path / "dQw4w9WgXcQ.webm"
        f2.write_bytes(b"data")

        cleanup_downloaded_files("dQw4w9WgXcQ")
        assert not f1.exists()
        assert not f2.exists()

    @patch("src.youtube_utils.config")
    def test_cleanup_no_matching_files(self, mock_config: MagicMock, tmp_path: Path) -> None:
        """No error when there are no matching files."""
        mock_config.temp_dir = str(tmp_path)
        cleanup_downloaded_files("no_match")

    @patch("src.youtube_utils.config")
    def test_cleanup_handles_permission_error(
        self, mock_config: MagicMock, tmp_path: Path
    ) -> None:
        """Logs warning when file deletion fails."""
        mock_config.temp_dir = str(tmp_path)
        f1 = tmp_path / "dQw4w9WgXcQ.mp4"
        f1.write_bytes(b"data")

        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            # Should not raise, just log warning
            cleanup_downloaded_files("dQw4w9WgXcQ")

    @patch("src.youtube_utils.config")
    def test_cleanup_skips_directories(self, mock_config: MagicMock, tmp_path: Path) -> None:
        """Directories matching the glob are skipped."""
        mock_config.temp_dir = str(tmp_path)
        d = tmp_path / "dQw4w9WgXcQ.mp4"
        d.mkdir()
        cleanup_downloaded_files("dQw4w9WgXcQ")
        # Directory should still exist (not deleted)
        assert d.is_dir()


# end backend/tests/unit/test_youtube_utils_coverage.py
