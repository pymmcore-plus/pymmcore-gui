"""A widget that paints a smooth, dithered linear gradient with optional watermark."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QColor, QImage, QPainter, QPixmap
from qtpy.QtWidgets import QWidget

from pymmcore_gui._qt.Qlementine import QlementineStyle  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from qtpy.QtCore import QSize
    from qtpy.QtWidgets import QWidget as QWidgetType

LOGO_PATH = Path(__file__).parent.parent / "resources" / "logo_trans.png"

# Bayer 4x4 ordered-dither threshold matrix, normalised to [-0.5, 0.5).
_BAYER = np.array(
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
    dtype=np.float32,
)
_BAYER_NORM = (_BAYER + 0.5) / 16.0 - 0.5


def dithered_gradient_bgra(
    color_top: tuple[int, int, int],
    color_bottom: tuple[int, int, int],
    width: int,
    height: int,
) -> np.ndarray:
    """Generate a dithered vertical gradient as an (h, w, 4) BGRA uint8 array."""
    top = np.array(color_top, dtype=np.float32)
    bot = np.array(color_bottom, dtype=np.float32)

    # (h, 1, 3) gradient: each row is a lerp between top and bottom.
    t = np.linspace(0.0, 1.0, height, dtype=np.float32).reshape(height, 1, 1)
    gradient = top + (bot - top) * t
    gradient = np.broadcast_to(gradient, (height, width, 3)).copy()

    # Tile the Bayer threshold and add to all 3 channels.
    rows = height // 4 + 1
    cols = width // 4 + 1
    dither = np.tile(_BAYER_NORM, (rows, cols))[:height, :width, np.newaxis]
    gradient += dither

    # Pack into BGRA (Qt ARGB32 is BGRA in memory on little-endian).
    bgra = np.empty((height, width, 4), dtype=np.uint8)
    clamped = np.clip(gradient + 0.5, 0, 255).astype(np.uint8)
    bgra[:, :, 0] = clamped[:, :, 2]  # B
    bgra[:, :, 1] = clamped[:, :, 1]  # G
    bgra[:, :, 2] = clamped[:, :, 0]  # R
    bgra[:, :, 3] = 255  # A
    return bgra


def bgra_to_pixmap(bgra: np.ndarray) -> QPixmap:
    """Convert an (h, w, 4) BGRA uint8 array to a QPixmap."""
    h, w = bgra.shape[:2]
    img = QImage(bytes(bgra.data), w, h, w * 4, QImage.Format.Format_ARGB32)
    return QPixmap.fromImage(img)


def overlay_watermark(
    bgra: np.ndarray,
    icon_path: str | Path,
    color: tuple[int, int, int],
    opacity: float = 0.33,
    scale: float = 0.4,
) -> None:
    """Composite a monochrome watermark onto a BGRA buffer in-place.

    The icon's alpha channel is used as the shape mask. It is tinted with
    `color` and blended at `opacity`. `scale` controls how large the icon
    is relative to the shorter dimension of `bgra`.
    """
    img = QImage(str(icon_path))
    if img.isNull():
        return
    img = img.convertToFormat(QImage.Format.Format_ARGB32)

    h, w = bgra.shape[:2]
    short = min(w, h)
    target = max(int(short * scale), 1)

    # Scale preserving aspect ratio.
    if img.width() >= img.height():
        scaled = img.scaledToWidth(target, Qt.TransformationMode.SmoothTransformation)
    else:
        scaled = img.scaledToHeight(target, Qt.TransformationMode.SmoothTransformation)

    iw, ih = scaled.width(), scaled.height()

    # Extract alpha from the scaled icon.
    ptr = scaled.bits()
    if ptr is None:
        return
    nbytes = ih * iw * 4
    if hasattr(ptr, "asarray"):
        icon_arr = np.array(cast("Any", ptr).asarray(nbytes), dtype=np.uint8)
    else:
        icon_arr = np.frombuffer(cast("bytes", ptr), dtype=np.uint8).copy()
    icon_arr = icon_arr.reshape(ih, iw, 4)
    alpha = icon_arr[:, :, 3].astype(np.float32) / 255.0 * opacity

    # Center in the bgra buffer.
    y0 = (h - ih) // 2
    x0 = (w - iw) // 2
    region = bgra[y0 : y0 + ih, x0 : x0 + iw, :3].astype(np.float32)

    tint = np.array([color[2], color[1], color[0]], dtype=np.float32)  # RGB -> BGR
    alpha3 = alpha[:, :, np.newaxis]
    blended = region * (1.0 - alpha3) + tint * alpha3
    bgra[y0 : y0 + ih, x0 : x0 + iw, :3] = np.clip(blended + 0.5, 0, 255).astype(
        np.uint8
    )


class DitheredGradient(QWidget):
    """Widget that displays a vertical linear gradient with ordered dithering.

    If no explicit colors are provided, pulls backgroundColorMain2 (top)
    and backgroundColorWorkspace (bottom) from the active QlementineStyle theme,
    and updates automatically when the theme changes.
    """

    def __init__(
        self,
        color_top: str | QColor | None = None,
        color_bottom: str | QColor | None = None,
        parent: QWidgetType | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_top = QColor(color_top) if color_top is not None else None
        self._color_bottom = QColor(color_bottom) if color_bottom is not None else None
        self._cache: QPixmap | None = None
        self._cache_size: QSize | None = None

    def changeEvent(self, event: object) -> None:
        if isinstance(event, QEvent) and event.type() == QEvent.Type.StyleChange:
            self._invalidate()
        super().changeEvent(event)  # type: ignore[arg-type]

    def resizeEvent(self, event: object) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        self._cache = None
        self.update()

    def _resolve_colors(self) -> tuple[QColor, QColor, QColor]:
        """Return (top, bottom, watermark) colors, falling back to theme."""
        style = self.style()
        if isinstance(style, QlementineStyle):
            theme = style.theme()
            top = self._color_top or theme.backgroundColorMain2
            bottom = self._color_bottom or theme.backgroundColorWorkspace
            watermark = theme.backgroundColorMain3
            return top, bottom, watermark

        top = self._color_top or QColor("#18191B")
        bot = self._color_bottom or QColor("#0C0C0E")
        return top, bot, QColor("#212225")

    def paintEvent(self, event: object) -> None:
        sz = self.size()
        if sz.width() <= 0 or sz.height() <= 0:
            return

        if self._cache is None or self._cache_size != sz:
            c0, c1, wm = self._resolve_colors()
            bgra = dithered_gradient_bgra(
                (c0.red(), c0.green(), c0.blue()),
                (c1.red(), c1.green(), c1.blue()),
                sz.width(),
                sz.height(),
            )
            if LOGO_PATH.exists():
                overlay_watermark(bgra, LOGO_PATH, (wm.red(), wm.green(), wm.blue()))
            self._cache = bgra_to_pixmap(bgra)
            self._cache_size = sz

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
        painter.end()
