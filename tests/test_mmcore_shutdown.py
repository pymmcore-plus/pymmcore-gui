from __future__ import annotations

import threading
import time
from unittest.mock import patch

from pymmcore_gui._mmcore_shutdown import shutdown_mmcore, track_mda_thread


def test_shutdown_unloads_all_devices(mmcore) -> None:  # noqa: ANN001
    assert len(mmcore.getLoadedDevices()) > 1
    shutdown_mmcore(mmcore)
    assert mmcore.getLoadedDevices() == ("Core",)


def test_shutdown_stops_live_sequence(mmcore) -> None:  # noqa: ANN001
    mmcore.startContinuousSequenceAcquisition(0)
    assert mmcore.isSequenceRunning()
    shutdown_mmcore(mmcore)
    assert not mmcore.isSequenceRunning()
    assert mmcore.getLoadedDevices() == ("Core",)


def test_shutdown_cancels_running_mda(mmcore) -> None:  # noqa: ANN001
    import useq

    thread = mmcore.run_mda(
        useq.MDASequence(
            time_plan=useq.TIntervalLoops(interval=1, loops=1000),  # pyright: ignore
        ),
    )
    assert mmcore.mda.is_running()
    shutdown_mmcore(mmcore, mda_thread=thread)
    assert not thread.is_alive()
    assert not mmcore.mda.is_running()
    assert mmcore.getLoadedDevices() == ("Core",)


def test_shutdown_auto_tracks_mda_thread_without_explicit_arg(mmcore) -> None:  # noqa: ANN001, E501
    """Regression test: polling `is_running()` alone is racy.

    `MDARunner.cancel()` can flip the runner to a non-running state while the
    acquisition thread is still mid-``setup_sequence()`` (a stand-in for a
    blocking hardware call). Without `track_mda_thread`, `shutdown_mmcore`
    would fall back to polling `is_running()` and could call
    `unloadAllDevices()` while that thread is still actively running --
    exactly the race that can leave a camera driver in a bad state. With
    tracking enabled, `shutdown_mmcore(mmcore)` (no `mda_thread` kwarg) must
    still correctly join the real thread before unloading.
    """
    import useq

    track_mda_thread(mmcore)
    mmcore.run_mda(
        useq.MDASequence(
            time_plan=useq.TIntervalLoops(interval=1, loops=1000),  # pyright: ignore
        ),
    )
    assert mmcore.mda.is_running()
    shutdown_mmcore(mmcore)  # no mda_thread kwarg: must auto-detect it
    assert not mmcore.mda.is_running()
    assert mmcore.getLoadedDevices() == ("Core",)


def test_shutdown_is_idempotent(mmcore) -> None:  # noqa: ANN001
    shutdown_mmcore(mmcore)
    # calling again on an already-unloaded core must not raise
    shutdown_mmcore(mmcore)
    assert mmcore.getLoadedDevices() == ("Core",)


def test_shutdown_tolerates_unload_exception(mmcore) -> None:  # noqa: ANN001
    with patch.object(
        mmcore, "unloadAllDevices", side_effect=RuntimeError("boom")
    ):
        shutdown_mmcore(mmcore)  # must not raise


def test_shutdown_does_not_hang_on_slow_unload(mmcore) -> None:  # noqa: ANN001
    def _slow_unload() -> None:
        time.sleep(5)

    with patch.object(mmcore, "unloadAllDevices", side_effect=_slow_unload):
        start = time.monotonic()
        shutdown_mmcore(mmcore, unload_timeout=0.2)
        elapsed = time.monotonic() - start
    assert elapsed < 2.0


def test_shutdown_tolerates_undead_mda_thread(mmcore) -> None:  # noqa: ANN001
    stuck = threading.Event()

    def _never_finishes() -> None:
        stuck.wait()

    thread = threading.Thread(target=_never_finishes, daemon=True)
    thread.start()
    try:
        start = time.monotonic()
        shutdown_mmcore(mmcore, mda_thread=thread, mda_cancel_timeout=0.2)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0
        assert mmcore.getLoadedDevices() == ("Core",)
    finally:
        stuck.set()
        thread.join()
