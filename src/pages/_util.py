# start src/pages/_util.py
"""Shared presentation and storage helpers for SupoClip NiceGUI pages.

Consolidates logic that would otherwise be duplicated across the page
modules: string truncation for display and on-disk clip-file cleanup.
"""

from collections.abc import Iterable

import structlog

from src.config import get_config

log = structlog.get_logger()

_ELLIPSIS = "…"


def truncate(text: str, max_len: int, *, reserve_ellipsis: bool = False) -> str:
    """Truncate *text* to *max_len* characters, appending an ellipsis when clipped.

    Args:
        text: Source string.
        max_len: Maximum length budget for the source text. The boundary check
            always compares against this value, so a string of exactly
            *max_len* characters is returned untouched.
        reserve_ellipsis: When ``True`` the appended ellipsis is counted within
            *max_len*, so the returned string never exceeds *max_len*
            characters. When ``False`` the ellipsis is added beyond *max_len*.

    Returns:
        The original string when it fits within *max_len*, otherwise a clipped
        string ending in an ellipsis.
    """
    if len(text) <= max_len:
        return text
    cut = max_len - 1 if reserve_ellipsis else max_len
    return text[:cut] + _ELLIPSIS


def remove_clip_files(filenames: Iterable[str]) -> None:
    """Best-effort removal of generated clip files from the clips directory.

    Files are deleted from ``get_config().temp_dir / "clips"``. Missing files
    are ignored. A removal failure (e.g. a permission error) is logged as a
    warning and does not abort the remaining deletions, because callers invoke
    this only after the authoritative database rows have already been removed.

    Args:
        filenames: Clip filenames (basename only) to delete from disk.
    """
    clips_dir = get_config().temp_dir / "clips"
    for filename in filenames:
        path = clips_dir / filename
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("pages.clip_file_remove_failed", path=str(path), error=str(exc))
        else:
            log.debug("pages.clip_file_removed", path=str(path))


# end src/pages/_util.py
