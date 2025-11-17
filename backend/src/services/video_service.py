"""
Video service - handles video processing business logic.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from ..utils.async_helpers import run_in_thread
from ..youtube_utils import (
    download_youtube_video,
    get_youtube_video_title,
    get_youtube_video_id,
)
from ..video_utils import get_video_transcript, create_clips_with_transitions
from ..ai import get_most_relevant_parts_by_transcript
from ..config import Config

logger = logging.getLogger(__name__)
config = Config()


class VideoDownloadError(Exception):
    """Raised when video download fails."""

    pass


class VideoNotFoundError(Exception):
    """Raised when video file is not found."""

    pass


class VideoProcessingResponse:
    """Helper for building video processing response."""

    @staticmethod
    def build_response(
        segments_json: List[Dict[str, Any]],
        clips_info: List[Dict[str, Any]],
        relevant_parts: Any,
    ) -> Dict[str, Any]:
        """Build the response dictionary."""
        return {
            "segments": segments_json,
            "clips": clips_info,
            "summary": relevant_parts.summary if relevant_parts else None,
            "key_topics": relevant_parts.key_topics if relevant_parts else None,
        }

    @staticmethod
    def segments_to_json(segments: List[Any]) -> List[Dict[str, Any]]:
        """Convert segment objects to JSON-serializable dicts."""
        return [
            {
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "text": segment.text,
                "relevance_score": segment.relevance_score,
                "reasoning": segment.reasoning,
            }
            for segment in segments
        ]


class VideoService:
    """Service for video processing operations."""

    @staticmethod
    async def _get_video_path(url: str, source_type: str) -> Path:
        """Get video path by downloading or validating existing path."""
        if source_type == "youtube":
            video_path = await VideoService.download_video(url)
            if not video_path:
                raise VideoDownloadError(f"Failed to download video from URL: {url}")
            return video_path
        else:
            video_path = Path(url)
            if not video_path.exists():
                raise VideoNotFoundError(f"Video file not found at path: {url}")
            return video_path

    @staticmethod
    async def download_video(url: str) -> Optional[Path]:
        """
        Download a YouTube video asynchronously.
        Runs the sync download_youtube_video in a thread pool.
        """
        try:
            logger.info(f"Starting video download: {url}")
            video_path = await run_in_thread(download_youtube_video, url)

            if not video_path:
                logger.error(f"Failed to download video: {url}")
                return None

            logger.info(f"Video downloaded successfully: {video_path}")
            return video_path
        except Exception as e:
            logger.error(
                f"Exception during video download from {url}: {e}", exc_info=True
            )
            raise

    @staticmethod
    async def get_video_title(url: str) -> str:
        """
        Get video title asynchronously.
        Returns a default title if retrieval fails.
        """
        try:
            title = await run_in_thread(get_youtube_video_title, url)
            return title or "YouTube Video"
        except Exception as e:
            logger.warning(f"Failed to get video title: {e}")
            return "YouTube Video"

    @staticmethod
    async def generate_transcript(video_path: Path) -> str:
        """
        Generate transcript from video using parakeet-mlx.
        Runs in thread pool to avoid blocking.
        """
        try:
            logger.info(f"Generating transcript for: {video_path}")
            transcript = await run_in_thread(get_video_transcript, video_path)
            logger.info(f"Transcript generated: {len(transcript)} characters")
            return transcript
        except Exception as e:
            logger.error(
                f"Exception during transcript generation for {video_path}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    async def analyze_transcript(transcript: str) -> Any:
        """
        Analyze transcript with AI to find relevant segments.
        This is already async, no need to wrap.
        """
        logger.info("Starting AI analysis of transcript")
        relevant_parts = await get_most_relevant_parts_by_transcript(transcript)
        logger.info(
            f"AI analysis complete: {len(relevant_parts.most_relevant_segments)} segments found"
        )
        return relevant_parts

    @staticmethod
    async def create_video_clips(
        video_path: Path,
        segments: List[Dict[str, Any]],
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
    ) -> List[Dict[str, Any]]:
        """
        Create video clips from segments with transitions and subtitles.
        Runs in thread pool as video processing is CPU-intensive.
        """
        try:
            logger.info(f"Creating {len(segments)} video clips")
            clips_output_dir = Path(config.temp_dir) / "clips"
            clips_output_dir.mkdir(parents=True, exist_ok=True)

            clips_info = await run_in_thread(
                create_clips_with_transitions,
                video_path,
                segments,
                clips_output_dir,
                font_family,
                font_size,
                font_color,
            )

            logger.info(f"Successfully created {len(clips_info)} clips")
            return clips_info
        except Exception as e:
            logger.error(
                f"Exception during clip creation for {video_path}: {e}", exc_info=True
            )
            raise

    @staticmethod
    def determine_source_type(url: str) -> str:
        """Determine if source is YouTube or uploaded file."""
        video_id = get_youtube_video_id(url)
        return "youtube" if video_id else "upload"

    @staticmethod
    async def process_video_complete(
        url: str,
        source_type: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Complete video processing pipeline.
        Returns dict with segments and clips info.

        progress_callback: Optional function to call with progress updates
                          Signature: async def callback(progress: int, message: str)
        """
        try:
            # Step 1: Get video path
            if progress_callback:
                await progress_callback(10, "Downloading video...")

            video_path = await VideoService._get_video_path(url, source_type)
            logger.info(f"Step 1 complete: Video path obtained: {video_path}")

            # Step 2: Generate transcript
            if progress_callback:
                await progress_callback(30, "Generating transcript...")

            transcript = await VideoService.generate_transcript(video_path)
            logger.info(
                f"Step 2 complete: Transcript generated ({len(transcript)} characters)"
            )

            # Step 3: AI analysis
            if progress_callback:
                await progress_callback(50, "Analyzing content with AI...")

            relevant_parts = await VideoService.analyze_transcript(transcript)
            logger.info(
                f"Step 3 complete: AI analysis done ({len(relevant_parts.most_relevant_segments)} segments identified)"
            )

            # Step 4: Create clips
            if progress_callback:
                await progress_callback(70, "Creating video clips...")

            segments_json = VideoProcessingResponse.segments_to_json(
                relevant_parts.most_relevant_segments
            )

            clips_info = await VideoService.create_video_clips(
                video_path, segments_json, font_family, font_size, font_color
            )
            logger.info(f"Step 4 complete: Created {len(clips_info)} video clips")

            if progress_callback:
                await progress_callback(100, "Processing complete!")

            return VideoProcessingResponse.build_response(
                segments_json, clips_info, relevant_parts
            )

        except Exception as e:
            logger.error(f"Error in video processing pipeline: {e}", exc_info=True)
            raise
