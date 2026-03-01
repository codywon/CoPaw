# -*- coding: utf-8 -*-
"""Safe JSON session with filename sanitization for cross-platform
compatibility.

Windows filenames cannot contain: \\ / : * ? " < > |
This module wraps agentscope's JSONSession so that session_id and user_id
are sanitized before being used as filenames.
"""
import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone

from agentscope.session import JSONSession
from agentscope.module import StateModule
from agentscope._logging import logger as agentscope_logger


# Characters forbidden in Windows filenames
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')
_TMP_SUFFIX = ".tmp"
logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Replace characters that are illegal in Windows filenames with ``--``.

    >>> sanitize_filename('discord:dm:12345')
    'discord--dm--12345'
    >>> sanitize_filename('normal-name')
    'normal-name'
    """
    return _UNSAFE_FILENAME_RE.sub("--", name)


class SafeJSONSession(JSONSession):
    """JSONSession subclass that sanitizes session_id / user_id before
    building file paths.

    All other behaviour (save / load / state management) is inherited
    unchanged from :class:`JSONSession`.
    """

    def _get_save_path(self, session_id: str, user_id: str) -> str:
        """Return a filesystem-safe save path.

        Overrides the parent implementation to ensure the generated
        filename is valid on Windows, macOS and Linux.
        """
        os.makedirs(self.save_dir, exist_ok=True)
        safe_sid = sanitize_filename(session_id)
        safe_uid = sanitize_filename(user_id) if user_id else ""
        if safe_uid:
            file_path = f"{safe_uid}_{safe_sid}.json"
        else:
            file_path = f"{safe_sid}.json"
        return os.path.join(self.save_dir, file_path)

    async def save_session_state(
        self,
        session_id: str,
        user_id: str = "",
        **state_modules_mapping: StateModule,
    ) -> None:
        """Write state JSON atomically to avoid partial/corrupt files."""
        state_dicts = {
            name: state_module.state_dict()
            for name, state_module in state_modules_mapping.items()
        }
        target_path = self._get_save_path(session_id, user_id=user_id)

        def _write_atomic() -> None:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=os.path.basename(target_path) + ".",
                suffix=_TMP_SUFFIX,
                dir=os.path.dirname(target_path),
                text=True,
            )
            try:
                with os.fdopen(
                    fd,
                    "w",
                    encoding="utf-8",
                    errors="surrogatepass",
                ) as file:
                    json.dump(state_dicts, file, ensure_ascii=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(tmp_path, target_path)
            finally:
                try:
                    os.remove(tmp_path)
                except (OSError, FileNotFoundError):
                    pass

        await asyncio.to_thread(_write_atomic)

    async def load_session_state(
        self,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
        **state_modules_mapping: StateModule,
    ) -> None:
        """Load state and quarantine corrupted JSON instead of hard-failing."""
        session_save_path = self._get_save_path(session_id, user_id=user_id)

        def _read_json():
            """Read and parse JSON file; returns (states, error_info)."""
            if not os.path.exists(session_save_path):
                return None, "not_found"
            try:
                with open(
                    session_save_path,
                    "r",
                    encoding="utf-8",
                    errors="surrogatepass",
                ) as file:
                    return json.load(file), None
            except json.JSONDecodeError:
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                corrupt_path = f"{session_save_path}.corrupt-{ts}.json"
                try:
                    os.replace(session_save_path, corrupt_path)
                except OSError:
                    corrupt_path = ""
                return None, f"corrupt:{corrupt_path}"

        states, err = await asyncio.to_thread(_read_json)

        if err == "not_found":
            if allow_not_exist:
                agentscope_logger.info(
                    "Session file %s does not exist. Skip loading session state.",
                    session_save_path,
                )
                return
            raise ValueError(
                f"Failed to load session state for file {session_save_path} "
                "does not exist.",
            )

        if err is not None and err.startswith("corrupt:"):
            corrupt_path = err[len("corrupt:"):]
            hint = f"; moved to {corrupt_path}" if corrupt_path else ""
            logger.warning(
                "Corrupted session state JSON: %s%s; skip loading and continue",
                session_save_path,
                hint,
            )
            if allow_not_exist:
                return
            raise ValueError(
                f"Failed to load session state for file {session_save_path} "
                f"because JSON is corrupted{hint}.",
            )

        if not isinstance(states, dict):
            logger.warning(
                "Session state is not a dict for file %s; skip loading.",
                session_save_path,
            )
            return

        for name, state_module in state_modules_mapping.items():
            if name in states:
                state_module.load_state_dict(states[name])
        agentscope_logger.info(
            "Load session state from %s successfully.",
            session_save_path,
        )
