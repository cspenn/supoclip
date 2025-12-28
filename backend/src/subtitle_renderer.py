import tempfile
from pathlib import Path
from typing import Optional
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class BrowserSubtitleRenderer:
    """
    Renders subtitles using a headless browser (Playwright) for perfect CSS styling.
    This replaces ImageMagick/MoviePy TextClip for better stability and font handling.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """Start the browser engine."""
        if not self._playwright:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._page = self._browser.new_page()
            logger.info("BrowserSubtitleRenderer: Engine started")

    def stop(self):
        """Stop the browser engine."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._page = None
        logger.info("BrowserSubtitleRenderer: Engine stopped")

    def render_text_to_image(
        self,
        text: str,
        font_family: str,
        font_size: int,
        color: str,
        width: int,
        stroke_width: int = 2,
        stroke_color: str = "black",
        shadow_color: Optional[str] = None,
        shadow_offset: int = 2,
        text_transform: str = "none",  # none, uppercase, lowercase, capitalize
        font_weight: str = "bold",
    ) -> Optional[Path]:
        """
        Render text to a image file using browser CSS with extended styling.
        """
        if not self._page:
            self.start()

        # Build Shadow CSS
        shadow_css = ""
        if shadow_color:
            # Create a hard shadow (PyCaps style) or soft? Hard is better for subtitles.
            shadow_css = (
                f"text-shadow: {shadow_offset}px {shadow_offset}px 0px {shadow_color};"
            )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: transparent;
                    display: flex;
                    justify_content: center;
                    align-items: center;
                    width: {width}px;
                }}
                .subtitle {{
                    font-family: "{font_family}", sans-serif;
                    font-size: {font_size}px;
                    color: {color};
                    text-align: center;
                    font-weight: {font_weight};
                    line-height: 1.2;
                    word-wrap: break-word;
                    text-transform: {text_transform};
                    
                    /* Text Stroke */
                    -webkit-text-stroke: {stroke_width}px {stroke_color};
                    paint-order: stroke fill;
                    
                    /* Shadow */
                    {shadow_css}
                }}
            </style>
        </head>
        <body>
            <div class="subtitle">{text}</div>
        </body>
        </html>
        """

        try:
            # Load HTML content
            self._page.set_content(html_content)

            # Get the element handle
            element = self._page.query_selector(".subtitle")

            if not element:
                logger.error("Could not find subtitle element in rendered page")
                return None

            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                output_path = Path(f.name)

            # Take screenshot of JUST the element with transparency
            element.screenshot(path=str(output_path), omit_background=True)

            return output_path

        except Exception as e:
            logger.error(f"Browser rendering failed: {e}")
            return None
