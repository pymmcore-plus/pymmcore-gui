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

from ._data_wrappers import MM5DWriterWrapper, MMTensorstoreWrapper

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
        self._last_loc, _ = QFileDialog.getSaveFileName(
            self,
            "Choose destination",
            str(self._last_loc),
            "TIFF (*.tif *.tiff);;ZARR (*.zarr)",
        )
        if not self._last_loc:
            return
        suffix = Path(self._last_loc).suffix
        if suffix == ".zarr":
            self._data_wrapper.save_as_zarr(self._last_loc)
        elif suffix in {".tif", ".tiff"} and isinstance(
            self._data_wrapper, (MMTensorstoreWrapper, MM5DWriterWrapper)
        ):
            self._data_wrapper.save_as_tiff(self._last_loc)
        else:
            raise ValueError(f"File format not yet supported: {self._last_loc}")
