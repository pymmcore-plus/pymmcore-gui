from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)
from pymmcore_widgets.mda._core_channels import CoreConnectedChannelTable
from pymmcore_widgets.mda._core_grid import CoreConnectedGridPlanWidget
from pymmcore_widgets.mda._core_positions import CoreConnectedPositionTable
from pymmcore_widgets.mda._core_z import CoreConnectedZPlanWidget
from pymmcore_widgets.useq_widgets import MDASequenceWidget
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY, MDATabs
from pymmcore_widgets.useq_widgets._time import TimePlanWidget
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from useq import MDASequence, Position

from micromanager_gui._writers._tensorstore_zarr import _TensorStoreHandler

from ._save_widget import (
    OME_TIFF,
    OME_ZARR,
    WRITERS,
    ZARR_TESNSORSTORE,
    SaveGroupBox,
)

OME_TIFFS = tuple(WRITERS[OME_TIFF])
GB_CACHE = 2_000_000_000  # 2 GB for tensorstore cache

NUM_SPLIT = re.compile(r"(.*?)(?:_(\d{3,}))?$")


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


class CoreMDATabs(MDATabs):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        self._mmc = core or CMMCorePlus.instance()
        super().__init__(parent)

    def create_subwidgets(self) -> None:
        self.time_plan = TimePlanWidget(1)
        self.stage_positions = CoreConnectedPositionTable(1, self._mmc)
        self.z_plan = CoreConnectedZPlanWidget(self._mmc)
        self.grid_plan = CoreConnectedGridPlanWidget(self._mmc)
        self.channels = CoreConnectedChannelTable(1, self._mmc)

    def _enable_tabs(self, enable: bool) -> None:
        """Enable or disable the tab checkboxes and their contents.

        However, we can still mover through the tabs and see their contents.
        """
        # disable tab checkboxes
        for cbox in self._cboxes:
            cbox.setEnabled(enable)
        # disable tabs contents
        self.time_plan.setEnabled(enable)
        self.stage_positions.setEnabled(enable)
        self.z_plan.setEnabled(enable)
        self.grid_plan.setEnabled(enable)
        self.channels.setEnabled(enable)


class MDAWidget(MDASequenceWidget):
    """Main MDA Widget connected to a [`pymmcore_plus.CMMCorePlus`][] instance.

    It provides a GUI to construct and run a [`useq.MDASequence`][].  Unlike
    [`useq_widgets.MDASequenceWidget`][pymmcore_widgets.MDASequenceWidget], this
    widget is connected to a [`pymmcore_plus.CMMCorePlus`][] instance, enabling
    awareness and control of the current state of the microscope.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        # create a couple core-connected variants of the tab widgets
        self._mmc = mmcore or CMMCorePlus.instance()

        super().__init__(parent=parent, tab_widget=CoreMDATabs(None, self._mmc))

        self.save_info = SaveGroupBox(parent=self)
        self.save_info.valueChanged.connect(self.valueChanged)
        self.control_btns = _MDAControlButtons(self._mmc, self)

        # writer for saving the MDA sequence. This is used by the MDAViewer to set its
        # internal datastore. If _writer is None, the MDAViewer will use its default
        # internal datastore.
        self.writer: OMETiffWriter | OMEZarrWriter | TensorStoreHandler | None = None

        # -------- initialize -----------

        self._on_sys_config_loaded()

        # ------------ layout ------------

        layout = cast("QBoxLayout", self.layout())
        layout.insertWidget(0, self.save_info)
        layout.addWidget(self.control_btns)

        # setContentsMargins
        pos_layout = cast("QVBoxLayout", self.stage_positions.layout())
        pos_layout.setContentsMargins(10, 10, 10, 10)
        time_layout = cast("QVBoxLayout", self.time_plan.layout())
        time_layout.setContentsMargins(10, 10, 10, 10)

        # ------------ connect signals ------------

        self.control_btns.run_btn.clicked.connect(self.run_mda)
        self.control_btns.pause_btn.released.connect(self._mmc.mda.toggle_pause)
        self.control_btns.cancel_btn.released.connect(self._mmc.mda.cancel)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)

        self.destroyed.connect(self._disconnect)

    # ----------- Override type hints in superclass -----------

    @property
    def channels(self) -> CoreConnectedChannelTable:
        return cast("CoreConnectedChannelTable", self.tab_wdg.channels)

    @property
    def z_plan(self) -> CoreConnectedZPlanWidget:
        return cast("CoreConnectedZPlanWidget", self.tab_wdg.z_plan)

    @property
    def stage_positions(self) -> CoreConnectedPositionTable:
        return cast("CoreConnectedPositionTable", self.tab_wdg.stage_positions)

    @property
    def grid_plan(self) -> CoreConnectedGridPlanWidget:
        return cast("CoreConnectedGridPlanWidget", self.tab_wdg.grid_plan)

    # ------------------- public Methods ----------------------

    def value(self) -> MDASequence:
        """Set the current state of the widget from a [`useq.MDASequence`][]."""
        val = super().value()
        replace: dict = {}

        # if the z plan is relative and there are stage positions but the 'include z' is
        # unchecked, use the current z stage position as the relative starting one.
        if (
            val.z_plan
            and val.z_plan.is_relative
            and (val.stage_positions and not self.stage_positions.include_z.isChecked())
        ):
            z = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
            replace["stage_positions"] = tuple(
                pos.replace(z=z) for pos in val.stage_positions
            )

        # if there is an autofocus_plan but the autofocus_motor_offset is None, set it
        # to the current value
        if (afplan := val.autofocus_plan) and afplan.autofocus_motor_offset is None:
            p2 = afplan.replace(autofocus_motor_offset=self._mmc.getAutoFocusOffset())
            replace["autofocus_plan"] = p2

        # if there are no stage positions, use the current stage position
        if not val.stage_positions:
            replace["stage_positions"] = (self._get_current_stage_position(),)
            # if "p" is not in the axis order, we need to add it or the position will
            # not be in the event
            if "p" not in val.axis_order:
                axis_order = list(val.axis_order)
                # add the "p" axis at the beginning or after the "t" as the default
                if "t" in axis_order:
                    axis_order.insert(axis_order.index("t") + 1, "p")
                else:
                    axis_order.insert(0, "p")
                replace["axis_order"] = tuple(axis_order)

        if replace:
            val = val.replace(**replace)

        meta: dict = val.metadata.setdefault(PYMMCW_METADATA_KEY, {})
        if self.save_info.isChecked():
            meta.update(self.save_info.value())
        return val  # type: ignore

    def setValue(self, value: MDASequence) -> None:
        """Get the current state of the widget as a [`useq.MDASequence`][]."""
        super().setValue(value)
        self.save_info.setValue(value.metadata.get(PYMMCW_METADATA_KEY, {}))

    def get_next_available_path(self, requested_path: Path) -> Path:
        """Get the next available path.

        This method is called immediately before running an MDA to ensure that the file
        being saved does not overwrite an existing file. It is also called at the end
        of the experiment to update the save widget with the next available path.

        It may be overridden to provide custom behavior, but it should always return a
        Path object to a non-existing file or folder.

        The default behavior adds/increments a 3-digit counter at the end of the path
        (before the extension) if the path already exists.

        Parameters
        ----------
        requested_path : Path
            The path we are requesting for use.
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

        Returns
        -------
        bool
            False if MDA to be cancelled due to autofocus issue.
        str | Path
            Preparation successful, save path to be used for saving and saving active
        None
            Preparation successful, saving deactivated
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

    def execute_mda(self, output: Path | str | object | None) -> None:
        """Execute the MDA experiment corresponding to the current value."""
        sequence = self.value()
        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=output)

    def run_mda(self) -> None:
        save_path = self.prepare_mda()
        if save_path is False:
            return
        self.execute_mda(save_path)

    # ------------------- private Methods ----------------------

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

    def _on_sys_config_loaded(self) -> None:
        # TODO: connect objective change event to update suggested step
        self.z_plan.setSuggestedStep(_guess_NA(self._mmc) or 0.5)

    def _get_current_stage_position(self) -> Position:
        """Return the current stage position."""
        x = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        y = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        z = self._mmc.getPosition() if self._mmc.getFocusDevice() else None
        return Position(x=x, y=y, z=z)

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
            return next_path
        return None

    def _confirm_af_intentions(self) -> bool:
        msg = (
            "You've selected to use autofocus for this experiment, "
            f"but the '{self._mmc.getAutoFocusDevice()!r}' autofocus device "
            "is not currently engaged. "
            "\n\nRun anyway?"
        )

        response = QMessageBox.warning(
            self,
            "Confirm AutoFocus",
            msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return bool(response == QMessageBox.StandardButton.Ok)

    def _enable_widgets(self, enable: bool) -> None:
        for child in self.children():
            if isinstance(child, CoreMDATabs):
                child._enable_tabs(enable)
            elif child is not self.control_btns and hasattr(child, "setEnabled"):
                child.setEnabled(enable)

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)

    def _on_mda_finished(self, sequence: MDASequence) -> None:
        self.writer = None
        self._enable_widgets(True)
        # update the save name in the gui with the next available path
        # FIXME: this is actually a bit error prone in the case of super fast
        # experiments and delayed writers that haven't yet written anything to disk
        # (e.g. the next available path might be the same as the current one)
        # however, the quick fix of using a QTimer.singleShot(0, ...) makes for
        # difficulties in testing.
        # FIXME: Also, we really don't care about the last sequence at this point
        # anyway.  We should just update the save widget with the next available path
        # based on what's currently in the save widget, since that's what really
        # matters (not whatever the last requested mda was)
        self._update_save_path_from_metadata(sequence)

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)


class _MDAControlButtons(QWidget):
    """Run, pause, and cancel buttons at the bottom of the MDA Widget."""

    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mmc = mmcore
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        icon_size = QSize(24, 24)
        self.run_btn = QPushButton("Run")
        self.run_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.run_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
        self.run_btn.setIconSize(icon_size)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_btn.setIconSize(icon_size)
        self.pause_btn.hide()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.setIcon(icon(MDI6.stop_circle_outline, color="#C33"))
        self.cancel_btn.setIconSize(icon_size)
        self.cancel_btn.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.run_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.cancel_btn)

        self.destroyed.connect(self._disconnect)

    def _on_mda_started(self) -> None:
        self.run_btn.hide()
        self.pause_btn.show()
        self.cancel_btn.show()

    def _on_mda_finished(self) -> None:
        self.run_btn.show()
        self.pause_btn.hide()
        self.cancel_btn.hide()
        self._on_mda_paused(False)

    def _on_mda_paused(self, paused: bool) -> None:
        if paused:
            self.pause_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
            self.pause_btn.setText("Pause")

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequencePauseToggled.disconnect(self._on_mda_paused)
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)


def _guess_NA(core: CMMCorePlus) -> float | None:
    with suppress(RuntimeError):
        if not (pix_cfg := core.getCurrentPixelSizeConfig()):
            return None  # pragma: no cover

        data = core.getPixelSizeConfigData(pix_cfg)
        for obj in core.guessObjectiveDevices():
            key = (obj, Keyword.Label)
            if key in data:
                val = data[key]
                for word in val.split():
                    try:
                        na = float(word)
                    except ValueError:
                        continue
                    if 0.1 < na < 1.5:
                        return na
    return None
