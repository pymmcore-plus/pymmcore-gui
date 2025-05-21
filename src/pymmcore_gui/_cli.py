import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import typer

import pymmcore_gui

__all__ = ["app", "main"]
app = typer.Typer(
    name="mmgui",
    add_completion=False,
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
)


def _show_version_and_exit(value: bool) -> None:
    if value:
        import pymmcore_plus

        typer.echo(f"pymmcore-gui v{pymmcore_gui.__version__}")
        typer.echo(f"pymmcore-plus v{pymmcore_plus.__version__}")
        try:  # pragma: no cover
            import pymmcore_nano as pymmcore  # type: ignore [import-not-found]

            typer.echo(f"pymmcore-nano v{pymmcore.__version__}")
        except ImportError:  # pragma: no cover
            import pymmcore

            typer.echo(f"pymmcore v{pymmcore.__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        callback=_show_version_and_exit,
        help="Show version and exit.",
        is_eager=True,
    ),
    config: Path | None = typer.Option(
        None,
        "-c",
        "--config",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Path to MM hardware config file.",
    ),
) -> None:
    """mmgui: pymmcore-gui command line (v{version}).

    For additional help on a specific command: type `mmgui [command] --help`

    The default command is `mmgui run`, use `mmgui run --help` for more options.
    """
    # fix for windows CI encoding and emoji printing
    if getattr(sys.stdout, "encoding", None) != "utf-8":
        with suppress(AttributeError):  # pragma: no cover
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore [union-attr]
    if ctx.invoked_subcommand is None:
        app(args=["run", *sys.argv[1:]])


if "mkdocs" in sys.argv[0]:  # pragma: no cover
    _main.__doc__ = (_main.__doc__ or "").replace(" (v{version})", "")
else:
    _main.__doc__ = typer.style(
        (_main.__doc__ or "").format(version=pymmcore_gui.__version__),
        fg=typer.colors.BRIGHT_YELLOW,
    )


@app.command()
def run(
    config: Path | None = typer.Option(
        None,
        "-c",
        "--config",
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        help="Path to MM hardware config file.",
    ),
    demo_config: bool = typer.Option(
        False,
        "--demo-config",
        help="Launch with demo configuration.",
    ),
    no_telemetry: bool = typer.Option(
        False,
        "--no-telemetry",
        help="Disable telemetry.",
    ),
) -> None:
    """Run the Micro-Manager GUI (this is the default command)."""
    from pymmcore_gui import create_mmgui

    mm_config = "MMConfig_demo.cfg" if demo_config else config
    create_mmgui(mm_config=mm_config, exec_app=True, install_sentry=not no_telemetry)
    sys.exit(0)


def _open_path(path: Path, just_reveal: bool = False) -> None:  # pragma: no cover
    path_ = str(path.resolve())
    if sys.platform.startswith("darwin"):
        if just_reveal:
            subprocess.run(["open", "-R", path_])
        else:
            subprocess.run(["open", path_])
    elif os.name == "nt":
        if just_reveal:
            subprocess.run(["explorer", "/select,", path_])
        else:
            subprocess.run(["explorer", path_])
    elif os.name == "posix":
        if just_reveal:
            subprocess.run(["xdg-open", str(path.parent)])
        else:
            subprocess.run(["xdg-open", path_])
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
    typer.secho(
        f"Opening settings file in default editor: {path_}",
        fg=typer.colors.BRIGHT_GREEN,
    )


@app.command()
def settings(
    ctx: typer.Context,
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Reset settings to default values.",
    ),
    edit: bool = typer.Option(
        False,
        "--edit",
        help="Open settings file in default editor.",
    ),
    reveal: bool = typer.Option(
        False,
        "--reveal",
        help="Reveal settings file in file explorer.",
    ),
) -> None:
    """Configure application settings."""
    from pymmcore_gui._settings import SETTINGS_FILE_NAME

    if not SETTINGS_FILE_NAME.exists():
        typer.secho(
            f"No settings have been created at: {SETTINGS_FILE_NAME}",
            fg=typer.colors.RED,
        )

    if reset:
        from pymmcore_gui._settings import reset_to_defaults

        reset_to_defaults()
        typer.secho("Settings reset to defaults.", fg=typer.colors.BRIGHT_GREEN)
        raise typer.Exit(0)

    if edit or reveal:
        _ensure_settings(SETTINGS_FILE_NAME)
        _open_path(SETTINGS_FILE_NAME, just_reveal=reveal)
        raise typer.Exit(0)

    ctx.get_help()
    raise typer.Exit(0)


def _ensure_settings(path: Path) -> None:
    if not path.exists():
        typer.secho(
            f"No settings have been created at: {path}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


def main() -> None:
    """Main entry point for the Micro-Manager GUI."""
    app()
