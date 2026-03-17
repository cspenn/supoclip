# start src/main.py
"""SupoClip — AI-powered video clipping tool.

Entry point for the NiceGUI + FastAPI application.
"""
import structlog
from nicegui import app, ui  # noqa: F401

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
    """Initialize the database on application startup."""
    cfg = get_config()
    await init_db(cfg.database_url)


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
