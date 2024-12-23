from __future__ import annotations

import argparse
import os
import sys
import traceback
from contextlib import suppress
from typing import IO, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication

from pymmcore_gui import MicroManagerGUI

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType

IS_FROZEN = getattr(sys, "frozen", False)


class MMQApplication(QApplication):
    exceptionRaised = pyqtSignal(BaseException)


def main(args: Sequence[str] | None = None) -> None:
    """Run the Micro-Manager GUI."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Enter string")
    parser.add_argument(
        "-c", "--config", type=str, default=None, help="Config file to load", nargs="?"
    )
    parsed_args = parser.parse_args(args)

    app = MMQApplication(sys.argv)
    _install_excepthook()

    win = MicroManagerGUI(config=parsed_args.config)
    win.show()

    app.exec()


# ------------------- Custom excepthook -------------------


def _install_excepthook() -> None:
    """Install a custom excepthook that does not raise sys.exit().

    This is necessary to prevent the application from closing when an exception
    is raised.
    """
    if hasattr(sys, "_original_excepthook_"):
        return
    sys._original_excepthook_ = sys.excepthook  # type: ignore
    sys.excepthook = ndv_excepthook


def rich_print_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    import psygnal
    from rich.console import Console
    from rich.traceback import Traceback

    tb = Traceback.from_exception(
        exc_type,
        exc_value,
        exc_traceback,
        suppress=[psygnal],
        max_frames=100 if IS_FROZEN else 10,
        show_locals=True,
    )
    Console(stderr=True).print(tb)


def _print_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    try:
        rich_print_exception(exc_type, exc_value, exc_traceback)
    except ImportError:
        traceback.print_exception(exc_type, value=exc_value, tb=exc_traceback)


EXCEPTION_LOG: list[
    tuple[type[BaseException], BaseException, TracebackType | None]
] = []


def ndv_excepthook(
    exc_type: type[BaseException], exc_value: BaseException, tb: TracebackType | None
) -> None:
    EXCEPTION_LOG.append((exc_type, exc_value, tb))
    _print_exception(exc_type, exc_value, tb)
    if sig := getattr(QApplication.instance(), "exceptionRaised", None):
        sig.emit(exc_value)
    if not tb:
        return

    # if we're running in a vscode debugger, let the debugger handle the exception
    if (
        (debugpy := sys.modules.get("debugpy"))
        and debugpy.is_client_connected()
        and ("pydevd" in sys.modules)
    ):
        with suppress(Exception):
            import threading

            import pydevd

            py_db = pydevd.get_global_debugger()
            thread = threading.current_thread()
            additional_info = py_db.set_additional_thread_info(thread)
            additional_info.is_tracing += 1

            try:
                arg = (exc_type, exc_value, tb)
                py_db.stop_on_unhandled_exception(py_db, thread, additional_info, arg)
            finally:
                additional_info.is_tracing -= 1
    # otherwise, if MMGUI_DEBUG_EXCEPTIONS is set, drop into pdb
    elif os.getenv("MMGUI_DEBUG_EXCEPTIONS"):
        import pdb

        pdb.post_mortem(tb)

    # after handling the exception, exit if MMGUI_EXIT_ON_EXCEPTION is set
    if os.getenv("MMGUI_EXIT_ON_EXCEPTION"):
        print("\nMMGUI_EXIT_ON_EXCEPTION is set, exiting.")
        sys.exit(1)
