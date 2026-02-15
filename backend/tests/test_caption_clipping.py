# start test_caption_clipping.py
"""
Visual test for caption clipping issue.

This script reproduces the caption clipping problem where text with descenders
(letters like g, p, y, j) gets cut off at the bottom despite margin application.
"""

import sys
from pathlib import Path


from moviepy import TextClip
from moviepy.video.fx import Margin
from PIL import Image, ImageDraw
import numpy as np

# Test configuration
FONT_PATH = "fonts/TikTokSans-Regular.ttf"
TEST_OUTPUT_DIR = Path("/tmp/caption_tests")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


def create_test_caption(
    text: str,
    font_size: int,
    bottom_margin: int,
    top_margin: int = 5,
    left_margin: int = 3,
    right_margin: int = 3,
    test_name: str = "test",
) -> tuple[TextClip, Path]:
    """
    Create a test caption with specified margins.

    Args:
        text: Text to render (should include letters with descenders)
        font_size: Font size in pixels
        bottom_margin: Bottom margin in pixels
        top_margin: Top margin in pixels
        left_margin: Left margin in pixels
        right_margin: Right margin in pixels
        test_name: Name for the output file

    Returns:
        Tuple of (TextClip, output_path)
    """
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"Text: '{text}'")
    print(f"Font size: {font_size}px")
    print(
        f"Margins: top={top_margin}, bottom={bottom_margin}, left={left_margin}, right={right_margin}"
    )

    # Create text clip exactly as done in production code
    text_clip = TextClip(
        text=text,
        font=FONT_PATH,
        font_size=font_size,
        color="#FFFFFF",
        stroke_color="black",
        stroke_width=1,
        method="label",
        text_align="center",
    )

    print(f"TextClip size before margin: {text_clip.size}")

    # Apply margin
    text_clip = text_clip.with_effects(
        [
            Margin(
                bottom=bottom_margin,
                top=top_margin,
                left=left_margin,
                right=right_margin,
                opacity=0,
            )
        ]
    )

    print(f"TextClip size after margin: {text_clip.size}")

    # Get a frame and save it
    frame = text_clip.get_frame(0)

    # Convert frame to proper format for PIL
    if frame.dtype != np.uint8:
        frame = (frame * 255).astype(np.uint8)

    # Ensure RGB format
    if len(frame.shape) == 2:
        # Grayscale to RGB
        frame = np.stack([frame, frame, frame], axis=-1)
    elif frame.shape[-1] == 4:
        # RGBA to RGB
        frame = frame[:, :, :3]

    img = Image.fromarray(frame)

    # Add visual guides to detect clipping
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Draw red border to show exact edges
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline="red", width=1)

    # Draw margin guides (green lines)
    if top_margin > 0:
        draw.line([(0, top_margin), (width, top_margin)], fill="green", width=1)
    if bottom_margin > 0:
        draw.line(
            [(0, height - bottom_margin), (width, height - bottom_margin)],
            fill="green",
            width=1,
        )
    if left_margin > 0:
        draw.line([(left_margin, 0), (left_margin, height)], fill="green", width=1)
    if right_margin > 0:
        draw.line(
            [(width - right_margin, 0), (width - right_margin, height)],
            fill="green",
            width=1,
        )

    output_path = TEST_OUTPUT_DIR / f"{test_name}.png"
    img.save(output_path)
    print(f"Saved to: {output_path}")

    # Analyze for clipping (check if any white pixels touch the bottom edge)
    frame_rgb = np.array(img.convert("RGB"))
    bottom_row = frame_rgb[-1, :, :]
    white_pixels_at_bottom = np.sum(np.all(bottom_row > [200, 200, 200], axis=1))

    # Check stroke (black pixels) at bottom
    black_pixels_at_bottom = np.sum(np.all(bottom_row < [50, 50, 50], axis=1))

    print(f"White pixels at bottom edge: {white_pixels_at_bottom}")
    print(f"Black/stroke pixels at bottom edge: {black_pixels_at_bottom}")

    if white_pixels_at_bottom > 0 or black_pixels_at_bottom > 0:
        print("⚠️  CLIPPING DETECTED: Text or stroke touches bottom edge!")
    else:
        print("✅ No clipping detected")

    return text_clip, output_path


def run_clipping_tests():
    """Run a series of tests with different margin values."""
    # Test text with descenders (letters that extend below baseline)
    test_text = "what happened instead."

    # Test cases with typical font sizes used in production (20-40px)
    test_cases = [
        {
            "name": "current_production_20px",
            "font_size": 20,
            "bottom_margin": 3,  # Current production value
            "description": "Current production settings with 20px font",
        },
        {
            "name": "current_production_24px",
            "font_size": 24,
            "bottom_margin": 3,  # Current production value
            "description": "Current production settings with 24px font",
        },
        {
            "name": "current_production_30px",
            "font_size": 30,
            "bottom_margin": 3,  # Current production value
            "description": "Current production settings with 30px font",
        },
        {
            "name": "current_production_40px",
            "font_size": 40,
            "bottom_margin": 3,  # Current production value
            "description": "Current production settings with 40px font (maximum)",
        },
        {
            "name": "increased_margin_8px_24px",
            "font_size": 24,
            "bottom_margin": 8,
            "description": "Increased margin (8px) with 24px font",
        },
        {
            "name": "increased_margin_10px_24px",
            "font_size": 24,
            "bottom_margin": 10,
            "description": "Increased margin (10px) with 24px font",
        },
        {
            "name": "increased_margin_12px_40px",
            "font_size": 40,
            "bottom_margin": 12,
            "description": "Increased margin (12px) with 40px font (worst case)",
        },
        {
            "name": "increased_margin_15px_40px",
            "font_size": 40,
            "bottom_margin": 15,
            "description": "Generous margin (15px) with 40px font",
        },
    ]

    results = []

    print("=" * 60)
    print("CAPTION CLIPPING TEST SUITE")
    print("=" * 60)
    print(f"Test text: '{test_text}'")
    print(f"Font: {FONT_PATH}")
    print(f"Output directory: {TEST_OUTPUT_DIR}")
    print()

    for test_case in test_cases:
        print(f"\n{test_case['description']}")

        try:
            text_clip, output_path = create_test_caption(
                text=test_text,
                font_size=test_case["font_size"],
                bottom_margin=test_case["bottom_margin"],
                test_name=test_case["name"],
            )

            results.append(
                {
                    "name": test_case["name"],
                    "description": test_case["description"],
                    "output": output_path,
                    "success": True,
                }
            )

        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(
                {
                    "name": test_case["name"],
                    "description": test_case["description"],
                    "error": str(e),
                    "success": False,
                }
            )

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['name']}: {result['description']}")
        if result["success"]:
            print(f"   Output: {result['output']}")
        else:
            print(f"   Error: {result.get('error', 'Unknown')}")

    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print(
        """
Descender Analysis:
- Typical font descender depth: 20-25% of font size
- Font size 24px: descender ~5-6px
- Font size 30px: descender ~6-7px
- Font size 40px: descender ~8-10px

Stroke Width:
- Current stroke_width=1 extends 1px in all directions
- This adds 1px to bottom requirement

Minimum Margin Calculation:
- For 24px font: descender(6px) + stroke(1px) + buffer(1px) = 8px minimum
- For 30px font: descender(7px) + stroke(1px) + buffer(1px) = 9px minimum
- For 40px font: descender(10px) + stroke(1px) + buffer(2px) = 13px minimum

Recommendation:
- Current margin (3px) is insufficient for all font sizes
- Safe margin for all sizes: 12-15px
- Alternative: Use dynamic margin = int(font_size * 0.35)
"""
    )

    print("\nVisual inspection required:")
    print(f"1. Open images in {TEST_OUTPUT_DIR}")
    print("2. Look for text/stroke touching red border at bottom")
    print("3. Green lines show margin boundaries")
    print("4. Compare current (3px) vs increased (8-15px) margins")


def test_dynamic_margin_calculation():
    """Test dynamic margin calculation based on font size."""
    print("\n" + "=" * 60)
    print("DYNAMIC MARGIN CALCULATION TEST")
    print("=" * 60)

    test_text = "Typography jest"  # Includes descenders: y, p, j
    font_sizes = [16, 20, 24, 30, 36, 40]

    print("\nDynamic margin formula: bottom_margin = int(font_size * 0.35)")
    print("\nFont Size | Dynamic Margin | Test Result")
    print("-" * 50)

    for font_size in font_sizes:
        dynamic_margin = int(font_size * 0.35)

        try:
            text_clip, output_path = create_test_caption(
                text=test_text,
                font_size=font_size,
                bottom_margin=dynamic_margin,
                test_name=f"dynamic_margin_{font_size}px",
            )
            print(
                f"{font_size:4d}px    | {dynamic_margin:4d}px         | ✅ {output_path.name}"
            )
        except Exception as e:
            print(
                f"{font_size:4d}px    | {dynamic_margin:4d}px         | ❌ Error: {e}"
            )


if __name__ == "__main__":
    # Check if font file exists
    font_path = Path(__file__).parent / FONT_PATH
    if not font_path.exists():
        print(f"❌ Error: Font file not found at {font_path}")
        print("Please ensure you're running from the backend directory.")
        sys.exit(1)

    # Run tests
    run_clipping_tests()
    test_dynamic_margin_calculation()

    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print(
        """
1. Review generated images in /tmp/caption_tests/
2. Identify which margin value prevents clipping
3. Update video_utils.py line 926 with correct margin
4. Re-test with actual video processing
5. Verify in production clip output
"""
    )

# end test_caption_clipping.py
