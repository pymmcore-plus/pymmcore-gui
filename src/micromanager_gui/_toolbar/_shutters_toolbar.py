from __future__ import annotations

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets import ShuttersWidget
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QToolBar, QWidget


class _ShuttersToolbar(QToolBar):
    """A QToolBar for the loased Shutters."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Shutters ToolBar", parent)

        self.setObjectName("Shutters ToolBar")

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)
        self._on_cfg_loaded()

    def _on_cfg_loaded(self) -> None:
        self._clear()

        if not self._mmc.getLoadedDevicesOfType(DeviceType.ShutterDevice):
            # FIXME:
            # ShuttersWidget has not been tested with an empty device label...
            # it raises all sorts of errors.
            # if we want to have a "placeholder" widget, it needs more testing.

            # empty_shutter = ShuttersWidget("")
            # self.layout().addWidget(empty_shutter)
            return

        shutters_devs = list(self._mmc.getLoadedDevicesOfType(DeviceType.ShutterDevice))
        for d in shutters_devs:
            props = self._mmc.getDevicePropertyNames(d)
            if bool([x for x in props if "Physical Shutter" in x]):
                shutters_devs.remove(d)
                shutters_devs.insert(0, d)

        for idx, shutter in enumerate(shutters_devs):
            if idx == len(shutters_devs) - 1:
                s = ShuttersWidget(shutter)
            else:
                s = ShuttersWidget(shutter, autoshutter=False)
            s.button_text_open = shutter
            s.button_text_closed = shutter
            s.icon_color_open = ()
            s.icon_color_closed = ()
            self.addWidget(s)

    def _clear(self) -> None:
        """Delete toolbar action."""
        while self.actions():
            action = self.actions()[0]
            self.removeAction(action)
