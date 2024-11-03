from __future__ import annotations

from os import path
from typing import TYPE_CHECKING

import tifffile
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import LiveButton, SnapButton
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QFileDialog, QPushButton, QSizePolicy
from superqt.fonticon import icon

if TYPE_CHECKING:
    from ndv import NDViewer
    from qtpy.QtWidgets import QWidget

BTN_SIZE = 30
ICON_SIZE = QSize(25, 25)


class Snap(SnapButton):
    """A SnapButton."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)
        self.setToolTip("Snap Image")
        self.setIcon(icon(MDI6.camera_outline))
        self.setText("")
        self.setFixedWidth(BTN_SIZE)
        self.setIconSize(ICON_SIZE)


class Live(LiveButton):
    """A LiveButton."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)
        self.setToolTip("Live Mode")
        self.button_text_on = ""
        self.button_text_off = ""
        self.icon_color_on = ()
        self.icon_color_off = "#C33"
        self.setFixedWidth(BTN_SIZE)
        self.setIconSize(ICON_SIZE)


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
        viewer: NDViewer,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        self._viewer = viewer
        self._mmc = mmcore if mmcore is not None else CMMCorePlus.instance()

        self._create_button()

    def _create_button(self) -> None:
        self.setIcon(icon(MDI6.content_save))
        self.setIconSize(ICON_SIZE)
        self.setFixedWidth(BTN_SIZE)

        self.clicked.connect(self._save_data)

    def _save_data(self) -> None:
        # Stop sequence acquisitions
        self._mmc.stopSequenceAcquisition()

        (file, _) = QFileDialog.getSaveFileName(
            self._viewer,
            "Save Image",
            "",  #
            "*.tif",  # Acceptable extensions
        )
        (p, extension) = path.splitext(file)
        if extension == ".tif":
            data = self._viewer.data_wrapper.isel({})
            # TODO: Save metadata?
            tifffile.imwrite(file, data=data)
        # TODO: Zarr seems like it would be easily supported through
        # self._view.data_wrapper.save_as_zarr, but it is not implemented
        # by TensorStoreWrapper
