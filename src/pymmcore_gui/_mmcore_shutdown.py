"""Best-effort, idempotent hardware shutdown for a `CMMCorePlus` instance.

Closing the app must always cleanly stop acquisition and unload devices
before exit. Skipping this leaves camera device adapters (e.g. PVCAM) without
a call to their C++ `Shutdown()`, which can leave the vendor driver's
kernel-mode component believing the device is still active -- a state that
has been observed to crash (BSOD) the OS when the camera is later
power-cycled.
"""

from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from threading import Thread

    from pymmcore_plus import CMMCorePlus

logger = logging.getLogger("pymmcore_gui")

_LIVE_STOP_TIMEOUT_S = 5.0
_MDA_CANCEL_TIMEOUT_S = 10.0
_UNLOAD_TIMEOUT_S = 10.0
_POLL_INTERVAL_S = 0.05

_LAST_MDA_THREAD_ATTR = "_mmcore_gui_last_mda_thread"
_RUN_MDA_WRAPPED_ATTR = "_mmcore_gui_run_mda_wrapped"


def track_mda_thread(mmc: CMMCorePlus) -> None:
    """Idempotently wrap ``mmc.run_mda`` so its `Thread` is tracked for shutdown.

    Without this, `shutdown_mmcore` can only *poll* ``mmc.mda.is_running()``
    while cancelling an in-progress MDA -- and that is racy: `MDARunner.cancel()`
    can flip the runner's state to a non-running one (making `is_running()`
    return `False`) *before* the acquisition thread has actually finished a
    blocking hardware call (e.g. mid-``engine.setup_sequence()``). Capturing the
    real `Thread` and `.join()`-ing it (done in `shutdown_mmcore`) is not racy:
    it only returns once that thread has truly stopped talking to hardware.
    """
    if getattr(mmc, _RUN_MDA_WRAPPED_ATTR, False):
        return
    original_run_mda = mmc.run_mda

    @wraps(original_run_mda)
    def _tracked_run_mda(*args: Any, **kwargs: Any) -> Thread:
        thread = original_run_mda(*args, **kwargs)
        setattr(mmc, _LAST_MDA_THREAD_ATTR, thread)
        return thread

    mmc.run_mda = _tracked_run_mda  # type: ignore[method-assign]
    setattr(mmc, _RUN_MDA_WRAPPED_ATTR, True)


def shutdown_mmcore(
    mmc: CMMCorePlus,
    *,
    mda_thread: Thread | None = None,
    live_stop_timeout: float = _LIVE_STOP_TIMEOUT_S,
    mda_cancel_timeout: float = _MDA_CANCEL_TIMEOUT_S,
    unload_timeout: float = _UNLOAD_TIMEOUT_S,
) -> None:
    """Stop any running acquisition and unload all devices from *mmc*.

    Safe to call more than once (e.g. from both a window's `closeEvent` and
    `QApplication.aboutToQuit`) and safe to call when nothing is running.
    Every step is independently guarded with a try/except and a bounded
    timeout so that one slow or misbehaving device adapter cannot prevent the
    rest of the sequence from running, and cannot prevent the process from
    exiting.

    If *mda_thread* is not given, the thread from the most recent
    ``mmc.run_mda()`` call is used, provided :func:`track_mda_thread` has been
    called on *mmc* at some point (e.g. once at GUI startup).
    """
    if mda_thread is None:
        mda_thread = getattr(mmc, _LAST_MDA_THREAD_ATTR, None)
    _stop_live(mmc, live_stop_timeout)
    _cancel_mda_and_wait(mmc, mda_thread, mda_cancel_timeout)
    _close_lasers()
    _run_with_timeout(mmc.unloadAllDevices, unload_timeout, "unloadAllDevices")


def _stop_live(mmc: CMMCorePlus, timeout_s: float) -> None:
    try:
        if mmc.isSequenceRunning():
            logger.info("Stopping live sequence acquisition before shutdown")
            _run_with_timeout(
                mmc.stopSequenceAcquisition, timeout_s, "stopSequenceAcquisition"
            )
            _wait_until(lambda: not mmc.isSequenceRunning(), timeout_s)
    except Exception:
        logger.exception("Error stopping live sequence acquisition during shutdown")


def _cancel_mda_and_wait(
    mmc: CMMCorePlus, mda_thread: Thread | None, timeout_s: float
) -> None:
    try:
        mmc.mda.cancel()  # no-op if nothing is running
    except Exception:
        logger.exception("Error requesting MDA cancel during shutdown")
        return

    if mda_thread is not None:
        mda_thread.join(timeout_s)
        if mda_thread.is_alive():
            logger.warning(
                "MDA thread did not finish within %.1fs; continuing shutdown anyway",
                timeout_s,
            )
    else:
        # No thread handle available (e.g. an MDA started outside the GUI's
        # MDA widget). Best-effort fallback.
        _wait_until(lambda: not mmc.mda.is_running(), timeout_s)


def _close_lasers() -> None:
    try:
        from pymmcore_gui.asi_z_stack.asi_controller import close_all_lasers

        close_all_lasers()
    except Exception:
        logger.exception("Error closing lasers during shutdown")


def _wait_until(predicate: Callable[[], bool], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL_S)


def _run_with_timeout(fn: Callable[[], None], timeout_s: float, label: str) -> None:
    """Run *fn* on a daemon thread; log and give up (without blocking) on timeout."""
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=_target, name=f"mmcore-shutdown-{label}", daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        logger.warning(
            "%s did not complete within %.1fs; abandoning and continuing shutdown",
            label,
            timeout_s,
        )
    elif errors:
        logger.exception("Error during %s", label, exc_info=errors[0])
    else:
        logger.debug("%s completed", label)
