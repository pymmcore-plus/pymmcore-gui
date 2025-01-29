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
    """Multi-dimensional acquisition widget.

    Subclassing to override the execute_mda method and add a handler to the
    sequence metadata that will be used by the viewers_core_link to display the
    images with ndv.
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

    # -------------------------PUBLIC METHODS-------------------------

    def execute_mda(self, output: Path | str | object | None) -> None:
        """Execute the MDA experiment corresponding to the current value."""
        sequence = self.value()
        # TODO: We are manually creating a TensorStoreHandler here. This should only 
        # happen if the user does not specify a save type through the MDAWidget. If the
        # user specifies a save type, we should retrieve the saving data type from the
        # sequence metadata and create or set the handler accordingly.
        handler = TensorStoreHandler(driver="zarr")
        # store the handler in the metadata of the sequence (this will be used by the
        # viewers_core_link to display the images with ndv)
        sequence.metadata[HANDLER_META_KEY] = store_handler(handler)
        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=handler)
