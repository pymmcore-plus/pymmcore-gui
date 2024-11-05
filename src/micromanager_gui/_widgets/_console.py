from typing import Any

import pyqtconsole.highlighter as hl
from pyqtconsole.console import PythonConsole
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import QDialog, QVBoxLayout, QWidget

# override the default formats to change blue and red colors
FORMATS = {
    "keyword": hl.format("green", "bold"),
    "operator": hl.format("magenta"),
    "inprompt": hl.format("green", "bold"),
    "outprompt": hl.format("magenta", "bold"),
}


class MMConsole(QDialog):
    """A Qt widget for an IPython console, providing access to UI components."""

    def __init__(
        self, parent: QWidget | None = None, user_variables: dict | None = None
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("micromanager-gui console")

        self._console = PythonConsole(parent=self, formats=FORMATS)
        self._console.eval_in_thread()

        layput = QVBoxLayout(self)
        layput.addWidget(self._console)

        # Add user variables if provided
        if user_variables is not None:
            self.push(user_variables)

    def push(self, user_variables: dict[str, Any]) -> None:
        """Push a dictionary of variables to the console.

        This is an alternative to using the native `push_local_ns` method.
        """
        for key, value in user_variables.items():
            self._console.push_local_ns(key, value)


class MMConsoleJupyter(QDialog):
    """A Qt widget for an IPython console, providing access to UI components."""

    def __init__(
        self, parent: QWidget | None = None, user_variables: dict | None = None
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("micromanager-gui console")

        self._console = _JupyterConsole(user_variables=user_variables)

        layput = QVBoxLayout(self)
        layput.addWidget(self._console)

        self._console.push(user_variables)


class _JupyterConsole(RichJupyterWidget):
    """A Qt widget for an IPython console, providing access to UI components.

    Copied from gselzer: https://github.com/gselzer/pymmcore-plus-sandbox/blob/53ac7e8ca3b4874816583b8b74024a75432b8fc9/src/pymmcore_plus_sandbox/_console_widget.py#L5
    """

    def __init__(self, user_variables: dict | None = None) -> None:
        if user_variables is None:
            user_variables = {}
        super().__init__()

        # this makes calling `setFocus()` on a QtConsole give keyboard focus to
        # the underlying `QTextEdit` widget
        self.setFocusProxy(self._control)

        # Create an in-process kernel
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = "qt"
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.shell = self.kernel_manager.kernel.shell
        self.push = self.shell.push

        # Add any user variables
        self.push(user_variables)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up the integrated console in napari."""
        if self.kernel_client is not None:
            self.kernel_client.stop_channels()
        if self.kernel_manager is not None and self.kernel_manager.has_kernel:
            self.kernel_manager.shutdown_kernel()

        # RichJupyterWidget doesn't clean these up
        self._completion_widget.deleteLater()
        self._call_tip_widget.deleteLater()
        self.deleteLater()
        event.accept()
