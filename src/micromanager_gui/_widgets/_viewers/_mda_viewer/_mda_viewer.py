from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from ndv import NDViewer
from pymmcore_plus.mda.handlers import TensorStoreHandler
from superqt import ensure_main_thread
from useq import MDAEvent

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

        self._save_btn = MDASaveButton(self._data_wrapper)
        self._btns.insertWidget(3, self._save_btn)
        self.dims_sliders.set_locks_visible(True)

    def _patched_frame_ready(self, *args: Any) -> None:
        self._superframeReady(*args)  # type: ignore
        if len(args) >= 2 and isinstance(e := args[1], MDAEvent):
            self._on_frame_ready(e)

    @ensure_main_thread  # type: ignore
    def _on_frame_ready(self, event: MDAEvent) -> None:
        self.set_current_index(event.index)
