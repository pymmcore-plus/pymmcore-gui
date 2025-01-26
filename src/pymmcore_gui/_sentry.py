from __future__ import annotations

import functools
import logging
import os
import platform
import sys
import uuid
from contextlib import suppress
from importlib import metadata
from pathlib import Path
from site import getsitepackages, getusersitepackages
from subprocess import run
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint
else:
    try:
        from rich import print
    except ImportError:  # pragma: no cover
        from pprint import pprint as print

SENTRY_DSN = "https://3ea8feba276ec96bdf6c110a26fe9699@o100671.ingest.us.sentry.io/4507535157952512"
SHOW_HOSTNAME = os.getenv("MM_TELEMETRY_SHOW_HOSTNAME", "0") in ("1", "True")
SHOW_LOCALS = os.getenv("MM_TELEMETRY_SHOW_LOCALS", "1") in ("1", "True")
DEBUG = bool(os.getenv("MM_TELEMETRY_DEBUG"))
HOME_DIR = str(Path.home())


def strip_sensitive_data(event: Event, hint: Hint) -> Event | None:
    """Pre-send hook to strip sensitive data from `event` dict.

    https://docs.sentry.io/platforms/python/configuration/filtering/#filtering-error-events
    """
    # strip home dir from `abs_paths` in stack_trace to hide local paths
    with suppress(Exception):
        if exception := event.get("exception"):
            for exc in exception.get("values", []):
                for frame in exc.get("stacktrace", {}).get("frames", []):
                    if "abs_path" in frame:
                        frame["abs_path"] = frame["abs_path"].replace(HOME_DIR, "~")

    with suppress(Exception):
        # only include the name of the executable in sys.argv (remove paths)
        if (
            (extra := event.get("extra"))
            and (args := extra.get("sys.argv"))
            and isinstance(args, list)
        ):
            args[:] = [str(x).replace(HOME_DIR, "~") for x in args]
    if DEBUG:  # pragma: no cover
        print(event)
    return event


def is_editable_install() -> bool:
    """Return True if `dist_name` is installed as editable.

    i.e: if the package isn't in site-packages or user site-packages.
    """
    import pymmcore_gui

    root = str(Path(pymmcore_gui.__file__).parent)
    installed_paths = (*getsitepackages(), getusersitepackages())
    return all(loc not in root for loc in installed_paths)


def try_get_git_sha(dist_name: str = "pymmcore-gui") -> str:
    """Try to return a git sha, for `dist_name` and detect if dirty.

    Return empty string on failure.
    """
    try:
        ff = str(metadata.distribution(dist_name).locate_file(""))
        out = run(["git", "-C", ff, "rev-parse", "HEAD"], capture_output=True)
        if out.returncode:  # pragma: no cover
            return ""
        sha = out.stdout.decode().strip()
        # exit with 1 if there are differences and 0 means no differences
        # disallow external diff drivers
        out = run(["git", "-C", ff, "diff", "--no-ext-diff", "--quiet", "--exit-code"])
        if out.returncode:  # pragma: no cover
            sha += "-dirty"
        return sha
    except Exception:  # pragma: no cover
        return ""


@functools.cache
def get_release() -> str | None:
    """Get the current release string for `package`.

    If the package is an editable install, it will return the current git sha.
    Otherwise return version string from package metadata.
    """
    with suppress(Exception):
        if is_editable_install():
            if sha := try_get_git_sha():
                return sha
        return metadata.version("pymmcore-gui")
    return None


@functools.cache
def get_tags() -> dict[str, str]:
    """Get platform and other tags to associate with this session."""
    tags = {"frozen": str(getattr(sys, "frozen", False))}
    with suppress(Exception):
        tags["editable_install"] = str(is_editable_install())

    return tags


SENTRY_INSTALLED = False


def install_error_reporter() -> None:  # pragma: no cover
    """Initialize the error reporter with sentry.io."""
    # never install sentry in pytest
    if "PYTEST_VERSION" in os.environ:
        return

    try:
        import sentry_sdk
    except ImportError:
        logging.info("sentry-sdk not installed, skipping error reporting.")
        return

    global SENTRY_INSTALLED
    if SENTRY_INSTALLED:
        return

    sentry_sdk.init(
        SENTRY_DSN,
        # When enabled, local variables are sent along with stackframes.
        # This can have a performance and PII impact.
        # Enabled by default on platforms where this is available.
        include_local_variables=SHOW_LOCALS,
        # A number between 0 and 1, controlling the percentage chance
        # a given transaction will be sent to Sentry.
        # (0 represents 0% while 1 represents 100%.)
        # Applies equally to all transactions created in the app.
        # Either this or traces_sampler must be defined to enable tracing.
        traces_sample_rate=1.0,
        # When provided, the name of the server is sent along and persisted
        # in the event. For many integrations the server name actually
        # corresponds to the device hostname, even in situations where the
        # machine is not actually a server. Most SDKs will attempt to
        # auto-discover this value. (computer name: potentially PII)
        server_name=None if SHOW_HOSTNAME else "",
        # If this flag is enabled, certain personally identifiable information (PII)
        # is added by active integrations. By default, no such data is sent.
        send_default_pii=False,
        # This function is called with an SDK-specific event object, and can return a
        # modified event object or nothing to skip reporting the event.
        # This can be used, for instance, for manual PII stripping before sending.
        before_send=strip_sensitive_data,
        debug=DEBUG,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # TODO: recommend adjusting this value in production.
        profiles_sample_rate=1.0,
        release=get_release(),
        environment=platform.system(),
    )

    for k, v in get_tags().items():
        sentry_sdk.set_tag(k, v)
    with suppress(Exception):
        sentry_sdk.set_user({"id": uuid.getnode()})
    SENTRY_INSTALLED = True
