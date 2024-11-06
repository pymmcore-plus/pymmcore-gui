from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from qtpy.QtCore import QObject, Qt
from qtpy.QtWidgets import QTabBar, QTabWidget

from micromanager_gui._widgets._viewers import MDAViewer

from ._menubar._menubar import PREVIEW, VIEWERS
from ._widgets._viewers import Preview

if TYPE_CHECKING:
    import useq
    from pymmcore_plus.metadata import SummaryMetaV1

    from ._main_window import MicroManagerGUI
    from ._widgets._mda_widget import MDAWidget
    from ._widgets._mm_console import MMConsole

DIALOG = Qt.WindowType.Dialog
VIEWER_TEMP_DIR = None
NO_R_BTN = (0, QTabBar.ButtonPosition.RightSide, None)
NO_L_BTN = (0, QTabBar.ButtonPosition.LeftSide, None)
MDA_VIEWER = "MDA Viewer"


class CoreViewersLink(QObject):
    def __init__(self, parent: MicroManagerGUI, *, mmcore: CMMCorePlus | None = None):
        super().__init__(parent)

        self._main_window = parent
        self._mmc = mmcore or CMMCorePlus.instance()

        # Tab widget for the viewers (preview and MDA)
        self._viewer_tab = QTabWidget()
        # Enable the close button on tabs
        self._viewer_tab.setTabsClosable(True)
        self._viewer_tab.tabCloseRequested.connect(self._close_tab)
        self._main_window._central_wdg_layout.addWidget(self._viewer_tab, 0, 0)

        # preview tab
        self._preview: Preview = Preview(parent=self._main_window, mmcore=self._mmc)
        self._viewer_tab.addTab(self._preview, PREVIEW.capitalize())
        # remove the preview tab close button
        self._viewer_tab.tabBar().setTabButton(*NO_R_BTN)
        self._viewer_tab.tabBar().setTabButton(*NO_L_BTN)

        # keep track of the current mda viewer
        self._current_viewer: MDAViewer | None = None

        self._mda_running: bool = False

        # the MDAWidget. It should have been set in the _MenuBar at startup
        self._mda = cast("MDAWidget", self._main_window._menu_bar._mda)

        ev = self._mmc.events
        ev.continuousSequenceAcquisitionStarted.connect(self._set_preview_tab)
        ev.imageSnapped.connect(self._set_preview_tab)

        self._mmc.mda.events.sequenceStarted.connect(self._on_sequence_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_sequence_finished)
        self._mmc.mda.events.sequencePauseToggled.connect(self._enable_gui)

    def _close_tab(self, index: int) -> None:
        """Close the tab at the given index."""
        if index == 0:
            return
        widget = self._viewer_tab.widget(index)
        self._viewer_tab.removeTab(index)
        widget.deleteLater()

        # Delete the current viewer
        del self._current_viewer
        self._current_viewer = None

        # remove the viewer from the console
        if console := self._get_mm_console():
            if VIEWERS not in console.get_user_variables():
                return
            # remove the item at pos index from the viewers variable in the console
            viewer_name = list(console.shell.user_ns[VIEWERS].keys())[index - 1]
            console.shell.user_ns[VIEWERS].pop(viewer_name, None)

    def _on_sequence_started(
        self, sequence: useq.MDASequence, meta: SummaryMetaV1
    ) -> None:
        """Show the MDAViewer when the MDA sequence starts."""
        self._mda_running = True

        # disable the menu bar
        self._main_window._menu_bar._enable(False)

        # pause until the viewer is ready
        self._mmc.mda.toggle_pause()
        # setup the viewer
        self._setup_viewer(sequence, meta)
        # resume the sequence
        self._mmc.mda.toggle_pause()

    def _setup_viewer(self, sequence: useq.MDASequence, meta: SummaryMetaV1) -> None:
        """Setup the MDAViewer."""
        # get the MDAWidget writer
        datastore = self._mda.writer if self._mda is not None else None
        self._current_viewer = MDAViewer(parent=self._main_window, data=datastore)

        # rename the viewer if there is a save_name' in the metadata or add a digit
        pmmcw_meta = cast(dict, sequence.metadata.get(PYMMCW_METADATA_KEY, {}))
        viewer_name = self._get_viewer_name(pmmcw_meta.get("save_name"))
        self._viewer_tab.addTab(self._current_viewer, viewer_name)
        self._viewer_tab.setCurrentWidget(self._current_viewer)

        # call it manually instead in _connect_viewer because this signal has been
        # emitted already
        self._current_viewer.data.sequenceStarted(sequence, meta)

        # disable the LUT drop down and the mono/composite button (temporary)
        self._enable_gui(False)

        # connect the signals
        self._connect_viewer(self._current_viewer)

        # update the viewers variable in the console with the new viewer
        self._add_viewer_to_mm_console(viewer_name, self._current_viewer)

    def _get_viewer_name(self, viewer_name: str | None) -> str:
        """Get the viewer name from the metadata.

        If viewer_name is None, get the highest index for the viewer name. Otherwise,
        return the viewer name.
        """
        if viewer_name:
            return viewer_name

        # loop through the tabs and get the highest index for the viewer name
        index = 0
        for v in range(self._viewer_tab.count()):
            tab_name = self._viewer_tab.tabText(v)
            if tab_name.startswith(MDA_VIEWER):
                idx = tab_name.replace(f"{MDA_VIEWER} ", "")
                if idx.isdigit():
                    index = max(index, int(idx))
        return f"{MDA_VIEWER} {index + 1}"

    def _on_sequence_finished(self, sequence: useq.MDASequence) -> None:
        """Hide the MDAViewer when the MDA sequence finishes."""
        self._main_window._menu_bar._enable(True)

        self._mda_running = False

        if self._current_viewer is None:
            return

        # enable the LUT drop down and the mono/composite button (temporary)
        self._enable_gui(True)

        # call it before we disconnect the signals or it will not be called
        self._current_viewer.data.sequenceFinished(sequence)

        self._disconnect_viewer(self._current_viewer)

        self._current_viewer = None

    def _connect_viewer(self, viewer: MDAViewer) -> None:
        self._mmc.mda.events.sequenceFinished.connect(viewer.data.sequenceFinished)
        self._mmc.mda.events.frameReady.connect(viewer.data.frameReady)

    def _disconnect_viewer(self, viewer: MDAViewer) -> None:
        """Disconnect the signals."""
        self._mmc.mda.events.frameReady.disconnect(viewer.data.frameReady)
        self._mmc.mda.events.sequenceFinished.disconnect(viewer.data.sequenceFinished)

    def _enable_gui(self, state: bool) -> None:
        """Pause the viewer when the MDA sequence is paused."""
        self._main_window._menu_bar._enable(state)
        if self._current_viewer is None:
            return

    def _set_preview_tab(self) -> None:
        """Set the preview tab."""
        if self._mda_running:
            return
        self._viewer_tab.setCurrentWidget(self._preview)

    def _get_mm_console(self) -> MMConsole | None:
        """Rertun the MMConsole if it exists."""
        return self._main_window._menu_bar._mm_console

    def _add_viewer_to_mm_console(
        self, viewer_name: str, mda_viewer: MDAViewer
    ) -> None:
        """Update the viewers variable in the MMConsole."""
        if console := self._get_mm_console():
            if VIEWERS not in console.get_user_variables():
                return
            console.shell.user_ns[VIEWERS].update({viewer_name: mda_viewer})
