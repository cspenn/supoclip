# start backend/src/font_resolver.py
"""
Font path resolution — resolves font family names to file paths.

Checks bundled fonts, name variations, and the system fonts database.
Extracted from video_utils to avoid circular imports with subtitles.
"""

from pathlib import Path
import logging

from .config import Config

logger = logging.getLogger(__name__)
config = Config()


def resolve_font_path(font_family: str) -> str:
    """Resolve font file path, checking bundled fonts first, then system fonts.

    Priority:
    1. Bundled font (backend/fonts/{font_family}.ttf)
    2. Common name variations (hyphens, underscores)
    3. System fonts database
    4. Default bundled font

    Args:
        font_family: Font name (e.g., "Barlow Condensed Semi Bold")

    Returns:
        Full path to .ttf file
    """
    # First, check if bundled font exists with exact name
    bundled_fonts_dir = Path(__file__).parent.parent / "fonts"
    font_path = bundled_fonts_dir / f"{font_family}.ttf"

    if font_path.exists():
        logger.debug(f"Found bundled font: {font_family}")
        return str(font_path)

    # Try common variations (replace spaces with hyphens/underscores)
    variations = [
        font_family.replace(" ", "-"),
        font_family.replace(" ", "_"),
        font_family.replace(" Semi ", "-Semi"),  # e.g., "Barlow Condensed Semi Bold"
    ]

    for variation in variations:
        font_path = bundled_fonts_dir / f"{variation}.ttf"
        if font_path.exists():
            logger.debug(f"Found bundled font with variation: {variation}")
            return str(font_path)

    # Try system fonts via database (synchronous lookup using SQLAlchemy)
    try:
        from sqlalchemy import create_engine, text

        db_url = config.database_url or "sqlite+aiosqlite:///./supoclip.db"
        sync_url = db_url.replace("sqlite+aiosqlite:", "sqlite:")

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT file_path FROM system_fonts "
                    "WHERE name = :name AND is_valid = 1"
                ),
                {"name": font_family},
            ).fetchone()

        engine.dispose()

        if result and result[0]:
            system_font_path = result[0]
            if Path(system_font_path).exists():
                logger.info(f"Found system font '{font_family}' at: {system_font_path}")
                return system_font_path
            else:
                logger.warning(f"System font file not found: {system_font_path}")
    except Exception as e:
        logger.debug(f"Could not query system fonts database: {e}")

    # Fall back to default font
    default_font = bundled_fonts_dir / "THEBOLDFONT-FREEVERSION.ttf"
    logger.warning(
        f"Font '{font_family}' not found. Using default font: {default_font}"
    )
    return str(default_font)


# end backend/src/font_resolver.py
