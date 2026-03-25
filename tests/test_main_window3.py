from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pymmcore_gui._main_window3 import (
    ActivityBar,
    ActivityBarPosition,
    MicroManagerGUI,
    PanelAlignment,
    SidebarContainer,
    WorkbenchWidget,
    _splitter_size,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytestqt.qtbot import QtBot

    from pymmcore_gui._qt.QtWidgets import QLabel


# ---- Fixtures -------------------------------------------------------------


@pytest.fixture()
def activity_bar(qtbot: QtBot) -> ActivityBar:
    ab = ActivityBar()
    qtbot.addWidget(ab)
    return ab


@pytest.fixture()
def sidebar(qtbot: QtBot) -> SidebarContainer:
    sb = SidebarContainer()
    qtbot.addWidget(sb)
    sb.addPanel("alpha", "Alpha", _label())
    sb.addPanel("beta", "Beta", _label())
    return sb


@pytest.fixture()
def workbench(qtbot: QtBot) -> WorkbenchWidget:
    w = _make_workbench()
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture()
def gui(qtbot: QtBot) -> Iterator[MicroManagerGUI]:
    g = MicroManagerGUI()
    qtbot.addWidget(g)
    yield g


def _label() -> QLabel:
    from pymmcore_gui._main_window3 import _make_label

    return _make_label("test")


def _make_workbench() -> WorkbenchWidget:
    """Create a WorkbenchWidget with minimal content for testing."""
    w = WorkbenchWidget()
    w.addLeftPanel("explorer", "Explorer", _label())
    w.leftSidebar.activityBar.setActive("explorer")
    w.addRightPanel("properties", "Properties", _label())
    w.rightSidebar.activityBar.setActive("properties")
    w.addBottomTab(_label(), "Terminal")
    return w


# ---- ActivityBar tests ----------------------------------------------------


class TestActivityBar:
    def test_add_panel(self, activity_bar: ActivityBar) -> None:
        btn = activity_bar.addPanel("foo", "Foo")
        assert "foo" in activity_bar.panelIds
        assert btn.toolTip() == "Foo"
        assert btn.text() == "Fo"  # fallback: first 2 chars

    def test_set_active_emits_signal(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.addPanel("b", "B")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("a")
        assert blocker.args == ["a"]
        assert activity_bar.activePanel == "a"

    def test_toggle_deactivates_when_collapsible(
        self, activity_bar: ActivityBar, qtbot: QtBot
    ) -> None:
        activity_bar.addPanel("x", "X")
        activity_bar.setActive("x")
        assert activity_bar.activePanel == "x"

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("x")  # toggle off
        assert blocker.args == [""]
        assert activity_bar.activePanel is None

    def test_toggle_blocked_when_not_collapsible(
        self, activity_bar: ActivityBar
    ) -> None:
        activity_bar.addPanel("x", "X")
        activity_bar.collapsible = False
        activity_bar.setActive("x")

        activity_bar.setActive("x")  # should NOT toggle off
        assert activity_bar.activePanel == "x"

    def test_deselect(self, activity_bar: ActivityBar) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.setActive("a")
        assert activity_bar.activePanel == "a"

        activity_bar.deselect()
        assert activity_bar.activePanel is None

    def test_activate_first(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.addPanel("first", "First")
        activity_bar.addPanel("second", "Second")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.activateFirst()
        assert blocker.args == ["first"]
        assert activity_bar.activePanel == "first"

    def test_switching_panels(self, activity_bar: ActivityBar, qtbot: QtBot) -> None:
        activity_bar.addPanel("a", "A")
        activity_bar.addPanel("b", "B")
        activity_bar.setActive("a")

        with qtbot.waitSignal(activity_bar.panelToggled) as blocker:
            activity_bar.setActive("b")
        assert blocker.args == ["b"]
        assert activity_bar.activePanel == "b"


# ---- SidebarContainer tests ----------------------------------------------


class TestSidebarContainer:
    def test_add_panel_adds_to_stack(self, sidebar: SidebarContainer) -> None:
        assert sidebar.stack.count() == 2
        assert "alpha" in sidebar.activityBar.panelIds
        assert "beta" in sidebar.activityBar.panelIds

    def test_panel_toggled_forwarded(
        self, sidebar: SidebarContainer, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(sidebar.panelToggled) as blocker:
            sidebar.activityBar.setActive("alpha")
        assert blocker.args == ["alpha"]

    def test_toggle_collapse_and_restore(self, sidebar: SidebarContainer) -> None:
        sidebar.activityBar.setActive("alpha")
        assert sidebar.activityBar.activePanel == "alpha"

        sidebar.collapse()
        assert sidebar.activityBar.activePanel is None

    def test_toggle_method(self, sidebar: SidebarContainer) -> None:
        sidebar.activityBar.setActive("alpha")
        sidebar.splitterWidget.show()
        sidebar.toggle()  # should collapse
        assert sidebar.activityBar.activePanel is None

    def test_ab_position_default(self, sidebar: SidebarContainer) -> None:
        assert sidebar.resolvedAbPosition == "side"
        assert sidebar.isAbExternal is True

    def test_ab_position_top(self, sidebar: SidebarContainer) -> None:
        sidebar.setAbPosition(ActivityBarPosition.TOP)
        assert sidebar.resolvedAbPosition == "top"
        assert sidebar.isAbExternal is False
        assert sidebar.splitterWidget is sidebar._combined

    def test_ab_position_hidden(self, sidebar: SidebarContainer) -> None:
        sidebar.setAbPosition(ActivityBarPosition.HIDDEN)
        sidebar.arrange()
        assert not sidebar.activityBar.isVisible()

    def test_ab_position_changed_signal(
        self, sidebar: SidebarContainer, qtbot: QtBot
    ) -> None:
        sidebar.setAbPosition(ActivityBarPosition.BOTTOM)
        sidebar._ab_position = ActivityBarPosition.DEFAULT  # reset
        with qtbot.waitSignal(sidebar.abPositionChanged) as blocker:
            sidebar.abPositionChanged.emit(ActivityBarPosition.BOTTOM)
        assert blocker.args == [ActivityBarPosition.BOTTOM]

    def test_restore_from_drag(self, sidebar: SidebarContainer) -> None:
        sidebar.deselect()
        assert sidebar.activityBar.activePanel is None

        sidebar.restoreFromDrag()
        assert sidebar.activityBar.activePanel == "alpha"

    def test_arrange_side(self, sidebar: SidebarContainer) -> None:
        sidebar.setAbPosition(ActivityBarPosition.DEFAULT)
        sidebar.arrange()
        assert sidebar.activityBar.collapsible is True
        assert sidebar.activityBar.isVisible()

    def test_arrange_top(self, sidebar: SidebarContainer) -> None:
        sidebar.setAbPosition(ActivityBarPosition.TOP)
        sidebar.arrange()
        assert sidebar.activityBar.collapsible is False
        assert sidebar.activityBar.parent() is sidebar._combined


# ---- WorkbenchWidget tests ------------------------------------------------


class TestWorkbenchWidget:
    def test_initial_state(self, workbench: WorkbenchWidget) -> None:
        assert workbench.panelAlignment == PanelAlignment.CENTER
        assert workbench.leftSidebar.activityBar.activePanel == "explorer"
        assert workbench.rightSidebar.activityBar.activePanel == "properties"
        assert workbench._root_splitter is not None

    @pytest.mark.parametrize("alignment", list(PanelAlignment))
    def test_set_panel_alignment_rebuilds(
        self, workbench: WorkbenchWidget, alignment: PanelAlignment
    ) -> None:
        workbench.setPanelAlignment(alignment)
        assert workbench.panelAlignment == alignment
        assert workbench._root_splitter is not None

    def test_set_same_alignment_is_noop(self, workbench: WorkbenchWidget) -> None:
        old_splitter = workbench._root_splitter
        workbench.setPanelAlignment(PanelAlignment.CENTER)
        assert workbench._root_splitter is old_splitter

    def test_sidebar_toggle_emits_visibility_changed(
        self, workbench: WorkbenchWidget, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.leftSidebar.activityBar.setActive("explorer")

    def test_toggle_panel(self, workbench: WorkbenchWidget, qtbot: QtBot) -> None:
        assert workbench.bottomPanel.isVisible()
        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.togglePanel()
        assert not workbench.bottomPanel.isVisible()

        with qtbot.waitSignal(workbench.visibilityChanged):
            workbench.togglePanel()
        assert workbench.bottomPanel.isVisible()

    def test_sidebar_collapse_and_restore(self, workbench: WorkbenchWidget) -> None:
        left = workbench.leftSidebar
        left.collapse()
        assert left.activityBar.activePanel is None

        left.toggle()
        assert left.activityBar.activePanel is not None

    def test_alignment_switch_preserves_leaf_widgets(
        self, workbench: WorkbenchWidget
    ) -> None:
        """Leaf widgets must survive splitter tree rebuilds."""
        editor = workbench.centralWidget
        panel = workbench.bottomPanel
        left_stack = workbench.leftSidebar.stack
        right_stack = workbench.rightSidebar.stack

        for alignment in PanelAlignment:
            workbench.setPanelAlignment(alignment)
            assert editor.parent() is not None
            assert panel.parent() is not None
            assert left_stack.parent() is not None
            assert right_stack.parent() is not None

    def test_toggle_actions_exist(self, workbench: WorkbenchWidget) -> None:
        assert workbench.toggleLeftSidebarAction is not None
        assert workbench.togglePanelAction is not None
        assert workbench.toggleRightSidebarAction is not None

    def test_action_icons_update(self, workbench: WorkbenchWidget) -> None:
        """setActionIcons + toggle cycle should not crash."""
        from superqt import QIconifyIcon

        workbench.setActionIcons(
            workbench.toggleLeftSidebarAction,
            QIconifyIcon("codicon:layout-sidebar-left"),
            QIconifyIcon("codicon:layout-sidebar-left-off"),
        )

        # Collapse and restore — _updateActionIcons runs each time
        workbench.toggleLeftSidebar()
        workbench.toggleLeftSidebar()


# ---- MicroManagerGUI tests ------------------------------------------------


class TestMicroManagerGUI:
    def test_construction(self, gui: MicroManagerGUI) -> None:
        assert gui.windowTitle() == "pyMM"
        assert gui.acquire_mode is not None
        assert gui.configure_mode is not None

    def test_mode_switching(self, gui: MicroManagerGUI) -> None:
        gui._navigation.setCurrentIndex(0)
        assert gui._mode_stack.currentWidget() is gui.configure_mode

        gui._navigation.setCurrentIndex(1)
        assert gui._mode_stack.currentWidget() is gui.acquire_mode

    def test_toggle_left_sidebar(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert not wb.leftSidebar.isCollapsed

        wb.toggleLeftSidebar()
        assert wb.leftSidebar.activityBar.activePanel is None

        wb.toggleLeftSidebar()
        assert wb.leftSidebar.activityBar.activePanel is not None

    def test_toggle_right_sidebar(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert not wb.rightSidebar.isCollapsed

        wb.toggleRightSidebar()
        assert wb.rightSidebar.activityBar.activePanel is None

        wb.toggleRightSidebar()
        assert wb.rightSidebar.activityBar.activePanel is not None

    def test_toggle_panel(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        assert wb.bottomPanel.isVisible()

        wb.togglePanel()
        assert not wb.bottomPanel.isVisible()

        wb.togglePanel()
        assert wb.bottomPanel.isVisible()

    def test_cycle_panel_alignment(self, gui: MicroManagerGUI) -> None:
        gui.show()
        wb = gui.acquire_mode
        expected_cycle = [
            PanelAlignment.RIGHT,
            PanelAlignment.JUSTIFY,
            PanelAlignment.LEFT,
            PanelAlignment.CENTER,
        ]
        for expected in expected_cycle:
            gui._cycle_panel_alignment()
            assert wb.panelAlignment == expected

    def test_ghost_buttons_are_auto_raise(self, gui: MicroManagerGUI) -> None:
        assert gui._left_sb_btn.autoRaise()
        assert gui._panel_btn.autoRaise()
        assert gui._right_sb_btn.autoRaise()


# ---- Splitter size stability tests ----------------------------------------

TOLERANCE = 4  # pixels — accounts for integer rounding and handle widths


@pytest.fixture()
def shown_workbench(qtbot: QtBot) -> WorkbenchWidget:
    """WorkbenchWidget shown and laid out so splitter sizes are meaningful."""
    w = _make_workbench()
    qtbot.addWidget(w)
    w.resize(1200, 800)
    w.show()
    qtbot.waitExposed(w)
    from pymmcore_gui._qt.QtWidgets import QApplication

    QApplication.processEvents()
    w._save_sizes()
    return w


def _sidebar_sizes(wb: WorkbenchWidget) -> tuple[int, int, int]:
    """Return (left_width, editor_width, right_width) from actual geometry."""
    left = wb.leftSidebar.splitterWidget
    right = wb.rightSidebar.splitterWidget
    editor = wb.centralWidget
    return left.width(), editor.width(), right.width()


def test_alignment_cycle_no_drift(shown_workbench: WorkbenchWidget) -> None:
    """Cycling through all alignments and back should preserve sizes."""
    from pymmcore_gui._qt.QtWidgets import QApplication

    wb = shown_workbench
    left0, _, right0 = _sidebar_sizes(wb)

    alignments = list(PanelAlignment)
    for _ in range(3):
        for alignment in alignments:
            wb.setPanelAlignment(alignment)
            QApplication.processEvents()

    wb.setPanelAlignment(PanelAlignment.CENTER)
    QApplication.processEvents()
    left_after, _, right_after = _sidebar_sizes(wb)

    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar drifted: {left0} -> {left_after}"
    )
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar drifted: {right0} -> {right_after}"
    )


def test_sidebar_toggle_preserves_other_sidebar(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Toggling one sidebar should not change the other sidebar's size."""
    wb = shown_workbench
    _, _, right0 = _sidebar_sizes(wb)

    for _ in range(5):
        wb.toggleLeftSidebar()
        wb.toggleLeftSidebar()

    _, _, right_after = _sidebar_sizes(wb)
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar changed when toggling left: {right0} -> {right_after}"
    )


def test_sidebar_toggle_restores_own_size(
    shown_workbench: WorkbenchWidget,
) -> None:
    """A sidebar should return to its original size after toggle cycle."""
    wb = shown_workbench
    left0, _, _ = _sidebar_sizes(wb)

    wb.toggleLeftSidebar()  # collapse
    wb.toggleLeftSidebar()  # restore

    left_after, _, _ = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar size changed after toggle cycle: {left0} -> {left_after}"
    )


def test_panel_toggle_preserves_sidebar_sizes(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Toggling the bottom panel should not affect sidebar widths."""
    wb = shown_workbench
    left0, _, right0 = _sidebar_sizes(wb)

    for _ in range(5):
        wb.togglePanel()
        wb.togglePanel()

    left_after, _, right_after = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar changed when toggling panel: {left0} -> {left_after}"
    )
    assert abs(right_after - right0) <= TOLERANCE, (
        f"right sidebar changed when toggling panel: {right0} -> {right_after}"
    )


def test_alignment_change_preserves_collapsed_state(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Changing panel alignment should not resurrect a collapsed sidebar."""
    from pymmcore_gui._qt.QtWidgets import QApplication

    wb = shown_workbench

    wb.toggleRightSidebar()
    QApplication.processEvents()
    assert wb.rightSidebar.isCollapsed

    wb.setPanelAlignment(PanelAlignment.RIGHT)
    QApplication.processEvents()

    right_w = wb.rightSidebar.splitterWidget
    assert _splitter_size(right_w) == 0, (
        "collapsed right sidebar reappeared after alignment change"
    )

    wb.setPanelAlignment(PanelAlignment.CENTER)
    QApplication.processEvents()
    wb.toggleLeftSidebar()
    QApplication.processEvents()
    assert wb.leftSidebar.isCollapsed

    wb.setPanelAlignment(PanelAlignment.JUSTIFY)
    QApplication.processEvents()

    left_w = wb.leftSidebar.splitterWidget
    assert _splitter_size(left_w) == 0, (
        "collapsed left sidebar reappeared after alignment change"
    )


def test_rapid_alignment_cycling_with_collapses(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Rapid alignment changes with collapsed parts must not corrupt state."""
    from pymmcore_gui._qt.QtWidgets import QApplication

    wb = shown_workbench

    wb.toggleRightSidebar()
    wb.togglePanel()
    QApplication.processEvents()

    for _ in range(3):
        for align in PanelAlignment:
            wb.setPanelAlignment(align)

    QApplication.processEvents()

    assert wb.rightSidebar.isCollapsed
    assert not wb.isPanelVisible
    assert not wb.leftSidebar.isCollapsed
    assert wb.leftSidebar.activityBar.activePanel is not None


def test_collapse_all_then_change_alignment(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Collapsing everything then changing alignment must not crash."""
    from pymmcore_gui._qt.QtWidgets import QApplication

    wb = shown_workbench

    wb.toggleLeftSidebar()
    wb.toggleRightSidebar()
    wb.togglePanel()
    QApplication.processEvents()

    for align in PanelAlignment:
        wb.setPanelAlignment(align)
        QApplication.processEvents()
        assert wb.leftSidebar.isCollapsed
        assert wb.rightSidebar.isCollapsed
        assert not wb.isPanelVisible


def test_drag_restore_does_not_disturb_other_sidebar(
    shown_workbench: WorkbenchWidget,
) -> None:
    """Drag-to-zero then drag-back should not shift other sidebar."""
    wb = shown_workbench
    left0, _, _ = _sidebar_sizes(wb)
    right_widget = wb.rightSidebar.splitterWidget
    parent = right_widget.parentWidget()
    assert parent is not None

    from pymmcore_gui._qt.QtWidgets import QSplitter

    assert isinstance(parent, QSplitter)
    idx = parent.indexOf(right_widget)

    # Simulate drag to zero
    sizes = parent.sizes()
    freed = sizes[idx]
    editor_idx = wb._editor_index_in(parent)
    sizes[editor_idx] += freed
    sizes[idx] = 0
    parent.setSizes(sizes)
    wb._on_splitter_moved()

    assert wb.rightSidebar.activityBar.activePanel is None

    # Simulate drag back
    sizes = parent.sizes()
    restore_px = 150
    sizes[editor_idx] -= restore_px
    sizes[idx] = restore_px
    parent.setSizes(sizes)
    wb._on_splitter_moved()

    left_after, _, _ = _sidebar_sizes(wb)
    assert abs(left_after - left0) <= TOLERANCE, (
        f"left sidebar shifted during right drag-restore: {left0} -> {left_after}"
    )
