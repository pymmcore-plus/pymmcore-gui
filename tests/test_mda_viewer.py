from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
import useq
from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter, TensorStoreHandler
from pymmcore_plus.metadata import SummaryMetaV1
from pymmcore_widgets._stack_viewer_v2 import MDAViewer
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY

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

    # simulate that the core run_mda method was called
    gui._core_link._on_sequence_started(sequence=mda, meta=SummaryMetaV1())
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(1) == "MDA Viewer 1"
    assert gui._core_link._viewer_tab.currentIndex() == 1
    # simulate that the core run_mda method was called again
    gui._core_link._on_sequence_started(sequence=mda, meta=SummaryMetaV1())
    assert gui._core_link._viewer_tab.count() == 3
    assert gui._core_link._viewer_tab.tabText(2) == "MDA Viewer 2"
    assert gui._core_link._viewer_tab.currentIndex() == 2


writers = [
    ("tensorstore-zarr", "ts.tensorstore.zarr", TensorStoreHandler),
    ("ome-tiff", "t.ome.tiff", OMETiffWriter),
    ("ome-zarr", "z.ome.zarr", OMEZarrWriter),
]


@pytest.mark.parametrize("writers", writers)
def test_mda_viewer_saving(
    qtbot: QtBot,
    global_mmcore: CMMCorePlus,
    tmp_path: Path,
    writers: tuple[str, str, type],
    _run_after_each_test,
):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)

    file_format, save_name, writer = writers

    mda = useq.MDASequence(
        channels=["FITC", "DAPI"],
        metadata={
            PYMMCW_METADATA_KEY: {
                "format": file_format,
                "save_dir": str(tmp_path),
                "save_name": save_name,
                "should_save": True,
            }
        },
    )
    gui._menu_bar._mda.setValue(mda)

    # patch the run_mda method to avoid running the MDA sequence
    def _run_mda(seq):
        print("Running MDA")
        return True

    # set the writer attribute of the MDAWidget without running the MDA sequence
    with patch.object(global_mmcore, "run_mda", _run_mda):
        gui._menu_bar._mda.run_mda()
    # simulate that the core run_mda method was called
    gui._core_link._on_sequence_started(sequence=mda, meta=SummaryMetaV1())

    assert isinstance(gui._menu_bar._mda.writer, writer)
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(1) == save_name

    # saving datastore and MDAViewer datastore should be the same
    viewer = cast(MDAViewer, gui._core_link._viewer_tab.widget(1))
    assert viewer.data == gui._core_link._mda.writer
