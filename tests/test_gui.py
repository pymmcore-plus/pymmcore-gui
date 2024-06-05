from __future__ import annotations

from typing import TYPE_CHECKING

# from pymmcore_plus.mda.handlers import TensorStoreHandler
# from pymmcore_widgets._stack_viewer_v2._mda_viewer import MDAViewer
from micromanager_gui import MicroManagerGUI

# from micromanager_gui._menubar._menubar import DOCKWIDGETS, WIDGETS

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_load_gui(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    assert gui._menu_bar._mda
    assert gui._core_link._preview
    assert not gui._core_link._preview.isHidden()
    assert gui._core_link._viewer_tab.count() == 1
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    assert gui._core_link._current_viewer is None
    assert gui._core_link._mda_running is False


# def test_menu_wdg(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)
#     menu = gui._menu_bar

#     assert len(menu._widgets.keys()) == 2  # MDA and GroupPreset widgets
#     for action in menu._widgets_menu.actions():
#         action.trigger()
#     assert len(menu._widgets.keys()) == len(WIDGETS) + len(DOCKWIDGETS)


# def test_menu_viewer(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)
#     menu = gui._menu_bar
#     assert gui._core_link._viewer_tab.tabText(0) == "Preview"
#     # add a viewer
#     gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA1")
#     gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA2")
#     assert gui._core_link._viewer_tab.count() == 3

#     menu._close_all()
#     assert gui._core_link._viewer_tab.count() == 1

#     gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA3")
#     gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA4")
#     gui._core_link._viewer_tab.setCurrentIndex(2)
#     assert gui._core_link._viewer_tab.count() == 3

#     menu._close_all_but_current()
#     assert gui._core_link._viewer_tab.count() == 2
#     assert gui._core_link._viewer_tab.tabText(0) == "Preview"
#     assert gui._core_link._viewer_tab.tabText(1) == "MDA4"

#     menu._close_all()


# def test_snap(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)

#     assert gui._core_link._preview
#     assert gui._core_link._preview._image_preview.image is None
#     assert not gui._core_link._preview.isHidden()

#     with qtbot.waitSignal(global_mmcore.events.imageSnapped):
#         gui._core_link._preview._snap._snap()
#     assert gui._core_link._preview._image_preview.image
#     assert gui._core_link._preview._image_preview.image._data.shape


# def test_live(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)

#     assert gui._core_link._preview
#     assert gui._core_link._preview._image_preview.image is None
#     assert not gui._core_link._preview.isHidden()

#     with qtbot.waitSignal(global_mmcore.events.continuousSequenceAcquisitionStarted):
#         gui._core_link._preview._live._toggle_live_mode()
#     assert global_mmcore.isSequenceRunning()
#     with qtbot.waitSignal(global_mmcore.events.sequenceAcquisitionStopped):
#         gui._core_link._preview._live._toggle_live_mode()
#     assert not global_mmcore.isSequenceRunning()


# def test_mda_viewer(
#     qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path, _run_after_each_test
# ):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)

#     mda = useq.MDASequence(channels=["DAPI", "FITC"])
#     with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
#         global_mmcore.mda.run(mda)
#     assert gui._core_link._viewer_tab.count() == 2
#     assert gui._core_link._viewer_tab.tabText(1) == "MDA Viewer 1"
#     assert gui._core_link._viewer_tab.currentIndex() == 1

#     mda = useq.MDASequence(
#         channels=["FITC", "DAPI"],
#         metadata={
#             PYMMCW_METADATA_KEY: {
#                 "format": "tensorstore-zarr",
#                 "save_dir": str(tmp_path),
#                 "save_name": "t.tensorstore.zarr",
#                 "should_save": True,
#             }
#         },
#     )
#     gui._menu_bar._mda.setValue(mda)

#     with qtbot.waitSignal(global_mmcore.mda.events.sequenceStarted):
#         gui._menu_bar._mda.run_mda()

#     assert isinstance(gui._menu_bar._mda.writer, TensorStoreHandler)
#     assert gui._core_link._viewer_tab.count() == 3
#     assert gui._core_link._viewer_tab.tabText(2) == "t.tensorstore.zarr"

#     # saving tensorstore and MDAViewer datastore should be the same
#     assert gui._core_link._mda.writer == gui._core_link._viewer_tab.widget(2)._data
#     gui._menu_bar._close_all()
