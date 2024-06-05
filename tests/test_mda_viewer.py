from __future__ import annotations

from typing import TYPE_CHECKING

import useq

# from pymmcore_plus.mda.handlers import TensorStoreHandler
# from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from micromanager_gui import MicroManagerGUI

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_mda_viewer_no_saving(
    qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path, _run_after_each_test
):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)

    mda = useq.MDASequence(channels=["DAPI", "FITC"])
    with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
        global_mmcore.mda.run(mda)
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(1) == "MDA Viewer 1"
    assert gui._core_link._viewer_tab.currentIndex() == 1

    with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
        global_mmcore.mda.run(mda)
    assert gui._core_link._viewer_tab.count() == 3
    assert gui._core_link._viewer_tab.tabText(1) == "MDA Viewer 2"
    assert gui._core_link._viewer_tab.currentIndex() == 2


# def test_mda_viewer_saving(
#     qtbot: QtBot, global_mmcore: CMMCorePlus, tmp_path: Path, _run_after_each_test
# ):
#     gui = MicroManagerGUI(mmcore=global_mmcore)
#     qtbot.addWidget(gui)

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
#     assert gui._core_link._viewer_tab.count() == 2
#     assert gui._core_link._viewer_tab.tabText(1) == "t.tensorstore.zarr"

#     # saving tensorstore and MDAViewer datastore should be the same
#     assert gui._core_link._mda.writer == gui._core_link._viewer_tab.widget(1)._data
#     gui._menu_bar._close_all()
