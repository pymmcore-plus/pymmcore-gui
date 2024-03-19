from __future__ import annotations

from qtpy.QtWidgets import QApplication

from micromanager_gui import MicroManagerGUI


def main() -> None:
    """Run the Micro-Manager GUI."""
    app = QApplication([])
    win = MicroManagerGUI()
    win.show()
    app.exec_()


if __name__ == "__main__":
    main()
