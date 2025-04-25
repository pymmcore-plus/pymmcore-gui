from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeGuard

import ndv
import numpy as np
import numpy.typing as npt
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase

if TYPE_CHECKING:
    from collections.abc import Mapping

    import rendercanvas.qt
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]


class CircularBuffer(ndv.DataWrapper):
    def __init__(
        self,
        plane_shape: tuple[int, ...],
        num_channels: int = 1,
        max_planes: int = 100,
        dtype: npt.DTypeLike = np.uint16,
    ):
        self.max_planes = max_planes
        self.num_channels = num_channels
        self.plane_shape = plane_shape

        self._start = 0  # index of the oldest frame in the buffer
        self._count = 0  # number of valid frames
        self._current_frame = -1  # logical time index for grouped channels

        self._data = np.zeros((max_planes, num_channels, *plane_shape), dtype=dtype)
        super().__init__(self._data)

    def _shape(self) -> tuple[int, ...]:
        """Return the shape of the *valid* data."""
        n_planes = self.count or 1
        return (n_planes, self.num_channels, *self.plane_shape)

    @property
    def dims(self) -> tuple[int, ...]:
        """Return the dimensions of the data."""
        return tuple(range(len(self._shape())))

    @property
    def coords(self) -> Mapping:
        """Return the coordinates for the data."""
        shape = self._shape()
        return {i: range(s) for i, s in enumerate(shape)}

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[Any]:
        return False

    def guess_channel_axis(self) -> int:
        return 1

    def isel(self, index: Mapping[int, int | slice]) -> np.ndarray:
        """Return a slice of the data as a numpy array, never empty in axis 0."""
        idx = self._cur_idx()
        ary = self._data[idx]
        idx_tuple = tuple(index.get(k, slice(None)) for k in range(ary.ndim))
        return ary[idx_tuple]

    def _cur_idx(self) -> slice | np.ndarray:
        """Return the current index of the logical timepoint."""
        count = self._count
        if count == 0:
            return slice(None, 1)
        elif count < self.max_planes:
            return slice(None, count)
        idx = np.arange(self._start, self._start + self.max_planes) % self.max_planes
        return idx

    @property
    def current_frame(self) -> int:
        """Return the current logical timepoint (frame)."""
        return self._current_frame

    @property
    def count(self) -> int:
        """Return the number of valid frames in the buffer."""
        return self._count

    def _advance(self) -> None:
        """Advance to a new logical timepoint (frame)."""
        mp = self.max_planes
        if self._count < mp:
            self._current_frame = self._count
            self._count += 1
            self.dims_changed.emit()
        else:
            # Advance _start first, then compute new end-of-buffer index
            self._start = (self._start + 1) % mp
            self._current_frame = (self._start + mp - 1) % mp

    def append(self, data: np.ndarray, channel: int | slice = 0) -> None:
        if channel == 0 or self.current_frame == -1:
            self._advance()

        nc = self.num_channels
        if data.shape != self.plane_shape:
            if nc == 3 and data.ndim == 3:
                data = np.transpose(data, (2, 0, 1))
                channel = slice(None)
            else:
                raise ValueError(f"Item must have shape {self.plane_shape}")

        if isinstance(channel, int) and not (0 <= channel < nc):
            raise ValueError(f"Channel index {channel} out of range")

        self._data[self.current_frame, channel] = data


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
        self.viewer = viewer
        self.viewer._viewer_model.show_roi_button = False
        self.viewer._viewer_model.show_3d_button = False
        self.process_events_on_update = process_events_on_update

        self._wrapper = CircularBuffer(plane_shape, num_channels, max_planes, dtype)
        viewer.data = self._wrapper

        viewer.display_model.channel_axis = -3
        if num_channels == 3:
            viewer.display_model.channel_mode = ndv.models.ChannelMode.RGBA
        viewer._update_visible_sliders()  # BUG

    def append(self, data: np.ndarray, channel: int | slice = 0) -> None:
        self._wrapper.append(data, channel)
        self.viewer.display_model.current_index.update({0: self._wrapper.count - 1})
        if self.process_events_on_update:
            QApplication.processEvents()


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
                shape = (img_height, img_width)
                num_channels = 3 if core.getNumberOfComponents() > 1 else 1

                np_dtype = f"uint{bits}"
                self._streamer = Streamer(
                    self._viewer,
                    shape,
                    num_channels=num_channels,
                    max_planes=20,
                    dtype=np_dtype,
                )

    def _on_system_config_loaded(self) -> None:
        self._setup_viewer()

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._setup_viewer()
