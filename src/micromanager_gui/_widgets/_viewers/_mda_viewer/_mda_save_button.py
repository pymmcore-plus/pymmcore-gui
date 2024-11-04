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

from ._data_wrappers import MMTensorstoreWrapper

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
        # TODO: add support for MM5DWriterWrapper. Ath the moment the MDAViewer will
        # only show the save button if a pymmcore_plus.mda.handlers.TensorStoreHandler
        # is used (and thus the MMTensorstoreWrapper)
        if not isinstance(self._data_wrapper, MMTensorstoreWrapper):
            raise ValueError(
                "Only `MMTensorstoreWrapper` data wrappers are currently supported."
            )

        self._last_loc, _ = QFileDialog.getSaveFileName(
            self,
            "Choose destination",
            str(self._last_loc),
            "TIFF (*.tif *.tiff);;Zarr (*.zarr)",
        )
        if not self._last_loc:
            return
        suffix = Path(self._last_loc).suffix
        if suffix == ".zarr":
            self._data_wrapper.save_as_zarr(self._last_loc)
        elif suffix in {".tif", ".tiff"}:
            self._data_wrapper.save_as_tiff(self._last_loc)
        else:
            raise ValueError(f"File format not yet supported: {self._last_loc}")
