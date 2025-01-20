from __future__ import annotations

from collections import ChainMap
from enum import Enum
from typing import TYPE_CHECKING, cast
from weakref import WeakValueDictionary

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ImagePreview
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
from .core_link._core_link import CoreViewersLink
from .widgets._toolbars import OCToolBar, ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class Menu(str, Enum):
    """Menu names."""

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


class MicroManagerGUI(QMainWindow):
    """Micro-Manager minimal GUI."""

    # Toolbars are a mapping of strings to either a list of ActionKeys or a callable
    # that takes a CMMCorePlus instance and QMainWindow and returns a QToolBar.
    TOOLBARS: Mapping[
        str, list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QToolBar]
    ] = {
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
    MENUS: Mapping[
        str, list[ActionKey] | Callable[[CMMCorePlus, QMainWindow], QMenu]
    ] = {
        Menu.WINDOW: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.INSTALL_DEVICES,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.EXCEPTION_LOG,
        ],
    }

    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Mike")
        self.setObjectName("MicroManagerGUI")

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        self._inner_widgets = WeakValueDictionary[ActionKey, QWidget]()
        self._dock_widgets = WeakValueDictionary[ActionKey, QDockWidget]()
        self._qwidgets = ChainMap[ActionKey, QWidget](
            self._dock_widgets,
            self._inner_widgets,
        )

        # get global CMMCorePlus instance
        self._mmc = mmc = mmcore or CMMCorePlus.instance()

        self._core_link = CoreViewersLink(self, mmcore=self._mmc)

        # MENUS ====================================
        # To add menus or menu items, add them to the MENUS dict above

        mb = cast("QMenuBar", self.menuBar())
        for name, entry in self.MENUS.items():
            if callable(entry):
                menu = entry(mmc, self)
                mb.addMenu(menu)
            else:
                menu = cast("QMenu", mb.addMenu(name))
                for action in entry:
                    menu.addAction(self.get_action(action))

        # TOOLBARS =================================
        # To add toolbars or toolbar items, add them to the TOOLBARS dict above

        for name, tb_entry in self.TOOLBARS.items():
            if callable(tb_entry):
                tb = tb_entry(mmc, self)
                self.addToolBar(tb)
            else:
                tb = cast("QToolBar", self.addToolBar(name))
                for action in tb_entry:
                    tb.addAction(self.get_action(action))

        # populate with default widgets ...
        # eventually this should be configurable and restored from a config file
        for key in (
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.MDA_WIDGET,
        ):
            self.get_widget(key)

        # LAYOUT ======================================

        central_wdg = QWidget(self)
        self.setCentralWidget(central_wdg)

        layout = QVBoxLayout(central_wdg)
        layout.addWidget(ImagePreview(mmcore=self._mmc))

    @property
    def mmc(self) -> CMMCorePlus:
        return self._mmc

    def get_action(self, key: ActionKey, create: bool = True) -> QAction:
        """Create a QAction from this key."""
        if key not in self._qactions:
            if not create:
                raise KeyError(
                    f"Action {key} has not been created yet, and 'create' is False"
                )
            # create and cache it
            info = WidgetActionInfo.for_key(key)
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
            widget.closeEvent = _closeEvent

            # also hook up QDialog's finished signal to closeEvent
            if isinstance(widget, QDialog):
                widget.finished.connect(_closeEvent)

            if dock_area := key.dock_area():
                self._dock_widgets[key] = dw = QDockWidget(key.value, self)
                dw.setWidget(widget)
                dw.closeEvent = _closeEvent
                self.addDockWidget(dock_area, dw)

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
