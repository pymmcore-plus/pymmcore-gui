import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

NAME = "pymmgui"
DIST = Path(__file__).parent.parent / "dist"
APP = DIST / NAME / (NAME + (".exe" if os.name == "nt" else ""))

if not APP.exists():
    pytest.skip(f"App not built: {APP}", allow_module_level=True)


@pytest.fixture
def app_process() -> Iterator[subprocess.Popen]:
    env = os.environ.copy()
    env["PYMMGUI_TEST_QUIT_AFTER"] = "2"

    proc = subprocess.Popen(
        [str(APP)],
        env=env,
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

    yield proc

    proc.wait(timeout=10)
    assert proc.returncode == 0


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(1)
