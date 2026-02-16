# start backend/tests/unit/test_logging_config.py
"""Comprehensive tests for logging_config.py to achieve 100% line coverage.

Covers:
- get_level_emoji: int level, string level, unknown level
- EmojiFormatter.format: prepends emoji to message
- setup_logging: valid level, invalid level, creates directory and handlers
- cleanup_old_logs: no dir, no old logs, old log deleted, delete error
"""

import logging
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.logging_config import (
    get_level_emoji,
    EmojiFormatter,
    setup_logging,
    cleanup_old_logs,
)


# ---------------------------------------------------------------------------
# get_level_emoji
# ---------------------------------------------------------------------------


class TestGetLevelEmoji:
    def test_debug(self) -> None:
        assert get_level_emoji(logging.DEBUG) == "\U0001f50d"

    def test_info(self) -> None:
        assert get_level_emoji(logging.INFO) == "\U0001f7e2"

    def test_warning(self) -> None:
        assert get_level_emoji(logging.WARNING) == "\U0001f7e1"

    def test_error(self) -> None:
        assert get_level_emoji(logging.ERROR) == "\U0001f6d1"

    def test_critical(self) -> None:
        assert get_level_emoji(logging.CRITICAL) == "\U0001f4a5"

    def test_unknown_level(self) -> None:
        assert get_level_emoji(999) == "\U0001f4dd"

    def test_string_level_info(self) -> None:
        """Accepts string level and converts to int."""
        assert get_level_emoji("INFO") == "\U0001f7e2"

    def test_string_level_lowercase(self) -> None:
        """Accepts lowercase string level."""
        assert get_level_emoji("debug") == "\U0001f50d"

    def test_string_level_unknown(self) -> None:
        """Unknown string level defaults to INFO (via getattr fallback)."""
        result = get_level_emoji("NOTAREAL")
        # getattr(logging, "NOTAREAL", logging.INFO) -> logging.INFO
        assert result == "\U0001f7e2"


# ---------------------------------------------------------------------------
# EmojiFormatter
# ---------------------------------------------------------------------------


class TestEmojiFormatter:
    def test_format_adds_emoji(self) -> None:
        formatter = EmojiFormatter(
            fmt="%(message)s",
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        result = formatter.format(record)
        assert "\U0001f7e2" in result
        assert "Test message" in result


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    def test_valid_level(self, tmp_path: Path) -> None:
        """Creates console + file handlers at specified level."""
        log_dir = str(tmp_path / "logs")
        setup_logging("DEBUG", log_dir)

        root = logging.getLogger()
        # Should have at least 2 handlers (console + file)
        assert len(root.handlers) >= 2
        assert root.level == logging.DEBUG

        # Cleanup handlers for other tests
        for h in root.handlers.copy():
            root.removeHandler(h)

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Accepts lowercase level strings."""
        log_dir = str(tmp_path / "logs")
        setup_logging("warning", log_dir)

        root = logging.getLogger()
        assert root.level == logging.WARNING

        for h in root.handlers.copy():
            root.removeHandler(h)

    def test_invalid_level(self, tmp_path: Path) -> None:
        """Raises ValueError for invalid log level."""
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging("NOTREAL", str(tmp_path / "logs"))

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Creates the log directory if it doesn't exist."""
        log_dir = tmp_path / "new_logs"
        assert not log_dir.exists()
        setup_logging("INFO", str(log_dir))
        assert log_dir.is_dir()

        root = logging.getLogger()
        for h in root.handlers.copy():
            root.removeHandler(h)

    def test_log_file_created(self, tmp_path: Path) -> None:
        """Creates a timestamped log file."""
        log_dir = tmp_path / "logs"
        setup_logging("INFO", str(log_dir), app_name="testapp")

        log_files = list(log_dir.glob("testapp-*.log"))
        assert len(log_files) >= 1

        root = logging.getLogger()
        for h in root.handlers.copy():
            root.removeHandler(h)

    def test_removes_existing_handlers(self, tmp_path: Path) -> None:
        """Removes pre-existing handlers before adding new ones."""
        root = logging.getLogger()
        dummy_handler = logging.StreamHandler()
        root.addHandler(dummy_handler)

        setup_logging("INFO", str(tmp_path / "logs"))

        # dummy_handler should have been removed
        assert dummy_handler not in root.handlers

        for h in root.handlers.copy():
            root.removeHandler(h)


# ---------------------------------------------------------------------------
# cleanup_old_logs
# ---------------------------------------------------------------------------


class TestCleanupOldLogs:
    def test_no_directory(self, tmp_path: Path) -> None:
        """Returns early if log directory doesn't exist."""
        cleanup_old_logs(str(tmp_path / "nonexistent"))
        # No error raised

    def test_no_old_logs(self, tmp_path: Path) -> None:
        """Keeps recent log files."""
        log_file = tmp_path / "recent.log"
        log_file.write_text("recent log")
        cleanup_old_logs(str(tmp_path), retention_days=30)
        assert log_file.exists()

    def test_deletes_old_logs(self, tmp_path: Path) -> None:
        """Deletes log files older than retention period."""
        old_log = tmp_path / "old.log"
        old_log.write_text("old log")

        # Set mtime to 60 days ago
        import os

        old_time = time.time() - (60 * 86400)
        os.utime(old_log, (old_time, old_time))

        cleanup_old_logs(str(tmp_path), retention_days=30)
        assert not old_log.exists()

    def test_handles_delete_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Logs warning when file deletion fails."""
        old_log = tmp_path / "old.log"
        old_log.write_text("old log")

        import os

        old_time = time.time() - (60 * 86400)
        os.utime(old_log, (old_time, old_time))

        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            with caplog.at_level(logging.WARNING):
                cleanup_old_logs(str(tmp_path), retention_days=30)

        assert "Could not delete" in caplog.text

    def test_ignores_non_log_files(self, tmp_path: Path) -> None:
        """Only processes .log files."""
        txt_file = tmp_path / "old.txt"
        txt_file.write_text("not a log")

        import os

        old_time = time.time() - (60 * 86400)
        os.utime(txt_file, (old_time, old_time))

        cleanup_old_logs(str(tmp_path), retention_days=30)
        assert txt_file.exists()  # Not deleted because it's not .log


# end backend/tests/unit/test_logging_config.py
