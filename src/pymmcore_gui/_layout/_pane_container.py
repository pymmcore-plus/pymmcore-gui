from __future__ import annotations

from pymmcore_gui._qt.QtCore import QPoint, Qt, Signal
from pymmcore_gui._qt.QtGui import QAction, QActionGroup, QIcon
from pymmcore_gui._qt.QtWidgets import (
    QMenu,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ._activity_bar import ActivityBar
from ._enums import ActivityBarPosition
from ._navigation_bar import NavigationBarAdapter
from ._splitter_utils import (
    DEFAULT_SIDEBAR_WIDTH,
    MIN_SIDEBAR_WIDTH,
    ensure_splitter_size,
    splitter_size,
)


class PaneContainer(QWidget):
    """Unified container: ActivityBar + QStackedWidget."""

    panelToggled = Signal(str)  # forwarded from activityBar
    abPositionChanged = Signal(ActivityBarPosition)

    def __init__(
        self,
        *,
        default_ab_position: str = "side",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._panels: dict[str, QWidget] = {}
        self._default_ab_position = default_ab_position
        self._ab_position = ActivityBarPosition.DEFAULT

        self._stack.setMinimumWidth(MIN_SIDEBAR_WIDTH)

        # Combined container for top/bottom activity bar positions
        self._combined = QWidget()
        self._combined.setMinimumWidth(MIN_SIDEBAR_WIDTH)
        self._combined_layout = QVBoxLayout(self._combined)
        self._combined_layout.setContentsMargins(0, 0, 0, 0)
        self._combined_layout.setSpacing(0)

        # Create initial activity bar based on default position
        self._activity_bar: ActivityBar | NavigationBarAdapter = self._make_bar()
        self._wire_bar()

        # Enable context menu on stack
        self._stack.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._stack.customContextMenuRequested.connect(self._show_context_menu_stack)

    # ---- public API -------------------------------------------------------

    @property
    def activityBar(self) -> ActivityBar | NavigationBarAdapter:
        return self._activity_bar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def resolvedAbPosition(self) -> str:
        """Return effective position: 'side', 'top', 'bottom', or 'hidden'."""
        if self._ab_position == ActivityBarPosition.DEFAULT:
            return self._default_ab_position
        return str(self._ab_position.value)

    @property
    def isAbExternal(self) -> bool:
        return self.resolvedAbPosition == "side"

    @property
    def splitterWidget(self) -> QWidget:
        """The widget to place into a splitter."""
        if self.resolvedAbPosition in ("top", "bottom"):
            return self._combined
        return self._stack

    @property
    def isCollapsed(self) -> bool:
        w = self.splitterWidget
        return not w.isVisible() or splitter_size(w) == 0

    def setAbPosition(self, pos: ActivityBarPosition) -> None:
        self._ab_position = pos

    def arrange(self) -> None:
        """Rearrange activity bar and stack for current position."""
        pos = self.resolvedAbPosition

        # Swap bar type if needed (vertical ↔ horizontal)
        self._ensure_correct_bar_type()

        self._activity_bar.setParent(None)
        self._stack.setParent(None)

        self._activity_bar.collapsible = pos == "side"

        if pos == "top":
            self._combined_layout.addWidget(self._activity_bar)
            self._combined_layout.addWidget(self._stack, 1)
            self._activity_bar.show()
        elif pos == "bottom":
            self._combined_layout.addWidget(self._stack, 1)
            self._combined_layout.addWidget(self._activity_bar)
            self._activity_bar.show()
        elif pos == "side":
            self._activity_bar.show()
        else:  # hidden
            self._activity_bar.hide()

    def addPanel(
        self,
        panel_id: str,
        title: str,
        widget: QWidget,
        *,
        icon: QIcon | None = None,
    ) -> None:
        self._activity_bar.addPanel(panel_id, title, icon=icon)
        self._stack.addWidget(widget)
        self._panels[panel_id] = widget

    def activate(self, panel_id: str) -> None:
        """Show a specific panel by id."""
        if panel_id not in self._panels:
            return
        self._stack.setCurrentWidget(self._panels[panel_id])
        widget = self.splitterWidget
        widget.show()
        ensure_splitter_size(widget, DEFAULT_SIDEBAR_WIDTH)

    def toggle(self) -> None:
        """Toggle visibility. Show first/active panel, or collapse."""
        if self.isCollapsed:
            active = self._activity_bar.activePanel
            if active:
                self.activate(active)
            else:
                self._activity_bar.activateFirst()
        else:
            self.collapse()

    def deselect(self) -> None:
        """Deselect the active AB button without hiding the widget."""
        self._activity_bar.deselect()

    def restoreFromDrag(self) -> None:
        """Re-activate the first panel after being dragged from zero."""
        first = next(iter(self._panels), None)
        if first:
            self._activity_bar.setActiveSilent(first)
            self._stack.setCurrentWidget(self._panels[first])

    def collapse(self) -> None:
        """Fully hide the container."""
        self.splitterWidget.hide()
        self.deselect()

    # ---- bar type management ----------------------------------------------

    def _needs_horizontal(self) -> bool:
        """Whether the current position requires a horizontal bar."""
        return self.resolvedAbPosition in ("top", "bottom")

    def _is_horizontal(self) -> bool:
        return isinstance(self._activity_bar, NavigationBarAdapter)

    def _make_bar(self) -> ActivityBar | NavigationBarAdapter:
        if self._needs_horizontal():
            return NavigationBarAdapter(self)
        return ActivityBar(parent=self)

    def _wire_bar(self) -> None:
        self._activity_bar.panelToggled.connect(self.panelToggled)
        self._activity_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._activity_bar.customContextMenuRequested.connect(self._show_context_menu)

    def _ensure_correct_bar_type(self) -> None:
        """Recreate the bar widget if orientation changed."""
        need_h = self._needs_horizontal()
        if need_h == self._is_horizontal():
            return

        # Save state from old bar
        active = self._activity_bar.activePanel
        panel_ids_and_titles: list[tuple[str, str, QIcon | None]] = []
        for pid in self._activity_bar.panelIds:
            # Recover title from tooltip (ActivityBar) or nav item text
            if isinstance(self._activity_bar, ActivityBar):
                btn = self._activity_bar._buttons[pid]
                title = btn.toolTip()
                icon = btn.icon() if not btn.icon().isNull() else None
            else:
                idx = self._activity_bar._panel_ids.index(pid)
                title = self._activity_bar._nav.getItemText(idx)
                icon = self._activity_bar._nav.getItemIcon(idx)
                if icon and icon.isNull():
                    icon = None
            panel_ids_and_titles.append((pid, title, icon))

        # Destroy old bar
        self._activity_bar.setParent(None)
        self._activity_bar.deleteLater()

        # Create new bar and re-add panels
        self._activity_bar = self._make_bar()
        self._wire_bar()
        for pid, title, icon in panel_ids_and_titles:
            self._activity_bar.addPanel(pid, title, icon=icon)

        # Restore active state
        if active:
            self._activity_bar.setActiveSilent(active)

    # ---- context menu -----------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self._activity_bar.mapToGlobal(pos))

    def _show_context_menu_stack(self, pos: QPoint) -> None:
        self._build_context_menu().exec(self._stack.mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        menu = QMenu(self._activity_bar)

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
        action: QAction = self.sender()  # type: ignore[assignment,unused-ignore]
        pos: ActivityBarPosition = action.data()
        if pos != self._ab_position:
            self._ab_position = pos
            self.abPositionChanged.emit(pos)


# Backwards-compatible alias
SidebarContainer = PaneContainer
