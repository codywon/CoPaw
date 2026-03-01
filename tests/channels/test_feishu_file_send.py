from types import SimpleNamespace

import pytest

from copaw.app.channels.feishu.channel import FeishuChannel


async def _dummy_process(_request):
    if False:
        yield None


class _FakeHttpResponse:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def json(self, content_type=None):  # noqa: ARG002
        return self._payload


class _FakePostContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
        return False


class _FakeHttpClient:
    def __init__(self):
        self.last_form = None

    def post(self, url, headers=None, data=None):  # noqa: ARG002
        self.last_form = data
        payload = {"code": 0, "data": {"file_key": "file_key_123"}}
        return _FakePostContext(_FakeHttpResponse(payload))


def _extract_form_field_value(form, name: str):
    for field in form._fields:  # pylint: disable=protected-access
        field_name = field[0].get("name")
        if field_name == name:
            return field[2]
    return None


@pytest.mark.asyncio
async def test_upload_file_uses_stream_file_type_for_video(tmp_path):
    channel = FeishuChannel(
        process=_dummy_process,
        enabled=True,
        app_id="app_id",
        app_secret="app_secret",
        bot_prefix="",
    )
    channel._http = _FakeHttpClient()  # pylint: disable=protected-access
    async def _fake_token():
        return "token"

    channel._get_tenant_access_token = _fake_token  # type: ignore[method-assign]

    video_path = tmp_path / "demo.mp4"
    video_path.write_bytes(b"video")

    file_key = await channel._upload_file(str(video_path))  # pylint: disable=protected-access
    assert file_key == "file_key_123"
    assert channel._http.last_form is not None  # pylint: disable=protected-access
    assert (
        _extract_form_field_value(channel._http.last_form, "file_type")  # pylint: disable=protected-access
        == "stream"
    )


@pytest.mark.asyncio
async def test_part_to_file_path_or_url_supports_audio_url(tmp_path):
    channel = FeishuChannel(
        process=_dummy_process,
        enabled=True,
        app_id="app_id",
        app_secret="app_secret",
        bot_prefix="",
    )
    audio_path = tmp_path / "demo.opus"
    audio_path.write_bytes(b"audio")
    part = SimpleNamespace(audio_url=str(audio_path), filename="demo.opus")

    resolved = await channel._part_to_file_path_or_url(part)  # pylint: disable=protected-access
    assert resolved == str(audio_path)
