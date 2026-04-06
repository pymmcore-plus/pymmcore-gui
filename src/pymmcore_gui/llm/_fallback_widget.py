"""Fallback widget shown when claude-code-sdk is not installed."""

from __future__ import annotations

from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtWidgets import QLabel, QVBoxLayout, QWidget


class LLMFallbackWidget(QWidget):
    """Shown when claude-code-sdk is not available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(
            "<h3>Christina</h3>"
            "<p>The AI assistant requires the <code>claude-code-sdk</code> "
            "package and the <code>claude</code> CLI to be installed.</p>"
            "<p>Install with:</p>"
            "<pre>pip install claude-code-sdk</pre>"
            "<p>And ensure the <code>claude</code> CLI is installed and "
            "authenticated with a Max subscription.</p>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)
