from copaw.app.channels.manager import ChannelManager
from copaw.config.config import Config


async def _dummy_process(_request):
    if False:
        yield None


def test_channel_manager_propagates_show_tool_details_to_console():
    config = Config()
    config.show_tool_details = False
    config.show_reasoning = False

    manager = ChannelManager.from_config(
        process=_dummy_process,
        config=config,
    )
    console = next((c for c in manager.channels if c.channel == "console"), None)

    assert console is not None
    assert getattr(console, "_show_tool_details", True) is False
    assert getattr(console, "_show_reasoning", True) is False


def test_channel_clone_can_override_show_tool_details():
    config = Config()
    config.show_tool_details = True
    config.show_reasoning = True
    manager = ChannelManager.from_config(
        process=_dummy_process,
        config=config,
    )
    console = next((c for c in manager.channels if c.channel == "console"), None)

    assert console is not None
    cloned = console.clone(
        config.channels.console,
        show_tool_details=False,
        show_reasoning=False,
    )
    assert getattr(cloned, "_show_tool_details", True) is False
    assert getattr(cloned, "_show_reasoning", True) is False
