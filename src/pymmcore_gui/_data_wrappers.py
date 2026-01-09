"""DataWrapper for OME-NGFF (OME-Zarr) stores with multi-position and plate support.

This module provides support for opening OME-Zarr stores that follow the
NGFF specification (version 0.4 and 0.5), including:
- Single-position images
- Multi-position (multi-FOV) images
- High-content screening plates with wells and FOVs

Requires the yaozarrs[io] package to be installed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from ndv.models._data_wrapper import DataWrapper

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping, Sequence
    from typing import TypeGuard

    from yaozarrs import ZarrGroup, v04, v05

logger = logging.getLogger(__name__)


# TODO: possibly this should be moved to ndv directly
class NGFFWrapper(DataWrapper["ZarrGroup"]):
    """Wrapper for OME-NGFF/OME-Zarr stores with multi-position/plate support.

    This wrapper handles:
    - Single-position images (standard multiscale)
    - Multi-position/multi-FOV datasets (bioformats2raw layout)
    - HCS plates with wells and fields of view

    For multi-position datasets, a "p" dimension is added as the first
    dimension, allowing navigation through positions using the ndv position slider.

    For plates, positions are ordered by: well (row-major), then FOV within well.

    Examples
    --------
    ```python
    import ndv

    # Works with paths - automatically detected as NGFF
    ndv.imshow("/path/to/data.ome.zarr")

    # Or with yaozarrs ZarrGroup objects
    import yaozarrs

    group = yaozarrs.open_group("/path/to/data.ome.zarr")
    ndv.imshow(group)
    ```
    """

    PRIORITY = 10

    def __init__(self, data: ZarrGroup | str) -> None:
        """Initialize NGFF wrapper.

        Parameters
        ----------
        data : ZarrGroup | str
            Either a yaozarrs ZarrGroup or a string path to an OME-Zarr store.
        """
        import yaozarrs

        # Convert string paths to ZarrGroup
        if isinstance(data, str):
            data = yaozarrs.open_group(data)

        self._zarr_group = data
        self._metadata = data.ome_metadata()
        self._positions: list[tuple[str, int]] = []  # (path, resolution_index) tuples
        self._dims: tuple[Hashable, ...] = ()
        self._coords: dict[Hashable, Sequence] = {}
        self._is_multiposition = False
        self._first_array_path: str | None = None

        # Detect structure and build position list
        self._detect_structure()

        # Initialize parent with the group
        super().__init__(data)

    def _detect_structure(self) -> None:
        """Detect the NGFF structure (plate, well, multiposition, or single image)."""
        from yaozarrs import v04, v05

        metadata = self._metadata

        # Check if this is a plate
        if isinstance(metadata, (v04.Plate, v05.Plate)):
            self._parse_plate()
            return

        # Check if this is a well
        if isinstance(metadata, (v04.Well, v05.Well)):
            self._parse_well()
            return

        # Check if it has multiscales (single or multi-position image)
        if hasattr(metadata, "multiscales") and metadata.multiscales:
            # Check for bioformats2raw layout (multi-position)
            if self._has_bioformats2raw_layout():
                self._parse_bioformats2raw()
                return

            # Standard single-position multiscale image
            self._parse_single_image()
            return

        # Check if it has a bioformats2raw layout at root
        if (
            hasattr(metadata, "bioformats2raw_layout")
            and metadata.bioformats2raw_layout
        ):
            self._parse_bioformats2raw()
            return

        raise ValueError(
            f"Could not determine NGFF structure for {self._zarr_group.store_path}"
        )

    def _has_bioformats2raw_layout(self) -> bool:
        """Check if the zarr group has a bioformats2raw layout."""
        # Check attrs for bioformats2raw.layout
        attrs = self._zarr_group.attrs
        if "bioformats2raw.layout" in attrs:
            return True
        if "ome" in attrs and "bioformats2raw.layout" in attrs["ome"]:
            return True
        return False

    def _parse_plate(self) -> None:
        """Parse a plate structure and collect all FOV positions."""
        logger.debug("Parsing plate structure")
        self._is_multiposition = True

        metadata = cast("v04.Plate | v05.Plate", self._metadata)
        plate_def = metadata.plate

        # Iterate through wells in the plate
        for well_ref in plate_def.wells:
            well_path = well_ref.path
            if well_path not in self._zarr_group:
                logger.warning(f"Well {well_path} not found in plate")
                continue

            well_group = self._zarr_group[well_path]
            well_metadata = well_group.ome_metadata()

            if not hasattr(well_metadata, "well"):
                logger.warning(f"Well {well_path} has no well metadata")
                continue

            # Get FOVs from well
            well_def = well_metadata.well
            for fov in well_def.images:
                fov_path = f"{well_path}/{fov.path}"
                # Use first resolution (index 0)
                self._positions.append((fov_path, 0))

        if not self._positions:
            raise ValueError("No FOV positions found in plate")

        # Get shape from first position
        self._load_first_position_metadata()

    def _parse_well(self) -> None:
        """Parse a well structure and collect all FOV positions."""
        logger.debug("Parsing well structure")
        self._is_multiposition = True

        metadata = cast("v04.Well | v05.Well", self._metadata)
        well_def = metadata.well

        # Collect all FOVs in this well
        for fov in well_def.images:
            fov_path = fov.path
            # Use first resolution (index 0)
            self._positions.append((fov_path, 0))

        if not self._positions:
            raise ValueError("No FOV positions found in well")

        # Get shape from first position
        self._load_first_position_metadata()

    def _parse_bioformats2raw(self) -> None:
        """Parse a bioformats2raw multi-position layout."""
        logger.debug("Parsing bioformats2raw multi-position layout")
        self._is_multiposition = True

        # Look for OME/series or numbered subgroups
        if "OME" in self._zarr_group:
            ome_group = self._zarr_group["OME"]
            ome_meta = ome_group.metadata
            if "series" in ome_meta.attributes:
                series = ome_meta.attributes["series"]
                for path in series:
                    self._positions.append((path, 0))
            else:
                # Fall back to numbered subgroups
                self._find_numbered_positions()
        else:
            # Look for numbered subgroups at root
            self._find_numbered_positions()

        if not self._positions:
            raise ValueError("No positions found in bioformats2raw layout")

        # Get shape from first position
        self._load_first_position_metadata()

    def _find_numbered_positions(self) -> None:
        """Find numbered position subgroups (0, 1, 2, ...)."""
        i = 0
        while True:
            path = str(i)
            if path not in self._zarr_group:
                break
            # Check if it has multiscales
            child = self._zarr_group[path]
            if hasattr(child, "ome_metadata"):
                child_meta = child.ome_metadata()
                if hasattr(child_meta, "multiscales") and child_meta.multiscales:
                    self._positions.append((path, 0))
            i += 1

    def _parse_single_image(self) -> None:
        """Parse a single multiscale image."""
        logger.debug("Parsing single-position image")
        self._is_multiposition = False

        # Use the first multiscale, first resolution
        metadata = self._metadata
        if not hasattr(metadata, "multiscales") or not metadata.multiscales:
            raise ValueError("No multiscales found in image")

        multiscale = metadata.multiscales[0]
        if not multiscale.datasets:
            raise ValueError("No datasets found in multiscale")

        dataset_path = multiscale.datasets[0].path
        self._first_array_path = dataset_path

        # Get the actual array
        if dataset_path not in self._zarr_group:
            raise ValueError(f"Dataset path {dataset_path} not found")

        array_node = self._zarr_group[dataset_path]
        from yaozarrs._zarr import ZarrArray

        if not isinstance(array_node, ZarrArray):
            raise ValueError(f"Expected ZarrArray at {dataset_path}")

        # Build dims and coords from axes
        if hasattr(multiscale, "axes"):
            self._dims = tuple(axis.name for axis in multiscale.axes)
        else:
            # Fallback to numbered dimensions
            self._dims = tuple(range(len(array_node.metadata.shape)))

        # Build coords
        shape = array_node.metadata.shape
        if shape is None:
            raise ValueError(f"Array at {dataset_path} has no shape")

        self._coords = {dim: range(size) for dim, size in zip(self._dims, shape, strict=False)}

    def _load_first_position_metadata(self) -> None:
        """Load metadata from the first position to determine shape and axes."""
        if not self._positions:
            raise ValueError("No positions to load metadata from")

        first_pos_path, res_idx = self._positions[0]

        # Navigate to the position group
        pos_group = self._zarr_group[first_pos_path]
        pos_metadata = pos_group.ome_metadata()

        if not hasattr(pos_metadata, "multiscales") or not pos_metadata.multiscales:
            raise ValueError(f"Position {first_pos_path} has no multiscales")

        multiscale = pos_metadata.multiscales[0]
        if res_idx >= len(multiscale.datasets):
            raise ValueError(
                f"Resolution index {res_idx} out of range for position {first_pos_path}"
            )

        dataset_path = multiscale.datasets[res_idx].path
        full_array_path = f"{first_pos_path}/{dataset_path}"

        # Store for later reference
        self._first_array_path = full_array_path

        # Get the actual array
        array_node = pos_group[dataset_path]
        from yaozarrs._zarr import ZarrArray

        if not isinstance(array_node, ZarrArray):
            raise ValueError(f"Expected ZarrArray at {full_array_path}")

        # Build dims with "position" as first dimension
        if hasattr(multiscale, "axes"):
            inner_dims = tuple(axis.name for axis in multiscale.axes)
        else:
            # Fallback to numbered dimensions
            shape = array_node.metadata.shape
            if shape is None:
                raise ValueError(f"Array at {full_array_path} has no shape")
            inner_dims = tuple(range(len(shape)))

        self._dims = ("p", *inner_dims)

        # Build coords
        shape = array_node.metadata.shape
        if shape is None:
            raise ValueError(f"Array at {full_array_path} has no shape")

        self._coords = {"p": range(len(self._positions))}
        for dim, size in zip(inner_dims, shape, strict=False):
            self._coords[dim] = range(size)

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[ZarrGroup]:
        """Check if the object is an OME-Zarr store or path.

        Parameters
        ----------
        obj : Any
            Object to check.

        Returns
        -------
        bool
            True if obj is a yaozarrs.ZarrGroup or a string path to an OME-Zarr store.
        """
        # Check if it's a ZarrGroup with OME metadata
        try:
            from yaozarrs._zarr import ZarrGroup

            if isinstance(obj, ZarrGroup):
                # Check if it has OME metadata
                try:
                    return obj.ome_metadata() is not None
                except Exception:
                    return False
        except ImportError:
            pass

        # Check if it's a string path ending in .ome.zarr
        if isinstance(obj, str):
            if obj.endswith(".ome.zarr"):
                return True
            # Try to open and check for OME metadata
            try:
                import yaozarrs

                group = yaozarrs.open_group(obj)
                return group.ome_metadata() is not None
            except Exception:
                return False

        return False

    @property
    def dims(self) -> tuple[Hashable, ...]:
        """Return the dimension labels for the data."""
        return self._dims

    @property
    def coords(self) -> Mapping[Hashable, Sequence]:
        """Return the coordinates for the data."""
        return self._coords

    def isel(self, indexers: Mapping[int, int | slice]) -> np.ndarray:
        """Select data by integer indices.

        Parameters
        ----------
        indexers : Mapping[int, int | slice]
            Mapping from dimension index to slice/index.

        Returns
        -------
        np.ndarray
            Selected data as numpy array.
        """
        # For single-position images, pass through directly
        if not self._is_multiposition:
            if self._first_array_path is None:
                raise ValueError("No array path available")

            # Navigate to array and slice
            array_node = self._zarr_group[self._first_array_path]
            from yaozarrs._zarr import ZarrArray

            if not isinstance(array_node, ZarrArray):
                raise ValueError(f"Expected ZarrArray at {self._first_array_path}")

            # Convert to zarr-python or tensorstore for actual data access
            try:
                # Try tensorstore first (better performance)
                ts_array = array_node.to_tensorstore()
                idx_tuple = tuple(
                    indexers.get(i, slice(None)) for i in range(len(self._dims))
                )
                return np.asarray(ts_array[idx_tuple].read().result())
            except ImportError:
                # Fall back to zarr-python (v3)
                zarr_array = array_node.to_zarr_python()
                idx_tuple = tuple(
                    indexers.get(i, slice(None)) for i in range(len(self._dims))
                )
                return np.asarray(zarr_array[idx_tuple])
                return np.asarray(zarr_array[idx_tuple])

        # For multi-position, extract position index and slice that position
        pos_idx = indexers.get(0)  # position is always dimension 0
        keep_pos_dim = False  # Track if we should keep position as singleton dimension

        if pos_idx is None or isinstance(pos_idx, slice):
            # For now, only support selecting a single position at a time
            # Could extend to support slicing across positions later
            if pos_idx is None:
                pos_idx = 0
            elif isinstance(pos_idx, slice):
                # Take the start of the slice but remember to add dimension back
                pos_idx = pos_idx.start if pos_idx.start is not None else 0
                keep_pos_dim = True  # slice(0, 1) means we want shape (1, ...)

        if not isinstance(pos_idx, int):
            raise ValueError("Position index must be an integer")

        if pos_idx < 0 or pos_idx >= len(self._positions):
            raise IndexError(
                f"Position index {pos_idx} out of range [0, {len(self._positions)})"
            )

        # Get the path for this position
        pos_path, res_idx = self._positions[pos_idx]

        # Navigate to position and get array path
        pos_group = self._zarr_group[pos_path]
        pos_metadata = pos_group.ome_metadata()

        if not hasattr(pos_metadata, "multiscales") or not pos_metadata.multiscales:
            raise ValueError(f"Position {pos_path} has no multiscales")

        multiscale = pos_metadata.multiscales[0]
        dataset_path = multiscale.datasets[res_idx].path

        # Get array
        array_node = pos_group[dataset_path]
        from yaozarrs._zarr import ZarrArray

        if not isinstance(array_node, ZarrArray):
            raise ValueError(f"Expected ZarrArray at {pos_path}/{dataset_path}")

        # Build index tuple for inner dimensions (skip position dimension)
        inner_indexers = {
            i - 1: indexers[i] for i in range(1, len(self._dims)) if i in indexers
        }
        inner_dims_count = len(self._dims) - 1
        idx_tuple = tuple(
            inner_indexers.get(i, slice(None)) for i in range(inner_dims_count)
        )

        # Read data
        try:
            # Try tensorstore first
            ts_array = array_node.to_tensorstore()
            data = np.asarray(ts_array[idx_tuple].read().result())
        except ImportError:
            # Fall back to zarr-python (v3)
            zarr_array = array_node.to_zarr_python()
            data = np.asarray(zarr_array[idx_tuple])

        # If position was indexed with a slice, add back singleton dimension
        if keep_pos_dim:
            data = data[np.newaxis, ...]

        return data

    @property
    def dtype(self) -> np.dtype:
        """Return the dtype for the data."""
        # Get dtype from first array
        if self._first_array_path is None:
            raise ValueError("No array path available")

        if not self._is_multiposition:
            array_node = self._zarr_group[self._first_array_path]
        else:
            # Navigate through position
            pos_path, _ = self._positions[0]
            pos_group = self._zarr_group[pos_path]
            # Remove position prefix from path
            array_path = self._first_array_path.replace(f"{pos_path}/", "")
            array_node = pos_group[array_path]

        from yaozarrs._zarr import ZarrArray

        if not isinstance(array_node, ZarrArray):
            raise ValueError("Expected ZarrArray")

        return np.dtype(array_node.dtype)  # type: ignore[no-any-return]
