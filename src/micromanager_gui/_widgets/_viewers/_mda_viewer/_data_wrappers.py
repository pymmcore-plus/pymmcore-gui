from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Hashable, Mapping, TypeGuard

from ndv import DataWrapper
from pymmcore_plus.mda.handlers import TensorStoreHandler

from micromanager_gui.readers import TensorstoreZarrReader

if TYPE_CHECKING:
    from pathlib import Path

    from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase


class MMTensorstoreWrapper(DataWrapper["TensorStoreHandler"]):
    """Wrapper for pymmcore_plus.mda.handlers.TensorStoreHandler objects."""

    def __init__(self, data: Any) -> None:
        super().__init__(data)

        self._data: TensorStoreHandler = data

    @classmethod
    def supports(cls, obj: Any) -> bool:
        return isinstance(obj, TensorStoreHandler)

    def sizes(self) -> Mapping[str, int]:
        with suppress(Exception):
            return self._data.current_sequence.sizes
        return {}

    def guess_channel_axis(self) -> Hashable | None:
        return "c"

    def isel(self, indexers: Mapping[str, int]) -> Any:
        return self._data.isel(indexers)

    def save_as_zarr(self, save_loc: str | Path) -> None:
        # to have access to the metadata, the generated zarr file should be opened with
        # the micromanager_gui.readers.TensorstoreZarrReader

        # TODO: find a way to save as ome-zarr

        import tensorstore as ts

        if (store := self._data.store) is None:
            return
        new_spec = store.spec().to_json()
        new_spec["kvstore"] = {"driver": "file", "path": str(save_loc)}
        new_ts = ts.open(new_spec, create=True).result()
        new_ts[:] = store.read().result()
        if meta_json := store.kvstore.read(".zattrs").result().value:
            new_ts.kvstore.write(".zattrs", meta_json).result()

    def save_as_tiff(self, save_loc: str | Path) -> None:
        if (store := self._data.store) is None:
            return
        reader = TensorstoreZarrReader(store)
        reader.write_tiff(save_loc)


class MM5DWriterWrapper(DataWrapper["_5DWriterBase"]):
    """Wrapper for pymmcore_plus.mda.handlers._5DWriterBase objects."""

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[_5DWriterBase]:
        try:
            from pymmcore_plus.mda.handlers._5d_writer_base import _5DWriterBase
        except ImportError:
            from pymmcore_plus.mda.handlers import OMETiffWriter, OMEZarrWriter

            _5DWriterBase = (OMETiffWriter, OMEZarrWriter)  # type: ignore

        return isinstance(obj, _5DWriterBase)

    def sizes(self) -> Mapping[Hashable, int]:
        try:
            return super().sizes()  # type: ignore
        except NotImplementedError:
            return {}

    def guess_channel_axis(self) -> Hashable | None:
        return "c"

    def isel(self, indexers: Mapping[str, int]) -> Any:
        return self._data.isel(indexers)

    def save_as_zarr(self, save_loc: str | Path) -> None:
        raise NotImplementedError

    def save_as_tiff(self, save_loc: str | Path) -> None:
        raise NotImplementedError
