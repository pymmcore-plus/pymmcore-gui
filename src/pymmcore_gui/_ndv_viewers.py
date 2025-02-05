from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast
from weakref import WeakValueDictionary

import ndv
from pymmcore_plus.mda.handlers import TensorStoreHandler
from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy as np
    import useq
    from ndv.models._array_display_model import IndexMap
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.mda import SupportsFrameReady
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from useq import MDASequence


# NOTE: we make this a QObject mostly so that the lifetime of this object is tied to
# the lifetime of the parent QMainWindow.  If inheriting from QObject is removed in
# the future, make sure not to store a strong reference to this main_window
class NDVViewersManager(QObject):
    """Object that mediates a connection between the MDA experiment and ndv viewers.

    Parameters
    ----------
    parent : QWidget
        The parent widget.
    mmcore : CMMCorePlus
        The CMMCorePlus instance.
    """

    def __init__(self, parent: QWidget, mmcore: CMMCorePlus):
        super().__init__(parent)
        self._mmc = mmcore

        # weakref map of {sequence_uid: ndv.ArrayViewer}
        self._seq_viewers = WeakValueDictionary[str, ndv.ArrayViewer]()
        # currently active viewer
        self._active_viewer: ndv.ArrayViewer | None = None

        # We differentiate between handlers that were created by someone else, and
        # gathered using mda.get_output_handlers(), vs handlers that were created by us.
        # because we need to call frameReady/sequenceFinished manually on the latter.
        self._handler: SupportsFrameReady | None = None
        self._own_handler: TensorStoreHandler | None = None

        # CONNECTIONS ---------------------------------------------------------

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.frameReady.connect(self._on_frame_ready)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)
        parent.destroyed.connect(self._cleanup)

    def _cleanup(self, obj: QObject | None = None) -> None:
        self._active_viewer = None
        self._handler = None
        self._own_handler = None

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Called when a new MDA sequence has been started.

        We grab the first handler in the list of output handlers, or create a new
        TensorStoreHandler if none exist. Then we create a new ndv viewer and show it.
        """
        self._own_handler = self._handler = None
        if handlers := self._mmc.mda.get_output_handlers():
            # someone else has created a handler for this sequence
            self._handler = handlers[0]
        else:
            # if it does not exist, create a new TensorStoreHandler
            self._own_handler = TensorStoreHandler(driver="zarr", kvstore="memory://")
            self._own_handler.reset(sequence)

        # since the handler is empty at this point, create a ndv viewer with no data
        self._active_viewer = viewer = self._create_ndv_viewer(sequence)
        self._seq_viewers[str(sequence.uid)] = viewer

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        # at this point the viewer should exist
        if self._own_handler is not None:
            self._own_handler.frameReady(frame, event, meta)

        if (viewer := self._active_viewer) is None:
            return  # pragma: no cover

        # if the viewer does not yet have data, it's likely the very first frame
        # so update the viewer's data source to the underlying handlers store
        if viewer.data_wrapper is None:
            handler = self._handler or self._own_handler
            if isinstance(handler, TensorStoreHandler):
                # TODO: temporary. maybe create the DataWrapper for the handlers
                viewer.data = handler.store
            else:
                warnings.warn(
                    f"don't know how to show data of type {type(handler)}",
                    stacklevel=2,
                )
        # otherwise update the sliders to the most recently acquired frame
        else:
            # Add a small delay to make sure the data are available in the handler
            # This is a bit of a hack to get around the data handlers can write data
            # asynchronously, so the data may not be available immediately to the viewer
            # after the handler's frameReady method is called.
            current_index = viewer.display_model.current_index

            def _update(_idx: IndexMap = current_index) -> None:
                try:
                    _idx.update(event.index.items())
                except Exception:  # pragma: no cover
                    # this happens if the viewer has been closed in the meantime
                    # usually it's a RuntimeError, but could be an EmitLoopError
                    pass

            QTimer.singleShot(10, _update)

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Called when a sequence has finished."""
        if self._own_handler is not None:
            self._own_handler.sequenceFinished(sequence)
        # cleanup pointers somehow?

    def _create_ndv_viewer(self, sequence: MDASequence) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        ndv_viewer = ndv.ArrayViewer()
        q_viewer = cast("QWidget", ndv_viewer.widget())

        if isinstance(par := self.parent(), QWidget):
            q_viewer.setParent(par)

        sha = str(sequence.uid)[:8]
        q_viewer.setObjectName(f"ndv-{sha}")
        q_viewer.setWindowTitle(f"MDA {sha}")
        q_viewer.setWindowFlags(Qt.WindowType.Dialog)
        q_viewer.show()
        return ndv_viewer

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} {hex(id(self))} ({len(self)} viewer)>"

    def __len__(self) -> int:
        return len(self._seq_viewers)

    def viewers(self) -> Iterator[ndv.ArrayViewer]:
        yield from (self._seq_viewers.values())
