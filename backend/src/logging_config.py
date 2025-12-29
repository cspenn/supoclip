# start backend/src/logging_config.py

"""Logging configuration module for SupoClip backend.

Provides functions to set up dual logging (console + file) with emoji indicators
and log file rotation based on retention days.
"""

import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path


def get_level_emoji(level: int | str) -> str:
    """Get emoji indicator for log level.

    Args:
        level: Log level (int or str).

    Returns:
        Emoji string for the log level.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    return {
        logging.DEBUG: "🔍",
        logging.INFO: "🟢",
        logging.WARNING: "🟡",
        logging.ERROR: "🛑",
        logging.CRITICAL: "💥",
    }.get(level, "📝")


class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emoji indicators to log messages."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with emoji indicator.

        Args:
            record: Log record to format.

        Returns:
            Formatted log message with emoji.
        """
        emoji = get_level_emoji(record.levelno)
        record.msg = f"{emoji} {record.msg}"
        return super().format(record)


def setup_logging(log_level: str, log_dir: str, app_name: str = "supoclip") -> None:
    """Set up dual logging (console + file) with emoji indicators.

    Creates logs directory if it doesn't exist and generates timestamped
    log filename. Configures console output with emoji indicators and
    file output for persistence.

    Args:
        log_level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory where log files will be stored.
        app_name: Application name for log file prefix.

    Raises:
        ValueError: If log_level is invalid.
    """
    # Validate log level
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    level_str = log_level.upper()
    if level_str not in valid_levels:
        raise ValueError(
            f"Invalid log level: {level_str}. Must be one of: {', '.join(valid_levels)}"
        )

    level = getattr(logging, level_str)

    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True, parents=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_path / f"{app_name}-{timestamp}.log"

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers.copy():
        root_logger.removeHandler(handler)

    # Console handler with emoji formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = EmojiFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (without emoji in file, just plain text)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - level: {level_str}, file: {log_file}")


def cleanup_old_logs(log_dir: str, retention_days: int = 30) -> None:
    """Delete log files older than retention period.

    Args:
        log_dir: Directory containing log files.
        retention_days: Number of days to retain logs (default: 30).
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)

    for log_file in log_path.glob("*.log"):
        try:
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                log_file.unlink()
                logger = logging.getLogger(__name__)
                logger.debug(f"Deleted old log file: {log_file}")
        except (OSError, ValueError) as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not delete log file {log_file}: {e}")


# end backend/src/logging_config.py
