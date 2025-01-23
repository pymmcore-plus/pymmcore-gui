from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from ndv import ArrayViewer
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter, TensorStoreHandler
from qtpy.QtCore import QObject

if TYPE_CHECKING:
    import useq
    from pymmcore_plus.metadata import SummaryMetaV1
    from qtpy.QtWidgets import QWidget
    from useq import MDAEvent


class ViewersCoreLink(QObject):

    from ..data_wrappers import MMTensorstoreWrapper

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._current_viewer: ArrayViewer | None = None
        self._datastore: OMETiffWriter | OMEZarrWriter | TensorStoreHandler | None = (
            None
        )

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Prepare the acquisition datastore."""
        self._current_viewer = None
        self._datastore = None

        # pause until the datastore is ready
        self._mmc.mda.toggle_pause()

        # TODO: to implement when we will get the datastore form the MDAWidget
        # datastore = self._mda.writer if self._mda is not None else None
        self._datastore = TensorStoreHandler()
        # emit the sequenceStarted signal of the datastore since it is not connected
        self._datastore.sequenceStarted(sequence, meta)
        # connect the datastore mmcore signals
        self._mmc.mda.events.frameReady.connect(self._datastore.frameReady)
        self._mmc.mda.events.sequenceFinished.connect(self._datastore.sequenceFinished)

        # resume the sequence
        self._mmc.mda.toggle_pause()

    def _on_frame_ready(self, image: np.ndarray, event: MDAEvent) -> None:
        """Show the MDAViewer when the MDA sequence starts."""
        if self._current_viewer is None and self._datastore.store is not None:
            self._create_ndv_viewer()

        # TODO: fix this
        # elif self._current_viewer is not None:
        #     self._current_viewer.display_model.current_index.update(event.index)

    def _create_ndv_viewer(self) -> None:
        # TODO: this is triggering the standard TensorstoreWrapper. Remove .store
        # to use the new TensorstoreWrapper whuch is not working yet
        self._current_viewer = ArrayViewer(self._datastore.store)
        # self._current_viewer = ArrayViewer(self._datastore)
        self._current_viewer.show()

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Reset the variables and disconnect the signals."""
        self._mmc.mda.events.sequenceFinished.disconnect(
            self._datastore.sequenceFinished
        )
        self._mmc.mda.events.frameReady.disconnect(self._datastore.frameReady)

        # if there is not a viewer, create one (this can happen if the sequence is very
        # short, like a single channel for example)
        if self._current_viewer is None and self._datastore.store is not None:
            self._create_ndv_viewer()
