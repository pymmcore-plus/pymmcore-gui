from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from qtpy.QtCore import QObject, Qt
from qtpy.QtWidgets import QApplication

from ._widgets._mda._mda_viewer import MDAViewer
from ._widgets._preview import Preview

DIALOG = Qt.WindowType.Dialog

if TYPE_CHECKING:
    import useq

    from ._main_window import MicroManagerGUI


class _CoreLink(QObject):
    def __init__(self, parent: MicroManagerGUI, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._main_window = parent

        # set max canvas size to the screen height
        app = QApplication.instance()
        screen_height = app.primaryScreen().geometry().height()
        self._canvas_size = (screen_height, screen_height)

        self._is_mda_running: bool = False

        # to keep track of the viewers
        self._current_viewer: MDAViewer | None = None
        self._viewers: list[MDAViewer] = []

        # preview widget
        self._preview = Preview(parent, mmcore=self._mmc, canvas_size=self._canvas_size)
        self._preview.setWindowFlags(DIALOG)
        self._preview.hide()

        # core connections
        ev = self._mmc.events
        ev.imageSnapped.connect(self._show_preview)
        ev.continuousSequenceAcquisitionStarted.connect(self._show_preview)
        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        """Disconnect signals."""
        ev = self._mmc.events
        ev.imageSnapped.disconnect(self._show_preview)
        ev.continuousSequenceAcquisitionStarted.disconnect(self._show_preview)
        self._mmc.mda.events.sequenceStarted.disconnect(self._on_sequence_started)
        self._mmc.mda.events.sequenceFinished.disconnect(self._on_sequence_finished)

    def _show_preview(self) -> None:
        """Show the preview widget."""
        # do not show if MDA is running
        if self._is_mda_running:
            return
        # show if hidden, raise if visible
        if self._preview.isHidden():
            self._preview.resize(self._preview.sizeHint() / 2)
            self._preview.show()
        else:
            self._preview.raise_()

    def _setup_viewer(self, sequence: useq.MDASequence) -> None:
        self._current_viewer = MDAViewer(
            self._main_window, mmcore=self._mmc, canvas_size=self._canvas_size
        )

        # rename the viewer if there is a save_name in the metadata or add a digit
        save_meta = cast(dict, sequence.metadata.get(PYMMCW_METADATA_KEY, {}))
        save_name = save_meta.get("save_name")
        save_name = (
            save_name
            if save_name is not None
            else f"MDA Viewer {len(self._viewers) + 1}"
        )
        self._current_viewer.setWindowTitle(save_name)

        # call it manually indted in _connect_viewer because this signal has been
        # emitted already
        self._current_viewer.sequenceStarted(sequence)

        # connect the signals
        self._connect_viewer(self._current_viewer)

        # set the dialog window flags and show
        self._current_viewer.setWindowFlags(DIALOG)
        self._current_viewer.resize(self._current_viewer.sizeHint() / 2)
        self._current_viewer.show()

        # store the viewer
        self._viewers.append(self._current_viewer)

    def _connect_viewer(self, viewer: MDAViewer) -> None:
        self._mmc.mda.events.sequenceFinished.connect(viewer.sequenceFinished)
        self._mmc.mda.events.frameReady.connect(viewer.frameReady)

    def _disconnect_viewer(self, viewer: MDAViewer) -> None:
        """Disconnect the signals."""
        self._mmc.mda.events.sequenceFinished.disconnect(viewer.sequenceFinished)
        self._mmc.mda.events.frameReady.disconnect(viewer.frameReady)

    def _on_sequence_started(self, sequence: useq.MDASequence) -> None:
        """Show the MDAViewer when the MDA sequence starts."""
        self._is_mda_running = True
        self._preview.hide()

        # pause until the viewer is ready
        self._mmc.mda.toggle_pause()
        # setup the viewer
        self._setup_viewer(sequence)
        # resume the sequence
        self._mmc.mda.toggle_pause()

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Hide the MDAViewer when the MDA sequence finishes."""
        self._is_mda_running = False
        if self._current_viewer is None:
            return
        self._disconnect_viewer(self._current_viewer)
