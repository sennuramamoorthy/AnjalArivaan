"""Structured JSON logger matching CLAUDE.md logging requirements.

Every log entry is a single-line JSON object with at minimum:
timestamp (ISO 8601), level, service, trace_id, message.
Outbound API calls include duration_ms.
AI requests include model_id, prompt_template_id, retrieved_chunk_count.
"""

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any


class Logger:
    def __init__(self, service: str, base_context: dict[str, Any] | None = None):
        self._service = service
        self._base = base_context or {}

    def _write(self, level: str, message: str, **kwargs: Any) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": self._service,
            "trace_id": self._base.get("trace_id", "unknown"),
            "message": message,
            **self._base,
            **kwargs,
        }
        # Flatten error objects
        err = kwargs.get("error")
        if isinstance(err, Exception):
            entry["error_name"] = type(err).__name__
            entry["error_message"] = str(err)
            del entry["error"]

        sys.stdout.write(json.dumps(entry, default=str) + "\n")
        sys.stdout.flush()

    def debug(self, message: str, **kwargs: Any) -> None:
        self._write("debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._write("info", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._write("warn", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._write("error", message, **kwargs)

    def child(self, **context: Any) -> "Logger":
        merged = {**self._base, **context}
        return Logger(self._service, merged)

    def timed(self, operation_name: str, **meta: Any):
        """Context manager that logs duration_ms on completion."""
        return _TimedContext(self, operation_name, meta)


class _TimedContext:
    def __init__(self, logger: Logger, operation: str, meta: dict[str, Any]):
        self._logger = logger
        self._operation = operation
        self._meta = meta
        self._start: float = 0

    def __enter__(self) -> "_TimedContext":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration_ms = round((time.monotonic() - self._start) * 1000, 1)
        if exc_type is None:
            self._logger.info(self._operation, duration_ms=duration_ms, **self._meta)
        else:
            self._logger.error(
                self._operation,
                duration_ms=duration_ms,
                error=exc_val,
                **self._meta,
            )
        return False


def create_logger(service: str, **base_context: Any) -> Logger:
    return Logger(service, base_context)
