# start tests/unit/test_pages_util.py
"""Unit tests for src/pages/_util.py shared page helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.pages._util import remove_clip_files, truncate

# ---------------------------------------------------------------------------
# truncate()
# ---------------------------------------------------------------------------


class TestTruncate:
    """Tests for the shared truncate() helper."""

    def test_short_string_unchanged(self) -> None:
        """Strings within the limit are returned unchanged."""
        assert truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        """A string exactly at max_len is returned untouched (both modes)."""
        s = "a" * 10
        assert truncate(s, 10) == s
        assert truncate(s, 10, reserve_ellipsis=True) == s

    def test_appended_mode_keeps_max_len_chars(self) -> None:
        """Default mode appends the ellipsis beyond max_len characters."""
        result = truncate("a" * 20, 10)
        assert result == "a" * 10 + "…"
        assert len(result) == 11

    def test_reserve_mode_counts_ellipsis_in_limit(self) -> None:
        """Reserve mode keeps the result at most max_len characters."""
        result = truncate("a" * 20, 10, reserve_ellipsis=True)
        assert result == "a" * 9 + "…"
        assert len(result) == 10


# ---------------------------------------------------------------------------
# remove_clip_files()
# ---------------------------------------------------------------------------


def _config_with_temp(temp_dir: Path) -> MagicMock:
    """Build a stub config exposing *temp_dir*.

    Args:
        temp_dir: Path to use as the config's temp_dir.

    Returns:
        A MagicMock whose ``temp_dir`` attribute is *temp_dir*.
    """
    cfg = MagicMock()
    cfg.temp_dir = temp_dir
    return cfg


class TestRemoveClipFiles:
    """Tests for remove_clip_files() exercising real filesystem behaviour."""

    def test_removes_existing_files(self, tmp_path: Path) -> None:
        """Listed clip files are deleted from the clips directory."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        f1 = clips_dir / "clip_001.mp4"
        f2 = clips_dir / "clip_002.mp4"
        f1.write_bytes(b"a")
        f2.write_bytes(b"b")

        with patch("src.pages._util.get_config", return_value=_config_with_temp(tmp_path)):
            remove_clip_files(["clip_001.mp4", "clip_002.mp4"])

        assert not f1.exists()
        assert not f2.exists()

    def test_missing_file_is_ignored(self, tmp_path: Path) -> None:
        """A filename that does not exist is silently skipped (missing_ok)."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()

        with patch("src.pages._util.get_config", return_value=_config_with_temp(tmp_path)):
            # Must not raise even though the file is absent.
            remove_clip_files(["never_existed.mp4"])

    def test_empty_iterable_is_noop(self, tmp_path: Path) -> None:
        """An empty filename iterable performs no deletions and does not raise."""
        with patch("src.pages._util.get_config", return_value=_config_with_temp(tmp_path)):
            remove_clip_files([])

    def test_os_error_is_logged_and_swallowed(self, tmp_path: Path) -> None:
        """A removal failure (here: target is a directory) is warned, not raised."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        # A directory cannot be unlink()'d -> raises IsADirectoryError (OSError).
        (clips_dir / "a_directory.mp4").mkdir()

        with (
            patch("src.pages._util.get_config", return_value=_config_with_temp(tmp_path)),
            patch("src.pages._util.log") as mock_log,
        ):
            # Must not raise despite the OSError.
            remove_clip_files(["a_directory.mp4"])

        mock_log.warning.assert_called_once()
        assert (clips_dir / "a_directory.mp4").is_dir()


# end tests/unit/test_pages_util.py
