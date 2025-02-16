from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabBar,
    QTabWidget,
    QWidget,
)


class DockableTabWidget(QTabWidget):
    """Tab widget that allows undocking tabs into floating dock widgets."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setTabBar(DockableTabBar(self))  # Use custom tab bar

    def undock_tab(self, widget: QWidget | None) -> None:
        """Remove the tab and create a dock widget."""
        index = self.indexOf(widget)
        if index >= 0 and index < self.count() and widget:
            title = self.tabText(index)
            # remove the tab
            self.removeTab(index)
            # convert the widget into a dialog window
            widget.setWindowFlags(Qt.WindowType.Dialog)
            widget.setWindowTitle(title)
            widget.show()
            # move the dialog window to the cursor position
            widget.move(QCursor.pos())


class DockableTabBar(QTabBar):
    """Custom tab bar to detect dragging of tabs."""

    def __init__(self, parent: DockableTabWidget) -> None:
        super().__init__(parent)
        self._tabwidget: DockableTabWidget = parent
        self._current_tab_info: tuple[QWidget | None, QPoint] | None = None

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        """Detect if a tab is being clicked."""
        if a0 is None or a0.buttons() != Qt.MouseButton.LeftButton:
            return None
        # get the tab widget at the mouse position
        tab_index = self.tabAt(a0.pos())
        widget = self._tabwidget.widget(tab_index) if tab_index >= 0 else None
        self._current_tab_info = (widget, a0.pos())
        super().mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        """Initiate undocking when dragging a tab."""
        if (
            a0 is None
            or a0.buttons() != Qt.MouseButton.LeftButton
            or self._current_tab_info is None
        ):
            return None

        # if the mouse is moved more than the drag distance, start undocking
        widget, start_pos = self._current_tab_info
        distance = (a0.pos() - start_pos).manhattanLength()
        if distance > QApplication.startDragDistance():
            self._tabwidget.undock_tab(widget)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dockable Tabs in QTabWidget")
        self.resize(800, 600)
        self.central_tabs = DockableTabWidget(self)
        self.setCentralWidget(self.central_tabs)
        # add tabs
        for i in range(3):
            tab = QWidget()
            self.central_tabs.addTab(tab, f"Tab {i+1}")


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
