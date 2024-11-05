from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import (
    CameraRoiWidget,
    ConfigWizard,
    GroupPresetTableWidget,
    PixelConfigurationWidget,
    PropertyBrowser,
)
from pymmcore_widgets.hcwizard.intro_page import SRC_CONFIG
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAction,
    QDockWidget,
    QFileDialog,
    QMenuBar,
    QScrollArea,
    QTabWidget,
    QWidget,
)

from micromanager_gui._widgets._install_widget import _InstallWidget
from micromanager_gui._widgets._mda_widget import MDAWidget
from micromanager_gui._widgets._mm_console import MMConsole
from micromanager_gui._widgets._stage_control import StagesControlWidget

if TYPE_CHECKING:
    from micromanager_gui._main_window import MicroManagerGUI

FLAGS = Qt.WindowType.Dialog
CONSOLE = "Console"
WIDGETS = {
    "Property Browser": PropertyBrowser,
    "Pixel Configuration": PixelConfigurationWidget,
    "Install Devices": _InstallWidget,
}
DOCKWIDGETS = {
    "MDA Widget": MDAWidget,
    "Groups and Presets": GroupPresetTableWidget,
    "Stage Control": StagesControlWidget,
    "Camera ROI": CameraRoiWidget,
    CONSOLE: MMConsole,
}
RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
BOTTOM = Qt.DockWidgetArea.BottomDockWidgetArea

MMC = "mmc"
MDA = "mda"
WDGS = "wdgs"
VIEWERS = "viewers"
PREVIEW = "preview"


class ScrollableDockWidget(QDockWidget):
    """A QDockWidget with a QScrollArea."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        widget: QWidget,
    ):
        super().__init__(title, parent)
        self.main_widget = widget
        # set allowed dock areas
        self.setAllowedAreas(LEFT | RIGHT)

        # create the scroll area and set it as the widget of the QDockwidget
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        super().setWidget(self.scroll_area)

        # set the widget to the scroll area
        self.scroll_area.setWidget(widget)
        # resize the dock widget to the size hint of the widget
        self.resize(widget.minimumSizeHint())


class _MenuBar(QMenuBar):
    """Menu Bar for the Micro-Manager GUI.

    It contains the actions to create and show widgets and dockwidgets.
    """

    def __init__(
        self, parent: MicroManagerGUI, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._main_window = parent

        # set tabbed dockwidgets tabs to the top
        self._main_window.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

        self._mmc = mmcore or CMMCorePlus.instance()

        # to keep track of the widgets
        self._widgets: dict[str, QWidget | ScrollableDockWidget] = {}

        # widgets
        self._wizard: ConfigWizard | None = None  # is in a different menu
        self._mda: MDAWidget | None = None
        self._mm_console: MMConsole | None = None

        # configurations_menu
        self._configurations_menu = self.addMenu("System Configurations")
        # hardware cfg wizard
        self._act_cfg_wizard = QAction("Hardware Configuration Wizard", self)
        self._act_cfg_wizard.triggered.connect(self._show_config_wizard)
        self._configurations_menu.addAction(self._act_cfg_wizard)
        # save cfg
        self._act_save_configuration = QAction("Save Configuration", self)
        self._act_save_configuration.triggered.connect(self._save_cfg)
        self._configurations_menu.addAction(self._act_save_configuration)
        # load cfg
        self._act_load_configuration = QAction("Load Configuration", self)
        self._act_load_configuration.triggered.connect(self._load_cfg)
        self._configurations_menu.addAction(self._act_load_configuration)

        # widgets_menu
        self._widgets_menu = self.addMenu("Widgets")

        # viewer menu
        self._viewer_menu = self.addMenu("Viewers")
        self._act_close_all = QAction("Close All Viewers", self)
        self._act_close_all.triggered.connect(self._close_all)
        self._viewer_menu.addAction(self._act_close_all)
        self._act_close_all_but_current = QAction(
            "Close All Viewers but the Current", self
        )
        self._act_close_all_but_current.triggered.connect(self._close_all_but_current)
        self._viewer_menu.addAction(self._act_close_all_but_current)

        # create actions from WIDGETS and DOCKWIDGETS
        keys = {*WIDGETS.keys(), *DOCKWIDGETS.keys()}
        for action_name in sorted(keys):
            action = QAction(action_name, self)
            action.triggered.connect(self._show_widget)
            self._widgets_menu.addAction(action)

        # create 'Group and Presets' and 'MDA' widgets at the startup
        self._create_dock_widget("Groups and Presets", dock_area=LEFT)
        mda = self._create_dock_widget("MDA Widget")
        self._mda = cast(MDAWidget, mda.main_widget)

    def _enable(self, enable: bool) -> None:
        """Enable or disable the actions."""
        self._configurations_menu.setEnabled(enable)
        self._widgets_menu.setEnabled(enable)
        self._viewer_menu.setEnabled(enable)

    def _save_cfg(self) -> None:
        (filename, _) = QFileDialog.getSaveFileName(
            self, "Save Micro-Manager Configuration."
        )
        if filename:
            self._mmc.saveSystemConfiguration(
                filename if str(filename).endswith(".cfg") else f"{filename}.cfg"
            )

    def _load_cfg(self) -> None:
        """Open file dialog to select a config file."""
        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a Micro-Manager configuration file", "", "cfg(*.cfg)"
        )
        if filename:
            self._mmc.unloadAllDevices()
            self._mmc.loadSystemConfiguration(filename)

    def _show_config_wizard(self) -> None:
        """Show the Micro-Manager Hardware Configuration Wizard."""
        if self._wizard is None:
            self._wizard = ConfigWizard(parent=self, core=self._mmc)
            self._wizard.setWindowFlags(FLAGS)
        if self._wizard.isVisible():
            self._wizard.raise_()
        else:
            current_cfg = self._mmc.systemConfigurationFile() or ""
            self._wizard.setField(SRC_CONFIG, current_cfg)
            self._wizard.show()

    def _close_all(self, skip: bool | list[int] | None = None) -> None:
        """Close all viewers."""
        # the QAction sends a bool when triggered. We don't want to handle a bool
        # so we convert it to an empty list.
        if isinstance(skip, bool) or skip is None:
            skip = []
        viewer_tab = self._main_window._core_link._viewer_tab
        for index in reversed(range(viewer_tab.count())):
            if index in skip or index == 0:  # 0 to skip the prewiew tab
                continue
            tab_name = viewer_tab.tabText(index)
            widget = viewer_tab.widget(index)
            viewer_tab.removeTab(index)
            widget.deleteLater()

            # update the viewers variable in the console
            if self._mm_console is not None:
                self._mm_console.shell.user_ns["viewers"].pop(tab_name, None)

    def _close_all_but_current(self) -> None:
        """Close all viewers except the current one."""
        # build the list of indexes to skip
        viewer_tab = self._main_window._core_link._viewer_tab
        current = viewer_tab.currentWidget()
        skip = [viewer_tab.indexOf(current)]
        # close all but the current one
        self._close_all(skip)

    def _show_widget(self) -> None:
        """Create or show a widget."""
        # get the action that triggered the signal
        sender = cast(QAction, self.sender())
        # get action name
        action_name = sender.text()

        if action_name not in {*WIDGETS.keys(), *DOCKWIDGETS.keys()}:
            warnings.warn(f"Widget '{action_name}' not found.", stacklevel=2)
            return

        # already created
        if action_name in self._widgets:
            wdg = self._widgets[action_name]
            wdg.show()
            wdg.raise_()
            return

        # create dock widget
        if action_name in DOCKWIDGETS:
            if action_name == CONSOLE:
                self._launch_mm_console()
            else:
                self._create_dock_widget(action_name)
        # create widget
        else:
            wdg = self._create_widget(action_name)
            wdg.show()

    def _create_dock_widget(
        self, action_name: str, dock_area: Qt.DockWidgetArea = RIGHT
    ) -> ScrollableDockWidget:
        """Create a dock widget with a scroll area."""
        wdg = DOCKWIDGETS[action_name](parent=self, mmcore=self._mmc)
        dock = ScrollableDockWidget(
            self,
            title=action_name,
            widget=wdg,
        )
        self._main_window.addDockWidget(dock_area, dock)
        self._widgets[action_name] = dock
        return dock

    def _create_widget(self, action_name: str) -> QWidget:
        """Create a widget."""
        wdg = WIDGETS[action_name](parent=self, mmcore=self._mmc)
        wdg.setWindowFlags(FLAGS)
        self._widgets[action_name] = wdg
        return wdg

    def _launch_mm_console(self) -> None:
        if self._mm_console is not None:
            return

        # All values in the dictionary below can be accessed from the console using
        # the associated string key
        user_vars = {
            MMC: self._mmc,  # CMMCorePlus instance
            WDGS: self._widgets,  # dictionary of all the widgets
            MDA: self._mda,  # quick access to the MDA widget
            VIEWERS: self._get_current_mda_viewers(),  # dictionary of all the viewers
            PREVIEW: self._main_window._core_link._preview,  # access to preview widget
        }

        self._mm_console = MMConsole(user_vars)

        dock = QDockWidget(CONSOLE, self)
        dock.setAllowedAreas(LEFT | RIGHT | BOTTOM)
        dock.setWidget(self._mm_console)
        self._widgets[CONSOLE] = dock

        self._main_window.addDockWidget(RIGHT, dock)

    def _get_current_mda_viewers(self) -> dict[str, QWidget]:
        """Update the viewers variable in the MMConsole."""
        viewers_dict = {}
        tab = self._main_window._core_link._viewer_tab
        for viewers in range(tab.count()):
            if viewers == 0:  # skip the preview tab
                continue
            tab_name = tab.tabText(viewers)
            wdg = tab.widget(viewers)
            viewers_dict[tab_name] = wdg
        return viewers_dict
