# start src/pages/history.py
"""NiceGUI history page for SupoClip.

Displays all video processing tasks ordered by creation date, with status
badges, clip counts, per-row navigation links, and delete controls.
"""

from datetime import datetime

import structlog
from nicegui import ui
from sqlalchemy import func, select

from src.database import get_session
from src.models import GeneratedClip, Task

log = structlog.get_logger()

# Color mapping from task status to NiceGUI badge color prop.
_STATUS_COLORS: dict[str, str] = {
    "completed": "positive",
    "processing": "warning",
    "pending": "warning",
    "failed": "negative",
}


def _format_date(dt: datetime) -> str:
    """Format a UTC datetime for display.

    Args:
        dt: The datetime to format.

    Returns:
        Human-readable string such as ``"Mar 17, 2026 14:30"``.
    """
    return dt.strftime("%b %d, %Y %H:%M")


def _truncate(text: str, max_len: int = 50) -> str:
    """Truncate a string to *max_len* characters, appending ``…`` if cut.

    Args:
        text: Source string.
        max_len: Maximum character count before truncation.

    Returns:
        Original string if short enough, otherwise a truncated version.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


async def _load_tasks() -> tuple[list[Task], dict[str, int]]:
    """Query all tasks and their clip counts from the database.

    Returns:
        A 2-tuple of ``(tasks, clip_counts)`` where *tasks* is ordered by
        ``created_at DESC`` and *clip_counts* maps ``task_id -> count``.
    """
    async with get_session() as session:
        task_result = await session.execute(select(Task).order_by(Task.created_at.desc()))
        tasks = list(task_result.scalars().all())

        count_result = await session.execute(select(GeneratedClip.task_id, func.count().label("n")).group_by(GeneratedClip.task_id))
        clip_counts: dict[str, int] = {row[0]: row[1] for row in count_result.all()}

    log.debug("history.tasks_loaded", count=len(tasks))
    return tasks, clip_counts


async def delete_task(task_id: str) -> None:
    """Delete a task and all its associated clips from the database.

    Args:
        task_id: Primary key of the task to remove.
    """
    log.info("history.delete_task", task_id=task_id)
    async with get_session() as session:
        task = await session.get(Task, task_id)
        if task:
            await session.delete(task)
            await session.commit()
            log.info("history.task_deleted", task_id=task_id)
        else:
            log.warning("history.task_not_found", task_id=task_id)

    ui.navigate.reload()


def _render_navigation() -> None:
    """Render the top navigation bar with links to Home and Settings."""
    with ui.row().classes("w-full items-center gap-4 mb-6"):
        ui.link("Home", "/").classes("text-blue-600 hover:underline")
        ui.link("Settings", "/settings").classes("text-blue-600 hover:underline")
        ui.label("History").classes("text-2xl font-bold ml-auto")


def _render_task_row(task: Task, clip_count: int) -> None:
    """Render a single task row inside a card.

    Args:
        task: The Task ORM object to display.
        clip_count: Number of GeneratedClip rows belonging to this task.
    """
    color = _STATUS_COLORS.get(task.status, "grey")
    display_url = _truncate(task.source_url)
    formatted_date = _format_date(task.created_at)
    clip_label = f"{clip_count} clip{'s' if clip_count != 1 else ''}"

    with ui.card().classes("w-full p-4 mb-2"):  # noqa: SIM117
        with ui.row().classes("w-full items-center gap-4 flex-wrap"):
            ui.link(display_url, f"/task/{task.id}").classes("text-blue-600 hover:underline flex-1 min-w-0 truncate")
            ui.badge(task.status, color=color)
            ui.label(formatted_date).classes("text-sm text-gray-500")
            ui.label(clip_label).classes("text-sm text-gray-600")
            ui.button(
                icon="delete",
                on_click=lambda t_id=task.id: delete_task(t_id),  # type: ignore[reportArgumentType]
            ).props("flat dense color=negative").tooltip("Delete task")


def _render_empty_state() -> None:
    """Render the empty-state message when no tasks exist."""
    with ui.column().classes("w-full items-center mt-16 gap-4"):
        ui.icon("video_library", size="4rem").classes("text-gray-300")
        ui.label("No clips yet — start by processing a video").classes("text-lg text-gray-500")
        ui.link("Process a video now", "/").classes("text-blue-600 hover:underline text-base")


async def render() -> None:
    """Render the history page.

    Queries all tasks from the database and displays them as a card list
    ordered by most recently created. Shows an empty-state message when
    no tasks have been created yet.
    """
    log.debug("history.render")
    _render_navigation()

    with ui.row().classes("w-full items-center justify-between mb-4"):
        ui.label("Your processed videos").classes("text-lg font-semibold")
        ui.button(
            "Refresh",
            icon="refresh",
            on_click=ui.navigate.reload,
        ).props("flat")

    try:
        tasks, clip_counts = await _load_tasks()
    except Exception as exc:
        log.error("history.load_failed", error=str(exc))
        ui.notify("Failed to load history. Please refresh.", type="negative")
        return

    if not tasks:
        _render_empty_state()
        return

    with ui.column().classes("w-full gap-2"):
        for task in tasks:
            count = clip_counts.get(task.id, 0)
            _render_task_row(task, count)


# end src/pages/history.py
