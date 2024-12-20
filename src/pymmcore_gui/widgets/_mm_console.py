from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

if TYPE_CHECKING:
    from PyQt6.QtGui import QCloseEvent
    from PyQt6.QtWidgets import QWidget


class MMConsole(RichJupyterWidget):
    """A Qt widget for an IPython console, providing access to UI components."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        cast("QWidget", self).setWindowTitle("Python kernel")
        self.set_default_style(colors="linux")

        # this makes calling `setFocus()` on a QtConsole give keyboard focus to
        # the underlying `QTextEdit` widget
        cast("QWidget", self).setFocusProxy(self._control)

        # Create an in-process kernel
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = "qt"
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.shell = self.kernel_manager.kernel.shell

        self.shell.run_cell("from rich import pretty; pretty.install()")
        self.shell.run_cell("from rich import print")

    def push(self, variables: dict[str, Any]) -> None:
        self.shell.push(variables)

    def get_user_variables(self) -> dict:
        """Return the variables pushed to the console."""
        return {k: v for k, v in self.shell.user_ns.items() if k != "__builtins__"}

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up the integrated console."""
        if self.kernel_client is not None:
            self.kernel_client.stop_channels()
        if self.kernel_manager is not None and self.kernel_manager.has_kernel:
            self.kernel_manager.shutdown_kernel()

        # RichJupyterWidget doesn't clean these up
        self._completion_widget.deleteLater()
        self._call_tip_widget.deleteLater()
        cast("QWidget", self).deleteLater()
        event.accept()
