from __future__ import annotations

from typing import TYPE_CHECKING, cast

import ndv
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import (
    TensorStoreHandler,
)
from qtpy.QtCore import QObject, Qt, QTimer

from ._shared_handler import get_handler

if TYPE_CHECKING:
    import numpy as np
    import useq
    from pymmcore_plus.metadata import SummaryMetaV1
    from qtpy.QtWidgets import QWidget


class ViewersCoreLink(QObject):
    from pymmcore_gui.data_wrappers import MMTensorstoreWrapper

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._parent = parent

        self._mmc = mmcore or CMMCorePlus.instance()

        self._mda_viewer: ndv.ArrayViewer | None = None

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Reset the viewer and handler."""
        self._mda_viewer = None

        # get the handler from the sequence metadata if it exists
        self._handler: TensorStoreHandler | None = get_handler(sequence)

        # if it does not exist, create a new TensorStoreHandler
        if self._handler is None:
            self._handler = self._create_tensorstore_handler(sequence, meta)

        # since the handler is empty, create a ndv viewer with no data
        self._mda_viewer = self._create_emply_viewer()
        self._mda_viewer.show()

    def _create_tensorstore_handler(self, sequence, meta) -> TensorStoreHandler:
        """Create a new TensorStoreHandler and connect the events."""
        handler = TensorStoreHandler()
        handler.sequenceStarted(sequence, meta)
        self._mmc.mda.events.frameReady.connect(handler.frameReady)
        self._mmc.mda.events.sequenceFinished.connect(handler.sequenceFinished)
        return handler

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: SummaryMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        # at this point the viewer should exist
        if self._mda_viewer is None:
            return
        # if the viewer does not have data, set the data to the handler (this should
        # only happen once when the fist frame is received)
        if self._mda_viewer.data is None and self._handler is not None:
            # TODO: temporary. maybe create the DataWrapper for the handlers
            # (e.g. data_wrappers.MMTensorstoreWrapper). right now we are using the
            self._mda_viewer.data = self._handler.store
        else:
            # Add a small delay to make sure the data are available in the handler
            QTimer.singleShot(
                5,
                lambda: self._mda_viewer.display_model.current_index.update(
                    dict(event.index.items())
                ),
            )

    def _create_emply_viewer(self) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        # TODO: temporary, create the DataWrapper for the handlers
        viewer = ndv.ArrayViewer(None)
        wdg = cast("QWidget", viewer.widget())
        wdg.setParent(self._parent)
        # TODO: add viewer name
        wdg.setWindowFlags(Qt.WindowType.Dialog)
        return viewer
