from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import ndv
import numpy as np
from ndv import DataWrapper
from ndv.controllers._channel_controller import ChannelController
from ndv.models import LUTModel
from ndv.views import _app

if TYPE_CHECKING:
    from concurrent.futures import Future

    from ndv.models._data_display_model import DataResponse


__all__ = ["ArrayViewer", "DataWrapper"]


class ArrayViewer(ndv.ArrayViewer):
    # this whole thing is just to comment out hist.set_range()
    @_app.ensure_main_thread
    def _on_data_response_ready(self, future: Future[DataResponse]) -> None:
        # NOTE: removing the reference to the last future here is important
        # because the future has a reference to this widget in its _done_callbacks
        # which will prevent the widget from being garbage collected if the future
        self._futures.discard(future)
        if not self._futures:
            self._viewer_model.show_progress_spinner = False

        if future.cancelled():
            return

        try:
            response = future.result()
        except Exception as e:
            warnings.warn(f"Error fetching data: {e}", stacklevel=2)
            return

        display_model = self._data_model.display
        for key, data in response.data.items():
            if (lut_ctrl := self._lut_controllers.get(key)) is None:
                if key is None:
                    model = display_model.default_lut
                elif key in display_model.luts:
                    model = display_model.luts[key]
                else:
                    # we received a new channel key that has not been set in the model
                    # so we create a new LUT model for it
                    model = display_model.luts[key] = LUTModel()

                lut_views = [self._view.add_lut_view(key)]
                if hist := self._histograms.get(key, None):
                    lut_views.append(hist)
                self._lut_controllers[key] = lut_ctrl = ChannelController(
                    key=key,
                    lut_model=model,
                    views=lut_views,
                )

            if not lut_ctrl.handles:
                # we don't yet have any handles for this channel
                if response.n_visible_axes == 2:
                    handle = self._canvas.add_image(data)
                    lut_ctrl.add_handle(handle)
                elif response.n_visible_axes == 3:
                    handle = self._canvas.add_volume(data)
                    lut_ctrl.add_handle(handle)

            else:
                lut_ctrl.update_texture_data(data)

            if hist := self._histograms.get(key, None):
                # TODO: once data comes in in chunks, we'll need a proper stateful
                # stats object that calculates the histogram incrementally
                counts, bin_edges = _calc_hist_bins(data)
                # FIXME: currently this is updating the histogram on *any*
                # channel index... so it doesn't work with composite mode
                hist.set_data(counts, bin_edges)
                # hist.set_range()

        self._canvas.refresh()


def _calc_hist_bins(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    maxval = np.iinfo(data.dtype).max
    counts = np.bincount(data.flatten(), minlength=maxval + 1)
    bin_edges = np.arange(maxval + 2) - 0.5
    return counts, bin_edges
