from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import StageExplorer
from pymmcore_widgets.control._rois.roi_manager import GRAY
from superqt import QIconifyIcon

from pymmcore_gui._qt.QtCore import Signal
from pymmcore_gui._qt.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus


class _StageExplorer(StageExplorer):
    """StageExplorer subclass with 'Send to MDA' support."""

    sendToMDARequested = Signal(list, bool)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent, mmcore=mmcore)

        self._send_to_mda_action = self._toolbar.addAction(
            QIconifyIcon("mdi:send", color=GRAY),
            "Send to MDA",
        )
        # move the action right after scan_action
        actions = self._toolbar.actions()
        idx = actions.index(
            self._toolbar.scan_action  # pyright: ignore[reportArgumentType]
        )
        self._toolbar.insertAction(
            actions[idx + 1],
            self._send_to_mda_action,  # pyright: ignore[reportArgumentType]
        )
        self._send_to_mda_action.triggered.connect(self._on_send_to_mda)

    def _on_send_to_mda(self) -> None:
        z_pos = self._mmc.getZPosition()
        positions: list = []
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
