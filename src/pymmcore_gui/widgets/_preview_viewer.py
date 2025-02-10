from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import ndv
from ndv.models._data_wrapper import ArrayLikeWrapper
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QObject, Qt, QTimerEvent

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtWidgets import QWidget


class PreviewDataWrapper(ArrayLikeWrapper):
    """Override the data wrapper to add a setter for the data."""

    def __init__(self, data: Any) -> None:
        super().__init__(data)

    @property
    def data(self) -> Any:
        return self._data

    @data.setter
    def data(self, data: Any) -> None:
        print("setting data")
        self._data = data


class LivePreview(QObject):
    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # timer id for live preview
        self._live_timer_id: int | None = None

        # used to avoid starting live view when the exposure or configuration is changed
        # and ContinuousSequenceAcquisition is not running (see _restart_live)
        self._live_view: bool = False

        # keep track of whether mda is running in a robust way
        self._mda_running: bool = False

        self._viewer = ndv.ArrayViewer()
        self._viewer.show()

        # core connections
        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_snap)
        ev.continuousSequenceAcquisitionStarted.connect(self._start_live_viewer)
        ev.sequenceAcquisitionStopped.connect(self._stop_live_viewer)
        ev.exposureChanged.connect(self._restart_live)
        ev.configSet.connect(self._restart_live)

        # mda connections
        ev_mda = self._mmc.mda.events
        ev_mda.sequenceStarted.connect(lambda: setattr(self, "_mda_running", True))
        ev_mda.sequenceFinished.connect(lambda: setattr(self, "_mda_running", False))

    @property
    def viewer(self) -> ndv.ArrayViewer:
        return self._viewer

    def _setData(self, data: Any) -> None:
        """Set the data to be displayed."""
        if data is None:
            return
        elif self._viewer._data_model.data_wrapper is not None:
            wrapper = cast(PreviewDataWrapper, self._viewer._data_model.data_wrapper)
            wrapper.data = data
            # TODO: change this
            self._viewer._clear_canvas()
            self._viewer._request_data()
        else:
            self._viewer._data_model.data_wrapper = PreviewDataWrapper(data)
            self._viewer._fully_synchronize_view()

    def _on_snap(self) -> None:
        """Update the viewer when an image is snapped."""
        if self._mda_running:
            return
        self._setData(self._mmc.getImage())

    def _start_live_viewer(self) -> None:
        """Start the live viewer."""
        self._live_view = True
        interval = int(self._mmc.getExposure())
        self._live_timer_id = self.startTimer(interval, Qt.TimerType.PreciseTimer)

    def _stop_live_viewer(self, cameraLabel: str) -> None:
        """Stop the live viewer."""
        if self._live_view and self._live_timer_id is not None:
            self._live_view = False
            self.killTimer(self._live_timer_id)
            self._live_timer_id = None

    def _update_live_viewer(self, data: np.ndarray | None = None) -> None:
        """Update the live viewer with the latest image from the circular buffer."""
        if data is None:
            if self._mmc.getRemainingImageCount() == 0:
                return
            try:
                self._setData(self._mmc.getLastImage())
            except (RuntimeError, IndexError):
                # circular buffer empty
                return
        self._setData(data)

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        """Handle the timer event by updating the viewer (on gui thread)."""
        self._update_live_viewer()

    def _restart_live(self, exposure: float) -> None:
        """Restart live view with new exposure or new configuration is set."""
        if not self._live_view:
            return
        self._mmc.stopSequenceAcquisition()
        self._mmc.startContinuousSequenceAcquisition()
