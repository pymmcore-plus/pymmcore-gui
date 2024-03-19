from __future__ import annotations

from typing import TYPE_CHECKING

# import tifffile
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ImagePreview
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    # QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledDoubleRangeSlider
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._snap_and_live import Live, Snap

if TYPE_CHECKING:
    import numpy as np
    from qtpy.QtGui import QCloseEvent

BTN_SIZE = (60, 40)


class _ImagePreview(ImagePreview):
    """Subclass of ImagePreview.

    This subclass updates the LUT slider when the image is updated.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        preview_widget: Preview,
        use_with_mda: bool = False,
    ):
        super().__init__(parent=parent, mmcore=mmcore, use_with_mda=use_with_mda)

        self._preview_wdg = preview_widget

    def _update_image(self, image: np.ndarray) -> None:
        super()._update_image(image)

        if self.image is None:
            return

        with signals_blocked(self._preview_wdg._lut_slider):
            self._preview_wdg._lut_slider.setValue(self.image.clim)


class Preview(QWidget):
    """A widget containing an ImagePreview and buttons for image preview."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        canvas_size: tuple[int, int] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")

        self._mmc = mmcore or CMMCorePlus.instance()
        self._canvas_size = canvas_size

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # preview
        self._image_preview = _ImagePreview(self, mmcore=self._mmc, preview_widget=self)
        main_layout.addWidget(self._image_preview)

        # buttons
        btn_wdg = QGroupBox()
        btn_wdg_layout = QHBoxLayout(btn_wdg)
        btn_wdg_layout.setContentsMargins(0, 0, 0, 0)
        # auto contrast checkbox
        self._auto = QCheckBox("Auto")
        self._auto.setChecked(True)
        self._auto.setToolTip("Auto Contrast")
        self._auto.setFixedSize(*BTN_SIZE)
        self._auto.toggled.connect(self._clims_auto)
        # LUT slider
        self._lut_slider = QLabeledDoubleRangeSlider()
        self._lut_slider.setDecimals(0)
        self._lut_slider.valueChanged.connect(self._on_range_changed)
        # snap and live buttons
        self._snap = Snap(mmcore=self._mmc)
        self._snap.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._live = Live(mmcore=self._mmc)
        self._live.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # reset view button
        self._reset_view = QPushButton()
        self._reset_view.clicked.connect(self._reset)
        self._reset_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._reset_view.setToolTip("Reset View")
        self._reset_view.setIcon(icon(MDI6.home_outline))
        self._reset_view.setIconSize(QSize(25, 25))
        self._reset_view.setFixedSize(*BTN_SIZE)
        # save button
        # self._save = QPushButton()
        # self._save.clicked.connect(self._on_save)
        # self._save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self._save.setToolTip("Save Image")
        # self._save.setIcon(icon(MDI6.content_save_outline))
        # self._save.setIconSize(QSize(25, 25))
        # self._save.setFixedSize(*BTN_SIZE)

        btn_wdg_layout.addWidget(self._lut_slider)
        btn_wdg_layout.addWidget(self._auto)
        btn_wdg_layout.addWidget(self._snap)
        btn_wdg_layout.addWidget(self._live)
        btn_wdg_layout.addWidget(self._reset_view)
        # btn_wdg_layout.addWidget(self._save)
        main_layout.addWidget(btn_wdg)

        self._reset()
        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        """Update the LUT slider range and the canvas size."""
        # update the LUT slider range
        if bit := self._mmc.getImageBitDepth():
            with signals_blocked(self._lut_slider):
                self._lut_slider.setRange(0, 2**bit - 1)
                self._lut_slider.setValue((0, 2**bit - 1))

        # set the canvas size to half of the image size
        self._image_preview._canvas.size = self._canvas_size or (
            int(self._mmc.getImageWidth()),
            int(self._mmc.getImageHeight()),
        )

    def _reset(self) -> None:
        """Reset the preview."""
        x = (0, self._mmc.getImageWidth()) if self._mmc.getImageWidth() else None
        y = (0, self._mmc.getImageHeight()) if self._mmc.getImageHeight() else None
        self._image_preview.view.camera.set_range(x, y, margin=0)

    def _on_range_changed(self, range: tuple[float, float]) -> None:
        """Update the LUT range."""
        self._image_preview.clims = range
        self._auto.setChecked(False)

    def _clims_auto(self, state: bool) -> None:
        """Set the LUT range to auto."""
        self._image_preview.clims = "auto" if state else self._lut_slider.value()
        if self._image_preview.image is not None:
            data = self._image_preview.image._data
            with signals_blocked(self._lut_slider):
                self._lut_slider.setValue((data.min(), data.max()))

    # def _on_save(self) -> None:
    #     """Save the image as tif."""
    #     # TODO: add metadata
    #     if self._image_preview.image is None:
    #         return
    #     path, _ = QFileDialog.getSaveFileName(
    #         self, "Save Image", "", "TIFF (*.tif *.tiff)"
    #     )
    #     if not path:
    #         return
    #     tifffile.imwrite(path, self._image_preview.image._data, imagej=True)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        # stop live acquisition if running
        if self._mmc.isSequenceRunning():
            self._mmc.stopSequenceAcquisition()
        super().closeEvent(event)
