from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_gui._qt.QtCore import Qt, Signal
from pymmcore_gui._qt.QtWidgets import (
    QBoxLayout,
    QHBoxLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pymmcore_gui._qt.QtGui import QIcon


class ActivityBar(QWidget):
    """Icon strip that toggles panels. Supports vertical or horizontal."""

    panelToggled = Signal(str)  # panel_id or "" to collapse

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QToolButton] = {}
        self._active: str | None = None
        self._collapsible = True
        self._orientation = orientation

        if orientation == Qt.Orientation.Vertical:
            self._layout: QBoxLayout = QVBoxLayout(self)
        else:
            self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)
        self._layout.addStretch()

    # ---- public API -------------------------------------------------------

    @property
    def orientation(self) -> Qt.Orientation:
        return self._orientation

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
        return list(self._buttons)

    def addPanel(
        self, panel_id: str, text: str, *, icon: QIcon | None = None
    ) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(text)
        if icon:
            btn.setIcon(icon)
        else:
            btn.setText(text)
        btn.setCheckable(True)
        btn.setAutoExclusive(False)
        btn.setObjectName(panel_id)
        btn.clicked.connect(self._on_clicked)

        self._buttons[panel_id] = btn
        self._layout.insertWidget(self._layout.count() - 1, btn)
        return btn

    def setActive(self, panel_id: str | None) -> None:
        """Programmatically activate (or deactivate) a panel."""
        if panel_id:
            self._toggle(panel_id)
        elif self._active:
            self._toggle(self._active)

    def deselect(self) -> None:
        """Uncheck the active button without emitting panelToggled."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = None

    def activateFirst(self) -> None:
        """Activate the first panel if any exist."""
        first = next(iter(self._buttons), None)
        if first:
            self._activate_without_collapse(first)

    def setActiveSilent(self, panel_id: str) -> None:
        """Update checked state without emitting panelToggled."""
        if self._active and self._active in self._buttons:
            self._buttons[self._active].setChecked(False)
        self._active = panel_id
        self._buttons[panel_id].setChecked(True)

    # ---- internals --------------------------------------------------------

    def _activate_without_collapse(self, panel_id: str) -> None:
        """Set panel as active (checked) without allowing collapse."""
        self.setActiveSilent(panel_id)
        self.panelToggled.emit(panel_id)

    def _on_clicked(self) -> None:
        panel_id = self.sender().objectName()
        self._toggle(panel_id)

    def _toggle(self, panel_id: str) -> None:
        if self._active == panel_id:
            if not self._collapsible:
                self._buttons[panel_id].setChecked(True)
                return
            self._buttons[panel_id].setChecked(False)
            self._active = None
            self.panelToggled.emit("")
        else:
            if self._active and self._active in self._buttons:
                self._buttons[self._active].setChecked(False)
            self._active = panel_id
            self._buttons[panel_id].setChecked(True)
            self.panelToggled.emit(panel_id)
