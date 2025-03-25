from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeGuard

import ndv
import numpy as np
import numpy.typing as npt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pymmcore_gui.widgets.image_preview._preview_base import _ImagePreviewBase

if TYPE_CHECKING:
    from collections.abc import Mapping

    import rendercanvas.qt
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]


class _StreamingWrapper(ndv.DataWrapper):
    def __init__(self, streamer: Streamer):
        super().__init__(streamer._data)
        self._streamer = streamer

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[Any]:
        return False

    def guess_channel_axis(self) -> int:
        return 1

    def isel(self, index: Mapping[int, int | slice]) -> np.ndarray:
        """Return a slice of the data as a numpy array, never empty in axis 0."""
        strm = self._streamer
        max_planes = strm._max_planes
        count = strm._count
        start = strm._start

        if count == 0:
            # Return a dummy first frame to maintain correct ndim
            ary = strm._data[:1]
        elif count < max_planes:
            ary = strm._data[:count]
        else:
            idx = np.arange(start, start + max_planes) % max_planes
            ary = strm._data[idx]

        idx_tuple = tuple(index.get(k, slice(None)) for k in range(ary.ndim))
        return ary[idx_tuple]


class Streamer:
    def __init__(
        self,
        viewer: ndv.ArrayViewer,
        plane_shape: tuple[int, ...],
        num_channels: int = 1,
        max_planes: int = 100,
        dtype: npt.DTypeLike = np.uint16,
        *,
        process_events_on_update: bool = True,
    ) -> None:
        self._plane_shape = plane_shape
        self._max_planes = max_planes
        self._num_channels = num_channels
        self._data = np.zeros((max_planes, num_channels, *plane_shape), dtype=dtype)
        self._wrapper = _StreamingWrapper(self)

        self.viewer = viewer
        self.viewer._viewer_model.show_roi_button = False
        self.viewer._viewer_model.show_3d_button = False
        self.process_events_on_update = process_events_on_update

        self._start = 0  # index of the oldest frame in the buffer
        self._count = 0  # number of valid frames
        self._current_frame = -1  # logical time index for grouped channels

        viewer.data = self._wrapper
        viewer.display_model.channel_axis = 1
        viewer._update_visible_sliders()  # BUG

    def append(self, data: np.ndarray, channel: int = 0) -> None:
        if channel == 0 or self._current_frame == -1:
            self._start_new_frame()

        if data.shape != self._plane_shape:
            raise ValueError(f"Item must have shape {self._plane_shape}")
        if not (0 <= channel < self._num_channels):
            raise ValueError(f"Channel index {channel} out of range")

        self._data[self._current_frame, channel] = data

        self.viewer.display_model.current_index.update({0: self._count - 1})
        if self.process_events_on_update:
            QApplication.processEvents()

    def _start_new_frame(self) -> None:
        """Advance to a new logical timepoint (frame)."""
        if self._count < self._max_planes:
            self._current_frame = self._count
            self._count += 1
        else:
            # Advance _start first, then compute new end-of-buffer index
            self._start = (self._start + 1) % self._max_planes
            self._current_frame = (
                self._start + self._max_planes - 1
            ) % self._max_planes


class NDVPreview(_ImagePreviewBase):
    def __init__(
        self,
        parent: QWidget | None,
        mmcore: CMMCorePlus,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent, mmcore, use_with_mda=use_with_mda)
        self._viewer = ndv.ArrayViewer()
        self._streamer: Streamer | None = None
        qwdg = self._viewer.widget()
        qwdg.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(qwdg)

    def set_data(self, data: np.ndarray) -> None:
        if self._streamer is None:
            self._setup_viewer()
        if self._streamer is not None:
            self._streamer.append(data)

    def _setup_viewer(self) -> None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                shape = (img_width, img_height)
                np_dtype = f"uint{bits}"
                self._streamer = Streamer(
                    self._viewer, shape, max_planes=20, dtype=np_dtype
                )

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
