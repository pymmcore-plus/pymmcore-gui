"""Custom ndv.ArrayViewer subclass for pymmcore-gui."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ndv
import numpy as np
import tifffile
from qtpy.QtWidgets import QFileDialog, QPushButton
from superqt import QIconifyIcon

if TYPE_CHECKING:
    import useq
    from ndv.models._viewer_model import ArrayViewerModelKwargs
    from pymmcore_plus.metadata import SummaryMetaV1


_VIEWER_OPTIONS: ArrayViewerModelKwargs = {"show_roi_button": False}


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
            _add_save_button(self)

        # Hide the ROI button since not linked to anything
        with suppress(Exception):
            self.widget().add_roi_btn.setVisible(False)

    def _save_data(self) -> None:
        """Save the current viewer data as an OME-TIFF file."""
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
            "OME-TIFF (*.ome.tif);;All Files (*)",
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

        # tifffile axes: sequence order (slowest→fastest, excluding p) + "YX".
        # Empty string lets tifffile infer the axes from the array shape (snap case).
        _to_axes = {"t": "T", "c": "C", "z": "Z"}
        axes = (
            "".join(_to_axes[a] for a in str(self._sequence.used_axes) if a in _to_axes)
            + "YX"
            if self._sequence
            else ""
        )

        # Multi-position: save one file per position.
        if sizes.get("p", 0) > 1:
            _save_multiposition(arr, sizes, path, pixel_size_um, z_step_um, axes)
        else:
            # Squeeze out the p axis if present (size 1 by definition here).
            if "p" in sizes:
                p_idx = list(sizes).index("p")
                arr = np.squeeze(arr, axis=p_idx)
            _save_as_tiff(arr, path, pixel_size_um, z_step_um, axes)


def _add_save_button(viewer: MMArrayViewer) -> QPushButton:
    """Add a save button to the viewer's button bar, after the 3D button."""
    q_widget = viewer.widget()
    btn_layout = q_widget._btn_layout

    btn = QPushButton(q_widget)
    btn.setIcon(QIconifyIcon("mdi:content-save-outline"))
    btn.setToolTip("Save as OME-TIFF")
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
    axes: str,
) -> None:
    """Save a multi-position array as one OME-TIFF file per position.

    Output files are named ``<stem>_p000.ome.tif``, ``<stem>_p001.ome.tif``, …
    """
    p_idx = list(sizes).index("p")
    # Strip up to two suffixes to handle both ".tif" and ".ome.tif".
    base = str(Path(path).with_suffix("").with_suffix(""))

    for i in range(arr.shape[p_idx]):
        _save_as_tiff(
            np.take(arr, i, axis=p_idx),
            f"{base}_p{i:03d}.ome.tif",
            pixel_size_um,
            z_step_um,
            axes,
        )


def _save_as_tiff(
    arr: Any,
    path: str,
    pixel_size_um: float | None = None,
    z_step_um: float | None = None,
    axes: str = "",
) -> None:
    """Save *arr* as an OME-TIFF with physical-size metadata."""
    arr = np.asarray(arr)

    metadata: dict[str, Any] = {}
    if axes:
        metadata["axes"] = axes
    if pixel_size_um:
        metadata["PhysicalSizeX"] = pixel_size_um
        metadata["PhysicalSizeXUnit"] = "µm"
        metadata["PhysicalSizeY"] = pixel_size_um
        metadata["PhysicalSizeYUnit"] = "µm"
    if z_step_um:
        metadata["PhysicalSizeZ"] = z_step_um
        metadata["PhysicalSizeZUnit"] = "µm"

    tifffile.imwrite(
        path, arr, ome=True, photometric="minisblack", metadata=metadata or None
    )
