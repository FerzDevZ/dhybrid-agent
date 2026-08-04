"""TDD tests for structured logger."""
import io
import json
import logging

from dhybrid.utils.log import JsonFormatter, LogConfig, TextFormatter, get_logger


def _fresh_logger(name, fmt="json", level="DEBUG"):
    log = logging.getLogger(name)
    log.handlers.clear()
    log.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    log.addHandler(h)
    log.propagate = False
    return log, buf


def test_json_formatter_emits_valid_json():
    log, buf = _fresh_logger("test_json", fmt="json")
    log.info("hello %s", "world")
    data = json.loads(buf.getvalue())
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert "timestamp" in data


def test_text_formatter_plain():
    log, buf = _fresh_logger("test_text", fmt="text")
    log.info("plain message")
    out = buf.getvalue()
    assert "plain message" in out
    assert "INFO" in out


def test_log_level_filter():
    log, _ = _fresh_logger("test_lvl", level="ERROR")
    assert log.isEnabledFor(logging.ERROR)
    assert not log.isEnabledFor(logging.DEBUG)


def test_logconfig_apply_switches_format(monkeypatch):
    monkeypatch.setenv("DHYBRID_LOG_FORMAT", "text")
    cfg = LogConfig(level="WARNING", fmt="text")
    cfg.apply()
    base = logging.getLogger("dhybrid")
    assert isinstance(base.handlers[0].formatter, TextFormatter)


def test_get_logger_returns_adapter():
    log = get_logger("test_adapter")
    assert hasattr(log, "info")
    assert hasattr(log, "debug")
