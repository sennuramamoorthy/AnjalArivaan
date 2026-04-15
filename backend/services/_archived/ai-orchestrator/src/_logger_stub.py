"""
Minimal logger stub used when the anjal_logger package is not installed.
In production, the real package from packages/py-logger is used.
"""
import json
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any


class Logger:
    def __init__(
        self,
        service: str,
        trace_id: str | None = None,
        min_level: str = "debug",
        base_context: dict[str, Any] | None = None,
    ) -> None:
        self._service = service
        self._trace_id = trace_id or str(uuid.uuid4())
        self._min_level = min_level
        self._base_context: dict[str, Any] = base_context or {}
        self._level_order = {"debug": 0, "info": 1, "warn": 2, "error": 3}

    def _emit(self, level: str, message: str, **kwargs: Any) -> None:
        if self._level_order.get(level, 0) < self._level_order.get(self._min_level, 0):
            return
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": self._service,
            "trace_id": self._trace_id,
            "message": message,
            **self._base_context,
            **kwargs,
        }
        if "error" in entry and isinstance(entry["error"], BaseException):
            exc = entry.pop("error")
            entry["error_name"] = type(exc).__name__
            entry["error_message"] = str(exc)
            entry["error_stack"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
        print(json.dumps(entry, default=str), file=sys.stdout, flush=True)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit("debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit("info", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._emit("warn", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._emit("error", message, **kwargs)

    def child(self, **context: Any) -> "Logger":
        return Logger(
            service=self._service,
            trace_id=self._trace_id,
            min_level=self._min_level,
            base_context={**self._base_context, **context},
        )


def get_logger(service: str, trace_id: str | None = None, min_level: str = "debug") -> Logger:
    return Logger(service=service, trace_id=trace_id, min_level=min_level)
