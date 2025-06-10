#!/usr/bin/env python3
"""
Debug script to investigate memory leak in NDVPreview widget.
This will help us track object references and identify why the RingBuffer persists.
"""

import gc
import sys
import weakref
from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6Ads import CDockWidget

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview


def get_referrers(obj: Any, max_depth: int = 2) -> list:
    """Get objects that reference the given object."""
    referrers = []
    for referrer in gc.get_referrers(obj):
        if referrer is not obj and referrer is not locals() and referrer is not globals():
            try:
                ref_type = type(referrer).__name__
                ref_info = f"{ref_type}: {str(referrer)[:100]}"
                referrers.append(ref_info)
            except Exception:
                referrers.append(f"{type(referrer).__name__}: <repr failed>")
    return referrers[:10]  # Limit to first 10 to avoid spam


def debug_memory_leak():
    """Debug the memory leak step by step."""

    print("=== Starting Memory Leak Debug ===")

    # Create the GUI
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        print("QApplication created")
        gui = MicroManagerGUI()
        print("MicroManagerGUI created")
        gui.mmcore.initializeCircularBuffer()
        print("CircularBuffer initialized")

    print(f"Initial object count: {len(gc.get_objects())}")

    # Take some snapshots to create the preview
    core = gui.mmcore
    for i in range(5):
        core.snapImage()

    # Get the dock widget and preview
    dw = gui.dock_manager.dockWidgetsMap().get("Preview")
    assert isinstance(dw, CDockWidget)
    ndv_preview = dw.widget()
    assert isinstance(ndv_preview, NDVPreview)

    # Create weak references to track objects
    buffer_ref = weakref.ref(ndv_preview._buffer)
    viewer_ref = weakref.ref(ndv_preview._viewer)
    preview_ref = weakref.ref(ndv_preview)
    dw_ref = weakref.ref(dw)

    print(f"Buffer object: {ndv_preview._buffer}")
    print(f"Buffer capacity: {ndv_preview._buffer.max_capacity}")
    print(f"Buffer length: {len(ndv_preview._buffer)}")
    print(f"Viewer object: {ndv_preview._viewer}")

    # Print references to the buffer
    print("\n=== BEFORE CLEANUP ===")
    if buffer_ref():
        print("Buffer referrers:")
        for ref in get_referrers(buffer_ref()):
            print(f"  - {ref}")

    print(f"Object count before cleanup: {len(gc.get_objects())}")

    # Now try to clean up
    print("\n=== CLEANUP PROCESS ===")

    # Step 1: Detach the preview
    print("1. Detaching preview...")
    ndv_preview.detach()

    # Step 2: Close dock widget
    print("2. Closing dock widget...")
    dw.closeDockWidgetInternal(True)

    # Step 3: Delete dock widget
    print("3. Deleting dock widget...")
    dw.deleteLater()

    # Step 4: Cleanup viewers manager
    print("4. Cleaning up viewers manager...")
    viewers_manager = gui._viewers_manager
    viewers_manager._cleanup_current_image_preview()

    # Process events
    print("5. Processing events...")
    app.processEvents()

    # Force garbage collection
    print("6. Forcing garbage collection...")
    gc.collect()
    gc.collect()

    print(f"Object count after cleanup: {len(gc.get_objects())}")

    # Check if objects still exist
    print("\n=== AFTER CLEANUP ===")
    print(f"Buffer still alive: {buffer_ref() is not None}")
    print(f"Viewer still alive: {viewer_ref() is not None}")
    print(f"Preview still alive: {preview_ref() is not None}")
    print(f"DockWidget still alive: {dw_ref() is not None}")

    if buffer_ref():
        print("\nBuffer is still alive! Referrers:")
        for ref in get_referrers(buffer_ref()):
            print(f"  - {ref}")

    if viewer_ref():
        print("\nViewer is still alive! Referrers:")
        for ref in get_referrers(viewer_ref()):
            print(f"  - {ref}")

    if preview_ref():
        print("\nPreview is still alive! Referrers:")
        for ref in get_referrers(preview_ref()):
            print(f"  - {ref}")

    # Clean up
    gui.close()
    gui.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    debug_memory_leak()
