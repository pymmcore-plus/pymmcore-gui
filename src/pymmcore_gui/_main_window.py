from __future__ import annotations

import logging
from collections import ChainMap
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast
from weakref import WeakValueDictionary

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDockWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pymmcore_gui.actions._core_qaction import QCoreAction
from pymmcore_gui.actions.widget_actions import WidgetActionInfo

from .actions import CoreAction, WidgetAction
from .actions._action_info import ActionKey
from .settings import settings
from .widgets._pygfx_image import PygfxImagePreview
from .widgets._toolbars import OCToolBar, ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class Menu(str, Enum):
    """Menu names."""

    PYMM_GUI = "pymmcore-gui"
    WINDOW = "Window"

    def __str__(self) -> str:
        return str(self.value)


class Toolbar(str, Enum):
    """Toolbar names."""

    CAMERA_ACTIONS = "Camera Actions"
    OPTICAL_CONFIGS = "Optical Configs"
    WIDGETS = "Widgets"
    SHUTTERS = "Shutters"

    def __str__(self) -> str:
        return str(self.value)


ToolDictValue = list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QToolBar]
MenuDictValue = list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QMenu]


class MicroManagerGUI(QMainWindow):
    """Micro-Manager minimal GUI."""

    DEFAULT_WIDGETS = (
        WidgetAction.CONFIG_GROUPS,
        WidgetAction.STAGE_CONTROL,
        WidgetAction.MDA_WIDGET,
    )
    # Toolbars are a mapping of strings to either a list of ActionKeys or a callable
    # that takes a CMMCorePlus instance and QMainWindow and returns a QToolBar.
    TOOLBARS: Mapping[str, ToolDictValue] = {
        Toolbar.CAMERA_ACTIONS: [
            CoreAction.SNAP,
            CoreAction.TOGGLE_LIVE,
        ],
        Toolbar.OPTICAL_CONFIGS: OCToolBar,
        Toolbar.SHUTTERS: ShuttersToolbar,
        Toolbar.WIDGETS: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
        ],
    }
    # Menus are a mapping of strings to either a list of ActionKeys or a callable
    # that takes a CMMCorePlus instance and QMainWindow and returns a QMenu.
    MENUS: Mapping[str, MenuDictValue] = {
        Menu.PYMM_GUI: [WidgetAction.ABOUT],
        Menu.WINDOW: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.INSTALL_DEVICES,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.EXCEPTION_LOG,
            WidgetAction.CONFIG_WIZARD,
        ],
    }

    def __init__(
        self, *, mmcore: CMMCorePlus | None = None, config: str | Path | None = None
    ) -> None:
        super().__init__()
        self.setWindowTitle("Mike")
        self.setObjectName("MicroManagerGUI")

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        self._inner_widgets = WeakValueDictionary[WidgetAction, QWidget]()
        self._dock_widgets = WeakValueDictionary[WidgetAction, QDockWidget]()
        self._qwidgets = ChainMap[WidgetAction, QWidget](
            self._dock_widgets,  # type: ignore [arg-type]  # (not covariant)
            self._inner_widgets,
        )

        # get global CMMCorePlus instance and setup configuration
        self._mmc = mmc = mmcore or CMMCorePlus.instance()
        # 1. if config is given, load it
        # 2. then check whether the last used config is set and load it
        # 3. if no config is set, load the demo config
        if config is None:
            if (last := settings.last_config) and last.is_file():
                config = last
            else:
                config = "MMConfig_demo.cfg"
        try:
            mmc.loadSystemConfiguration(config)
        except Exception as e:
            logger.warning(
                "Failed to load configuration file %s: %s", config, e, exc_info=True
            )

        mmc.events.systemConfigurationLoaded.connect(self._on_system_config_loaded)

        # MENUS ====================================
        # To add menus or menu items, add them to the MENUS dict above

        for name, entry in self.MENUS.items():
            self._add_menubar(name, entry)

        # TOOLBARS =================================
        # To add toolbars or toolbar items, add them to the TOOLBARS dict above

        for name, tb_entry in self.TOOLBARS.items():
            self._add_toolbar(name, tb_entry)

        # LAYOUT ======================================

        central_wdg = QWidget(self)
        self.setCentralWidget(central_wdg)

        layout = QVBoxLayout(central_wdg)
        self._img_preview = PygfxImagePreview(self, mmcore=self._mmc)
        layout.addWidget(self._img_preview)

        self._restore_state()

    def _on_system_config_loaded(self) -> None:
        if cfg := self._mmc.systemConfigurationFile():
            settings.last_config = Path(cfg)
        else:
            settings.last_config = None
        settings.flush()

    def _add_toolbar(self, name: str, tb_entry: ToolDictValue) -> None:
        if callable(tb_entry):
            tb = tb_entry(self._mmc, self)
            self.addToolBar(tb)
        else:
            tb = cast("QToolBar", self.addToolBar(name))
            for action in tb_entry:
                tb.addAction(self.get_action(action))
        tb.setObjectName(name)

    def _add_menubar(self, name: str, menu_entry: MenuDictValue) -> None:
        mb = cast("QMenuBar", self.menuBar())
        if callable(menu_entry):
            menu = menu_entry(self._mmc, self)
            mb.addMenu(menu)
        else:
            menu = cast("QMenu", mb.addMenu(name))
            for action in menu_entry:
                menu.addAction(self.get_action(action))

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._save_state()
        return super().closeEvent(a0)

    def _restore_state(self) -> None:
        """Restore the state of the window from settings."""
        for key in settings.window.open_widgets or self.DEFAULT_WIDGETS:
            try:
                print("restoring", key)
                self.get_widget(key)
            except Exception:
                logger.exception(f"Failed to restore widget {key}")
        if geo := settings.window.geometry:
            self.restoreGeometry(geo)
        if state := settings.window.window_state:
            # https://forum.qt.io/post/794120
            QTimer.singleShot(10, lambda: self.restoreState(state))

    def _save_state(self) -> None:
        """Save the state of the window to settings."""
        settings.window.geometry = self.saveGeometry().data()
        settings.window.window_state = self.saveState().data()
        settings.window.open_widgets.clear()
        settings.window.open_widgets.update(
            {key for key, widget in self._qwidgets.items() if widget.isVisible()}
        )
        settings.flush()

    @property
    def mmcore(self) -> CMMCorePlus:
        return self._mmc

    def get_action(self, key: ActionKey, create: bool = True) -> QAction:
        """Create a QAction from this key."""
        if key not in self._qactions:
            if not create:
                raise KeyError(
                    f"Action {key} has not been created yet, and 'create' is False"
                )
            # create and cache it
            info: WidgetActionInfo[QWidget] = WidgetActionInfo.for_key(key)
            self._qactions[key] = action = info.to_qaction(self._mmc, self)
            # connect WidgetActions to toggle their widgets
            if isinstance(action.key, WidgetAction):
                action.triggered.connect(self._toggle_action_widget)

        return self._qactions[key]

    def get_widget(self, key: WidgetAction, create: bool = True) -> QWidget:
        """Get (or create) widget for `key`.

        Parameters
        ----------
        key : WidgetAction
            The widget to get.
        create : bool, optional
            Whether to create the widget if it doesn't exist yet, by default True.

        Raises
        ------
        KeyError
            If the widget doesn't exist and `create` is False.
        """
        if key not in self._qwidgets:
            if not create:
                raise KeyError(
                    f"Widget {key} has not been created yet, and 'create' is False"
                )
            self._inner_widgets[key] = widget = key.create_widget(self)

            # override closeEvent to uncheck the corresponding QAction
            # FIXME: this still doesn't work for some QDialogs
            def _closeEvent(a0: QCloseEvent | None = None) -> None:
                if action := self._qactions.get(key):
                    action.setChecked(False)
                if isinstance(a0, QCloseEvent):
                    superCloseEvent(a0)

            superCloseEvent = widget.closeEvent
            widget.closeEvent = _closeEvent  # type: ignore [method-assign]

            # also hook up QDialog's finished signal to closeEvent
            if isinstance(widget, QDialog):
                widget.finished.connect(_closeEvent)

            if dock_area := key.dock_area():
                self._dock_widgets[key] = dw = QDockWidget(key.value, self)
                dw.setWidget(widget)
                dw.closeEvent = _closeEvent  # type: ignore [assignment]
                self.addDockWidget(dock_area, dw)
                dw.setObjectName(key.value)

            # toggle checked state of QAction if it exists
            # can this go somewhere else?
            if action := self._qactions.get(key):
                action.setChecked(True)

        return self._qwidgets[key]

    def _toggle_action_widget(self, checked: bool) -> None:
        """Callback that toggles the visibility of a widget.

        This is connected to the triggered signal of WidgetAction QActions above in
        `get_action`, so it is assumed that the sender is a QCoreAction with a
        WidgetAction key.  Calling otherwise will do nothing.
        """
        if not (
            isinstance(action := self.sender(), QCoreAction)
            and isinstance((key := action.key), WidgetAction)
        ):
            return

        widget = self.get_widget(key)
        widget.setVisible(checked)
        if checked:
            widget.raise_()
