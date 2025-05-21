from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import ndv
import pytest
import useq
from pymmcore_widgets import MDAWidget
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6Ads import CDockWidget

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui._app import MMQApplication
from pymmcore_gui._notification_manager import NotificationManager
from pymmcore_gui.actions import CoreAction, WidgetAction
from pymmcore_gui.widgets._toolbars import ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Iterator

    from PyQt6Ads import CDockAreaWidget
    from pytestqt.qtbot import QtBot

    from pymmcore_gui._settings import Settings


@pytest.fixture
def gui(qtbot: QtBot, qapp: QApplication) -> Iterator[MicroManagerGUI]:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)
    yield gui


@pytest.mark.parametrize("w_action", list(WidgetAction))
def test_main_window(gui: MicroManagerGUI, w_action: WidgetAction) -> None:
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

    for c_action in CoreAction:
        gui.get_action(c_action)
        assert c_action in gui._qactions

    assert isinstance(gui.get_widget(WidgetAction.MDA_WIDGET), MDAWidget)
    assert isinstance(gui.get_dock_widget(WidgetAction.MDA_WIDGET), CDockWidget)


def test_shutter_toolbar(gui: MicroManagerGUI) -> None:
    sh_toolbar = ShuttersToolbar(gui._mmc, gui)

    # in our test cfg we have 3 shutters
    assert (layout := sh_toolbar.layout()) is not None
    assert layout.count() == 3
    assert len(sh_toolbar.actions()) == 3

    # loading default cfg
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


@pytest.mark.skipif(
    bool(os.getenv("CI") and sys.platform == "darwin"),
    reason="need to debug hanging test on macOS CI",
)
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
