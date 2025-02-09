from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_widgets import MDAWidget
from PyQt6.QtWidgets import QApplication, QDialog, QDockWidget

from pymmcore_gui import CoreAction, MicroManagerGUI, WidgetAction

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


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
    assert isinstance(gui.get_dock_widget(WidgetAction.MDA_WIDGET), QDockWidget)
