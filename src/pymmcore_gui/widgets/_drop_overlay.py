"""Transparent overlay widget for drag-and-drop file opening."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_gui._io import SUPPORTED_EXTENSIONS
from pymmcore_gui._qt.QtCore import Qt, Signal
from pymmcore_gui._qt.QtGui import QColor, QPainter, QPen
from pymmcore_gui._qt.QtWidgets import QWidget

if TYPE_CHECKING:
    from pymmcore_gui._qt.QtCore import QMimeData
    from pymmcore_gui._qt.QtGui import (
        QDragEnterEvent,
        QDragLeaveEvent,
        QDropEvent,
        QPaintEvent,
    )


OVERLAY_COLOR = QColor(100, 150, 255, 40)
BORDER_COLOR = QColor(100, 150, 255, 120)
BORDER_WIDTH = 3


def has_supported_files(mime_data: QMimeData) -> bool:
    """Check if mime data contains URLs with supported file extensions."""
    if not mime_data.hasUrls():
        return False
    for url in mime_data.urls():
        path = url.toLocalFile().rstrip("/")
        if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            return True
    return False


class DropOverlay(QWidget):
    """Transparent overlay shown during file drag-over."""

    fileDropped = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_overlay(self) -> None:
        """Resize to cover the parent widget, show, and raise."""
        if (p := self.parentWidget()) is not None:
            self.setGeometry(p.rect())
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self.hide()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), OVERLAY_COLOR)
        pen = QPen(BORDER_COLOR, BORDER_WIDTH)
        painter.setPen(pen)
        r = self.rect().adjusted(
            BORDER_WIDTH // 2,
            BORDER_WIDTH // 2,
            -BORDER_WIDTH // 2,
            -BORDER_WIDTH // 2,
        )
        painter.drawRect(r)
        painter.end()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData() and has_supported_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            self.hide_overlay()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.hide_overlay()

    def dropEvent(self, event: QDropEvent) -> None:
        self.hide_overlay()
        if event.mimeData() is None:
            return
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                self.fileDropped.emit(path)
                break
        event.acceptProposedAction()
