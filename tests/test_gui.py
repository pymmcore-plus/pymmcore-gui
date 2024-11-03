from __future__ import annotations

from typing import TYPE_CHECKING

from micromanager_gui import MicroManagerGUI
from micromanager_gui._menubar._menubar import DOCKWIDGETS, WIDGETS
from micromanager_gui._widgets._viewers import MDAViewer

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_load_gui(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    assert gui._menu_bar._mda
    assert gui._core_link._preview
    assert not gui._core_link._preview.isHidden()
    assert gui._core_link._viewer_tab.count() == 1
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    assert gui._core_link._current_viewer is None
    assert gui._core_link._mda_running is False


def test_menu_wdg(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    menu = gui._menu_bar

    assert len(menu._widgets.keys()) == 2  # MDA and GroupPreset widgets
    for action in menu._widgets_menu.actions():
        action.trigger()
    assert len(menu._widgets.keys()) == len(WIDGETS) + len(DOCKWIDGETS)


def test_menu_viewer(qtbot: QtBot, global_mmcore: CMMCorePlus, _run_after_each_test):
    gui = MicroManagerGUI(mmcore=global_mmcore)
    qtbot.addWidget(gui)
    menu = gui._menu_bar
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    # add a viewer
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA1")
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA2")
    assert gui._core_link._viewer_tab.count() == 3

    menu._close_all()
    assert gui._core_link._viewer_tab.count() == 1

    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA3")
    gui._core_link._viewer_tab.addTab(MDAViewer(), "MDA4")
    gui._core_link._viewer_tab.setCurrentIndex(2)
    assert gui._core_link._viewer_tab.count() == 3

    menu._close_all_but_current()
    assert gui._core_link._viewer_tab.count() == 2
    assert gui._core_link._viewer_tab.tabText(0) == "Preview"
    assert gui._core_link._viewer_tab.tabText(1) == "MDA4"

    menu._close_all()
