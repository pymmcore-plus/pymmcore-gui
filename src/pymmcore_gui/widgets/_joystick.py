from __future__ import annotations

import math
import threading
from typing import TYPE_CHECKING, ClassVar

from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator

from pymmcore_gui._qt.Qlementine import SegmentedControl  # type: ignore[attr-defined]
from pymmcore_gui._qt.QtCore import (
    QObject,
    QPointF,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from pymmcore_gui._qt.QtGui import QBrush, QPainter, QPen, QRadialGradient
from pymmcore_gui._qt.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from pymmcore_gui._utils import current_core

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QPaintEvent


class JoystickWidget(QWidget):
    """Virtual joystick pad. Emits normalized (dx, dy) in [-1, 1].

    Deflection polarity:
    - when the vector from center to knob points right, dx is positive.
    - when the vector from center to knob points up, dy is positive.
    """

    # TODO: arrow-key / accessibility support

    deflectionChanged = Signal(float, float)  # dx, dy normalized
    released = Signal()

    def __init__(self, parent: QWidget | None = None, dead_zone: float = 0.05):
        super().__init__(parent)
        self._dead_zone = dead_zone
        self._knob_pos = QPointF(0, 0)  # relative to center, in pixels
        self._dragging = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    # ---- geometry helpers ----

    def sizeHint(self) -> QSize:
        return QSize(140, 140)

    @property
    def _radius(self) -> float:
        """Radius of the usable pad area."""
        return float(min(self.width(), self.height())) / 2 - 6

    @property
    def _knob_radius(self) -> float:
        return self._radius * 0.12

    @property
    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _clamp_to_circle(self, pos: QPointF) -> QPointF:
        """Clamp a point (relative to center) to the pad radius."""
        r = self._radius - self._knob_radius
        dist = math.hypot(pos.x(), pos.y())
        if dist > r:
            scale = r / dist
            return QPointF(pos.x() * scale, pos.y() * scale)
        return pos

    def _normalized(self) -> tuple[float, float]:
        r = self._radius - self._knob_radius
        if r <= 0:
            return (0.0, 0.0)
        dx = self._knob_pos.x() / r
        dy = -self._knob_pos.y() / r
        mag = math.hypot(dx, dy)
        if mag < self._dead_zone:
            return (0.0, 0.0)
        # remap [dead_zone, 1] → [0, 1] so there's no jump at the edge
        scale = (mag - self._dead_zone) / (1.0 - self._dead_zone) / mag
        return (dx * scale, dy * scale)

    # ---- mouse handling ----

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:  # type: ignore[comparison-overlap]
            self._dragging = True
            self._update_knob(ev.position())
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._dragging:
            self._update_knob(ev.position())
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:  # type: ignore[comparison-overlap]
            self._dragging = False
            self._knob_pos = QPointF(0, 0)
            self.update()
            self.deflectionChanged.emit(0.0, 0.0)
            self.released.emit()
        super().mouseReleaseEvent(ev)

    def _update_knob(self, global_pos: QPointF) -> None:
        rel = global_pos - self._center
        self._knob_pos = self._clamp_to_circle(rel)
        self.update()
        dx, dy = self._normalized()
        self.deflectionChanged.emit(dx, dy)

    # ---- painting ----

    def paintEvent(self, ev: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self._center
        radius = self._radius
        pal = self.palette()

        # background — use palette base color
        bg_color = pal.window().color()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_color))
        p.drawRect(self.rect())

        # outer ring — use palette mid for border, base for fill
        ring_color = pal.mid().color()
        p.setPen(QPen(ring_color, 2))
        fill = pal.base().color()
        p.setBrush(QBrush(fill))
        p.drawEllipse(center, radius, radius)

        # crosshair
        cross = pal.mid().color()
        cross.setAlpha(80)
        p.setPen(QPen(cross, 1, Qt.PenStyle.DashLine))
        p.drawLine(center + QPointF(-radius, 0), center + QPointF(radius, 0))
        p.drawLine(center + QPointF(0, -radius), center + QPointF(0, radius))

        # vector line from center to knob
        if self._dragging and self._knob_pos != QPointF(0, 0):
            accent = pal.highlight().color()
            accent.setAlpha(100)
            p.setPen(QPen(accent, 3))
            p.drawLine(center, center + self._knob_pos)

        # knob
        knob_center = center + self._knob_pos
        kr = self._knob_radius
        grad = QRadialGradient(knob_center, kr)
        if self._dragging:
            accent = pal.highlight().color()
            grad.setColorAt(0, accent.lighter(130))
            grad.setColorAt(1, accent)
        else:
            fg = pal.mid().color()
            fg.setAlpha(200)
            grad.setColorAt(0, fg)
            fg.setAlpha(120)
            grad.setColorAt(1, fg)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(knob_center, kr, kr)

        p.end()


class StageJoystick(QWidget):
    """Joystick widget that drives an XY stage via QStageMoveAccumulator."""

    # TODO: Z support via vertical slider or modifier-key+drag for focus.
    # QStageMoveAccumulator already supports single-axis StageDevice.

    def __init__(
        self,
        xy_device: str,
        mmcore: CMMCorePlus | None = None,
        max_um_per_sec: float = 4000.0,
        speed_exponent: float = 2.0,
        tick_ms: int = 20,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._device = xy_device
        self._acc = QStageMoveAccumulator.for_device(xy_device, mmcore)
        self._max_speed = max_um_per_sec
        self._speed_exponent = speed_exponent
        self._tick_ms = tick_ms
        self._dx = 0.0
        self._dy = 0.0

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(tick_ms)
        self._tick_timer.timeout.connect(self._on_tick)

        self._joystick = JoystickWidget(self)
        self._joystick.deflectionChanged.connect(self._on_deflection)
        self._joystick.released.connect(self._on_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._joystick)

        self._backlash_orig: dict[str, str] | None = None
        self._is_ASI_stage = (mmcore is not None) and (
            "BacklashX-B(um)" in mmcore.getDevicePropertyNames(self._device)
        )

    def _on_deflection(self, dx: float, dy: float) -> None:
        # Micromanager coordinate system is +X -> stage moves left
        # and +Y -> stage moves up (opposite of X situation).
        # we want the vector of deflection to go in the same direction as stage movement
        # so invert Y here.
        # https://micro-manager.org/Coordinates_and_Directionality
        if (
            self._backlash_orig is None
            and (mmcore := current_core(self))
            and self._is_ASI_stage
        ):
            props = ("BacklashX-B(um)", "BacklashY-B(um)")
            self._backlash_orig = {
                p: mmcore.getProperty(self._device, p) for p in props
            }
            for p in props:
                mmcore.setProperty(self._device, p, 0.0)

        self._dx = dx
        self._dy = -dy
        if not self._tick_timer.isActive() and (dx or dy):
            self._tick_timer.start()

    def _on_release(self) -> None:
        self._tick_timer.stop()
        if self._backlash_orig is not None and (mmcore := current_core(self)):
            for prop, val in self._backlash_orig.items():
                mmcore.setProperty(self._device, prop, val)
            self._backlash_orig = None

    def _on_tick(self) -> None:
        mag = min(math.hypot(self._dx, self._dy), 1.0)
        if mag < 0.05:
            return
        speed = mag**self._speed_exponent * self._max_speed
        ux, uy = self._dx / mag, self._dy / mag
        dt = self._tick_ms / 1000.0
        self._acc.move_relative((ux * speed * dt, uy * speed * dt))


class _ASIDeviceWorker(QObject):
    """Worker that performs all ASI stage I/O on a dedicated thread.

    The main thread writes the target velocity via set_target_velocity()
    (lock-protected, no queuing). A tick timer on the worker thread
    periodically applies the latest velocity and updates safe limits.
    """

    _LIMIT_PROPS = ("LowerLimX(mm)", "LowerLimY(mm)", "UpperLimX(mm)", "UpperLimY(mm)")
    TICK_MS: int = 50
    LIMIT_UPDATE_EVERY: int = 4  # update limits every N ticks (~200ms at 50ms tick)

    def __init__(self, device: str, mmcore: CMMCorePlus, safe_radius_mm: float) -> None:
        super().__init__()
        self._device = device
        self._mmcore = mmcore
        self._safe_radius_mm = safe_radius_mm
        self._orig_limits: dict[str, str] | None = None
        self._lock = threading.Lock()
        self._target_vx = 0.0
        self._target_vy = 0.0
        self._tick_count = 0

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(self.TICK_MS)
        self._tick_timer.timeout.connect(self._tick)

    def set_target_velocity(self, vx: float, vy: float) -> None:
        """Called from main thread. Stores latest target; no queuing."""
        with self._lock:
            self._target_vx = vx
            self._target_vy = vy

    def _tick(self) -> None:
        """Apply latest velocity and periodically update safe limits."""
        with self._lock:
            vx, vy = self._target_vx, self._target_vy
        self._mmcore.setProperty(self._device, "VectorMoveX-VE(mm/s)", vx)
        self._mmcore.setProperty(self._device, "VectorMoveY-VE(mm/s)", vy)

        self._tick_count += 1
        if self._tick_count >= self.LIMIT_UPDATE_EVERY:
            self._tick_count = 0
            self._update_safe_limits()

    def _update_safe_limits(self) -> None:
        x, y = self._mmcore.getXYPosition(self._device)
        r = self._safe_radius_mm
        x_mm, y_mm = x / 1000.0, y / 1000.0
        self._mmcore.setProperty(self._device, "LowerLimX(mm)", x_mm - r)
        self._mmcore.setProperty(self._device, "LowerLimY(mm)", y_mm - r)
        self._mmcore.setProperty(self._device, "UpperLimX(mm)", x_mm + r)
        self._mmcore.setProperty(self._device, "UpperLimY(mm)", y_mm + r)

    def begin_move(self) -> None:
        """Apply velocity immediately, then save/set limits, then start timer."""
        # Apply velocity FIRST so the stage starts moving before slow limit I/O
        with self._lock:
            vx, vy = self._target_vx, self._target_vy
        self._mmcore.setProperty(self._device, "VectorMoveX-VE(mm/s)", vx)
        self._mmcore.setProperty(self._device, "VectorMoveY-VE(mm/s)", vy)

        # Now do the slow limit setup
        self._orig_limits = {
            p: self._mmcore.getProperty(self._device, p) for p in self._LIMIT_PROPS
        }
        self._tick_count = 0
        self._update_safe_limits()
        self._tick_timer.start()

    def end_move(self) -> None:
        """Stop stage motion, stop tick timer, restore original limits."""
        self._tick_timer.stop()
        self._mmcore.setProperty(self._device, "VectorMoveX-VE(mm/s)", 0.0)
        self._mmcore.setProperty(self._device, "VectorMoveY-VE(mm/s)", 0.0)
        if self._orig_limits is not None:
            for prop, val in self._orig_limits.items():
                self._mmcore.setProperty(self._device, prop, val)
            self._orig_limits = None


class ASIStageJoystick(QWidget):
    """Joystick that drives an ASI XY stage via VectorMove properties.

    All device I/O runs on a single dedicated worker thread.
    """

    SAFE_RADIUS_MM: float = 1.0

    # Internal signals -> worker slots (queued across threads)
    _sig_begin_move = Signal()
    _sig_end_move = Signal()

    def __init__(
        self,
        xy_device: str,
        mmcore: CMMCorePlus,
        max_mm_per_sec: float = 4.0,
        speed_exponent: float = 2.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._device = xy_device
        self._max_speed = max_mm_per_sec
        self._speed_exponent = speed_exponent
        self._moving = False

        # Worker thread for device I/O
        self._worker = _ASIDeviceWorker(xy_device, mmcore, self.SAFE_RADIUS_MM)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        self._sig_begin_move.connect(self._worker.begin_move)
        self._sig_end_move.connect(self._worker.end_move)

        self._thread.start()

        # Joystick UI
        self._joystick = JoystickWidget(self)
        self._joystick.deflectionChanged.connect(self._on_deflection)
        self._joystick.released.connect(self._on_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._joystick)

    def _shutdown_thread(self) -> None:
        if self._thread.isRunning():
            self._on_release()
            self._thread.quit()
            self._thread.wait()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._shutdown_thread()
        super().closeEvent(event)

    def deleteLater(self) -> None:
        self._shutdown_thread()
        super().deleteLater()

    # ---- signal handlers (main thread) ----

    def _on_deflection(self, dx: float, dy: float) -> None:
        mag = min(math.hypot(dx, dy), 1.0)
        if mag < 0.05:
            self._worker.set_target_velocity(0.0, 0.0)
            return

        speed = mag**self._speed_exponent * self._max_speed
        ux, uy = dx / mag, dy / mag
        # Invert Y: MM convention is +Y = stage up, joystick +dy = screen up
        self._worker.set_target_velocity(ux * speed, -uy * speed)

        if not self._moving:
            self._moving = True
            self._sig_begin_move.emit()

    def _on_release(self) -> None:
        if not self._moving:
            return
        self._moving = False
        self._worker.set_target_velocity(0.0, 0.0)
        self._sig_end_move.emit()


# ---- D-Pad ----

STEP_SIZES = [0.1, 1, 10, 100, 1000]
STEP_LABELS = ["0.1", "1", "10", "100", "1k"]

_DPAD_BUTTONS: dict[int, tuple[str, int, int]] = {
    0: ("\u2196", -1, 1),
    1: ("\u25b2", 0, 1),
    2: ("\u2197", 1, 1),
    3: ("\u25c0", -1, 0),
    4: ("\u25ce", 0, 0),  # home
    5: ("\u25b6", 1, 0),
    6: ("\u2199", -1, -1),
    7: ("\u25bc", 0, -1),
    8: ("\u2198", 1, -1),
}


class DPadWidget(QWidget):
    """D-Pad with built-in step size selector."""

    stepRequested = Signal(float, float)
    homeRequested = Signal()
    snapRequested = Signal()

    _KEY_TO_BTN: ClassVar[dict[int, int]] = {
        Qt.Key.Key_Up: 1,
        Qt.Key.Key_Down: 7,
        Qt.Key.Key_Left: 3,
        Qt.Key.Key_Right: 5,
        Qt.Key.Key_Home: 4,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # -- step size row --
        self._step_ctrl = SegmentedControl()
        for label in STEP_LABELS:
            self._step_ctrl.addItem(label)
        self._step_ctrl.setCurrentIndex(2)  # default: 10
        layout.addWidget(self._step_ctrl)

        # -- 3x3 dpad grid --
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        self._dpad_btns: dict[int, QPushButton] = {}
        for idx, (label, _dx, _dy) in _DPAD_BUTTONS.items():
            btn = QPushButton(label)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            row, col = divmod(idx, 3)
            grid.addWidget(btn, row, col)
            btn.clicked.connect(lambda checked, i=idx: self._on_dpad(i))
            self._dpad_btns[idx] = btn
        layout.addLayout(grid)

        # -- snap button --
        self._snap_btn = QPushButton("Snap on Click")
        self._snap_btn.setCheckable(True)
        self._snap_btn.clicked.connect(self.snapRequested)
        layout.addWidget(self._snap_btn)

        # -- hint --
        hint = QLabel("\u2191\u2193\u2190\u2192 arrow keys")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setEnabled(False)  # uses disabled palette for muted text
        layout.addWidget(hint)

    @property
    def step_size(self) -> float:
        return float(STEP_SIZES[self._step_ctrl.currentIndex()])

    def _on_dpad(self, idx: int) -> None:
        _, dx, dy = _DPAD_BUTTONS[idx]
        if idx == 4:
            self.homeRequested.emit()
        else:
            s = self.step_size
            self.stepRequested.emit(dx * s, dy * s)

    def trigger_button(self, idx: int) -> None:
        """Programmatically activate a d-pad button with visual feedback."""
        if idx not in _DPAD_BUTTONS:
            return
        self._on_dpad(idx)
        btn = self._dpad_btns[idx]
        btn.setDown(True)
        QTimer.singleShot(100, lambda: btn.setDown(False))

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is not None:
            btn = self._KEY_TO_BTN.get(event.key())
            if btn is not None:
                self.trigger_button(btn)
                return
        super().keyPressEvent(event)  # type: ignore[arg-type]


class StageDPad(QWidget):
    """D-Pad widget that drives an XY stage."""

    def __init__(
        self,
        xy_device: str,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore
        self._acc = QStageMoveAccumulator.for_device(xy_device, mmcore)

        self._dpad = DPadWidget(self)
        self._dpad.stepRequested.connect(self._on_step)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._dpad)

    def _on_step(self, dx: float, dy: float) -> None:
        self._acc.move_relative((dx, dy))
        if self._dpad._snap_btn.isChecked() and self._mmc is not None:
            self._acc.moveFinished.connect(
                self._snap_once, Qt.ConnectionType.SingleShotConnection
            )

    def _snap_once(self) -> None:
        if self._mmc is not None:
            self._mmc.snap()
