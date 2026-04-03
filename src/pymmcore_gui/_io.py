"""IO module for reading image files into xarray DataArrays."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import xarray as xr

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: set[str] = {".tif", ".tiff", ".zarr"}


def imread(path: str | Path, *, series: int = 0, level: int = 0) -> xr.DataArray:
    """Read an image file into an xarray.DataArray."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        result = _read_tiff(path, series=series, level=level)
    elif suffix == ".zarr" or _is_zarr_directory(path):
        result = _read_ome_zarr(path, series=series, level=level)
    else:
        raise ValueError(
            f"Unsupported file format: {suffix!r}. Supported: {SUPPORTED_EXTENSIONS}"
        )

    logger.info("Read %s", path)
    return _ensure_all_coords(result)


# ----------------------- TIFF reader -----------------------


def _read_tiff(path: Path, *, series: int = 0, level: int = 0) -> xr.DataArray:
    import tifffile
    import xarray as xr

    tf = tifffile.TiffFile(path)
    s = tf.series[series]

    if 0 < level < len(s.levels):
        s = s.levels[level]

    data = s.asarray()
    dims = tuple(s.axes.replace("S", "C"))

    coords: dict[str, list[str]] = {}
    attrs: dict[str, object] = {}
    ndv_display: dict[str, object] = {}

    if tf.is_ome:
        ome = tf.ome_metadata
        if ome is not None:
            _apply_ome_metadata(ome, series, dims, coords, ndv_display)

    if ndv_display:
        attrs["ndv_display"] = ndv_display

    return xr.DataArray(data, dims=dims, coords=coords, attrs=attrs)


def _apply_ome_metadata(
    ome: str,
    series: int,
    dims: tuple[str, ...],
    coords: dict[str, list[str]],
    ndv_display: dict[str, object],
) -> None:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(ome)
    ns = {"ome": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
    prefix = f"{{{ns['ome']}}}" if ns else ""

    images = root.findall(f"{prefix}Image")
    if series >= len(images):
        return
    image = images[series]
    pixels = image.find(f"{prefix}Pixels")
    if pixels is None:
        return

    channels = pixels.findall(f"{prefix}Channel")
    if channels and "C" in dims:
        names = []
        colors: dict[int, str] = {}
        for i, ch in enumerate(channels):
            name = ch.get("Name", f"Ch{i}")
            names.append(name)
            color = ch.get("Color")
            if color is not None:
                cmap_name = _ome_color_to_cmap(int(color))
                if cmap_name:
                    colors[i] = cmap_name
        coords["C"] = names
        if colors:
            ndv_display["channel_colors"] = colors


def _ome_color_to_cmap(color_int: int) -> str | None:
    """Convert OME integer color (RGBA packed) to a cmap name."""
    color_int = color_int & 0xFFFFFFFF
    r = (color_int >> 24) & 0xFF
    g = (color_int >> 16) & 0xFF
    b = (color_int >> 8) & 0xFF

    if r > 200 and g < 50 and b < 50:
        return "red"
    if r < 50 and g > 200 and b < 50:
        return "green"
    if r < 50 and g < 50 and b > 200:
        return "blue"
    if r > 200 and g > 200 and b < 50:
        return "yellow"
    if r > 200 and g < 50 and b > 200:
        return "magenta"
    if r < 50 and g > 200 and b > 200:
        return "cyan"
    if r > 200 and g > 200 and b > 200:
        return "gray"
    return None


# ----------------------- OME-Zarr reader -----------------------


def _is_zarr_directory(path: Path) -> bool:
    if path.is_dir():
        return (path / ".zattrs").exists() or (path / "zarr.json").exists()
    return False


def _read_ome_zarr(path: Path, *, series: int = 0, level: int = 0) -> xr.DataArray:
    import xarray as xr
    import yaozarrs
    from yaozarrs import v05

    group = yaozarrs.open_group(str(path))
    meta = group.ome_metadata()

    if isinstance(meta, v05.Bf2Raw):
        return _read_bf2raw(group, level=level)
    if isinstance(meta, v05.Image):
        return _read_multiscale(group, meta, level=level)

    # Fallback: try reading as a plain multiscale at the given path
    store = group[str(level)].to_tensorstore()  # type: ignore[union-attr]
    dims = tuple(f"dim_{i}" for i in range(store.ndim))
    return xr.DataArray(store, dims=dims)


def _read_bf2raw(group: Any, *, level: int = 0) -> xr.DataArray:
    """Read a Bioformats2Raw layout, stacking all series into a 'P' dim."""
    import xarray as xr
    from yaozarrs import v05

    series_meta = group["OME"].ome_metadata()
    if not isinstance(series_meta, v05.Series):
        raise ValueError("Bf2Raw layout missing OME/Series metadata")

    arrays: list[xr.DataArray] = []
    for series_path in series_meta.series:
        sub = group[series_path]
        img_meta = sub.ome_metadata()
        if not isinstance(img_meta, v05.Image):
            continue
        arrays.append(_read_multiscale(sub, img_meta, level=level))

    if not arrays:
        raise ValueError("No image series found in Bf2Raw layout")
    if len(arrays) == 1:
        return arrays[0]
    return xr.concat(arrays, dim="P")


def _read_multiscale(group: Any, meta: Any, *, level: int = 0) -> xr.DataArray:
    """Read a single multiscale Image group."""
    import xarray as xr

    ms = meta.multiscales[0]
    ds = ms.datasets[min(level, len(ms.datasets) - 1)]
    store = group[ds.path].to_tensorstore()

    axes = ms.axes or []
    dims = (
        tuple(ax.name.upper() if len(ax.name) == 1 else ax.name for ax in axes)
        if axes
        else tuple(f"dim_{i}" for i in range(store.ndim))
    )

    attrs: dict[str, object] = {}
    ndv_display: dict[str, object] = {}
    if meta.omero:
        colors: dict[int, str] = {}
        for i, ch in enumerate(meta.omero.channels):
            if ch.color:
                cmap_name = _hex_color_to_cmap(ch.color)
                if cmap_name:
                    colors[i] = cmap_name
        if colors:
            ndv_display["channel_colors"] = colors
    if ndv_display:
        attrs["ndv_display"] = ndv_display

    return xr.DataArray(store, dims=dims, attrs=attrs)


def _hex_color_to_cmap(color: str) -> str | None:
    """Convert hex color string to a cmap name."""
    color = color.lstrip("#").upper()
    if len(color) < 6:
        return None

    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)

    if r > 200 and g < 50 and b < 50:
        return "red"
    if r < 50 and g > 200 and b < 50:
        return "green"
    if r < 50 and g < 50 and b > 200:
        return "blue"
    if r > 200 and g > 200 and b < 50:
        return "yellow"
    if r > 200 and g < 50 and b > 200:
        return "magenta"
    if r < 50 and g > 200 and b > 200:
        return "cyan"
    if r > 200 and g > 200 and b > 200:
        return "gray"
    return None


# ----------------------- Helpers -----------------------


def _ensure_all_coords(da: xr.DataArray) -> xr.DataArray:
    """Ensure every dim has a coordinate (ndv needs them for sliders)."""
    missing = {
        dim: list(range(da.sizes[dim])) for dim in da.dims if dim not in da.coords
    }
    if missing:
        da = da.assign_coords(missing)
    return da
