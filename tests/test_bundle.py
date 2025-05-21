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

    proc = subprocess.Popen([str(APP)], **kwargs)
    if sys.platform == "darwin":
        time.sleep(1)
    elif sys.platform == "win32":
        time.sleep(2)
    yield proc

    if proc.poll() is None:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            pyautogui.FAILSAFE = False
            pyautogui.moveTo(0, 0)
            pyautogui.moveTo(800, 1200, duration=0.1)
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    assert proc.returncode == 0


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(1)
