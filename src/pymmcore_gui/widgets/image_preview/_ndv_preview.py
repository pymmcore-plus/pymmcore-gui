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
        if self._viewer.dtype is not None:
            self._viewer.update_data(data)

    def _on_system_config_loaded(self) -> None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                np_dtype = f"uint{bits}"
                self._viewer.setup((img_width, img_height), np_dtype, 1)

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._on_system_config_loaded()

    def _on_property_changed(self, dev: str, prop: str, value: str) -> None:
        """Reconfigure the viewer when a Camera property is changed."""
        if self._mmc is None:
            return
        # if we change camera, reconfigure the viewer
        if dev =="Core" and prop == "Camera":
            self._on_system_config_loaded()
        # if any property related to the camera is changed, reconfigure the viewer
        # e.g. bit depth, binning, etc.
        # Maybe be more strict about which properties trigger a reconfigure?
        elif dev == self._mmc.getCameraDevice():
            self._on_system_config_loaded()
