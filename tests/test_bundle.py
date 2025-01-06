import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pyautogui
import pytest

NAME = "pymmgui"
DIST = Path(__file__).parent.parent / "dist"
APP = DIST / NAME / (NAME + (".exe" if os.name == "nt" else ""))


@pytest.fixture
def app_process() -> Iterator[subprocess.Popen]:
    process = subprocess.Popen([str(APP)])
    time.sleep(1)
    if sys.platform == "darwin":
        pyautogui.hotkey("command", "tab")
    yield process
    process.terminate()
    process.wait()
    assert process.returncode in (0, -15)


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    # open widgets
    # TODO: these hotkeys should be pulled from source code
    pyautogui.hotkey("command", "shift", "p")
    pyautogui.hotkey("command", "shift", "i")
    pyautogui.hotkey("command", "shift", "c")
    pyautogui.hotkey("command", "shift", "m")
    pyautogui.hotkey("command", "shift", "s")
    pyautogui.hotkey("command", "shift", "r")
    pyautogui.hotkey("command", "shift", "g")
    pyautogui.hotkey("command", "shift", "e")
    time.sleep(2)
