"""NavigationBar adapter that matches the ActivityBar interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_gui._qt.Qlementine import NavigationBar  # type: ignore[attr-defined]
from pymmcore_gui._qt.QtCore import Signal
from pymmcore_gui._qt.QtWidgets import QHBoxLayout, QWidget

if TYPE_CHECKING:
    from pymmcore_gui._qt.QtGui import QIcon


class NavigationBarAdapter(QWidget):
    """Wraps Qlementine's NavigationBar with the same interface as ActivityBar."""

    panelToggled = Signal(str)  # panel_id or "" to collapse

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._nav = NavigationBar(self)  # pyright: ignore[reportCallIssue]
        self._nav.setFixedHeight(32)
        self._nav.setItemsShouldExpand(False)
        self._panel_ids: list[str] = []
        self._active: str | None = None
        self._collapsible = True

        # Smaller text for panel/sidebar context
        font = self._nav.font()
        font.setPointSizeF(font.pointSizeF() * 0.75)
        font.setBold(False)
        self._nav.setFont(font)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._nav)
        layout.addStretch()

        self._nav.currentIndexChanged.connect(self._on_index_changed)  # pyright: ignore[reportAttributeAccessIssue]

    # ---- public API (matches ActivityBar) ---------------------------------

    @property
    def activePanel(self) -> str | None:
        return self._active

    @property
    def collapsible(self) -> bool:
        return self._collapsible

    @collapsible.setter
    def collapsible(self, value: bool) -> None:
        self._collapsible = value

    @property
    def panelIds(self) -> list[str]:
        return list(self._panel_ids)

    def addPanel(self, panel_id: str, text: str, *, icon: QIcon | None = None) -> None:
        if icon:
            self._nav.addItem(text, icon)
        else:
            self._nav.addItem(text)
        self._panel_ids.append(panel_id)

    def setActive(self, panel_id: str | None) -> None:
        """Programmatically activate (or deactivate) a panel."""
        if panel_id and panel_id in self._panel_ids:
            if self._active == panel_id and self._collapsible:
                # Toggle off
                self.deselect()
                self.panelToggled.emit("")
            elif self._active != panel_id:
                self.setActiveSilent(panel_id)
                self.panelToggled.emit(panel_id)
        elif not panel_id and self._active and self._collapsible:
            self.deselect()
            self.panelToggled.emit("")

    def deselect(self) -> None:
        """Uncheck the active item without emitting panelToggled."""
        self._active = None
        self._nav.blockSignals(True)
        self._nav.setCurrentIndex(-1)
        self._nav.blockSignals(False)

    def activateFirst(self) -> None:
        """Activate the first panel if any exist."""
        if self._panel_ids:
            self.setActiveSilent(self._panel_ids[0])
            self.panelToggled.emit(self._panel_ids[0])

    def setActiveSilent(self, panel_id: str) -> None:
        """Update selection without emitting panelToggled."""
        if panel_id in self._panel_ids:
            self._active = panel_id
            idx = self._panel_ids.index(panel_id)
            self._nav.blockSignals(True)
            self._nav.setCurrentIndex(idx)
            self._nav.blockSignals(False)

    # ---- internals --------------------------------------------------------

    def _on_index_changed(self) -> None:
        index = self._nav.currentIndex()
        if 0 <= index < len(self._panel_ids):
            panel_id = self._panel_ids[index]
            self._active = panel_id
            self.panelToggled.emit(panel_id)
