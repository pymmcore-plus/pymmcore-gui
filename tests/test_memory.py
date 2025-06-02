from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from pymmcore_gui import MicroManagerGUI

if TYPE_CHECKING:
    from collections.abc import Iterator

    from PyQt6.QtWidgets import QApplication
    from pytestqt.qtbot import QtBot


@pytest.fixture
def gui(qtbot: QtBot, qapp: QApplication) -> Iterator[MicroManagerGUI]:
    gui = MicroManagerGUI()
    # exclude this from memory leak checks
    gui.mmcore.initializeCircularBuffer()
    qtbot.addWidget(gui)
    yield gui


@pytest.mark.limit_leaks("10 MB")
def test_memory_main_window(qapp: QApplication) -> None:
    for _i in range(5):
        gui = MicroManagerGUI()
        gui.close()
        gui.deleteLater()
        qapp.processEvents()


@pytest.mark.limit_leaks("0.7 MB")
def test_memory_ndv_preview(gui: MicroManagerGUI, qapp: QApplication) -> None:
    core = gui.mmcore
    dm = gui.dock_manager
    for _i in range(5):
        core.startContinuousSequenceAcquisition()
        while core.getRemainingImageCount() < 5:
            time.sleep(0.01)
        core.stopSequenceAcquisition()
        assert core.getRemainingImageCount() >= 5
        assert not core.isSequenceRunning()

        # close the tab with the same path that a user would use by clicking
        # the 'x' button on the tab
        if dw := dm.dockWidgetsMap().get("Preview"):
            if tb := dw.tabWidget():
                tb.closeRequested.emit()
        qapp.processEvents()
        qapp.processEvents()
