from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import traceback
import warnings
from contextlib import suppress
from typing import TYPE_CHECKING, Literal, cast

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QCheckBox, QMessageBox, QWidget
from superqt.utils import WorkerBase

from pymmcore_gui import __version__
from pymmcore_gui._main_window import ICON, MicroManagerGUI
from pymmcore_gui._settings import Settings

from . import _sentry

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from pymmcore_plus import CMMCorePlus

    ExcTuple = tuple[type[BaseException], BaseException, TracebackType | None]

APP_NAME = "pyMM"
APP_VERSION = __version__
ORG_NAME = "pymmcore-plus"
ORG_DOMAIN = "pymmcore-plus"
APP_ID = f"{ORG_DOMAIN}.{ORG_NAME}.{APP_NAME}.{APP_VERSION}"
IS_FROZEN = getattr(sys, "frozen", False)
_QAPP: MMQApplication | None = None


def _set_osx_app_name(app_title: str) -> None:
    if not sys.platform.startswith("darwin"):
        return

    from ctypes import Structure, c_int, cdll, pointer
    from ctypes.util import find_library

    class ProcessSerialNumber(Structure):
        _fields_ = (("highLongOfPSN", c_int), ("lowLongOfPSN", c_int))

    if app_services := find_library("ApplicationServices"):
        lib = cdll.LoadLibrary(app_services)
        psn = ProcessSerialNumber()
        psn_p = pointer(psn)
        if lib.GetCurrentProcess(psn_p) >= 0:
            lib.CPSSetProcessName(psn_p, app_title.encode("utf-8"))


class MMQApplication(QApplication):
    exceptionRaised = pyqtSignal(BaseException)

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)

        self.setWindowIcon(QIcon(str(ICON)))
        self.setApplicationName(APP_NAME)
        self.setApplicationVersion(APP_VERSION)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)
        if not IS_FROZEN:
            if os.name == "nt":
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # type: ignore
            elif sys.platform.startswith("darwin"):
                _set_osx_app_name(APP_NAME)

        self.aboutToQuit.connect(WorkerBase.await_workers)


def create_mmgui(
    *,
    mm_config: Path | str | None | Literal[False] = None,
    mmcore: CMMCorePlus | None = None,
    install_sys_excepthook: bool = True,
    install_sentry: bool = True,
    exec_app: bool = True,
) -> MicroManagerGUI:
    """Initialize the pymmcore-gui application and Main Window.

    This is the primary way to start pymmcore-gui.  (It is also called by
    `__main__.main()` when running from the command line.)

    Parameters
    ----------
    mm_config : str | None | False
        The path to the Micro-Manager configuration file to load.
        - If `False`, no configuration will be loaded.
        - If a non-empty string, that configuration will be loaded.
        - If None (or the empty string), auto-deciding logic will be used based on the
          stored user settings (based on the settings values for
          `Settings.last_config` and `Settings.auto_load_last_config`).
    mmcore : CMMCorePlus | None
        The CMMCorePlus instance to use.  If `None` (default), the global
        `CMMCorePlus.instance()` will be used if it exists, or a new (global) instance
        will be created (which you may access later with `CMMCorePlus.instance()`).
        Note: you may wish to also pass `mm_config = False` to prevent loading a
        system configuration, if you have already loaded one in your instance.
    install_sys_excepthook : bool
        If True (the default), installs a custom excepthook that does not raise
        sys.exit(). This is necessary to prevent the application from closing when an
        unhandled exception is raised in the main thread.
    install_sentry : bool
        If True (the default), the user will be given an option to send error reports
        to the developers, unless they have previously opted in/out.  If False, no
        prompt will be shown, and no error reports will be sent.
    exec_app : bool
        If True (the default), the QApplication event loop will be started.  If
        False, the event loop will not be started, and the caller is responsible for
        starting it with `QApplication.instance().exec()`.
    """
    global _QAPP
    # Note: in practice this should almost never be None,
    # but in the case of testing, it's conceivable that it could be.
    if (app := QApplication.instance()) is None:
        # store the app instance in a global variable to prevent garbage collection
        _QAPP = app = MMQApplication(sys.argv)
    elif not isinstance(app, MMQApplication):  # pragma: no cover
        warnings.warn(
            "A QApplication instance already exists, but it is not MMQApplication. "
            " This may cause unexpected behavior.",
            RuntimeWarning,
            stacklevel=2,
        )

    win = MicroManagerGUI(mmcore=mmcore)
    QTimer.singleShot(0, lambda: win.restore_state(show=True))

    # if False was passed, don't load any config at all
    if mm_config is not False:
        # if a string was passed, load that config
        if mm_config:
            # if mm_config is a string, load that config
            win.mmcore.loadSystemConfiguration(mm_config)
        # otherwise, fall back to auto-loading / cli-based
        elif config := _decide_configuration(mm_config, win):
            try:
                win.mmcore.loadSystemConfiguration(config)
            except Exception as e:  # pragma: no cover
                warnings.warn(
                    f"Failed to load system configuration: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

    if install_sys_excepthook:
        _install_excepthook()
    if install_sentry:
        _sentry.install_error_reporter()

    # close the PyInstaller splash screen if it exists
    _close_splash_screen()

    if exec_app:
        app.exec()
    return win


def _close_splash_screen() -> None:  # pragma: no cover
    if "_PYI_SPLASH_IPC" in os.environ and importlib.util.find_spec("pyi_splash"):
        import pyi_splash  # pyright: ignore [reportMissingModuleSource]

        pyi_splash.update_text("UI Loaded ...")
        pyi_splash.close()


def _decide_configuration(
    config: Path | str | None = None, parent: QWidget | None = None
) -> str | None:
    settings = Settings.instance()
    if config:
        return str(config)

    if last_config := settings.last_config:
        if auto_load := settings.auto_load_last_config:
            return str(last_config)

        # show dialog to ask if the user wants to load the last config
        if auto_load is None:
            dialog = LoadConfigDialog(last_config)
            if (btn := dialog.exec()) != QMessageBox.StandardButton.Cancel:
                auto_load = btn == QMessageBox.StandardButton.Yes
                if dialog.dont_ask_again.isChecked():
                    settings.auto_load_last_config = auto_load
                    settings.flush()
                if auto_load:
                    return str(last_config)

    if settings.fallback_to_demo_config:
        return "MMConfig_demo.cfg"
    return None


class LoadConfigDialog(QMessageBox):
    def __init__(self, last_config: Path | str):
        super().__init__(
            QMessageBox.Icon.Question,
            "Load last config?",
            f"Do you want to load the last-used config file:\n\n{last_config}?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        self.setDefaultButton(QMessageBox.StandardButton.Yes)
        self.setEscapeButton(QMessageBox.StandardButton.Cancel)

        self.dont_ask_again = QCheckBox("Don't ask again")
        self.setCheckBox(self.dont_ask_again)


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


# This log list is used by the ExceptionLog widget
# Be aware that it's currently possible for that widget to clear this list.
# If an immutable record of exceptions is needed, additional logic will be required.
EXCEPTION_LOG: list[ExcTuple] = []


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
    ):  # pragma: no cover
        with suppress(Exception):
            import threading

            import pydevd  # pyright: ignore [reportMissingImports]

            if (py_db := pydevd.get_global_debugger()) is None:
                return

            py_db = cast("pydevd.PyDB", py_db)
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
        import pdb  # noqa: T100

        pdb.post_mortem(tb)

    # after handling the exception, exit if MMGUI_EXIT_ON_EXCEPTION is set
    if os.getenv("MMGUI_EXIT_ON_EXCEPTION"):
        print("\nMMGUI_EXIT_ON_EXCEPTION is set, exiting.")
        sys.exit(1)
