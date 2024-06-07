from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, cast

import numpy as np
import useq
import zarr
from tifffile import imwrite
from tqdm import tqdm

if TYPE_CHECKING:
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
        self,
        indexers: Mapping[str, int] | None = None,
        metadata: bool = False,
        **kwargs: Any,
    ) -> np.ndarray | tuple[np.ndarray, list[dict]]:
        """Select data from the array.

        Parameters
        ----------
        indexers : Mapping[str, int]
            The indexers to select the data. Thy should contain the 'p' axis since the
            OMEZarrWriter saves each position as a separate array. If None, it
            assume the first position {"p": 0}.
        metadata : bool
            If True, return the metadata as well as a list of dictionaries. By default,
            False.
        **kwargs : Any
            Additional way to pass the indexers. You can pass the indexers as kwargs
            (e.g. p=0, t=1). NOTE: kwargs will overwrite the indexers if already present
            in the indexers mapping.
        """
        if indexers is None:
            indexers = {}
        if kwargs:
            if all(
                isinstance(k, str) and isinstance(v, int) for k, v in kwargs.items()
            ):
                indexers = {**indexers, **kwargs}
            else:
                raise TypeError("kwargs must be a mapping from strings to integers")

        if len(self.store.keys()) > 1 and "p" not in indexers:
            raise ValueError(
                "The indexers should contain the 'p' axis since the zarr store has "
                "more than one position."
            )

        pos_key = f"p{indexers.get('p', 0)}"
        index = self._get_axis_index(indexers, pos_key)
        data = cast(np.ndarray, self.store[pos_key][index].squeeze())
        if metadata:
            meta = self._get_metadata_from_index(indexers, pos_key)
            return data, meta
        return data

    def write_tiff(
        self,
        path: str | Path,
        indexers: Mapping[str, int] | None = None,
        **kwargs: Any,
    ) -> None:
        """Write the data to a tiff file.

        Parameters
        ----------
        path : str | Path
            The path to the tiff file. If `indexers` is a Mapping of axis and index,
            the path should be a file path (e.g. 'path/to/file.tif'). Otherwise, it
            should be a directory path (e.g. 'path/to/directory').
        indexers : Mapping[str, int] | None
            The indexers to select the data. If None, write all the data per position
            to a tiff file. If a Mapping of axis and index (e.g. {"p": 0, "t": 1}),
            write the data for the given index to a tiff file.
        **kwargs : Any
            Additional way to pass the indexers. You can pass the indexers as kwargs
            (e.g. p=0, t=1). NOTE: kwargs will overwrite the indexers if already present
            in the indexers mapping.
        """
        if kwargs:
            indexers = indexers or {}
            if all(
                isinstance(k, str) and isinstance(v, int) for k, v in kwargs.items()
            ):
                indexers = {**indexers, **kwargs}
            else:
                raise TypeError(
                    "kwargs must be a mapping from strings to integers (e.g. p=0, t=1)!"
                )

        if indexers:
            data, metadata = self.isel(indexers, metadata=True)
            imj = len(data.shape) <= 5
            if Path(path).suffix not in {".tif", ".tiff"}:
                path = Path(path).with_suffix(".tiff")
            imwrite(path, data, imagej=imj)
            # save metadata as json
            dest = Path(path).with_suffix(".json")
            dest.write_text(json.dumps(metadata))

        else:
            keys = [
                key
                for key in self.store.keys()
                if key.startswith("p") and key[1:].isdigit()
            ]
            if pos := len(keys):
                if not Path(path).exists():
                    Path(path).mkdir(parents=True, exist_ok=False)
                with tqdm(total=pos) as pbar:
                    for i in range(pos):
                        data, metadata = self.isel({"p": i}, metadata=True)
                        imwrite(Path(path) / f"p{i}.tif", data, imagej=True)
                        # save metadata as json
                        dest = Path(path) / f"p{i}.json"
                        dest.write_text(json.dumps(metadata))
                        pbar.update(1)

    # ___________________________Private Methods___________________________

    def _get_axis_index(
        self, indexers: Mapping[str, int], pos_key: str
    ) -> tuple[object, ...]:
        """Return a tuple to index the data for the given axis."""
        axis_order = self.store[pos_key].attrs.get(ARRAY_DIMS, [])  # ['t','c','y','x']
        # remove x and y from the axis order
        if "x" in axis_order:
            axis_order.remove("x")
        if "y" in axis_order:
            axis_order.remove("y")

        # if any of the indexers are not in the axis order, raise an error, NOTE: we
        # add "p" to the axis order since the ome-zarr is saved per position
        if not set(indexers.keys()).issubset({"p", *axis_order}):
            raise ValueError(
                f"Invalid axis in indexers {indexers}: available {axis_order}"
            )

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
