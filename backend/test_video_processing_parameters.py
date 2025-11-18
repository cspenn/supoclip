#!/usr/bin/env python3
"""
Test script to verify parameter flow through video processing pipeline.

This script processes a real YouTube video with specific parameters to verify:
1. Font selection (system font: "Barlow Condensed Semi Bold")
2. Clip length settings (min=50s, max=60s)
3. Parameter logging

Test video: https://www.youtube.com/watch?v=5lN8I4PqLkc
"""
import asyncio
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.video_service import VideoService
from src.config import Config

# Setup logging to see parameter flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_video_processing_with_parameters():
    """
    Process a video with specific font and clip length parameters.

    Expected outcomes:
    1. Font "Barlow Condensed Semi Bold" should be resolved (bundled or system)
    2. Clips should be between 50-60 seconds long
    3. Logs should show all parameters being passed through
    """
    config = Config()

    logger.info("=" * 80)
    logger.info("PARAMETER FLOW TEST - Starting")
    logger.info("=" * 80)

    # Test parameters
    test_url = "https://www.youtube.com/watch?v=5lN8I4PqLkc"
    test_font = "Barlow Condensed Semi Bold"
    test_min_length = 50
    test_max_length = 60

    logger.info(f"Test URL: {test_url}")
    logger.info(f"Font requested: {test_font}")
    logger.info(f"Clip length range: {test_min_length}s - {test_max_length}s")
    logger.info("")

    try:
        # Process video with specific parameters
        logger.info("Starting video processing...")
        result = await VideoService.process_video_complete(
            url=test_url,
            source_type="youtube",
            font_family=test_font,
            font_size=24,
            font_color="#FFFFFF",
            min_length=test_min_length,
            max_length=test_max_length
        )

        logger.info("=" * 80)
        logger.info("PROCESSING COMPLETE - Analyzing Results")
        logger.info("=" * 80)

        # Analyze results
        segments = result.get('segments', [])
        clips = result.get('clips', [])

        logger.info(f"Number of segments identified: {len(segments)}")
        logger.info(f"Number of clips created: {len(clips)}")
        logger.info("")

        # Check segment lengths
        if segments:
            logger.info("Segment Analysis:")
            for i, segment in enumerate(segments, 1):
                start = segment['start_time']
                end = segment['end_time']
                duration = end - start
                logger.info(f"  Segment {i}: {duration:.1f}s ({start:.1f}s - {end:.1f}s)")

                # Check if duration is within requested range
                if test_min_length <= duration <= test_max_length:
                    logger.info(f"    ✓ Duration within range ({test_min_length}s - {test_max_length}s)")
                else:
                    logger.warning(f"    ✗ Duration outside range! Expected {test_min_length}s-{test_max_length}s, got {duration:.1f}s")
            logger.info("")

        # Check clip files
        if clips:
            logger.info("Clip Files Created:")
            for i, clip in enumerate(clips, 1):
                clip_path = clip.get('path', 'unknown')
                logger.info(f"  Clip {i}: {clip_path}")
            logger.info("")

        # Check for font resolution in logs
        logger.info("Font Resolution Check:")
        logger.info(f"  Requested font: {test_font}")
        logger.info("  Check logs above for font resolution messages")
        logger.info("  Look for: 'Found bundled font' or 'Found system font' or 'Using default font'")
        logger.info("")

        # Summary
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✓ Video processed successfully")
        logger.info(f"✓ {len(segments)} segments identified")
        logger.info(f"✓ {len(clips)} clips created")

        # Check if any segments are within our requested range
        if segments:
            in_range = sum(1 for s in segments if test_min_length <= (s['end_time'] - s['start_time']) <= test_max_length)
            total = len(segments)
            logger.info(f"✓ {in_range}/{total} segments within {test_min_length}s-{test_max_length}s range")

            if in_range == 0:
                logger.warning("⚠ No segments within requested clip length range!")
                logger.warning("   This may indicate clip length parameters were ignored.")

        logger.info("")
        logger.info("To verify font selection:")
        logger.info("  1. Check logs for 'Found bundled font' or 'Found system font' messages")
        logger.info("  2. Inspect generated clip files for correct font rendering")
        logger.info("")

        return result

    except Exception as e:
        logger.error(f"ERROR during video processing: {e}", exc_info=True)
        raise


async def quick_test_font_resolution():
    """
    Quick test to verify font resolution without processing entire video.
    """
    from src.video_utils import resolve_font_path

    logger.info("=" * 80)
    logger.info("QUICK FONT RESOLUTION TEST")
    logger.info("=" * 80)

    test_fonts = [
        "Barlow Condensed Semi Bold",
        "TikTokSans-Regular",
        "NonExistentFont12345"
    ]

    for font_name in test_fonts:
        logger.info(f"Testing font: {font_name}")
        result = resolve_font_path(font_name)
        logger.info(f"  Resolved to: {result}")
        logger.info("")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test video processing parameter flow")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick font resolution test only (no video processing)"
    )

    args = parser.parse_args()

    if args.quick:
        asyncio.run(quick_test_font_resolution())
    else:
        logger.warning("=" * 80)
        logger.warning("FULL VIDEO PROCESSING TEST")
        logger.warning("This will download and process a real YouTube video.")
        logger.warning("This may take several minutes depending on video length.")
        logger.warning("=" * 80)
        logger.warning("")

        # Give user a chance to cancel
        import time
        logger.info("Starting in 5 seconds... (Ctrl+C to cancel)")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Test cancelled by user.")
            sys.exit(0)

        asyncio.run(test_video_processing_with_parameters())
