from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal, TypeAlias

from pymmcore_plus._logger import logger
from pymmcore_plus.mda.handlers import TensorStoreHandler

if TYPE_CHECKING:
    from collections.abc import Mapping
    from os import PathLike
from pymmcore_plus.metadata.serialize import json_dumps, json_loads

TsDriver: TypeAlias = Literal["zarr", "zarr3", "n5", "neuroglancer_precomputed"]

WAIT_TIME = 10  # seconds


class _TensorStoreHandler(TensorStoreHandler):
    def __init__(
        self,
        *,
        driver: TsDriver = "zarr",
        kvstore: str | dict | None = "memory://",
        path: str | PathLike | None = None,
        delete_existing: bool = False,
        spec: Mapping | None = None,
    ) -> None:
        super().__init__(
            driver=driver,
            kvstore=kvstore,
            path=path,
            delete_existing=delete_existing,
            spec=spec,
        )

    # override this method to make sure the ".zattrs" file is written
    def finalize_metadata(self) -> None:
        """Finalize and flush metadata to storage."""
        if not (store := self._store) or not store.kvstore:
            return  # pragma: no cover

        metadata = {"frame_metadatas": [m[1] for m in self.frame_metadatas]}
        if not self._nd_storage:
            metadata["frame_indices"] = [
                (tuple(dict(k).items()), v)  # type: ignore
                for k, v in self._frame_indices.items()
            ]

        if self.ts_driver.startswith("zarr"):
            store.kvstore.write(".zattrs", json_dumps(metadata).decode("utf-8"))
            attrs = store.kvstore.read(".zattrs").result().value
            logger.info("Writing 'tensorstore_zarr' store 'zattrs' to disk.")
            start_time = time.time()
            # HACK: wait for attrs to be written. If we don't have the while loop,
            # most of the time the attrs will not be written. To avoid looping forever,
            # we wait for WAIT_TIME seconds. If the attrs are not written by then,
            # we continue.
            while not attrs and not time.time() - start_time > WAIT_TIME:
                store.kvstore.write(".zattrs", json_dumps(metadata).decode("utf-8"))
                attrs = store.kvstore.read(".zattrs").result().value

        elif self.ts_driver == "n5":  # pragma: no cover
            attrs = json_loads(store.kvstore.read("attributes.json").result().value)
            attrs.update(metadata)
            store.kvstore.write("attributes.json", json_dumps(attrs).decode("utf-8"))
