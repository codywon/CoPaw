import pytest

from copaw.app.channels.discord_ import channel as discord_channel_module
from copaw.app.channels.discord_.channel import DiscordChannel


async def _dummy_process(_request):
    if False:
        yield None


class _FlakySender:
    def __init__(self, fail_times, exc):
        self.fail_times = fail_times
        self.exc = exc
        self.calls = 0

    async def send(self, _text):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc


class _FakeClient:
    def __init__(self, sender):
        self.sender = sender

    def is_ready(self):
        return True

    def get_channel(self, _channel_id):
        return self.sender

    async def fetch_channel(self, _channel_id):
        return self.sender

    def get_user(self, _user_id):
        return None

    async def fetch_user(self, _user_id):
        raise RuntimeError("unused in this test")


def _build_channel(fake_client):
    channel = DiscordChannel(
        process=_dummy_process,
        enabled=False,
        token="",
        http_proxy="",
        http_proxy_auth="",
        bot_prefix="[BOT] ",
    )
    channel.enabled = True
    channel._client = fake_client
    return channel


@pytest.mark.asyncio
async def test_send_retries_transient_network_error_and_succeeds(monkeypatch):
    sender = _FlakySender(fail_times=2, exc=ConnectionResetError())
    channel = _build_channel(_FakeClient(sender))

    sleep_calls = []

    async def _fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(discord_channel_module.asyncio, "sleep", _fake_sleep)

    await channel.send("discord:ch:1", "hello", {"channel_id": "1"})

    assert sender.calls == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_send_raises_after_retry_limit(monkeypatch):
    sender = _FlakySender(fail_times=10, exc=ConnectionResetError())
    channel = _build_channel(_FakeClient(sender))

    sleep_calls = []

    async def _fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(discord_channel_module.asyncio, "sleep", _fake_sleep)

    with pytest.raises(ConnectionResetError):
        await channel.send("discord:ch:1", "hello", {"channel_id": "1"})

    assert sender.calls == 3
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_send_does_not_retry_non_transient_error(monkeypatch):
    sender = _FlakySender(fail_times=10, exc=ValueError("bad request"))
    channel = _build_channel(_FakeClient(sender))

    sleep_calls = []

    async def _fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(discord_channel_module.asyncio, "sleep", _fake_sleep)

    with pytest.raises(ValueError):
        await channel.send("discord:ch:1", "hello", {"channel_id": "1"})

    assert sender.calls == 1
    assert sleep_calls == []
