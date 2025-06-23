"""Defines actions that act on the global CMMCore instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._action_info import ActionInfo, ActionKey

if TYPE_CHECKING:
    from ._core_qaction import QCoreAction


# ######################## Functions acting on the Core #########################
class CoreAction(ActionKey):
    """Actions that act on the global CMMCore instance."""

    SNAP = "pymmcore_gui.snap_image"
    TOGGLE_LIVE = "pymmcore_gui.toggle_live"
    LOAD_DEMO = "pymmcore_gui.load_demo_config"
    LOAD_CONFIG = "pymmcore_gui.load_config"
    SAVE_CONFIG = "pymmcore_gui.save_config"


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


def _init_snap_image(action: QCoreAction) -> None:
    mmc = action.mmc

    def _on_load() -> None:
        action.setEnabled(bool(mmc.getCameraDevice()))

    mmc.events.systemConfigurationLoaded.connect(_on_load)

    _on_load()


def _init_toggle_live(action: QCoreAction) -> None:
    mmc = action.mmc

    def _on_load() -> None:
        action.setEnabled(bool(mmc.getCameraDevice()))

    mmc.events.systemConfigurationLoaded.connect(_on_load)

    def _on_change() -> None:
        action.setChecked(mmc.isSequenceRunning())

    mmc.events.sequenceAcquisitionStarted.connect(_on_change)
    mmc.events.continuousSequenceAcquisitionStarted.connect(_on_change)
    mmc.events.sequenceAcquisitionStopped.connect(_on_change)

    _on_load()


def load_demo_config(action: QCoreAction, checked: bool) -> None:
    """Load the demo configuration."""
    action.mmc.loadSystemConfiguration()


def load_sys_config_dialog(action: QCoreAction, checked: bool) -> None:
    """Open a dialog to load a system configuration."""
    from qtpy.QtWidgets import QFileDialog

    (path, _filter) = QFileDialog.getOpenFileName(
        None,
        "Select a Micro-Manager configuration file",
        "",
        "cfg(*.cfg)",
    )
    if path:
        action.mmc.loadSystemConfiguration(path)


def save_sys_config_dialog(action: QCoreAction, checked: bool) -> None:
    """Open a dialog to save a system configuration."""
    from qtpy.QtWidgets import QFileDialog

    (path, _filter) = QFileDialog.getSaveFileName(
        None,
        "Save Micro-Manager configuration file",
        "",
        "cfg(*.cfg)",
    )
    if path:
        action.mmc.saveSystemConfiguration(path)


# ########################## Action Info Instances #############################


snap_action = ActionInfo(
    key=CoreAction.SNAP,
    text="Snap Image",
    shortcut="Ctrl+K",
    auto_repeat=True,
    icon="mdi-light:camera",
    on_triggered=snap_image,
    on_created=_init_snap_image,
)


toggle_live_action = ActionInfo(
    key=CoreAction.TOGGLE_LIVE,
    text="Toggle Live",
    shortcut="Ctrl+L",
    auto_repeat=True,
    icon="mdi:video-outline",
    checkable=True,
    on_triggered=toggle_live,
    on_created=_init_toggle_live,
)

load_demo_action = ActionInfo(
    key=CoreAction.LOAD_DEMO,
    text="Load Demo Configuration",
    on_triggered=load_demo_config,
)

load_config_action = ActionInfo(
    key="pymmcore_gui.load_config",
    text="Load System Configuration...",
    on_triggered=load_sys_config_dialog,
)

load_config_action = ActionInfo(
    key="pymmcore_gui.save_config",
    text="Save System Configuration...",
    on_triggered=save_sys_config_dialog,
)
