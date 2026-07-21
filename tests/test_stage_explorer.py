from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import useq
from pymmcore_widgets.control._rois.roi_model import RectangleROI

from pymmcore_gui.actions.widget_actions import _setup_stage_mda_connections
from pymmcore_gui.widgets._stage_explorer import _StageExplorer

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# ---------------------------------------------------------------------------
# _StageExplorer - Send to MDA toolbar action
# ---------------------------------------------------------------------------


def test_send_to_mda_action_in_toolbar(qtbot: QtBot) -> None:
    """The Send to MDA action is present in the toolbar."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    assert any(a.text() == "Send to MDA" for a in explorer._toolbar.actions())


def test_send_to_mda_action_position_after_scan(qtbot: QtBot) -> None:
    """The Send to MDA action is inserted right after the scan action."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    actions = explorer._toolbar.actions()
    scan_idx = actions.index(explorer._toolbar.scan_action)  # pyright: ignore
    send_idx = actions.index(explorer._send_to_mda_action)  # pyright: ignore
    assert send_idx == scan_idx + 1


# ---------------------------------------------------------------------------
# _StageExplorer - send mode group
# ---------------------------------------------------------------------------


def test_send_mode_default_is_grid_subsequence(qtbot: QtBot) -> None:
    """Default send mode is 'ROIs with Grid Sub-Sequence'."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    checked = explorer._send_mode_group.checkedAction()
    assert checked is not None
    assert checked.text() == "ROIs with Grid Sub-Sequence"


def test_send_mode_switch_does_not_trigger_dialog(qtbot: QtBot) -> None:
    """Switching send mode does not open the Replace/Add/Cancel dialog."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        explorer._send_mode_group.actions()[1].setChecked(True)
        mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# _StageExplorer - _on_send_to_mda
# ---------------------------------------------------------------------------


def test_send_to_mda_no_rois_no_dialog_no_signal(qtbot: QtBot) -> None:
    """With no ROIs, _on_send_to_mda returns early without showing a dialog."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    emitted: list = []
    explorer.sendToMDARequested.connect(lambda pos, clear: emitted.append((pos, clear)))

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        explorer._on_send_to_mda()
        mock_cls.assert_not_called()

    assert not emitted


def _make_msg_mock(clicked_index: int) -> tuple[MagicMock, list[MagicMock]]:
    """Return a (mock_msg, [replace_btn, add_btn, cancel_btn]) for patching."""
    btns = [MagicMock(name=n) for n in ("replace_btn", "add_btn", "cancel_btn")]
    mock_msg = MagicMock()
    mock_msg.addButton.side_effect = btns
    mock_msg.clickedButton.return_value = btns[clicked_index]
    return mock_msg, btns


def test_send_to_mda_replace(qtbot: QtBot) -> None:
    """Clicking Replace emits sendToMDARequested with clear=True."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    explorer.roi_manager.add_roi(RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0)))
    mock_msg, _ = _make_msg_mock(clicked_index=0)  # replace_btn

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        mock_cls.return_value = mock_msg
        with qtbot.waitSignal(explorer.sendToMDARequested) as blocker:
            explorer._on_send_to_mda()

    assert blocker.args is not None
    positions, clear = blocker.args
    assert clear is True
    assert len(positions) == 1
    assert isinstance(positions[0], useq.AbsolutePosition)


def test_send_to_mda_add(qtbot: QtBot) -> None:
    """Clicking Add emits sendToMDARequested with clear=False."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    explorer.roi_manager.add_roi(RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0)))
    mock_msg, _ = _make_msg_mock(clicked_index=1)  # add_btn

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        mock_cls.return_value = mock_msg
        with qtbot.waitSignal(explorer.sendToMDARequested) as blocker:
            explorer._on_send_to_mda()

    assert blocker.args is not None
    positions, clear = blocker.args
    assert clear is False
    assert len(positions) == 1


def test_send_to_mda_cancel(qtbot: QtBot) -> None:
    """Clicking Cancel does not emit sendToMDARequested."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    explorer.roi_manager.add_roi(RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0)))
    mock_msg, _ = _make_msg_mock(clicked_index=2)  # cancel_btn

    emitted: list = []
    explorer.sendToMDARequested.connect(lambda pos, clear: emitted.append((pos, clear)))

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        mock_cls.return_value = mock_msg
        explorer._on_send_to_mda()

    assert not emitted


def test_send_to_mda_multiple_rois(qtbot: QtBot) -> None:
    """All ROIs are collected and emitted as positions."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    for coords in [((0, 0), (10, 10)), ((20, 20), (30, 30)), ((40, 40), (50, 50))]:
        explorer.roi_manager.add_roi(RectangleROI(*coords, fov_size=(5.0, 5.0)))

    mock_msg, _ = _make_msg_mock(clicked_index=0)  # replace_btn

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        mock_cls.return_value = mock_msg
        with qtbot.waitSignal(explorer.sendToMDARequested) as blocker:
            explorer._on_send_to_mda()

    assert blocker.args is not None
    positions, _ = blocker.args
    assert len(positions) == 3


# ---------------------------------------------------------------------------
# _StageExplorer - _flatten_to_single_positions
# ---------------------------------------------------------------------------


def test_flatten_roi_with_grid_expands_to_single_positions(qtbot: QtBot) -> None:
    """A position with a grid sub-sequence expands into individual positions."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    # A 10x10 ROI with a 3x3 fov will produce a multi-position grid
    roi = RectangleROI((0, 0), (10, 10), fov_size=(3.0, 3.0))
    pos = roi.create_useq_position(fov_w=3.0, fov_h=3.0)
    assert pos.sequence and pos.sequence.grid_plan  # sanity check

    flat = explorer._flatten_to_single_positions([pos])

    assert len(flat) > 1
    for p in flat:
        assert p.sequence is None or not p.sequence.grid_plan
        assert isinstance(p, useq.AbsolutePosition)


def test_flatten_roi_without_grid_is_unchanged(qtbot: QtBot) -> None:
    """A position without a grid sub-sequence passes through unchanged."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    pos = useq.AbsolutePosition(x=1.0, y=2.0, z=3.0, name="solo")
    flat = explorer._flatten_to_single_positions([pos])

    assert flat == [pos]


def test_flatten_preserves_z_from_parent_position(qtbot: QtBot) -> None:
    """Flattened positions inherit the z value from the parent position."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    roi = RectangleROI((0, 0), (10, 10), fov_size=(3.0, 3.0))
    pos = roi.create_useq_position(fov_w=3.0, fov_h=3.0, z_pos=42.0)

    flat = explorer._flatten_to_single_positions([pos])

    assert all(p.z == 42.0 for p in flat)


def test_send_to_mda_flatten_mode(qtbot: QtBot) -> None:
    """With 'List of Single Positions' mode, grid ROIs are expanded before emit."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    # Switch to flatten mode
    explorer._send_mode_group.actions()[1].setChecked(True)

    # A large ROI relative to FOV produces a multi-cell grid
    explorer.roi_manager.add_roi(RectangleROI((0, 0), (20, 20), fov_size=(3.0, 3.0)))
    mock_msg, _ = _make_msg_mock(clicked_index=0)  # replace_btn

    with patch("pymmcore_gui.widgets._stage_explorer.QMessageBox") as mock_cls:
        mock_cls.return_value = mock_msg
        with qtbot.waitSignal(explorer.sendToMDARequested) as blocker:
            explorer._on_send_to_mda()

    assert blocker.args is not None
    positions, _ = blocker.args
    # Flattened: no position should carry a grid sub-sequence
    for p in positions:
        assert not (p.sequence and p.sequence.grid_plan)


# ---------------------------------------------------------------------------
# _on_scan_action - passes output="memory"
# ---------------------------------------------------------------------------


def test_on_scan_action_uses_memory_output(qtbot: QtBot) -> None:
    """_on_scan_action runs the MDA with output='memory'."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    roi = RectangleROI((0, 0), (10, 10), fov_size=(5.0, 5.0))
    explorer.roi_manager.add_roi(roi)
    explorer.roi_manager.select_roi(roi)

    # _fov_w_h uses image dimensions * pixel size; patch to a size smaller than the ROI
    # so that create_grid_plan produces a valid plan
    with (
        patch.object(explorer, "_fov_w_h", return_value=(3.0, 3.0)),
        patch.object(explorer._mmc, "run_mda") as mock_run_mda,
    ):
        explorer._on_scan_action()

    mock_run_mda.assert_called_once()
    _, kwargs = mock_run_mda.call_args
    assert kwargs.get("output") == "memory"


# ---------------------------------------------------------------------------
# _setup_stage_mda_connections
# ---------------------------------------------------------------------------


def test_setup_connections_replace_sets_positions(qtbot: QtBot) -> None:
    """sendToMDARequested with clear=True replaces all stage positions."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    mock_mda = MagicMock()
    _setup_stage_mda_connections(explorer, mock_mda)

    new_positions = [useq.AbsolutePosition(x=1.0, y=2.0)]
    explorer.sendToMDARequested.emit(new_positions, True)

    mock_mda.stage_positions.setValue.assert_called_once_with(new_positions)


def test_setup_connections_add_appends_positions(qtbot: QtBot) -> None:
    """sendToMDARequested with clear=False appends to existing positions."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    existing = [useq.AbsolutePosition(x=0.0, y=0.0)]
    mock_mda = MagicMock()
    mock_mda.stage_positions.value.return_value = existing
    _setup_stage_mda_connections(explorer, mock_mda)

    new_positions = [useq.AbsolutePosition(x=5.0, y=5.0)]
    explorer.sendToMDARequested.emit(new_positions, False)

    mock_mda.stage_positions.setValue.assert_called_once_with(existing + new_positions)


def test_setup_connections_add_with_no_existing_positions(qtbot: QtBot) -> None:
    """Add mode handles an empty/None existing position list gracefully."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    mock_mda = MagicMock()
    mock_mda.stage_positions.value.return_value = None
    _setup_stage_mda_connections(explorer, mock_mda)

    new_positions = [useq.AbsolutePosition(x=1.0, y=2.0)]
    explorer.sendToMDARequested.emit(new_positions, False)

    mock_mda.stage_positions.setValue.assert_called_once_with(new_positions)


def test_setup_connections_noop_when_either_arg_is_none(qtbot: QtBot) -> None:
    """_setup_stage_mda_connections is a no-op when either argument is None."""
    explorer = _StageExplorer()
    qtbot.addWidget(explorer)

    mock_mda = MagicMock()

    _setup_stage_mda_connections(None, mock_mda)
    _setup_stage_mda_connections(explorer, None)

    # No connections made — emitting should not reach the mock
    explorer.sendToMDARequested.emit([useq.AbsolutePosition(x=0.0, y=0.0)], True)
    mock_mda.stage_positions.setValue.assert_not_called()
