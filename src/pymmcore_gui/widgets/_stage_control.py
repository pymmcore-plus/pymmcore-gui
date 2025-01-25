from __future__ import annotations

from itertools import chain
from typing import cast

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets import StageWidget
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

STAGE_DEVICES = {DeviceType.Stage, DeviceType.XYStage}


class _Group(QGroupBox):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(name, parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class StagesControlWidget(QWidget):
    """A widget to control all the XY and Z loaded stages."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(5)

        self._on_cfg_loaded()

    def _on_cfg_loaded(self) -> None:
        self._clear()

        stages = chain(
            self._mmc.getLoadedDevicesOfType(DeviceType.XYStage),  # pyright: ignore [reportArgumentType]
            self._mmc.getLoadedDevicesOfType(DeviceType.Stage),  # pyright: ignore [reportArgumentType]
        )
        for idx, stage_dev in enumerate(stages):
            bx = _Group(stage_dev, self)
            stage = StageWidget(device=stage_dev, parent=bx)
            cast(QHBoxLayout, bx.layout()).addWidget(stage)
            self._layout.addWidget(bx, idx // 2, idx % 2)
        self.resize(self.sizeHint())

    def _clear(self) -> None:
        while self._layout.count():
            if (item := self._layout.takeAt(0)) and (widget := item.widget()):
                widget.setParent(self)
                widget.deleteLater()
