from __future__ import annotations

from contextlib import suppress
from itertools import chain
from typing import TYPE_CHECKING, ClassVar

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import (  # type: ignore[attr-defined]
    MouseState,
    QlementineStyle,
    SegmentedControl,
)
from pymmcore_gui._qt.QtCore import QSignalBlocker, QSize, Qt, QTimer, Signal
from pymmcore_gui._qt.QtGui import QColor, QFont, QPalette
from pymmcore_gui._qt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QContextMenuEvent, QKeyEvent, QWheelEvent

ICON_SIZE = QSize(22, 22)
BTN_SIZE = 58
Z_BTN_HEIGHT = (BTN_SIZE * 3 + 2 * 2 - 2) // 2  # match 3-row D-pad height
POLL_INTERVAL_MS = 500
MAX_WHEEL_STEP = 1.0  # µm - cap scroll-wheel Z moves

_STEP_PRESETS: list[tuple[float, str]] = [
    (0.1, "0.1"),
    (1.0, "1"),
    (10.0, "10"),
    (100.0, "100"),
    (1000.0, "1k"),
]
_DEFAULT_STEP_INDEX = 2  # 10 µm

# (row, col): (icon_key, dx_sign, dy_sign)
_DPAD_BUTTONS: dict[tuple[int, int], tuple[str, int, int]] = {
    (0, 0): ("mdi:arrow-top-left", -1, -1),
    (0, 1): ("mdi:arrow-up", 0, -1),
    (0, 2): ("mdi:arrow-top-right", 1, -1),
    (1, 0): ("mdi:arrow-left", -1, 0),
    (1, 2): ("mdi:arrow-right", 1, 0),
    (2, 0): ("mdi:arrow-bottom-left", -1, 1),
    (2, 1): ("mdi:arrow-down", 0, 1),
    (2, 2): ("mdi:arrow-bottom-right", 1, 1),
}


def _qlementine_style() -> QlementineStyle | None:
    style = QApplication.instance().style()  # type: ignore [union-attr]
    return style if isinstance(style, QlementineStyle) else None


def _set_label_color(label: QLabel, color: QColor) -> None:
    pal = label.palette()
    pal.setColor(QPalette.ColorRole.WindowText, color)
    label.setPalette(pal)


def _mono_font(size: int = 11) -> QFont:
    font = QFont("Menlo, Consolas, monospace", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


# ── Position bar ─────────────────────────────────────────────────────


class _PositionSpinBox(QDoubleSpinBox):
    """Always-visible position display that doubles as an absolute-move input.

    Normally displays the current position. Click to edit, press Enter to
    move the stage to the entered value.
    """

    goToRequested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(-1e7, 1e7)
        self.setDecimals(2)
        self.setSuffix(" µm")
        self.setFont(_mono_font(12))
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setMinimumHeight(20)
        self.setKeyboardTracking(False)
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._last_core_value = 0.0

        self.editingFinished.connect(self._on_editing_finished)

    def set_core_value(self, v: float) -> None:
        """Update from core - only touches the display if not being edited."""
        self._last_core_value = v
        if not self.hasFocus():
            self.setValue(v)

    def focusInEvent(self, event: object) -> None:
        self.setReadOnly(False)
        self.selectAll()
        super().focusInEvent(event)  # type: ignore [arg-type]

    def focusOutEvent(self, event: object) -> None:
        self.setReadOnly(True)
        self.setValue(self._last_core_value)
        super().focusOutEvent(event)  # type: ignore [arg-type]

    def _on_editing_finished(self) -> None:
        if self.isReadOnly():
            return
        val = self.value()
        self.setReadOnly(True)
        self.clearFocus()
        self.goToRequested.emit(val)


class _PositionBar(QWidget):
    """X/Y/Z position readout - click a value to enter an absolute position."""

    goToRequested = Signal(str, float)  # (axis, value)

    AXIS_COLORS: ClassVar[dict[str, QColor]] = {
        "X": QColor("#e06060"),
        "Y": QColor("#60c060"),
        "Z": QColor("#6090e0"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self._labels: dict[str, QLabel] = {}
        self._spins: dict[str, _PositionSpinBox] = {}

        for axis in ("X", "Y", "Z"):
            lbl = QLabel(axis, self)
            lbl.setFont(_mono_font())
            _set_label_color(lbl, self.AXIS_COLORS[axis])
            self._labels[axis] = lbl

            spin = _PositionSpinBox(self)
            spin.goToRequested.connect(lambda v, a=axis: self.goToRequested.emit(a, v))
            self._spins[axis] = spin

            layout.addWidget(lbl)
            layout.addWidget(spin, 1)

    def set_position(self, axis: str, value: float) -> None:
        if axis in self._spins:
            self._spins[axis].set_core_value(value)

    def set_axis_visible(self, axis: str, visible: bool) -> None:
        if axis in self._labels:
            self._labels[axis].setVisible(visible)
        if axis in self._spins:
            self._spins[axis].setVisible(visible)


# ── D-pad and Z buttons ─────────────────────────────────────────────


class _DPadButton(QPushButton):
    """A single directional button in the XY pad."""

    def __init__(
        self, icon_key: str, dx: int, dy: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.dx = dx
        self.dy = dy
        self.setIcon(QIconifyIcon(icon_key, color="#aaa"))
        self.setIconSize(ICON_SIZE)
        self.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.setAutoRepeat(True)
        self.setAutoRepeatDelay(400)
        self.setAutoRepeatInterval(80)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class _XYPad(QWidget):
    """3x3 directional button grid for XY movement."""

    moveRequested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._buttons: dict[tuple[int, int], _DPadButton] = {}
        for (row, col), (icon_key, dx, dy) in _DPAD_BUTTONS.items():
            btn = _DPadButton(icon_key, dx, dy, self)
            btn.clicked.connect(
                lambda _=False, x=dx, y=dy: self.moveRequested.emit(x, y)
            )
            layout.addWidget(btn, row, col)
            self._buttons[(dx, dy)] = btn

        # Center crosshair (decorative)
        center = QLabel(self)
        center.setPixmap(QIconifyIcon("mdi:crosshairs", color="#555").pixmap(ICON_SIZE))
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.setFixedSize(BTN_SIZE, BTN_SIZE)
        layout.addWidget(center, 1, 1)

    def flash_button(self, dx: int, dy: int) -> None:
        """Briefly show the pressed state on the matching button."""
        if btn := self._buttons.get((dx, dy)):
            btn.setDown(True)
            QTimer.singleShot(100, lambda: btn.setDown(False))


class _ZButtons(QWidget):
    """Z-axis up/down buttons."""

    moveRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._up = self._make_btn("mdi:chevron-up")
        self._down = self._make_btn("mdi:chevron-down")

        self._up.clicked.connect(lambda: self.moveRequested.emit(1))
        self._down.clicked.connect(lambda: self.moveRequested.emit(-1))

        layout.addWidget(self._up)
        layout.addWidget(self._down)

    def flash_button(self, direction: int) -> None:
        btn = self._up if direction > 0 else self._down
        btn.setDown(True)
        QTimer.singleShot(100, lambda: btn.setDown(False))

    def _make_btn(self, icon_key: str) -> QPushButton:
        btn = QPushButton(self)
        btn.setIcon(QIconifyIcon(icon_key, color="#aaa"))
        btn.setIconSize(QSize(26, 26))
        btn.setFixedSize(BTN_SIZE, Z_BTN_HEIGHT)
        btn.setAutoRepeat(True)
        btn.setAutoRepeatDelay(400)
        btn.setAutoRepeatInterval(80)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn


# ── Step size (SegmentedControl) ─────────────────────────────────────


class _StepSizeBar(QWidget):
    """Qlementine SegmentedControl for step-size selection."""

    stepChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel("STEP", self)
        if qs := _qlementine_style():
            _set_label_color(
                lbl,
                qs.labelCaptionForegroundColor(MouseState.Normal),
            )
        font = lbl.font()
        font.setPointSize(font.pointSize() - 1)
        lbl.setFont(font)
        layout.addWidget(lbl)

        self._seg = SegmentedControl()
        self._seg.setMaximumWidth(280)
        self._seg.setMaximumHeight(34)
        for value, text in _STEP_PRESETS:
            self._seg.addItem(text, itemData=value)
        self._seg.setCurrentIndex(_DEFAULT_STEP_INDEX)
        self._seg.currentIndexChanged.connect(self._on_index_changed)  # pyright: ignore[reportAttributeAccessIssue]
        layout.addWidget(self._seg)

        unit = QLabel("µm", self)
        if qs:
            _set_label_color(
                unit,
                qs.labelCaptionForegroundColor(MouseState.Normal),
            )
        layout.addWidget(unit)

    def _on_index_changed(self) -> None:
        data = self._seg.currentData()
        if data is not None:
            self.stepChanged.emit(float(data))

    def current_step(self) -> float:
        data = self._seg.currentData()
        if data is not None:
            return float(data)
        return _STEP_PRESETS[_DEFAULT_STEP_INDEX][0]


# ── Main widget ──────────────────────────────────────────────────────


class StagesControlWidget(QWidget):
    """Unified stage control for XY and Z stages."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._invert_x = False
        self._invert_y = False
        self._invert_z = False
        self._xy_accum: QStageMoveAccumulator | None = None
        self._z_accum: QStageMoveAccumulator | None = None

        self._build_ui()
        self._connect_signals()
        self._on_cfg_loaded()
        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._poll_timer.stop()
        self._disconnect_accumulators()
        evts = self._mmc.events
        evts.systemConfigurationLoaded.disconnect(self._on_cfg_loaded)
        evts.XYStagePositionChanged.disconnect(self._on_xy_pos_changed)
        evts.stagePositionChanged.disconnect(self._on_z_pos_changed)

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Header: device combos + poll
        header = QHBoxLayout()
        header.setSpacing(4)

        self._xy_combo = QComboBox(self)
        self._xy_combo.setToolTip("XY stage device")
        self._xy_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._z_combo = QComboBox(self)
        self._z_combo.setToolTip("Z stage device")
        self._z_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        header.addWidget(self._xy_combo)
        header.addWidget(self._z_combo)

        self._snap_cb = QCheckBox("Snap on Click", self)
        self._snap_cb.setToolTip("Snap image after each move")
        header.addWidget(self._snap_cb)

        header.addStretch()

        self._poll_cb = QCheckBox("Poll", self)
        self._poll_cb.setToolTip("Poll stage position periodically")
        header.addWidget(self._poll_cb)

        root.addLayout(header)

        # Position bar (click a value to go to absolute position)
        self._pos_bar = _PositionBar(self)
        root.addWidget(self._pos_bar)

        # Step size bar (above buttons)
        self._step_bar = _StepSizeBar(self)
        root.addWidget(self._step_bar)

        # Movement controls: XY pad + Z buttons side by side
        move_row = QHBoxLayout()
        move_row.setSpacing(8)
        self._xy_pad = _XYPad(self)
        self._z_btns = _ZButtons(self)
        move_row.addStretch()
        move_row.addWidget(self._xy_pad)
        move_row.addWidget(self._z_btns)
        move_row.addStretch()
        root.addLayout(move_row)

        # Keyboard hint
        self._hint = QLabel(
            "\u2190 \u2192 \u2191 \u2193 XY \u00b7 PgUp\u00b7PgDn / scroll Z",
            self,
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if qs := _qlementine_style():
            _set_label_color(
                self._hint,
                qs.labelCaptionForegroundColor(MouseState.Normal),
            )
        font = self._hint.font()
        font.setPointSize(font.pointSize() - 1)
        self._hint.setFont(font)
        root.addWidget(self._hint)

        # STOP button - full width, prominent
        self._stop_btn = QPushButton(
            QIconifyIcon("glyphs:stop-sign-bold", color="white"), "", self
        )
        self._stop_btn.setIconSize(QSize(32, 32))
        self._stop_btn.setFixedWidth(234)
        self._stop_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._stop_btn.setToolTip("Stop all stage movement (Esc)")
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #a8222a; color: white; font-weight: bold;"
            " font-size: 13px; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background: #c0333b; }"
            "QPushButton:pressed { background: #8a1a22; }"
        )
        root.addWidget(self._stop_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Poll timer
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._update_positions)

    # ── Signal wiring ────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)
        self._mmc.events.XYStagePositionChanged.connect(self._on_xy_pos_changed)
        self._mmc.events.stagePositionChanged.connect(self._on_z_pos_changed)

        self._xy_combo.currentTextChanged.connect(self._on_xy_device_changed)
        self._z_combo.currentTextChanged.connect(self._on_z_device_changed)
        self._poll_cb.toggled.connect(self._on_poll_toggled)
        self._stop_btn.clicked.connect(self._stop_all)

        self._xy_pad.moveRequested.connect(self._on_xy_move)
        self._z_btns.moveRequested.connect(self._on_z_move)
        self._pos_bar.goToRequested.connect(self._on_go_to)

    # ── Configuration loaded ─────────────────────────────────────────

    def _on_cfg_loaded(self) -> None:
        xy_devs = list(self._mmc.getLoadedDevicesOfType(DeviceType.XYStage))
        z_devs = list(self._mmc.getLoadedDevicesOfType(DeviceType.Stage))

        with QSignalBlocker(self._xy_combo):
            self._xy_combo.clear()
            self._xy_combo.addItems(xy_devs)
            default_xy = self._mmc.getXYStageDevice()
            if default_xy in xy_devs:
                self._xy_combo.setCurrentText(default_xy)

        with QSignalBlocker(self._z_combo):
            self._z_combo.clear()
            self._z_combo.addItems(z_devs)
            default_z = self._mmc.getFocusDevice()
            if default_z in z_devs:
                self._z_combo.setCurrentText(default_z)

        has_xy = len(xy_devs) > 0
        has_z = len(z_devs) > 0
        self._xy_combo.setVisible(len(xy_devs) > 1)
        self._z_combo.setVisible(len(z_devs) > 1)
        self._xy_pad.setVisible(has_xy)
        self._z_btns.setVisible(has_z)
        self._pos_bar.set_axis_visible("X", has_xy)
        self._pos_bar.set_axis_visible("Y", has_xy)
        self._pos_bar.set_axis_visible("Z", has_z)

        self._setup_accumulators()
        self._update_positions()

    def _on_xy_device_changed(self, device: str) -> None:
        if device:
            self._setup_accumulators()
            self._update_positions()

    def _on_z_device_changed(self, device: str) -> None:
        if device:
            self._setup_accumulators()
            self._update_positions()

    def _setup_accumulators(self) -> None:
        self._disconnect_accumulators()

        xy_dev = self._current_xy_device()
        z_dev = self._current_z_device()

        if xy_dev:
            with suppress(Exception):
                accum = QStageMoveAccumulator.for_device(xy_dev, self._mmc)
                accum.moveFinished.connect(self._update_positions)
                self._xy_accum = accum

        if z_dev:
            with suppress(Exception):
                accum = QStageMoveAccumulator.for_device(z_dev, self._mmc)
                accum.moveFinished.connect(self._update_positions)
                self._z_accum = accum

    def _disconnect_accumulators(self) -> None:
        if self._xy_accum is not None:
            with suppress(TypeError, RuntimeError):
                self._xy_accum.moveFinished.disconnect(self._update_positions)
            self._xy_accum = None
        if self._z_accum is not None:
            with suppress(TypeError, RuntimeError):
                self._z_accum.moveFinished.disconnect(self._update_positions)
            self._z_accum = None

    # ── Device helpers ───────────────────────────────────────────────

    def _current_xy_device(self) -> str:
        return self._xy_combo.currentText()

    def _current_z_device(self) -> str:
        return self._z_combo.currentText()

    # ── Movement ─────────────────────────────────────────────────────

    def _on_xy_move(self, dx_sign: int, dy_sign: int) -> None:
        if not self._xy_accum:
            return
        step = self._step_bar.current_step()
        dx = step * dx_sign * (-1 if self._invert_x else 1)
        dy = step * dy_sign * (-1 if self._invert_y else 1)
        self._xy_accum.snap_on_finish = self._snap_cb.isChecked()
        self._xy_accum.move_relative((dx, dy))

    def _on_z_move(self, direction: int, max_step: float = 0) -> None:
        if not self._z_accum:
            return
        step = self._step_bar.current_step()
        if max_step > 0:
            step = min(step, max_step)
        dz = step * direction * (-1 if self._invert_z else 1)
        self._z_accum.snap_on_finish = self._snap_cb.isChecked()
        self._z_accum.move_relative(dz)

    def _on_go_to(self, axis: str, value: float) -> None:
        if axis in ("X", "Y") and self._xy_accum:
            xy_dev = self._current_xy_device()
            try:
                cx, cy = self._mmc.getXYPosition(xy_dev)
            except Exception:
                return
            if axis == "X":
                self._xy_accum.move_absolute((value, cy))
            else:
                self._xy_accum.move_absolute((cx, value))
        elif axis == "Z" and self._z_accum:
            self._z_accum.move_absolute(value)

    def _stop_all(self) -> None:
        for dev in chain(
            self._mmc.getLoadedDevicesOfType(DeviceType.XYStage),
            self._mmc.getLoadedDevicesOfType(DeviceType.Stage),
        ):
            try:
                self._mmc.stop(dev)
            except Exception:
                pass

    # ── Position updates ─────────────────────────────────────────────

    def _update_positions(self) -> None:
        xy_dev = self._current_xy_device()
        if xy_dev:
            try:
                x, y = self._mmc.getXYPosition(xy_dev)
                self._pos_bar.set_position("X", x)
                self._pos_bar.set_position("Y", y)
            except Exception:
                pass

        z_dev = self._current_z_device()
        if z_dev:
            try:
                z = self._mmc.getPosition(z_dev)
                self._pos_bar.set_position("Z", z)
            except Exception:
                pass

    def _on_xy_pos_changed(self, device: str, x: float, y: float) -> None:
        if device == self._current_xy_device():
            self._pos_bar.set_position("X", x)
            self._pos_bar.set_position("Y", y)

    def _on_z_pos_changed(self, device: str, z: float) -> None:
        if device == self._current_z_device():
            self._pos_bar.set_position("Z", z)

    # ── Polling ──────────────────────────────────────────────────────

    def _on_poll_toggled(self, checked: bool) -> None:
        if checked:
            self._poll_timer.start()
        else:
            self._poll_timer.stop()

    # ── Keyboard & mouse ─────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._xy_pad.flash_button(-1, 0)
            self._on_xy_move(-1, 0)
        elif key == Qt.Key.Key_Right:
            self._xy_pad.flash_button(1, 0)
            self._on_xy_move(1, 0)
        elif key == Qt.Key.Key_Up:
            self._xy_pad.flash_button(0, -1)
            self._on_xy_move(0, -1)
        elif key == Qt.Key.Key_Down:
            self._xy_pad.flash_button(0, 1)
            self._on_xy_move(0, 1)
        elif key == Qt.Key.Key_PageUp:
            self._z_btns.flash_button(1)
            self._on_z_move(1)
        elif key == Qt.Key.Key_PageDown:
            self._z_btns.flash_button(-1)
            self._on_z_move(-1)
        elif key == Qt.Key.Key_Escape:
            self._stop_all()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self._on_z_move(1, max_step=MAX_WHEEL_STEP)
        elif delta < 0:
            self._on_z_move(-1, max_step=MAX_WHEEL_STEP)
        event.accept()

    # ── Context menu ─────────────────────────────────────────────────

    def contextMenuEvent(self, event: QContextMenuEvent | None) -> None:
        if event is None:
            return
        menu = QMenu(self)

        invert_x = menu.addAction("Invert X")
        if invert_x:
            invert_x.setCheckable(True)
            invert_x.setChecked(self._invert_x)
            invert_x.toggled.connect(self._set_invert_x)

        invert_y = menu.addAction("Invert Y")
        if invert_y:
            invert_y.setCheckable(True)
            invert_y.setChecked(self._invert_y)
            invert_y.toggled.connect(self._set_invert_y)

        invert_z = menu.addAction("Invert Z")
        if invert_z:
            invert_z.setCheckable(True)
            invert_z.setChecked(self._invert_z)
            invert_z.toggled.connect(self._set_invert_z)

        menu.exec(event.globalPos())

    def _set_invert_x(self, v: bool) -> None:
        self._invert_x = v

    def _set_invert_y(self, v: bool) -> None:
        self._invert_y = v

    def _set_invert_z(self, v: bool) -> None:
        self._invert_z = v
