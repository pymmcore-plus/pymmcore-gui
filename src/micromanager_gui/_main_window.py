from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets.hcwizard.intro_page import SRC_CONFIG
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAction,
    QMainWindow,
    QMenuBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ._core_link import _CoreLink
from ._init_system_config import InitializeSystemConfigurations
from ._toolbar import MainToolBar
from ._util import load_sys_config_dialog, save_sys_config_dialog
from ._widgets._config_wizard import HardwareConfigWizard

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent

FLAGS = Qt.WindowType.Dialog
DEFAULT = "Experiment"
ALLOWED_AREAS = (
    Qt.DockWidgetArea.LeftDockWidgetArea
    | Qt.DockWidgetArea.RightDockWidgetArea
    # | Qt.DockWidgetArea.BottomDockWidgetArea
)


class MicroManagerGUI(QMainWindow):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        config: str | None = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.setWindowTitle("Micro-Manager GUI")

        # extend size to fill the screen
        self.showMaximized()

        # add menu
        self._add_menu()

        # add toolbar
        self._toolbar = MainToolBar(self)
        self.contextMenuEvent = self._toolbar.contextMenuEvent

        # add central widget
        central_widget = QWidget()
        central_widget.setLayout(QVBoxLayout())
        self.setCentralWidget(central_widget)

        # set tabbed dockwidgets tabs to the top
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

        # link to the core
        self._core_link = _CoreLink(self, mmcore=self._mmc)

        self._wizard: HardwareConfigWizard | None = None

        # load latest layout
        self._toolbar._widgets_toolbar._load_layout()

        # handle the system configurations at startup.
        # with this we create/updatethe list of the Micro-Manager hardware system
        # configurations files path stored as a json file in the user's configuration
        # file directory (USER_CONFIGS_PATHS).
        # a dialog will be also displayed if no system configuration file is
        # provided to either select one from the list of available ones or to create
        # a new one.
        self._init_cfg = InitializeSystemConfigurations(
            parent=self, config=config, mmcore=self._mmc
        )

    def _add_menu(self) -> None:

        menubar = QMenuBar(self)

        # main Micro-Manager menu
        mm_menu = menubar.addMenu("Micro-Manager")

        # Configurations Sub-Menu
        configurations_menu = mm_menu.addMenu("System Configurations")
        # save cfg
        self.act_save_configuration = QAction("Save Configuration", self)
        self.act_save_configuration.triggered.connect(self._save_cfg)
        configurations_menu.addAction(self.act_save_configuration)
        # load cfg
        self.act_load_configuration = QAction("Load Configuration", self)
        self.act_load_configuration.triggered.connect(self._load_cfg)
        configurations_menu.addAction(self.act_load_configuration)
        # cfg wizard
        self.act_cfg_wizard = QAction("Hardware Configuration Wizard", self)
        self.act_cfg_wizard.triggered.connect(self._show_config_wizard)
        configurations_menu.addAction(self.act_cfg_wizard)

    def _save_cfg(self) -> None:
        """Save the current Micro-Manager system configuration."""
        save_sys_config_dialog(parent=self, mmcore=self._mmc)

    def _load_cfg(self) -> None:
        """Load a Micro-Manager system configuration."""
        load_sys_config_dialog(parent=self, mmcore=self._mmc)

    def _show_config_wizard(self) -> None:
        """Show the Micro-Manager Hardware Configuration Wizard."""
        if self._wizard is None:
            self._wizard = HardwareConfigWizard(parent=self)

        if self._wizard.isVisible():
            self._wizard.raise_()
        else:
            current_cfg = self._mmc.systemConfigurationFile() or ""
            self._wizard.setField(SRC_CONFIG, current_cfg)
            self._wizard.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        # close all viewers
        for viewer in self._core_link._viewers:
            viewer.close()
        super().closeEvent(event)
