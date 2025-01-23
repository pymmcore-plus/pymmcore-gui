# Info for Contributors

## Setup with uv

Dependencies are managed strictly using [uv](https://docs.astral.sh/uv/), and the
`uv.lock` [lockfile](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile)
is checked into source, to ensure a reproducible environment for all developers.
The lockfile also dictates the exact dependencies that will go into the bundled> [!NOTE]  
application.

To get started, make sure you have
[uv installed](https://docs.astral.sh/uv/getting-started/installation/), then run

```sh
git clone https://github.com/pymmcore-plus/pymmcore-gui.git
cd pymmcore-gui
uv sync
```

That will create a virtual environment at `.venv` in the root directory, and
install all dependencies. Note: `uv sync` will *also* [install
python](https://docs.astral.sh/uv/guides/install-python/) for you if necessary,
so you don't need to have it installed before running the command.

At any time, you can re-run [`uv
sync`](https://docs.astral.sh/uv/reference/cli/#uv-sync) to ensure that your
current environment matches the requirements specified in `uv.lock`.

> [!NOTE]
> The lockfile itself shouldn't be manually edited, but if you need to
> modify the *constraints* of the dependencies, you should do so as usual
> in `pyproject.toml`, and then run `uv lock` to update the lockfile, then
> commit it and open a PR.

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

### Python version support

The "primary" version of python that we target at any time is defined in
`.python-version`. This is the version that will be installed by `uv` if it's
not already present on your system.  We also test against all versions greater
than the minimum version defined in `pyproject.toml` under the
`[project.requires-python]` section.

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

We use [PyInstaller](https://pyinstaller.org/) to freeze the application into a
single, double-clickable executable. The configuration for PyInstaller is
defined in [`app/mmgui.spec`](./app/mmgui.spec).

> [!TIP]
> For details `pyinstaller` and the `mmgui.spec` file, see the [PyInstaller
> documentation](https://pyinstaller.org/en/stable/spec-files.html).

### Locally

To create a bundled application locally , run

```sh
uv run pyinstaller app/mmgui.spec
```

Or, if you have [`just`](https://github.com/casey/just) installed, you can use
the `bundle` task defined in [justfile](./justfile):

```sh
just bundle
```

This will create a double-clickable application in the `dist/` directory.

### On CI (for distribution)

The bundled application is also created on CI using GitHub Actions (it runs on
every push to main, and even for pull-requests). The workflow is defined in
[`.github/workflows/bundle.yml`](./.github/workflows/build.yml).

You can download the latest build artifacts from `main` branch
[here](https://nightly.link/pymmcore-plus/pymmcore-gui/workflows/bundle/main)

For a list of all bundles created (including those from PRs), see the [GitHub
Actions
page](https://github.com/pymmcore-plus/pymmcore-gui/actions/workflows/bundle.yml)
for the bundle workflow.  Click on any given run, and you'll see the artifacts
produced by that run at the bottom.
