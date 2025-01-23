# Info for Contributors

## Setup with uv

Dependencies are managed strictly using [uv](https://docs.astral.sh/uv/), and the
`uv.lock` [lockfile](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile)
is checked into source, to ensure a reproducible environment for all developers.
The lockfile also dictates the exact dependencies that will go into the bundled application.

To get started, make sure you have
[uv installed](https://docs.astral.sh/uv/getting-started/installation/), then run

```sh
git clone https://github.com/pymmcore-plus/pymmcore-gui.git
cd pymmcore-gui
uv sync
```

That will create a virtual environment at `.venv` in the root directory, and install
all dependencies.

At any time, you can run `uv sync` to ensure that your current environment matches
the requirements specified in `uv.lock`. The lockfile itself shouldn't be manually
edited, but if you need to modify the *constraints* of the dependencies, you should
do so in the normal way in `pyproject.toml`, and then run `uv lock` to update the
lockfile, then commit it and open a PR.

### Activating the virtual environment (optional)

If you want to activate the virtual environment to run commands directly (without
preceding everything with `uv run`), run:

On windows:

```cmd
.venv\Scripts\activate
```

On linux/mac:

```sh
source .venv/bin/activate
```

## Running the GUI

To run the GUI, just run

```sh
uv run mmgui
```

(*or... just `mmgui` if you've [activated your virtual
environment](#activating-the-virtual-environment-optional)*)

> [!TIP]
> This script is defined in `pyproject.toml` under the `[project.scripts]` section.

## Testing

You can run the tests with

```sh
uv run pytest
```

(*or... just `pytest` if you've [activated your virtual
environment](#activating-the-virtual-environment-optional)*)

## Creating a bundled application

To create a bundled application, run

```sh
uv run pyinstaller app/mmgui.spec
```

Or, if you have [`just`](https://github.com/casey/just) installed, you can use
the `bundle` task defined in [justfile](./justfile):

```sh
just bundle
```

This will create a double-clickable application in the `dist/` directory.
