# start src/main.py
"""SupoClip — AI-powered video clipping tool.

Entry point for the NiceGUI + FastAPI application.
"""

import structlog
from nicegui import app, ui

from src.config import get_config
from src.database import init_db

log = structlog.get_logger()


@ui.page("/")
async def home_page() -> None:
    """Render the home page."""
    from src.pages.home import render

    await render()


@ui.page("/task/{task_id}")
async def task_page(task_id: str) -> None:
    """Render the task detail page."""
    from src.pages.task import render

    await render(task_id)


@ui.page("/history")
async def history_page() -> None:
    """Render the task history page."""
    from src.pages.history import render

    await render()


@ui.page("/settings")
async def settings_page() -> None:
    """Render the settings page."""
    from src.pages.settings import render

    await render()


async def _startup() -> None:
    """Initialize the database and mount static clip serving on startup."""
    cfg = get_config()
    cfg.ensure_temp_dirs()
    await init_db(cfg.database_url)
    # Serve generated clips so the task page can play and download them.
    # Without this mount every /clips/{filename} request 404s (audit C-2).
    # Guard against duplicate registration on hot reload / repeated startup.
    clips_dir = cfg.temp_dir / "clips"
    already_mounted = any(getattr(route, "path", "").startswith("/clips") for route in app.routes)
    if not already_mounted:
        app.add_media_files("/clips", clips_dir)


async def _shutdown() -> None:
    """Close the database on application shutdown."""
    from src.database import close_db

    await close_db()


def main() -> None:
    """Start the SupoClip application."""
    log.info("supoclip.starting", port=8008)
    app.on_startup(_startup)
    app.on_shutdown(_shutdown)
    ui.run(title="SupoClip", port=8008, show=False, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
# end src/main.py
