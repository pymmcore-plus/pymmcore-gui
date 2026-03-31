from __future__ import annotations

import csv

import numpy as np

from pymmcore_gui._qt.QtGui import QKeyEvent, QKeySequence
from pymmcore_gui._qt.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _CopyableTable(QTableWidget):
    def keyPressEvent(self, event: QKeyEvent) -> None:
        super().keyPressEvent(event)
        if event.matches(QKeySequence.StandardKey.Copy):
            selection = self.selectedRanges()
            if not selection:
                return
            sr = selection[0]
            rows = []
            for r in range(sr.topRow(), sr.bottomRow() + 1):
                cells = []
                for c in range(sr.leftColumn(), sr.rightColumn() + 1):
                    item = self.item(r, c)
                    cells.append(item.text() if item else "")
                rows.append("\t".join(cells))
            QApplication.clipboard().setText("\n".join(rows))
        else:
            super().keyPressEvent(event)


class MeasurementTable(QWidget):
    """Table widget for displaying ROI statistics."""

    HEADERS = ("Min", "Max", "Mean", "Std", "Area")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = _CopyableTable()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        clear_btn = QPushButton("Clear")
        save_btn = QPushButton("Save")
        clear_btn.clicked.connect(self._clear)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(btn_layout)
        layout.addWidget(self.table)

        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        if header := self.table.horizontalHeader():
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setMinimumSectionSize(70)
            header.setMaximumSectionSize(160)

    def _clear(self) -> None:
        self.table.setRowCount(0)

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.HEADERS)
            for r in range(self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    row.append(item.text() if item else "")
                writer.writerow(row)

    def add_stats(self, array: np.ndarray) -> None:
        """Calculate stats for *array* and add them as a new row."""
        stats = (
            np.min(array),
            np.max(array),
            np.mean(array),
            np.std(array),
            array.size,
        )
        row = self.table.rowCount()
        self.table.insertRow(row)
        for c, stat in enumerate(stats):
            item = self.table.item(row, c)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, c, item)
            item.setText(f"{stat:.4g}")
