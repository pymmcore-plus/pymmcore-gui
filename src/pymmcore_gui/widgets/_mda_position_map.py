from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QItemSelectionModel, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pymmcore_widgets.mda._core_mda import MDAWidget
    from qtpy.QtCore import QItemSelection
    from useq import Position


@dataclass(slots=True)
class PositionFootprint:
    row: int
    label: str
    x_um: float
    y_um: float
    width_um: float
    height_um: float


class _MapView(QGraphicsView):
    rectClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._rect_to_row: dict[QGraphicsItem, int] = {}

    def clear_rect_mapping(self) -> None:
        self._rect_to_row.clear()

    def register_rect(self, item: QGraphicsItem, row: int) -> None:
        self._rect_to_row[item] = row

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None:
                if item in self._rect_to_row:
                    self.rectClicked.emit(self._rect_to_row[item])
                    break
                item = item.parentItem()
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class MDAPositionMapWidget(QWidget):
    """Experimental XY overview of positions currently defined in the MDA widget."""

    def __init__(
        self,
        *,
        mda_widget: MDAWidget,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("MDA Position Map")

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mda_widget = mda_widget
        self._scene = QGraphicsScene(self)
        self._view = _MapView(self)
        self._view.setScene(self._scene)
        self._view.rectClicked.connect(self._select_row)

        self._status = QLabel(self)
        self._status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._status, 0)

        self._position_items: dict[
            int, tuple[QGraphicsRectItem, QGraphicsSimpleTextItem]
        ] = {}
        self._selection_model: QItemSelectionModel | None = None

        self._mda_widget.valueChanged.connect(self.refresh)
        self._mmc.events.systemConfigurationLoaded.connect(self.refresh)
        self._mmc.events.roiSet.connect(self.refresh)
        self._mmc.events.pixelSizeChanged.connect(self.refresh)
        self._attach_selection_model()
        self.refresh()

    def refresh(self) -> None:
        self._attach_selection_model()
        self._scene.clear()
        self._view.clear_rect_mapping()
        self._position_items.clear()

        footprints = self._collect_footprints()
        if not footprints:
            self._status.setText("No MDA positions to display.")
            return

        self._status.setText(
            f"{len(footprints)} position(s). FOV: {footprints[0].width_um:.1f} x {footprints[0].height_um:.1f} um"
        )

        for footprint in footprints:
            rect = QRectF(
                footprint.x_um - footprint.width_um / 2,
                footprint.y_um - footprint.height_um / 2,
                footprint.width_um,
                footprint.height_um,
            )
            rect_item = QGraphicsRectItem(rect)
            rect_item.setPen(QPen(QColor("#2F7D32"), 2))
            rect_item.setBrush(QColor(47, 125, 50, 35))
            rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._scene.addItem(rect_item)
            self._view.register_rect(rect_item, footprint.row)

            label_item = QGraphicsSimpleTextItem(footprint.label)
            label_item.setBrush(QColor("#1F2937"))
            label_item.setPos(rect.left() + 8, rect.top() + 8)
            self._scene.addItem(label_item)

            self._position_items[footprint.row] = (rect_item, label_item)

        margin = max(footprints[0].width_um, footprints[0].height_um) * 0.5
        self._scene.setSceneRect(
            self._scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)
        )
        self._view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self._update_selection_highlight()

    def _attach_selection_model(self) -> None:
        table = self._mda_widget.stage_positions.table()
        selection_model = table.selectionModel()
        if selection_model is self._selection_model or selection_model is None:
            return
        if self._selection_model is not None:
            try:
                self._selection_model.selectionChanged.disconnect(
                    self._on_selection_changed
                )
            except (RuntimeError, TypeError):
                pass
        self._selection_model = selection_model
        self._selection_model.selectionChanged.connect(self._on_selection_changed)

    def _collect_footprints(self) -> list[PositionFootprint]:
        positions = cast(
            "Sequence[Position]",
            self._mda_widget.stage_positions.value(
                exclude_unchecked=False, exclude_hidden_cols=True
            ),
        )
        width_um, height_um = self._fov_size_um()
        footprints: list[PositionFootprint] = []
        for row, pos in enumerate(positions):
            if pos.x is None or pos.y is None:
                continue
            footprints.append(
                PositionFootprint(
                    row=row,
                    label=pos.name or f"P{row + 1}",
                    x_um=pos.x,
                    y_um=pos.y,
                    width_um=width_um,
                    height_um=height_um,
                )
            )
        return footprints

    def _fov_size_um(self) -> tuple[float, float]:
        px = self._mmc.getPixelSizeUm()
        if px <= 0:
            px = 1.0
        return self._mmc.getImageWidth() * px, self._mmc.getImageHeight() * px

    def _selected_rows(self) -> set[int]:
        if self._selection_model is None:
            return set()
        return {index.row() for index in self._selection_model.selectedRows()}

    def _select_row(self, row: int) -> None:
        table = self._mda_widget.stage_positions.table()
        model = table.selectionModel()
        if model is None:
            return
        idx = table.model().index(row, 0)
        flags = cast(
            "QItemSelectionModel.SelectionFlags",
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        model.select(idx, flags)
        table.setCurrentCell(row, 0)

    def _on_selection_changed(
        self, _selected: QItemSelection, _deselected: QItemSelection
    ) -> None:
        self._update_selection_highlight()

    def _update_selection_highlight(self) -> None:
        selected = self._selected_rows()
        for row, (rect_item, label_item) in self._position_items.items():
            if row in selected:
                rect_item.setPen(QPen(QColor("#D9480F"), 3))
                rect_item.setBrush(QColor(217, 72, 15, 60))
                label_item.setBrush(QColor("#7C2D12"))
            else:
                rect_item.setPen(QPen(QColor("#2F7D32"), 2))
                rect_item.setBrush(QColor(47, 125, 50, 35))
                label_item.setBrush(QColor("#1F2937"))
