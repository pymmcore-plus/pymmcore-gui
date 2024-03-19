from __future__ import annotations

from typing import Any, cast

from fonticon_mdi6 import MDI6
from qtpy import QtCore
from qtpy.QtWidgets import (
    QBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QWidget,
    QWidgetAction,
)
from superqt import QLabeledSlider
from superqt.fonticon import icon

FIXED = QSizePolicy.Policy.Fixed
ICON_SIZE = (24, 24)


class _AxisSlider(QLabeledSlider):
    def __init__(
        self,
        axis: str = "",
        orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Horizontal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self.axis = axis
        name_label = QLabel(axis.lower())
        name_label.setSizePolicy(FIXED, FIXED)
        name_label.setFixedWidth(20)

        self._play_btn = QPushButton(icon(MDI6.play), "", self)
        self._play_btn.setMaximumWidth(self._play_btn.sizeHint().height())
        self._play_btn.setCheckable(True)
        self._play_btn.toggled.connect(self._on_play_toggled)
        # Enable the custom context menu for the play button
        self._play_btn.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._play_btn.customContextMenuRequested.connect(self._showContextMenu)

        self._timer_id: int | None = None

        self._interval: int = 10
        self._interval_spin = QSpinBox()
        self._interval_spin.setSuffix(" fps")
        self._interval_spin.setRange(1, 1000)
        self._interval_spin.setValue(self._interval)
        self._interval_spin.valueChanged.connect(
            lambda val: setattr(self, "_interval", val)
        )

        self._length_label = QLabel()
        self.rangeChanged.connect(self._on_range_changed)

        layout = cast(QBoxLayout, self.layout())
        layout.setContentsMargins(10, 0, 0, 0)
        layout.insertWidget(0, self._play_btn, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        layout.insertWidget(0, name_label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._length_label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.installEventFilter(self)
        self.setPageStep(1)
        self.last_val = 0

    def _on_play_toggled(self, state: bool) -> None:
        if state:
            self._play_btn.setIcon(icon(MDI6.pause))
            self._timer_id = self.startTimer(int(1000 / self._interval))  # ms
        elif self._timer_id is not None:
            self._play_btn.setIcon(icon(MDI6.play))
            self.killTimer(self._timer_id)
            self._timer_id = None

    def _showContextMenu(self, position: QtCore.QPoint) -> None:
        """Context menu to change the interval of the play button."""
        # toggle off the play button
        self._play_btn.setChecked(False)
        # create context menu
        context_menu = QMenu(self)
        # create a QWidgetAction and set its default widget to the QSpinBox
        spin_box_action = QWidgetAction(self)
        spin_box_action.setDefaultWidget(self._interval_spin)
        # add the QWidgetAction to the menu
        context_menu.addAction(spin_box_action)
        # show the context menu
        context_menu.exec_(self._play_btn.mapToGlobal(position))

    def timerEvent(self, e: QtCore.QTimerEvent) -> None:
        """Move the slider to the next value when play is toggled."""
        self.setValue(
            self.minimum()
            + (self.value() - self.minimum() + 1)
            % (self.maximum() - self.minimum() + 1)
        )

    def _on_range_changed(self, min_: int, max_: int) -> None:
        self._length_label.setText(f"/ {max_}")

    def eventFilter(self, source: QtCore.QObject, event: QtCore.QEvent) -> Any:
        if event.type() == QtCore.QEvent.Type.Paint and self.underMouse():
            if self.value() != self.last_val:
                self.sliderMoved.emit(self.value())
        self.last_val = self.value()
        return super().eventFilter(source, event)
