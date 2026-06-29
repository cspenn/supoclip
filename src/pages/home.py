# start src/pages/home.py
"""NiceGUI home page for SupoClip.

Presents the video input section (YouTube URL or file upload), processing
settings sliders/dropdowns, and a Start button that creates a Task in the
database and launches the pipeline as a background asyncio task.
"""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path

import structlog
from nicegui import ui

from src.config import get_config
from src.database import get_session
from src.models import Task
from src.pages.settings import load_prefs, subtitle_style_from_prefs
from src.services.video_service import ProcessingRequest, process_video

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOLUTIONS: list[str] = ["720p", "1080p"]
_DEFAULT_RESOLUTION = "1080p"
_SLIDER_MIN = 10
_SLIDER_MAX = 90

# Upload hardening (M-10).
_ALLOWED_UPLOAD_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".avi", ".mkv"})
_DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MiB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_youtube_url(text: str) -> bool:
    """Return True if *text* looks like a YouTube URL.

    Args:
        text: Raw string entered by the user.

    Returns:
        True when the string contains a YouTube domain or short-link.
    """
    lowered = text.strip().lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


async def _create_task(source_url: str, source_type: str) -> str:
    """Persist a new Task row and return its UUID.

    Args:
        source_url: YouTube URL or uploaded file path.
        source_type: ``'youtube'`` or ``'upload'``.

    Returns:
        The UUID string of the newly created Task.
    """
    async with get_session() as session:
        task = Task(source_url=source_url, source_type=source_type)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        task_id: str = task.id
    log.info("home.task_created", task_id=task_id, source_type=source_type)
    return task_id


def _max_upload_bytes() -> int:
    """Return the maximum allowed upload size in bytes.

    Reads ``max_upload_bytes`` from the application config when present,
    otherwise falls back to :data:`_DEFAULT_MAX_UPLOAD_BYTES`.

    Returns:
        The upload size ceiling in bytes.
    """
    return int(getattr(get_config(), "max_upload_bytes", _DEFAULT_MAX_UPLOAD_BYTES))


def _unsupported_type_message(suffix: str) -> str:
    """Build the rejection message for an unsupported upload extension.

    Args:
        suffix: The lower-cased file suffix (including the leading dot), or an
            empty string when the uploaded name has no extension.

    Returns:
        A human-readable error string naming the allowed extensions.
    """
    allowed = ", ".join(sorted(ext.lstrip(".") for ext in _ALLOWED_UPLOAD_EXTENSIONS))
    shown = suffix or "(none)"
    return f"Unsupported file type '{shown}'. Allowed: {allowed}."


def _seed_resolution(prefs_resolution: str) -> str:
    """Return a valid resolution preset to seed the home page select.

    Args:
        prefs_resolution: The persisted resolution preference.

    Returns:
        ``prefs_resolution`` when it is a known option, otherwise the
        default resolution.
    """
    return prefs_resolution if prefs_resolution in _RESOLUTIONS else _DEFAULT_RESOLUTION


async def _mark_task_failed(task_id: str, error: str) -> None:
    """Mark a Task row as failed with the given error message.

    Used by the background-pipeline done-callback so a crashed run does not
    leave the task stuck in ``pending``/``processing``.

    Args:
        task_id: Database Task UUID to update.
        error: Error message to persist on the row.
    """
    async with get_session() as session:
        task = await session.get(Task, task_id)
        if task is not None:
            task.status = "failed"
            task.error_message = error
    log.error("home.background_pipeline_failed", task_id=task_id, error=error)


def _on_pipeline_done(task_id: str, fut: asyncio.Future[None]) -> None:
    """Done-callback for the fire-and-forget pipeline task.

    If the background coroutine raised, schedule a DB update marking the task
    ``failed``. Cancelled tasks are ignored.

    Args:
        task_id: Database Task UUID associated with this run.
        fut: The completed background task future.
    """
    if fut.cancelled():
        return
    exc = fut.exception()
    if exc is not None:
        asyncio.create_task(_mark_task_failed(task_id, str(exc)))


async def build_processing_request(
    *,
    source: str,
    task_id: str,
    min_clip_length: int,
    max_clip_length: int,
    output_resolution: str,
) -> ProcessingRequest:
    """Construct a ProcessingRequest with saved style/prompt preferences wired in.

    This closes the audit's C-1 seam: it loads the persisted ``UserPreferences``
    and forwards a real ``SubtitleStyle`` (plus the custom AI prompt and logo
    path) onto the request, so produced clips actually carry the user's
    captions and styling instead of ``subtitle_style=None``.

    Args:
        source: YouTube URL or absolute path to a local video file.
        task_id: Database Task UUID that tracks this run.
        min_clip_length: Minimum clip duration in seconds.
        max_clip_length: Maximum clip duration in seconds.
        output_resolution: Target output resolution string, e.g. ``"1080p"``.

    Returns:
        A fully-populated :class:`ProcessingRequest`.
    """
    prefs = await load_prefs()
    style = subtitle_style_from_prefs(prefs, output_resolution)
    logo_path = Path(prefs.logo_path) if prefs.logo_path else None
    return ProcessingRequest(
        source=source,
        task_id=task_id,
        min_clip_length=min_clip_length,
        max_clip_length=max_clip_length,
        output_resolution=output_resolution,
        subtitle_style=style,
        logo_path=logo_path,
        custom_prompt=prefs.ai_prompt,
    )


async def _start_processing(
    task_id: str,
    source: str,
    min_len: int,
    max_len: int,
    resolution: str,
) -> None:
    """Run the full video processing pipeline for one task.

    Intended to be executed as a fire-and-forget background coroutine so the
    UI can navigate to the task page without waiting for completion.

    Args:
        task_id: Database Task UUID that tracks this run.
        source: YouTube URL or absolute path to an uploaded video file.
        min_len: Minimum clip duration in seconds.
        max_len: Maximum clip duration in seconds.
        resolution: Target output resolution string, e.g. ``"1080p"``.
    """
    request = await build_processing_request(
        source=source,
        task_id=task_id,
        min_clip_length=min_len,
        max_clip_length=max_len,
        output_resolution=resolution,
    )
    await process_video(request)


# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------


async def render() -> None:
    """Render the SupoClip home page.

    Builds the full page layout: header navigation, YouTube URL input, file
    upload widget, processing settings, and the Start button.  On submit the
    function creates a Task row, fires off a background coroutine for pipeline
    processing, and navigates to the task detail page.
    """
    # ---- page-level state ----
    uploaded_path: list[str] = []  # mutable container used as a cell

    # Seed widget defaults from saved preferences (M-10).
    prefs = await load_prefs()
    min_default = prefs.min_clip_length
    max_default = prefs.max_clip_length
    resolution_default = _seed_resolution(prefs.output_resolution)

    # ---- layout ----
    with ui.column().classes("w-full max-w-2xl mx-auto p-4 gap-4"):
        # Header / nav
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("SupoClip").classes("text-3xl font-bold")
            with ui.row().classes("gap-4"):
                ui.link("History", "/history").classes("text-blue-600 hover:underline")
                ui.link("Settings", "/settings").classes("text-blue-600 hover:underline")

        ui.separator()

        # --- YouTube URL section ---
        ui.label("YouTube URL").classes("text-lg font-semibold")
        url_input = ui.input(
            placeholder="https://www.youtube.com/watch?v=...",
        ).classes("w-full")

        # --- File upload section ---
        ui.label("Or upload a local video file").classes("text-lg font-semibold")

        def handle_upload(event: object) -> None:
            """Store the uploaded file path for use on form submit.

            Args:
                event: NiceGUI UploadEventArguments containing the uploaded
                    file content and name.
            """
            # NiceGUI UploadEventArguments provides .name and .content
            name: str = getattr(event, "name", "uploaded_video.mp4")
            content = getattr(event, "content", None)
            if content is None:
                ui.notify("Upload failed: no content received.", color="negative")
                return
            suffix = Path(name).suffix.lower()
            if suffix not in _ALLOWED_UPLOAD_EXTENSIONS:
                ui.notify(_unsupported_type_message(suffix), color="negative")
                return
            data: bytes = content.read() if hasattr(content, "read") else content
            max_bytes = _max_upload_bytes()
            if len(data) > max_bytes:
                ui.notify(
                    f"File too large: {len(data)} bytes exceeds the {max_bytes}-byte limit.",
                    color="negative",
                )
                return
            uploads_dir = get_config().temp_dir / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            save_path = uploads_dir / name
            save_path.write_bytes(data)
            uploaded_path.clear()
            uploaded_path.append(str(save_path))
            ui.notify(f"File ready: {name}", color="positive")
            log.info("home.file_uploaded", path=str(save_path))

        ui.upload(
            on_upload=handle_upload,
            label="Drop or click to upload a video file",
        ).props('accept=".mp4,.mov,.avi,.mkv"').classes("w-full")

        ui.separator()

        # --- Processing settings ---
        ui.label("Processing settings").classes("text-lg font-semibold")

        # Min clip length
        with ui.column().classes("w-full gap-1"):
            min_label = ui.label(f"Min clip length: {min_default}s").classes("text-sm text-gray-700")
            min_slider = ui.slider(min=_SLIDER_MIN, max=_SLIDER_MAX, value=min_default).props("label-always").classes("w-full")
            min_slider.on(
                "update:model-value",
                lambda e: min_label.set_text(f"Min clip length: {int(e.args)}s"),
            )

        # Max clip length
        with ui.column().classes("w-full gap-1"):
            max_label = ui.label(f"Max clip length: {max_default}s").classes("text-sm text-gray-700")
            max_slider = ui.slider(min=_SLIDER_MIN, max=_SLIDER_MAX, value=max_default).props("label-always").classes("w-full")
            max_slider.on(
                "update:model-value",
                lambda e: max_label.set_text(f"Max clip length: {int(e.args)}s"),
            )

        # Resolution
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Output resolution").classes("text-sm text-gray-700")
            resolution_select = ui.select(_RESOLUTIONS, value=resolution_default).classes("w-32")

        ui.separator()

        # --- Start button ---
        async def on_start() -> None:
            """Handle the Start button click.

            Validates input, creates a Task row in the database, fires off the
            pipeline as a background asyncio task, and navigates to the task
            detail page.
            """
            url_text = url_input.value.strip() if url_input.value else ""
            local_path = uploaded_path[0] if uploaded_path else ""

            # Determine source
            if url_text:
                source = url_text
                source_type = "youtube" if _is_youtube_url(url_text) else "upload"
            elif local_path:
                source = local_path
                source_type = "upload"
            else:
                ui.notify(
                    "Please enter a YouTube URL or upload a video file.",
                    color="negative",
                )
                return

            min_len = int(min_slider.value)
            max_len = int(max_slider.value)

            if min_len >= max_len:
                ui.notify(
                    "Min clip length must be less than max clip length.",
                    color="negative",
                )
                return

            resolution = str(resolution_select.value)

            try:
                task_id = await _create_task(source, source_type)
            except Exception as exc:
                log.error("home.task_creation_failed", error=str(exc))
                ui.notify(f"Failed to create task: {exc}", color="negative")
                return

            # Fire-and-forget background pipeline. A done-callback marks the
            # task 'failed' if the coroutine crashes (M-12) so it never stays
            # stuck in 'pending'/'processing'.
            bg_task = asyncio.create_task(_start_processing(task_id, source, min_len, max_len, resolution))
            bg_task.add_done_callback(functools.partial(_on_pipeline_done, task_id))

            ui.notify("Processing started!", color="positive")
            log.info("home.processing_started", task_id=task_id)
            ui.navigate.to(f"/task/{task_id}")

        ui.button("Start Processing", on_click=on_start).classes("w-full bg-blue-600 text-white font-semibold py-3 rounded").props(
            "size=lg"
        )


# end src/pages/home.py
