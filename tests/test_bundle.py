import os
import subprocess
from pathlib import Path

import pytest

NAME = "pymmgui"
DIST = Path(__file__).parent.parent / "dist"
APP = DIST / NAME / (NAME + (".exe" if os.name == "nt" else ""))

if not APP.exists():
    pytest.skip(f"App not built: {APP}", allow_module_level=True)

QUIT_AFTER_S = 2
EXIT_TIMEOUT_S = 30


def test_app() -> None:
    env = os.environ.copy()
    env["PYMMGUI_TEST_QUIT_AFTER"] = str(QUIT_AFTER_S)

    with subprocess.Popen(
        [str(APP)],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) as proc:
        proc.wait(timeout=EXIT_TIMEOUT_S)
        assert proc.returncode == 0
