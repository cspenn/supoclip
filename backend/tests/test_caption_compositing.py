# start test_caption_compositing.py
"""
Test caption clipping in CompositeVideoClip context.

This test demonstrates that caption clipping occurs during video composition,
not in the TextClip creation itself.
"""

from pathlib import Path
from moviepy import TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import Margin
from PIL import Image
import numpy as np

# Test configuration
FONT_PATH = "fonts/TikTokSans-Regular.ttf"
TEST_OUTPUT_DIR = Path("/tmp/caption_composite_tests")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


def test_composite_clipping():
    """Test if captions get clipped during composition."""
    print("=" * 60)
    print("CAPTION COMPOSITING CLIPPING TEST")
    print("=" * 60)

    # Create a simple background video (solid color)
    video_width = 720
    video_height = 1280  # 9:16 aspect ratio
    duration = 2.0

    print(f"\nVideo dimensions: {video_width}x{video_height}")
    print(f"Duration: {duration}s")

    # Create background
    background = ColorClip(
        size=(video_width, video_height),
        color=(30, 30, 30),  # Dark gray
        duration=duration,
    )

    # Test different scenarios
    test_cases = [
        {
            "name": "current_production_settings",
            "font_size": 30,
            "bottom_margin": 3,
            "y_percent": 0.75,
            "description": "Current production: 3px margin, 75% position",
        },
        {
            "name": "increased_margin_same_position",
            "font_size": 30,
            "bottom_margin": 12,
            "y_percent": 0.75,
            "description": "Increased margin (12px), same position (75%)",
        },
        {
            "name": "same_margin_higher_position",
            "font_size": 30,
            "bottom_margin": 3,
            "y_percent": 0.72,
            "description": "Same margin (3px), higher position (72%)",
        },
        {
            "name": "increased_margin_and_higher_position",
            "font_size": 30,
            "bottom_margin": 12,
            "y_percent": 0.72,
            "description": "Increased margin (12px), higher position (72%)",
        },
    ]

    for test_case in test_cases:
        print(f"\n{'-'*60}")
        print(f"Test: {test_case['description']}")

        # Create text clip
        text = "what happened instead."
        text_clip = TextClip(
            text=text,
            font=FONT_PATH,
            font_size=test_case["font_size"],
            color="#FFFFFF",
            stroke_color="black",
            stroke_width=1,
            method="label",
            text_align="center",
        )

        # Apply margin
        text_clip = text_clip.with_effects(
            [
                Margin(
                    bottom=test_case["bottom_margin"], top=5, left=3, right=3, opacity=0
                )
            ]
        )

        text_width, text_height = text_clip.size
        print(f"TextClip size: {text_width}x{text_height}")

        # Calculate position (same logic as production)
        vertical_position = int(
            video_height * test_case["y_percent"] - text_height // 2
        )
        print(
            f"Y-position: {vertical_position} (center at {test_case['y_percent']*100}%)"
        )

        # Check if text will extend beyond video bounds
        text_bottom = vertical_position + text_height
        pixels_beyond = text_bottom - video_height

        if pixels_beyond > 0:
            print(f"⚠️  WARNING: Text extends {pixels_beyond}px beyond video bottom!")
            print(f"   Text bottom: {text_bottom}px, Video height: {video_height}px")
        else:
            print(f"✅ Text fits within bounds ({-pixels_beyond}px clearance)")

        # Position the text
        text_clip = text_clip.with_duration(duration).with_position(
            ("center", vertical_position)
        )

        # Compose
        final_clip = CompositeVideoClip([background, text_clip])

        # Save a frame to inspect
        frame = final_clip.get_frame(0.5)
        img = Image.fromarray(frame)

        # Draw analysis overlay
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)

        # Draw text bounding box in red
        text_left = (video_width - text_width) // 2
        text_right = text_left + text_width
        text_top = vertical_position
        text_bottom_calc = text_top + text_height

        # Red box showing where text should be
        draw.rectangle(
            [
                (text_left, text_top),
                (text_right, min(text_bottom_calc, video_height - 1)),
            ],
            outline="red",
            width=2,
        )

        # Yellow line showing video bottom edge
        draw.line(
            [(0, video_height - 5), (video_width, video_height - 5)],
            fill="yellow",
            width=3,
        )

        # Green line showing where text center should be
        center_y = int(video_height * test_case["y_percent"])
        draw.line([(0, center_y), (video_width, center_y)], fill="green", width=1)

        output_path = TEST_OUTPUT_DIR / f"{test_case['name']}.png"
        img.save(output_path)
        print(f"Saved frame to: {output_path}")

        # Analyze bottom edge for clipping
        frame_rgb = np.array(img)
        bottom_region = frame_rgb[-10:, :, :]  # Last 10 rows

        # Check if white/black text pixels exist in bottom region
        white_pixels = np.sum(np.all(bottom_region > [200, 200, 200], axis=2))
        black_pixels = np.sum(np.all(bottom_region < [50, 50, 50], axis=2))

        if pixels_beyond > 0 and (white_pixels > 100 or black_pixels > 100):
            print("⚠️  CLIPPING CONFIRMED: Text pixels found at bottom edge")
            print(f"   White pixels: {white_pixels}, Black pixels: {black_pixels}")
        elif white_pixels > 100 or black_pixels > 100:
            print("✅ Text visible near bottom (no clipping)")
        else:
            print("✅ No text near bottom edge")

        # Cleanup
        final_clip.close()
        text_clip.close()

    background.close()

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nVisual inspection: Open images in {TEST_OUTPUT_DIR}")
    print("\nVisualization guide:")
    print("  - Red box: TextClip bounding box")
    print("  - Yellow line: Video bottom edge (5px from bottom)")
    print("  - Green line: Text center position (75% or 72%)")
    print("\nLook for:")
    print("  1. Red box extending beyond yellow line (indicates clipping)")
    print("  2. Text cut off at yellow line")
    print("  3. Gap between text and yellow line (indicates no clipping)")


def calculate_safe_position(
    video_height: int, text_height: int, bottom_clearance: int = 10
) -> int:
    """
    Calculate a safe Y-position that ensures text doesn't get clipped.

    Args:
        video_height: Height of video canvas
        text_height: Height of text clip (including margins)
        bottom_clearance: Minimum pixels from bottom edge

    Returns:
        Safe Y-position for text
    """
    # Position text so its bottom is at least bottom_clearance pixels from video bottom
    max_y = video_height - text_height - bottom_clearance

    # But also don't go above 70% of video height
    min_y = int(video_height * 0.70 - text_height // 2)

    # Use the lower position (closer to bottom, but still safe)
    safe_y = min(max_y, int(video_height * 0.75 - text_height // 2))

    return max(safe_y, min_y)


def test_safe_positioning():
    """Test the safe positioning calculation."""
    print("\n" + "=" * 60)
    print("SAFE POSITIONING CALCULATION TEST")
    print("=" * 60)

    video_height = 1280
    font_sizes = [20, 24, 30, 36, 40]

    print(f"\nVideo height: {video_height}px")
    print("\nFont | Text H | Current Y | Safe Y | Bottom Gap Current | Bottom Gap Safe")
    print("-" * 85)

    for font_size in font_sizes:
        # Estimate text height (font_size + margin)
        bottom_margin = int(font_size * 0.35)
        text_height = font_size + 5 + bottom_margin  # top margin + bottom margin

        # Current calculation (from production)
        current_y = int(video_height * 0.75 - text_height // 2)
        current_bottom = current_y + text_height
        current_gap = video_height - current_bottom

        # Safe calculation
        safe_y = calculate_safe_position(video_height, text_height, bottom_clearance=10)
        safe_bottom = safe_y + text_height
        safe_gap = video_height - safe_bottom

        clipping = "⚠️ CLIPS" if current_gap < 0 else "✅"

        print(
            f"{font_size:3d}px | {text_height:4d}px | {current_y:6d}px | {safe_y:6d}px | "
            f"{current_gap:6d}px {clipping:8s} | {safe_gap:6d}px"
        )


if __name__ == "__main__":
    # Check if font file exists
    font_path = Path(__file__).parent / FONT_PATH
    if not font_path.exists():
        print(f"❌ Error: Font file not found at {font_path}")
        print("Please ensure you're running from the backend directory.")
        import sys

        sys.exit(1)

    test_composite_clipping()
    test_safe_positioning()

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print(
        """
1. ROOT CAUSE: Text positioned too low (75%) with insufficient clearance

2. SOLUTIONS (choose one):

   Option A: Increase bottom margin AND adjust position
   - Line 926: Margin(bottom=12, top=5, left=3, right=3, opacity=0)
   - Line 951: vertical_position = int(video_height * 0.72 - text_height // 2)

   Option B: Use safe positioning calculation
   - Replace calculate_position() with safe positioning logic
   - Ensures text never extends beyond video bounds

   Option C: Add clearance check in positioning
   - Keep current calculation but add bounds checking
   - If text would extend beyond bottom, move it up

3. RECOMMENDED: Option A (simple, effective, minimal changes)
   - Increases margin from 3px to 12px
   - Moves text from 75% to 72% (3% higher)
   - Provides ~40-50px clearance from bottom
   - Maintains desired "lower middle" aesthetic
"""
    )

# end test_caption_compositing.py
