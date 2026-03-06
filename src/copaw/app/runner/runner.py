# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict

from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .command_dispatch import (
    _get_last_user_text,
    _is_command,
    run_command_path,
)
from .query_error_dump import write_query_error_dump
from ..bot_profiles import (
    extract_requested_bot_id,
    namespace_session_id,
    resolve_bot_profile,
)
from .session import SafeJSONSession
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.memory import MemoryManager
from ...agents.model_factory import create_model_and_formatter
from ...agents.react_agent import CoPawAgent
from ...agents.tools import read_file, write_file, edit_file
from ...agents.utils.token_counting import _get_token_counter
from ...config import load_config
from ...constant import (
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)

logger = logging.getLogger(__name__)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload

        self._memory_managers: Dict[str, MemoryManager] = {}
        self._memory_manager_lock = asyncio.Lock()

    def set_chat_manager(self, chat_manager):
        """Set chat manager for auto-registration.

        Args:
            chat_manager: ChatManager instance
        """
        self._chat_manager = chat_manager

    def set_mcp_manager(self, mcp_manager):
        """Set MCP client manager for hot-reload support.

        Args:
            mcp_manager: MCPClientManager instance
        """
        self._mcp_manager = mcp_manager

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle agent query.
        """
        # Command path: do not create agent; yield from run_command_path
        query = _get_last_user_text(msgs)
        if query and _is_command(query):
            logger.info("Command path: %s", query.strip()[:50])
            async for msg, last in run_command_path(request, msgs, self):
                yield msg, last
            return

        agent = None
        chat = None
        session_state_loaded = False
        raw_session_id = ""
        namespaced_session_id = ""
        user_id = ""
        channel = DEFAULT_CHANNEL

        try:
            raw_session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)
            config = load_config()
            requested_bot_id = extract_requested_bot_id(request)
            resolved_bot = resolve_bot_profile(
                profiles_config=config.agents.bot_profiles,
                channel=channel,
                requested_bot_id=requested_bot_id,
            )
            namespaced_session_id = namespace_session_id(
                bot_key=resolved_bot.key,
                session_id=raw_session_id,
            )

            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": raw_session_id,
                        "namespaced_session_id": namespaced_session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "bot_id": resolved_bot.key,
                        "bot_source": resolved_bot.source,
                        "msgs_len": len(msgs) if msgs else 0,
                        "msgs_str": str(msgs)[:300] + "...",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            env_context = build_env_context(
                session_id=namespaced_session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )
            env_context += (
                "\n\n# Bot Profile\n"
                f"- bot_id: {resolved_bot.key}\n"
                f"- bot_name: {resolved_bot.name}\n"
                f"- resolve_source: {resolved_bot.source}\n"
                f"- original_session_id: {raw_session_id}\n"
            )
            if resolved_bot.identity_prompt:
                env_context += (
                    "\n# Bot Identity\n"
                    f"{resolved_bot.identity_prompt}\n"
                )

            # Get MCP clients from manager (hot-reloadable)
            mcp_clients = []
            if self._mcp_manager is not None:
                mcp_clients = await self._mcp_manager.get_clients()

            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length
            memory_manager = await self._get_or_create_memory_manager(
                resolved_bot.key,
            )

            agent = CoPawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=memory_manager,
                max_iters=max_iters,
                max_input_length=max_input_length,
                agent_role="main",
                session_id=namespaced_session_id,
                user_id=user_id,
                channel=channel,
                subagents_config=config.agents.subagents,
            )
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)

            logger.debug(
                f"Agent Query msgs {msgs}",
            )

            name = "New Chat"
            if len(msgs) > 0:
                content = msgs[0].get_text_content()
                if content:
                    name = msgs[0].get_text_content()[:10]
                else:
                    name = "Media Message"

            if self._chat_manager is not None:
                chat = await self._chat_manager.get_or_create_chat(
                    namespaced_session_id,
                    user_id,
                    channel,
                    name=name,
                    meta={
                        "bot_id": resolved_bot.key,
                        "bot_name": resolved_bot.name,
                        "source_session_id": raw_session_id,
                    },
                )

            try:
                await self.session.load_session_state(
                    session_id=namespaced_session_id,
                    user_id=user_id,
                    agent=agent,
                )
            except KeyError as e:
                logger.warning(
                    "load_session_state skipped (state schema mismatch): %s; "
                    "will save fresh state on completion to recover file",
                    e,
                )
            session_state_loaded = True

            # Rebuild system prompt so it always reflects the latest
            # AGENTS.md / SOUL.md / PROFILE.md, not the stale one saved
            # in the session state.
            agent.rebuild_sys_prompt()

            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(msgs),
            ):
                yield msg, last

        except asyncio.CancelledError as exc:
            logger.info(f"query_handler: {namespaced_session_id} cancelled!")
            if agent is not None:
                await agent.interrupt()
            raise RuntimeError("Task has been cancelled!") from exc
        except Exception as e:
            debug_dump_path = write_query_error_dump(
                request=request,
                exc=e,
                locals_=locals(),
            )
            path_hint = (
                f"\n(Details:  {debug_dump_path})" if debug_dump_path else ""
            )
            logger.exception(f"Error in query handler: {e}{path_hint}")
            if debug_dump_path:
                setattr(e, "debug_dump_path", debug_dump_path)
                if hasattr(e, "add_note"):
                    e.add_note(
                        f"(Details:  {debug_dump_path})",
                    )
                suffix = f"\n(Details:  {debug_dump_path})"
                e.args = (
                    (f"{e.args[0]}{suffix}" if e.args else suffix.strip()),
                ) + e.args[1:]
            raise
        finally:
            if agent is not None and session_state_loaded:
                await self.session.save_session_state(
                    session_id=namespaced_session_id,
                    user_id=user_id,
                    agent=agent,
                )

            if self._chat_manager is not None and chat is not None:
                await self._chat_manager.update_chat(chat)

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        # Load environment variables from .env file
        env_path = Path(__file__).resolve().parents[4] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment variables from {env_path}")
        else:
            logger.debug(
                f".env file not found at {env_path}, "
                "using existing environment variables",
            )

        session_dir = str(WORKING_DIR / "sessions")
        self.session = SafeJSONSession(save_dir=session_dir)

        try:
            config = load_config()
            default_bot = config.agents.bot_profiles.default_bot
            await self._get_or_create_memory_manager(default_bot)
        except Exception as e:
            logger.exception(f"MemoryManager start failed: {e}")

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        for bot_key, manager in list(self._memory_managers.items()):
            try:
                await manager.close()
            except Exception as e:
                logger.warning(
                    "MemoryManager stop failed for bot=%s: %s",
                    bot_key,
                    e,
                )
        self._memory_managers.clear()

    async def _get_or_create_memory_manager(
        self,
        bot_key: str,
    ) -> MemoryManager:
        normalized_bot_key = (bot_key or "default").strip() or "default"
        async with self._memory_manager_lock:
            manager = self._memory_managers.get(normalized_bot_key)
            if manager is not None:
                return manager

            working_dir = WORKING_DIR / "bot_profiles" / normalized_bot_key
            working_dir.mkdir(parents=True, exist_ok=True)
            manager = MemoryManager(
                working_dir=str(working_dir),
            )
            await manager.start()
            self._memory_managers[normalized_bot_key] = manager
            logger.info(
                "MemoryManager started for bot=%s dir=%s",
                normalized_bot_key,
                str(working_dir),
            )
            return manager
