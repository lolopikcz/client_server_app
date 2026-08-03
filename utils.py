"""Utility functions for validation and logging."""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_FILENAME_LENGTH = 255


def validate_filename(name: str) -> str:
    """Validate and sanitize a filename.

    Rejects path traversal, empty names, null bytes, reserved Windows names,
    and names with invalid characters.

    Args:
        name: The filename to validate.

    Returns:
        The sanitized filename (basename only).

    Raises:
        ValueError: If the filename is invalid.
    """
    if not name or not name.strip():
        raise ValueError("Filename cannot be empty")

    if "\x00" in name:
        raise ValueError("Filename contains null byte")

    # Reject path traversal
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"Invalid filename: {name}")

    # Only allow safe characters
    if not re.match(r'^[\w\-. ]+$', name):
        raise ValueError(f"Filename contains invalid characters: {name}")

    safe_name = Path(name).name

    if not safe_name:
        raise ValueError(f"Filename resolves to empty: {name}")

    # Check length after sanitizing
    if len(safe_name.encode("utf-8")) > MAX_FILENAME_LENGTH:
        raise ValueError(f"Filename too long: {len(safe_name.encode('utf-8'))} bytes")

    # Check reserved Windows names (without extension)
    stem = Path(safe_name).stem.upper()
    if stem in RESERVED_WINDOWS_NAMES:
        raise ValueError(f"Reserved Windows filename: {stem}")

    return safe_name


def setup_logging(
    level: int = logging.INFO, log_mode: str = "append", name: str = "server"
) -> logging.Logger:
    """Configure and return the application logger.

    Logs to both console (INFO) and file (DEBUG). Log files rotate
    at 5MB, keeping 3 backups.

    Args:
        level: Logging level.
        log_mode: 'append' to keep old logs, 'overwrite' to clear on start.
        name: Logger and log file name (e.g. 'server', 'client').

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(f"file_transfer.{name}")
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

        # Console handler — INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler — DEBUG and above, rotates at 5MB
        log_file = Path(__file__).parent / "logs" / f"{name}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Clear log file if overwrite mode
        if log_mode == "overwrite" and log_file.exists():
            log_file.unlink()

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.setLevel(level)
    return logger
