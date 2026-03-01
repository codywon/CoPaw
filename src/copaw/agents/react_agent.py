# -*- coding: utf-8 -*-
"""CoPaw Agent - Main agent implementation.

This module provides the main CoPawAgent class built on ReActAgent,
with integrated tools, skills, and memory management.
"""
import logging
import os
from typing import TYPE_CHECKING, Any, List, Optional, Type

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.tool import Toolkit
from pydantic import BaseModel

from .command_handler import CommandHandler
from .hooks import BootstrapHook, MemoryCompactionHook
from .memory import CoPawInMemoryMemory
from .model_factory import create_model_and_formatter
from .prompt import build_system_prompt_from_working_dir
from .subagents import (
    SubagentManager,
    select_role_for_task,
    should_force_dispatch,
)
from .skills_manager import (
    ensure_skills_initialized,
    get_working_skills_dir,
    list_available_skills,
)
from .tools import (
    browser_use,
    create_memory_search_tool,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    make_spawn_worker_tool,
    read_file,
    send_file_to_user,
    write_file,
)
from .utils import process_file_and_media_blocks_in_message
from ..agents.memory import MemoryManager
from ..config import SubagentRoleConfig, SubagentsConfig, load_config
from ..constant import (
    MEMORY_COMPACT_KEEP_RECENT,
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)
from ..providers import load_providers_json, resolve_llm_config

if TYPE_CHECKING:
    from ..providers import ResolvedModelConfig

logger = logging.getLogger(__name__)


class CoPawAgent(ReActAgent):
    """CoPaw Agent with integrated tools, skills, and memory management.

    This agent extends ReActAgent with:
    - Built-in tools (shell, file operations, browser, etc.)
    - Dynamic skill loading from working directory
    - Memory management with auto-compaction
    - Bootstrap guidance for first-time setup
    - System command handling (/compact, /new, etc.)
    """

    def __init__(
        self,
        env_context: Optional[str] = None,
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List[Any]] = None,
        memory_manager: MemoryManager | None = None,
        max_iters: int = 50,
        max_input_length: int = 128 * 1024,  # 128K = 131072 tokens
        *,
        agent_role: str = "main",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        tool_allowlist: Optional[set[str]] = None,
        enable_skills: bool = True,
        allowed_skills: Optional[set[str]] = None,
        subagents_config: Optional[SubagentsConfig] = None,
        llm_cfg: Optional["ResolvedModelConfig"] = None,
    ):
        """Initialize CoPawAgent.

        Args:
            env_context: Optional environment context to prepend to
                system prompt
            enable_memory_manager: Whether to enable memory manager
            mcp_clients: Optional list of MCP clients for tool
                integration
            memory_manager: Optional memory manager instance
            max_iters: Maximum number of reasoning-acting iterations
                (default: 50)
            max_input_length: Maximum input length in tokens for model
                context window (default: 128K = 131072)
        """
        self._env_context = env_context
        self._agent_role = agent_role
        self._session_id = session_id or ""
        self._user_id = user_id or ""
        self._channel = channel or ""
        self._tool_allowlist = tool_allowlist
        self._enable_skills = enable_skills
        self._allowed_skills = allowed_skills
        self._max_input_length = max_input_length
        self._max_iters = max_iters
        self._mcp_clients = mcp_clients or []
        self._subagent_manager: Optional[SubagentManager] = None
        if subagents_config is not None:
            self._subagents_config = subagents_config
        else:
            self._subagents_config = load_config().agents.subagents

        # Memory compaction threshold: configurable ratio of max_input_length
        self._memory_compact_threshold = int(
            max_input_length * MEMORY_COMPACT_RATIO,
        )

        # Initialize toolkit with built-in tools
        toolkit = self._create_toolkit()

        # Load and register skills
        self._register_skills(toolkit)

        # Build system prompt
        sys_prompt = self._build_sys_prompt()

        # Create model and formatter using factory method
        model, formatter = create_model_and_formatter(llm_cfg=llm_cfg)

        # Initialize parent ReActAgent
        super().__init__(
            name="Friday",
            model=model,
            sys_prompt=sys_prompt,
            toolkit=toolkit,
            memory=CoPawInMemoryMemory(),
            formatter=formatter,
            max_iters=max_iters,
        )

        # Setup memory manager
        self._setup_memory_manager(
            enable_memory_manager,
            memory_manager,
        )

        # Setup command handler
        self.command_handler = CommandHandler(
            agent_name=self.name,
            memory=self.memory,
            formatter=self.formatter,
            memory_manager=self.memory_manager,
            enable_memory_manager=self._enable_memory_manager,
        )

        # Register hooks
        self._register_hooks()

    def _create_toolkit(self) -> Toolkit:
        """Create and populate toolkit with built-in tools.

        Returns:
            Configured toolkit instance
        """
        toolkit = Toolkit()

        built_in_tools = [
            execute_shell_command,
            read_file,
            write_file,
            edit_file,
            browser_use,
            desktop_screenshot,
            send_file_to_user,
            get_current_time,
        ]
        for tool_func in built_in_tools:
            tool_name = getattr(tool_func, "__name__", "")
            if (
                self._tool_allowlist is not None
                and tool_name not in self._tool_allowlist
            ):
                continue
            toolkit.register_tool_function(tool_func)

        if self._agent_role == "main" and self._subagents_config.enabled:
            spawn_worker_tool = make_spawn_worker_tool(self._spawn_worker_impl)
            toolkit.register_tool_function(spawn_worker_tool)
            logger.debug("Registered spawn_worker tool for main agent")

        return toolkit

    def _register_skills(self, toolkit: Toolkit) -> None:
        """Load and register skills from working directory.

        Args:
            toolkit: Toolkit to register skills to
        """
        if not self._enable_skills:
            logger.debug("Skills disabled for role=%s", self._agent_role)
            return

        # Check skills initialization
        ensure_skills_initialized()

        working_skills_dir = get_working_skills_dir()
        available_skills = list_available_skills()

        for skill_name in available_skills:
            if (
                self._allowed_skills is not None
                and skill_name not in self._allowed_skills
            ):
                continue
            skill_dir = working_skills_dir / skill_name
            if skill_dir.exists():
                try:
                    toolkit.register_agent_skill(str(skill_dir))
                    logger.debug("Registered skill: %s", skill_name)
                except Exception as e:
                    logger.error(
                        "Failed to register skill '%s': %s",
                        skill_name,
                        e,
                    )

    def _build_sys_prompt(self) -> str:
        """Build system prompt from working dir files and env context.

        Returns:
            Complete system prompt string
        """
        sys_prompt = build_system_prompt_from_working_dir()
        if self._env_context is not None:
            sys_prompt = self._env_context + "\n\n" + sys_prompt

        if self._agent_role == "main" and self._subagents_config.enabled:
            sys_prompt += (
                "\n\n# Subagent Orchestration\n"
                "- You can delegate complex or parallelizable subtasks by "
                "calling the `spawn_worker` tool.\n"
                "- Use it when decomposition, isolation, or long-running task "
                "execution is beneficial.\n"
                "- Keep responsibility split clear: delegate execution details "
                "to subagents, then synthesize final answer yourself.\n"
                f"- Current dispatch_mode: "
                f"`{self._subagents_config.dispatch_mode}`.\n"
            )
        return sys_prompt

    def _setup_memory_manager(
        self,
        enable_memory_manager: bool,
        memory_manager: MemoryManager | None,
    ) -> None:
        """Setup memory manager and register memory search tool if enabled.

        Args:
            enable_memory_manager: Whether to enable memory manager
            memory_manager: Optional memory manager instance
        """
        # Check env var: if ENABLE_MEMORY_MANAGER=false, disable memory manager
        env_enable_mm = os.getenv("ENABLE_MEMORY_MANAGER", "")
        if env_enable_mm.lower() == "false":
            enable_memory_manager = False

        self._enable_memory_manager: bool = enable_memory_manager
        self.memory_manager = memory_manager

        # Register memory_search tool if enabled and available
        if self._enable_memory_manager and self.memory_manager is not None:
            self.memory_manager.chat_model = self.model
            self.memory_manager.formatter = self.formatter

            memory_search_tool = create_memory_search_tool(self.memory_manager)
            self.toolkit.register_tool_function(memory_search_tool)
            logger.debug("Registered memory_search tool")

    def _register_hooks(self) -> None:
        """Register pre-reasoning hooks for bootstrap and memory compaction."""
        if self._agent_role != "main":
            return

        # Bootstrap hook - checks BOOTSTRAP.md on first interaction
        config = load_config()
        bootstrap_hook = BootstrapHook(
            working_dir=WORKING_DIR,
            language=config.agents.language,
        )
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="bootstrap_hook",
            hook=bootstrap_hook.__call__,
        )
        logger.debug("Registered bootstrap hook")

        # Memory compaction hook - auto-compact when context is full
        if self._enable_memory_manager and self.memory_manager is not None:
            memory_compact_hook = MemoryCompactionHook(
                memory_manager=self.memory_manager,
                memory_compact_threshold=self._memory_compact_threshold,
                keep_recent=MEMORY_COMPACT_KEEP_RECENT,
            )
            self.register_instance_hook(
                hook_type="pre_reasoning",
                hook_name="memory_compact_hook",
                hook=memory_compact_hook.__call__,
            )
            logger.debug("Registered memory compaction hook")

    def rebuild_sys_prompt(self) -> None:
        """Rebuild and replace the system prompt.

        Useful after load_session_state to ensure the prompt reflects
        the latest AGENTS.md / SOUL.md / PROFILE.md on disk.

        Updates both self._sys_prompt and the first system-role
        message stored in self.memory.content (if one exists).
        """
        self._sys_prompt = self._build_sys_prompt()

        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            break

    async def register_mcp_clients(self) -> None:
        """Register MCP clients on this agent's toolkit after construction."""
        for client in self._mcp_clients:
            await self.toolkit.register_mcp_client(client)

    def _get_or_create_subagent_manager(self) -> SubagentManager:
        if self._subagent_manager is None:
            cfg = self._subagents_config
            self._subagent_manager = SubagentManager(
                max_concurrency=cfg.max_concurrency,
                default_timeout_seconds=cfg.default_timeout_seconds,
                hard_timeout_seconds=cfg.hard_timeout_seconds,
            )
        return self._subagent_manager

    def _select_subagent_mcp_clients(
        self,
        role_config: Optional[SubagentRoleConfig] = None,
    ) -> list[Any]:
        cfg = self._subagents_config
        role_policy = role_config.mcp_policy if role_config is not None else "inherit"
        if role_policy == "inherit":
            policy = cfg.mcp_policy
            selected = set(cfg.mcp_selected)
        else:
            policy = role_policy
            selected = set(role_config.mcp_selected if role_config else [])

        if policy == "none":
            return []
        if policy == "all":
            return list(self._mcp_clients)

        if not selected:
            return []
        filtered: list[Any] = []
        for client in self._mcp_clients:
            client_name = getattr(client, "name", "")
            if client_name in selected:
                filtered.append(client)
        return filtered

    def _resolve_subagent_skills_policy(
        self,
        role_config: Optional[SubagentRoleConfig] = None,
    ) -> tuple[bool, Optional[set[str]]]:
        cfg = self._subagents_config
        role_policy = (
            role_config.skills_policy if role_config is not None else "inherit"
        )
        if role_policy == "inherit":
            policy = cfg.skills_policy
            selected = set(cfg.skills_selected)
        else:
            policy = role_policy
            selected = set(role_config.skills_selected if role_config else [])

        if policy == "none":
            return False, None
        if policy == "all":
            return True, None
        if not selected:
            return False, None
        return True, selected

    def _resolve_subagent_tool_allowlist(
        self,
        role_config: Optional[SubagentRoleConfig] = None,
    ) -> set[str]:
        if role_config is not None and role_config.tool_allowlist:
            return set(role_config.tool_allowlist)
        return set(self._subagents_config.tools.default_enabled)

    def _create_subagent_worker(
        self,
        role_config: Optional[SubagentRoleConfig] = None,
        llm_cfg: Optional["ResolvedModelConfig"] = None,
    ) -> "CoPawAgent":
        enable_skills, allowed_skills = self._resolve_subagent_skills_policy(
            role_config=role_config,
        )
        tool_allowlist = self._resolve_subagent_tool_allowlist(
            role_config=role_config,
        )
        role_key = role_config.key if role_config is not None else ""
        role_name = role_config.name if role_config is not None else ""

        sub_env_context = (
            f"{self._env_context or ''}\n"
            "====================\n"
            "- current_role: subagent\n"
            "- execution_mode: delegated_task\n"
            f"- role_key: {role_key or '(default)'}\n"
            f"- role_name: {role_name or '(default)'}\n"
            "===================="
        )
        if role_config is not None:
            if role_config.identity_prompt:
                sub_env_context += (
                    "\n\n# Role Identity\n"
                    f"{role_config.identity_prompt}\n"
                )
            if role_config.tool_guidelines:
                sub_env_context += (
                    "\n\n# Tool Guidelines\n"
                    f"{role_config.tool_guidelines}\n"
                )
        return CoPawAgent(
            env_context=sub_env_context,
            enable_memory_manager=False,
            mcp_clients=self._select_subagent_mcp_clients(
                role_config=role_config,
            ),
            memory_manager=None,
            max_iters=self._max_iters,
            max_input_length=self._max_input_length,
            agent_role="subagent",
            session_id=self._session_id,
            user_id=self._user_id,
            channel=self._channel,
            tool_allowlist=tool_allowlist,
            enable_skills=enable_skills,
            allowed_skills=allowed_skills,
            subagents_config=self._subagents_config,
            llm_cfg=llm_cfg,
        )

    def _resolve_subagent_model_plan(
        self,
        role_config: Optional[SubagentRoleConfig] = None,
    ) -> dict[str, Any]:
        """Resolve model selection for a subagent from role policy first."""
        providers_data = load_providers_json()
        active_provider = providers_data.active_llm.provider_id
        active_model = providers_data.active_llm.model

        selected_provider = active_provider
        selected_model = active_model
        fallback_used = False
        llm_cfg = None

        if role_config is not None:
            role_provider = role_config.model_provider.strip()
            role_model = role_config.model_name.strip()
            if role_provider and role_model:
                seen: set[str] = set()
                candidates: list[str] = []
                for item in [role_model, *role_config.fallback_models]:
                    model_name = item.strip()
                    if not model_name:
                        continue
                    key = model_name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(model_name)

                for idx, model_name in enumerate(candidates):
                    resolved = resolve_llm_config(
                        role_provider,
                        model_name,
                        providers_data,
                    )
                    if resolved is None:
                        continue
                    selected_provider = role_provider
                    selected_model = model_name
                    fallback_used = idx > 0
                    llm_cfg = resolved
                    break
                if llm_cfg is None:
                    logger.warning(
                        "Role model policy unresolved for role=%s provider=%s model=%s; falling back to active model",
                        role_config.key,
                        role_provider,
                        role_model,
                    )

        if llm_cfg is None and selected_provider and selected_model:
            llm_cfg = resolve_llm_config(
                selected_provider,
                selected_model,
                providers_data,
            )

        return {
            "provider": selected_provider,
            "model": selected_model,
            "fallback_used": fallback_used,
            "reasoning_effort": (
                role_config.reasoning_effort.strip()
                if role_config is not None
                else ""
            ),
            "cost_estimate_usd": None,
            "llm_cfg": llm_cfg,
        }

    async def _spawn_worker_impl(
        self,
        *,
        task: str,
        label: str = "",
        timeout_seconds: Optional[int] = None,
        profile: str = "",
        dispatch_reason: str = "",
    ) -> str:
        if self._agent_role != "main":
            return "spawn_worker is disabled for subagents."
        if not self._subagents_config.enabled:
            return (
                "Subagents are disabled. Enable them in "
                "Agent > Subagents > Config first."
            )
        if not task or not task.strip():
            return "Subagent task is empty. Please provide a non-empty task."

        task_prompt = task.strip()
        role_config = select_role_for_task(
            task_prompt=task_prompt,
            config=self._subagents_config,
            profile=profile,
        )
        if profile.strip() and role_config is None:
            return (
                f"Unknown subagent profile: '{profile.strip()}'. "
                "Please check Agent > Subagents > Roles."
            )
        role_key = role_config.key if role_config is not None else ""
        effective_timeout = timeout_seconds
        if (
            effective_timeout is None
            and role_config is not None
            and role_config.timeout_seconds is not None
        ):
            effective_timeout = role_config.timeout_seconds

        if dispatch_reason.strip():
            resolved_reason = dispatch_reason.strip()
        elif profile.strip():
            resolved_reason = f"manual_tool_call:profile:{profile.strip()}"
        else:
            resolved_reason = "manual_tool_call"

        manager = self._get_or_create_subagent_manager()
        model_plan = self._resolve_subagent_model_plan(role_config=role_config)

        async def _runner() -> str:
            worker = self._create_subagent_worker(
                role_config=role_config,
                llm_cfg=model_plan.get("llm_cfg"),
            )
            await worker.register_mcp_clients()
            worker.set_console_output_enabled(enabled=False)
            reply = await worker.reply(
                msg=Msg(
                    name="user",
                    role="user",
                    content=task_prompt,
                ),
            )
            text = reply.get_text_content()
            return text or "(Subagent finished with empty response.)"

        run_kwargs = dict(
            task_prompt=task_prompt,
            runner=_runner,
            parent_session_id=self._session_id,
            origin_user_id=self._user_id,
            origin_channel=self._channel,
            label=label.strip(),
            role_key=role_key,
            dispatch_reason=resolved_reason,
            timeout_seconds=effective_timeout,
            write_mode=self._subagents_config.write_mode,
            allowed_paths=self._subagents_config.allowed_paths,
            retry_max_attempts=self._subagents_config.retry_max_attempts,
            retry_backoff_seconds=self._subagents_config.retry_backoff_seconds,
            selected_model_provider=model_plan.get("provider", ""),
            selected_model_name=model_plan.get("model", ""),
            reasoning_effort=model_plan.get("reasoning_effort", ""),
            model_fallback_used=bool(model_plan.get("fallback_used", False)),
            cost_estimate_usd=model_plan.get("cost_estimate_usd"),
        )

        if self._subagents_config.execution_mode == "async":
            queued_task = manager.submit_task(**run_kwargs)
            return (
                "Subagent task queued.\n"
                f"- task_id: {queued_task.task_id}\n"
                f"- status: {queued_task.status}\n"
                f"- role: {queued_task.role_key or '(default)'}\n"
                f"- dispatch_reason: {queued_task.dispatch_reason}\n"
                "- monitor: Agent > Subagents > Tasks"
            )

        task_snapshot = await manager.run_task(**run_kwargs)

        if task_snapshot.status == "success":
            return (
                f"Subagent completed successfully.\n"
                f"- task_id: {task_snapshot.task_id}\n"
                f"- status: {task_snapshot.status}\n"
                f"- role: {task_snapshot.role_key or '(default)'}\n"
                f"- dispatch_reason: {task_snapshot.dispatch_reason}\n"
                f"- summary:\n{task_snapshot.result_summary}"
            )
        return (
            f"Subagent finished with status '{task_snapshot.status}'.\n"
            f"- task_id: {task_snapshot.task_id}\n"
            f"- role: {task_snapshot.role_key or '(default)'}\n"
            f"- dispatch_reason: {task_snapshot.dispatch_reason}\n"
            f"- error: {task_snapshot.error_message or '(none)'}\n"
            f"- summary: {task_snapshot.result_summary or '(empty)'}"
        )

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """Override reply to process file blocks and handle commands.

        Args:
            msg: Input message(s) from user
            structured_model: Optional pydantic model for structured output

        Returns:
            Response message
        """
        # Process file and media blocks in messages
        if msg is not None:
            await process_file_and_media_blocks_in_message(msg)

        # Check if message is a system command
        last_msg = msg[-1] if isinstance(msg, list) else msg
        query = (
            last_msg.get_text_content() if isinstance(last_msg, Msg) else None
        )

        if self.command_handler.is_command(query):
            logger.info(f"Received command: {query}")
            msg = await self.command_handler.handle_command(query)
            await self.print(msg)
            return msg

        if (
            self._agent_role == "main"
            and query is not None
            and self._subagents_config.enabled
        ):
            decision = should_force_dispatch(
                task_prompt=query,
                config=self._subagents_config,
            )
            if decision.should_dispatch:
                role = select_role_for_task(
                    task_prompt=query,
                    config=self._subagents_config,
                )
                profile = role.key if role is not None else ""
                delegated = await self._spawn_worker_impl(
                    task=query,
                    label="auto_dispatch",
                    profile=profile,
                    dispatch_reason=decision.reason,
                )
                return Msg(
                    name=self.name,
                    role="assistant",
                    content=delegated,
                )

        # Normal message processing
        return await super().reply(msg=msg, structured_model=structured_model)
