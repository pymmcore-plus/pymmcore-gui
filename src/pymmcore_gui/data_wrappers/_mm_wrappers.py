from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from ndv import DataWrapper
from pymmcore_plus.mda.handlers import OMEZarrWriter, TensorStoreHandler

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase


class MMTensorstoreWrapper(DataWrapper["TensorStoreHandler"]):
    """Wrapper for pymmcore_plus.mda.handlers.TensorStoreHandler objects."""

    def __init__(self, data: Any) -> None:
        super().__init__(data)

        self._data: TensorStoreHandler = data

        # get dims from "input_labels" in the transform of the spec
        spec = self.data.store.spec().to_json()
        dims = [str(x) for x in spec["transform"]["input_labels"]]

        if isinstance(dims, Sequence) and len(dims) == len(self.data.store.domain):
            self._dims: tuple[Hashable, ...] = tuple(str(x) for x in dims)
        else:
            self._dims = tuple(range(len(self.data.store.domain)))

        self._coords = {
            i: range(s)
            for i, s in zip(self._dims, self.data.store.domain.shape, strict=False)
        }

    @classmethod
    def supports(cls, obj: Any) -> bool:
        return isinstance(obj, TensorStoreHandler)

    @property
    def dims(self) -> tuple[Hashable, ...]:
        """Return the dimension labels for the data."""
        return self._dims

    @property
    def coords(self) -> Mapping[Hashable, Sequence]:
        """Return the coordinates for the data."""
        return self._coords

    def sizes(self) -> Mapping[Hashable, int]:
        """Return the sizes of the dimensions."""
        return dict(zip(self._dims, self.data.store.domain.shape, strict=False))

    def isel(self, index: Mapping[str, int | slice]) -> Any:
        """Return a slice of the data as a numpy array."""
        return self.data.isel(index)

    def save_as_zarr(self, path: str | Path) -> None:
        import tensorstore as ts

        if (store := self.data.store) is None:
            return
        new_spec = store.spec().to_json()
        new_spec["kvstore"] = {"driver": "file", "path": str(path)}
        new_ts = ts.open(new_spec, create=True).result()
        new_ts[:] = store.read().result()
        if meta_json := store.kvstore.read(".zattrs").result().value:
            new_ts.kvstore.write(".zattrs", meta_json).result()

    # def save_as_tiff(self, path: str | Path) -> None:
        # ...


# class MM5DWriterWrapper(DataWrapper["_5DWriterBase"]):
#     """Wrapper for pymmcore_plus.mda.handlers._5DWriterBase objects."""

#     @classmethod
#     def supports(cls, obj: Any) -> bool:
#         try:
#             from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
#         except ImportError:
#             from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter

#             _5DWriterBase = (OMETiffWriter, OMEZarrWriter)  # type: ignore

#         return isinstance(obj, _5DWriterBase)

#     @property
#     def dims(self) -> tuple[Hashable, ...]:
#         """Return the dimension labels for the data."""
#         return self._dims

#     @property
#     def coords(self) -> Mapping[Hashable, Sequence]:
#         """Return the coordinates for the data."""
#         ...

#     def sizes(self) -> Mapping[Hashable, int]:
#         """Return the sizes of the dimensions."""
#         ...

#     def sizes(self) -> Mapping[Hashable, int]:
#         ...

#     def isel(self, index: Mapping[str, int | slice]) -> Any:
#         """Return a slice of the data as a numpy array."""
#         return self.data.isel(index)

#     def save_as_zarr(self, save_loc: str | Path) -> None:
#         # TODO: implement logic for OMETiffWriter
#         if isinstance(self.data, OMEZarrWriter):
#             import zarr

#             # save a copy of the ome-zarr file
#             new_store = zarr.DirectoryStore(str(save_loc))
#             new_group = zarr.group(store=new_store, overwrite=True)
#             # the group property returns a zarr.hierarchy.Group object
#             zarr.copy_all(self.data.group, new_group)
#         else:  #  OMETiffWriter
#             raise NotImplementedError(
#                 "Saving as Zarr is not yet implemented for OMETiffWriter."
#             )

    # def save_as_tiff(self, path: str | Path) -> None:
    #     ...
