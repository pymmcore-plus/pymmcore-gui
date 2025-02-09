from __future__ import annotations

from typing import TYPE_CHECKING

import ndv
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QObject, Qt, QTimerEvent
from superqt.utils import ensure_main_thread

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtWidgets import QWidget


class LivePreview(QObject):
    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # timer id for live preview
        self._live_timer_id: int | None = None

        self.live_view: bool = False

        self._viewer = ndv.ArrayViewer()
        self._viewer.show()

        # connections
        ev = self._mmc.events
        ev.imageSnapped.connect(self._handle_snap)
        ev.continuousSequenceAcquisitionStarted.connect(self._start_live_viewer)
        ev.sequenceAcquisitionStopped.connect(self._stop_live_viewer)
        ev.exposureChanged.connect(self._restart_live)
        ev.configSet.connect(self._restart_live)

    @property
    def viewer(self) -> ndv.ArrayViewer:
        return self._viewer

    @ensure_main_thread
    def _handle_snap(self) -> None:
        if self._mmc.mda.is_running():
            return
        self._viewer.data = self._mmc.getImage()

    @ensure_main_thread
    def _start_live_viewer(self) -> None:
        """Start the live viewer."""
        self.live_view = True
        interval = int(self._mmc.getExposure())
        self._live_timer_id = self.startTimer(interval, Qt.TimerType.PreciseTimer)

    def _stop_live_viewer(self, cameraLabel: str) -> None:
        """Stop the live viewer."""
        if self.live_view and self._live_timer_id is not None:
            self.live_view = False
            self.killTimer(self._live_timer_id)
            self._live_timer_id = None

    def _update_viewer(self, data: np.ndarray | None = None) -> None:
        """Update viewer with the latest image from the circular buffer."""
        if data is None:
            if self._mmc.getRemainingImageCount() == 0:
                return
            try:
                self._viewer.data = self._mmc.getLastImage()
            except (RuntimeError, IndexError):
                # circular buffer empty
                return
        self._viewer.data = data

    def _restart_live(self, exposure: float) -> None:
        """Restart live view with new exposure settings."""
        if not self.live_view:
            return
        self._mmc.stopSequenceAcquisition()
        self._mmc.startContinuousSequenceAcquisition()

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        """Handle the timer event by updating the viewer (on gui thread)."""
        self._update_viewer()
