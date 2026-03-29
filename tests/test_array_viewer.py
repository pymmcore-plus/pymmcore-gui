from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile

from pymmcore_gui._array_viewer import _save_as_tiff, _save_multiposition

# Small image dimensions to keep tests fast.
_Y, _X = 16, 16


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series_axes(path: str | Path) -> str:
    """Return the tifffile series-0 axes string for the given OME-TIFF."""
    with tifffile.TiffFile(str(path)) as tif:
        return tif.series[0].axes


def _array_shape(path: str | Path) -> tuple[int, ...]:
    """Return the array shape when reading the given TIFF file."""
    return tuple(tifffile.imread(str(path)).shape)


def _ome_xml(path: str | Path) -> str:
    """Return the raw OME-XML string for the given TIFF file."""
    with tifffile.TiffFile(str(path)) as tif:
        return tif.ome_metadata or ""


# ---------------------------------------------------------------------------
# _save_as_tiff  (snap and single-position MDA scenarios)
# ---------------------------------------------------------------------------


_SAVE_AS_TIFF_CASES = [
    # snap: plain 2-D image, no axes metadata → tifffile infers "YX"
    pytest.param(
        np.zeros((_Y, _X), dtype=np.uint16),
        "",
        None,
        None,
        (_Y, _X),
        "YX",
        id="snap",
    ),
    # 2-channel MDA (channels only, default axis_order)
    pytest.param(
        np.zeros((2, _Y, _X), dtype=np.uint16),
        "CYX",
        None,
        None,
        (2, _Y, _X),
        "CYX",
        id="2ch",
    ),
    # 2-channel, 3-slice z-stack - default axis_order (c before z -> "CZYX")
    pytest.param(
        np.zeros((2, 3, _Y, _X), dtype=np.uint16),
        "CZYX",
        None,
        None,
        (2, 3, _Y, _X),
        "CZYX",
        id="2ch-z3-default-czyx",
    ),
    # 2-channel, 3-slice z-stack - z-before-c axis_order ("ZCYX")
    pytest.param(
        np.zeros((3, 2, _Y, _X), dtype=np.uint16),
        "ZCYX",
        None,
        None,
        (3, 2, _Y, _X),
        "ZCYX",
        id="2ch-z3-z-first-zcyx",
    ),
    # physical-size metadata round-trips via OME-XML
    pytest.param(
        np.zeros((2, 3, _Y, _X), dtype=np.uint16),
        "CZYX",
        0.65,
        0.5,
        (2, 3, _Y, _X),
        "CZYX",
        id="2ch-z3-with-metadata",
    ),
]


@pytest.mark.parametrize(
    "arr, axes, pixel_size_um, z_step_um, expected_shape, expected_axes",
    _SAVE_AS_TIFF_CASES,
)
def test_save_as_tiff(
    tmp_path: Path,
    arr: np.ndarray,
    axes: str,
    pixel_size_um: float | None,
    z_step_um: float | None,
    expected_shape: tuple[int, ...],
    expected_axes: str,
) -> None:
    path = str(tmp_path / "out.ome.tif")
    _save_as_tiff(
        arr, path, pixel_size_um=pixel_size_um, z_step_um=z_step_um, axes=axes
    )

    assert Path(path).is_file()
    assert _array_shape(path) == expected_shape
    assert _series_axes(path) == expected_axes

    ome = _ome_xml(path)
    if pixel_size_um is not None:
        assert str(pixel_size_um) in ome
    if z_step_um is not None:
        assert str(z_step_um) in ome


# ---------------------------------------------------------------------------
# _save_multiposition  (multi-position MDA scenarios)
# ---------------------------------------------------------------------------


_MULTIPOS_CASES = [
    # 2 positions, 2 channels (p is the outermost / slowest axis)
    pytest.param(
        np.zeros((2, 2, _Y, _X), dtype=np.uint16),
        {"p": 2, "c": 2},
        "CYX",
        2,
        (2, _Y, _X),
        id="2pos-2ch",
    ),
    # 2 positions, 2 channels, 3 z-slices - default axis_order (c before z)
    pytest.param(
        np.zeros((2, 2, 3, _Y, _X), dtype=np.uint16),
        {"p": 2, "c": 2, "z": 3},
        "CZYX",
        2,
        (2, 3, _Y, _X),
        id="2pos-2ch-z3-czyx",
    ),
    # 2 positions, 2 channels, 3 z-slices - z-before-c axis_order
    pytest.param(
        np.zeros((2, 3, 2, _Y, _X), dtype=np.uint16),
        {"p": 2, "z": 3, "c": 2},
        "ZCYX",
        2,
        (3, 2, _Y, _X),
        id="2pos-2ch-z3-zcyx",
    ),
    # 4 positions from a 2x2 grid (g remapped to p by ome-writer), 2 channels
    pytest.param(
        np.zeros((4, 2, _Y, _X), dtype=np.uint16),
        {"p": 4, "c": 2},
        "CYX",
        4,
        (2, _Y, _X),
        id="grid-2x2-2ch",
    ),
    # 2 regular positions where pos-1 carries a sub-sequence grid(2rx1c):
    # ome-writer flattens 1 + 2 = 3 virtual positions into p.
    pytest.param(
        np.zeros((3, 2, _Y, _X), dtype=np.uint16),
        {"p": 3, "c": 2},
        "CYX",
        3,
        (2, _Y, _X),
        id="2pos-subgrid-2r1c",
    ),
]


@pytest.mark.parametrize("arr, sizes, axes, n_files, per_pos_shape", _MULTIPOS_CASES)
def test_save_multiposition(
    tmp_path: Path,
    arr: np.ndarray,
    sizes: dict[str, int],
    axes: str,
    n_files: int,
    per_pos_shape: tuple[int, ...],
) -> None:
    path = str(tmp_path / "mda.ome.tif")
    _save_multiposition(arr, sizes, path, pixel_size_um=None, z_step_um=None, axes=axes)

    files = sorted(tmp_path.glob("*.ome.tif"))
    assert len(files) == n_files

    for i, f in enumerate(files):
        assert f.name == f"mda_p{i:03d}.ome.tif", f"unexpected filename: {f.name}"
        assert _array_shape(f) == per_pos_shape, f"wrong shape in {f.name}"
        assert _series_axes(f) == axes, f"wrong axes in {f.name}"


def test_save_multiposition_with_metadata(tmp_path: Path) -> None:
    """Physical-size metadata must appear in every per-position file."""
    arr = np.zeros((2, 2, 3, _Y, _X), dtype=np.uint16)  # (p, c, z, Y, X)
    sizes = {"p": 2, "c": 2, "z": 3}
    path = str(tmp_path / "mda.ome.tif")
    _save_multiposition(
        arr, sizes, path, pixel_size_um=0.65, z_step_um=0.3, axes="CZYX"
    )

    files = sorted(tmp_path.glob("*.ome.tif"))
    assert len(files) == 2
    for f in files:
        ome = _ome_xml(f)
        assert "0.65" in ome, f"pixel_size_um missing from {f.name}"
        assert "0.3" in ome, f"z_step_um missing from {f.name}"
