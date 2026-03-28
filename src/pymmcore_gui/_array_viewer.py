"""Custom ndv.ArrayViewer subclass for pymmcore-gui."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import ndv

if TYPE_CHECKING:
    import useq
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

        # Set by NDVViewersManager when an MDA sequence is running.
        self._mda_sequence: useq.MDASequence | None = None
        self._pixel_size_um: float | None = None

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

        # Dimension names — only needed to detect the 'p' (position) axis.
        dims: tuple[str, ...] = ()
        with suppress(Exception):
            if wrapper := self.data_wrapper:
                dims = tuple(str(d) for d in wrapper.dims)

        path, _ = QFileDialog.getSaveFileName(
            self.widget(),
            "Save Image",
            "",
            "TIFF Files (*.tif *.tiff);;All Files (*)",
        )
        if not path:
            return

        pixel_size_um = self._pixel_size_um
        z_step_um: float | None = None
        with suppress(Exception):
            if (seq := self._mda_sequence) and seq.z_plan:
                from useq import ZAboveBelow, ZRangeAround, ZTopBottom

                if isinstance(seq.z_plan, (ZTopBottom, ZRangeAround, ZAboveBelow)):
                    z_step_um = seq.z_plan.step

        # Multi-position: save one file per position.
        if "p" in dims:
            _save_multiposition(arr, dims, path, pixel_size_um, z_step_um)
        else:
            _save_as_tiff(arr, path, pixel_size_um, z_step_um)


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


def _save_multiposition(
    arr: Any,
    dims: tuple[str, ...],
    path: str,
    pixel_size_um: float | None,
    z_step_um: float | None,
) -> None:
    """Save a multi-position array as one TIFF file per position.

    Output files are named ``<stem>_p000<ext>``, ``<stem>_p001<ext>``, …
    """
    from pathlib import Path

    import numpy as np

    p_idx = dims.index("p")
    base = Path(path).with_suffix("")
    suffix = Path(path).suffix

    for i in range(arr.shape[p_idx]):
        _save_as_tiff(
            np.take(arr, i, axis=p_idx),
            str(base) + f"_p{i:03d}" + suffix,
            pixel_size_um,
            z_step_um,
        )


def _save_as_tiff(
    arr: Any,
    path: str,
    pixel_size_um: float | None = None,
    z_step_um: float | None = None,
) -> None:
    """Save *arr* as an OME-TIFF with XYZ physical-size metadata."""
    import numpy as np
    import tifffile
    from ome_types import OME
    from ome_types.model import Image, Pixels
    from ome_types.model.pixels import Pixels_DimensionOrder, PixelType

    arr = np.asarray(arr)

    _dtype_map: dict[str, PixelType] = {
        "uint8": PixelType.UINT8,
        "uint16": PixelType.UINT16,
        "uint32": PixelType.UINT32,
        "int8": PixelType.INT8,
        "int16": PixelType.INT16,
        "int32": PixelType.INT32,
        "float32": PixelType.FLOAT,
        "float64": PixelType.DOUBLE,
    }
    size_x = arr.shape[-1] if arr.ndim >= 1 else 1
    size_y = arr.shape[-2] if arr.ndim >= 2 else 1
    # Fold all leading dimensions into size_z so the IFD count is correct.
    size_z = arr.size // (size_x * size_y) if arr.ndim > 2 else 1

    pixels = Pixels(
        id="Pixels:0",
        dimension_order=Pixels_DimensionOrder.XYCZT,
        type=_dtype_map.get(arr.dtype.name, PixelType.UINT16),
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        size_c=1,
        size_t=1,
        physical_size_x=pixel_size_um or None,
        physical_size_y=pixel_size_um or None,
        physical_size_z=z_step_um or None,
    )
    ome = OME(images=[Image(id="Image:0", pixels=pixels)])
    # metadata=None prevents tifffile from adding its own tags that would
    # conflict with the OME-XML description.
    tifffile.imwrite(path, arr, description=ome.to_xml(), metadata=None)
