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
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus, configure_logging
from pymmcore_plus.core import _mmcore_plus

from pymmcore_gui import settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic_settings import (
        EnvSettingsSource,
        InitSettingsSource,
        PydanticBaseSettingsSource,
    )
    from PyQt6.QtWidgets import QApplication
    from pytest import FixtureRequest

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")

configure_logging(stderr_level="CRITICAL")


# to create a new CMMCorePlus() for every test
@pytest.fixture(autouse=True)
def global_mmcore() -> Iterator[CMMCorePlus]:
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration(TEST_CONFIG)
    with patch.object(_mmcore_plus, "_instance", mmc):
        yield mmc


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
def _mock_settings_sources() -> Iterator[None]:
    """Ensure that the user settings file is not read or written during tests.

    This is done by mocking the `settings_customise_sources` method to return only
    the `InitSettingsSource` and `EnvSettingsSource` sources.  Further only environment
    variables with the prefix `PMM_TEST_` will be considered.
    """

    def _test_sources(
        *args: Any,
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        **kwargs: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        env_settings.env_prefix = "PMM_TEST_"
        return (init_settings, env_settings)

    with patch.object(settings.SettingsV1, "settings_customise_sources", _test_sources):
        yield
