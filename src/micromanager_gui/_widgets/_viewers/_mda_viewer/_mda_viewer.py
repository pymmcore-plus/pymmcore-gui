from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from ndv import NDViewer
from pymmcore_plus.mda.handlers import OMEZarrWriter, TensorStoreHandler
from superqt import ensure_main_thread
from useq import MDAEvent

from micromanager_gui.readers import OMEZarrReader, TensorstoreZarrReader

from ._data_wrappers import MM5DWriterWrapper, MMTensorstoreWrapper
from ._mda_save_button import MDASaveButton

if TYPE_CHECKING:
    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
    from qtpy.QtWidgets import QWidget


class MDAViewer(NDViewer):
    """NDViewer specialized for pymmcore-plus MDA acquisitions."""

    from ._data_wrappers import MM5DWriterWrapper, MMTensorstoreWrapper

    def __init__(
        self,
        data: _5DWriterBase | TensorStoreHandler | None = None,
        *,
        parent: QWidget | None = None,
        **kwargs: Any,
    ):
        if data is None:
            data = TensorStoreHandler()

        # patch the frameReady method to call the superframeReady method
        # AFTER handling the event
        self._superframeReady = getattr(data, "frameReady", None)
        if callable(self._superframeReady):
            data.frameReady = self._patched_frame_ready  # type: ignore
        else:  # pragma: no cover
            warnings.warn(
                "MDAViewer: data does not have a frameReady method to patch, "
                "are you sure this is a valid data handler?",
                stacklevel=2,
            )

        super().__init__(data, parent=parent, channel_axis="c", **kwargs)

        # temporarily hide the ndims button since we don't yet support
        self._ndims_btn.hide()

        # add the save button only if using a TensorStoreHandler (and thus the
        # MMTensorstoreWrapper) or OMEZarrWriter (and thus the MM5DWriterWrapper)
        # since we didn't yet implement the save_as_zarr and save_as_tiff methods
        # for OMETiffWriter in the MM5DWriterWrapper.
        if isinstance(data, (TensorStoreHandler, OMEZarrWriter)):
            self._save_btn = MDASaveButton(self._data_wrapper)
            self._btns.insertWidget(3, self._save_btn)

        self.dims_sliders.set_locks_visible(True)

    def reader(self) -> Any:
        """Return the reader for the data or the data if no reader is available."""
        if isinstance(self._data_wrapper, MMTensorstoreWrapper):
            return TensorstoreZarrReader(self.data.store)
        elif isinstance(self._data_wrapper, MM5DWriterWrapper):
            if isinstance(self._data_wrapper.data, OMEZarrWriter):
                return OMEZarrReader(self.data.group)
            # TODO: implement logic for OMETiffWriter
        else:
            return self.data

    def _patched_frame_ready(self, *args: Any) -> None:
        self._superframeReady(*args)  # type: ignore
        if len(args) >= 2 and isinstance(e := args[1], MDAEvent):
            self._on_frame_ready(e)

    @ensure_main_thread  # type: ignore
    def _on_frame_ready(self, event: MDAEvent) -> None:
        self.set_current_index(event.index)
