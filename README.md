# pymmcore-gui

*Name pending – this is a working title for the project*

**pymmcore-gui** is a Graphical User Interface application for controlling
microscopes via the Micro-Manager core – completely in Python. It unifies the
capabilities of several libraries in the pymmcore-plus ecosystem under one
application. The goal is to provide a pure-Python replacement for the
traditional Java-based Micro-Manager GUI (also known as [MMStudio, and its
plugins](https://github.com/micro-manager/micro-manager)), leveraging modern
Python tools for device control, image acquisition, and visualization.

| [🔗 Skip to Installation ...](#-installation)|
| :--- |

## ✅ Project Status

`pymmcore-gui` has evolved from an experimental prototype into a working
application with:

- ✅ Complete device control and configuration
- ✅ Multi-dimensional acquisition workflows *(time, z, channels, plates, etc.)*
- ✅ Real-time image preview and acquisition visualization (2D and 3D)
- ✅ Customizable layouts and docking interface
- ✅ Integrated interactive IPython console
- ✅ Application bundle for easy distribution

Primary targets for improvement include:

- 📈 Better file I/O  
  *there are currently ways to save to OME-TIFF and OME-ZARR, but we want to
  improve them*
- 📈 Better metadata preservation in file outputs
- 📈 Performance optimizations
- 📈 Clearer paths for customizing the user interface (custom widgets, etc...)
- 📈 Theming and styles

## 👋 Have Questions or Ideas?  Looking for Help?

We love knowing that you're out there!  There are several ways to get in touch
with the pymmcore-plus community:

|If you want to... | Go here! |
|-|-|
| 🙋‍♀️ Ask a general question to the community | [![Image.sc Forum](https://img.shields.io/badge/Image.sc-Forum-green?style=for-the-badge&logo=discourse)](https://forum.image.sc/tag/pymmcore-plus) |
| 🐛 Report a bug<br>✨ Request a feature | [![GitHub Issues](https://img.shields.io/badge/GitHub-Issues-magenta?style=for-the-badge&logo=github)](https://github.com/pymmcore-plus/pymmcore-gui/issues) |
| 💬 Chat in real-time with developers | [![Zulip chat](https://img.shields.io/badge/Zulip-Chat-blue?style=for-the-badge&logo=zulip)](https://imagesc.zulipchat.com/#narrow/channel/442785-pymmcore.5B-plus.5D) |

## 🛠️ pymmcore-plus Ecosystem

`pymmcore-gui` combines functionality from the following components into one
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
  collection of reusable Qt widgets for microscope devices and settings.
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
and user-extensible, benefiting from the Python ecosystem.

All of these components are designed to work together, but can also be used
independently.

## 🚀 Installation

There are two primary ways to install and use pymmcore-gui:

### 🐍 Python Package
  
  ```sh
  # install this package (for now, just install from GitHub)
  pip install git+https://github.com/pymmcore-plus/pymmcore-gui
  
  # install micro-manager device adapters
  mmcore install

  # run the app
  mmgui
  ```

> [!NOTE]
> Since the GitHub version may change at any time, it is recommended
> to pin a specific `<commit-or-tag>` if you are adding this to your
> pyproject.toml dependencies.
>
> ```toml
> [project]
> dependencies = [
>     "pymmcore-gui @ git+https://github.com/pymmcore-plus/pymmcore-gui@<commit-or-tag>"
> ]
>

### 📦 Bundled Application

  For those wanting a fully contained, double-clickable application, we provide
  pre-built bundles that include the Python runtime and all necessary
  dependencies.
  
  You can download the latest nightly bundled applications
  [here](https://nightly.link/pymmcore-plus/pymmcore-gui/workflows/bundle/main).
  Simply download and extract the archive, then run the application.

> [!NOTE]
> The bundled application does *not* include Micro-Manager device adapters,
> these must be installed separately. (This may be done using the `Devices >
> Install Devices ...` menu in the GUI, or by running `mmcore install` from
> the command line.)

## 🖥️ Usage

### Launching the GUI (Standalone)

If you installed the bundled app, simply double-click the application to launch
it. You should see the main window appear, which includes menus and panels for
device control, configuration, live view, etc. By default, if no configuration
is loaded, the GUI will use Micro-Manager’s Demo devices (so you can try it even
without real hardware). You can then load a different hardware configuration
(from the "Devices" menu) or use the Hardware Config Wizard to connect to
hardware.

### Launching via Python (CLI)

If you installed pymmcore-gui into a Python environment, you can launch the
GUI from the command line using the `mmgui` command:

```bash
mmgui
```

### Launching via Python (Script)

You can also start the GUI from a Python session or script. This is
useful if you want to script around the GUI or integrate it with other Python
code. Simply import the library and call the `create_mmgui()` function:

```python
from pymmcore_gui import create_mmgui

create_mmgui()
```

This will initialize the application and show the main GUI window.

### Customizing Before Launch (Script)

If you would like to *further* customize the GUI before starting the application,
pass `exec_app=False` to `create_mmgui()`. This will return the main window,
allowing you to modify it before starting the Qt event loop:

```python
from pymmcore_gui import create_mmgui
from PyQt6.QtWidgets import QApplication

# (you do not need to create a QApplication instance)

window = create_mmgui(exec_app=False)

# customize the app or do other setup here
# mmcore = window.mmcore  # access the CMMCorePlus used by the GUI

QApplication.instance().exec()  # Start the Qt event loop
```

If you already have a `CMMCorePlus` instance that you want the GUI to use, you
can pass it to `create_mmgui(mmcore=my_core)`. By default the GUI will first
check if there is a global singleton (`CMMCorePlus.instance()`), and if not, it
will create a new instance.

## Prior Work

This project builds upon several prior efforts in the Python microscopy
community:

- [**napari-micromanager**](https://github.com/pymmcore-plus/napari-micromanager):
  A plugin using Napari as the viewer and pymmcore-widgets for UI. It
  demonstrated Micro-Manager control in a Python GUI. While it doesn't receive
  active updates, it remains usable for those who prefer a napari-based
  workflow.
- [**micromanager-gui**](https://github.com/fdrgsp/micromanager-gui) by Federico
  Gasparoli.
- [**pymmcore-plus-sandbox**](https://github.com/gselzer/pymmcore-plus-sandbox)
  by Gabe Selzer.

Lessons from these prototypes (and others at labs like LEB-EPFL) have influenced
pymmcore-gui’s design.

By unifying ideas from these projects, pymmcore-gui aims to provide a single,
officially supported application. Our design goal is a user experience familiar
to Micro-Manager users (for example, one prototype mimicked the MMStudio
layout), while taking advantage of Python’s flexibility and the growing
ecosystem of scientific libraries.

## Getting Started for Developers

The [contributing guide](CONTRIBUTING.md) covers development environment setup,
and architectural patterns used in the project. Briefly:

```bash
git clone https://github.com/pymmcore-plus/pymmcore-gui.git
cd pymmcore-gui
uv sync
uv run mmgui
uv run pytest
```

We welcome contributions and feedback! Feel free to open issues for bug reports
or feature requests, and join in the discussion.

------------------------------------------

### Licenses

This project and all pymmcore-plus ecosystem projects are provided under the
BSD-3-Clause license.  

> [!NOTE]
> The bundled [application](#-bundled-application) currently includes PyQt6,
> which is licensed under the GNU General Public License v3.0. This means the
> bundled application is distributed as a combined work under the terms of the
> GNU General Public License v3.0.  (If that is limiting for you, please reach
> out, we may be able to provide a PySide6-based version in the future)

It depends on the [C++ MMCore and
Devices](https://github.com/micro-manager/mmCoreAndDevices) which are licensed
under either LGPL and BSD-3-Clause, depending on the device or module.
