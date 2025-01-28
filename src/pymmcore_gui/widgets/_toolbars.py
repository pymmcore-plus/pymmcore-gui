from __future__ import annotations

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets import ShuttersWidget
from PyQt6.QtWidgets import QToolBar, QWidget


class OCToolBar(QToolBar):
    """A toolbar that allows selection of current channel.

    e.g:
    | DAPI | FITC | Cy5 |
    """

    def __init__(self, mmc: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__("Optical Configs", parent)
        self.mmc = mmc
        mmc.events.systemConfigurationLoaded.connect(self._refresh)
        mmc.events.configGroupChanged.connect(self._refresh)
        mmc.events.channelGroupChanged.connect(self._refresh)
        mmc.events.configSet.connect(self._on_config_set)

        self._refresh()

    def _on_config_set(self, group: str, config: str) -> None:
        if group == self.mmc.getChannelGroup():
            for action in self.actions():
                action.setChecked(action.text() == config)

    def _refresh(self) -> None:
        """Clear and refresh with all settings in current channel group."""
        self.clear()
        mmc = self.mmc
        if not (ch_group := mmc.getChannelGroup()):
            return

        current = mmc.getCurrentConfig(ch_group)
        for preset_name in mmc.getAvailableConfigs(ch_group):
            if not (action := self.addAction(preset_name)):
                continue
            action.setCheckable(True)
            action.setChecked(preset_name == current)

            @action.triggered.connect
            def _(checked: bool, pname: str = preset_name) -> None:
                mmc.setConfig(ch_group, pname)


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
        self._clear()
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
            s = ShuttersWidget(shutter, autoshutter=idx == len(shutters_devs) - 1)
            s.button_text_open = shutter
            s.button_text_closed = shutter
            # s.icon_color_open = ()
            # s.icon_color_closed = ()
            self.addWidget(s)

    def _clear(self) -> None:
        """Delete toolbar action."""
        while self.actions():
            action = self.actions()[0]
            self.removeAction(action)
