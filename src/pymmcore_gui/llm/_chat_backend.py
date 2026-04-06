"""Chat backend: manages ClaudeSDKClient in a background thread."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from claude_code_sdk.types import StreamEvent
from pymmcore_plus import CMMCorePlus

from pymmcore_gui._qt.QtCore import QObject, Signal

from ._mcp_tools import create_microscope_server
from ._system_prompt import build_system_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patch: the SDK raises MessageParseError for unknown message types (e.g.
# rate_limit_event), which kills the entire async generator mid-stream.
# We patch parse_message to return a SystemMessage instead of raising, so the
# response stream can continue.
# ---------------------------------------------------------------------------
import claude_code_sdk._internal.message_parser as _mp  # noqa: E402

_original_parse_message = _mp.parse_message


def _safe_parse_message(data: dict) -> Any:
    try:
        return _original_parse_message(data)
    except Exception:
        msg_type = data.get("type", "unknown")
        logger.debug(
            "Unknown SDK message type %r - wrapping as SystemMessage: %s",
            msg_type,
            data,
        )
        return SystemMessage(subtype=msg_type, data=data)


_mp.parse_message = _safe_parse_message

# sentinel value indicating "no tool_use_id" for signal purposes
_NO_TOOL_ID = ""


class ChatSession(QObject):
    """Manages a multi-turn conversation with Claude via the SDK.

    Runs the async ClaudeSDKClient in a background thread with its own
    asyncio event loop.  Communicates back to the Qt main thread via signals.
    """

    # Signals
    text_received = Signal(str)  # chunk of assistant text
    tool_use_started = Signal(str, str, str)  # tool_id, name, input_json
    tool_result_received = Signal(str, str, bool)  # tool_id, content, is_error
    response_finished = Signal()  # assistant turn is complete
    error_occurred = Signal(str)  # error message
    session_ready = Signal()  # client connected and ready
    rate_limit_updated = Signal(dict)  # rate limit info dict

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hardware_enabled = True
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: ClaudeSDKClient | None = None
        self._connected = False

    # ------------------------------------------------------------------
    # Public API (called from Qt main thread)
    # ------------------------------------------------------------------

    @property
    def hardware_enabled(self) -> bool:
        return self._hardware_enabled

    def set_hardware_enabled(self, enabled: bool) -> None:
        """Toggle hardware control.  Reconnects the session."""
        if enabled == self._hardware_enabled:
            return
        self._hardware_enabled = enabled
        # If already connected, reconnect with new tool set
        if self._connected:
            self.stop_session()
            self.start_session()

    def start_session(self) -> None:
        """Start the background thread and connect to Claude."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_event_loop, daemon=True, name="llm-chat"
        )
        self._thread.start()

    def send_message(self, text: str) -> None:
        """Send a user message.  Must be called after session_ready."""
        if self._loop is None or not self._connected:
            self.error_occurred.emit("Session not ready. Please wait.")
            return
        asyncio.run_coroutine_threadsafe(self._send(text), self._loop)

    def interrupt(self) -> None:
        """Interrupt the current response."""
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(self._interrupt(), self._loop)

    def stop_session(self) -> None:
        """Disconnect and stop the background thread."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self._loop = None
        self._client = None
        self._connected = False

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run_event_loop(self) -> None:
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())
        try:
            self._loop.run_forever()
        finally:
            # Drain remaining tasks
            pending = asyncio.all_tasks(self._loop)
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()

    async def _connect(self) -> None:
        """Connect the ClaudeSDKClient."""
        try:
            logger.debug("Connecting to Claude (hw=%s)...", self._hardware_enabled)
            core = CMMCorePlus.instance()
            system_prompt = build_system_prompt(core)
            mcp_server = create_microscope_server(
                hardware_enabled=self._hardware_enabled
            )

            options = ClaudeCodeOptions(
                system_prompt=system_prompt,
                mcp_servers={"microscope": mcp_server},
                permission_mode="bypassPermissions",
                # Only expose our MCP tools — block Claude Code built-ins
                # (Read, Write, Bash, ToolSearch, etc.) so the LLM focuses
                # on the microscope tools.
                allowed_tools=["mcp__microscope__*"],
                max_turns=25,
            )
            self._client = ClaudeSDKClient(options)
            await self._client.connect()
            self._connected = True
            logger.debug("Connected to Claude successfully")
            self.session_ready.emit()
        except Exception as e:
            logger.exception("Failed to connect to Claude")
            self.error_occurred.emit(f"Connection failed: {e}")

    async def _send(self, text: str) -> None:
        """Send a message and process the response stream."""
        if not self._client:
            return
        try:
            logger.debug("Sending message: %s", text[:100])
            await self._client.query(text)
            async for msg in self._client.receive_response():
                logger.debug("Received message: %s", type(msg).__name__)
                self._handle_message(msg)
        except Exception as e:
            logger.exception("Error during conversation")
            self.error_occurred.emit(str(e))
            self.response_finished.emit()

    def _handle_message(self, msg: Any) -> None:
        """Dispatch an SDK message to the appropriate signal."""
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    self.text_received.emit(block.text)
                elif isinstance(block, ToolUseBlock):
                    input_json = json.dumps(block.input, indent=2)
                    self.tool_use_started.emit(block.id, block.name, input_json)
                elif isinstance(block, ToolResultBlock):
                    content = ""
                    if isinstance(block.content, str):
                        content = block.content
                    elif isinstance(block.content, list):
                        parts = []
                        for item in block.content:
                            if isinstance(item, dict):
                                parts.append(item.get("text", str(item)))
                        content = "\n".join(parts)
                    self.tool_result_received.emit(
                        block.tool_use_id or _NO_TOOL_ID,
                        content,
                        bool(block.is_error),
                    )
        elif isinstance(msg, ResultMessage):
            self.response_finished.emit()
        elif isinstance(msg, SystemMessage):
            if msg.subtype == "rate_limit_event":
                info = msg.data.get("rate_limit_info", {})
                logger.debug(
                    "Rate limit: status=%s, resets_at=%s, overage=%s",
                    info.get("status"),
                    info.get("resetsAt"),
                    info.get("isUsingOverage"),
                )
                self.rate_limit_updated.emit(info)
        elif isinstance(msg, StreamEvent):
            pass  # partial streaming events — future enhancement

    async def _interrupt(self) -> None:
        if self._client:
            await self._client.interrupt()

    async def _disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._connected = False
