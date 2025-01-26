from __future__ import annotations

import contextlib
import warnings
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

from ._shared_handler import HANDLER

if TYPE_CHECKING:
    import numpy as np
    import useq
    from pymmcore_plus.metadata import SummaryMetaV1
    from qtpy.QtWidgets import QWidget


class ViewersCoreLink(QObject):

    from ..data_wrappers import MMTensorstoreWrapper

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
            if (handler := HANDLER.get()) is not None:
                self._mda_viewer = self._create_viewer(handler)
                self._mda_viewer.show()
        else:
            self._mda_viewer.display_model.current_index.update(
                dict(event.index.items())
            )

    def _create_viewer(
        self,
        handler: (
            TensorStoreHandler | OMETiffWriter | OMEZarrWriter | ImageSequenceWriter
        ),
    ) -> ndv.ArrayViewer:
        # TODO: temporary, create the DataWrapper for the handlers
        data = handler._store if isinstance(handler, TensorStoreHandler) else handler

        v = ndv.ArrayViewer(DataWrapper.create(data))
        wdg = cast("QWidget", v.widget())
        wdg.setParent(self._parent)
        wdg.setWindowFlags(Qt.WindowType.Dialog)
        # TODO: add viewer name
        return v

    def _on_sequence_finished(self) -> None:
        """Reset the viewer and handler."""
        HANDLER.set(None)
        self._mda_viewer = None

    # def _patch_handler(
    #     self,
    #     handler: (
    #         TensorStoreHandler | OMETiffWriter | OMEZarrWriter | ImageSequenceWriter
    #     ),
    # ) -> None:
    #     self._superframeReady = getattr(handler, "frameReady", None)
    #     if callable(self._superframeReady):
    #         handler.frameReady = self._patched_frame_ready  # type: ignore
    #     else:  # pragma: no cover
    #         warnings.warn(
    #             "MDAViewer: data does not have a frameReady method to patch, "
    #             "are you sure this is a valid data handler?",
    #             stacklevel=2,
    #         )

    # def _patched_frame_ready(
    #     self, frame: np.ndarray, event: useq.MDAEvent, meta: SummaryMetaV1
    # ) -> None:
    #     self._superframeReady(frame, event, meta)  # type: ignore

    #     if self._mda_viewer is None:
    #         if (handler := HANDLER.get()) is not None:
    #             self._mda_viewer = self._create_viewer(handler)
    #             self._mda_viewer.show()
    #     else:
    #         dims = {d: i for i, d in enumerate(self._mda_viewer.data_wrapper.dims)}
    #         self._mda_viewer.display_model.current_index.update(
    #             {dims[ax]: idx for ax, idx in event.index.items()}
    #         )
