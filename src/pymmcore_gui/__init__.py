"""A Micro-Manager GUI based on pymmcore-widgets and pymmcore-plus."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("pymmcore-gui")
except PackageNotFoundError:
    __version__ = "uninstalled"

import pymmcore  # noqa: F401, I001
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
