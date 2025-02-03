from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Literal

import numpy as np
import pygfx
from cmap import Colormap
from pymmcore_widgets import LiveButton
from PyQt6.QtCore import QObject, QSize, Qt, QTimerEvent
from PyQt6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    import rendercanvas.qt
    from cmap._colormap import ColorStopsLike
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]

else:
    from rendercanvas.qt import QRenderWidget

_DEFAULT_WAIT = 10


class PygfxImagePreview(QWidget):
    """A Widget that displays the last image snapped by active core.

    This widget will automatically update when the active core snaps an image, when the
    active core starts streaming or when a Multi-Dimensional Acquisition is running.

    This is a single-image-node viewer optimized for speed.

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
    mouse_wheel_sensitivity: float
        The sensitivity of the mouse wheel for zooming. By default, 0.004.  Higher
        means faster zooming.

    Attributes
    ----------
    data : np.ndarray | None
        The data of the image.
    clims : tuple[float, float]
        The contrast limits of the image.
    cmap : Colormap
        The colormap (lookup table) of the image.
    use_with_mda : bool
        Whether the widget updates when a Multi-Dimensional Acquisition is running.
    """

    def __init__(
        self,
        parent: QWidget | None,
        mmcore: CMMCorePlus,
        *,
        use_with_mda: bool = False,
        mouse_wheel_sensitivity: float = 0.004,
    ):
        super().__init__(parent)
        self.use_with_mda = use_with_mda

        self._mmc: CMMCorePlus | None = None

        self._clims: tuple[float, float] | Literal["auto"] = "auto"
        self._cmap: Colormap = Colormap("gray")
        self._timer_id: int | None = None  # timer for streaming

        # IMAGE NODE

        self._texture = pygfx.Texture(dim=2, size=(1, 1), format="1xf4")
        self._geometry = pygfx.Geometry(grid=self._texture)
        self._material = pygfx.ImageBasicMaterial(
            clim=(0, 1), map=self._cmap.to_pygfx()
        )
        self._image_node = pygfx.Image(self._geometry, self._material, visible=False)

        # SCENE

        self._scene = scene = pygfx.Scene()
        # slight gradient background
        top = np.array((50, 50, 50, 255)) / 255
        bot = np.array((30, 30, 30, 255)) / 255
        scene.add(pygfx.Background(None, pygfx.BackgroundMaterial(bot, top)))

        self._canvas = QRenderWidget()
        self._renderer = renderer = pygfx.WgpuRenderer(self._canvas)
        self._camera = camera = pygfx.OrthographicCamera()
        self._scene.add(self._image_node)
        self._scene.add(self._camera)
        self.reset_view()
        self._controller = pygfx.PanZoomController(
            camera, register_events=renderer, damping=2
        )

        # faster mouse wheel
        self._controller.controls["wheel"] = (
            "zoom_to_point",
            "push",
            -mouse_wheel_sensitivity,
        )
        self._controller.add_camera(self._camera)
        self._canvas.request_draw(self._draw_function)  # critical for showing

        self.attach(mmcore)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        if isinstance(parent, QObject):
            parent.destroyed.connect(self.detach)

    def sizeHint(self) -> QSize:
        return self._canvas.sizeHint()

    def attach(self, core: CMMCorePlus) -> None:
        """Attach this widget to events in `core`."""
        if self._mmc is not None:
            self.detach()
        ev = core.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStarted.connect(self._on_streaming_start)
        ev.sequenceAcquisitionStopped.connect(self._on_streaming_stop)
        ev.exposureChanged.connect(self._on_exposure_changed)
        self._mmc = core

    def detach(self) -> None:
        """Detach this widget from events in `core`."""
        if self._mmc is None:
            return
        with suppress(Exception):
            ev, self._mmc = self._mmc.events, None
            ev.imageSnapped.disconnect(self._on_image_snapped)
            ev.continuousSequenceAcquisitionStarted.disconnect(self._on_streaming_start)
            ev.sequenceAcquisitionStarted.disconnect(self._on_streaming_start)
            ev.sequenceAcquisitionStopped.disconnect(self._on_streaming_stop)
            ev.exposureChanged.disconnect(self._on_exposure_changed)

    @property
    def data(self) -> np.ndarray | None:
        """Return current texture data."""
        return self._texture.data

    def set_data(self, data: np.ndarray) -> None:
        """Set texture data.

        The dtype must be compatible with wgpu texture formats.
        Will also apply contrast limits if _clims is "auto".
        """
        if self._clims == "auto":
            self._material.clim = np.min(data), np.max(data)
        try:
            self._texture.set_data(data)
        except (ValueError, AttributeError):
            # texture has wrong shape or format, recreate it
            self._texture = pygfx.Texture(data, dim=2)
            self._geometry.grid = self._texture
            self.reset_view()
        self._image_node.visible = True

    @property
    def clims(self) -> tuple[float, float]:
        """Get the contrast limits of the image."""
        return self._material.clim  # type: ignore [no-any-return]

    def set_clims(self, clims: tuple[float, float] | Literal["auto"]) -> None:
        """Set the contrast limits of the image.

        Parameters
        ----------
        clims : tuple[float, float], or "auto"
            The contrast limits to set.
        """
        self._clims = clims
        if clims == "auto":
            if self.data is not None:
                self._material.clim = np.min(self.data), np.max(self.data)
        else:
            self._material.clim = clims

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
        self._cmap = cm = Colormap(cmap)
        self._material.map = cm.to_pygfx()

    @property
    def interpolation(self) -> Literal["nearest", "linear"]:
        """Return the interpolation method."""
        return self._material.interpolation  # type: ignore [no-any-return]

    def set_interpolation(self, interpolation: Literal["nearest", "linear"]) -> None:
        """Set the interpolation method."""
        self._material.interpolation = interpolation

    def reset_view(self, scale: float = 0.8) -> None:
        """Reset the view so that the image fills the widget area."""
        self._camera.show_object(self._image_node, scale=scale)  # pyright: ignore [reportArgumentType]

    # ----------------------------

    def _draw_function(self) -> None:
        self._renderer.render(self._scene, self._camera)
        self._renderer.request_draw()

    def _on_exposure_changed(self, device: str, value: str) -> None:
        # change timer interval
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = self.startTimer(int(value), Qt.TimerType.PreciseTimer)

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        if (core := self._mmc) and core.getRemainingImageCount() > 0:
            img = core.getLastImage()
            self.set_data(img)

    def _on_image_snapped(self) -> None:
        if (core := self._mmc) is None:
            return  # pragma: no cover
        if not self.use_with_mda and core.mda.is_running():
            return  # pragma: no cover

        last = core.getImage()
        self.set_data(last)

    def _on_streaming_start(self) -> None:
        if (core := self._mmc) is not None:
            wait = int(core.getExposure()) or _DEFAULT_WAIT
            self._timer_id = self.startTimer(wait, Qt.TimerType.PreciseTimer)

    def _on_streaming_stop(self) -> None:
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None


if __name__ == "__main__":  # pragma: no cover
    from pymmcore_plus import CMMCorePlus
    from pymmcore_widgets import SnapButton
    from PyQt6.QtWidgets import QApplication

    core = CMMCorePlus()
    core.loadSystemConfiguration()

    app = QApplication([])
    widget = PygfxImagePreview(None, core)
    widget.show()
    snap = SnapButton(parent=None, mmcore=core)
    snap.show()
    live = LiveButton(parent=None, mmcore=core)
    live.show()

    app.exec()
