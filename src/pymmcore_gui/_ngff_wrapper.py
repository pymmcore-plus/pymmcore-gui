class NGFFWrapper(DataWrapper):
    """Wrapper for OME-NGFF/OME-Zarr stores.

    Handles single-position, multi-position (bioformats2raw), wells, and plates
    NOTE: if pyramidal datasets are present, only the first resolution level is used.

    It requires the `yaozarrs` package to be installed.
    """

    PRIORITY = 45

    def __init__(self, data: Any) -> None:
        import yaozarrs

        self._group = yaozarrs.open_group(data) if isinstance(data, str) else data
        self._positions: list[str] = []
        self._dataset_path: str = ""
        self._dims, self._coords = self._detect_structure()
        super().__init__(self._group)

    @classmethod
    def supports(cls, obj: Any) -> TypeGuard[Any]:
        with contextlib.suppress(Exception):
            from yaozarrs import ZarrGroup

            if isinstance(obj, ZarrGroup):
                return obj.ome_metadata() is not None

        if isinstance(obj, str):
            with contextlib.suppress(Exception):
                import yaozarrs

                return yaozarrs.open_group(obj).ome_metadata() is not None
        return False

    @property
    def dims(self) -> tuple[Hashable, ...]:
        return self._dims

    @property
    def coords(self) -> Mapping[Hashable, Sequence]:
        return self._coords

    @property
    def dtype(self) -> np.dtype:
        group = self._group[self._positions[0]] if self._positions else self._group
        return np.dtype(group[self._dataset_path].dtype)

    def isel(self, indexers: Mapping[int, int | slice]) -> np.ndarray:
        if self._positions:
            return self._isel_multiposition(indexers)
        return self._isel_single(indexers)

    # ----------------------- Structure Detection -----------------------

    def _detect_structure(
        self,
    ) -> tuple[tuple[Hashable, ...], dict[Hashable, Sequence]]:
        """Detect NGFF structure and return (dims, coords).

        NGFF supports several layouts:
        - Single image: has `multiscales` directly
        - Bf2Raw: has `bioformats2raw.layout`, images in numbered subgroups
        - Series: has explicit `series` array listing image paths
        - Plate: has `plate` with wells containing images
        - Well: has `well` with images array
        """
        from yaozarrs import v04, v05

        meta = self._group.ome_metadata()

        if hasattr(meta, "multiscales") and meta.multiscales:
            return self._init_single(meta)
        if isinstance(meta, (v04.Bf2Raw, v05.Bf2Raw)):
            return self._init_bioformats2raw()
        if isinstance(meta, (v04.Series, v05.Series)):
            self._positions = list(meta.series)
            return self._init_multiposition()
        if isinstance(meta, (v04.Plate, v05.Plate)):
            return self._init_plate(meta)
        if isinstance(meta, (v04.Well, v05.Well)):
            return self._init_well(meta)

        raise ValueError(f"Unknown NGFF structure: {self._group.store_path}")

    def _init_single(self, meta: Any) -> tuple[tuple[Hashable, ...], dict]:
        """Initialize single-position image."""
        ms = meta.multiscales[0]
        self._dataset_path = ms.datasets[0].path
        arr = self._group[self._dataset_path]
        shape = arr.metadata.shape
        dims = self._dims_from_axes(ms.axes, len(shape))
        return dims, {d: range(s) for d, s in zip(dims, shape, strict=False)}

    def _init_bioformats2raw(self) -> tuple[tuple[Hashable, ...], dict]:
        """Initialize bioformats2raw layout."""
        if "OME" in self._group:
            series = self._group["OME"].metadata.attributes.get("series")
            if series:
                self._positions = list(series)
        if not self._positions:
            # Find numbered subgroups (0, 1, 2, ...)
            i = 0
            while str(i) in self._group:
                child = self._group[str(i)]
                if hasattr(child, "ome_metadata"):
                    child_meta = child.ome_metadata()
                    if hasattr(child_meta, "multiscales") and child_meta.multiscales:
                        self._positions.append(str(i))
                i += 1
        if not self._positions:
            raise ValueError("No positions found in bioformats2raw layout")
        return self._init_multiposition()

    def _init_well(self, meta: Any) -> tuple[tuple[Hashable, ...], dict]:
        """Initialize well."""
        self._positions = [fov.path for fov in meta.well.images]
        if not self._positions:
            raise ValueError("No FOV positions found in well")
        return self._init_multiposition()

    def _init_plate(self, meta: Any) -> tuple[tuple[Hashable, ...], dict]:
        """Initialize HCS plate."""
        for well_ref in meta.plate.wells:
            if well_ref.path not in self._group:
                continue
            well_meta = self._group[well_ref.path].ome_metadata()
            if hasattr(well_meta, "well"):
                self._positions.extend(
                    f"{well_ref.path}/{fov.path}" for fov in well_meta.well.images
                )
        if not self._positions:
            raise ValueError("No FOV positions found in plate")
        return self._init_multiposition()

    def _init_multiposition(self) -> tuple[tuple[Hashable, ...], dict]:
        """Finalize multi-position setup using first position's metadata."""
        pos_group = self._group[self._positions[0]]
        ms = pos_group.ome_metadata().multiscales[0]
        self._dataset_path = ms.datasets[0].path
        arr = pos_group[self._dataset_path]
        shape = arr.metadata.shape
        inner_dims = self._dims_from_axes(ms.axes, len(shape))
        dims = ("p", *inner_dims)
        coords: dict[Hashable, Sequence] = {"p": range(len(self._positions))}
        coords.update({d: range(s) for d, s in zip(inner_dims, shape, strict=False)})
        return dims, coords

    @staticmethod
    def _dims_from_axes(axes: Any, ndim: int) -> tuple[Hashable, ...]:
        """Extract dimension names from axes or use integer indices."""
        if axes:
            return tuple(ax.name for ax in axes)
        return tuple(range(ndim))

    # ----------------------- Data Access -----------------------

    def _isel_single(self, indexers: Mapping[int, int | slice]) -> np.ndarray:
        arr = self._group[self._dataset_path]
        idx = tuple(indexers.get(i, slice(None)) for i in range(len(self._dims)))
        return self._read_array(arr, idx)

    def _isel_multiposition(self, indexers: Mapping[int, int | slice]) -> np.ndarray:
        pos_idx = indexers.get(0)
        keep_dim = isinstance(pos_idx, slice)
        if pos_idx is None:
            pos_idx = 0
        elif isinstance(pos_idx, slice):
            pos_idx = pos_idx.start or 0
        if not 0 <= pos_idx < len(self._positions):
            raise IndexError(f"Position index {pos_idx} out of range")

        pos_group = self._group[self._positions[pos_idx]]
        arr = pos_group[self._dataset_path]
        inner_idx = tuple(
            indexers.get(i, slice(None)) for i in range(1, len(self._dims))
        )
        data = self._read_array(arr, inner_idx)
        return data[np.newaxis, ...] if keep_dim else data

    @staticmethod
    def _read_array(arr: Any, idx: tuple) -> np.ndarray:
        try:
            return np.asarray(arr.to_tensorstore()[idx].read().result())
        except ImportError:
            return np.asarray(arr.to_zarr_python()[idx])
