from __future__ import annotations

import argparse
import sys
from typing import Sequence

from qtpy.QtWidgets import QApplication

from micromanager_gui import MicroManagerGUI


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
    app.exec_()


if __name__ == "__main__":
    main()
