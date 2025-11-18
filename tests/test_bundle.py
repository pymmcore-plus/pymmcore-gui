import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import suppress
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
    proc = subprocess.Popen(
        [str(APP)],
        start_new_session=True,
        stdout=subprocess.PIPE,
    )

    # --- wait for the GUI to tell us it's ready ---
    while True:
        # this "READY" line is printed in _app.create_mmgui
        # when "PYTEST_VERSION" is set in the environment
        if proc.stdout and proc.stdout.readline().strip() == b"READY":
            break
        time.sleep(0.1)

    with proc:
        yield proc

        # --- teardown ---
        if proc.poll() is None:
            proc.terminate()
            try:
                with suppress(Exception):
                    pyautogui.moveTo(1200, 600, duration=0.1)
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    # FIXME: allowing 1 on windows is a cop-out
    # can't figure out how to send a signal to gracefully close the app
    acceptable_codes = {0, 1} if os.name == "nt" else {0, -9}
    assert proc.returncode in acceptable_codes


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(1)
