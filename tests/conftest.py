from __future__ import annotations

import os

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
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.core import _mmcore_plus

if TYPE_CHECKING:
    from pytest import FixtureRequest
    from qtpy.QtWidgets import QApplication

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")


# to create a new CMMCorePlus() for every test
@pytest.fixture(autouse=True)
def global_mmcore():
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration(TEST_CONFIG)
    with patch.object(_mmcore_plus, "_instance", mmc):
        yield mmc


@pytest.fixture()
def _run_after_each_test(request: FixtureRequest, qapp: QApplication):
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

    print()
    for r in remaining:
        print(r, r.parent())

    if len(remaining) > nbefore:
        test = f"{request.node.path.name}::{request.node.originalname}"
        raise AssertionError(f"topLevelWidgets remaining after {test!r}: {remaining}")
