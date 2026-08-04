"""Structured logging untuk dhybrid agent — JSON/text hybrid.

Support 2 format:
- json: {"timestamp","level","logger","message",**extra} — machine-readable
- text: "2026-08-04 07:54:31 [INFO] dhybrid.loop | message" — human-readable

Pakai di loop.py / tools / debug dump. Default json bila env DHYBRID_LOG_FORMAT=json.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit structured JSON di stderr — one JSON object per line."""

    def __init__(self, extra_fields: dict[str, Any] | None = None):
        super().__init__()
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if self.extra_fields:
            data.update(self.extra_fields)
        # merge record.__dict__ bila ada extra user
        for k in ("step", "model", "cost", "tokens"):
            if hasattr(record, k):
                data[k] = getattr(record, k)
        # jaringan error / exception
        if record.exc_info and record.exc_info[1]:
            data["error"] = str(record.exc_info[1])
        return json.dumps(data, default=str)


class TextFormatter(logging.Formatter):
    fmt = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.fmt, datefmt=self.datefmt)


_FACTORY = logging.getLogger("dhybrid")
_FORMATTER = JsonFormatter if os.environ.get("DHYBRID_LOG_FORMAT", "json") == "json" else TextFormatter  # type: ignore
_DEFAULT_FMT = _FORMATTER()  # type: ignore


class _Adapter(logging.LoggerAdapter):
    """LoggerAdapter — eksport .info/.debug/.error sama seperti logger standar."""

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None):
        super().__init__(logger, extra or {})


def get_logger(
    name: str = "dhybrid",
    level: str | None = None,
    fmt: str | None = None,
    extra: dict[str, Any] | None = None,
) -> _Adapter:
    """Return structured logger. fmt='json' atau 'text' (auto-detect dari env)."""
    fmt = fmt or os.environ.get("DHYBRID_LOG_FORMAT", "json")
    level = level or os.environ.get("DHYBRID_LOG_LEVEL", "INFO")

    base = logging.getLogger(name)
    if not base.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
        base.addHandler(h)
        base.setLevel(getattr(logging, level.upper(), logging.INFO))
        base.propagate = False

    return _Adapter(logging.getLogger(name), extra)


class LogConfig:
    """Konfigurasi logging sederhana — bisa di-set sekali di startup."""

    level: str = "INFO"
    format: str = "json"  # json | text

    def __init__(self, level: str | None = None, fmt: str | None = None):
        if level:
            self.level = level
        if fmt:
            self.format = fmt

    def apply(self) -> None:
        base = logging.getLogger("dhybrid")
        if not base.handlers:
            h = logging.StreamHandler()
            base.addHandler(h)
        base.handlers[0].setFormatter(
            JsonFormatter() if self.format == "json" else TextFormatter()
        )
