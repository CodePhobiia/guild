"""Logging configuration for CodeCrew."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Default log format
LOG_FORMAT = "%(message)s"
LOG_DATE_FORMAT = "[%X]"

# Log file location
LOG_DIR = Path.home() / ".codecrew" / "logs"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> logging.Logger:
    """Set up logging with Rich handler for console output.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        verbose: Enable verbose/debug output

    Returns:
        Configured logger instance
    """
    if verbose:
        level = logging.DEBUG

    # Create logger
    logger = logging.getLogger("codecrew")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with Rich
    console = Console(stderr=True)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=verbose,
        rich_tracebacks=True,
        tracebacks_show_locals=verbose,
        markup=True,
    )
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log debug to file
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (will be prefixed with 'codecrew.')

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"codecrew.{name}")
    return logging.getLogger("codecrew")


def enable_debug_logging() -> None:
    """Enable debug logging for all CodeCrew loggers."""
    logger = logging.getLogger("codecrew")
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)


def disable_logging() -> None:
    """Disable all logging (useful for testing)."""
    logging.getLogger("codecrew").handlers.clear()
    logging.getLogger("codecrew").addHandler(logging.NullHandler())


class LogCapture:
    """Context manager to capture log messages (useful for testing)."""

    def __init__(self, logger_name: str = "codecrew"):
        self.logger_name = logger_name
        self.records: list[logging.LogRecord] = []
        self._handler: Optional[logging.Handler] = None

    def __enter__(self) -> "LogCapture":
        self._handler = CaptureHandler(self.records)
        logging.getLogger(self.logger_name).addHandler(self._handler)
        return self

    def __exit__(self, *args) -> None:
        if self._handler:
            logging.getLogger(self.logger_name).removeHandler(self._handler)

    @property
    def messages(self) -> list[str]:
        """Get captured log messages."""
        return [record.getMessage() for record in self.records]

    def has_message(self, substring: str) -> bool:
        """Check if any captured message contains the substring."""
        return any(substring in msg for msg in self.messages)


class CaptureHandler(logging.Handler):
    """Handler that captures log records to a list."""

    def __init__(self, records: list[logging.LogRecord]):
        super().__init__()
        self.records = records

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
