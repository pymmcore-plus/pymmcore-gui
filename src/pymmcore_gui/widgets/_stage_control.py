from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets import StageWidget

from pymmcore_gui._qt.Qlementine import SegmentedControl  # type: ignore[attr-defined]
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pymmcore_gui.widgets._joystick import StageDPad, StageJoystick

if TYPE_CHECKING:
    from qtpy.QtGui import QWheelEvent

STAGE_DEVICES = {DeviceType.Stage, DeviceType.XYStage}


class _StageWidget(StageWidget):
    """Stage control widget with wheel event for z-axis control."""

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None:
            return
        delta = event.angleDelta().y()
        increment = self._step.value()
        # Use StageWidget's move helpers: build a relative move value and
        # delegate to the existing _do_move implementation.
        if delta > 0:
            val = (0.0, increment) if getattr(self, "_is_2axis", False) else increment
            self._do_move(val, relative=True)
        elif delta < 0:
            val = (0.0, -increment) if getattr(self, "_is_2axis", False) else -increment
            self._do_move(val, relative=True)
        super().wheelEvent(event)


class StagesControlWidget(QWidget):
    """A widget to control all the XY and Z loaded stages."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(2)

        self._on_cfg_loaded()

    def _on_cfg_loaded(self) -> None:
        self._clear()

        if current_xy := self._mmc.getXYStageDevice():
            widget = _XYWrapper(
                xy_device=current_xy,
                parent=self,
                mmcore=self._mmc,
            )
            self._layout.addWidget(widget)

        if current_xy := self._mmc.getFocusDevice():
            stage = _StageWidget(device=current_xy, parent=self, mmcore=self._mmc)
            self._layout.addWidget(stage)
        self.resize(self.sizeHint())

    def _clear(self) -> None:
        while self._layout.count():
            if (item := self._layout.takeAt(0)) and (widget := item.widget()):
                widget.setParent(self)
                widget.deleteLater()


class _XYWrapper(QWidget):
    """XY stage wrapper with Joystick / D-Pad mode switcher."""

    def __init__(
        self,
        xy_device: str,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._mode_tabs = SegmentedControl()
        self._mode_tabs.addItem("Joystick")
        self._mode_tabs.addItem("D-Pad")
        layout.addWidget(self._mode_tabs)

        self._stack = QStackedWidget(self)
        joystick = StageJoystick(xy_device=xy_device, parent=self, mmcore=mmcore)
        dpad = StageDPad(xy_device=xy_device, parent=self, mmcore=mmcore)
        self._stack.addWidget(joystick)
        self._stack.addWidget(dpad)
        layout.addWidget(self._stack)

        self._mode_tabs.currentIndexChanged.connect(  # pyright: ignore[reportAttributeAccessIssue]
            lambda: self._stack.setCurrentIndex(self._mode_tabs.currentIndex())
        )
