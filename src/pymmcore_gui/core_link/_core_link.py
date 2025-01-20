from __future__ import annotations

from typing import TYPE_CHECKING

from ndv import ArrayViewer
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import TensorStoreHandler
from qtpy.QtCore import QObject

if TYPE_CHECKING:
    import useq
    from pymmcore_plus.metadata import SummaryMetaV1
    from qtpy.QtWidgets import QWidget
    from useq import MDAEvent


class CoreViewersLink(QObject):

    from ..data_wrappers import MMTensorstoreWrapper

    def __init__(self, parent: QWidget, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._current_viewer: ArrayViewer | None = None

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Prepare the acquisition datastore."""
        self._current_viewer = None

        # pause until the viewer is ready
        self._mmc.mda.toggle_pause()
        print("------------------ PAUSED ------------------")

        # to implement when we will get the datastore form the MDAWidget
        # datastore = self._mda.writer if self._mda is not None else None
        self._datastore = TensorStoreHandler()
        # emit the sequenceStarted signal of the datastore since it is not connected
        self._datastore.sequenceStarted(sequence, meta)
        # connect the datastore mmcore signals
        self._mmc.mda.events.sequenceFinished.connect(self._datastore.sequenceFinished)
        self._mmc.mda.events.frameReady.connect(self._datastore.frameReady)

        # resume the sequence
        self._mmc.mda.toggle_pause()
        print("------------------ RESUMED ------------------")

    def _on_frame_ready(self, event: MDAEvent) -> None:
        """Show the MDAViewer when the MDA sequence starts."""
        print("------------------ FRAME READY ------------------")
        print(self._current_viewer is None, self._datastore.store is None)
        if self._current_viewer is None and self._datastore.store is not None:
            self._current_viewer = _ArrayViewer(self._datastore.store)
            self._current_viewer.show()

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Reset the variables and disconnect the signals."""
        self._mmc.mda.events.sequenceFinished.disconnect(
            self._datastore.sequenceFinished
        )
        self._mmc.mda.events.frameReady.disconnect(self._datastore.frameReady)

        if self._current_viewer is None and self._datastore.store is not None:
            print("------------------ ADDING AT THE END ------------------")
            self._current_viewer = _ArrayViewer(self._datastore.store)
            self._current_viewer.widget().show()

        breakpoint()

        # self._current_viewer = None
        # self._datastore = None


class _ArrayViewer(ArrayViewer):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        print("ArrayViewer created")
        print("----------------------")
        print(type(data))
        print(data)
