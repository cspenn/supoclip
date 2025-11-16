# start backend/src/dependencies.py

"""FastAPI dependency injection functions."""

from typing import Optional
from pathlib import Path

from .services.font_service import FontService
from .config import Config

# Global font service instance
_font_service: Optional[FontService] = None


async def get_font_service() -> FontService:
    """Get or create font service instance."""
    global _font_service
    if _font_service is None:
        config = Config()
        _font_service = FontService(db_session=None, temp_dir=Path(config.temp_dir))
    return _font_service


def set_font_service(service: FontService) -> None:
    """Set the global font service instance."""
    global _font_service
    _font_service = service

# end backend/src/dependencies.py
