from __future__ import annotations

from typing import ClassVar

from pymmcore_plus import CMMCorePlus
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import NavigationBar  # type: ignore[attr-defined]
from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtGui import QAction, QIcon
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QToolButton,
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

        # ---- toggle action icons ----
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

        # ---- ghost toggle buttons ----
        self._left_sb_btn = self._make_ghost_button(wb.toggleLeftSidebarAction)
        self._panel_btn = self._make_ghost_button(wb.togglePanelAction)
        self._right_sb_btn = self._make_ghost_button(wb.toggleRightSidebarAction)

        # ---- panel alignment cycle button ----
        self._panel_align_btn = QToolButton()
        self._panel_align_btn.setAutoRaise(True)
        self._panel_align_btn.setToolTip("Panel Alignment")
        self._panel_align_btn.clicked.connect(self._cycle_panel_alignment)
        self._update_panel_align_icon()

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addWidget(self._navigation)
        top_row.addStretch()
        top_row.addWidget(self._panel_align_btn)
        top_row.addWidget(self._left_sb_btn)
        top_row.addWidget(self._panel_btn)
        top_row.addWidget(self._right_sb_btn)

        # ---- central layout ----
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

    @staticmethod
    def _make_ghost_button(action: QAction) -> QToolButton:
        btn = QToolButton()
        btn.setDefaultAction(action)
        btn.setAutoRaise(True)
        return btn

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(self._navigation.currentIndex())

    # ---- panel alignment --------------------------------------------------

    _PANEL_ALIGN_CYCLE = (
        PanelAlignment.LEFT,
        PanelAlignment.CENTER,
        PanelAlignment.RIGHT,
        PanelAlignment.JUSTIFY,
    )
    _PANEL_ALIGN_ICONS: ClassVar[dict[PanelAlignment, str]] = {
        PanelAlignment.LEFT: "codicon:layout-panel-left",
        PanelAlignment.CENTER: "codicon:layout-panel-center",
        PanelAlignment.RIGHT: "codicon:layout-panel-right",
        PanelAlignment.JUSTIFY: "codicon:layout-panel-justify",
    }

    def _cycle_panel_alignment(self) -> None:
        cycle = self._PANEL_ALIGN_CYCLE
        current = self._acquire_mode.panelAlignment
        idx = cycle.index(current) if current in cycle else -1
        next_align = cycle[(idx + 1) % len(cycle)]
        self._acquire_mode.setPanelAlignment(next_align)
        self._update_panel_align_icon()

    def _update_panel_align_icon(self) -> None:
        align = self._acquire_mode.panelAlignment
        icon_key = self._PANEL_ALIGN_ICONS.get(align, "codicon:layout-panel-center")
        self._panel_align_btn.setIcon(QIconifyIcon(icon_key))
        self._panel_align_btn.setToolTip(f"Panel Alignment: {align.value.capitalize()}")
