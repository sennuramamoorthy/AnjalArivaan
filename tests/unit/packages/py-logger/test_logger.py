"""
Python logger unit tests — written first per TDD.

All tests capture stdout, parse JSON, and assert structure/values.
"""
import json
import sys
import re
from io import StringIO

import pytest

# Make the package importable from the monorepo tree
sys.path.insert(0, "backend/packages/py-logger/src")

from anjal_logger import Logger, get_logger  # noqa: E402


# ── stdout capture helper ─────────────────────────────────────────────────────

class CaptureOutput:
    """Context manager that captures stdout writes during the block."""

    def __init__(self) -> None:
        self._buf = StringIO()
        self._orig = sys.stdout

    def __enter__(self) -> "CaptureOutput":
        sys.stdout = self._buf
        return self

    def __exit__(self, *_: object) -> None:
        sys.stdout = self._orig

    def lines(self) -> list[str]:
        return [ln for ln in self._buf.getvalue().split("\n") if ln.strip()]

    def last_entry(self) -> dict:
        lines = self.lines()
        assert lines, "No log output captured"
        return json.loads(lines[-1])


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_emits_valid_json():
    """Each log call must write valid JSON to stdout."""
    with CaptureOutput() as cap:
        logger = get_logger("test-service")
        logger.info("hello world")

    lines = cap.lines()
    assert len(lines) >= 1
    parsed = json.loads(lines[-1])
    assert isinstance(parsed, dict)


def test_includes_mandatory_fields():
    """Every entry must carry timestamp, level, service, trace_id, message."""
    with CaptureOutput() as cap:
        logger = get_logger("identity", trace_id="tr-001")
        logger.info("mandatory fields check")

    entry = cap.last_entry()
    for field in ("timestamp", "level", "service", "trace_id", "message"):
        assert field in entry, f"Missing field: {field}"

    assert entry["service"] == "identity"
    assert entry["trace_id"] == "tr-001"
    assert entry["message"] == "mandatory fields check"
    assert entry["level"] == "info"


def test_iso_8601_timestamp():
    """timestamp must be a valid ISO 8601 UTC string ending in +00:00 or Z."""
    with CaptureOutput() as cap:
        get_logger("ts-svc").info("timestamp test")

    entry = cap.last_entry()
    ts: str = entry["timestamp"]
    # Python datetime.isoformat() with UTC produces e.g. 2026-04-12T06:00:00.123456+00:00
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    assert re.match(pattern, ts), f"Timestamp does not match ISO 8601: {ts}"
    # Must contain UTC offset
    assert ts.endswith("+00:00") or ts.endswith("Z"), f"Timestamp not UTC: {ts}"


def test_min_level_filtering():
    """Messages below min_level must be suppressed."""
    with CaptureOutput() as cap:
        logger = get_logger("filter-svc", min_level="warn")
        logger.debug("silent debug")
        logger.info("silent info")

    assert cap.lines() == [], "debug and info should be suppressed at min_level=warn"

    with CaptureOutput() as cap:
        logger = get_logger("filter-svc", min_level="warn")
        logger.warn("audible warn")
        logger.error("audible error")

    lines = cap.lines()
    assert len(lines) == 2
    assert json.loads(lines[0])["level"] == "warn"
    assert json.loads(lines[1])["level"] == "error"


def test_child_inherits_context():
    """child() must merge parent context into every log entry."""
    with CaptureOutput() as cap:
        parent = get_logger("mail-sync", trace_id="parent-trace")
        child = parent.child(component="indexer", account_id="acct-99")
        child.info("child log")

    entry = cap.last_entry()
    assert entry["service"] == "mail-sync"
    assert entry["trace_id"] == "parent-trace"
    assert entry["component"] == "indexer"
    assert entry["account_id"] == "acct-99"
    assert entry["message"] == "child log"


def test_timed_logs_duration_ms():
    """timed() context manager must log duration_ms on successful exit."""
    with CaptureOutput() as cap:
        logger = get_logger("ai-orchestrator")
        with logger.timed("qdrant.search", index="mail-idx"):
            pass  # simulated fast operation

    entry = cap.last_entry()
    assert entry["level"] == "info"
    assert "duration_ms" in entry
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0
    assert entry["operation"] == "qdrant.search"
    assert entry["index"] == "mail-idx"


def test_timed_logs_on_error_and_reraises():
    """timed() must log at error level with duration_ms and re-raise the exception."""
    logger = get_logger("urgent-notification")
    boom = ValueError("connection refused")

    with CaptureOutput() as cap:
        with pytest.raises(ValueError, match="connection refused"):
            with logger.timed("kafka.publish"):
                raise boom

    entry = cap.last_entry()
    assert entry["level"] == "error"
    assert "duration_ms" in entry
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0


def test_error_serializes_exception():
    """error() with error=<exception> must serialize error_name, error_message, error_stack."""
    logger = get_logger("notification-router")
    exc = RuntimeError("BSP unreachable")

    with CaptureOutput() as cap:
        logger.error("notification delivery failed", error=exc)

    entry = cap.last_entry()
    assert entry["level"] == "error"
    assert entry["error_name"] == "RuntimeError"
    assert entry["error_message"] == "BSP unreachable"
    assert "error_stack" in entry
    assert isinstance(entry["error_stack"], str)
    assert "RuntimeError" in entry["error_stack"]
    # raw error key must NOT be in the output (not JSON-serializable)
    assert "error" not in entry or isinstance(entry.get("error"), str)
