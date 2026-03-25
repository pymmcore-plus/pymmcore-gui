from __future__ import annotations

from pymmcore_gui._qt.QtWidgets import QSplitter, QWidget

DEFAULT_SIDEBAR_WIDTH = 300
DEFAULT_PANEL_HEIGHT = 220
MIN_SIDEBAR_WIDTH = 160
MIN_PANEL_HEIGHT = 100


def splitter_size(widget: QWidget) -> int:
    """Return the size allocated to *widget* by its parent QSplitter."""
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return -1
    idx = parent.indexOf(widget)
    if idx < 0:
        return -1
    return parent.sizes()[idx]


def ensure_splitter_size(widget: QWidget, size: int) -> None:
    """If widget is collapsed in a QSplitter, restore it to *size*."""
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return
    idx = parent.indexOf(widget)
    if idx < 0:
        return
    sizes = parent.sizes()
    if sizes[idx] == 0:
        sizes[idx] = size
        parent.setSizes(sizes)
