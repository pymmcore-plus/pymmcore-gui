"""Custom ndv.ArrayViewer subclass for pymmcore-gui."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ndv
import numpy as np
import tifffile
from ome_types import OME
from ome_types.model import Image, Pixels
from ome_types.model.pixels import Pixels_DimensionOrder, PixelType
from qtpy.QtWidgets import QFileDialog, QPushButton
from superqt import QIconifyIcon

if TYPE_CHECKING:
    import useq
    from ndv.models._viewer_model import ArrayViewerModelKwargs
    from pymmcore_plus.metadata import SummaryMetaV1


_VIEWER_OPTIONS: ArrayViewerModelKwargs = {"show_roi_button": False}
_DTYPE_MAP: dict[str, PixelType] = {
    "uint8": PixelType.UINT8,
    "uint16": PixelType.UINT16,
    "uint32": PixelType.UINT32,
    "int8": PixelType.INT8,
    "int16": PixelType.INT16,
    "int32": PixelType.INT32,
    "float32": PixelType.FLOAT,
    "float64": PixelType.DOUBLE,
}

class MMArrayViewer(ndv.ArrayViewer):
    """ArrayViewer subclass that hides the ROI button and adds a Save button."""

    def __init__(
        self,
        data: Any = None,
        /,
        sequence: useq.MDASequence | None = None,
        meta: SummaryMetaV1 | None = None,
        **kwargs: Any,
    ) -> None:
        # Merge our defaults into viewer_options
        opts = kwargs.pop("viewer_options", None) or {}
        if isinstance(opts, dict):
            opts = {**_VIEWER_OPTIONS, **opts}
        kwargs["viewer_options"] = opts
        super().__init__(data, **kwargs)

        self._sequence: useq.MDASequence | None = sequence
        self._meta: SummaryMetaV1 | None = meta

        with suppress(Exception):
            self._save_btn = _add_save_button(self)

        # Belt-and-suspenders: explicitly hide the ROI button widget
        with suppress(Exception):
            self.widget().add_roi_btn.setVisible(False)

    def _save_data(self) -> None:
        """Save the current viewer data as a TIFF file."""
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

        sizes: dict[str, int] = {}
        with suppress(Exception):
            if wrapper := self.data_wrapper:
                sizes = {str(k): v for k, v in wrapper.sizes().items()}

        pixel_size_um: float | None = None
        with suppress(Exception):
            if self._meta:
                pixel_size_um = self._meta["image_infos"][0]["pixel_size_um"] or None

        z_step_um: float | None = None
        with suppress(Exception):
            if self._sequence and self._sequence.z_plan:
                from useq import ZAboveBelow, ZRangeAround, ZTopBottom

                if isinstance(
                    self._sequence.z_plan, (ZTopBottom, ZRangeAround, ZAboveBelow)
                ):
                    z_step_um = self._sequence.z_plan.step

        # Derive OME dimension order from sequence.used_axes (slowest→fastest).
        # Reverse so the OME string goes fastest→slowest after XY.
        _ome = {"t": "T", "c": "C", "z": "Z"}
        seq_axes = (
            [_ome[a] for a in reversed(str(self._sequence.used_axes)) if a in _ome]
            if self._sequence
            else []
        )
        ome_str = "XY" + "".join(seq_axes)
        for a in ("C", "Z", "T"):
            if a not in ome_str:
                ome_str += a
        dim_order = Pixels_DimensionOrder(ome_str)

        # Multi-position: save one file per position.
        if "p" in sizes:
            _save_multiposition(arr, sizes, path, pixel_size_um, z_step_um, dim_order)
        else:
            _save_as_tiff(arr, path, pixel_size_um, z_step_um, sizes, dim_order)


def _add_save_button(viewer: MMArrayViewer) -> QPushButton:
    """Add a save button to the viewer's button bar, after the 3D button."""
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
    sizes: dict[str, int],
    path: str,
    pixel_size_um: float | None,
    z_step_um: float | None,
    dim_order: Pixels_DimensionOrder,
) -> None:
    """Save a multi-position array as one TIFF file per position.

    Output files are named ``<stem>_p000<ext>``, ``<stem>_p001<ext>``, …
    """
    p_idx = list(sizes).index("p")
    base = Path(path).with_suffix("")
    suffix = Path(path).suffix
    sizes_no_p = {k: v for k, v in sizes.items() if k != "p"}

    for i in range(arr.shape[p_idx]):
        _save_as_tiff(
            np.take(arr, i, axis=p_idx),
            str(base) + f"_p{i:03d}" + suffix,
            pixel_size_um,
            z_step_um,
            sizes_no_p,
            dim_order,
        )


def _save_as_tiff(
    arr: Any,
    path: str,
    pixel_size_um: float | None = None,
    z_step_um: float | None = None,
    sizes: dict[str, int] | None = None,
    dim_order: Pixels_DimensionOrder = Pixels_DimensionOrder.XYCZT,
) -> None:
    """Save *arr* as an OME-TIFF with XYZ physical-size metadata."""
    arr = np.asarray(arr)

    size_x = arr.shape[-1] if arr.ndim >= 1 else 1
    size_y = arr.shape[-2] if arr.ndim >= 2 else 1

    sizes = sizes or {}
    size_z = sizes.get("z", 1)
    size_c = sizes.get("c", 1)
    size_t = sizes.get("t", 1)

    pixels = Pixels(
        id="Pixels:0",
        dimension_order=dim_order,
        type=_DTYPE_MAP.get(arr.dtype.name, PixelType.UINT16),
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        size_c=size_c,
        size_t=size_t,
        physical_size_x=pixel_size_um or None,
        physical_size_y=pixel_size_um or None,
        physical_size_z=z_step_um or None,
    )
    ome = OME(images=[Image(id="Image:0", pixels=pixels)])
    # metadata=None prevents tifffile from adding its own tags that would
    # conflict with the OME-XML description.
    tifffile.imwrite(path, arr, description=ome.to_xml(), metadata=None)
