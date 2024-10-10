import re
from pathlib import Path
from typing import cast

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)
from pymmcore_widgets import MDAWidget
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY
from qtpy.QtWidgets import QBoxLayout, QWidget
from useq import MDASequence

from micromanager_gui._writers._tensorstore_zarr import _TensorStoreHandler

from ._save_widget import (
    OME_TIFF,
    OME_ZARR,
    WRITERS,
    ZARR_TESNSORSTORE,
    SaveGroupBox,
)

NUM_SPLIT = re.compile(r"(.*?)(?:_(\d{3,}))?$")
OME_TIFFS = tuple(WRITERS[OME_TIFF])
GB_CACHE = 2_000_000_000  # 2 GB for tensorstore cache


def get_next_available_path(requested_path: Path | str, min_digits: int = 3) -> Path:
    """Get the next available paths (filepath or folderpath if extension = "").

    This method adds a counter of min_digits to the filename or foldername to ensure
    that the path is unique.

    Parameters
    ----------
    requested_path : Path | str
        A path to a file or folder that may or may not exist.
    min_digits : int, optional
        The min_digits number of digits to be used for the counter. By default, 3.
    """
    if isinstance(requested_path, str):  # pragma: no cover
        requested_path = Path(requested_path)

    directory = requested_path.parent
    extension = requested_path.suffix
    # ome files like .ome.tiff or .ome.zarr are special,treated as a single extension
    if (stem := requested_path.stem).endswith(".ome"):
        extension = f".ome{extension}"
        stem = stem[:-4]
    elif (stem := requested_path.stem).endswith(".tensorstore"):
        extension = f".tensorstore{extension}"
        stem = stem[:-12]

    # look for ANY existing files in the folder that follow the pattern of
    # stem_###.extension
    current_max = 0
    for existing in directory.glob(f"*{extension}"):
        # cannot use existing.stem because of the ome (2-part-extension) special case
        base = existing.name.replace(extension, "")
        # if the base name ends with a number, increase the current_max
        if (match := NUM_SPLIT.match(base)) and (num := match.group(2)):
            current_max = max(int(num), current_max)
            # if it has more digits than expected, update the ndigits
            if len(num) > min_digits:
                min_digits = len(num)

    # if the path does not exist and there are no existing files,
    # return the requested path
    if not requested_path.exists() and current_max == 0:
        return requested_path

    current_max += 1
    # otherwise return the next path greater than the current_max
    # remove any existing counter from the stem
    if match := NUM_SPLIT.match(stem):
        stem, num = match.groups()
        if num:
            # if the requested path has a counter that is greater than any other files
            # use it
            current_max = max(int(num), current_max)
    return directory / f"{stem}_{current_max:0{min_digits}d}{extension}"


class MDAWidget_(MDAWidget):
    """Multi-dimensional acquisition widget."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

        # writer for saving the MDA sequence. This is used by the MDAViewer to set its
        # internal datastore. If _writer is None, the MDAViewer will use its default
        # internal datastore.
        self.writer: OMETiffWriter | OMEZarrWriter | TensorStoreHandler | None = None

        main_layout = cast(QBoxLayout, self.layout())

        # remove the existing save_info widget from the layout and replace it with
        # the custom SaveGroupBox widget that also handles tensorstore-zarr
        if hasattr(self, "save_info"):
            self.save_info.valueChanged.disconnect(self.valueChanged)
            main_layout.removeWidget(self.save_info)
            self.save_info.deleteLater()
        self.save_info: SaveGroupBox = SaveGroupBox(parent=self)
        self.save_info.valueChanged.connect(self.valueChanged)
        main_layout.insertWidget(0, self.save_info)

    def get_next_available_path(self, requested_path: Path) -> Path:
        """Get the next available path.

        Overwrites the method in the parent class to use the custom
        'get_next_available_path' function.
        """
        return get_next_available_path(requested_path=requested_path)

    def prepare_mda(
        self,
    ) -> (
        bool
        | OMEZarrWriter
        | OMETiffWriter
        | TensorStoreHandler
        | ImageSequenceWriter
        | None
    ):
        """Prepare the MDA sequence experiment.

        This method sets the writer to use for saving the MDA sequence.
        """
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
            return False

        sequence = self.value()

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
                # NOTE: 'self._writer' is used by the 'MDAViewer' to set its datastore
                self.writer = self._create_writer(save_format, save_path)
                # at this point, if self.writer is None, it means that a
                # ImageSequenceWriter should be used to save the sequence.
                if self.writer is None:
                    # Since any other type of writer will be handled by the 'MDAViewer',
                    # we need to pass a writer to the engine only if it is a
                    # 'ImageSequenceWriter'.
                    return ImageSequenceWriter(save_path)
        return None

    def run_mda(self) -> None:
        """Run the MDA experiment."""
        save_path = self.prepare_mda()
        if save_path is False:
            return
        self.execute_mda(save_path)

    def execute_mda(self, output: Path | str | object | None) -> None:
        """Execute the MDA experiment corresponding to the current value."""
        sequence = self.value()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=output)

    # ------------------- private Methods ----------------------

    def _on_mda_finished(self, sequence: MDASequence) -> None:
        self.writer = None
        super()._on_mda_finished(sequence)

    def _create_writer(
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
