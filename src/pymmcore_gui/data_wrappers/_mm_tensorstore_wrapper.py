from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from typing import Any

from ndv import DataWrapper
from pymmcore_plus.mda.handlers import TensorStoreHandler


class MMTensorstoreWrapper(DataWrapper["TensorStoreHandler"]):
    """Wrapper for pymmcore_plus.mda.handlers.TensorStoreHandler objects."""

    def __init__(self, data: Any) -> None:
        super().__init__(data)

        self._data: TensorStoreHandler = data
        self._dims: tuple[Hashable, ...] = ()
        self._coords: Mapping[Hashable, Sequence] = {}

    @classmethod
    def supports(cls, obj: Any) -> bool:
        return isinstance(obj, TensorStoreHandler)

    @property
    def dims(self) -> tuple[Hashable, ...]:
        """Return the dimension labels for the data."""
        if self._dims:
            return self._dims

        if (store := self._data._store) is None:
            return ()
        spec = store.spec().to_json()

        dims = [str(x) for x in spec["transform"]["input_labels"]]
        print("     dims1:", dims)

        if isinstance(dims, Sequence) and len(dims) == len(self._data._store.domain):
            self._dims: tuple[Hashable, ...] = tuple(str(x) for x in dims)
            print("     self._dims1:", self._dims)
            # self._data = self.data._store[ts.d[:].label[self._dims]]
        else:
            self._dims = tuple(range(len(self._data._store.domain)))
            print("     self._dims2:", self._dims)

        return self._dims

    @property
    def coords(self) -> Mapping[Hashable, Sequence]:
        """Return the coordinates for the data."""
        if self._coords:
            return self._coords

        if not self._dims or not self._data:
            return {}

        self._coords = {
            i: range(s)
            for i, s in zip(self._dims, self._data._store.domain.shape, strict=False)
        }

        return self._coords

    def sizes(self) -> Mapping[Hashable, int]:
        if not self._dims or not self._data:
            return {}
        return dict(zip(self._dims, self._data._store.domain.shape, strict=False))

    def guess_channel_axis(self) -> Hashable | None:
        return "c"

    def isel(self, indexers: Mapping[str, int]) -> Any:
        return self._data.isel(indexers)


# class MMTensorstoreWrapper(DataWrapper["TensorStoreHandler"]):
#     """Wrapper for pymmcore_plus.mda.handlers.TensorStoreHandler objects."""

#     def __init__(self, data: Any) -> None:
#         super().__init__(data)

#         self._data: TensorStoreHandler = data

#     @classmethod
#     def supports(cls, obj: Any) -> bool:
#         return isinstance(obj, TensorStoreHandler)

#     def sizes(self) -> Mapping[str, int]:
#         with suppress(Exception):
#             return self.data.current_sequence.sizes  # type: ignore
#         return {}

#     def guess_channel_axis(self) -> Hashable | None:
#         return "c"

#     def isel(self, indexers: Mapping[str, int]) -> Any:
#         return self.data.isel(indexers)

#     def save_as_zarr(self, save_loc: str | Path) -> None:
#         # to have access to the metadata, the generated zarr file should be opened with
#         # the micromanager_gui.readers.TensorstoreZarrReader

#         # TODO: find a way to save as ome-zarr

#         import tensorstore as ts

#         if (store := self.data.store) is None:
#             return
#         new_spec = store.spec().to_json()
#         new_spec["kvstore"] = {"driver": "file", "path": str(save_loc)}
#         new_ts = ts.open(new_spec, create=True).result()
#         new_ts[:] = store.read().result()
#         if meta_json := store.kvstore.read(".zattrs").result().value:
#             new_ts.kvstore.write(".zattrs", meta_json).result()

#     def save_as_tiff(self, save_loc: str | Path) -> None:
#         if (store := self.data.store) is None:
#             return
#         reader = TensorstoreZarrReader(store)
#         reader.write_tiff(save_loc)
