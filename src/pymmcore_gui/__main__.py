import argparse
import sys
from collections.abc import Sequence

from pymmcore_gui._app import create_mmgui


def _parse_args(args: Sequence[str] = ()) -> argparse.Namespace:
    if not args:
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
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Reset settings to default values and exit.",
    )

    return parser.parse_args(args)


def main() -> None:
    """Main entry point for the Micro-Manager GUI."""
    args = _parse_args()
    if args.reset:
        from pymmcore_gui._settings import reset_to_defaults

        reset_to_defaults()
        print("Settings reset to defaults.")
        sys.exit(0)

    create_mmgui(mm_config=args.config, exec_app=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
