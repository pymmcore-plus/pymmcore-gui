from __future__ import annotations

from enum import Enum

from pymmcore_plus import CMMCorePlus
from superqt import QIconifyIcon

from pymmcore_gui._qt.Qlementine import NavigationBar
from pymmcore_gui._qt.QtCore import QPoint, Qt, Signal
from pymmcore_gui._qt.QtGui import QAction, QActionGroup, QIcon
from pymmcore_gui._qt.QtOpenGLWidgets import QOpenGLWidget
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._main_window import ICON

DEFAULT_SIDEBAR_WIDTH = 240
DEFAULT_PANEL_HEIGHT = 200
MIN_SIDEBAR_WIDTH = 170
MIN_PANEL_HEIGHT = 100


def _splitter_size(widget: QWidget) -> int:
    """Return the size allocated to *widget* by its parent QSplitter.

    Returns -1 if the widget is not inside a QSplitter.
    Unlike widget.width()/height(), this reflects the splitter's
    internal state immediately during splitterMoved signals.
    """
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return -1
    idx = parent.indexOf(widget)
    if idx < 0:
        return -1
    return parent.sizes()[idx]


def _ensure_splitter_size(widget: QWidget, size: int) -> None:
    """If widget is collapsed in a QSplitter, restore it to *size*."""
    parent = widget.parent()
    if not isinstance(parent, QSplitter):
        return
    idx = parent.indexOf(widget)
    if idx < 0:
        return
    sizes = parent.sizes()
    if sizes[idx] == 0:
        sizes[idx] = size
        parent.setSizes(sizes)


class PanelAlignment(Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    JUSTIFY = "justify"


class ActivityBarPosition(Enum):
    DEFAULT = "default"
    TOP = "top"
    BOTTOM = "bottom"
    HIDDEN = "hidden"


# ---- Activity Bar --------------------------------------------------------


class ActivityBar(QWidget):
    """Vertical icon strip that toggles sidebar panels."""

    panel_toggled = Signal(str)  # panel_id or "" to collapse

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QToolButton] = {}
        self._active: str | None = None
        self.collapsible = True

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)
        self._layout.addStretch()

    def add_panel(
        self, panel_id: str, text: str, *, icon: QIcon | None = None
    ) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(text)
        if icon:
            btn.setIcon(icon)
        else:
            btn.setText(text[:2])
        btn.setCheckable(True)
        btn.setAutoExclusive(False)
        btn.setObjectName(panel_id)
        btn.clicked.connect(self._on_clicked)

        self._buttons[panel_id] = btn
        self._layout.insertWidget(self._layout.count() - 1, btn)
        return btn

    def set_active(self, panel_id: str | None) -> None:
        """Programmatically activate (or deactivate) a panel."""
        if panel_id:
            self._toggle(panel_id)
        elif self._active:
            self._toggle(self._active)

    def _on_clicked(self) -> None:
        panel_id = self.sender().objectName()
        self._toggle(panel_id)

    def _toggle(self, panel_id: str) -> None:
        if self._active == panel_id:
            if not self.collapsible:
                self._buttons[panel_id].setChecked(True)
                return
            self._buttons[panel_id].setChecked(False)
            self._active = None
            self.panel_toggled.emit("")
        else:
            if self._active and self._active in self._buttons:
                self._buttons[self._active].setChecked(False)
            self._active = panel_id
            self._buttons[panel_id].setChecked(True)
            self.panel_toggled.emit(panel_id)


# ---- Sidebar Container ---------------------------------------------------


class SidebarContainer(QWidget):
    """ActivityBar + QStackedWidget pair.

    The activity bar can be positioned relative to the sidebar:
    - side: activity bar is external (placed in outer layout by parent)
    - top/bottom: activity bar is bundled with the stack in a combined widget
    - hidden: activity bar is not shown
    """

    ab_position_changed = Signal(ActivityBarPosition)

    def __init__(
        self,
        *,
        default_ab_position: str = "side",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.activity_bar = ActivityBar(self)
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._panels: dict[str, QWidget] = {}
        self._default_ab_position = default_ab_position
        self._ab_position = ActivityBarPosition.DEFAULT

        # Both possible splitter widgets need a minimum width
        self.stack.setMinimumWidth(MIN_SIDEBAR_WIDTH)

        # Combined container for top/bottom activity bar positions
        self._combined = QWidget()
        self._combined.setMinimumWidth(MIN_SIDEBAR_WIDTH)
        self._combined_layout = QVBoxLayout(self._combined)
        self._combined_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_layout.setSpacing(0)

        # Enable context menu on activity bar and stack
        self.activity_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.activity_bar.customContextMenuRequested.connect(self._show_context_menu)
        self.stack.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stack.customContextMenuRequested.connect(self._show_context_menu_stack)

    @property
    def resolved_ab_position(self) -> str:
        """Return effective position: 'side', 'top', 'bottom', or 'hidden'."""
        if self._ab_position == ActivityBarPosition.DEFAULT:
            return self._default_ab_position
        return self._ab_position.value

    @property
    def is_ab_external(self) -> bool:
        return self.resolved_ab_position == "side"

    @property
    def splitter_widget(self) -> QWidget:
        """The widget to place into a splitter."""
        if self.resolved_ab_position in ("top", "bottom"):
            return self._combined
        return self.stack

    def set_ab_position(self, pos: ActivityBarPosition) -> None:
        self._ab_position = pos

    def arrange(self) -> None:
        """Rearrange activity bar and stack for current position."""
        pos = self.resolved_ab_position

        # Detach both from wherever they currently live
        self.activity_bar.setParent(None)
        self.stack.setParent(None)

        # Clear the combined layout
        while self._combined_layout.count():
            self._combined_layout.takeAt(0)

        # Only allow collapsing the sidebar when the activity bar
        # is on the side (external). When top/bottom/hidden, the
        # activity bar lives with the sidebar so collapsing would
        # hide the toggle buttons too.
        self.activity_bar.collapsible = pos == "side"

        if pos == "top":
            self._combined_layout.addWidget(self.activity_bar)
            self._combined_layout.addWidget(self.stack, 1)
            self.activity_bar.show()
        elif pos == "bottom":
            self._combined_layout.addWidget(self.stack, 1)
            self._combined_layout.addWidget(self.activity_bar)
            self.activity_bar.show()
        elif pos == "side":
            self.activity_bar.show()
        else:  # hidden
            self.activity_bar.hide()

    def add_panel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        self.activity_bar.add_panel(panel_id, title, icon=icon)
        self.stack.addWidget(widget)
        self._panels[panel_id] = widget

    def activate(self, panel_id: str) -> None:
        if panel_id not in self._panels:
            return
        self.stack.setCurrentWidget(self._panels[panel_id])
        widget = self.splitter_widget
        widget.show()
        _ensure_splitter_size(widget, DEFAULT_SIDEBAR_WIDTH)

    @property
    def is_collapsed(self) -> bool:
        w = self.splitter_widget
        return not w.isVisible() or _splitter_size(w) == 0

    def deselect(self) -> None:
        """Deselect the active AB button without hiding the widget.

        Used when the splitter snaps to zero — the widget stays in the
        splitter (so drag-to-restore works) but the state updates.
        """
        if self.activity_bar._active:
            btn = self.activity_bar._buttons.get(self.activity_bar._active)
            if btn:
                btn.setChecked(False)
            self.activity_bar._active = None

    def collapse(self) -> None:
        """Fully hide the sidebar (programmatic toggle)."""
        self.splitter_widget.hide()
        self.deselect()

    # ---- context menu -----------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self.activity_bar.mapToGlobal(pos))

    def _show_context_menu_stack(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self.stack.mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self.activity_bar)

        # Activity Bar Position submenu
        ab_menu = menu.addMenu("Activity Bar Position")
        group = QActionGroup(ab_menu)
        group.setExclusive(True)

        for pos in ActivityBarPosition:
            action = QAction(pos.value.capitalize(), ab_menu)
            action.setCheckable(True)
            action.setChecked(self._ab_position == pos)
            action.setData(pos)
            action.triggered.connect(self._on_ab_position_action)
            group.addAction(action)
            ab_menu.addAction(action)

        return menu

    def _on_ab_position_action(self) -> None:
        action: QAction = self.sender()  # type: ignore[assignment]
        pos: ActivityBarPosition = action.data()
        if pos != self._ab_position:
            self._ab_position = pos
            self.ab_position_changed.emit(pos)


# ---- Bottom Panel ---------------------------------------------------------


class BottomPanel(QTabWidget):
    """Tabbed panel (terminal / output / problems)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabPosition(QTabWidget.TabPosition.North)
        self.setMovable(True)
        self.setMinimumHeight(MIN_PANEL_HEIGHT)


# ---- Status Bar -----------------------------------------------------------


class StatusBar(QStatusBar):
    """Status bar with a notification bell."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bell_button = QPushButton(QIconifyIcon("codicon:bell"), "")
        self.bell_button.setFlat(True)
        self.addPermanentWidget(self.bell_button)


# ---- Mode Widgets ---------------------------------------------------------


def _make_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size: 18px; color: gray;")
    return lbl


class ConfigureModeWidget(QWidget):
    """Placeholder for the Configure mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_make_label("Configure Mode"))


class AcquireModeWidget(QWidget):
    """VS Code-style workbench layout for the Acquire mode."""

    visibility_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel_alignment = PanelAlignment.CENTER
        self._root_splitter: QSplitter | None = None

        # Saved part sizes (survive alignment rebuilds)
        self._left_sb_width = DEFAULT_SIDEBAR_WIDTH
        self._right_sb_width = DEFAULT_SIDEBAR_WIDTH
        self._panel_height = DEFAULT_PANEL_HEIGHT

        # Sidebar lookup for sender()-based signal handling
        self._sidebar_for_bar: dict[int, SidebarContainer] = {}

        # ---- leaf widgets (never destroyed) ----
        self._left_sidebar = SidebarContainer(default_ab_position="side")
        self._right_sidebar = SidebarContainer(default_ab_position="top")
        self._editor_tabs = QTabWidget()
        self._editor_tabs.setTabsClosable(True)
        self._editor_tabs.setMovable(True)
        self._bottom_panel = BottomPanel()

        # ---- layout ----
        self._outer_layout = QHBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        self._splitter_container = QWidget()
        self._splitter_layout = QVBoxLayout(self._splitter_container)
        self._splitter_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter_layout.setSpacing(0)

        # ---- wire sidebar signals ----
        for sb in (self._left_sidebar, self._right_sidebar):
            self._sidebar_for_bar[id(sb.activity_bar)] = sb
            sb.activity_bar.panel_toggled.connect(self._on_sidebar_toggled)
            sb.ab_position_changed.connect(self._on_ab_position_changed)

        # ---- placeholder content ----
        self._left_sidebar.add_panel(
            "explorer",
            "Explorer",
            _make_label("Primary Side Bar\n(Explorer)"),
        )
        self._left_sidebar.activity_bar.set_active("explorer")

        self._right_sidebar.add_panel(
            "properties",
            "Properties",
            _make_label("Secondary Side Bar\n(Properties)"),
        )
        self._right_sidebar.activity_bar.set_active("properties")

        self._editor_tabs.addTab(_make_label("Editor Area"), "Tab 1")
        self._bottom_panel.addTab(_make_label("Panel\n(Terminal / Output)"), "Terminal")

        # ---- build initial splitter tree ----
        self._rebuild_layout()

    # ---- public API -------------------------------------------------------

    @property
    def panel_alignment(self) -> PanelAlignment:
        return self._panel_alignment

    def set_panel_alignment(self, alignment: PanelAlignment) -> None:
        if alignment == self._panel_alignment:
            return
        self._panel_alignment = alignment
        self._rebuild_layout()

    # ---- layout rebuild ---------------------------------------------------

    def _rebuild_layout(self) -> None:
        self.setUpdatesEnabled(False)

        # Save sizes from current splitters
        if self._root_splitter is not None:
            self._save_sizes()
            # Detach leaf widgets so they survive splitter deletion
            for sb in (self._left_sidebar, self._right_sidebar):
                sb.splitter_widget.setParent(None)
                sb.activity_bar.setParent(None)
            self._editor_tabs.setParent(None)
            self._bottom_panel.setParent(None)
            self._root_splitter.setParent(None)
            self._root_splitter.deleteLater()

        # Clear outer layout
        while self._outer_layout.count():
            self._outer_layout.takeAt(0)

        # Arrange sidebars (reparents activity bar + stack internally)
        self._left_sidebar.arrange()
        self._right_sidebar.arrange()

        # Rebuild outer: [ext_ab_L?] [splitter_container] [ext_ab_R?]
        if self._left_sidebar.is_ab_external:
            self._outer_layout.addWidget(self._left_sidebar.activity_bar)
        self._outer_layout.addWidget(self._splitter_container, 1)
        if self._right_sidebar.is_ab_external:
            self._outer_layout.addWidget(self._right_sidebar.activity_bar)

        # Build splitter tree
        root = self._build_splitter_tree()
        self._root_splitter = root
        self._splitter_layout.addWidget(root)

        # Mark sidebar/panel widgets as collapsible and connect signals
        collapsible_widgets = {
            self._left_sidebar.splitter_widget,
            self._right_sidebar.splitter_widget,
            self._bottom_panel,
        }
        self._configure_splitters(root, collapsible_widgets)

        self._restore_sizes()
        self.setUpdatesEnabled(True)

    def _build_splitter_tree(self) -> QSplitter:
        V = Qt.Orientation.Vertical
        H = Qt.Orientation.Horizontal
        left = self._left_sidebar.splitter_widget
        right = self._right_sidebar.splitter_widget
        editor = self._editor_tabs
        panel = self._bottom_panel
        align = self._panel_alignment

        if align == PanelAlignment.CENTER:
            v = QSplitter(V)
            v.addWidget(editor)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(left)
            root.addWidget(v)
            root.addWidget(right)

        elif align == PanelAlignment.JUSTIFY:
            h = QSplitter(H)
            h.addWidget(left)
            h.addWidget(editor)
            h.addWidget(right)
            root = QSplitter(V)
            root.addWidget(h)
            root.addWidget(panel)

        elif align == PanelAlignment.LEFT:
            inner_h = QSplitter(H)
            inner_h.addWidget(left)
            inner_h.addWidget(editor)
            v = QSplitter(V)
            v.addWidget(inner_h)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(v)
            root.addWidget(right)

        else:  # PanelAlignment.RIGHT
            inner_h = QSplitter(H)
            inner_h.addWidget(editor)
            inner_h.addWidget(right)
            v = QSplitter(V)
            v.addWidget(inner_h)
            v.addWidget(panel)
            root = QSplitter(H)
            root.addWidget(left)
            root.addWidget(v)

        return root

    def _configure_splitters(
        self, splitter: QSplitter, collapsible: set[QWidget]
    ) -> None:
        """Mark collapsible widgets and connect signals, recursively."""
        for i in range(splitter.count()):
            w = splitter.widget(i)
            splitter.setCollapsible(i, w in collapsible)
            if isinstance(w, QSplitter):
                self._configure_splitters(w, collapsible)
        splitter.splitterMoved.connect(self._on_splitter_moved)

    def _on_splitter_moved(self) -> None:
        for sb in (self._left_sidebar, self._right_sidebar):
            w = sb.splitter_widget
            if not w.isVisible():
                continue  # programmatically hidden, ignore
            size = _splitter_size(w)
            if size == 0 and sb.activity_bar._active is not None:
                # Splitter collapsed it — deselect but keep in splitter
                # so drag-to-restore works.
                sb.deselect()
            elif size > 0 and sb.activity_bar._active is None:
                # Dragged back from zero — re-activate first panel
                first = next(iter(sb._panels), None)
                if first:
                    sb.activity_bar._active = first
                    sb.activity_bar._buttons[first].setChecked(True)
                    sb.stack.setCurrentWidget(sb._panels[first])
        self.visibility_changed.emit()

    # ---- size persistence across rebuilds ---------------------------------

    def _save_sizes(self) -> None:
        left = self._left_sidebar.splitter_widget
        right = self._right_sidebar.splitter_widget
        panel = self._bottom_panel

        if left.isVisible() and left.width() > 0:
            self._left_sb_width = left.width()
        if right.isVisible() and right.width() > 0:
            self._right_sb_width = right.width()
        if panel.isVisible() and panel.height() > 0:
            self._panel_height = panel.height()

    def _restore_sizes(self) -> None:
        root = self._root_splitter
        if root is None:
            return

        total_w = self._splitter_container.width() or 1200
        total_h = self._splitter_container.height() or 800
        lw = self._left_sb_width
        rw = self._right_sb_width
        ph = self._panel_height
        align = self._panel_alignment

        if align == PanelAlignment.CENTER:
            v = root.widget(1)
            root.setSizes([lw, total_w - lw - rw, rw])
            v.setSizes([total_h - ph, ph])
        elif align == PanelAlignment.JUSTIFY:
            h = root.widget(0)
            root.setSizes([total_h - ph, ph])
            h.setSizes([lw, total_w - lw - rw, rw])
        elif align == PanelAlignment.LEFT:
            v = root.widget(0)
            inner_h = v.widget(0)
            root.setSizes([total_w - rw, rw])
            v.setSizes([total_h - ph, ph])
            inner_h.setSizes([lw, total_w - rw - lw])
        elif align == PanelAlignment.RIGHT:
            v = root.widget(1)
            inner_h = v.widget(0)
            root.setSizes([lw, total_w - lw])
            v.setSizes([total_h - ph, ph])
            inner_h.setSizes([total_w - lw - rw, rw])

    # ---- sidebar toggling -------------------------------------------------

    def _on_sidebar_toggled(self, panel_id: str) -> None:
        sidebar = self._sidebar_for_bar[id(self.sender())]
        if panel_id:
            sidebar.activate(panel_id)
        else:
            sidebar.collapse()
        self.visibility_changed.emit()

    def _on_ab_position_changed(self) -> None:
        self._rebuild_layout()


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
        self._acquire_mode = AcquireModeWidget()

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
        self._navigation.currentIndexChanged.connect(self._on_mode_changed)

        # ---- layout toggle buttons ----
        self._left_sb_btn = QToolButton()
        self._left_sb_btn.setCheckable(True)
        self._left_sb_btn.setChecked(True)
        self._left_sb_btn.setToolTip("Toggle Primary Side Bar")
        self._left_sb_btn.clicked.connect(self._toggle_left_sidebar)

        self._panel_btn = QToolButton()
        self._panel_btn.setCheckable(True)
        self._panel_btn.setChecked(True)
        self._panel_btn.setToolTip("Toggle Panel")
        self._panel_btn.clicked.connect(self._toggle_panel)

        self._right_sb_btn = QToolButton()
        self._right_sb_btn.setCheckable(True)
        self._right_sb_btn.setChecked(True)
        self._right_sb_btn.setToolTip("Toggle Secondary Side Bar")
        self._right_sb_btn.clicked.connect(self._toggle_right_sidebar)

        self._update_layout_icons()

        # Sync toggle buttons when any part visibility changes
        self._acquire_mode.visibility_changed.connect(self._sync_toggle_buttons)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)
        top_row.addWidget(self._navigation)
        top_row.addStretch()
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

        # Pre-init OpenGL surface to avoid flash when adding
        # QOpenGLWidget-based viewers later.
        _gl = QOpenGLWidget(self)
        _gl.setFixedSize(0, 0)
        _gl.close()

        self.resize(1200, 800)

    # ---- public API -------------------------------------------------------

    @property
    def mmcore(self) -> CMMCorePlus:
        return self._mmc

    @property
    def acquire_mode(self) -> AcquireModeWidget:
        return self._acquire_mode

    @property
    def configure_mode(self) -> ConfigureModeWidget:
        return self._configure_mode

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(self._navigation.currentIndex())

    # ---- layout toggle buttons --------------------------------------------

    def _update_layout_icons(self) -> None:
        left_on = self._left_sb_btn.isChecked()
        panel_on = self._panel_btn.isChecked()
        right_on = self._right_sb_btn.isChecked()

        self._left_sb_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-sidebar-left"
                if left_on
                else "codicon:layout-sidebar-left-off"
            )
        )
        self._panel_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-panel" if panel_on else "codicon:layout-panel-off"
            )
        )
        self._right_sb_btn.setIcon(
            QIconifyIcon(
                "codicon:layout-sidebar-right"
                if right_on
                else "codicon:layout-sidebar-right-off"
            )
        )

    def _toggle_left_sidebar(self) -> None:
        acq = self._acquire_mode
        if self._left_sb_btn.isChecked():
            ab = acq._left_sidebar.activity_bar
            if ab._active:
                acq._left_sidebar.activate(ab._active)
            else:
                ab.set_active(next(iter(ab._buttons), None))
        else:
            acq._left_sidebar.collapse()
        self._update_layout_icons()

    def _toggle_panel(self) -> None:
        panel = self._acquire_mode._bottom_panel
        if self._panel_btn.isChecked():
            panel.show()
            _ensure_splitter_size(panel, DEFAULT_PANEL_HEIGHT)
        else:
            panel.hide()
        self._update_layout_icons()

    def _toggle_right_sidebar(self) -> None:
        acq = self._acquire_mode
        if self._right_sb_btn.isChecked():
            ab = acq._right_sidebar.activity_bar
            if ab._active:
                acq._right_sidebar.activate(ab._active)
            else:
                ab.set_active(next(iter(ab._buttons), None))
        else:
            acq._right_sidebar.collapse()
        self._update_layout_icons()

    def _sync_toggle_buttons(self) -> None:
        acq = self._acquire_mode
        self._left_sb_btn.setChecked(not acq._left_sidebar.is_collapsed)
        self._right_sb_btn.setChecked(not acq._right_sidebar.is_collapsed)
        self._panel_btn.setChecked(
            acq._bottom_panel.isVisible() and _splitter_size(acq._bottom_panel) != 0
        )
        self._update_layout_icons()
