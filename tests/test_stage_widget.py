from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_gui._widgets._stage_control import StagesControlWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.mark.usefixtures("check_leaks")
def test_stage_widget(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    s = StagesControlWidget(mmcore=global_mmcore)
    qtbot.addWidget(s)
    group1 = s._layout.takeAt(0).widget()
    group2 = s._layout.takeAt(0).widget()
    assert group1.title() == "XY"
    assert group2.title() == "Z"
    global_mmcore.loadSystemConfiguration()
    global_mmcore.loadSystemConfiguration()
