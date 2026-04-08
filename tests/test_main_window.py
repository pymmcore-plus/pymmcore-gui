from __future__ import annotations

import sys
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import ndv
import pytest
import useq

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui._app import MMQApplication
from pymmcore_gui._notification_manager import NotificationManager
from pymmcore_gui._qt.QtWidgets import QApplication, QDialog
from pymmcore_gui.actions import CoreAction, WidgetAction
from pymmcore_gui.widgets._toolbars import ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytestqt.qtbot import QtBot

    from pymmcore_gui._qt.QtAds import CDockAreaWidget
    from pymmcore_gui._settings import Settings


@pytest.fixture
def gui(qtbot: QtBot, qapp: QApplication) -> Iterator[MicroManagerGUI]:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)
    yield gui


@pytest.mark.parametrize("w_action", list(WidgetAction))
def test_main_window_widget_actions(
    gui: MicroManagerGUI, w_action: WidgetAction
) -> None:
    gui = MicroManagerGUI()
    action = gui.get_action(w_action)
    with patch.object(QDialog, "exec", lambda x: x.show()):
        wdg = gui.get_widget(w_action)
        assert w_action in gui._qactions
    if isinstance(wdg, QDialog):
        ...
    else:
        assert w_action in gui._action_widgets
        assert action.isChecked()
        gui.get_dock_widget(w_action).toggleView(False)
        assert not action.isChecked()


@pytest.mark.parametrize("c_action", list(CoreAction))
def test_main_window_core_actions(gui: MicroManagerGUI, c_action: CoreAction) -> None:
    gui = MicroManagerGUI()
    with patch.object(QDialog, "exec", lambda x: x.show()):
        _ = gui.get_action(c_action)
    assert c_action in gui._qactions


# this warning only occurs on PySide6 for some reason
@pytest.mark.filterwarnings("ignore:No device with label")
def test_shutter_toolbar(gui: MicroManagerGUI, qtbot: QtBot) -> None:
    sh_toolbar = ShuttersToolbar(gui._mmc, gui)

    # in our test cfg we have 3 shutters
    assert (layout := sh_toolbar.layout()) is not None
    assert layout.count() == 3
    assert len(sh_toolbar.actions()) == 3

    # loading default cfg
    with qtbot.waitSignal(gui._mmc.events.systemConfigurationLoaded):
        gui._mmc.loadSystemConfiguration()
    # in our test cfg we have 2 shutters
    assert layout.count() == 2
    assert len(sh_toolbar.actions()) == 2


def test_save_restore_state(gui: MicroManagerGUI, settings: Settings) -> None:
    assert not gui._open_widgets()
    settings.window.open_widgets.clear()

    # save the state
    assert not settings.window.open_widgets
    assert not settings.window.geometry
    gui._save_state()
    assert settings.window.geometry

    # add a widget
    gui.get_widget(WidgetAction.STAGE_CONTROL)
    assert WidgetAction.STAGE_CONTROL in gui._open_widgets()
    # restore the state
    assert not settings.window.open_widgets
    gui.restore_state()
    assert WidgetAction.STAGE_CONTROL not in gui._open_widgets()


def test_ndv_viewers_in_main_window(gui: MicroManagerGUI) -> None:
    central_area = cast("CDockAreaWidget", gui._central_dock_area)
    assert central_area.dockWidgetsCount() == 1
    gui.mmcore.mda.run(
        useq.MDASequence(
            time_plan=useq.TIntervalLoops(interval=1, loops=2),  # pyright: ignore
            channels=["DAPI", "FITC"],  #  pyright: ignore
        ),
    )
    assert central_area.dockWidgetsCount() == 2


def test_main_window_notifications(gui: MicroManagerGUI) -> None:
    """Test that notifications are created and removed correctly."""
    assert isinstance(gui.nm, NotificationManager)

    with patch.object(gui.nm, "show_error_message") as mock_show_error:
        err = ValueError("Boom!")
        app = QApplication.instance()
        assert isinstance(app, MMQApplication)
        app.exceptionRaised.emit(err)
        mock_show_error.assert_called_once()
        assert mock_show_error.call_args[0][0] == "Boom!"


def test_snap(gui: MicroManagerGUI, qtbot: QtBot) -> None:
    """Test that snapping creates a new image preview."""
    vm = gui._viewers_manager
    assert vm._current_image_preview is None
    core = gui._mmc
    with qtbot.waitSignal(vm.previewViewerCreated):
        core.snapImage()
    preview = vm._current_image_preview
    assert preview is not None
    assert len(vm._preview_dock_widgets) == 1

    # change image dtype/shape.
    # We should end up with a second preview widget
    core.setProperty(core.getCameraDevice(), "PixelType", "32bitRGB")
    with qtbot.waitSignal(vm.previewViewerCreated):
        core.snapImage()
    assert vm._current_image_preview is not preview
    preview = vm._current_image_preview
    assert preview is not None
    assert len(vm._preview_dock_widgets) == 2

    # but this should *not* create a new preview
    core.setProperty(core.getCameraDevice(), "Exposure", "42")
    with qtbot.waitSignal(core.events.imageSnapped):
        core.snapImage()
    assert vm._current_image_preview is preview
    assert len(vm._preview_dock_widgets) == 2


@pytest.mark.skipif(
    bool(sys.platform == "darwin"),
    reason="need to debug hanging test on macOS CI",
)
def test_stream(gui: MicroManagerGUI, qtbot: QtBot) -> None:
    """Test that streaming creates a new image preview."""
    vm = gui._viewers_manager
    current = vm._current_image_preview
    assert current is None
    core = gui._mmc
    with qtbot.waitSignal(vm.previewViewerCreated):
        core.startContinuousSequenceAcquisition()

    assert vm._current_image_preview is not None
    ndv_viewer = vm._current_image_preview.widget()._viewer  # type: ignore
    assert isinstance(ndv_viewer, ndv.ArrayViewer)

    # we should be able to change the exposure
    core.setExposure(11)
    # wait until the ndv viewer actually changes the current index (sanity check)
    change_signal = ndv_viewer.display_model.current_index.value_changed
    qtbot.waitSignals([change_signal] * 4)
    qtbot.wait(40)
    core.stopSequenceAcquisition()


def test_core_status_bar(gui: MicroManagerGUI, qtbot: QtBot) -> None:
    """Test that the status bar shows and updates core state."""
    sb = gui._core_status
    core = gui._mmc

    # Initial state should be populated from demo config
    assert "XY:" in sb._xy_label.text()
    assert "Z:" in sb._z_label.text()
    assert "Ch:" in sb._channel_label.text()
    assert "512x512" in sb._camera_label.text()
    assert sb._mda_label.text() == "MDA: idle"
    assert not sb._mda_progress.isVisible()

    # XY position update via accumulator moveFinished
    assert sb._xy_accum is not None
    sb._xy_accum.moveFinished.emit()
    assert "XY:" in sb._xy_label.text()
    assert sb._xy_label.text() != "XY: --"

    # Z position update via signal
    core.events.stagePositionChanged.emit("Z", 42.5)
    assert "42.5" in sb._z_label.text()

    # Channel update
    core.setConfig("Channel", "FITC")
    assert "FITC" in sb._channel_label.text()

    # Camera binning update
    cam = core.getCameraDevice()
    core.setProperty(cam, "Binning", "2")
    assert "bin:2" in sb._camera_label.text()

    # MDA progress bar
    seq = useq.MDASequence(
        time_plan=useq.TIntervalLoops(interval=0, loops=2),  # pyright: ignore
        channels=["DAPI"],  # pyright: ignore
    )
    expected_total = len(list(seq))
    with qtbot.waitSignal(gui._viewers_manager.mdaViewerCreated):
        core.mda.run(seq)
    # After MDA finishes, progress should be at max and label says done
    assert sb._mda_progress.value() == expected_total
    assert sb._mda_progress.maximum() == expected_total
    assert sb._mda_label.text() == "MDA: done"

    # After the hide timer fires, progress bar hides and label resets
    sb._mda_hide_timer.timeout.emit()
    assert not sb._mda_progress.isVisible()
    assert sb._mda_label.text() == "MDA: idle"
    assert sb._mda_progress.value() == 0


def test_mda(gui: MicroManagerGUI, qtbot: QtBot) -> None:
    vm = gui._viewers_manager
    assert vm._active_mda_viewer is None
    core = gui._mmc
    with qtbot.waitSignal(vm.mdaViewerCreated):
        core.mda.run(
            useq.MDASequence(
                time_plan=useq.TIntervalLoops(interval=1, loops=2),  # pyright: ignore
                channels=["DAPI", "FITC"],  #  pyright: ignore
            ),
        )
    assert vm._active_mda_viewer is not None
