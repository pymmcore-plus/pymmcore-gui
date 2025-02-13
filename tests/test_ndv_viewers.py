from __future__ import annotations

import datetime
import gc
from typing import TYPE_CHECKING

import pytest
import useq
from PyQt6.QtWidgets import QApplication, QWidget
from useq import MDASequence

from pymmcore_gui._ndv_viewers import NDVViewersManager

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_viewers_manager(mmcore: CMMCorePlus, qtbot: QtBot) -> None:
    """Ensure that the viewers manager creates and cleans up viewers during MDA."""
    dummy = QWidget()
    manager = NDVViewersManager(dummy, mmcore)

    assert len(manager) == 0
    mmcore.mda.run(
        MDASequence(
            time_plan=useq.TIntervalLoops(
                interval=datetime.timedelta(seconds=0.1), loops=2
            ),
            channels=["DAPI", "FITC"],  # pyright: ignore
            z_plan=useq.ZRangeAround(range=4, step=1),
        ),
    )
    assert len(manager) == 1

    with qtbot.waitSignal(dummy.destroyed, timeout=1000):
        dummy.deleteLater()
    QApplication.processEvents()
    gc.collect()
    if len(manager):
        for viewer in manager.viewers():
            if "vispy" in type(viewer._canvas).__name__.lower():
                # don't even bother... vispy is a mess of hard references
                del viewer._canvas
                del viewer._histogram
                continue
            referrers = gc.get_referrers(viewer)[1:]
            pytest.fail(f"Viewer {viewer} not deleted. Still referenced by {referrers}")
