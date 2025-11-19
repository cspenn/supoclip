# start test_caption_clipping_1080p.py
"""
Test caption clipping at 1080p resolution.

The user's screenshot likely shows clipping at 1080p (1080x1920).
At higher resolution, larger font sizes may cause text to extend beyond canvas.
"""

from pathlib import Path
from moviepy import TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import Margin
from PIL import Image, ImageDraw
import numpy as np

# Test configuration
FONT_PATH = "fonts/TikTokSans-Regular.ttf"
TEST_OUTPUT_DIR = Path("/tmp/caption_1080p_tests")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


def test_resolution_clipping():
    """Test clipping at different resolutions."""
    print("="*60)
    print("CAPTION CLIPPING AT DIFFERENT RESOLUTIONS")
    print("="*60)

    resolutions = {
        "480p": (480, 854),
        "720p": (720, 1280),
        "1080p": (1080, 1920),
    }

    test_text = "what happened instead."
    duration = 1.0

    for res_name, (video_width, video_height) in resolutions.items():
        print(f"\n{'='*60}")
        print(f"Resolution: {res_name} ({video_width}x{video_height})")
        print("="*60)

        # Calculate font size (same logic as production: line 1042)
        base_font_size = 24
        calculated_font_size = max(20, min(40, int(base_font_size * (video_width / 720))))

        print(f"Calculated font size: {calculated_font_size}px (from base {base_font_size}px)")

        # Test with current production settings
        print(f"\nCurrent production settings (bottom_margin=3px, y_percent=75%):")

        text_clip = TextClip(
            text=test_text,
            font=FONT_PATH,
            font_size=calculated_font_size,
            color="#FFFFFF",
            stroke_color="black",
            stroke_width=1,
            method="label",
            text_align="center",
        )

        # Current production margin
        text_clip = text_clip.with_effects([
            Margin(bottom=3, top=3, left=2, right=2, opacity=0)
        ])

        text_width, text_height = text_clip.size
        print(f"  TextClip size: {text_width}x{text_height}")

        # Current production position calculation (line 951)
        vertical_position = int(video_height * 0.75 - text_height // 2)
        print(f"  Y-position: {vertical_position}px")

        text_bottom = vertical_position + text_height
        clearance = video_height - text_bottom

        print(f"  Text bottom: {text_bottom}px")
        print(f"  Video height: {video_height}px")
        print(f"  Clearance: {clearance}px", end="")

        if clearance < 10:
            print(" ⚠️  TOO CLOSE TO EDGE!")
        elif clearance < 0:
            print(" ❌ CLIPPING WILL OCCUR!")
        else:
            print(" ✅")

        # Create composite and save frame
        background = ColorClip(
            size=(video_width, video_height),
            color=(30, 30, 30),
            duration=duration
        )

        text_clip_positioned = text_clip.with_duration(duration).with_position(
            ("center", vertical_position)
        )

        final_clip = CompositeVideoClip([background, text_clip_positioned])
        frame = final_clip.get_frame(0.5)

        # Scale down for easier viewing (keep aspect ratio)
        if video_width > 720:
            scale = 720 / video_width
            new_width = 720
            new_height = int(video_height * scale)
            img = Image.fromarray(frame).resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            img = Image.fromarray(frame)
            new_width, new_height = video_width, video_height

        # Draw annotations (scaled)
        draw = ImageDraw.Draw(img)
        scale_x = new_width / video_width
        scale_y = new_height / video_height

        # Text bounding box (red)
        text_left = int((video_width - text_width) // 2 * scale_x)
        text_right = int((text_left + text_width * scale_x))
        text_top = int(vertical_position * scale_y)
        text_bottom_scaled = int(min(text_bottom, video_height) * scale_y)

        draw.rectangle(
            [(text_left, text_top), (text_right, text_bottom_scaled)],
            outline="red",
            width=2
        )

        # Video bottom edge (yellow)
        bottom_line_y = int((video_height - 10) * scale_y)
        draw.line([(0, bottom_line_y), (new_width, bottom_line_y)], fill="yellow", width=2)

        # Center line (green)
        center_y = int(video_height * 0.75 * scale_y)
        draw.line([(0, center_y), (new_width, center_y)], fill="green", width=1)

        output_path = TEST_OUTPUT_DIR / f"current_production_{res_name}.png"
        img.save(output_path)
        print(f"  Saved: {output_path}")

        # Cleanup
        final_clip.close()
        text_clip_positioned.close()
        text_clip.close()
        background.close()


def test_1080p_with_fixes():
    """Test potential fixes specifically for 1080p."""
    print("\n" + "="*60)
    print("1080p CLIPPING FIX COMPARISON")
    print("="*60)

    video_width, video_height = 1080, 1920
    base_font_size = 24
    calculated_font_size = max(20, min(40, int(base_font_size * (video_width / 720))))
    test_text = "what happened instead."
    duration = 1.0

    print(f"\nVideo: {video_width}x{video_height} (1080p)")
    print(f"Font size: {calculated_font_size}px")

    test_cases = [
        {
            "name": "current_production",
            "bottom_margin": 3,
            "y_percent": 0.75,
            "description": "Current (3px margin, 75% position)"
        },
        {
            "name": "fix_option_a",
            "bottom_margin": 12,
            "y_percent": 0.72,
            "description": "Fix A (12px margin, 72% position)"
        },
        {
            "name": "fix_option_b",
            "bottom_margin": 15,
            "y_percent": 0.75,
            "description": "Fix B (15px margin, 75% position)"
        },
        {
            "name": "fix_option_c",
            "bottom_margin": 8,
            "y_percent": 0.73,
            "description": "Fix C (8px margin, 73% position)"
        },
    ]

    for test_case in test_cases:
        print(f"\n{'-'*60}")
        print(f"{test_case['description']}")

        text_clip = TextClip(
            text=test_text,
            font=FONT_PATH,
            font_size=calculated_font_size,
            color="#FFFFFF",
            stroke_color="black",
            stroke_width=1,
            method="label",
            text_align="center",
        )

        text_clip = text_clip.with_effects([
            Margin(
                bottom=test_case["bottom_margin"],
                top=5,
                left=3,
                right=3,
                opacity=0
            )
        ])

        text_width, text_height = text_clip.size
        vertical_position = int(video_height * test_case["y_percent"] - text_height // 2)

        text_bottom = vertical_position + text_height
        clearance = video_height - text_bottom

        print(f"  TextClip: {text_width}x{text_height}")
        print(f"  Y-position: {vertical_position}px (center at {test_case['y_percent']*100}%)")
        print(f"  Text bottom: {text_bottom}px")
        print(f"  Clearance: {clearance}px", end="")

        if clearance < 10:
            print(" ⚠️  TOO CLOSE!")
        elif clearance < 0:
            print(" ❌ CLIPS!")
        else:
            print(" ✅")

        # Create composite
        background = ColorClip(
            size=(video_width, video_height),
            color=(30, 30, 30),
            duration=duration
        )

        text_clip_positioned = text_clip.with_duration(duration).with_position(
            ("center", vertical_position)
        )

        final_clip = CompositeVideoClip([background, text_clip_positioned])
        frame = final_clip.get_frame(0.5)

        # Scale to 720p for viewing
        img = Image.fromarray(frame).resize((720, 1280), Image.Resampling.LANCZOS)

        # Draw annotations
        draw = ImageDraw.Draw(img)
        scale_x = 720 / video_width
        scale_y = 1280 / video_height

        text_left = int((video_width - text_width) // 2 * scale_x)
        text_right = int((text_left + text_width * scale_x))
        text_top = int(vertical_position * scale_y)
        text_bottom_scaled = int(min(text_bottom, video_height) * scale_y)

        draw.rectangle(
            [(text_left, text_top), (text_right, text_bottom_scaled)],
            outline="red",
            width=2
        )

        # Bottom edge
        bottom_line_y = int((video_height - 10) * scale_y)
        draw.line([(0, bottom_line_y), (720, bottom_line_y)], fill="yellow", width=2)

        # Center line
        center_y = int(video_height * test_case["y_percent"] * scale_y)
        draw.line([(0, center_y), (720, center_y)], fill="green", width=1)

        output_path = TEST_OUTPUT_DIR / f"1080p_{test_case['name']}.png"
        img.save(output_path)
        print(f"  Saved: {output_path}")

        # Cleanup
        final_clip.close()
        text_clip_positioned.close()
        text_clip.close()
        background.close()


if __name__ == "__main__":
    # Check font
    font_path = Path(__file__).parent / FONT_PATH
    if not font_path.exists():
        print(f"❌ Error: Font file not found at {font_path}")
        import sys
        sys.exit(1)

    test_resolution_clipping()
    test_1080p_with_fixes()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\nTest images saved to: {TEST_OUTPUT_DIR}")
    print("\nVisualization guide:")
    print("  - Red box: TextClip bounding box")
    print("  - Yellow line: Video bottom edge")
    print("  - Green line: Text center position")
    print("\nRecommended fix for 1080p clipping:")
    print("  1. Increase bottom margin from 3px to 12px (line 926)")
    print("  2. Adjust position from 75% to 72% (line 951)")
    print("\nThis provides adequate clearance while maintaining")
    print("the desired 'lower middle' caption placement.")

# end test_caption_clipping_1080p.py
