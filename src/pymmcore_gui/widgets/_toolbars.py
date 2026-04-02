from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets import ShuttersWidget

from pymmcore_gui._qt.Qlementine import SegmentedControl
from pymmcore_gui._qt.QtCore import QSize
from pymmcore_gui._qt.QtWidgets import QToolBar, QWidget, QWidgetAction
from pymmcore_gui.actions import CoreAction
from pymmcore_gui.widgets._exposure import ExposureWidget

if TYPE_CHECKING:
    from pymmcore_gui._main_window import MicroManagerGUI


class CameraControlToolbar(QToolBar):
    """Toolbar with snap, live, and exposure controls."""

    def __init__(self, mmc: CMMCorePlus, parent: MicroManagerGUI) -> None:
        super().__init__("Camera Actions", parent)
        self.setIconSize(QSize(32, 32))
        self.addAction(parent.get_action(CoreAction.SNAP))
        self.addAction(parent.get_action(CoreAction.TOGGLE_LIVE))
        self.addWidget(ExposureWidget(parent=self, mmcore=mmc))


class OCToolBar(QToolBar):
    """A toolbar that allows selection of current channel.

    e.g:
    | DAPI | FITC | Cy5 |
    """

    def __init__(self, mmc: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__("Optical Configs", parent)
        self.mmc = mmc
        self._seg = SegmentedControl()
        self._seg.currentIndexChanged.connect(self._on_seg_changed)  # pyright: ignore[reportAttributeAccessIssue]
        self.addWidget(self._seg)

        mmc.events.systemConfigurationLoaded.connect(self._refresh)
        mmc.events.configGroupChanged.connect(self._refresh)
        mmc.events.channelGroupChanged.connect(self._refresh)
        mmc.events.configSet.connect(self._on_config_set)
        mmc.events.propertyChanged.connect(self._on_property_changed)
        mmc.events.configDefined.connect(self._refresh)
        mmc.events.configDeleted.connect(self._refresh)
        self._refresh()

    def _on_seg_changed(self) -> None:
        """Apply the selected config when the segment changes."""
        if preset := self._seg.currentData():
            if ch_group := self.mmc.getChannelGroup():
                self.mmc.setConfig(ch_group, preset)

    def _on_config_set(self, group: str, config: str) -> None:
        """Update the selected segment when a config is set externally."""
        if group == self.mmc.getChannelGroup():
            idx = self._seg.findItemIndex(config)
            if idx >= 0:
                self._seg.setCurrentIndex(idx)

    def _on_property_changed(self, device: str, property: str, value: str) -> None:
        """Refresh the widget when the ChannelGroup property is changed."""
        if device == "Core" and property == "ChannelGroup":
            self._refresh()

    def _refresh(self) -> None:
        """Clear and refresh with all settings in current channel group."""
        self._seg.currentIndexChanged.disconnect(self._on_seg_changed)  # pyright: ignore[reportAttributeAccessIssue]
        try:
            while self._seg.itemCount() > 0:
                self._seg.removeItem(0)

            mmc = self.mmc
            if not (ch_group := mmc.getChannelGroup()):
                return

            current = mmc.getCurrentConfig(ch_group)
            current_idx = 0
            for preset_name in mmc.getAvailableConfigs(ch_group):
                idx = self._seg.addItem(preset_name, itemData=preset_name)
                if preset_name == current:
                    current_idx = idx
            if self._seg.itemCount() > 0:
                self._seg.setCurrentIndex(current_idx)
        finally:
            self._seg.currentIndexChanged.connect(self._on_seg_changed)  # pyright: ignore[reportAttributeAccessIssue]


class ShuttersToolbar(QToolBar):
    """A QToolBar for the loased Shutters."""

    def __init__(
        self,
        mmc: CMMCorePlus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Shutters", parent)
        self.mmc = mmc
        self.mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)
        self._on_cfg_loaded()

    def _on_cfg_loaded(self) -> None:
        # delete current actions if any
        self._clear_shutter_toolbar()

        shutters = self.mmc.getLoadedDevicesOfType(DeviceType.ShutterDevice)  # pyright: ignore [reportArgumentType]
        if not shutters:
            return

        shutters_devs = sorted(
            shutters,
            key=lambda d: any(
                "Physical Shutter" in x for x in self.mmc.getDevicePropertyNames(d)
            ),
            reverse=True,
        )

        for idx, shutter in enumerate(shutters_devs):
            s = ShuttersWidget(
                shutter,
                button_text_open=shutter,
                button_text_closed=shutter,
                autoshutter=idx == len(shutters_devs) - 1,
            )
            self.addWidget(s)

    def _clear_shutter_toolbar(self) -> None:
        """Delete all actions in the toolbar."""
        while self.actions():
            action = cast("QWidgetAction", self.actions()[0])
            # get the shutter widget associated with the action and delete it
            widget = action.defaultWidget()
            if widget is not None:
                widget.deleteLater()
            self.removeAction(action)
