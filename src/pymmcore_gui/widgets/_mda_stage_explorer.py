from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import useq
from pymmcore_widgets import StageExplorer
from pymmcore_widgets.control._stage_explorer._stage_position_marker import (
    StagePositionMarker,
)
from pymmcore_widgets.control._stage_explorer._stage_viewer import get_vispy_scene_bounds
from vispy.color import Color
from vispy.scene.visuals import Text

from pymmcore_gui._qt.QtCore import QTimer, Qt

if TYPE_CHECKING:
    from vispy.app.canvas import MouseEvent

    from pymmcore_gui.actions.widget_actions import MDAWidget


@dataclass(slots=True)
class MDAStagePosition:
    row: int
    x: float
    y: float
    name: str
    enabled: bool


class MDALinkedStageExplorer(StageExplorer):
    """StageExplorer extension that mirrors positions from an MDAWidget."""

    _MDA_NORMAL = "#3FA7FF"
    _MDA_SELECTED = "#FFB020"
    _MDA_ACTIVE = "#22C55E"
    _MDA_DISABLED = "#7F8C8D"

    def __init__(self, parent=None, mmcore=None):
        super().__init__(parent=parent, mmcore=mmcore)
        self._mda_widget: MDAWidget | None = None
        self._mda_positions: list[MDAStagePosition] = []
        self._selected_row: int | None = None
        self._active_row: int | None = None
        self._mda_overlays: dict[int, tuple[StagePositionMarker, Text]] = {}
        self._refresh_pending = False

        self._show_mda_positions = self._toolbar.addAction("Show MDA Positions")
        self._show_mda_positions.setCheckable(True)
        self._show_mda_positions.setChecked(True)
        self._show_mda_positions.toggled.connect(self._set_mda_overlays_visible)

        self._zoom_to_mda_positions = self._toolbar.addAction("Zoom to MDA Positions")
        self._zoom_to_mda_positions.triggered.connect(self.zoom_to_mda_positions)

        self._stage_viewer.canvas.events.mouse_press.connect(self._on_mouse_press)
        self._mmc.events.roiSet.connect(self.refresh_mda_positions)
        self._mmc.events.pixelSizeChanged.connect(self._on_mda_geometry_changed)
        self._mmc.events.pixelSizeAffineChanged.connect(self.refresh_mda_positions)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

    def set_mda_widget(self, mda_widget: MDAWidget | None) -> None:
        if mda_widget is self._mda_widget:
            return
        self._disconnect_mda_widget()
        self._mda_widget = mda_widget
        if mda_widget is None:
            self._clear_mda_overlays()
            return

        table = mda_widget.stage_positions.table()
        mda_widget.stage_positions.valueChanged.connect(self.schedule_mda_refresh)
        table.itemSelectionChanged.connect(self._sync_selection_from_table)
        if model := table.model():
            model.dataChanged.connect(self.schedule_mda_refresh)
            model.rowsInserted.connect(self.schedule_mda_refresh)
            model.rowsRemoved.connect(self.schedule_mda_refresh)
            model.modelReset.connect(self.schedule_mda_refresh)
        self.schedule_mda_refresh()
        self._sync_selection_from_table()

    def schedule_mda_refresh(self, *_args) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self.refresh_mda_positions)

    def refresh_mda_positions(self, *_args) -> None:
        self._refresh_pending = False
        self._clear_mda_overlays()
        if self._mda_widget is None or not self._show_mda_positions.isChecked():
            return

        try:
            table = self._mda_widget.stage_positions.table()
            name_col = table.indexOf(self._mda_widget.stage_positions.NAME)
            x_key = self._mda_widget.stage_positions.X.key
            y_key = self._mda_widget.stage_positions.Y.key
        except RuntimeError:
            return

        positions: list[MDAStagePosition] = []
        for row in range(table.rowCount()):
            data = table.rowData(row, exclude_hidden_cols=True)
            x = data.get(x_key)
            y = data.get(y_key)
            if x is None or y is None:
                continue

            name_item = table.item(row, name_col)
            name = name_item.text() if name_item and name_item.text() else f"P{row + 1}"
            enabled = True
            if name_item is not None and bool(name_item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                enabled = name_item.checkState() != Qt.CheckState.Unchecked

            positions.append(
                MDAStagePosition(
                    row=row,
                    x=float(x),
                    y=float(y),
                    name=name,
                    enabled=enabled,
                )
            )

        self._mda_positions = positions
        if self._active_row not in {p.row for p in positions}:
            self._active_row = None
        self._rebuild_mda_overlays()
        self._sync_selection_from_table()

    def zoom_to_mda_positions(self) -> None:
        if not self._mda_overlays:
            return
        visuals = [marker for marker, _text in self._mda_overlays.values()]
        x_bounds, y_bounds, *_ = get_vispy_scene_bounds(visuals)
        self._stage_viewer.view.camera.set_range(x=x_bounds, y=y_bounds, margin=0.08)

    def _on_mda_geometry_changed(self, _value: float) -> None:
        self.refresh_mda_positions()

    def _disconnect_mda_widget(self) -> None:
        if self._mda_widget is None:
            return
        table = self._mda_widget.stage_positions.table()
        with suppress(Exception):
            self._mda_widget.stage_positions.valueChanged.disconnect(
                self.schedule_mda_refresh
            )
        with suppress(Exception):
            table.itemSelectionChanged.disconnect(self._sync_selection_from_table)
        if model := table.model():
            with suppress(Exception):
                model.dataChanged.disconnect(self.schedule_mda_refresh)
            with suppress(Exception):
                model.rowsInserted.disconnect(self.schedule_mda_refresh)
            with suppress(Exception):
                model.rowsRemoved.disconnect(self.schedule_mda_refresh)
            with suppress(Exception):
                model.modelReset.disconnect(self.schedule_mda_refresh)

    def _clear_mda_overlays(self) -> None:
        for marker, label in self._mda_overlays.values():
            marker.parent = None
            label.parent = None
        self._mda_overlays.clear()

    def _rebuild_mda_overlays(self) -> None:
        if not self._mda_positions:
            return

        img_w = self._mmc.getImageWidth() or 1
        img_h = self._mmc.getImageHeight() or 1
        _, fov_h = self._fov_w_h()
        label_offset = max(fov_h * 0.55, 25.0)

        for pos in self._mda_positions:
            color = self._MDA_NORMAL if pos.enabled else self._MDA_DISABLED
            marker = StagePositionMarker(
                parent=self._stage_viewer.view.scene,
                rect_width=img_w,
                rect_height=img_h,
                rect_color=color,
                marker_symbol_color=color,
                marker_symbol_size=max(min(img_w, img_h) / 12, 6),
            )
            marker.apply_transform(
                self._affine_state.system_affine_translated(pos.x, pos.y).T
            )
            marker.visible = True

            label = Text(
                text=pos.name,
                pos=(pos.x, pos.y + label_offset),
                color=Color(color),
                font_size=10,
                anchor_x="center",
                anchor_y="bottom",
                parent=self._stage_viewer.view.scene,
            )
            self._mda_overlays[pos.row] = (marker, label)

    def _set_mda_overlays_visible(self, visible: bool) -> None:
        if not visible:
            self._clear_mda_overlays()
            return
        self.refresh_mda_positions()

    def _sync_selection_from_table(self) -> None:
        self._selected_row = None
        if self._mda_widget is None:
            return

        selected_rows = {
            idx.row() for idx in self._mda_widget.stage_positions.table().selectedIndexes()
        }
        self._selected_row = next(iter(selected_rows), None) if len(selected_rows) == 1 else None
        self._update_overlay_styles()

    def _update_overlay_styles(self) -> None:
        for pos in self._mda_positions:
            marker, label = self._mda_overlays.get(pos.row, (None, None))
            if marker is None or label is None:
                continue

            if pos.row == self._active_row:
                color = self._MDA_ACTIVE
            elif pos.row == self._selected_row:
                color = self._MDA_SELECTED
            elif pos.enabled:
                color = self._MDA_NORMAL
            else:
                color = self._MDA_DISABLED

            marker._rect.border_color = Color(color)
            marker._marker.set_data(
                pos=np.array([[0.0, 0.0]], dtype=float),
                symbol="++",
                face_color=Color(color),
                edge_color=Color(color),
                size=max(min(self._mmc.getImageWidth() or 1, self._mmc.getImageHeight() or 1) / 12, 6),
                edge_width=2,
            )
            label.color = Color(color)
            marker.update()
            label.update()

    def _set_active_row(self, row: int | None) -> None:
        if row == self._active_row:
            return
        self._active_row = row
        self._update_overlay_styles()

    def _match_event_to_position(self, event: useq.MDAEvent) -> int | None:
        if not self._mda_positions:
            return None

        if event.pos_name:
            for pos in self._mda_positions:
                if pos.name == event.pos_name:
                    return pos.row

        if event.x_pos is None or event.y_pos is None:
            return None

        nearest = self._nearest_position(float(event.x_pos), float(event.y_pos))
        return nearest.row if nearest is not None else None

    def _nearest_position(self, world_x: float, world_y: float) -> MDAStagePosition | None:
        if not self._mda_positions:
            return None
        fov_w, fov_h = self._fov_w_h()
        hit_radius = max(fov_w, fov_h) * 0.6

        nearest: tuple[float, MDAStagePosition] | None = None
        for pos in self._mda_positions:
            dx = world_x - pos.x
            dy = world_y - pos.y
            dist2 = dx * dx + dy * dy
            if dist2 > hit_radius * hit_radius:
                continue
            if nearest is None or dist2 < nearest[0]:
                nearest = (dist2, pos)
        return nearest[1] if nearest is not None else None

    def _on_mouse_press(self, event: MouseEvent) -> None:
        if self._mda_widget is None or not self._show_mda_positions.isChecked():
            return
        if getattr(event, "button", None) not in (1,):
            return

        world_x, world_y = self._stage_viewer.canvas_to_world(event.pos)
        pos = self._nearest_position(world_x, world_y)
        if pos is None:
            return

        table = self._mda_widget.stage_positions.table()
        table.clearSelection()
        table.selectRow(pos.row)
        self._selected_row = pos.row
        self._update_overlay_styles()

    def _on_mouse_double_click(self, event: MouseEvent) -> None:
        if self._mda_widget is not None and self._show_mda_positions.isChecked():
            world_x, world_y = self._stage_viewer.view.camera.transform.imap(event.pos)[:2]
            pos = self._nearest_position(float(world_x), float(world_y))
            if pos is not None and self._stage_controller is not None:
                self._stage_controller.move_absolute((pos.x, pos.y))
                self._stage_controller.snap_on_finish = self._snap_on_double_click
                self._stage_pos_label.setText(f"X: {pos.x:.2f} um  Y: {pos.y:.2f} um")
                return
        super()._on_mouse_double_click(event)

    def _on_frame_ready(self, image: np.ndarray, event: useq.MDAEvent) -> None:
        super()._on_frame_ready(image, event)
        self._set_active_row(self._match_event_to_position(event))

    def _on_mda_finished(self, _sequence: useq.MDASequence) -> None:
        self._set_active_row(None)

    def closeEvent(self, event) -> None:
        self._disconnect_mda_widget()
        self._clear_mda_overlays()
        super().closeEvent(event)
