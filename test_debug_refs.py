import gc
import weakref
from collections.abc import Iterator

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6Ads import CDockWidget
from pytestqt.qtbot import QtBot

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview


@pytest.fixture
def gui(qtbot: QtBot, qapp: QApplication) -> Iterator[MicroManagerGUI]:
    gui = MicroManagerGUI()
    # exclude this from memory leak checks
    gui.mmcore.initializeCircularBuffer()
    qtbot.addWidget(gui)
    yield gui


def test_debug_memory_refs(
    gui: MicroManagerGUI, qapp: QApplication, qtbot: QtBot
) -> None:
    """Debug test to track what's holding references to the buffer."""
    core = gui.mmcore

    # Take some snapshots to create the preview
    for _ in range(5):
        core.snapImage()
    qtbot.wait(20)

    dw = gui.dock_manager.dockWidgetsMap().get("Preview")
    assert isinstance(dw, CDockWidget)
    ndv_preview = dw.widget()
    assert isinstance(ndv_preview, NDVPreview)
    ndv_viewer = ndv_preview._viewer
    qtbot.waitUntil(lambda: ndv_viewer.data is not None, timeout=2000)
    assert ndv_viewer.data is not None

    # Create weak references to track objects
    buffer_ref = weakref.ref(ndv_preview._buffer) if ndv_preview._buffer else None
    viewer_ref = weakref.ref(ndv_preview._viewer)
    preview_ref = weakref.ref(ndv_preview)

    print("\nBefore cleanup:")
    print(f"Buffer exists: {ndv_preview._buffer is not None}")
    if ndv_preview._buffer:
        print(f"Buffer length: {len(ndv_preview._buffer)}")
        print(f"Buffer id: {id(ndv_preview._buffer)}")

        # Get direct referrers to the buffer
        refs = gc.get_referrers(ndv_preview._buffer)
        print(f"Buffer has {len(refs)} direct referrers:")
        for i, ref in enumerate(refs[:10]):  # Show first 10
            ref_type = type(ref).__name__
            if hasattr(ref, "__name__"):
                ref_name = getattr(ref, "__name__", "unnamed")
                print(f"  {i}: {ref_type} ({ref_name})")
            else:
                print(f"  {i}: {ref_type}")

    print(f"Viewer id: {id(ndv_preview._viewer)}")

    # Now do the cleanup
    print("\nStarting cleanup...")

    # Explicitly detach the preview widget before closing
    preview_widget = dw.widget()
    if isinstance(preview_widget, NDVPreview):
        preview_widget.detach()

    # Close and destroy the dock widget completely to force recreation next time
    dw.closeDockWidgetInternal(True)
    dw.deleteLater()

    # Force a complete cleanup of the viewers manager's preview reference
    viewers_manager = gui._viewers_manager
    viewers_manager._cleanup_current_image_preview()

    # Force garbage collection and Qt cleanup after closing the dock widget
    gc.collect()
    qapp.processEvents()
    gc.collect()

    # Give some time for cleanup to complete and process any pending deletions
    qtbot.wait(10)
    qapp.processEvents()
    gc.collect()

    print("\nAfter cleanup:")
    print(f"Buffer still alive: {buffer_ref() is not None if buffer_ref else 'N/A'}")
    print(f"Viewer still alive: {viewer_ref() is not None}")
    print(f"Preview still alive: {preview_ref() is not None}")

    if buffer_ref and buffer_ref():
        print("Buffer is still alive! Finding referrers...")
        refs = gc.get_referrers(buffer_ref())
        print(f"Buffer still has {len(refs)} referrers:")
        for i, ref in enumerate(refs[:10]):
            ref_type = type(ref).__name__
            if hasattr(ref, "__name__"):
                ref_name = getattr(ref, "__name__", "unnamed")
                print(f"  {i}: {ref_type} ({ref_name})")
            else:
                print(f"  {i}: {ref_type}")

        # Try to find the path to the buffer
        import sys

        ref_count = sys.getrefcount(buffer_ref())
        print(f"Buffer reference count: {ref_count}")
