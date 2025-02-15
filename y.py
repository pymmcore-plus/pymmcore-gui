from typing import cast

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview


class DraggableWidget(QDialog):
    """Widget that follows the mouse when undocked."""

    def __init__(self, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.installEventFilter(self)

        self._widget = widget
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._widget)
        self._dragging = False

        # the offset is used to make sure the cursor is at the center of the window
        self._offset = QPoint(0, 0)

    def start_dragging(self, start_pos: QPoint, offset: QPoint) -> None:
        """Enable dragging immediately after undocking."""
        self._dragging = True
        self._offset = offset
        self.grabMouse()
        self.move(start_pos + self._offset)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        """Move the window with the cursor if still dragging."""
        if (
            a0 is not None
            and self._dragging
            and a0.buttons() == Qt.MouseButton.LeftButton
        ):
            self.move(QCursor.pos() + self._offset)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        """Stop dragging when mouse is released."""
        self._dragging = False
        self.releaseMouse()


class DockableTabWidget(QTabWidget):
    """Tab widget that allows undocking tabs into floating dock widgets."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setTabBar(DockableTabBar(self))  # Use custom tab bar

    def undock_tab(self, widget: DraggableWidget) -> None:
        """Remove the tab and create a floating dialog that follows the mouse."""
        index = self.indexOf(widget)
        if index >= 0 and index < self.count() and widget:
            # Remove the tab
            self.removeTab(index)
            widget.setParent(self.parent())
            # Convert the widget into a dialog window
            widget.setWindowFlags(Qt.WindowType.Dialog)
            widget.show()
            # get the current window width
            window_size = widget.size().width()
            # start dragging the dialog window. The offset is to make sure the cursor is
            # at the center of the dialog window
            widget.start_dragging(QCursor.pos(), QPoint(-window_size // 2, -10))

    def redock_tab(self, widget: DraggableWidget) -> None:
        """Re-add the widget as a tab if it is dropped onto the tab bar."""
        widget.setWindowFlags(Qt.WindowType.Widget)  # Remove floating window behavior
        widget.hide()  # Temporarily hide to avoid flickering
        widget.show()  # Show again after setting parent
        self.addTab(widget, f"REDOCKED {self.count() + 1}")


class DockableTabBar(QTabBar):
    """Custom tab bar to detect dragging of tabs."""

    def __init__(self, parent: DockableTabWidget) -> None:
        super().__init__(parent)
        self._tabwidget: DockableTabWidget = parent
        self._current_tab_info: tuple[DraggableWidget | None, QPoint] | None = None

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        """Detect if a tab is being clicked."""
        if a0 is None or a0.buttons() != Qt.MouseButton.LeftButton:
            return None
        # Get the tab widget at the mouse position
        tab_index = self.tabAt(a0.pos())
        widget = self._tabwidget.widget(tab_index) if tab_index >= 0 else None
        self._current_tab_info = (
            cast(DraggableWidget, widget),
            a0.globalPosition().toPoint(),
        )
        super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        """Initiate undocking when dragging a tab."""
        if (
            a0 is None
            or a0.buttons() != Qt.MouseButton.LeftButton
            or self._current_tab_info is None
        ):
            return None

        widget, start_pos = self._current_tab_info
        distance = (a0.globalPosition().toPoint() - start_pos).manhattanLength()
        if distance > QApplication.startDragDistance() and widget is not None:
            self._tabwidget.undock_tab(widget)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dockable Tabs in QTabWidget")
        self.resize(800, 600)
        self.central_tabs = DockableTabWidget(self)
        self.setCentralWidget(self.central_tabs)

        mmc = CMMCorePlus.instance()
        mmc.loadSystemConfiguration()

        # Add tabs
        for i in range(2):
            v = NDVPreview(self, mmcore=mmc)
            v._setup_viewer()
            tab = DraggableWidget(v, parent=self)
            self.central_tabs.addTab(tab, f"Tab {i+1}")


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
