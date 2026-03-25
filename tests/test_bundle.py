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

STARTUP_TIMEOUT_S = 30.0


def _wait_for_ready(proc: subprocess.Popen, timeout_s: float) -> None:
    if proc.stdout is None:  # pragma: no cover
        pytest.fail("Subprocess stdout was not captured.")

    os.set_blocking(proc.stdout.fileno(), False)
    deadline = time.monotonic() + timeout_s
    output = ""

    while time.monotonic() < deadline:
        if (returncode := proc.poll()) is not None:
            tail = output.strip().splitlines()[-10:]
            tail_text = "\n".join(tail)
            pytest.fail(
                "App exited before reporting READY "
                f"(returncode={returncode}).\nCaptured output:\n{tail_text}"
            )

        chunk = proc.stdout.read()
        if chunk:
            output += chunk
            if any(line.strip() == "READY" for line in output.splitlines()):
                return

        time.sleep(0.05)

    tail = output.strip().splitlines()[-10:]
    tail_text = "\n".join(tail)
    pytest.fail(
        f"Timed out waiting {timeout_s:.0f}s for READY.\nCaptured output:\n{tail_text}"
    )


@pytest.fixture
def app_process() -> Iterator[subprocess.Popen]:
    env = os.environ.copy()
    env["PYMMGUI_TEST_QUIT_AFTER"] = "2"

    with subprocess.Popen(
        [str(APP)],
        env=env,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as proc:
        _wait_for_ready(proc, STARTUP_TIMEOUT_S)

        yield proc

        proc.wait(timeout=10)
        assert proc.returncode == 0
        if proc.stdout is not None:
            proc.stdout.close()


CMD_CTRL = "ctrl" if os.name == "nt" else "command"


@pytest.mark.usefixtures("app_process")
def test_app() -> None:
    time.sleep(1)
