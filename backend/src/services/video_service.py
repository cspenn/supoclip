"""
Video service - handles video processing business logic.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import logging

from ..utils.async_helpers import run_in_thread
from ..youtube_utils import (
    download_youtube_video,
    get_youtube_video_title,
    get_youtube_video_id,
)
from ..video_utils import (
    get_video_transcript,
    create_clips_with_transitions,
    parse_timestamp_to_seconds,
    snap_segment_to_sentence_start,
    format_ms_to_timestamp_precise,
)
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
    async def analyze_transcript(
        transcript: str, min_length: int = 10, max_length: int = 45
    ) -> Any:
        """
        Analyze transcript with AI to find relevant segments.
        This is already async, no need to wrap.

        Args:
            transcript: Video transcript text
            min_length: Minimum clip length in seconds (default: 10)
            max_length: Maximum clip length in seconds (default: 45)
        """
        logger.info("Starting AI analysis of transcript")
        relevant_parts = await get_most_relevant_parts_by_transcript(
            transcript, min_length=min_length, max_length=max_length
        )
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
        output_resolution: str = "720p",
        logo_path: Optional[str] = None,
        logo_corner_position: Optional[str] = "top-right",
    ) -> List[Dict[str, Any]]:
        """
        Create video clips from segments with transitions and subtitles.
        Runs in thread pool as video processing is CPU-intensive.
        """
        try:
            logger.info(f"Creating {len(segments)} video clips at {output_resolution}")
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
                logo_path,  # Use parameter instead of hardcoded None
                logo_corner_position,  # Use parameter instead of hardcoded "top-right"
                output_resolution,
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
    def _validate_clip_duration_params(
        min_length: int, max_length: int
    ) -> tuple[int, int]:
        """Validate and normalize clip duration parameters.

        Args:
            min_length: Minimum clip length in seconds
            max_length: Maximum clip length in seconds

        Returns:
            Tuple of (validated_min_length, validated_max_length)
        """
        if min_length < 10:
            logger.warning(f"min_length {min_length}s too short. Setting to 10s.")
            min_length = 10

        if min_length > 60:
            logger.warning(
                f"min_length {min_length}s exceeds recommended maximum. Capping at 60s."
            )
            min_length = 60

        if max_length > 120:
            logger.warning(
                f"max_length {max_length}s exceeds recommended maximum. Capping at 120s."
            )
            max_length = 120

        if max_length < min_length:
            logger.warning(f"max_length < min_length. Adjusting to {min_length + 10}s.")
            max_length = min_length + 10

        return min_length, max_length

    @staticmethod
    def _apply_verbatim_text_to_segment(
        segment: Dict[str, Any], video_path: Path
    ) -> None:
        """Apply verbatim transcript text to a segment, snapping to sentence start.

        Modifies segment in-place with corrected start_time and verbatim text.

        Args:
            segment: Segment dictionary to update
            video_path: Path to video file for transcript cache lookup
        """
        from ..video_utils import extract_text_from_cache

        # Snap segment start to nearest valid sentence start
        original_start_ts = segment["start_time"]
        start_sec = parse_timestamp_to_seconds(original_start_ts)

        new_start_sec, snapped_word, snap_reason = snap_segment_to_sentence_start(
            video_path, start_sec
        )

        if abs(new_start_sec - start_sec) > 0.01:
            new_start_ts = format_ms_to_timestamp_precise(int(new_start_sec * 1000))
            logger.info(
                f"Snapped segment start: {original_start_ts} -> {new_start_ts} "
                f"({snap_reason})"
            )
            segment["start_time"] = new_start_ts
            segment["original_ai_start_time"] = original_start_ts
        else:
            logger.debug(
                f"[SYNC CHECK] No snap needed for {original_start_ts} ({snap_reason})"
            )

        # Extract verbatim text using the potentially adjusted start time
        verbatim_text = extract_text_from_cache(
            video_path,
            parse_timestamp_to_seconds(segment["start_time"]),
            parse_timestamp_to_seconds(segment["end_time"]),
        )

        if verbatim_text:
            original_ai_text = segment["text"]
            segment["text"] = verbatim_text
            logger.debug(
                f"[SYNC CHECK] Segment {segment['start_time']}-{segment['end_time']}: "
                f"extracted {len(verbatim_text.split())} words"
            )
            logger.info(
                f"Replaced text for segment {segment['start_time']}: "
                f"'{original_ai_text[:30]}...' -> '{verbatim_text[:30]}...'"
            )
        else:
            logger.warning(
                f"Could not extract verbatim text for segment {segment['start_time']} - "
                f"check transcript cache alignment"
            )

    @staticmethod
    async def process_video_complete(
        url: str,
        source_type: str,
        font_family: str = "TikTokSans-Regular",
        font_size: int = 24,
        font_color: str = "#FFFFFF",
        min_length: int = 10,
        max_length: int = 45,
        output_resolution: str = "720p",
        logo_path: Optional[str] = None,
        logo_corner_position: Optional[str] = "top-right",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Complete video processing pipeline.
        Returns dict with segments and clips info.

        Args:
            url: Video URL or file path
            source_type: "youtube" or "upload"
            font_family: Font family for subtitles
            font_size: Font size for subtitles
            font_color: Font color for subtitles
            min_length: Minimum clip length in seconds (default: 10)
            max_length: Maximum clip length in seconds (default: 45)
            output_resolution: Target resolution - "480p", "720p", or "1080p" (default: 720p)
            logo_path: Optional path to logo image file
            logo_corner_position: Logo corner position (default: "top-right")
            progress_callback: Optional function to call with progress updates
                              Signature: async def callback(progress: int, message: str)
        """
        try:
            # Log parameters at start
            logger.info(
                f"Processing video with parameters: "
                f"font_family={font_family}, font_size={font_size}, font_color={font_color}, "
                f"clip_length={min_length}s-{max_length}s, output_resolution={output_resolution}"
            )

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

            # Step 3: AI analysis with clip length settings
            if progress_callback:
                await progress_callback(50, "Analyzing content with AI...")

            # Validate clip duration parameters
            min_length, max_length = VideoService._validate_clip_duration_params(
                min_length, max_length
            )

            relevant_parts = await VideoService.analyze_transcript(
                transcript, min_length=min_length, max_length=max_length
            )
            logger.info(
                f"Step 3 complete: AI analysis done ({len(relevant_parts.most_relevant_segments)} segments identified)"
            )

            # Step 4: Create clips
            if progress_callback:
                await progress_callback(70, "Creating video clips...")

            segments_json = VideoProcessingResponse.segments_to_json(
                relevant_parts.most_relevant_segments
            )

            # Apply verbatim text from transcript cache to each segment
            # This prevents "Ghost Words" where AI summarizes/paraphrases but video shows original
            logger.info("Overwriting AI segment text with verbatim transcript text...")
            for segment in segments_json:
                VideoService._apply_verbatim_text_to_segment(segment, video_path)

            clips_info = await VideoService.create_video_clips(
                video_path,
                segments_json,
                font_family,
                font_size,
                font_color,
                output_resolution,
                logo_path,
                logo_corner_position,
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
