from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast
from weakref import WeakValueDictionary

import ndv
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import TensorStoreHandler
from qtpy.QtCore import Qt, QTimer

if TYPE_CHECKING:
    import numpy as np
    import useq
    from pymmcore_plus.mda import SupportsFrameReady
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from qtpy.QtWidgets import QWidget
    from useq import MDASequence

SEQ_VIEWERS: WeakValueDictionary[str, ndv.ArrayViewer] = WeakValueDictionary()


class ViewersCoreLink:
    """Object that mediates a connection between the MDA experiment and the viewers."""

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        self._parent = parent
        self._mmc = mmcore or CMMCorePlus.instance()
        self._active_viewer: ndv.ArrayViewer | None = None
        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)
        self._handler: SupportsFrameReady | None = None
        self._own_handler: TensorStoreHandler | None = None

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Reset the viewer and handler."""
        # get the handler from the sequence metadata if it exists
        if handlers := self._mmc.mda.get_output_handlers():
            self._handler = handlers[0]
            self._own_handler = None
        # if it does not exist, create a new TensorStoreHandler
        else:
            self._own_handler = self._create_tensorstore_handler(sequence, meta)
            self._handler = None

        # since the handler is empty, create a ndv viewer with no data
        self._active_viewer = viewer = self._create_viewer()
        SEQ_VIEWERS[str(sequence.uid)] = viewer
        viewer.show()

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        # at this point the viewer should exist
        if self._own_handler is not None:
            self._own_handler.frameReady(frame, event, meta)

        if (viewer := self._active_viewer) is None:
            return

        # if the viewer does not have data, set the data to the handler (this should
        # only happen once when the fist frame is received)
        if viewer.data_wrapper is None:
            handler = self._handler or self._own_handler
            if isinstance(handler, TensorStoreHandler):
                # TODO: temporary. maybe create the DataWrapper for the handlers
                # (e.g. data_wrappers.MMTensorstoreWrapper). right now we are using the
                viewer.data = handler.store
            else:
                warnings.warn(
                    f"don't know how to show data of type {type(handler)}",
                    stacklevel=2,
                )
        else:
            # Add a small delay to make sure the data are available in the handler
            QTimer.singleShot(
                5,
                lambda: viewer.display_model.current_index.update(
                    dict(event.index.items())
                ),
            )

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        if self._own_handler is not None:
            self._own_handler.sequenceFinished(sequence)

    def _create_viewer(self) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        viewer = ndv.ArrayViewer(None)
        wdg = cast("QWidget", viewer.widget())
        wdg.setParent(self._parent)
        # TODO: add viewer name
        wdg.setWindowFlags(Qt.WindowType.Dialog)
        return viewer

    def _create_tensorstore_handler(
        self, sequence: MDASequence, meta: SummaryMetaV1
    ) -> TensorStoreHandler:
        """Create a new TensorStoreHandler and connect the events."""
        handler = TensorStoreHandler(driver="zarr", kvstore="memory://")
        handler.reset(sequence)
        return handler
