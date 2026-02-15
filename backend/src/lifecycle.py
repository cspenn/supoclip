# start backend/src/lifecycle.py
"""
Application lifecycle management.
Handles startup and shutdown events, including database initialization,
font service setup, and job queue management.
"""

from contextlib import asynccontextmanager
from pathlib import Path
import logging
import asyncio
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from .database import init_db, close_db, AsyncSessionLocal
from .services.font_service import FontService
from .dependencies import set_font_service
from .workers.local_queue import get_job_queue
from .config import Config

logger = logging.getLogger(__name__)


async def initialize_font_service(db_session: AsyncSession, config: Config) -> None:
    """Initialize font service with database session."""
    font_service = FontService(db_session=db_session, temp_dir=Path(config.temp_dir))
    set_font_service(font_service)

    logger.info("🚀 Initializing FontService...")

    # Load bundled fonts
    bundled = await font_service.get_bundled_fonts()
    await font_service.cache_fonts(bundled)
    logger.info(f"✅ Loaded {len(bundled)} bundled fonts")

    # Detect and cache system fonts in background
    asyncio.create_task(_detect_system_fonts_background(font_service))


async def _detect_system_fonts_background(font_service: FontService) -> None:
    """Background task to detect and cache system fonts."""
    try:
        logger.info("🔍 Starting background system font detection...")
        system_fonts = await font_service.detect_system_fonts()
        await font_service.cache_fonts(system_fonts)
        logger.info(f"✅ Detected and cached {len(system_fonts)} system fonts")
    except Exception as e:
        logger.error(f"❌ Background font detection failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    config = Config()

    try:
        await init_db()
        logger.info("🟢 Database initialized")

        # Initialize font service
        async with AsyncSessionLocal() as session:
            await initialize_font_service(session, config)

        # Initialize job queue
        queue = get_job_queue()
        await queue.start_workers()
        logger.info("🟢 Job queue workers started")

        yield
    finally:
        # Shutdown job queue
        try:
            queue = get_job_queue()
            await queue.stop_workers()
            logger.info("🛑 Job queue workers stopped")
        except Exception as e:
            logger.error(f"🛑 Error stopping workers: {e}")

        await close_db()
        logger.info("🛑 Database connection closed")


# end backend/src/lifecycle.py
