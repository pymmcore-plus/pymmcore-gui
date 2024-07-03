from __future__ import annotations

import argparse
import sys
import traceback
from typing import TYPE_CHECKING, Sequence

from qtpy.QtWidgets import QApplication

from micromanager_gui import MicroManagerGUI

if TYPE_CHECKING:
    from types import TracebackType


def main(args: Sequence[str] | None = None) -> None:
    """Run the Micro-Manager GUI."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Enter string")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Config file to load",
        nargs="?",
    )
    parsed_args = parser.parse_args(args)

    app = QApplication([])
    win = MicroManagerGUI(config=parsed_args.config)
    win.show()

    sys.excepthook = _our_excepthook
    app.exec_()


def _our_excepthook(
    type: type[BaseException], value: BaseException, tb: TracebackType | None
) -> None:
    """Excepthook that prints the traceback to the console.

    By default, Qt's excepthook raises sys.exit(), which is not what we want.
    """
    # this could be elaborated to do all kinds of things...
    traceback.print_exception(type, value, tb)


if __name__ == "__main__":
    main()
