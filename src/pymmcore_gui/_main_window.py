from __future__ import annotations

from collections import ChainMap
from enum import Enum
from typing import TYPE_CHECKING, Literal, cast, overload
from weakref import WeakValueDictionary

from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ConfigWizard
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

from ._ndv_viewers import NDVViewersManager
from .actions import CoreAction, WidgetAction
from .actions._action_info import ActionKey
from .widgets._pygfx_image import PygfxImagePreview
from .widgets._toolbars import OCToolBar, ShuttersToolbar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
        self.setObjectName("MicroManagerGUI")

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        self._inner_widgets = WeakValueDictionary[ActionKey, QWidget]()
        self._dock_widgets = WeakValueDictionary[ActionKey, QDockWidget]()
        self._qwidgets = ChainMap[ActionKey, QWidget](
            self._dock_widgets,  # type: ignore [arg-type]  # (not covariant)
            self._inner_widgets,
        )

        # get global CMMCorePlus instance
        self._mmc = mmc = mmcore or CMMCorePlus.instance()

        self._img_preview = PygfxImagePreview(self, mmcore=self._mmc)
        self._viewers_manager = NDVViewersManager(self, self._mmc)

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
        layout.addWidget(self._img_preview)

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
            if not create:  # pragma: no cover
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

            # If this key specifies a dock area, create a QDockWidget for it
            if dock_area := key.dock_area():
                self._dock_widgets[key] = dw = QDockWidget(key.value, self)
                dw.setWidget(widget)
                dw.closeEvent = _closeEvent  # type: ignore [assignment]
                self.addDockWidget(dock_area, dw)

            # toggle checked state of QAction if it exists
            # can this go somewhere else?
            if action := self._qactions.get(key):
                action.setChecked(True)

        return self._inner_widgets[key]

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
