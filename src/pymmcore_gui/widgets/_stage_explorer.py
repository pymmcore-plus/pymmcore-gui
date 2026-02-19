from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymmcore_widgets import StageExplorer
from superqt import QIconifyIcon

from pymmcore_gui._qt.QtCore import Signal
from pymmcore_gui._qt.QtGui import QAction
from pymmcore_gui._qt.QtWidgets import QMessageBox

if TYPE_CHECKING:
    import useq


class _StageExplorer(StageExplorer):
    sendToMDARequested = Signal(list, bool)  # positions, clear

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        tb = self.toolBar()
        self._send_to_mda_action = QAction(
            QIconifyIcon("mdi:send"), "Send to MDA", self
        )
        self._send_to_mda_action.triggered.connect(self._on_send_to_mda)
        # Insert right after scan_action (before the spacer/label at the end)
        actions = tb.actions()
        scan_idx = actions.index(tb.scan_action)
        if scan_idx + 1 < len(actions):
            tb.insertAction(actions[scan_idx + 1], self._send_to_mda_action)
        else:
            tb.addAction(self._send_to_mda_action)

    def _on_send_to_mda(self) -> None:
        z_pos = self._mmc.getZPosition()
        positions: list[useq.Position] = []
        roi_model = self.roi_manager.roi_model
        for row in range(roi_model.rowCount()):
            roi = roi_model.index(row).internalPointer()
            if pos := roi.create_useq_position(*self._fov_w_h(), z_pos=z_pos):
                positions.append(pos)
        if not positions:
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Send to MDA")
        msg.setText("Replace existing stage positions or add to them?")
        replace_btn = msg.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Add", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is cancel_btn or clicked is None:
            return

        self.sendToMDARequested.emit(positions, clicked is replace_btn)
