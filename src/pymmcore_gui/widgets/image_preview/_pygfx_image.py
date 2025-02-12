from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
import pygfx
from cmap import Colormap
from PyQt6.QtCore import QObject, QSize
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ._preview_base import _ImagePreviewBase

if TYPE_CHECKING:
    import rendercanvas.qt
    from cmap._colormap import ColorStopsLike
    from pymmcore_plus import CMMCorePlus

    class QRenderWidget(rendercanvas.qt.QRenderWidget, QWidget): ...  # pyright: ignore [reportIncompatibleMethodOverride]

else:
    from rendercanvas.qt import QRenderWidget

_DEFAULT_WAIT = 10


class PygfxImagePreview(_ImagePreviewBase):
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
        super().__init__(parent, mmcore, use_with_mda=use_with_mda)

        self._clims: tuple[float, float] | Literal["auto"] = "auto"
        self._cmap: Colormap = Colormap("gray")

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        if isinstance(parent, QObject):
            parent.destroyed.connect(self.detach)

    def sizeHint(self) -> QSize:
        return self._canvas.sizeHint()

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
