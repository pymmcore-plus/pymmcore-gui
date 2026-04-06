"""LLM chat integration for pymmcore-gui."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymmcore_gui._qt.QtWidgets import QWidget

# Enable debug logging for the LLM subsystem.
# Set PYMMCORE_GUI_LLM_DEBUG=1 in the environment, or call
#   logging.getLogger("pymmcore_gui.llm").setLevel(logging.DEBUG)
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def create_llm_chat(parent: QWidget) -> QWidget:
    """Create the LLM chat widget, or a fallback if dependencies are missing."""
    try:
        from claude_code_sdk import __version__ as _sdk_version
    except ImportError:
        _logger.warning("claude-code-sdk not installed — using fallback widget")
        from pymmcore_gui.llm._fallback_widget import LLMFallbackWidget

        return LLMFallbackWidget(parent=parent)

    _logger.info("claude-code-sdk v%s available", _sdk_version)
    from pymmcore_gui.llm._chat_widget import LLMChatWidget

    return LLMChatWidget(parent=parent)
