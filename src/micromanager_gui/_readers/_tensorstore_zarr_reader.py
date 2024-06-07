import json
from pathlib import Path
from typing import Any, Mapping, cast

import numpy as np
import tensorstore as ts
import useq
from tifffile import imwrite
from tqdm import tqdm


class TensorstoreZarrReader:
    """Read a tensorstore zarr file generated with the 'TensorstoreZarrWriter'.

    Parameters
    ----------
    path : str | Path
        The path to the tensorstore zarr file.

    Attributes
    ----------
    path : Path
        The path to the tensorstore zarr file.
    store : ts.TensorStore
        The tensorstore.
    sequence : useq.MDASequence
        The acquired useq.MDASequence. It is loaded from the metadata using the
        `useq.MDASequence` key.

    Usage
    -----
    reader = TensorZarrReader("path/to/file")
    # to get the numpy array for a specific axis, for example, the first time point for
    # the first position and the first z-slice:
    data = reader.isel({"p": 0, "t": 1, "z": 0})
    # to also get the metadata for the given index:
    data, metadata = reader.isel({"p": 0, "t": 1, "z": 0}, metadata=True)
    """

    def __init__(self, path: str | Path):
        self._path = path

        spec = {
            "driver": "zarr",
            "kvstore": {"driver": "file", "path": str(self._path)},
        }

        _store = ts.open(spec).result()

        self._metadata: dict = {}
        if metadata_json := _store.kvstore.read(".zattrs").result().value:
            self._metadata = json.loads(metadata_json)

        # set the axis labels
        if self.sequence is not None:
            # not sure if is x, y or y, x
            axis_order = [*self.sequence.axis_order, "y", "x"]
            if len(axis_order) > 2:
                _store = _store[ts.d[:].label[*axis_order]]

        self._store = _store

    @property
    def path(self) -> Path:
        """Return the path."""
        return Path(self._path)

    @property
    def store(self) -> ts.TensorStore:
        """Return the tensorstore."""
        return self._store

    @property
    def sequence(self) -> useq.MDASequence | None:
        seq = self._metadata.get("useq_MDASequence")
        return useq.MDASequence(**json.loads(seq)) if seq is not None else None

    # ___________________________Public Methods___________________________

    def isel(
        self,
        indexers: Mapping[str, int] | None = None,
        metadata: bool = False,
        **kwargs: Any,
    ) -> np.ndarray | tuple[np.ndarray, list[dict]]:
        """Select data from the array.

        Parameters
        ----------
        indexers : Mapping[str, int] | None
            The indexers to select the data (e.g. {"p": 0, "t": 1}). If None, return
            the entire data.
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
                raise TypeError(
                    "kwargs must be a mapping from strings to integers (e.g. p=0, t=1)!"
                )

        index = self._get_axis_index(indexers)
        data = cast(np.ndarray, self.store[index].read().result().squeeze())
        if metadata:
            meta = self._get_metadata_from_index(indexers)
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
                raise TypeError("kwargs must be a mapping from strings to integers")

        if indexers:
            data, metadata = self.isel(indexers, metadata=True)
            imj = len(data.shape) <= 5
            if Path(path).suffix not in {".tif", ".tiff"}:
                path = Path(path).with_suffix(".tiff")
            if not Path(path).parent.exists():
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            imwrite(path, data, imagej=imj)
            # save metadata as json
            dest = Path(path).with_suffix(".json")
            dest.write_text(json.dumps(metadata))

        else:
            if self.sequence is None:
                raise ValueError("No 'useq.MDASequence' found in the metadata!")
            if pos := len(self.sequence.stage_positions):
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

    def _get_axis_index(self, indexers: Mapping[str, int]) -> tuple[object, ...]:
        """Return a tuple to index the data for the given axis."""
        if self.sequence is None:
            raise ValueError("No 'useq.MDASequence' found in the metadata!")

        axis_order = self.sequence.axis_order

        # if any of the indexers are not in the axis order, raise an error
        if not set(indexers.keys()).issubset(set(axis_order)):
            raise ValueError("Invalid axis in indexers!")

        # get the correct index for the axis
        # e.g. (slice(None), 1, slice(None), slice(None))
        return tuple(
            indexers[axis] if axis in indexers else slice(None) for axis in axis_order
        )

    def _get_metadata_from_index(self, indexers: Mapping[str, int]) -> list[dict]:
        """Return the metadata for the given indexers."""
        metadata = []
        for meta in self._metadata.get("frame_metadatas", []):
            event_index = meta["Event"]["index"]  # e.g. {"p": 0, "t": 1}
            if indexers.items() <= event_index.items():
                metadata.append(meta)
        return metadata
