"""
Utility functions for YouTube-related operations.
"""

import re
from urllib.parse import urlparse, parse_qs
import yt_dlp
from typing import Optional
from pathlib import Path
import logging

from .config import Config

logger = logging.getLogger(__name__)

config = Config()

def get_youtube_video_id(url: str) -> str:
    """
    Extract the YouTube video ID from a URL.
    Supports various YouTube URL formats.
    Returns None if no valid video ID is found.
    """
    if not isinstance(url, str) or not url:
        return None

    patterns = [
        r"(?:youtube\.com/(?:.*v=|v/|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    try:
        parsed_url = urlparse(url)
        query = parse_qs(parsed_url.query)
        video_ids = query.get("v")
        if video_ids and len(video_ids[0]) == 11:
            return video_ids[0]
    except Exception:
        pass

    return None


def get_youtube_video_title(url: str) -> Optional[str]:
    """
    Get the title of a YouTube video from a URL.
    """
    video_id = get_youtube_video_id(url)
    if not video_id:
        return None

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title')

    except Exception:
        return None

def download_youtube_video(url: str) -> Optional[Path]:
    """
    Download a YouTube video from a URL.
    Returns the path to the downloaded file, or None if download fails.
    """
    logger.info(f"📺 Starting YouTube download from: {url}")
    video_id = get_youtube_video_id(url)
    if not video_id:
        logger.error(f"❌ Could not extract video ID from URL: {url}")
        return None

    logger.info(f"🆔 Video ID extracted: {video_id}")
    temp_dir = Path(config.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Using temp directory: {temp_dir}")

    output_path = temp_dir / f"{video_id}.%(ext)s"

    try:
        ydl_opts = {
            'outtmpl': str(output_path),
            'format': 'best[height<=720]',
            'quiet': True,
            'no_warnings': True,
        }

        logger.info(f"⬇️ Starting download with yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

            logger.info(f"🔍 Looking for downloaded file: {video_id}.*")
            for file_path in temp_dir.glob(f"{video_id}.*"):
                if file_path.is_file():
                    logger.info(f"✅ Download successful: {file_path} ({file_path.stat().st_size} bytes)")
                    return file_path

        logger.error(f"❌ No file found after download for video ID: {video_id}")
        return None

    except Exception as e:
        logger.error(f"❌ Download failed with exception: {str(e)}")
        logger.error(f"📊 Exception type: {type(e)}")
        return None
