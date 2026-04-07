from __future__ import annotations

from types import SimpleNamespace

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


def test_stage_explorer_matches_events_to_positions(qtbot) -> None:
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

    assert explorer._match_event_to_position(useq.MDAEvent(pos_name="Trap A")) == 1
    assert explorer._match_event_to_position(useq.MDAEvent(x_pos=101, y_pos=201)) == 0
    assert (
        explorer._match_event_to_position(useq.MDAEvent(x_pos=9999, y_pos=9999)) is None
    )
    assert explorer._match_event_to_position(useq.MDAEvent()) is None


def test_stage_explorer_toggles_mda_overlays(qtbot) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)
    mda_widget.stage_positions.setValue([useq.Position(x=100.0, y=200.0, name="P1")])
    qtbot.wait(10)
    assert explorer._mda_overlays

    explorer._set_mda_overlays_visible(False)
    assert explorer._mda_overlays == {}

    explorer._set_mda_overlays_visible(True)
    assert explorer._mda_overlays

    explorer.set_mda_widget(None)
    assert explorer._mda_widget is None
    assert explorer._mda_overlays == {}


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


def test_stage_explorer_chip_reference_helpers(qtbot) -> None:
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
    explorer._chip_stage_offset_um = np.array([10.0, 20.0], dtype=float)

    assert explorer._nearest_chip_reference(12.0, 21.0) == (0.0, 0.0)
    assert explorer._nearest_chip_reference(111.0, 72.0) == (100.0, 50.0)

    explorer._chip_selected_reference = (100.0, 50.0)
    curves = explorer._chip_curves_in_stage_coordinates()
    np.testing.assert_allclose(curves[0].points[0], np.array([10.0, 20.0]))

    explorer._reset_chip_reference()
    assert explorer._chip_selected_reference is None
    np.testing.assert_allclose(explorer._chip_stage_offset_um, np.zeros(2))


def test_stage_explorer_mouse_press_selects_position(qtbot, monkeypatch) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)
    mda_widget.stage_positions.setValue([useq.Position(x=100.0, y=200.0, name="P1")])
    qtbot.wait(10)

    monkeypatch.setattr(
        explorer._stage_viewer, "canvas_to_world", lambda pos: (100.0, 200.0)
    )

    explorer._on_mouse_press(SimpleNamespace(pos=(0, 0), button=1))

    assert explorer._selected_row == 0
    assert (
        mda_widget.stage_positions.table().selectionModel().selectedRows()[0].row() == 0
    )


def test_stage_explorer_mouse_press_picks_chip_reference(qtbot, monkeypatch) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    explorer = gui.get_widget(WidgetAction.STAGE_EXPLORER)
    explorer._chip_overlay_data = ChipOverlayData(
        curves=[],
        reference_points=[(10.0, 20.0)],
        source=None,  # type: ignore[arg-type]
    )
    explorer._calibration_pick_mode = True
    explorer._pick_chip_ref_action.setChecked(True)
    monkeypatch.setattr(
        explorer._stage_viewer, "canvas_to_world", lambda pos: (10.0, 20.0)
    )

    explorer._on_mouse_press(SimpleNamespace(pos=(0, 0), button=1))

    assert explorer._chip_selected_reference == (10.0, 20.0)
    assert not explorer._pick_chip_ref_action.isChecked()
