# start test_descender_clipping.py
"""
Test caption clipping with words that have prominent descenders.

Letters with descenders: g, j, p, q, y
The user's screenshot shows "what happened instead." - which has 'p' descenders.
"""

from pathlib import Path
from moviepy import TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import Margin
from PIL import Image, ImageDraw, ImageFont
import numpy as np

FONT_PATH = "fonts/TikTokSans-Regular.ttf"
TEST_OUTPUT_DIR = Path("/tmp/descender_tests")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


def measure_descender_depth():
    """Measure actual descender depth for the font at different sizes."""
    print("=" * 60)
    print("FONT DESCENDER DEPTH MEASUREMENT")
    print("=" * 60)

    font_path = Path(__file__).parent / FONT_PATH
    test_texts = [
        "ABCDEFGH",  # No descenders (uppercase)
        "abcdefgh",  # No descenders (lowercase without descenders)
        "gpqjy",  # All descenders
        "what happened instead.",  # User's reported text
        "Typography",  # Mixed
    ]

    font_sizes = [20, 24, 30, 36, 40]

    for size in font_sizes:
        print(f"\nFont size: {size}px")
        print("-" * 50)

        pil_font = ImageFont.truetype(str(font_path), size)

        for text in test_texts:
            # Get bounding box
            bbox = pil_font.getbbox(text)
            # bbox is (left, top, right, bottom) relative to the anchor
            left, top, right, bottom = bbox

            # Ascent/descent calculation
            height = bottom - top
            descent = bottom  # How far below baseline

            print(f"  '{text:25s}': height={height:2d}px, descent={descent:2d}px")


def test_descender_clipping_with_stroke():
    """Test if stroke extends descenders enough to cause clipping."""
    print("\n" + "=" * 60)
    print("DESCENDER + STROKE CLIPPING TEST")
    print("=" * 60)

    video_width, video_height = 720, 1280
    test_text = "what happened instead."
    duration = 1.0

    test_cases = [
        {
            "name": "no_stroke_3px_margin",
            "stroke_width": 0,
            "bottom_margin": 3,
            "description": "No stroke, 3px margin",
        },
        {
            "name": "stroke_1px_3px_margin",
            "stroke_width": 1,
            "bottom_margin": 3,
            "description": "1px stroke, 3px margin (CURRENT)",
        },
        {
            "name": "stroke_1px_12px_margin",
            "stroke_width": 1,
            "bottom_margin": 12,
            "description": "1px stroke, 12px margin (PROPOSED)",
        },
        {
            "name": "stroke_2px_3px_margin",
            "stroke_width": 2,
            "bottom_margin": 3,
            "description": "2px stroke, 3px margin (worst case)",
        },
    ]

    font_size = 30

    for test_case in test_cases:
        print(f"\n{'-'*60}")
        print(f"{test_case['description']}")

        text_clip = TextClip(
            text=test_text,
            font=FONT_PATH,
            font_size=font_size,
            color="#FFFFFF",
            stroke_color="black" if test_case["stroke_width"] > 0 else None,
            stroke_width=test_case["stroke_width"],
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
        print(f"  TextClip size: {text_width}x{text_height}")

        # Calculate position (75% down)
        vertical_position = int(video_height * 0.75 - text_height // 2)

        text_bottom = vertical_position + text_height
        clearance = video_height - text_bottom

        print(f"  Y-position: {vertical_position}px")
        print(f"  Text bottom: {text_bottom}px")
        print(f"  Clearance: {clearance}px", end="")

        if clearance < 5:
            print(" ❌ LIKELY CLIPPING!")
        elif clearance < 15:
            print(" ⚠️  TOO CLOSE!")
        else:
            print(" ✅")

        # Create composite
        background = ColorClip(
            size=(video_width, video_height), color=(30, 30, 30), duration=duration
        )

        text_clip_positioned = text_clip.with_duration(duration).with_position(
            ("center", vertical_position)
        )

        final_clip = CompositeVideoClip([background, text_clip_positioned])
        frame = final_clip.get_frame(0.5)
        img = Image.fromarray(frame)

        # Zoom into bottom region to see descenders clearly
        zoom_img = img.crop((100, video_height - 200, video_width - 100, video_height))

        # Draw annotations
        draw = ImageDraw.Draw(zoom_img)
        zoom_height = 200
        zoom_offset = video_height - 200

        # Red line at absolute bottom
        draw.line(
            [(0, zoom_height - 1), (zoom_img.size[0], zoom_height - 1)],
            fill="red",
            width=2,
        )

        # Yellow line 10px from bottom
        draw.line(
            [(0, zoom_height - 11), (zoom_img.size[0], zoom_height - 11)],
            fill="yellow",
            width=1,
        )

        # Green line 20px from bottom
        draw.line(
            [(0, zoom_height - 21), (zoom_img.size[0], zoom_height - 21)],
            fill="green",
            width=1,
        )

        output_path = TEST_OUTPUT_DIR / f"{test_case['name']}_zoom.png"
        zoom_img.save(output_path)
        print(f"  Saved zoom: {output_path}")

        # Also save full frame
        output_path_full = TEST_OUTPUT_DIR / f"{test_case['name']}_full.png"
        img.save(output_path_full)

        # Check if pixels exist in danger zone (last 10 rows)
        frame_rgb = np.array(img)
        danger_zone = frame_rgb[-10:, :, :]

        white_pixels = np.sum(np.all(danger_zone > [200, 200, 200], axis=2))
        black_pixels = np.sum(np.all(danger_zone < [50, 50, 50], axis=2))

        if white_pixels > 50 or black_pixels > 50:
            print(
                f"  ⚠️  TEXT IN DANGER ZONE! White={white_pixels}, Black={black_pixels}"
            )

        # Cleanup
        final_clip.close()
        text_clip_positioned.close()
        text_clip.close()
        background.close()


def test_actual_user_scenario():
    """Reproduce the exact scenario from user's screenshot."""
    print("\n" + "=" * 60)
    print("USER SCENARIO REPRODUCTION")
    print("=" * 60)

    # Try different resolutions - user might be using 1080p
    resolutions = {
        "720p": (720, 1280),
        "1080p": (1080, 1920),
    }

    test_text = "what happened instead."
    base_font_size = 24
    duration = 1.0

    for res_name, (video_width, video_height) in resolutions.items():
        print(f"\n{'-'*60}")
        print(f"Resolution: {res_name} ({video_width}x{video_height})")

        # Calculate font size (production logic)
        calculated_font_size = max(
            20, min(40, int(base_font_size * (video_width / 720)))
        )
        print(f"Calculated font size: {calculated_font_size}px")

        # Current production settings
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

        # Current margin
        text_clip = text_clip.with_effects(
            [Margin(bottom=3, top=3, left=2, right=2, opacity=0)]
        )

        text_width, text_height = text_clip.size
        vertical_position = int(video_height * 0.75 - text_height // 2)

        text_bottom = vertical_position + text_height
        clearance = video_height - text_bottom

        print(f"TextClip: {text_width}x{text_height}")
        print(f"Y-position: {vertical_position}px")
        print(f"Text bottom: {text_bottom}px")
        print(f"Clearance: {clearance}px")

        # Create composite
        background = ColorClip(
            size=(video_width, video_height), color=(30, 30, 30), duration=duration
        )

        text_clip_positioned = text_clip.with_duration(duration).with_position(
            ("center", vertical_position)
        )

        final_clip = CompositeVideoClip([background, text_clip_positioned])
        frame = final_clip.get_frame(0.5)

        # Scale to 720p for viewing if needed
        if video_width > 720:
            img = Image.fromarray(frame).resize((720, 1280), Image.Resampling.LANCZOS)
        else:
            img = Image.fromarray(frame)

        # Save full frame
        output_path = TEST_OUTPUT_DIR / f"user_scenario_{res_name}.png"
        img.save(output_path)

        # Zoom into bottom
        zoom_height = 200
        zoom_img = img.crop(
            (100, img.size[1] - zoom_height, img.size[0] - 100, img.size[1])
        )
        output_path_zoom = TEST_OUTPUT_DIR / f"user_scenario_{res_name}_zoom.png"
        zoom_img.save(output_path_zoom)

        print(f"Saved: {output_path}")
        print(f"Saved zoom: {output_path_zoom}")

        # Cleanup
        final_clip.close()
        text_clip_positioned.close()
        text_clip.close()
        background.close()


if __name__ == "__main__":
    font_path = Path(__file__).parent / FONT_PATH
    if not font_path.exists():
        print(f"❌ Error: Font file not found at {font_path}")
        import sys

        sys.exit(1)

    measure_descender_depth()
    test_descender_clipping_with_stroke()
    test_actual_user_scenario()

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nTest images saved to: {TEST_OUTPUT_DIR}")
    print("\nKey findings:")
    print("  1. Check zoom images to see descender rendering")
    print("  2. Red line = absolute bottom of video")
    print("  3. Yellow line = 10px from bottom")
    print("  4. Green line = 20px from bottom")
    print("\nIf text or stroke touches red line, clipping will occur.")

# end test_descender_clipping.py
