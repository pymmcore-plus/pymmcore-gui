from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Mapping, cast

import useq
import zarr

if TYPE_CHECKING:
    import numpy as np
    from zarr.hierarchy import Group

EVENT = "Event"
FRAME_META = "frame_meta"
ARRAY_DIMS = "_ARRAY_DIMENSIONS"


class OMEZarrReader:
    """Reads a ome-zarr file generated with the 'OMEZarrWriter'.

    Parameters
    ----------
    path : str | Path
        The path to the ome-zarr file.

    Attributes
    ----------
    path : Path
        The path to the ome-zarr file.
    store : zarr.Group
        The zarr file.
    sequence : useq.MDASequence | None
        The acquired useq.MDASequence. It is loaded from the metadata using the
        `useq.MDASequence` key.

    Usage
    -----
    reader = OMEZarrReader("path/to/file")
    # to get the numpy array for a specific axis, for example, the first time point for
    # the first position and the first z-slice:
    data = reader.isel({"p": 0, "t": 1, "z": 0})
    # to also get the metadata for the given index:
    data, metadata = reader.isel({"p": 0, "t": 1, "z": 0}, metadata=True)
    """

    def __init__(self, path: str | Path):
        self._path = path

        # open the zarr file
        self._store: Group = zarr.open(self._path)

        # the useq.MDASequence if it exists
        self._sequence: useq.MDASequence | None = None

    # ___________________________Public Methods___________________________

    @property
    def path(self) -> Path:
        """Return the path."""
        return Path(self._path)

    @property
    def store(self) -> Group:
        """Return the zarr file."""
        return self._store

    @property
    def sequence(self) -> useq.MDASequence | None:
        """Return the MDASequence if it exists."""
        try:
            seq = cast(dict, self._store["p0"].attrs["useq_MDASequence"])
            self._sequence = useq.MDASequence(**seq) if seq is not None else None
        except KeyError:
            self._sequence = None
        return self._sequence

    def isel(
        self, indexers: dict[str, int], metadata: bool = False
    ) -> np.ndarray | tuple[np.ndarray, dict]:
        """Select data from the array.

        Parameters
        ----------
        indexers : Mapping[str, int]
            The indexers to select the data. Thy should contain the 'p' axis since the
            OMEZarrWriter saves each position as a separate array. If not present, it
            assume the first position {"p": 0}.
        metadata : bool
            If True, return the metadata as well as a list of dictionaries. By default,
            False.
        """
        # add the position axis if not present
        if "p" not in indexers:
            indexers["p"] = 0
        pos_key = f"p{indexers['p']}"
        index = self._get_axis_index(indexers, pos_key)
        data = self.store[pos_key][index].squeeze()
        if metadata:
            meta = self._get_metadata_from_index(indexers, pos_key)
            return data, meta
        return data

    # ___________________________Private Methods___________________________

    def _get_axis_index(
        self, indexers: Mapping[str, int], pos_key: str
    ) -> tuple[object, ...]:
        """Return a tuple to index the data for the given axis."""
        axis_order = self.store[pos_key].attrs.get(ARRAY_DIMS)  # ['t','c','y','x']
        # add p if not in the axis order
        if "p" not in axis_order:
            axis_order = ["p", *axis_order]
        # remove x and y from the axis order
        if "x" in axis_order:
            axis_order.remove("x")
        if "y" in axis_order:
            axis_order.remove("y")

        # if any of the indexers are not in the axis order, raise an error
        if not set(indexers.keys()).issubset(set(axis_order)):
            raise ValueError(f"Invalid axis in indexers: {indexers}, {axis_order}")

        # get the correct index for the axis
        # e.g. (slice(None), 1, slice(None), slice(None))
        return tuple(
            indexers[axis] if axis in indexers else slice(None) for axis in axis_order
        )

    def _get_metadata_from_index(
        self, indexers: Mapping[str, int], pos_key: str
    ) -> list[dict]:
        """Return the metadata for the given indexers."""
        metadata = []
        for meta in self.store[pos_key].attrs.get(FRAME_META, []):
            event_index = meta["Event"]["index"]  # e.g. {"p": 0, "t": 1}
            if indexers.items() <= event_index.items():
                metadata.append(meta)
        return metadata
