from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tifffile
import useq

# from pymmcore_plus.mda.handlers import TensorStoreHandler
# from pymmcore_widgets._stack_viewer_v2._mda_viewer import MDAViewer
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY

# from micromanager_gui._menubar._menubar import DOCKWIDGETS, WIDGETS
from micromanager_gui._readers._ome_zarr_reader import OMEZarrReader
from micromanager_gui._readers._tensorstore_zarr_reader import TensorstoreZarrReader
from micromanager_gui._writers._tensorstore_zarr import _TensorStoreHandler

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


# fmt: off
files = [
    # indexers, expected files, file_to_check, expected shape
    ({}, ["p0.tif", "p0.json", "p1.tif", "p1.json"], "p0.tif", (3, 2, 512, 512)),
    ({"p": 0}, ["test.tiff", "test.json"], "test.tiff", (3, 2, 512, 512)),
    ({"p": 0, "t": 0}, ["test.tiff", "test.json"], "test.tiff", (2, 512, 512)),
    # when a tuple is passed, first element is indexers and second is the kwargs
    (({"p": 0}, {"p": 0}), ["test.tiff", "test.json"], "test.tiff", (3, 2, 512, 512)),
    (({"p": 0}, {"t": 0}), ["test.tiff", "test.json"], "test.tiff", (2, 512, 512)),
]

MDA = useq.MDASequence(
    channels=["FITC", "DAPI"],
    stage_positions=[(0, 0), (0, 1)],
    time_plan={"loops": 3, "interval": 0.1},
)
ZARR_META = {"format": "ome-zarr", "save_name": "z.ome.zarr"}
TENSOR_META = {
    "format": "tensorstore-zarr",
    "save_name": "ts.tensorstore.zarr",
}

writers = [
    (ZARR_META, "z.ome.zarr", "", OMEZarrReader),
    (TENSOR_META, "ts.tensorstore.zarr", _TensorStoreHandler, TensorstoreZarrReader),
]
# fmt: on


# NOTE: the tensorstore reader works only if we use the internal _TensorStoreHandler
# TODO: fix the main TensorStoreHandler because it does not write the ".zattrs"
@pytest.mark.parametrize("writers", writers)
@pytest.mark.parametrize("kwargs", [True, False])
@pytest.mark.parametrize("files", files)
def test_readers(
    qtbot: QtBot,
    global_mmcore: CMMCorePlus,
    tmp_path: Path,
    writers: tuple,
    files: tuple,
    kwargs: bool,
):
    meta, name, writer, reader = writers
    indexers, expected_files, file_to_check, expected_shape = files

    mda = MDA.replace(
        metadata={
            PYMMCW_METADATA_KEY: {
                **meta,
                "save_dir": str(tmp_path),
                "should_save": True,
            }
        }
    )

    dest = tmp_path / name
    writer = writer(path=dest) if writer else dest
    with qtbot.waitSignal(global_mmcore.mda.events.sequenceFinished):
        global_mmcore.mda.run(mda, output=writer)

    assert dest.exists()

    w = reader(path=dest)
    assert w.store
    assert w.sequence

    assert w.isel({"p": 0}).shape == (3, 2, 512, 512)
    assert w.isel({"p": 0, "t": 0}).shape == (2, 512, 512)
    _, metadata = w.isel({"p": 0}, metadata=True)
    assert metadata

    # test saving as tiff
    dest = tmp_path / "test"

    if not indexers and "ome.zarr" in name:
        return  # skipping since the no 'p' index error will be raised

    # if indexers is a tuple, use one as indexers and the other as kwargs
    if isinstance(indexers, tuple):
        # skip if kwargs is False since we don't want to test it twice
        if not kwargs:
            return
        w.write_tiff(dest, indexers[0], **indexers[1])
    # depends om kwargs (once as dict and once as kwargs)
    else:
        w.write_tiff(dest, **indexers) if kwargs else w.write_tiff(dest, indexers)
    # all files in dest
    parent = dest.parent if indexers else dest
    dir_files = [f.name for f in parent.iterdir()]
    assert all(f in dir_files for f in expected_files)
    # open with tifffile and check the shape
    with tifffile.TiffFile(parent / file_to_check) as tif:
        assert tif.asarray().shape == expected_shape
