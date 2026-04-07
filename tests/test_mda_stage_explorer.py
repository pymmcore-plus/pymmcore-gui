from __future__ import annotations

import numpy as np
import useq

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.actions import WidgetAction
from pymmcore_gui.widgets._chip_dxf import ChipCurve, ChipOverlayData
from pymmcore_gui.widgets._mda_stage_explorer import MDALinkedStageExplorer


def test_stage_explorer_binds_to_existing_mda_widget(qtbot) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)
    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)

    assert isinstance(explorer, MDALinkedStageExplorer)
    assert explorer._mda_widget is mda_widget


def test_stage_explorer_tracks_mda_positions(qtbot) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)

    mda_widget.stage_positions.setValue(
        [
            useq.Position(x=100.0, y=200.0, name="Inlet"),
            useq.Position(x=350.0, y=500.0, name="Trap A"),
        ]
    )
    qtbot.wait(10)

    assert [p.row for p in explorer._mda_positions] == [0, 1]
    assert [p.name for p in explorer._mda_positions] == ["Inlet", "Trap A"]
    assert set(explorer._mda_overlays) == {0, 1}


def test_stage_explorer_tracks_selected_mda_row(qtbot) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)

    mda_widget.stage_positions.setValue(
        [
            useq.Position(x=100.0, y=200.0, name="Inlet"),
            useq.Position(x=350.0, y=500.0, name="Trap A"),
        ]
    )
    qtbot.wait(10)

    table = mda_widget.stage_positions.table()
    table.clearSelection()
    table.selectRow(1)
    qtbot.wait(10)

    assert explorer._selected_row == 1


def test_stage_explorer_tracks_active_mda_position_from_frame_ready(qtbot) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)

    mda_widget.stage_positions.setValue(
        [
            useq.Position(x=100.0, y=200.0, name="Inlet"),
            useq.Position(x=350.0, y=500.0, name="Trap A"),
        ]
    )
    qtbot.wait(10)

    event = useq.MDAEvent(x_pos=350.0, y_pos=500.0, pos_name="Trap A")
    explorer._on_frame_ready(np.zeros((16, 16), dtype=np.uint16), event)

    assert explorer._active_row == 1

    explorer._on_mda_finished(useq.MDASequence())
    assert explorer._active_row is None


def test_stage_explorer_calibrates_chip_overlay_by_translation(
    qtbot, monkeypatch
) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    assert isinstance(explorer, MDALinkedStageExplorer)

    explorer._chip_overlay_data = ChipOverlayData(
        curves=[
            ChipCurve(
                points=np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 50.0]], dtype=float)
            )
        ],
        reference_points=[(0.0, 0.0), (100.0, 50.0)],
        source=None,  # type: ignore[arg-type]
    )
    explorer._chip_selected_reference = (0.0, 0.0)
    monkeypatch.setattr(explorer._mmc, "getXYStageDevice", lambda: "XY")
    monkeypatch.setattr(explorer._mmc, "getXYPosition", lambda: (250.0, 400.0))
    explorer._set_chip_reference_to_current_stage()

    np.testing.assert_allclose(explorer._chip_stage_offset_um, np.array([250.0, 400.0]))
