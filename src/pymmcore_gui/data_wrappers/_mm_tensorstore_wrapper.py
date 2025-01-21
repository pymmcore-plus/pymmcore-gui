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

        # get dims from "input_labels" in the transform of the spec
        spec = self._data._store.spec().to_json()
        dims = [str(x) for x in spec["transform"]["input_labels"]]

        if isinstance(dims, Sequence) and len(dims) == len(self._data._store.domain):
            self._dims: tuple[Hashable, ...] = tuple(str(x) for x in dims)
        else:
            self._dims = tuple(range(len(self._data._store.domain)))

        self._coords = {
            i: range(s)
            for i, s in zip(self._dims, self._data._store.domain.shape, strict=False)
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
        return dict(zip(self._dims, self._data._store.domain.shape, strict=False))

    def isel(self, indexers: Mapping[str, int]) -> Any:
        return self._data.isel(indexers)
