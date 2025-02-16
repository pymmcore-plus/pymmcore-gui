from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from ndv import StreamingViewer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from pymmcore_gui.widgets.image_preview._preview_base import _ImagePreviewBase

if TYPE_CHECKING:
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

    def _setup_viewer(self) -> None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                shape = (img_width, img_height)
                np_dtype = f"uint{bits}"
                self._viewer.setup(shape, np_dtype, 1)
                self._viewer.update_data(_get_scope_img(shape, np_dtype))
                try:
                    self._viewer._handles[0].set_clims((0, 2000))
                except Exception:
                    pass  # :)

    def _on_system_config_loaded(self) -> None:
        self._setup_viewer()

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._setup_viewer()

    def _on_property_changed(self, dev: str, prop: str, value: str) -> None:
        """Reconfigure the viewer when a Camera property is changed."""
        if self._mmc is None:
            return
        # if we change camera, reconfigure the viewer
        if dev == "Core" and prop == "Camera":
            self._setup_viewer()
        # if any property related to the camera is changed, reconfigure the viewer
        # e.g. bit depth, binning, etc.
        # Maybe be more strict about which properties trigger a reconfigure?
        elif dev == self._mmc.getCameraDevice():
            self._setup_viewer()


@cache
def _scope_img_numpy() -> np.ndarray:
    resources = Path(__file__).parent.parent.parent / "resources"
    qimage = QImage(str(resources / "logo.png"))
    qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = qimage.width(), qimage.height()
    ptr = qimage.bits()
    ptr.setsize(qimage.sizeInBytes())  # type: ignore [union-attr]
    ary = np.array(ptr).reshape(height, width, 4)
    return np.mean(ary, axis=-1)


def _get_scope_img(shape: tuple[int, int], dtype: np.typing.DTypeLike) -> np.ndarray:
    """Get an adorable little image of the logo to place on the canvas."""
    ary = _scope_img_numpy()
    img = _resize_nearest_neighbor(ary, shape).astype(dtype)
    return img


def _resize_nearest_neighbor(arr: np.ndarray, new_shape: tuple[int, int]) -> np.ndarray:
    """Rescale a 2D numpy array using nearest neighbor interpolation."""
    old_M, old_N = arr.shape
    new_M, new_N = new_shape

    # Compute the ratio between the old and new dimensions.
    row_ratio: float = old_M / new_M
    col_ratio: float = old_N / new_N

    # Compute the indices for the new array using nearest neighbor interpolation.
    row_indices: np.ndarray = (np.arange(new_M) * row_ratio).astype(int)
    col_indices: np.ndarray = (np.arange(new_N) * col_ratio).astype(int)

    # Ensure indices are within bounds
    row_indices = np.clip(row_indices, 0, old_M - 1)
    col_indices = np.clip(col_indices, 0, old_N - 1)

    # Use np.ix_ to generate the 2D index arrays for advanced indexing
    return arr[np.ix_(row_indices, col_indices)]
