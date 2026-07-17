from __future__ import annotations

import os

from pymmcore_gui._settings import Settings

# This is a temporary fix due to a `DeprecationWarning` from the `qtconsole` package:
# """DeprecationWarning: Jupyter is migrating its paths to use standard platformdirs
# given by the platformdirs library.  To remove this warning and
# see the appropriate new directories, set the environment variable
# `JUPYTER_PLATFORM_DIRS=1` and then run `jupyter --paths`.
# The use of platformdirs will be the default in `jupyter_core` v6"""
os.environ["JUPYTER_PLATFORM_DIRS"] = "1"

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus, configure_logging
from pymmcore_plus.core import _mmcore_plus

from pymmcore_gui import _app

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest import FixtureRequest

    from pymmcore_gui._qt.QtWidgets import QApplication

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")

configure_logging(stderr_level="CRITICAL")


@pytest.fixture(scope="session")
def qapp_cls() -> type[QApplication]:
    return _app.MMQApplication


# to create a new CMMCorePlus() for every test
@pytest.fixture(autouse=True)
def mmcore() -> Iterator[CMMCorePlus]:
    # Clear the singleton so the new instance auto-registers via __init__
    _mmcore_plus._instance = None
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration(TEST_CONFIG)
    yield mmc
    mmc.waitForSystem()
    _mmcore_plus._instance = None


# fresh default settings for every test
@pytest.fixture(autouse=True)
def settings() -> Iterator[Settings]:
    settings = Settings()
    with patch("pymmcore_gui._settings._GLOBAL_SETTINGS", settings):
        yield settings


@pytest.fixture()
def check_leaks(request: FixtureRequest, qapp: QApplication) -> Iterator[None]:
    """Run after each test to ensure no widgets have been left around.

    When this test fails, it means that a widget being tested has an issue closing
    cleanly. Perhaps a strong reference has leaked somewhere.  Look for
    `functools.partial(self._method)` or `lambda: self._method` being used in that
    widget's code.
    """
    nbefore = len(qapp.topLevelWidgets())
    failures_before = request.session.testsfailed
    yield
    # if the test failed, don't worry about checking widgets
    if request.session.testsfailed - failures_before:
        return

    remaining = qapp.topLevelWidgets()

    if len(remaining) > nbefore:
        print()
        for r in remaining:
            print(r, r.parent())
        test = f"{request.node.path.name}::{request.node.originalname}"
        raise AssertionError(f"topLevelWidgets remaining after {test!r}: {remaining}")


@pytest.fixture(autouse=True)
def _mock_pyconify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mock pyconify.svg_path to avoid network requests in tests."""
    svg_dir = tmp_path / "icons"
    svg_dir.mkdir()
    _counter = 0

    def mock_svg_path(*key: str, color: str | None = None, **kwargs: object) -> Path:
        nonlocal _counter
        fill = color or "currentColor"
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<rect width="24" height="24" fill="{fill}"/></svg>'
        )
        svg_file = svg_dir / f"icon_{_counter}.svg"
        _counter += 1
        svg_file.write_text(svg_content)
        return svg_file

    monkeypatch.setattr(
        "pymmcore_widgets.control._stage_widget.svg_path", mock_svg_path
    )
    monkeypatch.setattr("superqt.iconify.svg_path", mock_svg_path)
    yield
