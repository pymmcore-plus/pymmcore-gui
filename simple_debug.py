#!/usr/bin/env python3
"""Simple debug script to track memory references in NDVPreview."""

import gc
import sys
import weakref

from PyQt6.QtWidgets import QApplication
from PyQt6Ads import CDockWidget

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview


def main():
    print("=== Memory Debug Script ===")

    app = QApplication.instance() or QApplication(sys.argv)
    gui = MicroManagerGUI()
    gui.mmcore.initializeCircularBuffer()

    print("Taking snapshots...")
    for _ in range(5):
        gui.mmcore.snapImage()

    # Get the preview widget
    dw = gui.dock_manager.dockWidgetsMap().get("Preview")
    if not isinstance(dw, CDockWidget):
        print("No Preview dock widget found!")
        return

    ndv_preview = dw.widget()
    if not isinstance(ndv_preview, NDVPreview):
        print("No NDVPreview widget found!")
        return

    # Create weak references to track lifecycle
    buffer_ref = weakref.ref(ndv_preview._buffer) if ndv_preview._buffer else None
    viewer_ref = weakref.ref(ndv_preview._viewer)

    print(f"Buffer exists: {ndv_preview._buffer is not None}")
    if ndv_preview._buffer:
        print(f"Buffer length: {len(ndv_preview._buffer)}")
        print(f"Buffer id: {id(ndv_preview._buffer)}")

    print(f"Viewer id: {id(ndv_preview._viewer)}")

    # Check references before cleanup
    print("\n=== BEFORE CLEANUP ===")
    if buffer_ref and buffer_ref():
        refs = gc.get_referrers(buffer_ref())
        print(f"Buffer has {len(refs)} referrers")
        for i, ref in enumerate(refs[:5]):  # Show first 5
            print(f"  {i}: {type(ref).__name__}")

    # Now cleanup
    print("\n=== CLEANUP ===")
    ndv_preview.detach()
    dw.closeDockWidgetInternal(True)
    dw.deleteLater()
    gui._viewers_manager._cleanup_current_image_preview()

    app.processEvents()
    gc.collect()

    # Check if objects still exist
    print("\n=== AFTER CLEANUP ===")
    print(f"Buffer still alive: {buffer_ref() is not None if buffer_ref else 'N/A'}")
    print(f"Viewer still alive: {viewer_ref() is not None}")

    if buffer_ref and buffer_ref():
        print("Buffer is still alive!")
        refs = gc.get_referrers(buffer_ref())
        print(f"Buffer still has {len(refs)} referrers")
        for i, ref in enumerate(refs[:5]):
            print(f"  {i}: {type(ref).__name__}")

    gui.close()


if __name__ == "__main__":
    main()
