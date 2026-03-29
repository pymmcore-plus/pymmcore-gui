from __future__ import annotations

from typing import TYPE_CHECKING

import ndv.models
from ndv.models import RingBuffer

from pymmcore_gui._array_viewer import MMArrayViewer
from pymmcore_gui._qt.QtWidgets import QApplication, QVBoxLayout, QWidget
from pymmcore_gui.widgets.image_preview._preview_base import ImagePreviewBase

if TYPE_CHECKING:
    import numpy as np
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.metadata import SummaryMetaV1


BUFFER_SIZE = 1


class NDVPreview(ImagePreviewBase):
    def __init__(
        self,
        mmcore: CMMCorePlus,
        parent: QWidget | None = None,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent, mmcore, use_with_mda=use_with_mda)
        self._viewer = MMArrayViewer(meta=self._pixel_size_meta())
        self._buffer: RingBuffer | None = None
        self._core_dtype: tuple[str, tuple[int, ...]] | None = None
        self._is_rgb: bool = False
        self.process_events_on_update = True
        qwdg = self._viewer.widget()
        qwdg.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(qwdg)

    def append(self, data: np.ndarray) -> None:
        needs_setup = self._buffer is None
        if needs_setup:
            self._init_buffer()
        if self._buffer is not None:
            self._buffer.append(data)
            if needs_setup:
                self._apply_viewer_settings()
            self._viewer.display_model.current_index.update({0: len(self._buffer) - 1})
            self._viewer.data_wrapper.data_changed.emit()
            if self.process_events_on_update:
                QApplication.processEvents()

    @property
    def dtype_shape(self) -> tuple[str, tuple[int, ...]] | None:
        return self._core_dtype

    def _get_core_dtype_shape(self) -> tuple[str, tuple[int, ...]] | None:
        if (core := self._mmc) is not None:
            if bits := core.getImageBitDepth():
                img_width = core.getImageWidth()
                img_height = core.getImageHeight()
                if core.getNumberOfComponents() > 1:
                    shape: tuple[int, ...] = (img_height, img_width, 3)
                else:
                    shape = (img_height, img_width)
                # coerce packed bits to byte-aligned numpy dtype
                # (this is how the data will actually come from pymmcore)
                if bits <= 8:
                    bits = 8
                elif bits <= 16:
                    bits = 16
                elif bits <= 32:
                    bits = 32
                return (f"uint{bits}", shape)
        return None

    def _init_buffer(self) -> None:
        """Create the ring buffer (without assigning to viewer yet)."""
        if (core_dtype := self._get_core_dtype_shape()) is None:
            return  # pragma: no cover
        self._core_dtype = core_dtype
        self._is_rgb = core_dtype[1][-1] == 3
        self._buffer = RingBuffer(max_capacity=BUFFER_SIZE, dtype=core_dtype)

    def _apply_viewer_settings(self) -> None:
        """Assign the buffer to the viewer and configure display settings."""
        self._viewer.data = self._buffer
        self._viewer.display_model.visible_axes = (1, 2)
        if self._is_rgb:  # RGB
            self._viewer.display_model.channel_axis = 3
            self._viewer.display_model.channel_mode = ndv.models.ChannelMode.RGBA
        else:
            self._viewer.display_model.channel_mode = ndv.models.ChannelMode.GRAYSCALE
            self._viewer.display_model.channel_axis = None

    def _setup_viewer(self) -> None:
        """Create the buffer, assign to viewer, and configure display."""
        self._init_buffer()
        if self._buffer is not None:
            self._apply_viewer_settings()

    def _pixel_size_meta(self) -> SummaryMetaV1 | None:
        px = (self._mmc.getPixelSizeUm() or None) if self._mmc else None
        return {"image_infos": [{"pixel_size_um": px}]} if px else None  # type: ignore[return-value]

    def _on_system_config_loaded(self) -> None:
        self._setup_viewer()
        self._viewer._meta = self._pixel_size_meta()

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._setup_viewer()
        self._viewer._meta = self._pixel_size_meta()
