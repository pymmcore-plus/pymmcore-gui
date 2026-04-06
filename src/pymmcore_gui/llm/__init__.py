"""LLM chat integration for pymmcore-gui."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymmcore_gui._qt.QtWidgets import QWidget

_logger = logging.getLogger(__name__)
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def _has_ollama() -> bool:
    try:
        import ollama  # noqa: F401

        return True
    except ImportError:
        return False


def _has_claude() -> bool:
    try:
        import claude_code_sdk  # noqa: F401

        return True
    except ImportError:
        return False


def create_llm_chat(parent: QWidget) -> QWidget:
    """Create the LLM chat widget.

    Backend priority: ollama (local) > claude-code-sdk > fallback.
    """
    from pymmcore_gui.llm._chat_widget import LLMChatWidget

    if _has_ollama():
        _logger.info("Using ollama backend (local)")
        from pymmcore_gui.llm._ollama_backend import OllamaChatSession

        return LLMChatWidget(parent=parent, session_factory=OllamaChatSession)

    if _has_claude():
        _logger.info("Using claude-code-sdk backend")
        from pymmcore_gui.llm._chat_backend import ChatSession

        return LLMChatWidget(parent=parent, session_factory=ChatSession)

    _logger.warning("No LLM backend available")
    from pymmcore_gui.llm._fallback_widget import LLMFallbackWidget

    return LLMFallbackWidget(parent=parent)
