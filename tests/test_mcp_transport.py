"""Tests for MCP multi-transport support (stdio, sse, streamable_http)."""

import pytest
from pydantic import ValidationError
from copaw.config.config import MCPClientConfig, Config
from copaw.app.mcp.manager import MCPClientManager, _VALID_TRANSPORTS


class TestMCPClientConfig:
    """Config model tests."""

    def test_stdio_backward_compat(self):
        """Existing stdio configs without transport field still work."""
        cfg = MCPClientConfig(name="test", command="npx", args=["-y", "pkg"])
        assert cfg.transport == "stdio"
        assert cfg.url == ""
        assert cfg.headers == {}

    def test_sse_config(self):
        cfg = MCPClientConfig(
            name="sse",
            transport="sse",
            url="http://localhost:8080/sse",
            headers={"Authorization": "Bearer tok"},
        )
        assert cfg.transport == "sse"
        assert cfg.url == "http://localhost:8080/sse"
        assert cfg.headers["Authorization"] == "Bearer tok"

    def test_streamable_http_config(self):
        cfg = MCPClientConfig(
            name="http",
            transport="streamable_http",
            url="http://localhost:8080/mcp",
        )
        assert cfg.transport == "streamable_http"

    def test_stdio_cwd_config(self):
        cfg = MCPClientConfig(name="local", command="npx", cwd="/tmp/mcp")
        assert cfg.transport == "stdio"
        assert cfg.cwd == "/tmp/mcp"

    def test_legacy_alias_fields_normalized(self):
        cfg = MCPClientConfig(
            name="legacy",
            isActive=False,
            type="http",
            baseUrl="http://localhost:8080/mcp",
        )
        assert cfg.enabled is False
        assert cfg.transport == "streamable_http"
        assert cfg.url == "http://localhost:8080/mcp"

    def test_url_without_command_defaults_streamable_http(self):
        cfg = MCPClientConfig(name="auto", url="http://localhost:8080/mcp")
        assert cfg.transport == "streamable_http"

    def test_json_roundtrip(self):
        original = MCPClientConfig(
            name="rt",
            transport="sse",
            url="http://x:9000/sse",
            headers={"X-Key": "val"},
        )
        data = original.model_dump()
        restored = MCPClientConfig(**data)
        assert restored.transport == "sse"
        assert restored.url == original.url
        assert restored.headers == original.headers

    def test_full_config_roundtrip(self):
        config = Config()
        config.mcp.clients["remote"] = MCPClientConfig(
            name="r", transport="sse", url="http://a/sse",
        )
        config.mcp.clients["local"] = MCPClientConfig(
            name="l", command="echo",
        )
        dump = config.model_dump(mode="json")
        restored = Config(**dump)
        assert restored.mcp.clients["remote"].transport == "sse"
        assert restored.mcp.clients["local"].transport == "stdio"

    def test_invalid_transport_rejected_by_model(self):
        with pytest.raises(ValidationError):
            MCPClientConfig(
                name="bad",
                transport="websocket",
                url="ws://localhost",
            )

    def test_stdio_missing_command_rejected_by_model(self):
        with pytest.raises(ValidationError, match="non-empty command"):
            MCPClientConfig(name="bad", transport="stdio")

    def test_remote_missing_url_rejected_by_model(self):
        with pytest.raises(ValidationError, match="non-empty url"):
            MCPClientConfig(name="bad", transport="sse")


class TestMCPClientManager:
    """Manager _create_client factory tests."""

    def test_create_stdio_client(self):
        from agentscope.mcp import StdIOStatefulClient
        cfg = MCPClientConfig(name="s", command="echo", args=["hi"])
        client = MCPClientManager._create_client(cfg)
        assert isinstance(client, StdIOStatefulClient)

    def test_create_sse_client(self):
        from agentscope.mcp import HttpStatefulClient
        cfg = MCPClientConfig(
            name="e", transport="sse", url="http://localhost/sse",
        )
        client = MCPClientManager._create_client(cfg)
        assert isinstance(client, HttpStatefulClient)

    def test_create_streamable_http_client(self):
        from agentscope.mcp import HttpStatefulClient
        cfg = MCPClientConfig(
            name="h", transport="streamable_http", url="http://localhost/mcp",
        )
        client = MCPClientManager._create_client(cfg)
        assert isinstance(client, HttpStatefulClient)

    def test_invalid_transport_raises(self):
        cfg = MCPClientConfig.model_construct(
            name="bad",
            transport="websocket",
            url="ws://localhost",
            command="",
            args=[],
            env={},
            headers={},
            cwd="",
            description="",
            enabled=True,
        )
        with pytest.raises(ValueError, match="websocket"):
            MCPClientManager._create_client(cfg)

    def test_stdio_missing_command_raises(self):
        cfg = MCPClientConfig.model_construct(
            name="bad",
            transport="stdio",
            command="",
            args=[],
            env={},
            headers={},
            cwd="",
            url="",
            description="",
            enabled=True,
        )
        with pytest.raises(ValueError, match="command"):
            MCPClientManager._create_client(cfg)

    def test_sse_missing_url_raises(self):
        cfg = MCPClientConfig.model_construct(
            name="bad",
            transport="sse",
            command="echo",
            args=[],
            env={},
            headers={},
            cwd="",
            url="",
            description="",
            enabled=True,
        )
        with pytest.raises(ValueError, match="url"):
            MCPClientManager._create_client(cfg)

    def test_valid_transports_constant(self):
        assert _VALID_TRANSPORTS == ("stdio", "sse", "streamable_http")
