from __future__ import annotations

import functools
import warnings
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakSet, WeakValueDictionary

import ndv
import useq
from ome_writers._array_view import AcquisitionView
from pymmcore_plus.mda.handlers._runner_handler import OMERunnerHandler

from pymmcore_gui._qt.QtAds import CDockWidget
from pymmcore_gui._qt.QtCore import QObject, Signal
from pymmcore_gui._qt.QtWidgets import QWidget
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview

if TYPE_CHECKING:
    from collections.abc import Hashable, Iterator, Mapping, Sequence

    import numpy as np
    from ome_writers._coord_tracker import CoordUpdate
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.metadata import FrameMetaV1, SummaryMetaV1
    from useq import MDASequence

    from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase


class _StreamEventBridge(QObject):
    """Bridges ome-writers stream events to the Qt main thread.

    Stream events (coords_expanded, coords_changed) fire on the writer thread.
    This QObject re-emits them as Qt signals so that connected slots run on the
    main thread via Qt's automatic cross-thread signal delivery.
    """

    coordsExpanded = Signal(object)
    coordsChanged = Signal(object)


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

    def update_coords(self, update: CoordUpdate) -> None:
        """Called when new dimensions become visible (high water marks)."""
        # Store the latest coordinate ranges
        self._current_coords = update.max_coords  #  type: ignore[assignment]
        # Emit dims_changed to tell ndv to update its slider ranges
        self.dims_changed.emit()
        print("Updating ndv slider ranges to:\n", self._current_coords)

    def on_coords_expanded(self, update: CoordUpdate) -> None:
        """Called when high water marks change — expand slider ranges."""
        self._current_coords = update.max_coords  # type: ignore[assignment]
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

        self._handler: OMERunnerHandler | None = None

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

        # Monkeypatch run_mda to always inject a default writer when none is
        # provided.  This ensures the MDA runner manages the handler lifecycle
        # (prepare / _writeframe / cleanup) so the viewer manager only needs to
        # create the viewer on the main thread.
        self._patch_run_mda()

        parent.destroyed.connect(self._cleanup)

    def _patch_run_mda(self) -> None:
        """Wrap CMMCorePlus.run_mda to inject a default OME writer."""
        original = self._mmc.run_mda

        @functools.wraps(original)
        def _run_mda_with_default_writer(
            events: Any, *, output: Any = None, **kwargs: Any
        ) -> Any:
            if output is None:
                output = OMERunnerHandler.in_tempdir()
            return original(events, output=output, **kwargs)

        self._mmc.run_mda = _run_mda_with_default_writer  #  type: ignore

    def _cleanup(self, obj: QObject | None = None) -> None:
        self._active_mda_viewer = None
        self._handler = None

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Called when a new MDA sequence has been started.

        We look for an OMERunnerHandler in the runner's writer handlers (which
        the runner has already called prepare() on), or fall back to the output
        handlers for legacy TensorStoreHandler support.
        """
        self._is_mda_running = True
        self._handler = None
        self._active_mda_viewer = None

        # Check writer handlers first (managed by the runner via the writer= arg)
        if handlers := self._mmc.mda.get_output_handlers():
            _handler = handlers[0]
            if not isinstance(_handler, OMERunnerHandler):
                warnings.warn(
                    f"Expected a OMERunnerHandler in writer handlers, got "
                    f"{type(_handler)}.  Viewer will not be updated.",
                    stacklevel=2,
                )
                return
            self._handler = _handler
            self._active_mda_viewer = self._create_ndv_viewer(sequence)

    def _on_frame_ready(
        self, frame: np.ndarray, event: useq.MDAEvent, meta: FrameMetaV1
    ) -> None: ...

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Called when a sequence has finished."""
        # runner handles cleanup for writer handlers
        self._is_mda_running = False

    def _create_ndv_viewer(self, sequence: MDASequence) -> ndv.ArrayViewer | None:
        """Create a new ndv viewer backed by an OMERunnerHandler's stream."""
        if self._handler is None or self._handler.stream is None:
            return None
        stream = self._handler.stream
        view = AcquisitionView.from_stream(stream)
        wrapper = CoordsAwareDataWrapper(view)

        channel_kwargs: dict[str, Any] = {}
        if len(sequence.channels) > 1:
            channel_kwargs = {"channel_axis": "c", "channel_mode": "composite"}
        ndv_viewer = ndv.ArrayViewer(wrapper, **channel_kwargs)

        # Stream events fire on the writer thread.  Use a Qt signal bridge so
        # viewer updates happen on the main thread.
        bridge = _StreamEventBridge(ndv_viewer.widget())
        bridge.coordsExpanded.connect(wrapper.on_coords_expanded)
        bridge.coordsChanged.connect(
            lambda update: ndv_viewer.display_model.current_index.update(
                update.current_indices
            ),
        )
        stream.on("coords_expanded", bridge.coordsExpanded.emit)
        stream.on("coords_changed", bridge.coordsChanged.emit)

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
