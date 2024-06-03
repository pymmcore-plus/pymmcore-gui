from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import DefaultCameraExposureWidget
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QToolBar, QWidget

from micromanager_gui._widgets._snap_live_buttons import Live, Snap


class _SnapLive(QToolBar):
    """A QToolBar for the Snap and Live buttons."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Snap Live", parent)

        self.setObjectName("Snap Live")

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        self._mmc = mmcore or CMMCorePlus.instance()

        # snap button
        self._snap = Snap(mmcore=self._mmc)
        self._snap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addWidget(self._snap)

        # live button
        self._live = Live(mmcore=self._mmc)
        self._live.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addWidget(self._live)

        # camera exposure widget
        exp_wdg = QGroupBox()
        exp_wdg_layout = QHBoxLayout(exp_wdg)
        exp_wdg_layout.setContentsMargins(5, 0, 5, 0)
        exp_wdg_layout.setSpacing(0)
        exp = QLabel("Exposure:")
        self._exposure = DefaultCameraExposureWidget(mmcore=self._mmc)
        self._exposure.layout().setContentsMargins(0, 0, 0, 0)
        exp_wdg_layout.addWidget(exp)
        exp_wdg_layout.addWidget(self._exposure)
        self.addWidget(exp_wdg)
