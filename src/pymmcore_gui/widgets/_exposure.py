from __future__ import annotations

from contextlib import suppress

from pymmcore_plus import CMMCorePlus, Keyword
from superqt.utils import signals_blocked

from pymmcore_gui._qt.QtCore import Qt, Slot
from pymmcore_gui._qt.QtWidgets import QHBoxLayout, QSpinBox, QWidget


# Similar to the one in pymmcore-widgets... but simpler
class ExposureWidget(QWidget):
    """A Widget to get/set exposure on the current camera."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.spinBox = QSpinBox()
        self.spinBox.setSuffix(" ms")
        self.spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinBox.setMinimum(1)
        self.spinBox.setMaximum(9999)
        self.spinBox.setKeyboardTracking(False)
        layout = QHBoxLayout(self)
        layout.addWidget(self.spinBox)

        self._mmc.events.exposureChanged.connect(self._on_exp_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_load)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)
        self.spinBox.valueChanged.connect(self._on_spin_changed)

        self._on_load()

    @Slot()
    def _on_load(self) -> None:
        with signals_blocked(self.spinBox):
            if cam := self._mmc.getCameraDevice():
                self.spinBox.setValue(int(self._mmc.getExposure(cam)))
            self.setEnabled(bool(cam))

    @Slot(str, str, object)
    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        if device == self._mmc.getCameraDevice() and prop == Keyword.Exposure:
            with signals_blocked(self.spinBox):
                self.spinBox.setValue(int(float(value)))

    @Slot(str, float)
    def _on_exp_changed(self, camera: str, exposure: float) -> None:
        if camera == self._mmc.getCameraDevice():
            with signals_blocked(self.spinBox):
                self.spinBox.setValue(int(exposure))

    def _on_spin_changed(self, value: int) -> None:
        if cam := self._mmc.getCameraDevice():
            self._mmc.setExposure(cam, value)
            with suppress(Exception):
                self._mmc.setProperty(cam, "Exposure", str(value))
