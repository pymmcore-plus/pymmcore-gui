from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from pymmcore_widgets import StageExplorer
from pymmcore_widgets.control._rois.roi_manager import GRAY
from superqt import QIconifyIcon

from pymmcore_gui._qt.QtCore import Signal
from pymmcore_gui._qt.QtGui import QActionGroup
from pymmcore_gui._qt.QtWidgets import QMenu, QMessageBox, QToolButton, QWidget

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
        send_menu = QMenu(self)
        self._send_mode_group = QActionGroup(send_menu)
        self._send_mode_group.setExclusive(True)
        for label in ("ROIs with Grid Sub-Sequence", "List of Single Positions"):
            act = self._send_mode_group.addAction(label)
            act.setCheckable(True)
        self._send_mode_group.actions()[1].setChecked(True)
        send_menu.addActions(self._send_mode_group.actions())
        self._send_to_mda_action.triggered.connect(self._on_send_to_mda)
        btn = self._toolbar.widgetForAction(
            self._send_to_mda_action  # pyright: ignore[reportArgumentType]
        )
        if isinstance(btn, QToolButton):
            btn.setMenu(send_menu)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    def _on_scan_action(self) -> None:
        """Override to pass output='memory' so the ndv viewer gets data."""
        if not (active_rois := self.roi_manager.selected_rois()):
            return
        active_roi = active_rois[0]

        overlap, mode = self._toolbar.scan_menu.value()
        if plan := active_roi.create_grid_plan(*self._fov_w_h(), overlap, mode):
            seq = useq.MDASequence(grid_plan=plan)
            if not self._mmc.mda.is_running():
                self._our_mda_running = True
                self._mmc.run_mda(seq, output="memory")

    def _on_send_to_mda(self) -> None:
        checked = self._send_mode_group.checkedAction()
        flatten = checked is not None and checked.text() == "List of Single Positions"
        z_pos = self._mmc.getZPosition()
        positions: list[useq.AbsolutePosition] = []
        roi_model = self.roi_manager.roi_model
        for row in range(roi_model.rowCount()):
            roi = roi_model.index(row).internalPointer()
            if pos := roi.create_useq_position(*self._fov_w_h(), z_pos=z_pos):
                positions.append(pos)
        if not positions:
            return

        if flatten:
            positions = self._flatten_to_single_positions(positions)

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

    def _flatten_to_single_positions(
        self, positions: list[useq.AbsolutePosition]
    ) -> list[useq.AbsolutePosition]:
        flat: list[useq.AbsolutePosition] = []
        for pos in positions:
            if pos.sequence and pos.sequence.grid_plan:
                base_name = pos.name or "pos"
                for idx, grid_pos in enumerate(pos.sequence.grid_plan):
                    flat.append(
                        useq.AbsolutePosition(
                            x=grid_pos.x,
                            y=grid_pos.y,
                            z=pos.z,
                            name=f"{base_name}_{idx:04d}",
                        )
                    )
            else:
                flat.append(pos)
        return flat
