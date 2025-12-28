import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.video_service import VideoService

async def run_e2e_test():
    # Setup
    video_url = "https://www.youtube.com/watch?v=jYjJjYeMt3k"
    
    # Create dummy logo
    fixtures_dir = Path("tests/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    logo_path = fixtures_dir / "e2e_logo.png"
    
    if not logo_path.exists():
        print("Creating dummy logo...")
        from moviepy import ColorClip
        # Create green square logo
        ColorClip(size=(100, 100), color=(0, 255, 0), duration=1).save_frame(str(logo_path), t=0)
        
    print(f"Starting E2E test with URL: {video_url}")
    print(f"Using logo: {logo_path.absolute()}")
    
    try:
        # Call the service method that orchestrates everything
        print("Calling VideoService.process_video_complete...")
        result = await VideoService.process_video_complete(
            url=video_url,
            source_type="youtube",
            font_family="TikTokSans-Regular",
            font_size=24,
            font_color="#FFFFFF",
            min_length=10,
            max_length=30,
            output_resolution="720p",
            logo_path=str(logo_path.absolute()),
            logo_corner_position="top-left"
        )
        
        print("\n✅ Processing complete!")
        print(f"Summary: {result.get('summary')}")
        print(f"Generated {len(result.get('clips', []))} clips")
        
        for clip in result.get('clips', []):
            print(f"Clip: {clip['filename']}")
            print(f"Path: {clip['path']}")
            
    except Exception as e:
        print(f"\n❌ E2E Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
