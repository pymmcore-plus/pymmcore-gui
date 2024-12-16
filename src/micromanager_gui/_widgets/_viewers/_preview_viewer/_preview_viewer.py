from __future__ import annotations

from typing import TYPE_CHECKING, Any, Hashable, Mapping, cast

import tensorstore as ts
from ndv import DataWrapper, NDViewer
from ndv.viewer._backends._vispy import VispyViewerCanvas
from pymmcore_plus import CMMCorePlus, Metadata
from qtpy import QtCore
from superqt.utils import ensure_main_thread

from micromanager_gui._widgets._snap_live_buttons import Live, Snap

from ._preview_save_button import SaveButton

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtGui import QCloseEvent
    from qtpy.QtWidgets import QWidget


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

    # based on: https://github.com/gselzer/pymmcore-plus-sandbox/blob/53ac7e8ca3b4874816583b8b74024a75432b8fc9/src/pymmcore_plus_sandbox/_viewfinder.py#L154-L211

    def __init__(
        self, mmcore: CMMCorePlus | None = None, parent: QWidget | None = None
    ):
        super().__init__(data=None, parent=parent)
        self.setWindowTitle("Preview")
        self.live_view: bool = False
        self._meta: Metadata | dict = {}
        self._mmc = mmcore if mmcore is not None else CMMCorePlus.instance()

        # custom buttons
        # hide the channel mode and ndims buttons
        self._channel_mode_btn.hide()
        self._ndims_btn.hide()

        # snap and live buttons
        snap_btn = Snap(mmcore=self._mmc)
        live_btn = Live(mmcore=self._mmc)
        icon_size = self._set_range_btn.iconSize()
        btn_size = self._set_range_btn.sizeHint().width()
        snap_btn.setIconSize(icon_size)
        snap_btn.setFixedWidth(btn_size)
        live_btn.setIconSize(icon_size)
        live_btn.setFixedWidth(btn_size)

        # save button
        self.save_btn = SaveButton(mmcore=self._mmc, viewer=self)

        self._btns.insertWidget(1, snap_btn)
        self._btns.insertWidget(2, live_btn)
        self._btns.insertWidget(3, self.save_btn)

        # create initial buffer
        self.ts_array = None
        self.ts_shape = (0, 0)
        self.bytes_per_pixel = 0

        # connections
        ev = self._mmc.events
        ev.imageSnapped.connect(self._handle_snap)
        ev.continuousSequenceAcquisitionStarted.connect(self._start_live_viewer)
        ev.sequenceAcquisitionStopped.connect(self._stop_live_viewer)

        self._mmc.events.exposureChanged.connect(self._restart_live)
        self._mmc.events.configSet.connect(self._restart_live)

    def image(self) -> Any:
        """Return the current image data."""
        return self.data.read().result()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self._mmc.stopSequenceAcquisition()
        super().closeEvent(event)

    # Begin TODO: Remove once https://github.com/pyapp-kit/ndv/issues/39 solved

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

            # this is a hack to update the canvas with the new image shape or the
            # set_range method will not work properly
            self._canvas = cast(VispyViewerCanvas, self._canvas)  # type: ignore
            if self._canvas._current_shape:
                self._canvas._current_shape = self.ts_shape

            super().set_data(self.ts_array)

            self._canvas.set_range()

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

    # End TODO: Remove once https://github.com/pyapp-kit/ndv/issues/39 solved

    # Snap -------------------------------------------------------------
    @ensure_main_thread  # type: ignore
    def _handle_snap(self) -> None:
        if self._mmc.mda.is_running():
            # This signal is emitted during MDAs as well - we want to ignore those.
            return
        img, meta = self._mmc.getTaggedImage()
        self.set_data(img)
        self._meta = meta

    # Live -------------------------------------------------------

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
            self._meta = self._mmc.getTags()

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

    def _restart_live(self, exposure: float) -> None:
        if not self.live_view:
            return
        self._mmc.stopSequenceAcquisition()
        self._mmc.startContinuousSequenceAcquisition()

    def timerEvent(self, a0: QtCore.QTimerEvent | None) -> None:
        """Handles TimerEvents."""
        # Handle the timer event by updating the viewer (on gui thread)
        self._update_viewer()
