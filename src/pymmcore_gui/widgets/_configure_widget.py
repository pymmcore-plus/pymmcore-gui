from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_gui._qt.QtCore import Qt
from pymmcore_gui._qt.QtGui import QFont, QPalette
from pymmcore_gui._qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from pymmcore_gui._utils import current_core

if TYPE_CHECKING:
    from collections.abc import Callable

# (section_name, [(page_id, page_title), ...])
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "HARDWARE",
        [
            ("devices", "Devices"),
            ("device_roles", "Device Roles"),
        ],
    ),
    (
        "PRESETS",
        [
            ("config_groups", "Config Groups"),
            ("pixel_calibration", "Pixel Calibration"),
        ],
    ),
    (
        "APPLICATION",
        [
            ("general", "General"),
            ("appearance", "Appearance"),
            ("shortcuts", "Shortcuts"),
        ],
    ),
]


class ConfigureModeWidget(QWidget):
    """Configure mode with sidebar navigation and stacked content pages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._page_items: dict[str, QTreeWidgetItem] = {}
        self._page_widgets: dict[str, QWidget] = {}
        self._page_factories: dict[str, Callable[[], QWidget]] = {
            "config_groups": self._make_config_groups_page
        }

        # --- sidebar tree ---
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setItemsExpandable(False)
        self._tree.setIndentation(12)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # --- stacked content ---
        self._stack = QStackedWidget()

        # Build sections and pages
        for section_name, pages in SECTIONS:
            header = QTreeWidgetItem(self._tree, [section_name.upper()])
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)  # not selectable
            font = header.font(0)
            font.setWeight(QFont.Weight.DemiBold)
            font.setPointSize(max(font.pointSize() - 1, 1))
            header.setFont(0, font)
            muted = self.palette().brush(QPalette.ColorRole.PlaceholderText)
            header.setForeground(0, muted)
            header.setExpanded(True)

            for page_id, page_title in pages:
                item = QTreeWidgetItem(header, [page_title])
                self._page_items[page_id] = item

                # Placeholder page
                page = _placeholder_page(page_title)

                self._page_widgets[page_id] = page
                self._stack.addWidget(page)

        self._tree.expandAll()
        self._tree.currentItemChanged.connect(self._on_item_changed)

        # Select first page
        first_id = SECTIONS[0][1][0][0]
        self._tree.setCurrentItem(self._page_items[first_id])

        # --- layout ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 600])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    def pageWidget(self, page_id: str) -> QWidget:
        """Return the content widget for the given page id."""
        return self._page_widgets[page_id]

    def setPage(self, page_id: str, widget: QWidget) -> None:
        """Replace the current widget for page_id with the given widget."""
        self._replacePage(page_id, widget)

    def setPageFactory(self, page_id: str, factory: Callable[[], QWidget]) -> None:
        """Register a factory that creates a new widget each time the page is shown."""
        self._page_factories[page_id] = factory

    def _replacePage(self, page_id: str, widget: QWidget) -> None:
        old = self._page_widgets[page_id]
        idx = self._stack.indexOf(old)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(idx, widget)
        self._page_widgets[page_id] = widget

    def _on_item_changed(
        self,
        current: QTreeWidgetItem | None,
        _prev: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            return
        for page_id, item in self._page_items.items():
            if item is current:
                if page_id in self._page_factories:
                    self._replacePage(page_id, self._page_factories[page_id]())
                self._stack.setCurrentWidget(self._page_widgets[page_id])
                return

    def _make_config_groups_page(self) -> QWidget:
        from pymmcore_widgets import ConfigGroupsEditor

        if not (core := current_core(self)):
            return _placeholder_page("No core found")
        return ConfigGroupsEditor.create_from_core(core)


def _placeholder_page(page_title: str) -> QWidget:
    page = QWidget()
    page_layout = QVBoxLayout(page)
    lbl = QLabel(page_title)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    page_layout.addWidget(lbl)
    return page
