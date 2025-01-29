from __future__ import annotations

from typing import TYPE_CHECKING, cast

import ndv
from ndv import DataWrapper
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)
from qtpy.QtCore import QObject, Qt

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
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Reset the viewer and handler."""
        self._mda_viewer = None

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: SummaryMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        if self._mda_viewer is None:
            if handler := get_handler(event):
                self._mda_viewer = self._create_viewer(handler)
                self._mda_viewer.show()
        else:
            # TODO: add timer to delay the update
            self._mda_viewer.display_model.current_index.update(
                dict(event.index.items())
            )

    def _create_viewer(self, handler: TensorStoreHandler | None) -> ndv.ArrayViewer:
        # TODO: temporary, create the DataWrapper for the handlers
        data = None if handler is None else handler.store

        viewer = ndv.ArrayViewer(DataWrapper.create(data))

        wdg = cast("QWidget", viewer.widget())
        wdg.setParent(self._parent)
        # TODO: add viewer name
        wdg.setWindowFlags(Qt.WindowType.Dialog)

        return viewer

    def _on_sequence_finished(self) -> None:
        """Reset the viewer and handler."""
        self._mda_viewer = None
