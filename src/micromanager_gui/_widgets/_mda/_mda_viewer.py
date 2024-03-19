from __future__ import annotations

from typing import TYPE_CHECKING, Any, MutableMapping, cast

import zarr
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter
from pymmcore_plus.mda.handlers._ome_zarr_writer import POS_PREFIX
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt import QLabeledDoubleRangeSlider
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._sliders import _AxisSlider

if TYPE_CHECKING:
    import os
    from typing import Literal

    import numpy as np
    import useq
    from fsspec import FSMap

BTN_SIZE = (60, 40)


class MDAViewer(OMEZarrWriter, QWidget):
    """A Widget that displays an MDA sequence.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    store : MutableMapping | str | os.PathLike | FSMap | None = None
        The store to use for the zarr group. By default, None.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
        store: MutableMapping | str | os.PathLike | FSMap | None = None,
        canvas_size: tuple[int, int] | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        try:
            from vispy import scene
        except ImportError as e:
            raise ImportError(
                "vispy is required for ImagePreview. "
                "Please run `pip install pymmcore-widgets[image]`"
            ) from e

        super().__init__(store, *args, **kwargs)
        QWidget.__init__(self, parent)

        self.setWindowTitle("MDA Viewer")

        self._mmc = mmcore or CMMCorePlus.instance()
        self._canvas_size = canvas_size

        # buttons groupbox
        btn_wdg = QGroupBox()
        btn_wdg_layout = QHBoxLayout(btn_wdg)
        btn_wdg_layout.setContentsMargins(10, 0, 10, 0)
        # auto contrast checkbox
        self._auto = QCheckBox("Auto")
        self._auto.setChecked(True)
        self._auto.setToolTip("Auto Contrast")
        self._auto.setFixedSize(*BTN_SIZE)
        self._auto.toggled.connect(self._clims_auto)
        # LUT slider
        self._lut_slider = QLabeledDoubleRangeSlider()
        self._lut_slider.setDecimals(0)
        self._lut_slider.valueChanged.connect(self._on_range_changed)
        # reset view button
        self._reset_view = QPushButton()
        self._reset_view.clicked.connect(self._reset)
        self._reset_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._reset_view.setToolTip("Reset View")
        self._reset_view.setIcon(icon(MDI6.home_outline))
        self._reset_view.setIconSize(QSize(25, 25))
        self._reset_view.setFixedSize(*BTN_SIZE)
        # save button
        self._save = QPushButton()
        self._save.clicked.connect(self._on_save)
        self._save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._save.setToolTip("Save as Zarr")
        self._save.setIcon(icon(MDI6.content_save_outline))
        self._save.setIconSize(QSize(25, 25))
        self._save.setFixedSize(*BTN_SIZE)

        # add to layout
        btn_wdg_layout.addWidget(self._lut_slider)
        btn_wdg_layout.addWidget(self._auto)
        btn_wdg_layout.addWidget(self._reset_view)
        btn_wdg_layout.addWidget(self._save)

        # # connect core signals
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self._mda_running: bool = False

        self._sliders: dict[str, _AxisSlider] | None = None

        self._imcls = scene.visuals.Image
        self._clims: tuple[float, float] | Literal["auto"] = "auto"
        self._cmap: str = "grays"

        self._canvas = scene.SceneCanvas(
            keys="interactive", size=(512, 512), parent=self
        )
        self.view = self._canvas.central_widget.add_view(camera="panzoom")
        self.view.camera.aspect = 1

        self.image: scene.visuals.Image | None = None

        self._sliders_widget = QGroupBox()
        self._sliders_layout = QVBoxLayout(self._sliders_widget)
        self._sliders_layout.setContentsMargins(10, 0, 10, 0)
        self._sliders_layout.setSpacing(5)

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(5)
        self.layout().addWidget(self._canvas.native)
        self.layout().addWidget(self._sliders_widget)
        self.layout().addWidget(btn_wdg)

        self.destroyed.connect(self._disconnect)

        if bit := self._mmc.getImageBitDepth():
            with signals_blocked(self._lut_slider):
                self._lut_slider.setRange(0, 2**bit - 1)
                self._lut_slider.setValue((0, 2**bit - 1))

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        """Set the canvas size to half of the image size."""
        self._canvas.size = self._canvas_size or (
            int(self._mmc.getImageWidth() / 2),
            int(self._mmc.getImageHeight() / 2),
        )

    def _disconnect(self) -> None:
        """Disconnect the signals."""
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)

    def sequenceStarted(self, sequence: useq.MDASequence) -> None:
        # this method is called be in `_CoreLink` when the MDA sequence starts
        self._mda_running = True
        super().sequenceStarted(sequence)

    def sequenceFinished(self, sequence: useq.MDASequence) -> None:
        super().sequenceFinished(sequence)
        if not self._sliders:
            self._sliders_widget.hide()
        self._mda_running = False
        self._disconnect()

    def frameReady(self, image: np.ndarray, event: useq.MDAEvent, meta: dict) -> None:
        """Update the image and sliders when a new frame is ready."""
        super().frameReady(image, event, meta)
        # update the image in the viewer
        self._update_image(image)
        # get the position key to select which array to use
        key = f"{POS_PREFIX}{event.index.get(POS_PREFIX, 0)}"
        # get the data array
        data = self.position_arrays[key]
        # get the index keys from zarr attrs and remove 'x' and 'y'
        index_keys = cast(list[str], data.attrs["_ARRAY_DIMENSIONS"][:-2])

        if self._sliders is not None:
            self._update_sliders_position(event, index_keys)

        if self._sliders is None:
            # if self._sliders is None, create the sliders
            self._initialize_sliders(data, index_keys, event)
        else:
            # create any missing slider if the shape of the data has changed (e.g. if
            # the shape of the position differs from any of the previous)
            self._update_sliders(data, index_keys)

    def _update_image(self, image: np.ndarray) -> None:
        """Update the image in the viewer."""
        clim = (image.min(), image.max()) if self._clims == "auto" else self._clims
        if self.image is None:
            # first time we see this position, create the image
            self.image = self._imcls(
                image, cmap=self._cmap, clim=clim, parent=self.view.scene
            )
            self.view.camera.set_range(margin=0)
        else:
            # we have seen this position before, update the image
            self.image.set_data(image)
            self.image.clim = clim

        # update the LUT slider to match the new image
        with signals_blocked(self._lut_slider):
            if isinstance(clim, tuple):
                self._lut_slider.setValue(clim)
            else:
                self._lut_slider.setValue((image.min(), image.max()))

    def _update_sliders_position(
        self, event: useq.MDAEvent, index_keys: list[str]
    ) -> None:
        """Update the sliders to match the new position."""
        if self._sliders is None:
            return

        # move the position sliders to the current position
        if POS_PREFIX in self._sliders:
            self._update_slider_range_and_value(POS_PREFIX, event)
            self._enable_sliders(index_keys)
        # move all the other sliders to the current position
        for key in index_keys:
            if key in self._sliders:
                self._update_slider_range_and_value(key, event)

    def _update_slider_range_and_value(self, key: str, event: useq.MDAEvent) -> None:
        """Update the sliders to match the new dimensions."""
        if self._sliders is None:
            return
        index = event.index.get(key, 0)
        # set the range of the slider
        self._sliders[key].setRange(0, index)
        # set the value of the slider
        # block signals to avoid triggering "_on_slider_value_changed"
        self._sliders[key].blockSignals(True)
        self._sliders[key].setValue(index)
        self._sliders[key].blockSignals(False)

    def _enable_sliders(self, dims: list[str]) -> None:
        """Enable only sliders with the keys that are in the data attrs."""
        # useful when we have a jagged array
        if self._sliders is None:
            return
        for sl in self._sliders:
            if sl == POS_PREFIX:
                continue
            self._sliders[sl].setEnabled(sl in dims)

    def _initialize_sliders(
        self, data: np.ndarray, index_keys: list[str], event: useq.MDAEvent
    ) -> None:
        """Create the sliders for the first time."""
        if event.sequence is None:
            return

        self._sliders = {}

        # create position slider if there is more than one position.
        # the OMEZarrDatastore divides the data into positions using the POS_PREFIX
        # so we can use that to create the position sliders
        if POS_PREFIX not in self._sliders and len(event.sequence.stage_positions) > 1:
            self._create_and_add_slider(POS_PREFIX, 1)

        if POS_PREFIX in index_keys:
            index_keys.remove(POS_PREFIX)

        # create sliders for any other axis
        self._create_sliders_for_dimensions(data, index_keys)

    def _create_and_add_slider(self, key: str, range_end: int) -> None:
        """Create a slider for the given key and add it to the _sliders_layout."""
        slider = self._create_axis_slider(key, range_end)
        if slider is not None:
            self._sliders_layout.addWidget(slider)

    def _create_axis_slider(self, key: str, range_end: int) -> _AxisSlider | None:
        """Create a slider for the given key."""
        if self._sliders is None:
            return None
        slider = _AxisSlider(key, parent=self)
        slider.valueChanged.connect(self._on_slider_value_changed)
        slider.setRange(0, range_end)
        self._sliders[key] = slider
        return slider

    def _create_sliders_for_dimensions(
        self, data: np.ndarray, index_keys: list[str]
    ) -> None:
        """Create a slider for each index key if the corresponding shape is > 1."""
        if self._sliders is None:
            return
        for idx, sh in enumerate(data.shape[:-2]):
            if sh > 1 and index_keys[idx] not in self._sliders:
                self._create_and_add_slider(index_keys[idx], data.shape[idx] - 1)

    def _update_sliders(self, data: np.ndarray, index_keys: list[str]) -> None:
        """Update the sliders to match the new dimensions."""
        if self._sliders is None:
            return

        if POS_PREFIX in index_keys:
            index_keys.remove(POS_PREFIX)

        # create a slider if the key is not yet in the sliders
        if any(k not in self._sliders for k in index_keys):
            self._create_sliders_for_dimensions(data, index_keys)

    def _on_slider_value_changed(self, value: int) -> None:
        """Update the shown image when the slider value changes."""
        if self._sliders is None or self.image is None:
            return

        # get the position slider
        pos_slider = self._sliders.get(POS_PREFIX, None)

        # get the position key to select which array to use
        key = "p0" if pos_slider is None else f"p{pos_slider.value()}"

        # get the data array
        data = self.position_arrays[key]

        # get the index keys from zarr attrs and remove 'x' and 'y'
        dims = data.attrs["_ARRAY_DIMENSIONS"][:-2]

        # disable sliders that are not in the data attrs (if we have multiple positions)
        sender = cast(_AxisSlider, self.sender())
        if sender.axis == POS_PREFIX:
            self._enable_sliders(dims)
            if not self._mda_running:
                # update the sliders range to match the data array
                # e.g. if a pos has a 2x1 grid and another has a 2x2 grid, when moving
                # the pos slider the range of the g slider should change
                self._set_slider_range(dims, data)

        # get the index values from the sliders
        index = tuple(
            self._sliders[dim].value()
            for dim in dims
            if dim in self._sliders and dim != POS_PREFIX
        )

        # get the image from the data array
        # squeeze the data to remove any dimensions of size 1
        image = data[index].squeeze()

        # display the image in the viewer
        self.image.set_data(image)
        clim = (image.min(), image.max()) if self._clims == "auto" else self._clims
        self.image.clim = clim

    def _set_slider_range(self, dims: list[str], data: np.ndarray) -> None:
        """Set the range of the sliders to match the data."""
        if self._sliders is None:
            return
        for dim in dims:
            if dim in self._sliders:
                self._sliders[dim].setRange(0, data.shape[dims.index(dim)] - 1)

    def _reset(self) -> None:
        """Reset the preview."""
        x = (0, self._mmc.getImageWidth()) if self._mmc.getImageWidth() else None
        y = (0, self._mmc.getImageHeight()) if self._mmc.getImageHeight() else None
        self.view.camera.set_range(x, y, margin=0)

    def _on_range_changed(self, range: tuple[float, float]) -> None:
        """Update the LUT range."""
        self.clims = range
        self._auto.setChecked(False)

    def _clims_auto(self, state: bool) -> None:
        """Set the LUT range to auto."""
        self.clims = "auto" if state else self._lut_slider.value()

        if self.image is None:
            return

        image = self.image._data
        with signals_blocked(self._lut_slider):
            self._lut_slider.setValue((image.min(), image.max()))

    @property
    def clims(self) -> tuple[float, float] | Literal["auto"]:
        """Get the contrast limits of the image."""
        return self._clims

    @clims.setter
    def clims(self, clims: tuple[float, float] | Literal["auto"] = "auto") -> None:
        """Set the contrast limits of the image.

        Parameters
        ----------
        clims : tuple[float, float], or "auto"
            The contrast limits to set.
        """
        if self.image is not None:
            self.image.clim = clims

        self._clims = clims

    @property
    def cmap(self) -> str:
        """Get the colormap (lookup table) of the image."""
        return self._cmap

    @cmap.setter
    def cmap(self, cmap: str = "grays") -> None:
        """Set the colormap (lookup table) of the image.

        Parameters
        ----------
        cmap : str
            The colormap to use.
        """
        if self.image is not None:
            self.image.cmap = cmap

        self._cmap = cmap

    def _on_save(self) -> None:
        """Save the data as a zarr."""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Saving directory and filename.",
            "",
            "ZARR (*.zarr);",
        )
        if save_path:
            dir_store = zarr.DirectoryStore(save_path)
            zarr.copy_store(self._group.attrs.store, dir_store)
