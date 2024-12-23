import sys
from pathlib import Path

import rich.pretty
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.config import CONF

if "workpath" not in CONF:
    raise ValueError("This script must run with `pyinstaller mmgui.spec`")

CONF["noconfirm"] = True


# PATCH rich:
# https://github.com/Textualize/rich/pull/3592

fpath = Path(rich.pretty.__file__)
src = fpath.read_text().replace(
    "        return obj.__repr__.__code__.co_filename in (\n",
    "        return obj.__repr__.__code__.co_filename in ('dataclasses.py',\n",
)
fpath.write_text(src)

####################################################

a = Analysis(
    ["src/pymmcore_gui/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["pdb"],
    hookspath=["hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "FixTk",
        "tcl",
        "tk",
        "_tkinter",
        "tkinter",
        "Tkinter",
        "matplotlib",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mmgui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mmgui",
)

if sys.platform == "darwin":
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        coll,
        name="mmgui.app",
        icon=None,
        bundle_identifier=None,
    )
