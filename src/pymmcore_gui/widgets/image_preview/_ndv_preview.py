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

        # Ensure cleanup when widget is destroyed
        self.destroyed.connect(self._cleanup_on_destroy)

    def append(self, data: np.ndarray) -> None:
        if self._buffer is None:
            self._setup_viewer()
        if self._buffer is not None:
            self._buffer.append(data)
            self._viewer.display_model.current_index.update({0: len(self._buffer) - 1})
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

    def _setup_viewer(self) -> None:
        # TODO: maybe we should let this continue if core_dtype != self.dtype_shape
        if (core_dtype := self._get_core_dtype_shape()) is None:
            return  # pragma: no cover

        self._core_dtype = core_dtype
        self._viewer.data = self._buffer = RingBuffer(
            max_capacity=100, dtype=core_dtype
        )
        self._viewer.display_model.visible_axes = (1, 2)
        if core_dtype[1][-1] == 3:  # RGB
            self._viewer.display_model.channel_axis = 3
            self._viewer.display_model.channel_mode = ndv.models.ChannelMode.RGBA
        else:
            self._viewer.display_model.channel_mode = ndv.models.ChannelMode.GRAYSCALE
            self._viewer.display_model.channel_axis = None

    def _on_system_config_loaded(self) -> None:
        self._setup_viewer()

    def _on_roi_set(self) -> None:
        """Reconfigure the viewer when a Camera ROI is set."""
        self._setup_viewer()

    def detach(self) -> None:
        """Detach this widget from events and clean up viewer resources."""
        super().detach()
        self._cleanup_viewer()

    def _cleanup_on_destroy(self) -> None:
        """Clean up resources when widget is destroyed."""
        self._cleanup_viewer()

    def _cleanup_viewer(self) -> None:
        """Thoroughly clean up the NDV viewer and associated resources."""
        # First disconnect the data model to prevent further updates
        if hasattr(self, "_viewer") and self._viewer is not None:
            # Call the new close method on ArrayViewer
            if hasattr(self._viewer, "close") and callable(self._viewer.close):
                self._viewer.close()  # MODIFIED

            # # Original cleanup code, now mostly handled by ArrayViewer.close()
            # try:
            #     data_model = self._viewer._data_model
            #     if data_model is not None:
            #         # Disconnect data and dimension signals
            #         wrapper = getattr(data_model, 'data_wrapper', None)
            #         if wrapper is not None:
            #             try:
            #                 wrapper.data_changed.disconnect(self._viewer._request_data)
            #                 wrapper.dims_changed.disconnect(self._viewer._fully_synchronize_view)
            #             except Exception:
            #                 pass
            #             try:
            #                 wrapper._ring.resized.disconnect(wrapper.dims_changed)
            #             except Exception:
            #                 pass
            #             # clear wrapper internals to drop references
            #             try:
            #                 wrapper._data = None
            #                 wrapper._ring = None
            #             except Exception:
            #                 pass
            #             # remove wrapper from data_model
            #             try:
            #                 data_model.data_wrapper = None
            #             except Exception:
            #                 pass
            #         # drop the data_model itself
            #         try:
            #             self._viewer._data_model = None
            #         except Exception:
            #             pass

            #     # Ensure viewer no longer holds any data wrapper
            #     try:
            #         self._viewer._set_data_wrapper(None)
            #     except Exception:
            #         pass

            #     # Cancel any outstanding futures and wait for completion
            #     try:
            #         self._viewer._cancel_futures()
            #         self._viewer._join()
            #     except Exception:
            #         pass

            #     # Get and clean up the Qt widget
            #     try:
            #         qwdg = self._viewer.widget()
            #         if qwdg is not None:
            #             # Remove from layout if present
            #             layout = self.layout()
            #             if layout is not None:
            #                 layout.removeWidget(qwdg)
            #             # Set parent to None and delete
            #             qwdg.setParent(None)
            #             qwdg.deleteLater()
            #     except Exception:
            #         pass  # Ignore errors during cleanup

            #     # Close the viewer
            #     try:
            #         self._viewer.close() # This was already here, but now it does more
            #     except Exception:
            #         pass  # Ignore errors during cleanup

            # Nullify the viewer reference itself after it has been closed and cleaned.
            self._viewer = None  # ADDED

        # Clear and clean up the buffer reference thoroughly
        if hasattr(self, "_buffer") and self._buffer is not None:
            # Cancel any outstanding futures and wait for completion
            try:
                self._buffer.cancel()
                self._buffer.join()
            except Exception:
                pass
            # Nullify the buffer reference
            self._buffer = None
