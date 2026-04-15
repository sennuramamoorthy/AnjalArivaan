"""Response envelope helpers matching the API contract.

All API responses use: { success, data?, error?, meta: { traceId } }
"""

from typing import Any


def success_response(data: Any, trace_id: str = "unknown") -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {"traceId": trace_id},
    }


def error_response(code: str, message: str, trace_id: str = "unknown") -> dict:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "meta": {"traceId": trace_id},
    }
