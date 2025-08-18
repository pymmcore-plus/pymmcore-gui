"""Defines actions that toggle/create singleton widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, TypeVar, cast

from pymmcore_plus import CMMCorePlus

from pymmcore_gui._qt.QtAds import CDockWidget, DockWidgetArea, SideBarLocation
from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtGui import QAction
from pymmcore_gui._qt.QtWidgets import QDialog, QVBoxLayout, QWidget

from ._action_info import ActionKey, WidgetActionInfo, _ensure_isinstance

if TYPE_CHECKING:
    import pymmcore_widgets as pmmw

    from pymmcore_gui._main_window import MicroManagerGUI
    from pymmcore_gui._qt.QtCore import QObject
    from pymmcore_gui.widgets._exception_log import ExceptionLog
    from pymmcore_gui.widgets._mm_console import MMConsole
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

QWidgetType = Annotated[QWidget, _ensure_isinstance(QWidget)]

CT = TypeVar("CT", bound=Callable[[QWidget], QWidget])


class WidgetAction(ActionKey):
    """Widget Actions toggle/create singleton widgets."""

    ABOUT = "pymmcore_gui.about_widget"
    PROP_BROWSER = "pymmcore_gui.property_browser"
    PIXEL_CONFIG = "pymmcore_gui.pixel_config_widget"
    INSTALL_DEVICES = "pymmcore_gui.install_devices_widget"
    MDA_WIDGET = "pymmcore_gui.mda_widget"
    CONFIG_GROUPS = "pymmcore_gui.config_groups_widget"
    CAMERA_ROI = "pymmcore_gui.camera_roi_widget"
    CONSOLE = "pymmcore_gui.console"
    EXCEPTION_LOG = "pymmcore_gui.exception_log"
    STAGE_CONTROL = "pymmcore_gui.stage_control_widget"
    CONFIG_WIZARD = "pymmcore_gui.hardware_config_wizard"


# ######################## Functions that create widgets #########################


def _get_mm_main_window(obj: QObject) -> MicroManagerGUI | None:
    if obj.objectName() == "MicroManagerGUI":
        return cast("MicroManagerGUI", obj)
    parent = obj.parent()
    while parent is not None:
        if parent.objectName() == "MicroManagerGUI":
            return cast("MicroManagerGUI", parent)
        parent = parent.parent()
    return None


def _get_core(obj: QObject) -> CMMCorePlus:
    if win := _get_mm_main_window(obj):
        return win.mmcore
    return CMMCorePlus.instance()


def create_property_browser(parent: QWidget) -> pmmw.PropertyBrowser:
    """Create a Property Browser widget."""
    from pymmcore_widgets import PropertyBrowser

    return PropertyBrowser(parent=parent, mmcore=_get_core(parent))


def create_mm_console(parent: QWidget) -> MMConsole:
    """Create a console widget."""
    from pymmcore_gui.widgets._mm_console import MMConsole

    return MMConsole(parent=parent)


def create_install_widgets(parent: QWidget) -> QDialog:
    """Create the Install Devices widget."""
    from pymmcore_widgets import InstallWidget

    class InstallDialog(QDialog):
        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._install_widget = InstallWidget(parent=self)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._install_widget)

    wdg = InstallDialog(parent=parent)
    wdg.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
    wdg.resize(800, 400)
    return wdg


def create_mda_widget(parent: QWidget) -> pmmw.MDAWidget:
    """Create the MDA widget."""
    # from pymmcore_gui.widgets import _MDAWidget
    from pymmcore_widgets import MDAWidget

    return MDAWidget(parent=parent, mmcore=_get_core(parent))


def create_camera_roi(parent: QWidget) -> pmmw.CameraRoiWidget:
    """Create the Camera ROI widget."""
    from pymmcore_widgets import CameraRoiWidget

    return CameraRoiWidget(parent=parent, mmcore=_get_core(parent))


def create_config_groups(parent: QWidget) -> pmmw.GroupPresetTableWidget:
    """Create the Config Groups widget."""
    from pymmcore_widgets import GroupPresetTableWidget

    return GroupPresetTableWidget(parent=parent, mmcore=_get_core(parent))


def create_pixel_config(parent: QWidget) -> pmmw.PixelConfigurationWidget:
    """Create the Pixel Configuration widget."""
    from pymmcore_widgets import PixelConfigurationWidget

    return PixelConfigurationWidget(parent=parent, mmcore=_get_core(parent))


def create_exception_log(parent: QWidget) -> ExceptionLog:
    """Create the Exception Log widget."""
    from pymmcore_gui.widgets._exception_log import ExceptionLog

    wdg = ExceptionLog(parent=parent)
    wdg.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
    wdg.resize(800, 400)
    return wdg


def create_stage_widget(parent: QWidget) -> StagesControlWidget:
    """Create the Stage Control widget."""
    from pymmcore_gui.widgets._stage_control import StagesControlWidget

    return StagesControlWidget(parent=parent, mmcore=_get_core(parent))


def create_config_wizard(parent: QWidget) -> pmmw.ConfigWizard:
    """Create the Hardware Configuration Wizard."""
    from pymmcore_widgets import ConfigWizard

    mmcore = _get_core(parent)
    config_file = mmcore.systemConfigurationFile() or ""
    return ConfigWizard(config_file=config_file, core=mmcore, parent=parent)


# ######################## WidgetAction Enum #########################


# ######################## WidgetActionInfos #########################


def create_about_widget(parent: QWidget) -> QWidget:
    """Create an "about this program" widget."""
    from pymmcore_gui.widgets._about_widget import AboutWidget

    return AboutWidget(parent=parent)


show_about = WidgetActionInfo(
    key=WidgetAction.ABOUT,
    text="About Pymmcore Gui...",
    create_widget=create_about_widget,
    dock_area=None,
    checkable=False,
    menu_role=QAction.MenuRole.AboutRole,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_console = WidgetActionInfo(
    key=WidgetAction.CONSOLE,
    text="Console",
    shortcut="Ctrl+Shift+C",
    icon="iconoir:terminal",
    create_widget=create_mm_console,
    dock_area=DockWidgetArea.BottomDockWidgetArea,
)

show_property_browser = WidgetActionInfo(
    key=WidgetAction.PROP_BROWSER,
    text="Device Property Browser...",
    shortcut="Ctrl+Shift+P",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_property_browser,
    dock_area=SideBarLocation.SideBarLeft,
)

show_install_devices = WidgetActionInfo(
    key=WidgetAction.INSTALL_DEVICES,
    text="Install Devices...",
    shortcut="Ctrl+Shift+I",
    icon="mdi-light:download",
    create_widget=create_install_widgets,
    dock_area=None,
    checkable=False,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_mda_widget = WidgetActionInfo(
    key=WidgetAction.MDA_WIDGET,
    text="MDA",
    shortcut="Ctrl+Shift+M",
    icon="qlementine-icons:cube-16",
    create_widget=create_mda_widget,
)

show_camera_roi = WidgetActionInfo(
    key=WidgetAction.CAMERA_ROI,
    text="Camera ROI",
    shortcut="Ctrl+Shift+R",
    icon="material-symbols-light:screenshot-region-rounded",
    create_widget=create_camera_roi,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
)

show_config_groups = WidgetActionInfo(
    key=WidgetAction.CONFIG_GROUPS,
    text="Config Groups",
    shortcut="Ctrl+Shift+G",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_config_groups,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
    scroll_mode=CDockWidget.eInsertMode.ForceNoScrollArea,
)

show_pixel_config = WidgetActionInfo(
    key=WidgetAction.PIXEL_CONFIG,
    text="Pixel Size Configuration",
    shortcut="Ctrl+Shift+X",
    icon="mdi-light:grid",
    create_widget=create_pixel_config,
)

show_exception_log = WidgetActionInfo(
    key=WidgetAction.EXCEPTION_LOG,
    text="Exception Log",
    shortcut="Ctrl+Shift+E",
    icon="mdi-light:alert",
    create_widget=create_exception_log,
    dock_area=None,
)

show_stage_control = WidgetActionInfo(
    key=WidgetAction.STAGE_CONTROL,
    text="Stage Control",
    shortcut="Ctrl+Shift+S",
    icon="fa:arrows",
    create_widget=create_stage_widget,
    dock_area=DockWidgetArea.LeftDockWidgetArea,
)

show_config_wizard = WidgetActionInfo(
    key=WidgetAction.CONFIG_WIZARD,
    text="Hardware Config Wizard...",
    icon="mdi:cog",
    create_widget=create_config_wizard,
    dock_area=None,
    checkable=False,
)
