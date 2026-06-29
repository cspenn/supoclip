# start src/pages/task.py
"""NiceGUI task detail page for SupoClip.

Displays real-time processing progress while a task is running, then shows
a grid of generated clips once processing is complete.  Error states are
surfaced with a red banner.
"""

import functools

import structlog
from nicegui import ui
from sqlalchemy import select

from src.database import get_session
from src.models import GeneratedClip, Task
from src.pages._util import remove_clip_files, truncate

log = structlog.get_logger()

_MAX_URL_DISPLAY_LEN = 60

# Polling interval and the maximum wall-clock time the progress timer keeps
# polling before giving up on an apparently stuck task.
_POLL_INTERVAL_SECONDS = 1.0
_MAX_POLL_SECONDS = 1800.0


def _truncate(text: str, max_len: int = _MAX_URL_DISPLAY_LEN) -> str:
    """Truncate a string to *max_len* characters, appending '…' when clipped.

    Thin wrapper over :func:`src.pages._util.truncate` preserving this page's
    historical behaviour (the ellipsis counts toward *max_len*).

    Args:
        text: The string to truncate.
        max_len: Maximum number of characters allowed (including the ellipsis).

    Returns:
        The original string if it fits within *max_len*, otherwise a truncated
        version ending with '…'.
    """
    return truncate(text, max_len, reserve_ellipsis=True)


def _format_seconds(seconds: float) -> str:
    """Format a floating-point second offset as ``MM:SS``.

    Args:
        seconds: Offset in seconds (non-negative).

    Returns:
        Zero-padded ``MM:SS`` string, e.g. ``'01:07'``.
    """
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def _score_color(score: float | None) -> str:
    """Return a Tailwind background colour class based on the AI relevance score.

    Args:
        score: A float in [0, 1] or ``None`` when the score is unavailable.

    Returns:
        A Tailwind CSS class string.
    """
    if score is None:
        return "bg-gray-200 text-gray-700"
    if score >= 0.8:
        return "bg-green-200 text-green-800"
    if score >= 0.6:
        return "bg-yellow-200 text-yellow-800"
    return "bg-red-200 text-red-800"


async def delete_clip(clip_id: str) -> None:
    """Delete a single generated clip row and its file from disk.

    The clip's database row is hard-deleted and its ``.mp4`` file removed from
    the clips directory so per-clip deletion does not leak storage. The page is
    reloaded afterwards.

    Args:
        clip_id: Primary key of the :class:`~src.models.GeneratedClip` to remove.
    """
    log.info("task_page.delete_clip", clip_id=clip_id)
    async with get_session() as session:
        clip: GeneratedClip | None = await session.get(GeneratedClip, clip_id)
        if clip is None:
            log.warning("task_page.clip_not_found", clip_id=clip_id)
            ui.navigate.reload()
            return
        filename = clip.filename
        await session.delete(clip)
        await session.commit()
        log.info("task_page.clip_deleted", clip_id=clip_id)

    remove_clip_files([filename])
    ui.navigate.reload()


def _render_clip_card(clip: GeneratedClip) -> None:
    """Render a single clip card inside the current NiceGUI container.

    The card contains a video player, title, score badge, timing info,
    a download button, and a collapsible transcript.

    Args:
        clip: The :class:`~src.models.GeneratedClip` instance to render.
    """
    with ui.card().classes("w-full shadow-md"):
        # --- video player ---
        ui.video(src=f"/clips/{clip.filename}").classes("w-full rounded")

        with ui.column().classes("p-3 gap-2 w-full"):
            # title + score badge on the same row
            with ui.row().classes("items-center gap-2 flex-wrap"):
                clip_title = clip.title or clip.filename
                ui.label(clip_title).classes("text-base font-semibold flex-1")

                score_pct = f"{clip.score * 100:.0f}%" if clip.score is not None else "N/A"
                colour = _score_color(clip.score)
                ui.badge(f"Score: {score_pct}").classes(f"text-xs px-2 py-0.5 rounded-full {colour}")

                ui.button(
                    icon="delete",
                    on_click=functools.partial(delete_clip, clip.id),  # type: ignore[reportArgumentType]
                ).props("flat dense color=negative").tooltip("Delete clip")

            # timing
            start_fmt = _format_seconds(clip.start_time)
            end_fmt = _format_seconds(clip.end_time)
            ui.label(f"{start_fmt} – {end_fmt}  ({clip.duration:.1f}s)").classes("text-xs text-gray-500")

            # download
            ui.button(
                "Download",
                icon="download",
                on_click=lambda c=clip: ui.download(f"/clips/{c.filename}"),  # type: ignore[reportAttributeAccessIssue]
            ).classes("w-full mt-1").props("flat color=primary")

            # collapsible transcript
            if clip.transcript_text:
                with ui.expansion("Transcript", icon="article").classes("w-full"):
                    ui.label(clip.transcript_text).classes("text-sm text-gray-600 whitespace-pre-wrap")


async def render(task_id: str) -> None:
    """Render the task detail page for *task_id*.

    Fetches the task from the database and renders:

    * A navigation bar with links back to home and history.
    * A progress section that polls the DB every second while the task is
      active (status ``'pending'`` or ``'processing'``).
    * A clip grid once the task reaches ``'completed'`` status.
    * A red error banner if the task has ``'failed'``.
    * A graceful "not found" message when *task_id* does not exist.

    Args:
        task_id: UUID string identifying the :class:`~src.models.Task` to display.
    """
    log.info("task_page.render", task_id=task_id)

    # --- navigation bar ---
    with ui.row().classes("w-full items-center gap-4 p-4 border-b"):
        ui.link("← Home", "/").classes("text-blue-600 hover:underline")
        ui.link("History", "/history").classes("text-blue-600 hover:underline")

    # --- load initial task state ---
    async with get_session() as session:
        task: Task | None = await session.get(Task, task_id)
        if task is None:
            log.warning("task_page.not_found", task_id=task_id)
            with ui.card().classes("m-4 p-4 bg-yellow-50 border border-yellow-300"):
                ui.label(f"Task '{task_id}' not found.").classes("text-yellow-800 font-semibold")
                ui.label("The task may have been deleted or the URL is incorrect.").classes("text-yellow-700 text-sm")
            return

        source_display = _truncate(task.source_url)
        initial_status = task.status
        initial_progress = task.progress
        initial_message = task.progress_message or task.status
        initial_error = task.error_message

        # prefetch clips if already completed
        initial_clips: list[GeneratedClip] = []
        if initial_status == "completed":
            result = await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == task_id).order_by(GeneratedClip.created_at))
            initial_clips = list(result.scalars().all())

    # --- page title ---
    with ui.row().classes("w-full px-4 pt-4 items-center gap-2"):
        ui.label("SupoClip").classes("text-2xl font-bold text-indigo-700")
        ui.label("·").classes("text-gray-400")
        ui.label(source_display).classes("text-sm text-gray-500 truncate flex-1")

    # --- progress section ---
    with ui.column().classes("w-full px-4 py-3 gap-2") as progress_section:
        status_label = ui.label(initial_message).classes("text-sm text-gray-700")
        progress_bar = ui.linear_progress(value=initial_progress / 100.0).classes("w-full")

    # --- error banner (hidden initially unless already failed) ---
    with ui.card().classes("w-full mx-4 mt-2 p-3 bg-red-50 border border-red-300") as error_card:
        error_label = ui.label(initial_error or "").classes("text-red-800 text-sm font-medium")

    error_card.set_visibility(initial_status == "failed" and bool(initial_error))

    # --- clips container ---
    clips_heading = ui.label("Generated Clips").classes("text-lg font-semibold px-4 pt-4")
    clips_heading.set_visibility(initial_status == "completed")

    with ui.grid(columns=2).classes("w-full px-4 gap-4") as clips_grid:
        if initial_status == "completed":
            for clip in initial_clips:
                _render_clip_card(clip)

    async def _show_clips() -> None:
        """Fetch completed clips from DB and populate the clips grid."""
        async with get_session() as session:
            result = await session.execute(select(GeneratedClip).where(GeneratedClip.task_id == task_id).order_by(GeneratedClip.created_at))
            clips = list(result.scalars().all())

        clips_grid.clear()
        with clips_grid:
            for clip in clips:
                _render_clip_card(clip)

        clip_count = len(clips)
        plural = "s" if clip_count != 1 else ""
        status_label.text = f"Done — {clip_count} clip{plural} generated."
        progress_section.set_visibility(True)
        clips_heading.set_visibility(True)
        log.info("task_page.clips_shown", task_id=task_id, count=clip_count)

    # --- timer polling (only needed while task is active) ---
    if initial_status in ("pending", "processing"):
        progress_section.set_visibility(True)
        clips_heading.set_visibility(False)
        poll_elapsed = {"seconds": 0.0}

        async def _refresh() -> None:
            """Poll the DB for the latest task state and update the UI.

            A wall-clock guard stops the timer after ``_MAX_POLL_SECONDS`` so a
            task that is stuck in ``pending``/``processing`` does not poll
            forever.
            """
            poll_elapsed["seconds"] += _POLL_INTERVAL_SECONDS
            if poll_elapsed["seconds"] >= _MAX_POLL_SECONDS:
                poll_timer.active = False
                status_label.text = "Stopped checking for updates — the task appears stuck. Refresh to retry."
                log.warning("task_page.poll_timeout", task_id=task_id, elapsed=poll_elapsed["seconds"])
                return

            async with get_session() as session:
                refreshed: Task | None = await session.get(Task, task_id)

            if refreshed is None:
                poll_timer.active = False
                status_label.text = "Task not found."
                log.warning("task_page.poll_task_missing", task_id=task_id)
                return

            progress_bar.value = refreshed.progress / 100.0
            status_label.text = refreshed.progress_message or refreshed.status

            match refreshed.status:
                case "completed":
                    poll_timer.active = False
                    progress_bar.value = 1.0
                    await _show_clips()
                case "failed":
                    poll_timer.active = False
                    err_msg = refreshed.error_message or "An unknown error occurred."
                    error_label.text = err_msg
                    error_card.set_visibility(True)
                    log.error(
                        "task_page.task_failed",
                        task_id=task_id,
                        error=err_msg,
                    )
                case _:
                    pass  # still running — keep polling

        poll_timer = ui.timer(_POLL_INTERVAL_SECONDS, _refresh)

    elif initial_status == "completed":
        progress_section.set_visibility(False)
    # end src/pages/task.py
