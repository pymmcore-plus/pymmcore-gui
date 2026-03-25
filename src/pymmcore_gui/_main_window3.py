from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import NavigationBar  # type: ignore[attr-defined]
from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtGui import QIcon
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ._layout import PanelAlignment, ViewContainerLocation, WorkbenchWidget
from ._main_window import ICON

# ---- Status Bar -----------------------------------------------------------


class StatusBar(QStatusBar):
    """Status bar with a notification bell."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bell_button = QPushButton(QIconifyIcon("codicon:bell"), "")
        self.bell_button.setFlat(True)
        self.addPermanentWidget(self.bell_button)


# ---- Helper ---------------------------------------------------------------


def _make_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size: 18px; color: gray;")
    return lbl


# ---- Mode Widgets ---------------------------------------------------------


class ConfigureModeWidget(QWidget):
    """Placeholder for the Configure mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_make_label("Configure Mode"))


# ---- Main Window ----------------------------------------------------------


class MicroManagerGUI(QMainWindow):
    def __init__(self, *, mmcore: CMMCorePlus | None = None) -> None:
        super().__init__()
        self.setWindowTitle("pyMM")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setObjectName("MicroManagerGUI")

        self._mmc = mmcore or CMMCorePlus.instance()

        # ---- mode widgets ----
        self._configure_mode = ConfigureModeWidget()
        self._acquire_mode = WorkbenchWidget(central=_make_label("Editor Area"))

        # Populate workbench with placeholder content
        wb = self._acquire_mode
        L = ViewContainerLocation
        wb.addView(
            "explorer",
            "Explorer",
            _make_label("Primary Side Bar"),
            L.LEFT_SIDEBAR,
        )
        wb.leftSidebar.activityBar.setActive("explorer")
        wb.addView(
            "properties",
            "Properties",
            _make_label("Secondary Side Bar"),
            L.RIGHT_SIDEBAR,
        )
        wb.rightSidebar.activityBar.setActive("properties")
        wb.addView(
            "terminal",
            "Terminal",
            _make_label("Panel"),
            L.PANEL,
        )
        wb.bottomPanel.activityBar.setActive("terminal")

        # ---- set icons on workbench actions ----
        wb.setActionIcons(
            wb.toggleLeftSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-left"),
            QIconifyIcon("codicon:layout-sidebar-left-off"),
        )
        wb.setActionIcons(
            wb.togglePanelAction,
            QIconifyIcon("codicon:layout-panel"),
            QIconifyIcon("codicon:layout-panel-off"),
        )
        wb.setActionIcons(
            wb.toggleRightSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-right"),
            QIconifyIcon("codicon:layout-sidebar-right-off"),
        )
        wb.setAlignmentIcons(
            {
                PanelAlignment.LEFT: QIconifyIcon("codicon:layout-panel-left"),
                PanelAlignment.CENTER: QIconifyIcon("codicon:layout-panel-center"),
                PanelAlignment.RIGHT: QIconifyIcon("codicon:layout-panel-right"),
                PanelAlignment.JUSTIFY: QIconifyIcon("codicon:layout-panel-justify"),
            }
        )

        # ---- mode stack ----
        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(self._configure_mode)
        self._mode_stack.addWidget(self._acquire_mode)

        # ---- navigation bar (mode switcher) ----
        self._navigation = NavigationBar()
        self._navigation.setItemsShouldExpand(False)
        self._navigation.addItem("Configure")
        self._navigation.addItem("Acquire")
        self._navigation.setCurrentIndex(1)  # start on Acquire
        self._mode_stack.setCurrentIndex(1)
        self._navigation.currentIndexChanged.connect(self._on_mode_changed)  # pyright: ignore[reportAttributeAccessIssue]

        # ---- layout ----
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addWidget(self._navigation)
        top_row.addStretch()
        top_row.addWidget(wb.stateButtons())

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top_row)
        layout.addWidget(self._mode_stack, 1)
        self.setCentralWidget(central)

        # ---- status bar ----
        self._status_bar = StatusBar(self)
        self.setStatusBar(self._status_bar)

        self.resize(1200, 800)

    # ---- public API -------------------------------------------------------

    @property
    def mmcore(self) -> CMMCorePlus:
        return self._mmc

    @property
    def acquire_mode(self) -> WorkbenchWidget:
        return self._acquire_mode

    @property
    def configure_mode(self) -> ConfigureModeWidget:
        return self._configure_mode

    # ---- internals --------------------------------------------------------

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(self._navigation.currentIndex())
