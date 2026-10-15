"""Behavior checks for pipeline logging, without API or database calls."""

import io
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config.logging_config import PipelineFormatter, configure_logging


@pytest.fixture
def logging_state(monkeypatch):
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    dependency_levels = {
        name: logging.getLogger(name).level for name in ("httpx", "httpcore")
    }
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.delenv("LOG_FILE", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = io.StringIO()
    monkeypatch.setattr("src.config.logging_config.sys", SimpleNamespace(stderr=stream))
    yield stream
    for handler in root.handlers[:]:
        if handler not in original_handlers:
            root.removeHandler(handler)
            handler.close()
    # configure_logging may replace the original pipeline console handler.
    for handler in original_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(original_level)
    for name, level in dependency_levels.items():
        logging.getLogger(name).setLevel(level)


def test_console_filters_debug_and_keeps_test_capture(logging_state, caplog):
    configure_logging()
    logger = logging.getLogger("src.extract.extract")
    logger.debug("Hidden detail")
    logger.info("Extracted %s companies", 2)

    output = logging_state.getvalue()
    assert "Hidden detail" not in output
    assert "INFO     | extract.extract" in output
    assert "Extracted 2 companies" in output
    assert "\033[" not in output
    assert "Extracted 2 companies" in caplog.text


def test_reconfiguration_does_not_duplicate_messages(logging_state):
    configure_logging()
    configure_logging(level="DEBUG")
    logging.getLogger("src.transform.normalize").debug("One message")
    assert logging_state.getvalue().count("One message") == 1


def test_no_color_is_respected_on_a_terminal(logging_state, monkeypatch):
    monkeypatch.setattr(logging_state, "isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "")
    configure_logging()
    logging.getLogger("src.transform.validate").warning("Quality warning")
    assert "\033[" not in logging_state.getvalue()


def test_color_does_not_mutate_records():
    record = logging.LogRecord(
        "src.extract.extract",
        logging.WARNING,
        __file__,
        1,
        "Extracted %s",
        (2,),
        None,
    )
    record.created = 0
    colored = PipelineFormatter(color=True).format(record)
    plain = PipelineFormatter().format(record)

    assert colored.startswith("1970-01-01 00:00:00Z")
    assert "\033[33m" in colored
    assert "\033[" not in plain
    assert "Extracted 2" in plain
    assert record.levelname == "WARNING"
    assert not hasattr(record, "severity")


def test_rotating_file_keeps_plain_text_and_tracebacks(logging_state, tmp_path):
    log_path = tmp_path / "logs" / "pipeline.log"
    configure_logging(log_file=log_path)
    try:
        raise ValueError("Invalid table")
    except ValueError:
        logging.getLogger("src.transform.validate").exception("Validation failed")

    output = log_path.read_text(encoding="utf-8")
    assert "Validation failed" in output
    assert "ValueError: Invalid table" in output
    assert "\033[" not in output
    handler = next(
        handler
        for handler in logging.getLogger().handlers
        if handler.name == "pipeline.file"
    )
    handler.maxBytes = 1
    logging.getLogger("src.transform.validate").info("Next event")
    assert Path(f"{log_path}.1").exists()


def test_invalid_level_preserves_existing_handlers(logging_state):
    handlers = logging.getLogger().handlers[:]
    with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
        configure_logging(level="VERBOSE")
    assert logging.getLogger().handlers == handlers


@pytest.mark.parametrize(
    "level, expected",
    [
        (" debug ", logging.DEBUG),
        ("info", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ],
)
def test_environment_level_is_normalized(logging_state, monkeypatch, level, expected):
    monkeypatch.setenv("LOG_LEVEL", level)
    configure_logging()
    assert logging.getLogger().level == expected
    dependency_level = logging.DEBUG if expected == logging.DEBUG else logging.WARNING
    assert logging.getLogger("httpx").level == dependency_level
    assert logging.getLogger("httpcore").level == dependency_level


def test_explicit_level_overrides_environment(logging_state, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "invalid")
    configure_logging(level="ERROR")
    assert logging.getLogger().level == logging.ERROR


@pytest.mark.parametrize("level", ["", "TRACE", "20"])
def test_invalid_environment_level_does_not_reconfigure(
    logging_state, monkeypatch, level
):
    root = logging.getLogger()
    handlers, original_level = root.handlers[:], root.level
    monkeypatch.setenv("LOG_LEVEL", level)
    with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
        configure_logging()
    assert root.handlers == handlers
    assert root.level == original_level


def test_log_file_environment_creates_utf8_rotating_handler(
    logging_state, tmp_path, monkeypatch
):
    path = tmp_path / "logs" / "pipeline.log"
    monkeypatch.setenv("LOG_FILE", str(path))
    configure_logging()
    logging.getLogger("src.load.load").info("Loaded Café records")
    assert "Loaded Café records" in path.read_text(encoding="utf-8")
    handler = next(h for h in logging.getLogger().handlers if h.name == "pipeline.file")
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    assert handler.encoding == "utf-8"


def test_explicit_log_file_overrides_environment(logging_state, tmp_path, monkeypatch):
    ignored = tmp_path / "ignored.log"
    selected = tmp_path / "selected.log"
    monkeypatch.setenv("LOG_FILE", str(ignored))
    configure_logging(log_file=selected)
    logging.getLogger("src.load.load").info("Selected destination")
    assert selected.exists()
    assert not ignored.exists()


def test_empty_explicit_log_file_disables_environment_file(
    logging_state, tmp_path, monkeypatch
):
    path = tmp_path / "disabled.log"
    monkeypatch.setenv("LOG_FILE", str(path))
    configure_logging(log_file="")
    assert not path.exists()
    assert not any(h.name == "pipeline.file" for h in logging.getLogger().handlers)


def test_reconfiguration_closes_previous_file_handler(logging_state, tmp_path):
    configure_logging(log_file=tmp_path / "first.log")
    old_handler = next(
        h for h in logging.getLogger().handlers if h.name == "pipeline.file"
    )
    configure_logging(log_file=tmp_path / "second.log")
    assert old_handler.stream is None
    assert old_handler not in logging.getLogger().handlers
    assert sum(h.name == "pipeline.file" for h in logging.getLogger().handlers) == 1


def test_reconfiguration_preserves_unrelated_handlers(logging_state):
    handler = logging.StreamHandler(io.StringIO())
    handler.set_name("external.application")
    logging.getLogger().addHandler(handler)
    configure_logging()
    configure_logging()
    assert handler in logging.getLogger().handlers


def test_log_destination_failure_preserves_existing_handlers(logging_state, tmp_path):
    parent = tmp_path / "file-instead-of-directory"
    parent.write_text("occupied", encoding="utf-8")
    root = logging.getLogger()
    handlers, original_level = root.handlers[:], root.level
    with pytest.raises(FileExistsError):
        configure_logging(level="DEBUG", log_file=parent / "pipeline.log")
    assert root.handlers == handlers
    assert root.level == original_level


@pytest.mark.parametrize(
    "level, escape",
    [
        (logging.DEBUG, "\033[90m"),
        (logging.INFO, "\033[36m"),
        (logging.WARNING, "\033[33m"),
        (logging.ERROR, "\033[31m"),
        (logging.CRITICAL, "\033[1;31m"),
    ],
)
def test_terminal_colors_each_severity(logging_state, monkeypatch, level, escape):
    monkeypatch.setattr(logging_state, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm")
    configure_logging(level="DEBUG")
    logging.getLogger("src.load.load").log(level, "Colored event")
    assert escape in logging_state.getvalue()
    assert "\033[0m" in logging_state.getvalue()


def test_dumb_terminal_disables_color(logging_state, monkeypatch):
    monkeypatch.setattr(logging_state, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "dumb")
    configure_logging()
    logging.getLogger("src.load.load").warning("Plain event")
    assert "\033[" not in logging_state.getvalue()


def test_formatter_accepts_unknown_severity_without_color():
    record = logging.LogRecord(
        "external.library", 25, __file__, 1, "Custom event", (), None
    )
    result = PipelineFormatter(color=True).format(record)
    assert "\033[" not in result
    assert "external.library" in result
    assert "Custom event" in result
