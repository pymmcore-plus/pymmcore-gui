from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from qtpy.QtWidgets import (
    QFileDialog,
    QPushButton,
    QWidget,
)
from superqt.fonticon import icon

if TYPE_CHECKING:
    from ndv import DataWrapper


class MDASaveButton(QPushButton):
    def __init__(
        self,
        data_wrapper: DataWrapper,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.setIcon(icon(MDI6.content_save_outline))
        self.clicked.connect(self._on_click)

        self._data_wrapper = data_wrapper
        self._last_loc = str(Path.home())

    def _on_click(self) -> None:
        # TODO: Add support for other file formats
        self._last_loc, _ = QFileDialog.getSaveFileName(
            self, "Choose destination", str(self._last_loc), ""
        )
        if not self._last_loc:
            return
        suffix = Path(self._last_loc).suffix
        if suffix in (".zarr", ".ome.zarr", ""):
            self._data_wrapper.save_as_zarr(self._last_loc)
        else:
            raise ValueError(f"File format not yet supported: {self._last_loc}")
