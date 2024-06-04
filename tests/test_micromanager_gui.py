from pathlib import Path

import useq
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import TensorStoreHandler
from pymmcore_widgets._stack_viewer_v2._mda_viewer import MDAViewer
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from pytestqt.qtbot import QtBot

from micromanager_gui import MicroManagerGUI
from micromanager_gui._menubar._menubar import DOCKWIDGETS, WIDGETS

# from micromanager_gui._readers._tensorstore_zarr_reader import TensorstoreZarrReader
from micromanager_gui._readers._ome_zarr_reader import OMEZarrReader


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


def test_menu_wdg(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    menu = gui._menu_bar

    assert len(menu._widgets.keys()) == 2  # MDA and GroupPreset widgets
    for action in menu._widgets_menu.actions():
        action.trigger()
    assert len(menu._widgets.keys()) == len(WIDGETS) + len(DOCKWIDGETS)


def test_menu_viewer(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    menu = gui._menu_bar
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    # add a viewer
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA1")
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA2")
    assert gui._core_link._viewer_tab.count() == 3

    menu._close_all()
    assert gui._core_link._viewer_tab.count() == 1

    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA3")
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA4")
    gui._core_link._viewer_tab.setCurrentIndex(2)
    assert gui._core_link._viewer_tab.count() == 3

    menu._close_all_but_current()
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    assert gui._core_link._viewer_tab.tabText(1) == "MDA4"


def test_snap(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)

    assert gui._core_link._preview
    assert gui._core_link._preview._image_preview.image is None
    assert not gui._core_link._preview.isHidden()

    with qtbot.waitSignal(global_mmcore.events.imageSnapped):
        gui._core_link._preview._snap._snap()
    assert gui._core_link._preview._image_preview.image
    assert gui._core_link._preview._image_preview.image._data.shape


def test_live(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)

    assert gui._core_link._preview
    assert gui._core_link._preview._image_preview.image is None
    assert not gui._core_link._preview.isHidden()

    with qtbot.waitSignal(global_mmcore.events.continuousSequenceAcquisitionStarted):
        gui._core_link._preview._live._toggle_live_mode()
    assert global_mmcore.isSequenceRunning()
    with qtbot.waitSignal(global_mmcore.events.sequenceAcquisitionStopped):
        gui._core_link._preview._live._toggle_live_mode()
    assert not global_mmcore.isSequenceRunning()


# _run_after_each_test not using because it gives an error (to fix)
def test_mda_viewer(qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)

    mda = useq.MDASequence(channels=["DAPI", "FITC"])
    with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
        global_mmcore.mda.run(mda)
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(1) == "MDA Viewer 1"
    assert gui._core_link._viewer_tab.currentIndex() == 1

    dest = tmp_path / "ts.tensorstore.zarr"
    mda = useq.MDASequence(
        channels=["FITC", "DAPI"],
        metadata={
            PYMMCW_METADATA_KEY: {
                "format": "tensorstore-zarr",
                "save_dir": str(dest),
                "save_name": "t.tensorstore.zarr",
                "should_save": True,
            }
        },
    )
    gui._menu_bar._mda.setValue(mda)

    with qtbot.waitSignal(global_mmcore.mda.events.sequenceStarted):
        gui._menu_bar._mda.run_mda()

    assert isinstance(gui._menu_bar._mda.writer, TensorStoreHandler)
    assert gui._core_link._viewer_tab.count() == 3
    assert gui._core_link._viewer_tab.tabText(2) == "t.tensorstore.zarr"

    # saving tensorstore and MDAViewer datastore should be the same
    assert gui._core_link._mda.writer == gui._core_link._viewer_tab.widget(2)._data
    gui._menu_bar._close_all()


def test_ome_zarr_reader(qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path):
    dest = tmp_path / "z.ome.zarr"

    mda = useq.MDASequence(
        channels=["FITC", "DAPI"],
        stage_positions=[(0, 0), (0, 1)],
        time_plan={"loops": 3, "interval": 0.1},
        metadata={
            PYMMCW_METADATA_KEY: {
                "format": "ome-zarr",
                "save_dir": str(dest),
                "save_name": "z.ome.zarr",
                "should_save": True,
            }
        },
    )

    with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
        global_mmcore.mda.run(mda, output=dest)

    assert dest.exists()

    z = OMEZarrReader(dest)
    assert z.store
    assert z.sequence
    assert z.isel({"p": 0}).shape == (3, 2, 512, 512)
    assert z.isel({"p": 0, "t": 0}).shape == (2, 512, 512)


# def test_tensor_reader(qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path):
#     dest = tmp_path / "ts.tensorstore.zarr"

#     mda = useq.MDASequence(
#         channels=["FITC", "DAPI"],
#         stage_positions=[(0, 0), (0, 1)],
#         time_plan={"loops": 3, "interval": 0.1},
#         metadata={
#             PYMMCW_METADATA_KEY: {
#                 "format": "tensorstore-zarr",
#                 "save_dir": str(dest),
#                 "save_name": "t.tensorstore.zarr",
#                 "should_save": True,
#             }
#         },
#     )

#     with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
#         global_mmcore.mda.run(mda, output=dest)

#     assert dest.exists()

#     ts = TensorstoreZarrReader(dest)
#     assert ts.store
#     assert ts.sequence
#     data = ts.isel({"p": 0})
#     # assert data.shape == (3, 2, 2, 512, 512)
