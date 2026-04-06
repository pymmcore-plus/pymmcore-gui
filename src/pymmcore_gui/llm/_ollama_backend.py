"""Ollama chat backend: local LLM with tool calling."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
from typing import Any

from pymmcore_plus import CMMCorePlus

from pymmcore_gui._qt.QtCore import QObject, Signal

from ._system_prompt import build_system_prompt
from ._tools import ToolDef, get_tools

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5:7b"


def _tooldef_to_ollama(td: ToolDef) -> dict[str, Any]:
    """Convert a ToolDef to an ollama tool definition."""
    # Build JSON Schema properties from ToolDef.parameters
    params = td.parameters
    if "type" in params and "properties" in params:
        schema = params  # already a full schema
    elif not params:
        schema = {"type": "object", "properties": {}}
    else:
        properties = {}
        for name, ptype in params.items():
            if ptype is str:
                properties[name] = {"type": "string"}
            elif ptype is int:
                properties[name] = {"type": "integer"}
            elif ptype is float:
                properties[name] = {"type": "number"}
            elif ptype is bool:
                properties[name] = {"type": "boolean"}
            else:
                properties[name] = {"type": "string"}
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
        }

    return {
        "type": "function",
        "function": {
            "name": td.name,
            "description": td.description,
            "parameters": schema,
        },
    }


class OllamaChatSession(QObject):
    """Chat session using a local ollama model.

    Same signal interface as ChatSession so the widget can use either.
    """

    text_received = Signal(str)
    tool_use_started = Signal(str, str, str)  # tool_id, name, input_json
    tool_result_received = Signal(str, str, bool)  # tool_id, content, is_error
    response_finished = Signal()
    error_occurred = Signal(str)
    session_ready = Signal()
    status_changed = Signal(str)  # startup progress text
    rate_limit_updated = Signal(dict)  # never emitted, but keeps interface

    def __init__(
        self,
        parent: QObject | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._hardware_enabled = True
        self._messages: list[dict[str, Any]] = []
        self._tool_map: dict[str, ToolDef] = {}
        self._tools: list[dict[str, Any]] = []
        self._ready = False
        self._responding = False

    @property
    def hardware_enabled(self) -> bool:
        return self._hardware_enabled

    def set_hardware_enabled(self, enabled: bool) -> None:
        if enabled == self._hardware_enabled:
            return
        self._hardware_enabled = enabled
        self._rebuild_tools()

    def start_session(self) -> None:
        if self._ready:
            return
        thread = threading.Thread(
            target=self._init_session, daemon=True, name="ollama-init"
        )
        thread.start()

    def _init_session(self) -> None:
        """Ensure ollama is running, model is available, and initialize."""
        try:
            import ollama

            # Try to connect; if not running, start it
            self.status_changed.emit("Connecting to ollama...")
            if not self._ensure_ollama_running():
                self.error_occurred.emit(
                    "Could not find or start ollama.\n\n"
                    "Install it from https://ollama.com"
                )
                return

            # Check if model exists, pull if not
            try:
                ollama.show(self._model)
            except Exception:
                logger.info("Pulling model %s (first run)...", self._model)
                self.status_changed.emit(f"Downloading model {self._model}...")
                ollama.pull(self._model)

            self._rebuild_tools()
            system_prompt = build_system_prompt(CMMCorePlus.instance())

            # Warm up: send a trivial message with full system prompt + tools
            # so the model is loaded and the prompt is cached.
            self.status_changed.emit("Loading model into memory...")
            ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "hi"},
                ],
                tools=self._tools,
                keep_alive="10m",
            )
            self._messages = [{"role": "system", "content": system_prompt}]
            self._ready = True
            logger.debug(
                "Ollama session ready (model=%s, hardware=%s)",
                self._model,
                self._hardware_enabled,
            )
            self.session_ready.emit()
        except Exception as e:
            logger.exception("Ollama init failed")
            self.error_occurred.emit(str(e))

    @staticmethod
    def _ensure_ollama_running() -> bool:
        """Check if ollama is reachable; if not, try to start it."""
        import urllib.request

        url = "http://localhost:11434/api/tags"

        # Already running?
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            pass

        # Try to start it
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return False

        logger.debug("Starting ollama serve...")
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for it
        for _ in range(30):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(url, timeout=2)
                return True
            except Exception:
                pass
        return False

    def send_message(self, text: str) -> None:
        if not self._ready:
            self.error_occurred.emit("Session not ready.")
            return
        if self._responding:
            return
        self._responding = True
        self._messages.append({"role": "user", "content": text})
        thread = threading.Thread(
            target=self._run_conversation, daemon=True, name="ollama-chat"
        )
        thread.start()

    def interrupt(self) -> None:
        pass  # ollama sync calls can't be interrupted easily

    def stop_session(self) -> None:
        self._ready = False
        self._messages.clear()

    def _rebuild_tools(self) -> None:
        tools = get_tools(hardware_enabled=self._hardware_enabled)
        self._tool_map = {td.name: td for td in tools}
        self._tools = [_tooldef_to_ollama(td) for td in tools]

    def _run_conversation(self) -> None:
        """Run the chat loop in a background thread."""
        try:
            import ollama

            max_tool_rounds = 10
            for _ in range(max_tool_rounds):
                response = ollama.chat(
                    model=self._model,
                    messages=self._messages,
                    tools=self._tools,
                    stream=False,
                )
                msg = response.message

                # Emit any text content
                if msg.content:
                    self.text_received.emit(msg.content)

                # Handle tool calls
                if not msg.tool_calls:
                    self._messages.append(
                        {"role": "assistant", "content": msg.content or ""}
                    )
                    break

                # Add assistant message with tool calls
                self._messages.append(msg.model_dump())

                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = dict(tc.function.arguments)
                    tool_id = f"{name}_{id(tc)}"
                    input_json = json.dumps(args, indent=2)
                    self.tool_use_started.emit(tool_id, name, input_json)

                    td = self._tool_map.get(name)
                    if td is None:
                        result = f"Unknown tool: {name}"
                        is_error = True
                    else:
                        try:
                            logger.debug("Tool CALL: %s args=%s", name, args)
                            result = td.handler(args)
                            logger.debug("Tool OK: %s len=%d", name, len(result))
                            is_error = False
                        except Exception as e:
                            logger.exception("Tool ERROR: %s", name)
                            result = str(e)
                            is_error = True

                    self.tool_result_received.emit(tool_id, result, is_error)
                    self._messages.append({"role": "tool", "content": result})
            else:
                self.text_received.emit("(Reached maximum tool call rounds.)")

        except Exception as e:
            logger.exception("Ollama conversation error")
            self.error_occurred.emit(str(e))
        finally:
            self._responding = False
            self.response_finished.emit()
