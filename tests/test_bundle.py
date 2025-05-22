import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

NAME = "pymmgui"
DIST = Path(__file__).parent.parent / "dist"
APP = DIST / NAME / (NAME + (".exe" if os.name == "nt" else ""))

if not APP.exists():
    pytest.skip(f"App not built: {APP}", allow_module_level=True)

import pyautogui  # noqa: E402


@pytest.fixture
def app_process() -> Iterator[subprocess.Popen]:
    kwargs: dict = {}
    if sys.platform == "win32":
        # needed so SIGINT / CTRL_BREAK only hit this child
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [str(APP)],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kwargs,
    )

    # --- wait for the GUI to tell us it's ready ---
    while True:
        # this "READY" line is printed in _app.create_mmgui
        # when "PYTEST_VERSION" is set in the environment
        if proc.stdout and proc.stdout.readline().strip() == b"READY":
            break
        time.sleep(0.1)

    try:
        yield proc
    finally:
        # --- teardown ---
        if proc.poll() is None:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGTERM)

            try:
                pyautogui.moveTo(1200, 600, duration=0.1)
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # read any leftover output _before_ closing
        err_info = ""
        if proc.stdout:
            err_info = proc.stdout.read()
            proc.stdout.close()

        if proc.returncode != 0:
            raise AssertionError(
                f"App process exited with code {proc.returncode!r}:\n{err_info}"
            )


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(1)
