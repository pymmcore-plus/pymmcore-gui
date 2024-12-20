from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pymmcore_plus import CMMCorePlus
from PyQt6.QtGui import QAction, QIcon
from superqt import QIconifyIcon
from zmq import Enum

from . import _core_functions as cf
from ._action_info import ActionInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from PyQt6.QtCore import QObject

    from ._core_functions import CoreFunc


# -------------------------- QCoreAction ------------------------------


class QInfoAction(QAction):
    def apply_info(self, info: ActionInfo) -> None:
        """Apply settings from a `CoreActionInfo` object to the QAction."""
        if info.key:
            self.setText(info.key)

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
                icon: QIcon = QIconifyIcon(info.icon)
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


class QCoreAction(QInfoAction):
    """QAction that can act on a CMMCorePlus instance."""

    def __init__(
        self,
        mmc: CMMCorePlus | None = None,
        parent: QObject | None = None,
        info: CoreActionInfo | None = None,
    ) -> None:
        super().__init__(parent)
        self.mmc = mmc or CMMCorePlus.instance()
        self._triggered_callback: CoreFunc | None = None
        self.triggered.connect(self._on_triggered)
        if info is not None:
            self.apply_info(info)

    def apply_info(self, info: CoreActionInfo) -> None:
        """Apply settings from a `CoreActionInfo` object to the QAction."""
        super().apply_info(info)
        self._triggered_callback = info.on_triggered

        if info.on_created is not None:
            info.on_created(self, self.mmc)

    def _on_triggered(self, checked: bool) -> None:
        if self._triggered_callback is not None:
            self._triggered_callback(self.mmc)


# -------------------------- CoreActionInfo ------------------------------


@dataclass
class CoreActionInfo(ActionInfo):
    """Information for creating a QCoreAction."""

    key: CoreAction

    # called when triggered
    on_triggered: CoreFunc | None = None
    # called when QAction is created, can be used to connect stuff
    on_created: Callable[[QCoreAction, CMMCorePlus], Any] | None = None

    def mark_on_created(
        self, f: Callable[[QCoreAction, CMMCorePlus], Any]
    ) -> Callable[[QCoreAction, CMMCorePlus], Any]:
        """Decorator to mark a function to call when the QAction is created."""
        self.on_created = f
        return f

    def to_qaction(
        self, mmc: CMMCorePlus | None = None, parent: QObject | None = None
    ) -> QCoreAction:
        """Create a QCoreAction from this info."""
        return QCoreAction(mmc, parent, info=self)


# ------------------------------ Registry of Actions ------------------------


class CoreAction(str, Enum):
    """A registry of core actions."""

    SNAP = "Snap Image"
    TOGGLE_LIVE = "Toggle Live"

    def __str__(self) -> str:
        """Return value as the string representation."""
        return str(self.value)


snap_action = CoreActionInfo(
    key=CoreAction.SNAP,
    shortcut="Ctrl+K",
    auto_repeat=True,
    icon="mdi-light:camera",
    on_triggered=cf.snap_image,
)


live_action = CoreActionInfo(
    key=CoreAction.TOGGLE_LIVE,
    shortcut="Ctrl+L",
    auto_repeat=True,
    icon="mdi:video-outline",
    on_triggered=cf.toggle_live,
    checkable=True,
)


@live_action.mark_on_created
def _(action: QCoreAction, mmc: CMMCorePlus) -> None:
    def _on_change() -> None:
        action.setChecked(mmc.isSequenceRunning())

    mmc.events.sequenceAcquisitionStarted.connect(_on_change)
    mmc.events.continuousSequenceAcquisitionStarted.connect(_on_change)
    mmc.events.sequenceAcquisitionStopped.connect(_on_change)


# just gather up all the CoreActionInfos we declared in this module
CORE_ACTIONS = {
    act.key: act for act in globals().values() if isinstance(act, CoreActionInfo)
}
