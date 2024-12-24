from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, cast

os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"


# Redirect sys.stdout and sys.stderr to devnull if they are None
# this is necessary for the IPython console to work properly in a windows PyInstaller
if os.name == "nt":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


from PyQt6.QtWidgets import QApplication
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from traitlets import default

try:
    import rich
except ImportError:
    rich = None  # type: ignore

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
        self.kernel_manager.start_kernel()
        self.kernel_manager.kernel.gui = "qt"
        self.shell = self.kernel_manager.kernel.shell
        self.shell.banner1 = ""
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        if rich is not None:
            self.shell.run_cell("from rich import pretty; pretty.install()")
            self.shell.run_cell("from rich import print")

        self._inject_core_vars()

    def _inject_core_vars(self) -> None:
        import numpy
        import pymmcore_plus
        import useq

        import pymmcore_gui

        default_vars = {
            **pymmcore_plus.__dict__,
            **useq.__dict__,
            **pymmcore_gui.__dict__,
            "useq": useq,
            "np": numpy,
        }
        mmc = None
        for wdg in QApplication.topLevelWidgets():
            if wdg.objectName() == "MicroManagerGUI":
                default_vars["window"] = wdg
                mmc = getattr(wdg, "mmc", None)
                break

        mmc = mmc or pymmcore_plus.CMMCorePlus.instance()
        default_vars.update({"mmc": mmc, "core": mmc, "mmcore": mmc, "mda": mmc.mda})
        self.push(default_vars)

    @default("banner")  # type: ignore [misc]
    def _banner_default(self) -> str:
        # Set the banner displayed at the top of the console
        lines = [
            "Welcome to the pymmcore-plus console!",
            "All top level pymmcore_plus and useq names are available.",
            "",
            "Use \033[1;33mmmc\033[0m (or \033[1;33mcore\033[0m) to interact with the CMMCorePlus instance.\n"  # noqa: E501
            "Use \033[1;33mmda\033[0m to access the pymmcore_plus.MDARunner.",
        ]
        if "window" in self.shell.user_ns:
            lines.append("Use \033[1;33mwindow\033[0m to interact with the MainWindow.")
        return "\n".join(lines)

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
