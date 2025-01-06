import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import rich.pretty
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.splash import Splash
from PyInstaller.config import CONF
from PyInstaller.utils.hooks import collect_data_files

import pymmcore_gui

if TYPE_CHECKING:
    from PyInstaller.utils.win32 import versioninfo as vi

if "workpath" not in CONF:
    raise ValueError("This script must run with `pyinstaller mmgui.spec`")


# PATCH rich:
# https://github.com/Textualize/rich/pull/3592

fpath = Path(rich.pretty.__file__)
src = fpath.read_text().replace(
    "        return obj.__repr__.__code__.co_filename in (\n",
    "        return obj.__repr__.__code__.co_filename in ('dataclasses.py',\n",
)
fpath.write_text(src)

####################################################


PACKAGE = Path(pymmcore_gui.__file__).parent
ROOT = PACKAGE.parent.parent
APP_ROOT = ROOT / "app"
RESOURCES = PACKAGE / "resources"
ICON = RESOURCES / ("icon.ico" if sys.platform.startswith("win") else "icon.icns")

ONEFILE = "--onefile" in sys.argv
SPLASH = os.name == "nt"

NAME = "pymmgui"
DEBUG = False
UPX = True

os.environ["QT_API"] = "PyQt6"
os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"


def _get_win_version() -> "vi.VSVersionInfo":
    if sys.platform != "win32":
        return None
    from PyInstaller.utils.win32 import versioninfo as vi

    ver_str = pymmcore_gui.__version__
    version = [int(x) for x in ver_str.replace("+", ".").split(".") if x.isnumeric()]
    version += [0] * (4 - len(version))
    version_t = tuple(version)[:4]
    return vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=version_t, prodvers=version_t),
        kids=[
            vi.StringFileInfo(
                [
                    vi.StringTable(
                        "000004b0",
                        [
                            vi.StringStruct("CompanyName", NAME),
                            vi.StringStruct("FileDescription", NAME),
                            vi.StringStruct("FileVersion", ver_str),
                            vi.StringStruct("LegalCopyright", ""),
                            vi.StringStruct("OriginalFileName", NAME + ".exe"),
                            vi.StringStruct("ProductName", NAME),
                            vi.StringStruct("ProductVersion", ver_str),
                        ],
                    )
                ]
            ),
            vi.VarFileInfo([vi.VarStruct("Translation", [0, 1200])]),
        ],
    )


a = Analysis(
    [PACKAGE / "__main__.py"],
    binaries=[],
    datas=collect_data_files("pymmcore_gui"),
    # An optional list of additional (hidden) modules to include.
    hiddenimports=["pdb"],
    # An optional list of additional paths to search for hooks.
    hookspath=[APP_ROOT / "hooks"],
    # An optional list of module or package names (their Python names, not path names)
    # that will be ignored (as though they were not found).
    excludes=[
        "pdbpp",
        "FixTk",
        "tcl",
        "tk",
        "_tkinter",
        "tkinter",
        "Tkinter",
        "matplotlib",
    ],
    # If True, do not place source files in a archive, but keep them as individual files
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
if SPLASH:
    splash = Splash(
        str(RESOURCES / "logo_trans.png"),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )

if ONEFILE:
    if SPLASH:
        exe_args = (pyz, a.scripts, a.binaries, a.datas, splash, splash.binaries, [])
    else:
        exe_args = (pyz, a.scripts, a.binaries, a.datas, [])
    exe_kwargs = {"upx_exclude": [], "runtime_tmpdir": None}
else:
    if SPLASH:
        exe_args = (pyz, a.scripts, splash, [])
    else:
        exe_args = (pyz, a.scripts, [])
    exe_kwargs = {"exclude_binaries": True}

exe = EXE(
    *exe_args,
    **exe_kwargs,
    name=NAME,
    debug=DEBUG,
    bootloader_ignore_signals=False,
    strip=False,
    upx=UPX,
    # whether to use the console executable or the windowed executable
    console=False,
    # windows only
    # In console-enabled executable, hide or minimize the console window if the program
    # owns the console window (i.e., was not launched from existing console window).
    hide_console=None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    icon=ICON,
    version=_get_win_version(),
)
if not ONEFILE:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        *((splash.binaries,) if SPLASH else ()),
        strip=False,
        upx=True,
        upx_exclude=[],
        name=NAME,
    )

if sys.platform == "darwin":
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=ICON,
        bundle_identifier=None,
        info_plist={
            "CFBundleIdentifier": f"com.{NAME}.{NAME}",
            "CFBundleShortVersionString": pymmcore_gui.__version__,
            "NSHighResolutionCapable": "True",
        },
    )
