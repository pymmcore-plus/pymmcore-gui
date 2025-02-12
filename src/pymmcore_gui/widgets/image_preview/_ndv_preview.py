from __future__ import annotations

from typing import TYPE_CHECKING

from ndv import StreamingViewer
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from pymmcore_gui.widgets.image_preview._preview_base import _ImagePreviewBase

if TYPE_CHECKING:
    import numpy as np
    import rendercanvas.qt
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]


class NDVPreview(_ImagePreviewBase):
    def __init__(
        self,
        parent: QWidget | None,
        mmcore: CMMCorePlus,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent, mmcore, use_with_mda=use_with_mda)
        self._viewer = StreamingViewer()
        qwdg = self._viewer.widget()
        qwdg.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(qwdg)

    def attach(self, core: CMMCorePlus) -> None:
        super().attach(core)

    def set_data(self, data: np.ndarray) -> None:
        # FIXME: need better public method to determine readiness.
        if self._viewer._dtype is not None:
            self._viewer.update_data(data)

    def _on_system_config_loaded(self) -> None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                np_dtype = f"uint{bits}"
                self._viewer.setup((img_width, img_height), np_dtype, 1)
