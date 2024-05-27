from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QToolBar, QWidget

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
