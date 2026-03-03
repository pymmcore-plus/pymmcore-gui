"""Diagnostic script to detect window-level events on first snap."""

from __future__ import annotations

import sys
import time
from typing import Any

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import QWidget

_t0 = time.perf_counter()


def _ts() -> str:
    return f"{time.perf_counter() - _t0:8.4f}s"


class WindowEventSpy(QObject):
    """Logs window-level events."""

    WATCHED = {
        QEvent.Type.Show,
        QEvent.Type.Hide,
        QEvent.Type.Close,
        QEvent.Type.Resize,
        QEvent.Type.Move,
        QEvent.Type.WindowStateChange,
        QEvent.Type.WindowActivate,
        QEvent.Type.WindowDeactivate,
        QEvent.Type.ActivationChange,
        QEvent.Type.WinIdChange,
        QEvent.Type.PlatformSurface,
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._snap_count = 0
        self._active = False

    def activate(self) -> None:
        self._active = True

    def bump_snap(self) -> None:
        self._snap_count += 1
        print(f"\n{'=' * 60}", flush=True)
        print(f"[{_ts()}] === SNAP #{self._snap_count} ===", flush=True)
        print(f"{'=' * 60}", flush=True)

    def eventFilter(self, a0: QObject, a1: QEvent) -> bool:  # type: ignore [override]
        if not self._active:
            return False
        etype = a1.type()
        if etype not in self.WATCHED:
            return False

        name = etype.name if hasattr(etype, "name") else str(etype)
        extra = ""
        if etype == QEvent.Type.Resize and isinstance(a0, QWidget):
            extra = f" -> {a0.size().width()}x{a0.size().height()}"
        elif etype == QEvent.Type.PlatformSurface:
            from PyQt6.QtGui import QPlatformSurfaceEvent

            if isinstance(a1, QPlatformSurfaceEvent):
                st = a1.surfaceEventType()
                ct = QPlatformSurfaceEvent.SurfaceEventType.SurfaceCreated
                extra = f" -> {'CREATED' if st == ct else 'ABOUT_TO_DESTROY'}"

        obj_name = getattr(a0, "objectName", lambda: "")()
        cls_name = type(a0).__name__
        is_main = isinstance(a0, QWidget) and a0.isWindow()
        is_critical = etype in {
            QEvent.Type.WinIdChange,
            QEvent.Type.PlatformSurface,
            QEvent.Type.Hide,
            QEvent.Type.Show,
            QEvent.Type.Close,
            QEvent.Type.WindowStateChange,
        }
        if is_main or is_critical:
            tag = "WINDOW" if is_main else "widget"
            print(
                f"[{_ts()}] {tag:>6} | {name:<25} {cls_name}({obj_name!r}){extra}",
                flush=True,
            )
        return False


def main() -> None:
    global _t0

    from pymmcore_gui._app import MMQApplication
    from pymmcore_gui._main_window import MicroManagerGUI

    app = MMQApplication(sys.argv)
    _t0 = time.perf_counter()
    win = MicroManagerGUI()

    spy = WindowEventSpy()

    win.installEventFilter(spy)
    for child in win.findChildren(QWidget):
        child.installEventFilter(spy)

    original_add = win.dock_manager.addDockWidgetTabToArea

    def patched_add(Dockwidget: Any, DockAreaWidget: Any, Index: int = -1) -> Any:
        print(f"\n[{_ts()}] >>> addDockWidgetTabToArea <<<", flush=True)
        if Dockwidget is not None:
            Dockwidget.installEventFilter(spy)
            for child in Dockwidget.findChildren(QWidget):
                child.installEventFilter(spy)
        result = original_add(Dockwidget, DockAreaWidget, Index)
        if Dockwidget is not None:
            for child in Dockwidget.findChildren(QWidget):
                child.installEventFilter(spy)
        print(f"[{_ts()}] >>> addDockWidgetTabToArea done <<<", flush=True)
        return result

    win.dock_manager.addDockWidgetTabToArea = patched_add  # type: ignore

    win._mmc.loadSystemConfiguration("MMConfig_demo.cfg")

    win.show()
    print(f"\n[{_ts()}] Window shown.", flush=True)

    if wh := win.windowHandle():
        wh.installEventFilter(spy)

    def do_snap(n: int) -> None:
        spy.bump_snap()
        spy.activate()
        print(f"[{_ts()}] Calling mmc.snapImage()...", flush=True)
        win._mmc.snapImage()
        print(f"[{_ts()}] snapImage() returned.", flush=True)
        if n < 2:
            QTimer.singleShot(1000, lambda: do_snap(n + 1))
        else:
            print(f"\n[{_ts()}] All snaps done. Quitting.", flush=True)
            QTimer.singleShot(500, app.quit)

    QTimer.singleShot(1000, lambda: do_snap(1))

    app.exec()
    print(f"[{_ts()}] App exited.", flush=True)


if __name__ == "__main__":
    main()
