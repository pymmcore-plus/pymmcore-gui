"""Local LLM backend: llama-cpp-python server + OpenAI client."""

from __future__ import annotations

import json
import logging
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any

from pymmcore_plus import CMMCorePlus

from pymmcore_gui._qt.QtCore import QObject, Signal

from ._system_prompt import build_system_prompt
from ._tools import ToolDef, get_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------

DEFAULT_REPO = "bartowski/Qwen2.5-7B-Instruct-GGUF"
DEFAULT_FILE = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"

# Regex to extract <tool_call>{"name": ..., "arguments": ...}</tool_call>
# from the model's output (Qwen2.5-Instruct native format).
_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _ensure_model() -> str:
    """Download the model if needed, return the local path."""
    from huggingface_hub import hf_hub_download

    logger.info("Ensuring model %s/%s is downloaded...", DEFAULT_REPO, DEFAULT_FILE)
    path = hf_hub_download(repo_id=DEFAULT_REPO, filename=DEFAULT_FILE)
    logger.info("Model path: %s", path)
    return path


def _tooldef_to_openai(td: ToolDef) -> dict[str, Any]:
    """Convert a ToolDef to an OpenAI-style tool definition."""
    params = td.parameters
    if "type" in params and "properties" in params:
        schema = params
    elif not params:
        schema = {"type": "object", "properties": {}}
    else:
        properties = {}
        for name, typ in params.items():
            if typ is str:
                properties[name] = {"type": "string"}
            elif typ is int:
                properties[name] = {"type": "integer"}
            elif typ is float:
                properties[name] = {"type": "number"}
            elif typ is bool:
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


def _parse_tool_calls(
    content: str | None,
) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    """Parse <tool_call> tags from model output.

    Returns (clean_text, [(tool_name, args_dict), ...]).
    """
    calls: list[tuple[str, dict[str, Any]]] = []
    for match in _TOOL_CALL_RE.finditer(content or ""):
        try:
            data = json.loads(match.group(1))
            calls.append((data.get("name", ""), data.get("arguments", {})))
        except json.JSONDecodeError:
            pass
    clean = _TOOL_CALL_RE.sub("", content or "").strip()
    return clean, calls


# ---------------------------------------------------------------------------
# LocalChatSession
# ---------------------------------------------------------------------------


class LocalChatSession(QObject):
    """Chat session using a local llama-cpp-python server.

    Same signal interface as ChatSession / OllamaChatSession.
    """

    text_received = Signal(str)
    tool_use_started = Signal(str, str, str)
    tool_result_received = Signal(str, str, bool)
    response_finished = Signal()
    error_occurred = Signal(str)
    session_ready = Signal()
    rate_limit_updated = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hardware_enabled = True
        self._messages: list[dict[str, Any]] = []
        self._tool_map: dict[str, ToolDef] = {}
        self._openai_tools: list[dict[str, Any]] = []
        self._server_proc: subprocess.Popen[str] | None = None
        self._port: int = 0
        self._ready = False
        self._responding = False
        self._client: Any = None  # openai.OpenAI

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
            target=self._start_server, daemon=True, name="llm-server-start"
        )
        thread.start()

    def send_message(self, text: str) -> None:
        if not self._ready or self._client is None:
            self.error_occurred.emit("Session not ready. Please wait.")
            return
        if self._responding:
            return
        self._responding = True
        self._messages.append({"role": "user", "content": text})
        thread = threading.Thread(
            target=self._run_conversation, daemon=True, name="llm-chat"
        )
        thread.start()

    def interrupt(self) -> None:
        pass

    def stop_session(self) -> None:
        self._ready = False
        self._stop_server()
        self._messages.clear()

    def _rebuild_tools(self) -> None:
        tools = get_tools(hardware_enabled=self._hardware_enabled)
        self._tool_map = {td.name: td for td in tools}
        self._openai_tools = [_tooldef_to_openai(td) for td in tools]

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def _start_server(self) -> None:
        try:
            model_path = _ensure_model()
            self._port = _find_free_port()
            self._rebuild_tools()

            logger.info("Starting llama.cpp server on port %d...", self._port)
            self._server_proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "llama_cpp.server",
                    "--model",
                    model_path,
                    "--port",
                    str(self._port),
                    "--n_gpu_layers",
                    "-1",
                    "--n_ctx",
                    "4096",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if not self._wait_for_server(timeout=120):
                self.error_occurred.emit("Server failed to start in time.")
                return

            from openai import OpenAI

            self._client = OpenAI(
                base_url=f"http://localhost:{self._port}/v1",
                api_key="not-needed",
            )

            system_prompt = build_system_prompt(CMMCorePlus.instance())
            self._messages = [{"role": "system", "content": system_prompt}]
            self._ready = True
            logger.info("Local LLM server ready on port %d", self._port)
            self.session_ready.emit()

        except Exception as e:
            logger.exception("Failed to start local LLM server")
            self.error_occurred.emit(f"Server start failed: {e}")

    def _wait_for_server(self, timeout: float = 120) -> bool:
        import urllib.request

        deadline = time.monotonic() + timeout
        url = f"http://localhost:{self._port}/v1/models"
        while time.monotonic() < deadline:
            if self._server_proc and self._server_proc.poll() is not None:
                stderr = self._server_proc.stderr
                err = stderr.read() if stderr else ""
                logger.error("Server exited early: %s", err[:500])
                return False
            try:
                urllib.request.urlopen(url, timeout=2)
                return True
            except Exception:
                time.sleep(0.5)
        return False

    def _stop_server(self) -> None:
        if self._server_proc is not None:
            logger.info("Stopping local LLM server...")
            try:
                self._server_proc.send_signal(signal.SIGTERM)
                self._server_proc.wait(timeout=5)
            except Exception:
                self._server_proc.kill()
            self._server_proc = None
        self._client = None

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def _run_conversation(self) -> None:
        try:
            max_tool_rounds = 10
            for _ in range(max_tool_rounds):
                resp = self._client.chat.completions.create(
                    model="local",
                    messages=self._messages,
                    tools=self._openai_tools or None,
                    max_tokens=1024,
                )
                msg = resp.choices[0].message
                content = msg.content or ""

                # Parse <tool_call> tags from model output
                clean_text, parsed_calls = _parse_tool_calls(content)

                # Also check OpenAI-style tool_calls (in case server
                # natively supports them for some models)
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        parsed_calls.append((tc.function.name, args))

                if clean_text:
                    self.text_received.emit(clean_text)

                if not parsed_calls:
                    self._messages.append({"role": "assistant", "content": content})
                    break

                # Store the raw assistant message
                self._messages.append({"role": "assistant", "content": content})

                for name, args in parsed_calls:
                    tool_id = f"{name}_{id(args)}"
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
                            logger.debug("Tool OK: %s", name)
                            is_error = False
                        except Exception as e:
                            logger.exception("Tool ERROR: %s", name)
                            result = str(e)
                            is_error = True

                    self.tool_result_received.emit(tool_id, result, is_error)
                    # Feed tool result back as user message (Qwen format)
                    self._messages.append(
                        {
                            "role": "user",
                            "content": f"<tool_response>\n{result}\n</tool_response>",
                        }
                    )
            else:
                self.text_received.emit("(Reached max tool rounds.)")

        except Exception as e:
            logger.exception("Local LLM conversation error")
            self.error_occurred.emit(str(e))
        finally:
            self._responding = False
            self.response_finished.emit()
