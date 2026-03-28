"""Custom ndv.ArrayViewer subclass for pymmcore-gui."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import ndv

if TYPE_CHECKING:
    from ndv.models._viewer_model import ArrayViewerModelKwargs

    from pymmcore_gui._qt.QtWidgets import QPushButton

_VIEWER_OPTIONS: ArrayViewerModelKwargs = {"show_roi_button": False}


class MMArrayViewer(ndv.ArrayViewer):
    """ArrayViewer subclass that hides the ROI button and adds a Save button."""

    def __init__(self, data: Any = None, /, **kwargs: Any) -> None:
        # Merge our defaults into viewer_options
        opts = kwargs.pop("viewer_options", None) or {}
        if isinstance(opts, dict):
            opts = {**_VIEWER_OPTIONS, **opts}
        kwargs["viewer_options"] = opts
        super().__init__(data, **kwargs)

        with suppress(Exception):
            self._save_btn = _add_save_button(self)

        # Belt-and-suspenders: explicitly hide the ROI button widget
        with suppress(Exception):
            self.widget().add_roi_btn.setVisible(False)

    def _save_data(self) -> None:
        """Save the current viewer data as a TIFF file."""
        import numpy as np

        from pymmcore_gui._qt.QtWidgets import QFileDialog

        data = self.data
        if data is None:
            return

        arr = np.asarray(data)
        if arr.size == 0:
            return

        path, _ = QFileDialog.getSaveFileName(
            self.widget(),
            "Save Image",
            "",
            "TIFF Files (*.tif *.tiff);;All Files (*)",
        )
        if not path:
            return

        _save_as_tiff(arr, path, metadata=_collect_metadata(self))


def _add_save_button(viewer: MMArrayViewer) -> QPushButton:
    """Add a save button to the viewer's button bar, after the 3D button."""
    from superqt import QIconifyIcon

    from pymmcore_gui._qt.QtWidgets import QPushButton

    q_widget = viewer.widget()
    btn_layout = q_widget._btn_layout

    btn = QPushButton(q_widget)
    btn.setIcon(QIconifyIcon("mdi:content-save-outline"))
    btn.setToolTip("Save as TIFF")
    btn.clicked.connect(viewer._save_data)

    # Insert after the 3D button (ndims_btn is at index 3)
    ndims_idx = btn_layout.indexOf(q_widget.ndims_btn)
    btn_layout.insertWidget(ndims_idx + 1, btn)
    return btn


def _collect_metadata(viewer: MMArrayViewer) -> dict:
    """Collect metadata from the viewer's data wrapper if available."""
    metadata: dict = {}
    wrapper = viewer.data_wrapper
    if wrapper is None:
        return metadata

    with suppress(Exception):
        metadata["dims"] = list(wrapper.dims)
    with suppress(Exception):
        coords = wrapper.coords
        # Convert coords to JSON-serializable form
        serializable: dict = {}
        for k, v in coords.items():
            try:
                import numpy as np

                serializable[str(k)] = (
                    v.tolist() if isinstance(v, np.ndarray) else list(v)
                )
            except Exception:
                serializable[str(k)] = str(v)
        metadata["coords"] = serializable

    # If the underlying data has metadata (e.g. from ome-writers), include it
    data = wrapper.data
    if hasattr(data, "metadata"):
        with suppress(Exception):
            metadata["source_metadata"] = data.metadata
    if hasattr(data, "attrs"):
        with suppress(Exception):
            attrs = dict(data.attrs)
            if attrs:
                metadata["attrs"] = attrs

    return metadata


def _save_as_tiff(arr: Any, path: str, metadata: dict | None = None) -> None:
    """Save a numpy array as a TIFF file with optional metadata."""
    import json

    import numpy as np
    import tifffile

    arr = np.asarray(arr)
    description = json.dumps(metadata, default=str) if metadata else None
    tifffile.imwrite(path, arr, description=description)
