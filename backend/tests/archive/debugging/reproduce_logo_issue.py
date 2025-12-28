import asyncio
from pathlib import Path
import sys

# Add backend directory to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.video_utils import create_optimized_clip
from src.config import Config

# Mock config if needed
config = Config()

import logging
logging.basicConfig(level=logging.INFO)


async def test_logo_overlay():
    # Setup paths (assume running from backend dir)
    fixtures_dir = Path("tests/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    output_dir = Path("tests/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    video_path = fixtures_dir / "sample_video.mp4"
    logo_path = fixtures_dir / "sample_logo.png"
    output_path = output_dir / "logo_test.mp4"
    
    # Create dummy files if they don't exist
    if not video_path.exists():
        print(f"Creating dummy video at {video_path}")
        from moviepy import ColorClip
        # Create 3 second black video
        ColorClip(size=(720, 1280), color=(0,0,0), duration=3).write_videofile(str(video_path), fps=24)
        
    if not logo_path.exists():
        print(f"Creating dummy logo at {logo_path}")
        from moviepy import ColorClip
        # Create red square logo
        ColorClip(size=(100, 100), color=(255,0,0), duration=1).save_frame(str(logo_path), t=0)

    print(f"Testing with logo_path: {logo_path.absolute()}")
    print(f"Output path: {output_path.absolute()}")
    
    try:
        success = create_optimized_clip(
            video_path=video_path,
            start_time=0,
            end_time=2,
            output_path=output_path,
            logo_path=str(logo_path.absolute()),
            logo_position="top-right",
            output_resolution="720p"
        )
        
        if success:
            print("✅ Clip created successfully.")
            print(f"Check output at: {output_path}")
        else:
            print("❌ Failed to create clip.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Exception during clip creation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_logo_overlay())
