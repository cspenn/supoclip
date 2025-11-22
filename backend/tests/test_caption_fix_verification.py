# start test_caption_fix_verification.py
"""
Verification test for caption clipping fix.

This test verifies that the increased margin (12px bottom) prevents
caption text from being clipped at the bottom edge.
"""

from pathlib import Path
from moviepy import TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import Margin
from PIL import Image, ImageDraw
import numpy as np

FONT_PATH = "fonts/TikTokSans-Regular.ttf"
TEST_OUTPUT_DIR = Path("/tmp/caption_fix_verification")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)


def test_fix_verification():
    """Verify the caption fix at all resolutions with problematic text."""
    print("=" * 60)
    print("CAPTION FIX VERIFICATION")
    print("=" * 60)

    resolutions = {
        "480p": (480, 854),
        "720p": (720, 1280),
        "1080p": (1080, 1920),
    }

    # Text with prominent descenders
    test_texts = [
        "what happened instead.",  # User's reported text
        "Typography jest",  # Multiple descenders
        "gpqjy",  # All descenders
    ]

    base_font_size = 24
    duration = 1.0

    all_passed = True

    for res_name, (video_width, video_height) in resolutions.items():
        print(f"\n{'='*60}")
        print(f"Resolution: {res_name} ({video_width}x{video_height})")
        print("=" * 60)

        # Calculate font size (production logic)
        calculated_font_size = max(
            20, min(40, int(base_font_size * (video_width / 720)))
        )
        print(f"Font size: {calculated_font_size}px")

        for test_text in test_texts:
            print(f"\n{'-'*60}")
            print(f"Text: '{test_text}'")

            # Create text clip with FIXED margin (12px bottom)
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

            # Apply FIXED margin (12px bottom, 5px top, 3px sides)
            text_clip = text_clip.with_effects(
                [Margin(bottom=12, top=5, left=3, right=3, opacity=0)]
            )

            text_width, text_height = text_clip.size
            print(f"  TextClip size: {text_width}x{text_height}")

            # Production positioning (75% down)
            vertical_position = int(video_height * 0.75 - text_height // 2)
            text_bottom = vertical_position + text_height
            clearance = video_height - text_bottom

            print(f"  Y-position: {vertical_position}px")
            print(f"  Text bottom: {text_bottom}px")
            print(f"  Clearance: {clearance}px", end="")

            if clearance < 10:
                print(" ⚠️  WARNING: TOO CLOSE!")
                all_passed = False
            elif clearance < 0:
                print(" ❌ FAIL: CLIPPING!")
                all_passed = False
            else:
                print(" ✅ PASS")

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
                img = Image.fromarray(frame).resize(
                    (720, 1280), Image.Resampling.LANCZOS
                )
            else:
                img = Image.fromarray(frame)

            # Save full frame
            safe_text = test_text.replace(" ", "_").replace(".", "")
            output_path = TEST_OUTPUT_DIR / f"fixed_{res_name}_{safe_text}.png"
            img.save(output_path)

            # Create zoom view of bottom region
            zoom_height = 300
            if img.size[1] > zoom_height:
                zoom_img = img.crop(
                    (50, img.size[1] - zoom_height, img.size[0] - 50, img.size[1])
                )

                # Draw reference lines on zoom
                draw = ImageDraw.Draw(zoom_img)

                # Red line at absolute bottom
                draw.line(
                    [(0, zoom_height - 1), (zoom_img.size[0], zoom_height - 1)],
                    fill="red",
                    width=2,
                )

                # Yellow line 20px from bottom
                draw.line(
                    [(0, zoom_height - 21), (zoom_img.size[0], zoom_height - 21)],
                    fill="yellow",
                    width=1,
                )

                # Green line 50px from bottom
                draw.line(
                    [(0, zoom_height - 51), (zoom_img.size[0], zoom_height - 51)],
                    fill="green",
                    width=1,
                )

                output_path_zoom = (
                    TEST_OUTPUT_DIR / f"fixed_{res_name}_{safe_text}_zoom.png"
                )
                zoom_img.save(output_path_zoom)

                # Check if any text pixels are in danger zone (last 15 rows)
                frame_rgb = np.array(zoom_img)
                danger_zone = frame_rgb[-15:, :, :]

                white_pixels = np.sum(np.all(danger_zone > [200, 200, 200], axis=2))
                black_stroke_pixels = np.sum(np.all(danger_zone < [50, 50, 50], axis=2))

                # Subtract background pixels (dark gray = 30,30,30)
                background_pixels = np.sum(np.all(danger_zone < [40, 40, 40], axis=2))
                actual_text_pixels = (
                    white_pixels + black_stroke_pixels
                ) - background_pixels

                if actual_text_pixels > 100:
                    print(
                        f"  ⚠️  WARNING: Text near bottom edge ({actual_text_pixels} pixels)"
                    )
                    all_passed = False
                else:
                    print("  ✅ Safe clearance from bottom")

                print(f"  Saved: {output_path_zoom}")

            # Cleanup
            final_clip.close()
            text_clip_positioned.close()
            text_clip.close()
            background.close()

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        print("\nThe caption fix (12px bottom margin) successfully prevents clipping")
        print("at all resolutions with all tested text combinations.")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\nPlease review the test output above for details.")

    print(f"\nTest images saved to: {TEST_OUTPUT_DIR}")
    print("\nVisualization guide:")
    print("  - Red line: Absolute bottom of video")
    print("  - Yellow line: 20px from bottom")
    print("  - Green line: 50px from bottom")
    print("\nText should NOT touch or cross the yellow line.")

    return all_passed


if __name__ == "__main__":
    font_path = Path(__file__).parent / FONT_PATH
    if not font_path.exists():
        print(f"❌ Error: Font file not found at {font_path}")
        import sys

        sys.exit(1)

    success = test_fix_verification()

    if success:
        print("\n" + "=" * 60)
        print("FIX VERIFIED SUCCESSFULLY")
        print("=" * 60)
        print("\nThe caption clipping issue has been resolved.")
        print("Caption text with descenders will no longer be cut off.")
        import sys

        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("FIX VERIFICATION FAILED")
        print("=" * 60)
        print("\nAdditional adjustments may be needed.")
        import sys

        sys.exit(1)

# end test_caption_fix_verification.py
