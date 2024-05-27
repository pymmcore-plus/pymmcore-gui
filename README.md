# micromanager-gui [WIP]

[![License](https://img.shields.io/pypi/l/micromanager-gui.svg?color=green)](https://github.com/fdrgsp/micromanager-gui/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/micromanager-gui.svg?color=green)](https://pypi.org/project/micromanager-gui)
[![Python Version](https://img.shields.io/pypi/pyversions/micromanager-gui.svg?color=green)](https://python.org)
[![CI](https://github.com/fdrgsp/micromanager-gui/actions/workflows/ci.yml/badge.svg)](https://github.com/fdrgsp/micromanager-gui/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/fdrgsp/micromanager-gui/branch/main/graph/badge.svg)](https://codecov.io/gh/fdrgsp/micromanager-gui)

A Micro-Manager GUI based on [pymmcore-widgets](https://pymmcore-plus.github.io/pymmcore-widgets/) and [pymmcore-plus](https://pymmcore-plus.github.io/pymmcore-plus/).

<img width="1840" alt="Screenshot 2024-05-27 at 11 55 53 AM" src="https://github.com/fdrgsp/micromanager-gui/assets/70725613/78d5728b-10b5-4ea0-8058-68b461442f0c">


## Installation

```bash
pip install git+https://github.com/fdrgsp/micromanager-gui
```

### Installing PyQt or PySide

Since `micromanager-gui` relies on either the [PyQt](https://riverbankcomputing.com/software/pyqt/) or [PySide](https://www.qt.io/qt-for-python) libraries, you also **need** to install one of these packages. You can use any of the available versions of these libraries: [PyQt5](https://pypi.org/project/PyQt5/), [PyQt6](https://pypi.org/project/PyQt6/), [PySide2](https://pypi.org/project/PySide2/) or [PySide6](https://pypi.org/project/PySide6/). For example, to install [PyQt6](https://riverbankcomputing.com/software/pyqt/download), you can use:

```sh
pip install PyQt6
```

### Installing Micro-Manager

You also need to install the `Micro-Manager` device adapters and C++ core provided by [mmCoreAndDevices](https://github.com/micro-manager/mmCoreAndDevices#mmcoreanddevices). This can be done by following the steps described in the `pymmcore-plus` [documentation page](https://pymmcore-plus.github.io/pymmcore-plus/install/#installing-micro-manager-device-adapters).

## To run the GUI

```bash
python -m micromanager_gui
```

By passing the `-c` or `-config` flag, you can specify the path to a micromanager configuration file you want to load. For example:

```bash
python -m micromanager_gui -c path/to/config.cfg
```
