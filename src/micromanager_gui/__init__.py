"""A Micro-Manager GUI based on pymmcore-widgets and pymmcore-plus."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("micromanager-gui")
except PackageNotFoundError:
    __version__ = "uninstalled"

__author__ = "Federico Gasparoli"
__email__ = "federico.gasparoli@gmail.com"
