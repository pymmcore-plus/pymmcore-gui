"""A Micro-Manager GUI based on pymmcore-widgets and pymmcore-plus."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("pymmcore-gui")
except PackageNotFoundError:
    __version__ = "uninstalled"

import sys

if sys.platform == "win32":
    # On Windows, a DLL of a given basename is only loaded once per process.
    # This can cause issues if one Python package (e.g. PyQt6) bundles and
    # loads an old DLL and another, later-imported package (e.g. pymmcore or a
    # device adapter) requires a newer version of the DLL. The symptom, if any,
    # will likely be a crash (but could be e.g. silent memory corruption).
    # Most often this happens with Microsoft Visual C++ Runtime DLLs, because
    # all C++ code depends on them. Here we preemptively load a (heuristically
    # chosen) subset of these DLLs so that we load the system-installed
    # versions, which are most likely to be up to date.
    # Note 1: We are relying on the fact that the Micro-Manager installer
    # (among other things) installs the Visual C++ Redistributables (vc_redist)
    # package onto the system, and the fact that these DLLs are designed to be
    # backward-compatible.
    # Note 2: The list of DLLs loaded below cover all that are used by pymmcore
    # and the device adapters at the time of writing and/or are bundled by
    # PyQt6. The full list is at
    # https://learn.microsoft.com/en-us/cpp/windows/determining-which-dlls-to-redistribute
    # but we do not want to load the DLLs that will never be used.
    # Note 3: In fact the Python interpreter itself bundles vcruntime140.dll
    # and vcruntime140_1.dll; but these are usually new enough if using the
    # latest Python versions.
    import contextlib
    import ctypes

    msvc_runtimes = [
        "concrt140",
        "msvcp140",
        "msvcp140_1",
        "msvcp140_2",
        "vcruntime140",
        "vcruntime140_1",
    ]
    for dll in msvc_runtimes:
        with contextlib.suppress(OSError):
            ctypes.WinDLL(dll)

from ._app import create_mmgui
from ._main_window import MicroManagerGUI
from .actions import ActionInfo, CoreAction, WidgetAction

__all__ = [
    "ActionInfo",
    "CoreAction",
    "MicroManagerGUI",
    "WidgetAction",
    "__version__",
    "create_mmgui",
]
