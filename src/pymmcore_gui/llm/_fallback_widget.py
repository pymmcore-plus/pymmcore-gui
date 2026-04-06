"""Fallback widget shown when no LLM backend is installed."""

from __future__ import annotations

from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtWidgets import QLabel, QVBoxLayout, QWidget


class LLMFallbackWidget(QWidget):
    """Shown when no LLM backend is available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "<h3>Christina</h3>"
            "<p>No LLM backend is installed. Install one of:</p>"
            "<p><b>Local (recommended, fully self-contained):</b></p>"
            "<pre>pip install pymmcore-gui[local-llm]</pre>"
            "<p>Downloads a ~4 GB model on first use.</p>"
            "<p><b>Ollama (local, requires ollama app):</b></p>"
            "<pre>pip install pymmcore-gui[ollama]</pre>"
            "<p><b>Cloud (Claude, requires Max subscription):</b></p>"
            "<pre>pip install pymmcore-gui[claude]</pre>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)
