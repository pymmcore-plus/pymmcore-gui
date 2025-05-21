from __future__ import annotations

from typing import TYPE_CHECKING

import ndv
from ndv.models import RingBuffer
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase

if TYPE_CHECKING:
    import numpy as np
    import rendercanvas.qt
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]


class NDVPreview(ImagePreviewBase):
    def __init__(
        self,
        mmcore: CMMCorePlus,
        parent: QWidget | None = None,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent, mmcore, use_with_mda=use_with_mda)
        self._viewer = ndv.ArrayViewer()
        self._buffer: RingBuffer | None = None
        self.process_events_on_update = True
        qwdg = self._viewer.widget()
        qwdg.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(qwdg)

    def set_data(self, data: np.ndarray) -> None:
        if self._buffer is None:
            self._setup_viewer()
        if self._buffer is not None:
            self._buffer.append(data)
            self._viewer.display_model.current_index.update({0: len(self._buffer) - 1})
            if self.process_events_on_update:
                QApplication.processEvents()

    def _setup_viewer(self) -> None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                shape: tuple[int, ...] = (img_height, img_width)
                if core.getNumberOfComponents() > 1:
                    shape = (*shape, 3)

                self._buffer = RingBuffer(
                    max_capacity=100, dtype=(f"uint{bits}", shape)
                )
                self._viewer.data = self._buffer

    def _on_system_config_loaded(self) -> None:
        self._setup_viewer()

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._setup_viewer()
