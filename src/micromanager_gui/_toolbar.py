from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fonticon_mdi6 import MDI6
from pymmcore_widgets import MDAWidget, PropertyBrowser
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QDockWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QWidget,
)
from superqt.fonticon import icon

from ._widgets._camera_roi import _CameraRoiWidget
from ._widgets._group_and_preset import _GroupsAndPresets
from ._widgets._pixel_configurations import _PixelConfigurationWidget
from ._widgets._shutters_toolbar import _ShuttersToolbar
from ._widgets._snap_and_live import Live, Snap
from ._widgets._stage_control import _StagesControlWidget

if TYPE_CHECKING:
    from ._main_window import MicroManagerGUI


BTN_SIZE = (60, 40)
ALLOWED_AREAS = (
    Qt.DockWidgetArea.LeftDockWidgetArea
    | Qt.DockWidgetArea.RightDockWidgetArea
    # | Qt.DockWidgetArea.BottomDockWidgetArea
)


# fmt: off
# key: (widget, window name, icon)
WIDGETS: dict[str, tuple[type[QWidget], str, str | None]] = {
    "Shutters": (_ShuttersToolbar, "Shutters Control", MDI6.hexagon_slice_6),
    "Camera ROI": (_CameraRoiWidget, "Camera ROI", MDI6.crop),
    "Property Browser": (PropertyBrowser, "Device Property Browser", MDI6.table_large),
    "Group Presets": (_GroupsAndPresets, "Group & Presets Table", MDI6.table_large_plus),  # noqa: E501
    "Stages": (_StagesControlWidget, "Stages Control", MDI6.arrow_all),
    "Pixel": (_PixelConfigurationWidget, "Pixel Configuration Table", None),
    "MDA": (MDAWidget, "Multi-Dimensional Acquisition", None),
}
# fmt: on


class ScrollableDockWidget(QDockWidget):
    """A QDockWidget with a QScrollArea."""

    def __init__(self, title: str, parent: QWidget | None = None, *, widget: QWidget):
        super().__init__(title, parent)
        # set allowed dock areas
        self.setAllowedAreas(ALLOWED_AREAS)

        # create the scroll area and set it as the widget of the QDockwidget
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        super().setWidget(self.scroll_area)

        # set the widget to the scroll area
        self.scroll_area.setWidget(widget)
        # resize the dock widget to the size hint of the widget
        self.resize(widget.minimumSizeHint())


class MainToolBar(QToolBar):
    """A QToolBar containing QPushButtons for pymmcore-widgets."""

    def __init__(self, parent: MicroManagerGUI) -> None:
        super().__init__(parent)

        self._main_window = parent

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        # snap and live toolbar
        self._snap_live_toolbar = QToolBar("Snap/Live Toolbar", self)
        self._snap_live_toolbar.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._snap_live_toolbar
        )
        self._snap_button = Snap()
        self._live_button = Live()
        self._snap_live_toolbar.addWidget(self._snap_button)
        self._snap_live_toolbar.addWidget(self._live_button)

        # widgets toolbar
        self._widgets_toolbar = _WidgetsToolBar(
            self, main_window=self._main_window, main_toolbar=self
        )
        self._widgets_toolbar.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._widgets_toolbar
        )

        # shutters toolbar
        self._shutter_toolbar = _ShuttersToolbar(self)
        self._main_window.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._shutter_toolbar
        )

    def contextMenuEvent(self, event: Any) -> None:
        """Remove all actions from the context menu but the shutter toolbar."""
        menu = self._main_window.createPopupMenu()
        for action in menu.actions():
            if action.text() == "Shutters ToolBar":
                continue
            menu.removeAction(action)
        menu.exec_(event.globalPos())


class _WidgetsToolBar(QToolBar):
    """A QToolBar containing QPushButtons for pymmcore-widgets.

    e.g. Property Browser, MDAWidget, StagesWidget, ...

    The QPushButton.whatsThis() property is used to store the key that
    will be used by the `_show_widget` method.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        main_window: MicroManagerGUI,
        main_toolbar: MainToolBar,
    ) -> None:
        super().__init__("Widgets ToolBar", parent)

        self._main_window = main_window
        self._main_toolbar = main_toolbar

        # keep track of the created widgets
        self._widgets: dict[str, ScrollableDockWidget] = {}

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)

        for key in WIDGETS:
            _, windows_name, btn_icon = WIDGETS[key]
            btn = QPushButton()
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setToolTip(windows_name)
            btn.setWhatsThis(key)
            btn.setIcon(icon(btn_icon)) if btn_icon else btn.setText(key)
            btn.setFixedSize(*BTN_SIZE)
            btn.setIconSize(QSize(25, 25))
            if key == "Shutters":
                btn.clicked.connect(self._show_shutters_toolbar)
            else:
                btn.clicked.connect(self._show_widget)
            self.addWidget(btn)

    def _show_shutters_toolbar(self) -> None:
        """Show or raise the shutters toolbar."""
        if self._main_toolbar._shutter_toolbar is None:
            return
        if self._main_toolbar._shutter_toolbar.isVisible():
            self._main_toolbar._shutter_toolbar.hide()
        else:
            self._main_toolbar._shutter_toolbar.show()

    def _show_widget(self) -> None:
        """Show or raise a widget."""
        # using QPushButton.whatsThis() property to get the key.
        btn = cast(QPushButton, self.sender())
        key = btn.whatsThis()

        if key in self._widgets:
            # already exists
            wdg = self._widgets[key]
            wdg.show()
            wdg.raise_()
            return

        wdg = self._create_widget(key)
        wdg.show()

    def _create_widget(self, key: str) -> ScrollableDockWidget:
        """Create a widget for the first time."""
        try:
            wdg_cls = WIDGETS[key][0]
        except KeyError as e:
            raise KeyError(
                "Not a recognized widget key. "
                f"Must be one of {list(WIDGETS)} "
                " or the `whatsThis` property of a `sender` `QPushButton`."
            ) from e

        wdg = wdg_cls(parent=self, mmcore=self._main_window._mmc)

        windows_title = WIDGETS[key][1]
        dock = ScrollableDockWidget(windows_title, self, widget=wdg)
        self._main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)
        self._widgets[key] = dock

        # if the widget is an MDAWidget, connect the onRunClicked signal
        # if isinstance(wdg, _MDAWidget):
        #     wdg.onRunClicked.connect(self._on_mda_run)

        return dock
