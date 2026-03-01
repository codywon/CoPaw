import pytest

from copaw.agents.tools.send_file import send_file_to_user


def _block_type(block) -> str:
    if isinstance(block, dict):
        return str(block.get("type", ""))
    return str(getattr(block, "type", ""))


def _block_text(block) -> str:
    if isinstance(block, dict):
        return str(block.get("text", ""))
    return str(getattr(block, "text", ""))


@pytest.mark.asyncio
async def test_send_file_to_user_returns_file_block_without_success_text(
    tmp_path,
):
    path = tmp_path / "demo.txt"
    path.write_text("hello", encoding="utf-8")

    resp = await send_file_to_user(str(path))

    assert len(resp.content) == 1
    assert _block_type(resp.content[0]) == "file"
    assert all(_block_type(block) != "text" for block in resp.content)


@pytest.mark.asyncio
async def test_send_file_to_user_returns_error_when_file_missing():
    resp = await send_file_to_user("not_exists_12345.txt")

    assert len(resp.content) == 1
    assert _block_type(resp.content[0]) == "text"
    assert "does not exist" in _block_text(resp.content[0])
