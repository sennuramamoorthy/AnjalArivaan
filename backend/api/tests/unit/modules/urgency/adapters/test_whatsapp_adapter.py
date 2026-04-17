"""Unit tests for BspWhatsAppAdapter.

Uses httpx.MockTransport — no real network. Verifies:
  * env / ctor configuration
  * happy-path JSON payload shape and auth headers
  * duration_ms log on success
  * error propagation on HTTP failure
  * MockWhatsAppAdapter records calls and can simulate failure
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.modules.urgency.adapters.whatsapp.bsp_whatsapp_adapter import (
    BspWhatsAppAdapter,
    MockWhatsAppAdapter,
    _redact_phone,
)


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, timeout=5.0)


@pytest.mark.asyncio
async def test_bsp_adapter_sends_template_with_auth_headers():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message_id": "bsp-123"})

    adapter = BspWhatsAppAdapter(
        base_url="https://bsp.example.com/v1/messages",
        api_key="secret-key",
        default_template="urgent_gov_email_v1",
        http_client=_mock_client(handler),
    )

    result = await adapter.send_template(
        template_name="urgent_gov_email_v1",
        to_phone="+919876543210",
        parameters={"subject": "Deadline", "deadline": "21 June", "deep_link": "https://x"},
    )

    assert result == {"message_id": "bsp-123", "status": "sent"}
    assert captured["url"] == "https://bsp.example.com/v1/messages"
    # both auth header styles present
    assert captured["headers"]["authorization"] == "Bearer secret-key"
    assert captured["headers"]["apikey"] == "secret-key"
    body = captured["json"]
    assert body["template_name"] == "urgent_gov_email_v1"
    assert body["to"] == "+919876543210"
    assert body["parameters"]["subject"] == "Deadline"


@pytest.mark.asyncio
async def test_bsp_adapter_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    adapter = BspWhatsAppAdapter(
        base_url="https://bsp.example.com/v1/messages",
        api_key="secret",
        http_client=_mock_client(handler),
    )

    with pytest.raises(Exception):
        await adapter.send_template(
            template_name="urgent_gov_email_v1",
            to_phone="+911234567890",
            parameters={},
        )


@pytest.mark.asyncio
async def test_bsp_adapter_requires_url_env():
    adapter = BspWhatsAppAdapter(base_url="", api_key="k")
    with pytest.raises(RuntimeError, match="WHATSAPP_BSP_URL"):
        await adapter.send_template(
            template_name="t", to_phone="+91", parameters={}
        )


@pytest.mark.asyncio
async def test_bsp_adapter_requires_api_key_env():
    adapter = BspWhatsAppAdapter(base_url="https://x", api_key="")
    with pytest.raises(RuntimeError, match="WHATSAPP_BSP_API_KEY"):
        await adapter.send_template(
            template_name="t", to_phone="+91", parameters={}
        )


@pytest.mark.asyncio
async def test_bsp_adapter_uses_default_template_when_name_blank():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"messageId": "m1"})

    adapter = BspWhatsAppAdapter(
        base_url="https://bsp.example.com/v1",
        api_key="k",
        default_template="env_template_v2",
        http_client=_mock_client(handler),
    )
    result = await adapter.send_template(
        template_name="",  # blank → default
        to_phone="+911111111111",
        parameters={},
    )
    assert result["message_id"] == "m1"
    assert captured["json"]["template_name"] == "env_template_v2"


@pytest.mark.asyncio
async def test_bsp_adapter_logs_duration_ms(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message_id": "ok"})

    adapter = BspWhatsAppAdapter(
        base_url="https://bsp.example.com/v1",
        api_key="k",
        http_client=_mock_client(handler),
    )

    import logging

    with caplog.at_level(logging.INFO):
        await adapter.send_template(
            template_name="t", to_phone="+919999999999", parameters={}
        )

    found = [r for r in caplog.records if r.getMessage() == "whatsapp_bsp_sent"]
    assert found, "expected a structured success log"
    r = found[0]
    assert hasattr(r, "duration_ms")
    assert isinstance(r.duration_ms, int)
    assert r.template_name == "t"


def test_redact_phone_masks_all_but_last_4():
    assert _redact_phone("+919876543210") == "***3210"
    assert _redact_phone("") == ""


# ---------------------------------------------------------------------------
# Mock adapter contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_adapter_records_calls():
    mock = MockWhatsAppAdapter()
    res = await mock.send_template(
        template_name="t", to_phone="+91x", parameters={"a": "b"}
    )
    assert res["status"] == "sent"
    assert len(mock.sent) == 1
    assert mock.sent[0]["to_phone"] == "+91x"


@pytest.mark.asyncio
async def test_mock_adapter_can_simulate_failure():
    mock = MockWhatsAppAdapter()
    mock.fail_next = True
    with pytest.raises(RuntimeError):
        await mock.send_template(template_name="t", to_phone="+91", parameters={})
    # subsequent call succeeds
    res = await mock.send_template(template_name="t", to_phone="+91", parameters={})
    assert res["status"] == "sent"
