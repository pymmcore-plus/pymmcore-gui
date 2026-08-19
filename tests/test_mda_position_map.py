from __future__ import annotations

import useq

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.actions import WidgetAction
from pymmcore_gui.widgets._mda_position_map import (
    MDAPositionMapWidget,
    PositionFootprint,
)


def _position_map(qtbot, positions=()):
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)
    mda_widget = gui.get_widget(WidgetAction.MDA_WIDGET)
    mda_widget.stage_positions.setValue(list(positions))
    widget = MDAPositionMapWidget(mda_widget=mda_widget, mmcore=gui._mmc)
    qtbot.addWidget(widget)
    return gui, widget, mda_widget


def test_position_map_starts_empty(qtbot) -> None:
    _gui, widget, _mda_widget = _position_map(qtbot)

    assert widget._collect_footprints() == []
    assert widget._position_items == {}
    assert widget._view._rect_to_row == {}
    assert widget._status.text() == "No MDA positions to display."


def test_position_map_collects_named_footprints(qtbot, monkeypatch) -> None:
    _gui, widget, mda_widget = _position_map(qtbot)
    monkeypatch.setattr(widget._mmc, "getImageWidth", lambda: 100)
    monkeypatch.setattr(widget._mmc, "getImageHeight", lambda: 50)
    monkeypatch.setattr(widget._mmc, "getPixelSizeUm", lambda: 0.5)

    mda_widget.stage_positions.setValue(
        [
            useq.Position(x=10.0, y=20.0, name="Inlet"),
            useq.Position(x=None, y=30.0, name="Skipped"),
            useq.Position(x=40.0, y=50.0),
        ]
    )
    widget.refresh()

    assert widget._collect_footprints() == [
        PositionFootprint(
            row=0,
            label="Inlet",
            x_um=10.0,
            y_um=20.0,
            width_um=50.0,
            height_um=25.0,
        ),
        PositionFootprint(
            row=1,
            label="Skipped",
            x_um=0.0,
            y_um=30.0,
            width_um=50.0,
            height_um=25.0,
        ),
        PositionFootprint(
            row=2,
            label="P3",
            x_um=40.0,
            y_um=50.0,
            width_um=50.0,
            height_um=25.0,
        ),
    ]
    assert set(widget._position_items) == {0, 1, 2}
    assert "3 position(s). FOV: 50.0 x 25.0 um" == widget._status.text()


def test_position_map_selects_table_row_from_rect(qtbot) -> None:
    _gui, widget, mda_widget = _position_map(qtbot)
    mda_widget.stage_positions.setValue(
        [
            useq.Position(x=10.0, y=20.0, name="Inlet"),
            useq.Position(x=40.0, y=50.0, name="Trap"),
        ]
    )
    widget.refresh()

    widget._select_row(1)

    table = mda_widget.stage_positions.table()
    assert table.currentRow() == 1
    assert widget._selected_rows() == {1}
    rect_item, label_item = widget._position_items[1]
    assert rect_item.pen().width() == 3
    assert label_item.brush().color().name().lower() == "#7c2d12"
