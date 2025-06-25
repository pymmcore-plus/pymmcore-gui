from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from superqt import QIconifyIcon

from pymmcore_gui._qt.QtGui import QAction, QIcon, QPalette
from pymmcore_gui._qt.QtWidgets import QApplication

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

    from pymmcore_gui._qt.QtCore import QMetaObject, QObject

    from ._action_info import ActionInfo, ActionTriggeredFunc


class QCoreAction(QAction):
    """QAction that can act on a CMMCorePlus instance."""

    key: str

    def __init__(
        self,
        mmc: CMMCorePlus,
        info: ActionInfo | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.mmc = mmc
        self._triggered_callback: ActionTriggeredFunc | None = None
        # pyside6 is picky about not trying to disconnect an unconnected signal,
        # so we manually track the connection.
        self._triggered_connection: QMetaObject.Connection | None = None
        self.setMenuRole(QAction.MenuRole.NoRole)  # don't guess menu placement
        if info is not None:
            self.apply_info(info)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} for {self.key!r} at {id(self):#x}>"

    def apply_info(self, info: ActionInfo) -> None:
        """Apply settings from a `CoreActionInfo` object to the QAction."""
        self.key = info.key

        if not (text := info.text):
            text = info.key.value if isinstance(info.key, Enum) else info.key

        # Avoid mnemonics - use the shortcuts below instead.
        self.setText(text.replace("&", "&&"))
        if info.auto_repeat is not None:
            self.setAutoRepeat(info.auto_repeat)
        if info.checkable is not None:
            self.setCheckable(info.checkable)
        if info.checked is not None:
            self.setChecked(info.checked)
        if info.enabled is not None:
            self.setEnabled(info.enabled)
        if info.icon is not None:
            if isinstance(info.icon, str):
                color = QApplication.palette().color(QPalette.ColorRole.WindowText)
                icon: QIcon = QIconifyIcon(info.icon, color=color.name())
            else:
                icon = QIcon(info.icon)
            self.setIcon(icon)
        if info.icon_text is not None:
            self.setIconText(info.icon_text)
        if info.icon_visible_in_menu is not None:
            self.setIconVisibleInMenu(info.icon_visible_in_menu)
        if info.menu_role is not None:
            self.setMenuRole(info.menu_role)
        if info.priority is not None:
            self.setPriority(info.priority)
        if info.shortcut is not None:
            self.setShortcut(info.shortcut)
        if info.shortcut_context is not None:
            self.setShortcutContext(info.shortcut_context)
        if info.shortcut_visible_in_context_menu is not None:
            self.setShortcutVisibleInContextMenu(info.shortcut_visible_in_context_menu)
        if info.status_top is not None:
            self.setStatusTip(info.status_top)
        if info.tooltip is not None:
            self.setToolTip(info.tooltip)
        if info.visible is not None:
            self.setVisible(info.visible)
        if info.whats_this is not None:
            self.setWhatsThis(info.whats_this)

        self._triggered_callback = info.on_triggered
        if info.on_triggered is None:
            if self._triggered_connection is not None:
                self.triggered.disconnect(self._triggered_connection)
                self._triggered_connection = None
        else:
            self._triggered_connection = self.triggered.connect(self._on_triggered)

        if info.on_created is not None:
            info.on_created(self)

    def _on_triggered(self, checked: bool) -> None:
        if self._triggered_callback is not None:
            self._triggered_callback(self, checked)
