import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import typer

import pymmcore_gui

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
            import pymmcore_nano as pymmcore

            typer.echo(f"pymmcore-nano v{pymmcore.__version__}")
        except ImportError:  # pragma: no cover
            import pymmcore

            typer.echo(f"pymmcore v{pymmcore.__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_show_version_and_exit,
        help="Show version and exit.",
        is_eager=True,
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


def _open_in_default_editor() -> None:  # pragma: no cover
    from pymmcore_gui._settings import SETTINGS_FILE_NAME

    if not SETTINGS_FILE_NAME.exists():
        typer.secho(
            f"Settings file does not exist: {SETTINGS_FILE_NAME}",
            fg=typer.colors.RED,
        )
    else:
        path = str(SETTINGS_FILE_NAME.resolve())
        if sys.platform.startswith("darwin"):
            subprocess.run(["open", path], check=True)
        elif os.name == "nt":
            os.startfile(path)
        elif os.name == "posix":
            subprocess.run(["xdg-open", path], check=True)
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
        typer.secho(
            f"Opening settings file in default editor: {path}",
            fg=typer.colors.BRIGHT_GREEN,
        )


@app.command()
def settings(
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
) -> None:
    """Configure application settings."""
    if reset:
        from pymmcore_gui._settings import reset_to_defaults

        reset_to_defaults()
        typer.secho("Settings reset to defaults.", fg=typer.colors.BRIGHT_GREEN)
        raise typer.Exit()

    if edit:
        _open_in_default_editor()
        raise typer.Exit(0)

    _show_help_for_command(settings)


def _show_help_for_command(func: Callable) -> None:
    info = next((cmd for cmd in app.registered_commands if cmd.callback == func), None)
    cmd = typer.main.get_command_from_info(
        info,  # type: ignore
        pretty_exceptions_short=True,
        rich_markup_mode="rich",
    )
    ctx = typer.Context(cmd)
    typer.echo(ctx.get_help())
    raise typer.Exit()


def main() -> None:
    """Main entry point for the Micro-Manager GUI."""
    if len(sys.argv) == 1:
        app(args=["run"])
    elif sys.argv[1] in ("-h", "--help"):
        # show help normally
        app()
    else:
        # prepend "default" if user didn't specify a command
        first_arg = sys.argv[1]
        if first_arg.startswith("-"):
            app(args=["run", *sys.argv[1:]])
        else:
            app()
