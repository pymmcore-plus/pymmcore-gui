from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)
from pymmcore_widgets import MDAWidget
from pymmcore_widgets.mda._save_widget import OME_TIFF, OME_ZARR, TIFF_SEQ, WRITERS

from pymmcore_gui.core_link._shared_handler import HANDLER_META_KEY, store_handler

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QWidget

FORMATS = [OME_ZARR, OME_TIFF, TIFF_SEQ]
OME_TIFFS = tuple(WRITERS[OME_TIFF])


class _MDAWidget(MDAWidget):
    """Multi-dimensional acquisition widget."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

    # -------------------------PUBLIC METHODS-------------------------

    def execute_mda(self, output: Path | str | object | None) -> None:
        """Execute the MDA experiment corresponding to the current value."""
        sequence = self.value()
        handler = TensorStoreHandler(driver="zarr")
        sequence.metadata[HANDLER_META_KEY] = store_handler(handler)
        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=handler)

    # -------------------------PRIVATE METHODS-------------------------

    def _create_writer(
        self, save_format: str, save_path: bool | str | Path | None
    ) -> (
        OMEZarrWriter | OMETiffWriter | TensorStoreHandler | ImageSequenceWriter | None
    ):
        """Create a writer based on the save format."""
        # if save_path is a bool (False) or None or if save_format is not recognized
        if not isinstance(save_path, str | Path) or save_format not in FORMATS:
            return TensorStoreHandler(driver="zarr")
        save_path = Path(save_path)
        if OME_TIFF in save_format:
            # if OME-TIFF, save_path should be a directory without extension, so
            # we need to add the ".ome.tif" to correctly use the OMETiffWriter
            if not save_path.name.endswith(OME_TIFFS):
                save_path = save_path.with_suffix(OME_TIFF)
            return OMETiffWriter(save_path)
        elif OME_ZARR in save_format:
            return OMEZarrWriter(save_path)
        else:
            return ImageSequenceWriter(save_path)
