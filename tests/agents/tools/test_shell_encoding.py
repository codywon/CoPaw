from pathlib import Path

import pytest

from copaw.agents.tools import shell as shell_module


class _FakeProcess:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
    ):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def wait(self):
        return self.returncode

    async def communicate(self):
        return self._stdout, self._stderr


def _response_text(resp) -> str:
    block = resp.content[0]
    if isinstance(block, dict):
        return block.get("text", "")
    return getattr(block, "text", "")


@pytest.mark.asyncio
async def test_execute_shell_command_prefers_utf8_when_locale_is_cp936(
    monkeypatch,
):
    expected = "\u72b6\u6001\u6b63\u5e38"
    fake_proc = _FakeProcess(stdout=expected.encode("utf-8"))

    async def _fake_create_subprocess_shell(*_args, **_kwargs):
        return fake_proc

    monkeypatch.setattr(
        shell_module.asyncio,
        "create_subprocess_shell",
        _fake_create_subprocess_shell,
    )
    monkeypatch.setattr(
        shell_module.locale,
        "getpreferredencoding",
        lambda _do_setlocale=False: "cp936",
    )

    resp = await shell_module.execute_shell_command(
        "echo ignored",
        cwd=Path("."),
    )

    assert _response_text(resp) == expected


@pytest.mark.asyncio
async def test_execute_shell_command_decodes_utf8_stderr_when_command_fails(
    monkeypatch,
):
    stderr_text = "\u72b6\u6001\u5f02\u5e38"
    fake_proc = _FakeProcess(stderr=stderr_text.encode("utf-8"), returncode=2)

    async def _fake_create_subprocess_shell(*_args, **_kwargs):
        return fake_proc

    monkeypatch.setattr(
        shell_module.asyncio,
        "create_subprocess_shell",
        _fake_create_subprocess_shell,
    )
    monkeypatch.setattr(
        shell_module.locale,
        "getpreferredencoding",
        lambda _do_setlocale=False: "cp936",
    )

    resp = await shell_module.execute_shell_command(
        "echo ignored",
        cwd=Path("."),
    )
    text = _response_text(resp)

    assert "Command failed with exit code 2." in text
    assert "[stderr]" in text
    assert stderr_text in text
