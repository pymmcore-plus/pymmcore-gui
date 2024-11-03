from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import tifffile
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QFileDialog, QPushButton, QSizePolicy
from superqt.fonticon import icon

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from micromanager_gui._widgets._viewers import Preview


class SaveButton(QPushButton):
    """Create a QPushButton to save Viewfinder data.

    TODO

    Parameters
    ----------
    viewfinder : Viewfinder | None
        The `Viewfinder` displaying the data to save.
    parent : QWidget | None
        Optional parent widget.

    """

    def __init__(
        self,
        viewer: Preview,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        self.setIcon(icon(MDI6.content_save_outline))

        self._viewer = viewer
        self._mmc = mmcore if mmcore is not None else CMMCorePlus.instance()

        self.clicked.connect(self._on_click)

    def _on_click(self) -> None:
        # TODO: Add support for other file formats
        # Stop sequence acquisitions
        self._mmc.stopSequenceAcquisition()

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "TIFF (*.tif *.tiff)"
        )
        if not path:
            return
        tifffile.imwrite(
            path,
            self._viewer.data_wrapper.isel({}),
            imagej=True,
            # description=self._image_preview._meta, # TODO: ome-tiff
        )
        # save meta as json
        dest = Path(path).with_suffix(".json")
        dest.write_text(json.dumps(self._viewer._meta))
