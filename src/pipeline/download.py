# start src/pipeline/download.py
"""YouTube video download utilities.

Plain functions for downloading YouTube videos via yt-dlp, with
stamina-based retry logic and async-safe thread offloading.
"""

import asyncio
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import stamina
import structlog
import yt_dlp  # type: ignore

from src.exceptions import DownloadError as BaseDownloadError

logger = structlog.get_logger(__name__)

VALID_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".webm"})

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_YDL_HTTP_HEADERS: dict[str, str] = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_YOUTUBE_ID_PATTERNS = (
    r"(?:youtube\.com/(?:.*v=|v/|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})",
    r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    r"youtube\.com/v/([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    r"youtube\.com/live/([A-Za-z0-9_-]{11})",
    r"m\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
)


class DownloadError(BaseDownloadError):
    """Raised when video download fails."""


def _build_ydl_opts(output_dir: Path, video_id: str) -> dict[str, Any]:
    """Build yt-dlp options for a single download.

    Args:
        output_dir: Directory where the video will be saved.
        video_id: YouTube video ID used for the output filename template.

    Returns:
        Dict of yt-dlp options ready for use with YoutubeDL.
    """
    return {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / f"{video_id}.%(ext)s"),
        "noplaylist": True,
        "nocheckcertificate": False,
        "quiet": True,
        "no_warnings": False,
        "ignoreerrors": False,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "http_chunk_size": 10_485_760,
        "http_headers": _YDL_HTTP_HEADERS,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writeinfojson": False,
        "extract_flat": False,
    }


def _extract_video_id(url: str) -> str | None:
    """Extract the 11-character video ID from a YouTube URL.

    Args:
        url: YouTube URL in any supported format.

    Returns:
        11-character video ID, or None if not found.
    """
    if not isinstance(url, str) or not url.strip():
        return None

    url = url.strip()

    for pattern in _YOUTUBE_ID_PATTERNS:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            # Every pattern's capture group enforces exactly 11 chars, so a
            # match is already a valid id — no redundant length re-check.
            return match.group(1)

    try:
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc.lower():
            params = parse_qs(parsed.query)
            ids = params.get("v")
            if ids and len(ids[0]) == 11:
                return ids[0]
    except Exception as exc:
        logger.warning("download.url_parse_failed", error=str(exc))

    return None


def validate_youtube_url(url: str) -> bool:
    """Check if a URL is a valid YouTube video URL.

    Args:
        url: URL string to validate.

    Returns:
        True if the URL is a valid YouTube video URL.
    """
    return _extract_video_id(url) is not None


def find_downloaded_file(output_dir: Path, base_stem: str | None = None) -> Path | None:
    """Find the most recently modified video file in the output directory.

    yt-dlp can output .mp4, .mkv, or .webm depending on source.

    Args:
        output_dir: Directory to search.
        base_stem: Optional filename stem to look for specifically.

    Returns:
        Path to the video file, or None if not found.
    """
    if base_stem is not None:
        for ext in VALID_VIDEO_EXTENSIONS:
            candidate = output_dir / f"{base_stem}{ext}"
            if candidate.is_file():
                size_mb = candidate.stat().st_size // (1024 * 1024)
                logger.info("download.file_found", name=candidate.name, size_mb=size_mb)
                return candidate
        return None

    video_files = [p for p in output_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_VIDEO_EXTENSIONS]
    if not video_files:
        return None

    most_recent = max(video_files, key=lambda p: p.stat().st_mtime)
    size_mb = most_recent.stat().st_size // (1024 * 1024)
    logger.info("download.file_found", name=most_recent.name, size_mb=size_mb)
    return most_recent


def _run_ydl_download(url: str, ydl_opts: dict[str, Any]) -> None:
    """Execute yt-dlp download synchronously.

    Args:
        url: YouTube URL to download.
        ydl_opts: yt-dlp options dict.

    Raises:
        DownloadError: If yt-dlp reports a download failure.
    """
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:  # type: ignore[reportAttributeAccessIssue]
        raise DownloadError(str(exc)) from exc


@stamina.retry(on=DownloadError, attempts=3, wait_initial=1.0, wait_max=4.0)
async def download_youtube_video(
    url: str,
    output_dir: str | Path,
) -> Path:
    """Download a YouTube video to the output directory.

    Downloads the best available quality up to 1080p. The download
    runs in a thread pool to avoid blocking the async event loop.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save the downloaded video.

    Returns:
        Path to the downloaded video file.

    Raises:
        DownloadError: If the download fails after retries.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    video_id = _extract_video_id(url)
    if not video_id:
        raise DownloadError(f"Could not extract video ID from URL: {url}")

    logger.info("download.start", url=url, video_id=video_id)

    ydl_opts = _build_ydl_opts(output_path, video_id)
    await asyncio.to_thread(_run_ydl_download, url, ydl_opts)

    file_path = find_downloaded_file(output_path, base_stem=video_id)
    if not file_path:
        raise DownloadError(f"No video file found after download of: {url}")

    logger.info("download.complete", path=str(file_path))
    return file_path


# end src/pipeline/download.py
