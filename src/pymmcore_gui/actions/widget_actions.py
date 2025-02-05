"""Defines actions that toggle/create singleton widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar, cast

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from pymmcore_gui.actions._action_info import ActionKey

from ._action_info import ActionInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    import pymmcore_widgets as pmmw
    from PyQt6.QtCore import QObject
    from PyQt6.QtWidgets import QWidget

    from pymmcore_gui._main_window import MicroManagerGUI
    from pymmcore_gui.widgets._exception_log import ExceptionLog
    from pymmcore_gui.widgets._mm_console import MMConsole
    from pymmcore_gui.widgets._stage_control import StagesControlWidget


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


def create_about_widget(parent: QWidget) -> QWidget:
    """Create an "about this program" widget."""
    from pymmcore_gui.widgets._about_widget import AboutWidget

    return AboutWidget(parent=parent)


def create_mm_console(parent: QWidget) -> MMConsole:
    """Create a console widget."""
    from pymmcore_gui.widgets._mm_console import MMConsole

    return MMConsole(parent=parent)


def create_install_widgets(parent: QWidget) -> pmmw.InstallWidget:
    """Create the Install Devices widget."""
    from pymmcore_widgets import InstallWidget

    wdg = InstallWidget(parent=parent)
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


class WidgetAction(ActionKey):
    """Widget Actions toggle/create singleton widgets."""

    ABOUT = "About Pymmcore Gui"
    PROP_BROWSER = "Property Browser"
    PIXEL_CONFIG = "Pixel Configuration"
    INSTALL_DEVICES = "Install Devices"
    MDA_WIDGET = "MDA Widget"
    CONFIG_GROUPS = "Configs and Preset"
    CAMERA_ROI = "Camera ROI"
    CONSOLE = "Console"
    EXCEPTION_LOG = "Exception Log"
    STAGE_CONTROL = "Stage Control"
    CONFIG_WIZARD = "Hardware Config Wizard"

    def create_widget(self, parent: QWidget) -> QWidget:
        """Create the widget associated with this action."""
        info: WidgetActionInfo[QWidget] = WidgetActionInfo.for_key(self)
        if not info.create_widget:
            raise NotImplementedError(f"No constructor has been provided for {self!r}")
        return info.create_widget(parent)

    def dock_area(self) -> Qt.DockWidgetArea | None:
        """Return the default dock area for this widget."""
        return WidgetActionInfo.for_key(self).dock_area


# ######################## WidgetActionInfos #########################

WT = TypeVar("WT", bound="QWidget")


@dataclass
class WidgetActionInfo(ActionInfo, Generic[WT]):
    """Subclass to set default values for WidgetAction."""

    # by default, widget actions are checkable, and the check state indicates visibility
    checkable: bool = True
    # function that can be called with (parent: QWidget) -> QWidget
    create_widget: Callable[[QWidget], WT] | None = None
    # Use None to indicate that the widget should not be docked
    dock_area: Qt.DockWidgetArea | None = Qt.DockWidgetArea.RightDockWidgetArea


show_about = WidgetActionInfo(
    key=WidgetAction.ABOUT,
    create_widget=create_about_widget,
    dock_area=None,
    menu_role=QAction.MenuRole.AboutRole,
)

show_console = WidgetActionInfo(
    key=WidgetAction.CONSOLE,
    shortcut="Ctrl+Shift+C",
    icon="iconoir:terminal",
    create_widget=create_mm_console,
    dock_area=Qt.DockWidgetArea.BottomDockWidgetArea,
)

show_property_browser = WidgetActionInfo(
    key=WidgetAction.PROP_BROWSER,
    shortcut="Ctrl+Shift+P",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_property_browser,
    dock_area=None,
)

show_install_devices = WidgetActionInfo(
    key=WidgetAction.INSTALL_DEVICES,
    shortcut="Ctrl+Shift+I",
    icon="mdi-light:download",
    create_widget=create_install_widgets,
    dock_area=None,
)

show_mda_widget = WidgetActionInfo(
    key=WidgetAction.MDA_WIDGET,
    shortcut="Ctrl+Shift+M",
    icon="qlementine-icons:cube-16",
    create_widget=create_mda_widget,
)

show_camera_roi = WidgetActionInfo(
    key=WidgetAction.CAMERA_ROI,
    shortcut="Ctrl+Shift+R",
    icon="material-symbols-light:screenshot-region-rounded",
    create_widget=create_camera_roi,
    dock_area=Qt.DockWidgetArea.LeftDockWidgetArea,
)

show_config_groups = WidgetActionInfo(
    key=WidgetAction.CONFIG_GROUPS,
    shortcut="Ctrl+Shift+G",
    icon="mdi-light:format-list-bulleted",
    create_widget=create_config_groups,
    dock_area=Qt.DockWidgetArea.LeftDockWidgetArea,
)

show_pixel_config = WidgetActionInfo(
    key=WidgetAction.PIXEL_CONFIG,
    shortcut="Ctrl+Shift+X",
    icon="mdi-light:grid",
    create_widget=create_pixel_config,
)

show_exception_log = WidgetActionInfo(
    key=WidgetAction.EXCEPTION_LOG,
    shortcut="Ctrl+Shift+E",
    icon="mdi-light:alert",
    create_widget=create_exception_log,
    dock_area=None,
)

show_stage_control = WidgetActionInfo(
    key=WidgetAction.STAGE_CONTROL,
    shortcut="Ctrl+Shift+S",
    icon="fa:arrows",
    create_widget=create_stage_widget,
    dock_area=Qt.DockWidgetArea.LeftDockWidgetArea,
)

show_config_wizard = WidgetActionInfo(
    key=WidgetAction.CONFIG_WIZARD,
    icon="mdi:cog",
    create_widget=create_config_wizard,
    dock_area=None,
)
