import json
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

LogLevel = str  # 'debug' | 'info' | 'warn' | 'error'

_LEVEL_ORDER: dict[str, int] = {'debug': 0, 'info': 1, 'warn': 2, 'error': 3}


class Logger:
    """
    Production-grade structured JSON logger for AnjalArivaan Python services.

    Each call writes one JSON line to stdout. Fields follow the shared LogEntry
    contract defined in packages/logger/src/types.ts.
    """

    def __init__(
        self,
        service: str,
        trace_id: str | None = None,
        min_level: LogLevel = 'debug',
        base_context: dict[str, Any] | None = None,
    ) -> None:
        self._service = service
        self._trace_id = trace_id or str(uuid.uuid4())
        self._min_level = min_level
        self._base_context: dict[str, Any] = base_context or {}

    def _emit(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        if _LEVEL_ORDER.get(level, 0) < _LEVEL_ORDER.get(self._min_level, 0):
            return

        entry: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': level,
            'service': self._service,
            'trace_id': self._trace_id,
            'message': message,
            **self._base_context,
            **kwargs,
        }

        # Serialize exceptions if present
        if 'error' in entry and isinstance(entry['error'], BaseException):
            exc = entry.pop('error')
            entry['error_name'] = type(exc).__name__
            entry['error_message'] = str(exc)
            entry['error_stack'] = ''.join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )

        print(json.dumps(entry, default=str), file=sys.stdout, flush=True)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit('debug', message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit('info', message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._emit('warn', message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._emit('error', message, **kwargs)

    def child(self, **context: Any) -> 'Logger':
        """Return a new Logger that inherits and extends base_context."""
        return Logger(
            service=self._service,
            trace_id=self._trace_id,
            min_level=self._min_level,
            base_context={**self._base_context, **context},
        )

    @contextmanager
    def timed(self, operation: str, **meta: Any) -> Generator[None, None, None]:
        """
        Context manager that measures wall-clock time and logs duration_ms on exit.

        On success: logs at INFO level with duration_ms.
        On exception: logs at ERROR level with duration_ms + error details, then re-raises.
        """
        start = time.perf_counter()
        try:
            yield
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self.info(
                f'{operation} completed',
                duration_ms=duration_ms,
                operation=operation,
                **meta,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self.error(
                f'{operation} failed',
                duration_ms=duration_ms,
                operation=operation,
                error=exc,
                **meta,
            )
            raise


def get_logger(
    service: str,
    trace_id: str | None = None,
    min_level: LogLevel = 'debug',
) -> Logger:
    """Factory function to create a new structured JSON logger."""
    return Logger(service=service, trace_id=trace_id, min_level=min_level)
