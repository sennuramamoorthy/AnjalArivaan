import pytest

from src.modules.notification.adapters.push.mock_adapter import MockPushAdapter


@pytest.mark.asyncio
async def test_send_captures_message():
    adapter = MockPushAdapter()

    await adapter.send(
        user_id="user-1",
        title="Hi",
        body="Hello world",
        data={"kind": "test"},
    )

    assert len(adapter.sent) == 1
    msg = adapter.sent[0]
    assert msg["user_id"] == "user-1"
    assert msg["title"] == "Hi"
    assert msg["body"] == "Hello world"
    assert msg["data"] == {"kind": "test"}


@pytest.mark.asyncio
async def test_send_defaults_data_to_empty_dict_when_none():
    adapter = MockPushAdapter()
    await adapter.send(user_id="u", title="t", body="b")
    assert adapter.sent[0]["data"] == {}


@pytest.mark.asyncio
async def test_multiple_sends_recorded_in_order():
    adapter = MockPushAdapter()
    await adapter.send(user_id="u1", title="a", body="1")
    await adapter.send(user_id="u2", title="b", body="2")

    assert [m["user_id"] for m in adapter.sent] == ["u1", "u2"]
    assert [m["title"] for m in adapter.sent] == ["a", "b"]


@pytest.mark.asyncio
async def test_clear_resets_captured_messages():
    adapter = MockPushAdapter()
    await adapter.send(user_id="u", title="t", body="b")
    assert adapter.sent

    adapter.clear()
    assert adapter.sent == []
