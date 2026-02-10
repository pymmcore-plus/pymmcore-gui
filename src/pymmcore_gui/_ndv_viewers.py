from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakSet, WeakValueDictionary

import ndv
import useq
from ome_writers._array_view import AcquisitionView
from pymmcore_plus.mda.handlers import OMEWriterHandler, TensorStoreHandler

from pymmcore_gui._qt.QtAds import CDockWidget
from pymmcore_gui._qt.QtCore import QObject, Signal
from pymmcore_gui._qt.QtWidgets import QWidget
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterator, Mapping, Sequence

    import numpy as np
    from ome_writers._coord_tracker import CoordUpdate
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.mda import SupportsFrameReady
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from useq import MDASequence

    from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase


class CoordsAwareDataWrapper(ndv.DataWrapper):
    """DataWrapper that tracks acquisition progress via coordinate events.

    NDV updates the viewers sliders based on the coordinate ranges returned by `coords`,
    and you can trigger slider range updates by emitting `dims_changed`.
    """

    def __init__(self, view: AcquisitionView) -> None:
        super().__init__(view)
        self._view = view
        self._current_coords: Mapping[Hashable, Sequence] = {
            i: range(s) for i, s in zip(self.dims, self._data.shape, strict=False)
        }

    def on_coords_expanded(self, update: CoordUpdate) -> None:
        """Called when high water marks change — expand slider ranges."""
        self._current_coords = update.max_coords
        self.dims_changed.emit()

    @property
    def dims(self) -> tuple[Hashable, ...]:
        """Return dimension names."""
        # Get dimension names from the view
        return self._view.dims

    @property
    def coords(self) -> Mapping[Hashable, Sequence]:
        """Return current visible coordinate ranges."""
        return self._current_coords

    @classmethod
    def supports(cls, obj: Any) -> bool:  # type: ignore[override]
        """Check if this wrapper supports the given object."""
        return isinstance(obj, AcquisitionView)


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

    mdaViewerCreated = Signal(ndv.ArrayViewer, useq.MDASequence)
    previewViewerCreated = Signal(CDockWidget)
    viewerDestroyed = Signal(str)

    def __init__(self, parent: QWidget, mmcore: CMMCorePlus):
        super().__init__(parent)
        self._mmc = mmcore

        # weakref map of {sequence_uid: ndv.ArrayViewer}
        self._seq_viewers = WeakValueDictionary[str, ndv.ArrayViewer]()
        self._preview_dock_widgets = WeakSet[CDockWidget]()
        # currently active viewer
        self._active_mda_viewer: ndv.ArrayViewer | None = None

        # We differentiate between handlers that were created by someone else, and
        # gathered using mda.get_output_handlers(), vs handlers that were created by us.
        # because we need to call frameReady/sequenceFinished manually on the latter.
        self._handler: SupportsFrameReady | None = None
        self._own_handler: OMEWriterHandler | None = None

        # CONNECTIONS ---------------------------------------------------------

        self._is_mda_running = False
        self._current_image_preview: CDockWidget | None = None

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.sequenceAcquisitionStarted.connect(self._on_streaming_started)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_started)
        ev.propertyChanged.connect(self._on_property_changed)

        mda_ev = self._mmc.mda.events
        mda_ev.sequenceStarted.connect(self._on_sequence_started)
        mda_ev.frameReady.connect(self._on_frame_ready)
        mda_ev.sequenceFinished.connect(self._on_sequence_finished)

        parent.destroyed.connect(self._cleanup)

    def _cleanup(self, obj: QObject | None = None) -> None:
        self._active_mda_viewer = None
        self._handler = None
        self._own_handler = None

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Called when a new MDA sequence has been started.

        We grab the first handler in the list of output handlers, or create a new
        TensorStoreHandler if none exist. Then we create a new ndv viewer and show it.
        """
        self._is_mda_running = True

        self._own_handler = self._handler = None
        if handlers := self._mmc.mda.get_output_handlers():
            # someone else has created a handler for this sequence
            self._handler = handlers[0]
        else:
            # if it does not exist, create an internal OMEWriterHandler
            self._own_handler = OMEWriterHandler.in_tmpdir()
            self._own_handler.sequenceStarted(sequence, meta)

        # since the handler is empty at this point, create a ndv viewer with no data
        self._active_mda_viewer = self._create_ndv_viewer(sequence)

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        # at this point the viewer should exist
        if self._own_handler is not None:
            self._own_handler.frameReady(frame, event, meta)

        if (viewer := self._active_mda_viewer) is None:
            return  # pragma: no cover

        # if the viewer does not yet have data, it's likely the very first frame
        # so update the viewer's data source to the underlying handlers store
        if viewer.data_wrapper is None:
            handler = self._handler or self._own_handler
            if isinstance(handler, TensorStoreHandler):
                # TODO: temporary. maybe create the DataWrapper for the handlers
                viewer.data = handler.store
            elif isinstance(handler, OMEWriterHandler):
                self._setup_ome_writer_viewer(viewer, handler)
            else:
                warnings.warn(
                    f"don't know how to show data of type {type(handler)}",
                    stacklevel=2,
                )

    def _setup_ome_writer_viewer(
        self, viewer: ndv.ArrayViewer, handler: OMEWriterHandler
    ) -> None:
        """Set up an ndv viewer with AcquisitionView and coordinate tracking."""
        from ome_writers._array_view import AcquisitionView

        stream = handler.stream
        if stream is None:
            return  # pragma: no cover

        view = AcquisitionView.from_stream(stream)
        wrapper = CoordsAwareDataWrapper(view)
        viewer.data = wrapper
        stream.on("coords_expanded", wrapper.on_coords_expanded)
        stream.on(
            "coords_changed",
            lambda update: viewer.display_model.current_index.update(
                update.current_indices
            ),
        )

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Called when a sequence has finished."""
        if self._own_handler is not None:
            self._own_handler.sequenceFinished(sequence)
        # cleanup pointers somehow?
        self._is_mda_running = False

    def _create_ndv_viewer(self, sequence: MDASequence) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        ndv_viewer = ndv.ArrayViewer()
        self._seq_viewers[str(sequence.uid)] = ndv_viewer
        self.mdaViewerCreated.emit(ndv_viewer, sequence)
        return ndv_viewer

    def _create_or_show_img_preview(self) -> ImagePreviewBase | None:
        """Create or show the image preview widget, return True if created."""
        preview = None
        if self._current_image_preview is None:
            preview = NDVPreview(mmcore=self._mmc)
            if not isinstance((parent := self.parent()), QWidget):
                parent = None  # pragma: no cover

            # this is a hacky workaround:
            # Calling CDockWidget('title', parent) is deprecated
            # It is preferred to instantiate with a CDockManager.
            # parent will almost always be the MainWindow that dock_manager
            # (and in reality, will never be None)
            if dm := getattr(parent, "dock_manager", None):
                dw = CDockWidget(dm, "Preview", parent)
            else:  # pragma: no cover
                dw = CDockWidget("Preview", parent)

            self._current_image_preview = dw
            self._preview_dock_widgets.add(dw)
            dw.setWidget(preview)
            dw.setFeature(dw.DockWidgetFeature.DockWidgetFloatable, False)
            self.previewViewerCreated.emit(dw)
        else:
            self._current_image_preview.toggleView(True)

        return preview

    def _on_streaming_started(self) -> None:
        if not self._is_mda_running:
            if preview := self._create_or_show_img_preview():
                preview._on_streaming_start()

    def _on_image_snapped(self) -> None:
        if not self._is_mda_running:
            if preview := self._create_or_show_img_preview():
                preview.append(self._mmc.getImage())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} {hex(id(self))} ({len(self)} viewer)>"

    def __len__(self) -> int:
        return len(self._seq_viewers)

    def viewers(self) -> Iterator[ndv.ArrayViewer]:
        yield from (self._seq_viewers.values())

    def _on_property_changed(self, dev: str, prop: str, value: str) -> None:
        if self._mmc is None:
            return  # pragma: no cover

        # if we change any camera property
        if dev == self._mmc.getCameraDevice() or (dev == "Core" and prop == "Camera"):
            if self._current_image_preview:
                # check if the existing viewer still has a valid shape and dtype
                # (dtype is actually tuple of (dtype, shape))
                preview = cast("NDVPreview", self._current_image_preview.widget())
                if preview._get_core_dtype_shape() != preview.dtype_shape:
                    preview.detach()
                    self._current_image_preview = None
