from types import SimpleNamespace
import json

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    MessageType,
)

from copaw.app.channels.renderer import MessageRenderer, RenderStyle


def _msg(msg_type, content):
    return SimpleNamespace(type=msg_type, content=content)


def _data_block(data):
    return SimpleNamespace(type=ContentType.DATA, data=data)


def test_hide_tool_call_messages_when_tool_details_disabled():
    renderer = MessageRenderer(RenderStyle(show_tool_details=False))
    message = _msg(
        MessageType.FUNCTION_CALL,
        [
            _data_block(
                {
                    "name": "execute_shell_command",
                    "arguments": '{"command":"dir"}',
                }
            )
        ],
    )

    assert renderer.message_to_parts(message) == []


def test_hide_tool_output_text_when_tool_details_disabled():
    renderer = MessageRenderer(RenderStyle(show_tool_details=False))
    message = _msg(
        MessageType.FUNCTION_CALL_OUTPUT,
        [
            _data_block(
                {
                    "name": "execute_shell_command",
                    "output": "ok",
                }
            )
        ],
    )

    assert renderer.message_to_parts(message) == []


def test_keep_tool_output_media_when_tool_details_disabled():
    renderer = MessageRenderer(RenderStyle(show_tool_details=False))
    output = json.dumps(
        [
            {
                "type": "image",
                "source": {"type": "url", "url": "https://example.com/a.png"},
            }
        ]
    )
    message = _msg(
        MessageType.FUNCTION_CALL_OUTPUT,
        [
            _data_block(
                {
                    "name": "execute_shell_command",
                    "output": output,
                }
            )
        ],
    )

    parts = renderer.message_to_parts(message)
    assert len(parts) == 1
    assert getattr(parts[0], "type", None) == ContentType.IMAGE


def test_hide_reasoning_messages_when_reasoning_disabled():
    renderer = MessageRenderer(RenderStyle(show_reasoning=False))
    message = _msg(
        MessageType.REASONING,
        [
            SimpleNamespace(
                type=ContentType.TEXT,
                text="internal chain of thought",
            )
        ],
    )

    assert renderer.message_to_parts(message) == []


def test_hide_thinking_blocks_in_tool_output_when_reasoning_disabled():
    renderer = MessageRenderer(
        RenderStyle(
            show_tool_details=True,
            show_reasoning=False,
        )
    )
    output = json.dumps(
        [
            {"type": "thinking", "thinking": "internal chain of thought"},
            {"type": "text", "text": "public result"},
        ]
    )
    message = _msg(
        MessageType.FUNCTION_CALL_OUTPUT,
        [
            _data_block(
                {
                    "name": "tool_a",
                    "output": output,
                }
            )
        ],
    )

    parts = renderer.message_to_parts(message)
    texts = [getattr(p, "text", "") for p in parts]
    assert any("tool_a" in text for text in texts)
    assert any("public result" in text for text in texts)
    assert all("internal chain of thought" not in text for text in texts)
