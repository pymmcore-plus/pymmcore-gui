from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import MDAWidget
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6Ads import CDockWidget

from pymmcore_gui import CoreAction, MicroManagerGUI, WidgetAction
from pymmcore_gui.widgets._toolbars import ShuttersToolbar

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

    from pymmcore_gui.settings import Settings


def test_main_window(qtbot: QtBot, qapp: QApplication) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)
    for w_action in (WidgetAction.ABOUT, WidgetAction.PROP_BROWSER):
        action = gui.get_action(w_action)
        wdg = gui.get_widget(w_action)
        assert w_action in gui._qactions
        assert w_action in gui._action_widgets
        if not isinstance(wdg, QDialog):
            assert action.isChecked()
            wdg.close()
            assert not action.isChecked()

    for c_action in CoreAction:
        gui.get_action(c_action)
        assert c_action in gui._qactions

    assert isinstance(gui.get_widget(WidgetAction.MDA_WIDGET), MDAWidget)
    assert isinstance(gui.get_dock_widget(WidgetAction.MDA_WIDGET), CDockWidget)


def test_shutter_toolbar(qtbot: QtBot, qapp: QApplication, tmp_path) -> None:
    # make sure that when we load a new cfg the shutters toolbar is updated
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)

    sh_toolbar = ShuttersToolbar(gui._mmc, gui)

    # in our test cfg we have 3 shutters
    assert sh_toolbar.layout().count() == 3  # pyright: ignore
    assert len(sh_toolbar.actions()) == 3

    # loading default cfg
    gui._mmc.loadSystemConfiguration()
    # in our test cfg we have 2 shutters
    assert sh_toolbar.layout().count() == 2  # pyright: ignore
    assert len(sh_toolbar.actions()) == 2


def test_save_restore_state(
    qtbot: QtBot, qapp: QApplication, settings: Settings
) -> None:
    gui = MicroManagerGUI()
    qtbot.addWidget(gui)
    qapp.processEvents()  # force the initial _restore_state to run.

    # the thing we're going to restore
    assert WidgetAction.STAGE_CONTROL not in gui._open_widgets()

    # save the state
    assert not settings.window.geometry
    gui._save_state()
    assert settings.window.geometry

    # add a widget
    gui.get_widget(WidgetAction.STAGE_CONTROL)
    assert WidgetAction.STAGE_CONTROL in gui._open_widgets()
    # restore the state
    gui._restore_state()
    assert WidgetAction.STAGE_CONTROL not in gui._open_widgets()
