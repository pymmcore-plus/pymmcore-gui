from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast, overload
from weakref import WeakValueDictionary

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ConfigWizard
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QIcon
from PyQt6.QtWidgets import (
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

from ._ndv_viewers import NDVViewersManager
from .actions import CoreAction, WidgetAction
from .actions._action_info import ActionKey
from .settings import settings
from .widgets._pygfx_image import PygfxImagePreview
from .widgets._toolbars import OCToolBar, ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pymmcore_widgets import (
        CameraRoiWidget,
        ConfigWizard,
        GroupPresetTableWidget,
        InstallWidget,
        MDAWidget,
        PixelConfigurationWidget,
        PropertyBrowser,
    )

    from pymmcore_gui.widgets._about_widget import AboutWidget
    from pymmcore_gui.widgets._exception_log import ExceptionLog
    from pymmcore_gui.widgets._mm_console import MMConsole
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

logger = logging.getLogger("pymmcore_gui")

RESOURCES = Path(__file__).parent / "resources"
ICON = RESOURCES / ("icon.ico" if sys.platform.startswith("win") else "logo.png")


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

    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Mike")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setObjectName("MicroManagerGUI")

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        # widgets that are associated with a QAction
        self._action_widgets = WeakValueDictionary[WidgetAction, QWidget]()
        # the wrapping QDockWidget for widgets that are associated with a QAction
        self._dock_widgets = WeakValueDictionary[ActionKey, QDockWidget]()

        # get global CMMCorePlus instance
        self._mmc = mmcore or CMMCorePlus.instance()

        self._img_preview = PygfxImagePreview(self, mmcore=self._mmc)
        self._viewers_manager = NDVViewersManager(self, self._mmc)

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
        initial_widgets = settings.window.initial_widgets
        # we need to create the widgets first, before calling restoreState.
        for key in initial_widgets:
            self.get_widget(key)
        # restore position and size of the main window
        if geo := settings.window.geometry:
            self.restoreGeometry(geo)

        # restore state of toolbars and dockwidgets, but only after event loop start
        # https://forum.qt.io/post/794120
        if initial_widgets and (state := settings.window.window_state):

            def _restore_later() -> None:
                self.restoreState(state)
                for key in self._open_widgets():
                    self.get_action(key).setChecked(True)

            QTimer.singleShot(0, _restore_later)

    def _save_state(self) -> None:
        """Save the state of the window to settings."""
        # save position and size of the main window
        settings.window.geometry = self.saveGeometry().data()
        # remember which widgets are open, and preserve their state.
        settings.window.initial_widgets = open_ = self._open_widgets()
        if open_:
            settings.window.window_state = self.saveState().data()
        else:
            settings.window.window_state = None
        # write to disk, blocking up to 5 seconds
        settings.flush(timeout=5000)

    def _open_widgets(self) -> set[WidgetAction]:
        """Return the set of open widgets."""
        return {
            key for key, widget in self._action_widgets.items() if widget.isVisible()
        }

    @property
    def mmcore(self) -> CMMCorePlus:
        return self._mmc

    def get_action(self, key: ActionKey, create: bool = True) -> QAction:
        """Create a QAction from this key."""
        if key not in self._qactions:
            if not create:  # pragma: no cover
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

    # TODO: it's possible this could be expressed using Generics...
    # which would avoid the need for the manual overloads
    # fmt: off
    @overload
    def get_widget(self, key: Literal[WidgetAction.ABOUT], create: bool = ...) -> AboutWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.CAMERA_ROI], create: bool = ...) -> CameraRoiWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.CONFIG_GROUPS], create: bool = ...) -> GroupPresetTableWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.CONFIG_WIZARD], create: bool = ...) -> ConfigWizard: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.CONSOLE], create: bool = ...) -> MMConsole: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.EXCEPTION_LOG], create: bool = ...) -> ExceptionLog: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.INSTALL_DEVICES], create: bool = ...) -> InstallWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.MDA_WIDGET], create: bool = ...) -> MDAWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.PIXEL_CONFIG], create: bool = ...) -> PixelConfigurationWidget: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.PROP_BROWSER], create: bool = ...) -> PropertyBrowser: ...  # noqa: E501
    @overload
    def get_widget(self, key: Literal[WidgetAction.STAGE_CONTROL], create: bool = ...) -> StagesControlWidget: ...  # noqa: E501
    # generic fallback
    @overload
    def get_widget(self, key: WidgetAction, create: bool = ...) -> QWidget: ...
    # fmt: on
    def get_widget(self, key: WidgetAction, create: bool = True) -> QWidget:
        """Get (or create) widget for `key` ensuring that it is linked to its QAction.

        If the widget has been "closed" (hidden), it will be re-shown.

        Note that all widgets created this way are singletons, so calling this method
        multiple times will return the same widget instance.

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
        if key not in self._action_widgets:
            if not create:  # pragma: no cover
                raise KeyError(
                    f"Widget {key} has not been created yet, and 'create' is False"
                )
            widget = key.create_widget(self)
            widget.setObjectName(key.name)
            self._action_widgets[key] = widget

            # If a dock area is specified, wrap the widget in a QDockWidget.
            if (dock_area := key.dock_area()) is not None:
                dock = QDockWidget(key.value, self)
                dock.setWidget(widget)
                dock.setObjectName(f"docked_{key.name}")
                self._link_widget_to_action(dock, key)
                self._dock_widgets[key] = dock
                self.addDockWidget(dock_area, dock)
            else:
                self._link_widget_to_action(widget, key)

            # Set the action checked since the widget is now “open.”
            if (action := self._qactions.get(key)) is not None:
                action.setChecked(True)

        return self._action_widgets[key]

    def get_dock_widget(self, key: WidgetAction) -> QDockWidget:
        """Get the QDockWidget for `key`.

        Note, you can also get the QDockWidget by calling `get_widget(key)`, and then
        calling `widget.parent()`.  The parent will *either* be an instance of
        `QDockWidget` (if it's actually a docked widget), or `MicroManagerGUI`, if
        it's not docked.  You *should* use `isisinstance` in this case to check.

        Parameters
        ----------
        key : WidgetAction
            The key for the *inner* widget owned by the requested QDockWidget.

        Raises
        ------
        KeyError
            If the widget doesn't exist.
        """
        if key not in self._dock_widgets:
            raise KeyError(  # pragma: no cover
                f"Dock widget for {key} has not been created yet, "
                "or it is not owned by a dock widget"
            )
        return self._dock_widgets[key]

    def _link_widget_to_action(self, widget: QWidget, key: WidgetAction) -> None:
        """Sets up the two-way link between a widget and its associated QAction."""
        # When the action is toggled, show or hide the widget.
        action: QAction = self.get_action(key)

        # Ensure the widget does not get deleted on close.
        widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        inner_widget: QWidget | None = None
        if isinstance(widget, QDockWidget) and (inner_widget := widget.widget()):
            inner_widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # Install an event filter so that "closing" the widget
        # simply hides it and updates the action toggle state.
        if not hasattr(widget, "_close_filter"):
            # it's important to store the event filter on the widget, otherwise
            # it will be garbage collected and the event filter will stop working
            widget._close_filter = ef = _CloseEventFilter(action)  # type: ignore
            widget.installEventFilter(ef)
            if inner_widget is not None:
                inner_widget.installEventFilter(ef)

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

        # if the widget is a dock widget, we want to toggle the dock widget
        # rather than the inner widget
        if key in self._dock_widgets:
            widget: QWidget = self.get_dock_widget(key)
        else:
            # this will create the widget if it doesn't exist yet,
            # e.g. for a click event on a Toolbutton that doesn't yet have a widget
            widget = self.get_widget(key)
        widget.setVisible(checked)
        if checked:
            widget.raise_()


class _CloseEventFilter(QObject):
    """Event filter that intercepts close events and hides the widget instead.

    This is installed on widgets that are associated with a QAction, so that closing
    the widget will simply hide it and update the action toggle state.
    """

    def __init__(self, action: QAction) -> None:
        super().__init__()
        self._action = action

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if event and event.type() in (QEvent.Type.Close, QEvent.Type.HideToParent):
            # Instead of destroying, simply hide the widget and update the action.
            event.ignore()
            try:
                self._action.setChecked(False)
            except RuntimeError:
                return True
            if isinstance(watched, QWidget):
                # prefer hiding/showing the dock widget, since this will also hide/show
                # the inner widget.
                if isinstance(par := watched.parent(), QDockWidget):
                    par.hide()
                else:
                    watched.hide()
            return True  # Prevent further processing (do not destroy the widget)
        return False
