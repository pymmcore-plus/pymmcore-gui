from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Literal

import numpy as np
import pygfx
from cmap import Colormap
from PyQt6.QtCore import QObject, Qt, QTimerEvent
from PyQt6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    import rendercanvas.qt
    from cmap._colormap import ColorStopsLike
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]

else:
    from rendercanvas.qt import QRenderWidget

_DEFAULT_WAIT = 10


class ImagePreview(QWidget):
    """A Widget that displays the last image snapped by active core.

    This widget will automatically update when the active core snaps an image, when the
    active core starts streaming or when a Multi-Dimensional Acquisition is running.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    use_with_mda: bool
        If False, the widget will not update when a Multi-Dimensional Acquisition is
        running. By default, True.
    """

    def __init__(
        self,
        parent: QWidget | None,
        mmcore: CMMCorePlus,
        *,
        use_with_mda: bool = False,
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore
        self._use_with_mda = use_with_mda

        self._clims: tuple[float, float] | Literal["auto"] = "auto"
        self._cmap: Colormap = Colormap("viridis")
        self._timer_id: int | None = None
        # IMAGE NODE

        self._texture = pygfx.Texture(np.zeros((512, 512), dtype=np.uint8), dim=2)
        self._geometry = pygfx.Geometry(grid=self._texture)
        self._material = pygfx.ImageBasicMaterial(
            clim=(0, 1), map=self._cmap.to_pygfx()
        )
        self._image_node = img = pygfx.Image(self._geometry, self._material)

        # SCENE

        self._scene = pygfx.Scene()
        self._scene.add(self._image_node)
        self._canvas = QRenderWidget(self)
        self._renderer = renderer = pygfx.WgpuRenderer(self._canvas)
        self._camera = camera = pygfx.OrthographicCamera()
        self._camera.show_object(img, up=(0, 1, 0), scale=1.4)  # pyright: ignore [reportArgumentType]
        self._scene.add(self._camera)
        self._controller = pygfx.PanZoomController(camera, register_events=renderer)
        self._canvas.request_draw(self._draw_function)

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        if isinstance(parent, QObject):
            parent.destroyed.connect(self._disconnect)

    def _draw_function(self) -> None:
        self._renderer.render(self._scene, self._camera)
        self._renderer.request_draw()

    @property
    def use_with_mda(self) -> bool:
        """Get whether the widget should update when a MDA is running."""
        return self._use_with_mda

    @use_with_mda.setter
    def use_with_mda(self, use_with_mda: bool) -> None:
        """Set whether the widget should update when a MDA is running.

        Parameters
        ----------
        use_with_mda : bool
            Whether the widget is used with MDA.
        """
        self._use_with_mda = use_with_mda

    def _disconnect(self) -> None:
        with suppress(RuntimeError):
            ev = self._mmc.events
            ev.imageSnapped.disconnect(self._on_image_snapped)
            ev.continuousSequenceAcquisitionStarted.disconnect(self._on_streaming_start)
            ev.sequenceAcquisitionStopped.disconnect(self._on_streaming_stop)
            ev.exposureChanged.disconnect(self._on_exposure_changed)

    def _on_streaming_start(self) -> None:
        wait = int(self._mmc.getExposure()) or _DEFAULT_WAIT
        self._timer_id = self.startTimer(wait, Qt.TimerType.PreciseTimer)

    def _on_streaming_stop(self) -> None:
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None

    def _on_exposure_changed(self, device: str, value: str) -> None:
        # change timer interval
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = self.startTimer(int(value), Qt.TimerType.PreciseTimer)

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        self._on_image_snapped()

    def _on_image_snapped(self) -> None:
        if not self._use_with_mda and self._mmc.mda.is_running():
            return

        with suppress(RuntimeError):
            last = self._mmc.getImage()
            self.set_data(last)

    @property
    def data(self) -> np.ndarray | None:
        return self._texture.data  # type: ignore [no-any-return]

    def set_data(self, data: np.ndarray) -> None:
        """Set the data of the image.

        The dtype must be compatible with wgpu texture formats.s
        """
        # if self._clims == "auto":
        self._material.clim = np.min(data), np.max(data)
        print(" > DATA", data.shape, data.dtype, self._material.clim)
        self._texture = pygfx.Texture(data, dim=2)
        self._geometry = pygfx.Geometry(grid=self._texture)

    @property
    def clims(self) -> tuple[float, float]:
        """Get the contrast limits of the image."""
        return self._material.clim  # type: ignore [no-any-return]

    def set_clims(self, clims: tuple[float, float]) -> None:
        """Set the contrast limits of the image.

        Parameters
        ----------
        clims : tuple[float, float], or "auto"
            The contrast limits to set.
        """
        print(" > clims", clims)
        self._material.clim = clims
        self._clims = clims

    @property
    def cmap(self) -> Colormap:
        """Get the colormap (lookup table) of the image."""
        return self._cmap

    def set_cmap(self, cmap: ColorStopsLike) -> None:
        """Set the colormap (lookup table) of the image.

        Parameters
        ----------
        cmap : str
            The colormap to use.
        """
        cmap = Colormap(cmap)
        self._cmap = cmap
        self._material.map = cmap.to_pygfx()
