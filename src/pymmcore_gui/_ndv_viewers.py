from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from weakref import WeakSet, WeakValueDictionary

import ndv
import useq

from pymmcore_gui._qt.QtAds import CDockWidget
from pymmcore_gui._qt.QtCore import QObject, QTimer, Signal
from pymmcore_gui._qt.QtWidgets import QWidget
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview

if TYPE_CHECKING:
    from collections.abc import Iterator

    import numpy as np
    from ndv.models._array_display_model import (
        IndexMap,  # pyright: ignore[reportPrivateImportUsage]
    )
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from useq import MDASequence

    from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase


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
        self._active_mda_viewer: ndv.ArrayViewer | None = None

        # CONNECTIONS ---------------------------------------------------------

        self._is_mda_running = False
        self._current_image_preview: CDockWidget | None = None

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.sequenceAcquisitionStarted.connect(self._on_streaming_started)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_started)
        ev.propertyChanged.connect(self._on_property_changed)

        self._runner = self._mmc.mda
        mda_ev = self._mmc.mda.events
        mda_ev.sequenceStarted.connect(self._on_sequence_started)
        mda_ev.frameReady.connect(self._on_frame_ready)
        mda_ev.sequenceFinished.connect(self._on_sequence_finished)

        parent.destroyed.connect(self._cleanup)

    def _cleanup(self, obj: QObject | None = None) -> None:
        self._active_mda_viewer = None

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Called when a new MDA sequence has been started."""
        self._is_mda_running = True
        self._view = view = self._runner.get_view()
        self._active_mda_viewer = viewer = self._create_ndv_viewer(self._view, sequence)
        if hasattr(view, "coords_changed"):
            view.coords_changed.connect(viewer.data_wrapper.dims_changed)

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None:
        """Create a viewer if it does not exist, otherwise update the current index."""
        if (viewer := self._active_mda_viewer) is None:
            return  # pragma: no cover

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
        # cleanup pointers somehow?
        self._is_mda_running = False

    def _create_ndv_viewer(self, view: Any, sequence: MDASequence) -> ndv.ArrayViewer:
        """Create a new ndv viewer with no data."""
        ndv_viewer = ndv.ArrayViewer(view)
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
