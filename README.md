# pymmcore-gui

**pymmcore-gui** is a Graphical User Interface application for controlling
microscopes via the Micro-Manager core – completely in Python. It unifies the
capabilities of several libraries in the pymmcore-plus ecosystem under one
application. The goal is to provide a pure-Python replacement for the
traditional Java-based [Micro-Manager
GUI](https://github.com/micro-manager/micro-manager), leveraging modern Python
tools for device control, image acquisition, and visualization.

## Overview

pymmcore-gui combines functionality from the following components into one
cohesive desktop app:

- [**pymmcore-plus**](https://github.com/pymmcore-plus/pymmcore-plus): Pythonic
  interface to the Micro-Manager C++ core (MMCore), with an integrated
  multi-dimensional acquisition engine and event system. This provides the
  foundation for microscope device control and complex experiments (using
  `CMMCorePlus` and the `MDAEngine`). `pymmcore-plus` provides the core
  programmatic interface, and may be used independently.
- [**useq-schema**](https://github.com/pymmcore-plus/useq-schema): A schema for
  describing multi-dimensional acquisitions ("MDA sequences") in a
  hardware-agnostic way. `pymmcore-gui` uses this to define and run rich imaging
  protocols (timelapses, z-stacks, channel series, well-plates, grids, etc.).
- [**pymmcore-widgets**](https://github.com/pymmcore-plus/pymmcore-widgets): A
  collection of re-usable Qt widgets for microscope devices and settings ￼.
  These are the building blocks of the GUI’s panels (e.g. camera controls, stage
  control, property browsers, acquisition setup forms), ensuring that all device
  control UI is robust and consistent.
- [**ndv**](https://github.com/pyapp-kit/ndv): A lightweight – but capable –
  n-dimensional image viewer for live and captured images. NDV provides fast,
  minimal-dependency image visualization, allowing `pymmcore-gui` to display
  camera feeds and multi-dimensional datasets without relying on heavier/slower
  frameworks (i.e. it avoids the need for napari).

By integrating these components, `pymmcore-gui` offers a comprehensive
microscope control interface similar in spirit to Micro-Manager’s MMStudio, but
running entirely in Python (via Qt for the GUI) instead of Java, and
facilitating Python devices and image-processing and analysis routines. The
interface should be familiar to Micro-Manager users, but more flexible, modern,
and user-extensible, benefitting from the Python ecosystem.

### Status

This project is under active development, but it is already a working
product (no longer just an aspirational prototype). Many planned features have
been implemented, and it can be used for real microscope control and image
acquisition.

## Installation

There are two primary ways to install and use pymmcore-gui:

- **Download the Standalone Application**: We provide pre-built, double-clickable
  application packages for easy installation. These bundles include the Python
  runtime and all necessary dependencies. You can download the latest automated
  build for Windows or macOS from our [Nightly Builds server] ￼ ￼ (look for the
  pymmgui-Windows.zip or pymmgui-macOS.zip). Simply download and extract the
  archive, then run the application:
  - On **Windows**: run the pymmcore-gui.exe (after extracting the zip).
  - On **macOS**: open the pymmcore-gui.app (you may need to bypass Gatekeeper on the
    first run).
  - On **Linux**: a Linux bundle may be provided in the future. For now, Linux
    users can run from source – see below.)
- **Install via Python for use as a library**: You may also install pymmcore-gui
  into a python environment:
  
  ```sh
  pip install git+https://github.com/pymmcore-plus/pymmcore-gui
  mmcore install
  ```

  This will install the `pymmcore_gui` Python package, and `mmcore install` will
  fetch the latest micro-manager device adapters, allowing you to launch the GUI
  from a Python session or integrate it into custom scripts.

## Usage

**Launching the GUI (Standalone)**: If you installed the bundled app, simply
double-click the application to launch it. You should see the main window
appear, which includes menus and panels for device control, configuration, live
view, etc. By default, if no configuration is loaded, the GUI will use
Micro-Manager’s Demo devices (so you can try it even without real hardware). You
can then load a different hardware configuration (from the "Devices" menu) or use
the Hardware Config Wizard to connect to hardware.

**Launching via Python**: You can also start the GUI from an interactive Python
session or script. This is useful if you want to script around the GUI or
integrate it with other Python code. Simply import the library and call the
`create_mmgui()` function:

```python
from pymmcore_gui import create_mmgui
create_mmgui()
```

This will initialize the application and show the main GUI window.

If you would like to further customize the GUI before starting the application:

```python
from pymmcore_gui import create_mmgui
from PyQt6.QtWidgets import QApplication

window = create_mmgui(exec_app=False)

# customize the app or do other setup here
# mmcore = window.mmcore  # access the CMMCorePlus used by the GUI

QApplication.instance().exec()  # Start the Qt event loop
```

If you already have a CMMCorePlus instance you want the GUI to use, you
can pass it to `create_mmgui(mmcore=my_core)`. By default the GUI will first
check if there is a global singleton (`CMMCorePlus.instance()`), and if not,
it will create a new instance.

Once launched, you can interact with the GUI just as you would with
Micro-Manager Studio: select devices, adjust properties, snap images, start live
view, and run multi-dimensional acquisitions. Images acquired will be displayed
in the `ndv` viewer component embedded in the GUI. You can save images or datasets
via the GUI’s save functions – by default using Micro-Manager’s image file
formats.

## Getting Started for Developers

If you are interested in contributing to pymmcore-gui or running it from source
for development, please see our [CONTRIBUTING.md](./CONTRIBUTING.md) guide for
setup instructions and development notes ￼. In brief, you can clone this
repository and set up a development environment to run the latest code. The
contributing guide covers how to install in editable mode, run tests, and the
architectural patterns (e.g. settings management, plugins) used in the project.

We welcome contributions and feedback! Feel free to open issues for bug reports
or feature requests, and join in the discussion. The intent of this project is
to bring together the community’s efforts on a Python-based Micro-Manager GUI
into a single application, without hindering the ability to experiment
independently. By collaborating here, we hope to avoid duplicate work and
create a robust, extensible tool for microscope control in Python.

## Background

This project builds upon several prior efforts in the Python microscopy
community:

- [**napari-micromanager**](https://github.com/pymmcore-plus/napari-micromanager):
  A plugin using Napari as the viewer and pymmcore-widgets for UI. It
  demonstrated Micro-Manager control in a python GUI. While it doesn't receive
  active updates, it remains usable for those who prefer a napari-based
  workflow.
- **Independent GUIs**: Experimental apps like [micromanager-gui by @fdrgsp】 and
  [pymmcore-plus-sandbox by @gselzer] explored standalone interfaces ￼ ￼.
  Lessons from these prototypes (and others at labs like LEB-EPFL) have
  influenced pymmcore-gui’s design.

By unifying ideas from these projects, pymmcore-gui aims to provide a single,
officially supported application. Our design goal is a user experience familiar
to Micro-Manager users (for example, one prototype mimicked the MMStudio layout
￼), while taking advantage of Python’s flexibility and the growing ecosystem of
scientific libraries.

------------------------------------------

**License**: This project is provided under the BSD-3-Clause license.
