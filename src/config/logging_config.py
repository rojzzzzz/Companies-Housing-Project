"""Consistent console and optional rotating-file logging for the pipeline.

LOG_LEVEL defaults to INFO. Set LOG_FILE=data/logs/pipeline.log to retain
plain-text logs (5 MiB per file, three backups). NO_COLOR disables terminal
color. Existing module loggers work without changes.
"""

from __future__ import annotations

import copy
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

_HANDLER_PREFIX = "pipeline."
_COLORS = {
    logging.DEBUG: "\033[90m",
    logging.INFO: "\033[36m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
_RESET = "\033[0m"


class PipelineFormatter(logging.Formatter):
    """Aligned UTC timestamps and module names; color only the severity."""

    converter = time.gmtime

    def __init__(self, *, color: bool = False) -> None:
        super().__init__(
            "%(asctime)sZ | %(severity)s | %(source)-24s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        # Do not change records shared with file handlers or test capture.
        formatted = copy.copy(record)
        formatted.source = record.name.removeprefix("src.")
        severity = f"{record.levelname:<8}"
        color = _COLORS.get(record.levelno, "") if self.color else ""
        formatted.severity = f"{color}{severity}{_RESET}" if color else severity
        return super().format(formatted)


def configure_logging(
    *,
    level: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """Configure logging safely on repeated calls, preserving other handlers.

    Explicit arguments override environment settings. An empty LOG_FILE
    leaves logging on the console only. Call after loading .env.
    """
    level_name = (level if level is not None else os.getenv("LOG_LEVEL", "INFO"))
    level_name = level_name.strip().upper()
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    if level_name not in levels:
        raise ValueError(
            f"Invalid LOG_LEVEL {level_name!r}; choose "
            "DEBUG, INFO, WARNING, ERROR or CRITICAL."
        )

    destination = log_file if log_file is not None else os.getenv("LOG_FILE", "")
    console = logging.StreamHandler(sys.stderr)
    console.set_name(f"{_HANDLER_PREFIX}console")
    console.setFormatter(
        PipelineFormatter(
            color=sys.stderr.isatty()
            and "NO_COLOR" not in os.environ
            and os.getenv("TERM") != "dumb"
        )
    )
    handlers: list[logging.Handler] = [console]

    if destination:
        path = Path(destination).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.set_name(f"{_HANDLER_PREFIX}file")
        file_handler.setFormatter(PipelineFormatter())
        handlers.append(file_handler)

    root = logging.getLogger()
    for handler in root.handlers[:]:
        if (handler.name or "").startswith(_HANDLER_PREFIX):
            root.removeHandler(handler)
            handler.close()

    root.setLevel(levels[level_name])
    for handler in handlers:
        root.addHandler(handler)

    # Keep HTTP request chatter out of INFO; DEBUG exposes it when needed.
    dependency_level = logging.DEBUG if level_name == "DEBUG" else logging.WARNING
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(dependency_level)

