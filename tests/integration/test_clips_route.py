# start tests/integration/test_clips_route.py
"""Startup-wiring test for serving generated clips (audit finding C-2).

The task page links to ``/clips/{filename}`` for playback and download, but
``main._startup`` never mounted the clips directory, so every clip 404s. This
test runs the real ``_startup`` and asserts it registers the ``/clips`` static
mount against the configured clips directory (and that the directory is created).

Note on scope: the test suite injects a session-wide *fake* ``nicegui`` (see
``tests/unit/conftest.py``), so the real ASGI server cannot be exercised here to
assert a literal HTTP 200 — serving correctness of ``add_media_files`` is
nicegui's responsibility. We assert the wiring main is responsible for: the
right URL path mapped to the right on-disk directory, which a per-file unit test
of the page could never see.

RED until C-2 / Subtitle Playbook step S3 mounts ``/clips/`` in ``_startup``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.config import get_config


@pytest.mark.asyncio
async def test_startup_mounts_clips_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_startup registers /clips against temp/clips and creates the directory."""
    monkeypatch.setenv("TEMP_DIR", str(tmp_path))
    get_config.cache_clear()

    import nicegui

    from src import main as main_mod

    nicegui.app.reset_mock()

    # init_db is exercised elsewhere; stub it so this test stays focused on the mount.
    with patch.object(main_mod, "init_db", AsyncMock()):
        await main_mod._startup()

    expected_dir = tmp_path / "clips"
    nicegui.app.add_media_files.assert_called_once_with("/clips", expected_dir)
    assert expected_dir.is_dir(), "ensure_temp_dirs did not create the clips directory"

    get_config.cache_clear()


# end tests/integration/test_clips_route.py
