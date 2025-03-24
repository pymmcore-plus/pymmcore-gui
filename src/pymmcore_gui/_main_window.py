from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast, overload
from weakref import WeakValueDictionary

import ndv
import tifffile
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import ConfigWizard
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QIcon,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QStatusBar,
    QToolBar,
    QWidget,
)
from PyQt6Ads import CDockManager, CDockWidget, SideBarLocation
from superqt import QIconifyIcon

from pymmcore_gui.actions._core_qaction import QCoreAction
from pymmcore_gui.actions.widget_actions import WidgetActionInfo
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview

from ._ndv_viewers import NDVViewersManager
from ._notification_manager import NotificationManager
from .actions import CoreAction, WidgetAction
from .actions._action_info import ActionKey
from .settings import Settings
from .widgets._toolbars import OCToolBar

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
    from useq import MDASequence

    from pymmcore_gui.widgets._about_widget import AboutWidget
    from pymmcore_gui.widgets._exception_log import ExceptionLog
    from pymmcore_gui.widgets._mm_console import MMConsole
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

    from ._app import MMQApplication


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
        # Toolbar.SHUTTERS: ShuttersToolbar,
        Toolbar.WIDGETS: [
            WidgetAction.CONSOLE,
            WidgetAction.PROP_BROWSER,
            WidgetAction.MDA_WIDGET,
            WidgetAction.STAGE_CONTROL,
            WidgetAction.CAMERA_ROI,
            WidgetAction.ILLUM,
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
            WidgetAction.ILLUM,
            WidgetAction.CONFIG_GROUPS,
            WidgetAction.EXCEPTION_LOG,
            WidgetAction.CONFIG_WIZARD,
        ],
    }

    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Christina (A QI Special)")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setObjectName("MicroManagerGUI")
        self.setAcceptDrops(True)

        # Serves to cache created QAction objects so that they can be re-used
        # when the same action is requested multiple times. This is useful to
        # synchronize the state of actions that may appear in multiple menus or
        # toolbars.
        self._qactions = WeakValueDictionary[ActionKey, QAction]()
        # widgets that are associated with a QAction
        self._action_widgets = WeakValueDictionary[WidgetAction, QWidget]()
        # the wrapping QDockWidget for widgets that are associated with a QAction
        self._dock_widgets = WeakValueDictionary[WidgetAction, CDockWidget]()

        # get global CMMCorePlus instance
        self._mmc = mmcore or CMMCorePlus.instance()

        self._is_mda_running = False
        mda_ev = self._mmc.mda.events
        mda_ev.sequenceStarted.connect(lambda: setattr(self, "_is_mda_running", True))
        mda_ev.sequenceFinished.connect(lambda: setattr(self, "_is_mda_running", False))

        ev = self._mmc.events
        ev.imageSnapped.connect(self._on_image_snapped)
        ev.sequenceAcquisitionStarted.connect(self._on_streaming_started)
        ev.continuousSequenceAcquisitionStarted.connect(self._on_streaming_started)
        self._img_preview: CDockWidget | None = None

        self._viewers_manager = NDVViewersManager(self, self._mmc)
        self._viewers_manager.viewerCreated.connect(self._on_viewer_created)
        self._notification_manager = NotificationManager(self)
        if app := QApplication.instance():
            if hasattr(app, "exceptionRaised"):
                cast("MMQApplication", app).exceptionRaised.connect(self._on_exception)

        # Status bar -----------------------------------------

        self._status_bar = QStatusBar(self)
        self._status_bar.setMaximumHeight(26)
        self.setStatusBar(self._status_bar)

        self.bell_button = QPushButton("")
        self.bell_button.setIcon(QIconifyIcon("codicon:bell"))
        self.bell_button.setFlat(True)  # Make it blend nicely
        self._status_bar.addPermanentWidget(self.bell_button)

        # MENUS ====================================
        # To add menus or menu items, add them to the MENUS dict above

        for name, entry in self.MENUS.items():
            self._add_menubar(name, entry)

        # TOOLBARS =================================
        # To add toolbars or toolbar items, add them to the TOOLBARS dict above

        for name, tb_entry in self.TOOLBARS.items():
            self._add_toolbar(name, tb_entry)

        # LAYOUT ======================================

        # Create the dock manager. Because the parent parameter is a QMainWindow
        # the dock manager registers itself as the central widget.
        # It controls *all* widgets that are owned by the QMainWindow (both those that
        # are docked and floating).
        CDockManager.setConfigFlag(
            CDockManager.eConfigFlag.DockAreaHasCloseButton, False
        )
        CDockManager.setConfigFlag(CDockManager.eConfigFlag.OpaqueSplitterResize, True)
        CDockManager.setAutoHideConfigFlag(
            CDockManager.eAutoHideFlag.AutoHideFeatureEnabled, True
        )
        self.dock_manager = CDockManager(self)

        self._central = CDockWidget("Viewers", self)
        self._central.setFeature(CDockWidget.DockWidgetFeature.NoTab, True)
        blank = QWidget()
        blank.setObjectName("blank")
        blank.setStyleSheet(
            "background-color: qlineargradient("
            "x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #333, stop: 1 #111);"
        )
        self._central.setWidget(blank)
        self._central_dock_area = self.dock_manager.setCentralWidget(self._central)

        QTimer.singleShot(0, self._restore_state)

    @property
    def nm(self) -> NotificationManager:
        """A callable that can be used to show a message in the status bar."""
        return self._notification_manager

    def _create_or_show_img_preview(self) -> NDVPreview | None:
        """Create or show the image preview widget, return True if created."""
        preview = None
        if self._img_preview is None:
            preview = NDVPreview(self, mmcore=self._mmc)
            self._img_preview = dw = CDockWidget("Preview", self)
            self._img_preview.setWidget(preview)
            self.dock_manager.addDockWidgetTabToArea(dw, self._central_dock_area)
        elif not self._img_preview.isVisible():
            self.dock_manager.addDockWidgetTabToArea(
                self._img_preview, self._central_dock_area
            )
        return preview

    def _on_streaming_started(self) -> None:
        if not self._is_mda_running:
            if preview := self._create_or_show_img_preview():
                preview._on_streaming_start()

    def _on_image_snapped(self) -> None:
        if not self._is_mda_running:
            if preview := self._create_or_show_img_preview():
                preview.set_data(self._mmc.getImage())

    def _on_system_config_loaded(self) -> None:
        settings = Settings.instance()
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

    def _restore_state(self, show: bool = False) -> None:
        """Restore the state of the window from settings (or load default state).

        show is added as a convenience here because it may be a common use case to
        restore the state in a single shot timer and (only) then show the window.
        This avoids the window flashing on the screen before it is properly positioned.
        """
        settings = Settings.instance()
        initial_widgets = settings.window.initial_widgets
        # we need to create the widgets first, before calling restoreState.
        for key in initial_widgets:
            self.get_widget(key)

        # restore position and size of the main window
        if geo := settings.window.geometry:
            self.restoreGeometry(geo)
        elif screen := QGuiApplication.primaryScreen():
            # if no geometry is saved, center the window taking up 90% of the screen
            percent = 0.9
            ageo = screen.availableGeometry()
            ageo.setSize(ageo.size() * percent)
            margin = (1 - percent) / 2
            ageo.translate(int(ageo.width() * margin), int(ageo.height() * margin))
            self.setGeometry(ageo)

        # restore state of toolbars and dockwidgets, but only after event loop start
        # https://forum.qt.io/post/794120
        if initial_widgets and (state := settings.window.dock_manager_state):
            self.dock_manager.restoreState(state)
            for key in self._open_widgets():
                self.get_action(key).setChecked(True)
            if wdg := self.dock_manager.centralWidget():
                self._central_dock_area = wdg.dockAreaWidget()

        if show:
            self.show()

    def _save_state(self) -> None:
        """Save the state of the window to settings."""
        # save position and size of the main window
        settings = Settings.instance()
        settings.window.geometry = self.saveGeometry().data()
        # remember which widgets are open, and preserve their state.
        settings.window.initial_widgets = open_ = self._open_widgets()
        if open_:
            # note that dock_manager.saveState mostly replaces QMainWindow.saveState
            # the one thing it doesn't capture is the Toolbar state.
            # so we will need to add that separately if that is desired.
            settings.window.dock_manager_state = self.dock_manager.saveState().data()
        else:
            settings.window.dock_manager_state = None
        # write to disk, blocking up to 5 seconds
        settings.flush(timeout=5000)

    def _open_widgets(self) -> set[WidgetAction]:
        """Return the set of open widgets."""
        return {
            key
            for key, widget in self._dock_widgets.items()
            if (action := widget.toggleViewAction()) and action.isChecked()
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

            action = self.get_action(key)
            dock = CDockWidget(key.value, self)
            dock.setWidget(widget)
            dock.setObjectName(f"docked_{key.name}")
            dock.setToggleViewAction(action)
            dock.setIcon(action.icon())
            self._dock_widgets[key] = dock
            if (area := key.dock_area()) is None:
                self.dock_manager.addDockWidgetFloating(dock)
            elif isinstance(area, SideBarLocation):
                self.dock_manager.addAutoHideDockWidget(area, dock)
            else:
                self.dock_manager.addDockWidget(area, dock)

            # Set the action checked since the widget is now “open.”
            action.setChecked(True)

        return self._action_widgets[key]

    def get_dock_widget(self, key: WidgetAction) -> CDockWidget:
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

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 and (data := a0.mimeData()) and data.hasUrls():
            a0.acceptProposedAction()

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0 and (data := a0.mimeData()):
            for url in data.urls():
                local_path = Path(url.toLocalFile())
                if local_path.suffix in {".tif", ".tiff"}:
                    ary = tifffile.imread(local_path)
                    viewer = ndv.ArrayViewer(ary)

                    dw = CDockWidget(f"{local_path.name[:40]}")
                    dw.setWidget(viewer.widget())
                    dw._viewer = viewer  # pyright: ignore
                    self.dock_manager.addDockWidgetTabToArea(
                        dw, self._central_dock_area
                    )

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

    def _on_viewer_created(
        self, ndv_viewer: ndv.ArrayViewer, sequence: MDASequence
    ) -> None:
        q_viewer = cast("QWidget", ndv_viewer.widget())

        sha = str(sequence.uid)[:8]
        q_viewer.setObjectName(f"ndv-{sha}")
        q_viewer.setWindowTitle(f"MDA {sha}")
        q_viewer.setWindowFlags(Qt.WindowType.Dialog)

        dw = CDockWidget(f"ndv-{sha}")
        dw._viewer = ndv_viewer  # pyright: ignore
        dw.setWidget(q_viewer)
        self.dock_manager.addDockWidgetTabToArea(dw, self._central_dock_area)

    def _on_exception(self, exc: BaseException) -> None:
        """Show a notification when an exception is raised."""
        see_tb = "See traceback"

        def _open_traceback(choice: str | None) -> None:
            if choice == see_tb:
                log = self.get_widget(WidgetAction.EXCEPTION_LOG)
                log.show_exception(exc)
                log.show()

        self._notification_manager.show_error_message(
            str(exc), see_tb, on_action=_open_traceback
        )
