import os
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
    process = subprocess.Popen([str(APP)])
    if sys.platform == "darwin":
        time.sleep(2)
    elif sys.platform == "win32":
        time.sleep(5)
    pyautogui.click()
    pyautogui.click(100, 500)
    yield process
    process.terminate()
    process.wait()
    assert process.returncode == -15, (
        f"Process terminated with code {process.returncode}"
    )


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(2)
