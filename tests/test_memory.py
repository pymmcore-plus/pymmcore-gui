from __future__ import annotations

import gc
import weakref
from typing import TYPE_CHECKING

import pytest
from PyQt6Ads import CDockWidget

from pymmcore_gui import MicroManagerGUI
from pymmcore_gui.widgets.image_preview._ndv_preview import NDVPreview

if TYPE_CHECKING:
    from collections.abc import Iterator

    from PyQt6.QtWidgets import QApplication
    from pytestqt.qtbot import QtBot


@pytest.fixture
def gui(qtbot: QtBot, qapp: QApplication) -> Iterator[MicroManagerGUI]:
    gui = MicroManagerGUI()
    # exclude this from memory leak checks
    gui.mmcore.initializeCircularBuffer()
    qtbot.addWidget(gui)
    yield gui


@pytest.mark.limit_leaks("10 MB")
def test_memory_main_window(qapp: QApplication) -> None:
    for _i in range(5):
        gui = MicroManagerGUI()
        gui.close()
        gui.deleteLater()
        qapp.processEvents()


@pytest.mark.limit_leaks("5 MB")
def test_memory_ndv_preview(
    gui: MicroManagerGUI, qapp: QApplication, qtbot: QtBot
) -> None:
    core = gui.mmcore

    for _i in range(5):
        for _i in range(20):
            core.snapImage()
        qtbot.wait(20)

        dw = gui.dock_manager.dockWidgetsMap().get("Preview")
        assert isinstance(dw, CDockWidget)
        ndv_preview = dw.widget()
        assert isinstance(ndv_preview, NDVPreview)
        ndv_viewer = ndv_preview._viewer
        qtbot.waitUntil(lambda: ndv_viewer.data is not None, timeout=2000)
        assert ndv_viewer.data is not None

        # Explicitly detach the preview widget before closing
        preview_widget = dw.widget()
        if isinstance(preview_widget, NDVPreview):
            preview_widget.detach()

        # Close and destroy the dock widget completely to force recreation
        dw.closeDockWidgetInternal(True)
        dw.deleteLater()

        # Force a complete cleanup of the viewers manager's preview reference
        viewers_manager = gui._viewers_manager
        viewers_manager._cleanup_current_image_preview()

        # Force garbage collection and Qt cleanup after closing the dock widget
        gc.collect()
        gc.collect()
        qapp.processEvents()

        # Give some time for cleanup to complete and process any pending deletions
        qtbot.wait(10)
        qapp.processEvents()
        gc.collect()
        gc.collect()


def test_debug_memory_refs(
    gui: MicroManagerGUI, qapp: QApplication, qtbot: QtBot
) -> None:
    """Debug test to identify what's holding references to the buffer."""
    core = gui.mmcore

    # Take some snapshots to create the preview
    for _i in range(5):
        core.snapImage()
    qtbot.wait(20)

    dw = gui.dock_manager.dockWidgetsMap().get("Preview")
    assert isinstance(dw, CDockWidget)
    ndv_preview = dw.widget()
    assert isinstance(ndv_preview, NDVPreview)
    ndv_viewer = ndv_preview._viewer
    qtbot.waitUntil(lambda: ndv_viewer.data is not None, timeout=2000)
    assert ndv_viewer.data is not None

    # Create weak references to track object lifecycle
    buffer_ref = weakref.ref(ndv_preview._buffer) if ndv_preview._buffer else None
    viewer_ref = weakref.ref(ndv_preview._viewer)
    preview_ref = weakref.ref(ndv_preview)

    print("\n=== BEFORE CLEANUP ===")
    print(f"Buffer exists: {ndv_preview._buffer is not None}")
    if ndv_preview._buffer:
        print(f"Buffer length: {len(ndv_preview._buffer)}")
        print(f"Buffer id: {id(ndv_preview._buffer)}")

        # Get referrers to the buffer
        refs = gc.get_referrers(ndv_preview._buffer)
        print(f"Buffer has {len(refs)} direct referrers:")
        for i, ref in enumerate(refs[:8]):  # Show first 8
            ref_type = type(ref).__name__
            print(f"  {i}: {ref_type}")
            # Try to identify the object that owns this dict
            if isinstance(ref, dict):
                # Look for objects that have this dict as their __dict__
                dict_owners = gc.get_referrers(ref)
                print(f"    Dict has {len(dict_owners)} owners:")
                for j, owner in enumerate(dict_owners[:3]):
                    owner_type = type(owner).__name__
                    print(f"      {j}: {owner_type}")
                    if hasattr(owner, "_buffer"):
                        print(
                            f"         Has _buffer: {owner._buffer is ndv_preview._buffer}"
                        )

    # Cleanup process
    print("\n=== STARTING CLEANUP ===")

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

    print("\n=== AFTER CLEANUP ===")
    print(f"Buffer still alive: {buffer_ref() is not None if buffer_ref else 'N/A'}")
    print(f"Viewer still alive: {viewer_ref() is not None}")
    print(f"Preview still alive: {preview_ref() is not None}")

    assert buffer_ref() is None, "Buffer should be garbage collected"
    assert viewer_ref() is not None, "Viewer might still exist"
    assert preview_ref() is not None, "Preview might still exist"

    if buffer_ref and buffer_ref() is not None:
        print("\nBuffer is still alive! Referrers:")
        refs = gc.get_referrers(buffer_ref())
        print(f"Buffer still has {len(refs)} referrers:")
        for i, ref in enumerate(refs[:8]):
            ref_type = type(ref).__name__
            print(f"  {i}: {ref_type}")
            # Try to get more info about the referrer
            if isinstance(ref, dict):
                dict_owners = gc.get_referrers(ref)
                print(f"    Dict has {len(dict_owners)} owners:")
                for j, owner in enumerate(dict_owners[:5]):
                    owner_type = type(owner).__name__
                    print(f"      {j}: {owner_type}")
                    if hasattr(owner, "__dict__") and owner.__dict__ is ref:
                        print("         Owner's __dict__ contains buffer reference")
                        if hasattr(owner, "_buffer"):
                            is_same = owner._buffer is buffer_ref()
                            print(f"         Owner has _buffer (same obj: {is_same})")
                        if hasattr(owner, "_data"):
                            is_same = getattr(owner, "_data", None) is buffer_ref()
                            print(f"         Owner has _data (same obj: {is_same})")

    if viewer_ref and viewer_ref():
        print("\\nViewer is still alive!")
        viewer = viewer_ref()
        try:
            # Attempt to access viewer.data
            v_data = viewer.data
            print(f"Viewer data: {v_data}")
            # If viewer.data didn't raise an error, it means _data_model exists
            # and _data_model.data_wrapper should be None.
            # So viewer.data (which is _data_model.data_wrapper.data) should be None.
            assert v_data is None, "Viewer data should be None if accessible"
        except AttributeError:
            print(
                "Viewer data access raised AttributeError "
                "(expected if _data_model is None)"
            )
            # Verify _data_model is indeed None if AttributeError was raised
            # It's possible _data_model doesn't even exist if viewer is partially cleaned up
            assert not hasattr(viewer, "_data_model") or viewer._data_model is None, (
                "Viewer _data_model should be None if data access failed"
            )

    if preview_ref and preview_ref():
        print("\nPreview is still alive!")
        preview = preview_ref()
        print(f"Preview buffer: {preview._buffer}")
        if buffer_ref and buffer_ref():
            buffer_is_same = preview._buffer is buffer_ref()
            print(f"Preview buffer is buffer: {buffer_is_same}")
        else:
            print("Preview buffer is buffer: N/A")
