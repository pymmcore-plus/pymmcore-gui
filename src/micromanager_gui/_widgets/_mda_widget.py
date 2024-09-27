from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)
from pymmcore_widgets.mda import MDAWidget
from pymmcore_widgets.mda._save_widget import (
    OME_TIFF,
    OME_ZARR,
    WRITERS,
    ZARR_TESNSORSTORE,
)
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from useq import MDASequence

from micromanager_gui._writers._tensorstore_zarr import _TensorStoreHandler

OME_TIFFS = tuple(WRITERS[OME_TIFF])
GB_CACHE = 2_000_000_000  # 2 GB for tensorstore cache

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import (
        QVBoxLayout,
        QWidget,
    )
    from useq import MDASequence


class _MDAWidget(MDAWidget):
    """Main napari-micromanager GUI."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

        # writer for saving the MDA sequence. This is used by the MDAViewer to set its
        # internal datastore. If writer is None, the MDAViewer will use its default
        # internal datastore.
        self.writer: OMETiffWriter | OMEZarrWriter | TensorStoreHandler | None = None

        # setContentsMargins
        pos_layout = cast("QVBoxLayout", self.stage_positions.layout())
        pos_layout.setContentsMargins(10, 10, 10, 10)
        time_layout = cast("QVBoxLayout", self.time_plan.layout())
        time_layout.setContentsMargins(10, 10, 10, 10)

    def _on_mda_finished(self, sequence: MDASequence) -> None:
        """Handle the end of the MDA sequence."""
        self.writer = None
        super()._on_mda_finished(sequence)

    def run_mda(self) -> None:
        """Run the MDA sequence experiment."""
        # in case the user does not press enter after editing the save name.
        self.save_info.save_name.editingFinished.emit()

        # if autofocus has been requested, but the autofocus device is not engaged,
        # and position-specific offsets haven't been set, show a warning
        pos = self.stage_positions
        if (
            self.af_axis.value()
            and not self._mmc.isContinuousFocusLocked()
            and (not self.tab_wdg.isChecked(pos) or not pos.af_per_position.isChecked())
            and not self._confirm_af_intentions()
        ):
            return

        sequence = self.value()

        # reset the writer
        self.writer = None

        # technically, this is in the metadata as well, but isChecked is more direct
        if self.save_info.isChecked():
            save_path = self._update_save_path_from_metadata(
                sequence, update_metadata=True
            )
            if isinstance(save_path, Path):
                # get save format from metadata
                save_meta = sequence.metadata.get(PYMMCW_METADATA_KEY, {})
                save_format = save_meta.get("format")
                # set the writer to use for saving the MDA sequence.
                # NOTE: 'self.writer' is used by the 'MDAViewer' to set its datastore
                self.writer = self._create_mda_viewer_writer(save_format, save_path)
                # at this point, if self.writer is None, it means that a
                # ImageSequenceWriter should be used to save the sequence.
                if self.writer is None:
                    output = ImageSequenceWriter(save_path)
                    # Since any other type of writer will be handled by the 'MDAViewer',
                    # we need to pass a writer to the engine only if it is a
                    # 'ImageSequenceWriter'.
                    self._mmc.run_mda(sequence, output=output)
                    return

        self._mmc.run_mda(sequence)

    def _create_mda_viewer_writer(
        self, save_format: str, save_path: Path
    ) -> OMEZarrWriter | OMETiffWriter | TensorStoreHandler | None:
        """Create a writer for the MDAViewer based on the save format."""
        # use internal OME-TIFF writer if selected
        if OME_TIFF in save_format:
            # if OME-TIFF, save_path should be a directory without extension, so
            # we need to add the ".ome.tif" to correctly use the OMETiffWriter
            if not save_path.name.endswith(OME_TIFFS):
                save_path = save_path.with_suffix(OME_TIFF)
            return OMETiffWriter(save_path)
        elif OME_ZARR in save_format:
            return OMEZarrWriter(save_path)
        elif ZARR_TESNSORSTORE in save_format:
            return self._create_zarr_tensorstore(save_path)
        # cannot use the ImageSequenceWriter here because the MDAViewer will not be
        # able to handle it.
        return None

    def _create_zarr_tensorstore(self, save_path: Path) -> _TensorStoreHandler:
        """Create a Zarr TensorStore writer."""
        return _TensorStoreHandler(
            driver="zarr",
            path=save_path,
            delete_existing=True,
            spec={"context": {"cache_pool": {"total_bytes_limit": GB_CACHE}}},
        )

    def _update_save_path_from_metadata(
        self,
        sequence: MDASequence,
        update_widget: bool = True,
        update_metadata: bool = False,
    ) -> Path | None:
        """Get the next available save path from sequence metadata and update widget.

        Parameters
        ----------
        sequence : MDASequence
            The MDA sequence to get the save path from. (must be in the
            'pymmcore_widgets' key of the metadata)
        update_widget : bool, optional
            Whether to update the save widget with the new path, by default True.
        update_metadata : bool, optional
            Whether to update the Sequence metadata with the new path, by default False.
        """
        if (
            (meta := sequence.metadata.get(PYMMCW_METADATA_KEY, {}))
            and (save_dir := meta.get("save_dir"))
            and (save_name := meta.get("save_name"))
        ):
            requested = (Path(save_dir) / str(save_name)).expanduser().resolve()
            next_path = self.get_next_available_path(requested)

            if next_path != requested:
                if update_widget:
                    self.save_info.setValue(next_path)
                    if update_metadata:
                        meta.update(self.save_info.value())
            return Path(next_path)
        return None
