# -*- coding: utf-8 -*-
import os
from typing import Optional, Union, Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict

from ..constant import (
    HEARTBEAT_DEFAULT_EVERY,
    HEARTBEAT_DEFAULT_TARGET,
)


class BaseChannelConfig(BaseModel):
    """Base for channel config (read from config.json, no env)."""

    enabled: bool = False
    bot_prefix: str = ""


class IMessageChannelConfig(BaseChannelConfig):
    db_path: str = "~/Library/Messages/chat.db"
    poll_sec: float = 1.0


class DiscordConfig(BaseChannelConfig):
    bot_token: str = ""
    http_proxy: str = ""
    http_proxy_auth: str = ""


class DingTalkConfig(BaseChannelConfig):
    """DingTalk: client_id, client_secret; media_dir for received media."""

    client_id: str = ""
    client_secret: str = ""
    media_dir: str = "~/.copaw/media"


class FeishuConfig(BaseChannelConfig):
    """Feishu/Lark channel: app_id, app_secret; optional encrypt_key,
    verification_token for event handler. media_dir for received media.
    """

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    media_dir: str = "~/.copaw/media"


class QQConfig(BaseChannelConfig):
    app_id: str = ""
    client_secret: str = ""


class ConsoleConfig(BaseChannelConfig):
    """Console channel: prints agent responses to stdout."""

    enabled: bool = True


class ChannelConfig(BaseModel):
    """Built-in channel configs; extra keys allowed for plugin channels."""

    model_config = ConfigDict(extra="allow")

    imessage: IMessageChannelConfig = IMessageChannelConfig()
    discord: DiscordConfig = DiscordConfig()
    dingtalk: DingTalkConfig = DingTalkConfig()
    feishu: FeishuConfig = FeishuConfig()
    qq: QQConfig = QQConfig()
    console: ConsoleConfig = ConsoleConfig()


class LastApiConfig(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None


class ActiveHoursConfig(BaseModel):
    """Optional active window for heartbeat (e.g. 08:00–22:00)."""

    start: str = "08:00"
    end: str = "22:00"


class HeartbeatConfig(BaseModel):
    """Heartbeat: run agent with HEARTBEAT.md as query at interval."""

    model_config = {"populate_by_name": True}

    every: str = Field(default=HEARTBEAT_DEFAULT_EVERY)
    target: str = Field(default=HEARTBEAT_DEFAULT_TARGET)
    active_hours: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="activeHours",
    )


class AgentsDefaultsConfig(BaseModel):
    heartbeat: Optional[HeartbeatConfig] = None


class AgentsRunningConfig(BaseModel):
    """Agent runtime behavior configuration."""

    max_iters: int = Field(
        default=50,
        ge=1,
        description=(
            "Maximum number of reasoning-acting iterations for ReAct agent"
        ),
    )
    max_input_length: int = Field(
        default=128 * 1024,  # 128K = 131072 tokens
        ge=1000,
        description=(
            "Maximum input length (tokens) for the model context window"
        ),
    )


class SubagentToolsConfig(BaseModel):
    """Default tools available to subagents."""

    default_enabled: List[str] = Field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "edit_file",
            "execute_shell_command",
            "web_search",
            "web_fetch",
        ],
    )


SubagentPolicy = Literal["none", "selected", "all"]
SubagentDispatchMode = Literal[
    "advisory",
    "force_when_matched",
    "force_by_default",
]
SubagentRoleSelectionMode = Literal["auto", "default"]
SubagentRolePolicy = Literal["inherit", "none", "selected", "all"]
SubagentExecutionMode = Literal["sync", "async"]


class SubagentRoleConfig(BaseModel):
    """Role profile for subagent specialization."""

    key: str
    name: str
    description: str = ""
    identity_prompt: str = ""
    tool_guidelines: str = ""
    enabled: bool = True
    routing_keywords: List[str] = Field(default_factory=list)
    tool_allowlist: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[int] = Field(default=None, ge=1)
    mcp_policy: SubagentRolePolicy = "inherit"
    mcp_selected: List[str] = Field(default_factory=list)
    skills_policy: SubagentRolePolicy = "inherit"
    skills_selected: List[str] = Field(default_factory=list)


class SubagentsConfig(BaseModel):
    """Subagent orchestration behavior configuration."""

    enabled: bool = False
    max_concurrency: int = Field(default=5, ge=1)
    default_timeout_seconds: int = Field(default=3600, ge=1)
    hard_timeout_seconds: int = Field(default=10800, ge=1)
    execution_mode: SubagentExecutionMode = "sync"
    retry_max_attempts: int = Field(default=1, ge=1)
    retry_backoff_seconds: int = Field(default=0, ge=0)
    write_mode: Literal["worktree", "direct"] = "worktree"
    allow_nested_spawn: bool = False
    dispatch_mode: SubagentDispatchMode = "advisory"
    auto_dispatch_keywords: List[str] = Field(
        default_factory=lambda: [
            "parallel",
            "batch",
            "crawl",
            "research",
            "collect",
            "并行",
            "批量",
            "爬取",
            "调研",
            "采集",
        ],
    )
    auto_dispatch_min_prompt_chars: int = Field(default=120, ge=1)
    role_selection_mode: SubagentRoleSelectionMode = "auto"
    default_role: str = ""
    roles: List[SubagentRoleConfig] = Field(default_factory=list)
    allowed_paths: List[str] = Field(default_factory=lambda: ["<workspace>"])
    tools: SubagentToolsConfig = Field(default_factory=SubagentToolsConfig)
    mcp_policy: SubagentPolicy = "selected"
    mcp_selected: List[str] = Field(default_factory=list)
    skills_policy: SubagentPolicy = "selected"
    skills_selected: List[str] = Field(default_factory=list)


class AgentsConfig(BaseModel):
    defaults: AgentsDefaultsConfig = Field(
        default_factory=AgentsDefaultsConfig,
    )
    running: AgentsRunningConfig = Field(
        default_factory=AgentsRunningConfig,
    )
    subagents: SubagentsConfig = Field(
        default_factory=SubagentsConfig,
    )
    language: str = Field(
        default="zh",
        description="Language for agent MD files (en/zh)",
    )
    installed_md_files_language: Optional[str] = Field(
        default=None,
        description="Language of currently installed md files",
    )


class LastDispatchConfig(BaseModel):
    """Last channel/user/session that received a user-originated reply."""

    channel: str = ""
    user_id: str = ""
    session_id: str = ""


class MCPClientConfig(BaseModel):
    """Configuration for a single MCP client.

    Supports three transport modes:
    - "stdio" (default): Launch a local subprocess via command + args.
    - "sse": Connect to a remote MCP server over Server-Sent Events.
    - "streamable_http": Connect via the Streamable HTTP transport.

    For "stdio", ``command`` and ``args`` are required.
    For "sse" / "streamable_http", ``url`` is required; ``command``/``args``
    are ignored.
    """

    name: str
    description: str = ""
    enabled: bool = True
    transport: str = Field(
        default="stdio",
        description=(
            'Transport mode: "stdio", "sse", or "streamable_http"'
        ),
    )
    # stdio fields
    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    # sse / streamable_http fields
    url: str = Field(
        default="",
        description="Server URL for sse / streamable_http transport",
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers for sse / streamable_http transport",
    )


class MCPConfig(BaseModel):
    """MCP clients configuration.

    Uses a dict to allow dynamic client definitions.
    Default tavily_search client is created and auto-enabled if API key exists.
    """

    clients: Dict[str, MCPClientConfig] = Field(
        default_factory=lambda: {
            "tavily_search": MCPClientConfig(
                name="tavily_mcp",
                # Auto-enable if TAVILY_API_KEY exists in environment
                enabled=bool(os.getenv("TAVILY_API_KEY")),
                command="npx",
                args=["-y", "tavily-mcp@latest"],
                env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
            ),
        },
    )


class Config(BaseModel):
    """Root config (config.json)."""

    channels: ChannelConfig = ChannelConfig()
    mcp: MCPConfig = MCPConfig()
    last_api: LastApiConfig = LastApiConfig()
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    last_dispatch: Optional[LastDispatchConfig] = None
    # When False, channel output hides tool call/result details (show "...").
    show_tool_details: bool = True


ChannelConfigUnion = Union[
    IMessageChannelConfig,
    DiscordConfig,
    DingTalkConfig,
    FeishuConfig,
    QQConfig,
    ConsoleConfig,
]
