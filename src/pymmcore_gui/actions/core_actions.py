"""Define actions that act on the global CMMCore instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from superqt import QIconifyIcon

from ._action_info import ActionInfo, ActionKey

if TYPE_CHECKING:
    from ._core_qaction import QCoreAction


class CoreAction(ActionKey):
    """Actions that act on the global CMMCore instance."""

    SNAP = "Snap Image"
    TOGGLE_LIVE = "Toggle Live"


# ######################## Functions acting on the Core #########################


# TODO: perhaps have alternate signatures for these functions that take a
# CMMCorePlus instance, rather than needing to extract it from the QCoreAction.
def snap_image(action: QCoreAction, checked: bool) -> None:
    """Snap an image, stopping sequence if running."""
    mmc = action.mmc
    if mmc.isSequenceRunning():
        mmc.stopSequenceAcquisition()
    mmc.snapImage()


def toggle_live(action: QCoreAction, checked: bool) -> None:
    """Start or stop live mode."""
    mmc = action.mmc
    if mmc.isSequenceRunning():
        mmc.stopSequenceAcquisition()
    else:
        mmc.startContinuousSequenceAcquisition(0)


def _init_toggle_live(action: QCoreAction) -> None:
    mmc = action.mmc

    def _on_change() -> None:
        _is_running = mmc.isSequenceRunning()
        action.setChecked(_is_running)
        _icon = "mdi:video-off-outline" if _is_running else "mdi:video-outline"
        action.setIcon(QIconifyIcon(_icon))

    mmc.events.sequenceAcquisitionStarted.connect(_on_change)
    mmc.events.continuousSequenceAcquisitionStarted.connect(_on_change)
    mmc.events.sequenceAcquisitionStopped.connect(_on_change)


# ########################## Action Info Instances #############################

snap_action = ActionInfo(
    key=CoreAction.SNAP,
    shortcut="Ctrl+K",
    auto_repeat=True,
    icon="mdi:camera-outline",
    on_triggered=snap_image,
)


toggle_live_action = ActionInfo(
    key=CoreAction.TOGGLE_LIVE,
    shortcut="Ctrl+L",
    auto_repeat=True,
    icon="mdi:video-outline",
    checkable=True,
    on_triggered=toggle_live,
    on_created=_init_toggle_live,
)
