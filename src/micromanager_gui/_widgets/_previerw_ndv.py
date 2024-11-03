from __future__ import annotations

from typing import TYPE_CHECKING, Any, Hashable, Mapping

import tensorstore as ts
from ndv import DataWrapper, NDViewer
from pymmcore_plus import CMMCorePlus
from qtpy import QtCore
from superqt.utils import ensure_main_thread

from ._snap_live_buttons import BTN_SIZE, ICON_SIZE, Live, SaveButton, Snap

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtGui import QCloseEvent


def _data_type(mmc: CMMCorePlus) -> ts.dtype:
    px_type = mmc.getBytesPerPixel()
    if px_type == 1:
        return ts.uint8
    elif px_type == 2:
        return ts.uint16
    elif px_type == 4:
        return ts.uint32
    else:
        raise Exception(f"Unsupported Pixel Type: {px_type}")


class Preview(NDViewer):
    """An NDViewer subclass tailored to active data viewing."""

    def __init__(self, mmc: CMMCorePlus | None = None) -> None:
        super().__init__(data=None)
        self.setWindowTitle("Preview")
        self.live_view: bool = False
        self._mmc = mmc if mmc is not None else CMMCorePlus.instance()

        # BUTTONS
        self._btns.setSpacing(5)
        self._channel_mode_btn.hide()
        self._ndims_btn.hide()
        self._set_range_btn.setIconSize(ICON_SIZE)
        self._set_range_btn.setFixedWidth(BTN_SIZE)
        self._btns.insertWidget(2, Snap(mmcore=self._mmc))
        self._btns.insertWidget(3, Live(mmcore=self._mmc))
        self.save_btn = SaveButton(mmcore=self._mmc, viewer=self)
        self._btns.insertWidget(4, self.save_btn)

        # Create initial buffer
        self.ts_array = None
        self.ts_shape = (0, 0)
        self.bytes_per_pixel = 0

        # Connections
        ev = self._mmc.events
        ev.imageSnapped.connect(self._handle_snap)
        ev.continuousSequenceAcquisitionStarted.connect(self._start_live_viewer)
        ev.sequenceAcquisitionStopped.connect(self._stop_live_viewer)

    # # Begin TODO: Remove once https://github.com/pyapp-kit/ndv/issues/39 solved

    def _update_datastore(self) -> Any:
        if (
            self.ts_array is None
            or self.ts_shape[0] != self._mmc.getImageHeight()
            or self.ts_shape[1] != self._mmc.getImageWidth()
            or self.bytes_per_pixel != self._mmc.getBytesPerPixel()
        ):
            self.ts_shape = (self._mmc.getImageHeight(), self._mmc.getImageWidth())
            self.bytes_per_pixel = self._mmc.getBytesPerPixel()
            self.ts_array = ts.open(
                {"driver": "zarr", "kvstore": {"driver": "memory"}},
                create=True,
                shape=self.ts_shape,
                dtype=_data_type(self._mmc),
            ).result()
            super().set_data(self.ts_array)
        return self.ts_array

    def set_data(
        self,
        data: DataWrapper[Any] | Any,
        *,
        initial_index: Mapping[Hashable, int | slice] | None = None,
    ) -> None:
        if initial_index is None:
            initial_index = {}
        array = self._update_datastore()
        array[:] = data
        self.set_current_index(initial_index)

    # # End TODO: Remove once https://github.com/pyapp-kit/ndv/issues/39 solved

    # -- SNAP VIEWER -- #

    @ensure_main_thread  # type: ignore
    def _handle_snap(self) -> None:
        if self._mmc.mda.is_running():
            # This signal is emitted during MDAs as well - we want to ignore those.
            return
        self.set_data(self._mmc.getImage())

    # -- LIVE VIEWER -- #

    @ensure_main_thread  # type: ignore
    def _start_live_viewer(self) -> None:
        self.live_view = True

        # Start timer to update live viewer
        interval = int(self._mmc.getExposure())
        self._live_timer_id = self.startTimer(
            interval, QtCore.Qt.TimerType.PreciseTimer
        )

    def _stop_live_viewer(self, cameraLabel: str) -> None:
        # Pause live viewer, but leave it open.
        if self.live_view:
            self.live_view = False
            self.killTimer(self._live_timer_id)
            self._live_timer_id = None

    def _update_viewer(self, data: np.ndarray | None = None) -> None:
        """Update viewer with the latest image from the circular buffer."""
        if data is None:
            if self._mmc.getRemainingImageCount() == 0:
                return
            try:
                self.set_data(self._mmc.getLastImage())
            except (RuntimeError, IndexError):
                # circular buffer empty
                return

    def timerEvent(self, a0: QtCore.QTimerEvent | None) -> None:
        """Handles TimerEvents."""
        # Handle the timer event by updating the viewer (on gui thread)
        self._update_viewer()

    # -- HELPERS -- #

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self._mmc.stopSequenceAcquisition()
        super().closeEvent(event)
