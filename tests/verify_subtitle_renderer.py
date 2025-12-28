
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from src.subtitle_renderer import BrowserSubtitleRenderer

def verify_styling():
    """Verify that BrowserSubtitleRenderer accepts new style arguments."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("VerifyStyling")
    
    output_dir = Path("tests/output")
    output_dir.mkdir(exist_ok=True)
    
    styles = [
        {
            "name": "default",
            "params": {}
        },
        {
            "name": "styled_uppercase_shadow",
            "params": {
                "stroke_width": 4,
                "stroke_color": "red",
                "shadow_color": "blue",
                "shadow_offset": 5,
                "text_transform": "uppercase",
                "font_weight": "900"
            }
        }
    ]
    
    with BrowserSubtitleRenderer() as renderer:
        for style in styles:
            logger.info(f"Testing style: {style['name']}")
            
            # Combine defaults with params
            args = {
                "text": "Hello World",
                "font_family": "Arial",
                "font_size": 60,
                "color": "white",
                "width": 500
            }
            args.update(style["params"])
            
            output_path = renderer.render_text_to_image(**args)
            
            if output_path and output_path.exists():
                # Move to test output dir
                dest = output_dir / f"test_subtitle_{style['name']}.png"
                import shutil
                shutil.copy(output_path, dest)
                logger.info(f"✅ Generated: {dest}")
            else:
                logger.error(f"❌ Failed to generate {style['name']}")

if __name__ == "__main__":
    verify_styling()
