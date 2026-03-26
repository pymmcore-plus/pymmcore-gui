from __future__ import annotations

import math
import random
import weakref
from typing import TYPE_CHECKING

from pymmcore_plus.experimental.simulate import Line, Point, Rectangle, Sample
from wrapt import partial

if TYPE_CHECKING:
    import contextlib

    from pymmcore_plus import CMMCorePlus


def create_sample(
    extent: float = 2000,
    point_spacing: float = 200,
    n_spokes: int = 24,
    ring_radii: tuple[float, ...] = (300, 600, 900, 1200, 1500),
    n_scattered_lines: int = 120,
    grid_line_spacing: float = 250,
    cluster_positions: tuple[tuple[float, float], ...] = (
        (800, 800),
        (-800, 800),
        (-800, -800),
        (800, -800),
    ),
    cluster_size: int = 15,
    seed: int | None = 42,
) -> Sample:
    """Create a simulated sample with various geometric objects."""
    rng = random.Random(seed)
    objects: list[Point | Line | Rectangle] = []

    # Grid of points across the field
    lo, hi = int(-extent), int(extent) + 1
    spacing = int(point_spacing)
    for x in range(lo, hi, spacing):
        for y in range(lo, hi, spacing):
            r = rng.uniform(2, 8)
            intensity = rng.randint(80, 255)
            objects.append(Point(x, y, intensity=intensity, radius=r))

    # Radial spokes from the origin
    for i in range(n_spokes):
        angle = 2 * math.pi * i / n_spokes
        length = rng.uniform(extent * 0.25, extent * 0.75)
        x2 = length * math.cos(angle)
        y2 = length * math.sin(angle)
        objects.append(Line((0, 0), (x2, y2), intensity=rng.randint(460, 1040)))

    # Concentric rings of rectangles
    for ring_r in ring_radii:
        n = max(6, int(ring_r) // 100)
        for i in range(n):
            angle = 2 * math.pi * i / n
            cx = ring_r * math.cos(angle)
            cy = ring_r * math.sin(angle)
            w = rng.uniform(15, 50)
            h = rng.uniform(15, 50)
            objects.append(
                Rectangle(
                    (cx - w / 2, cy - h / 2),
                    width=w,
                    height=h,
                    intensity=rng.randint(100, 220),
                    fill=rng.choice([True, False]),
                )
            )

    # Scattered lines across the field
    length = extent * 0.25
    for _ in range(n_scattered_lines):
        x1 = rng.uniform(-extent, extent)
        y1 = rng.uniform(-extent, extent)
        dx = rng.uniform(-length, length)
        dy = rng.uniform(-length, length)
        objects.append(
            Line((x1, y1), (x1 + dx, y1 + dy), intensity=rng.randint(390, 1080))
        )

    # Diagonal grid lines
    glo, ghi = int(-extent), int(extent) + 1
    gspacing = int(grid_line_spacing)
    for offset in range(glo, ghi, gspacing):
        objects.append(Line((offset, -extent), (offset + extent, extent), intensity=40))
        objects.append(Line((-extent, offset), (extent, offset + extent), intensity=40))

    # Bright landmark clusters
    for qx, qy in cluster_positions:
        for _ in range(cluster_size):
            px = qx + rng.gauss(0, 60)
            py = qy + rng.gauss(0, 60)
            objects.append(Point(px, py, intensity=255, radius=rng.uniform(3, 10)))

    return Sample(objects)


_SIM_CTX: contextlib.AbstractContextManager | None = None


def install_sim_sample(core: CMMCorePlus) -> None:
    """Install the simulated sample patch on the given core."""
    core.events.systemConfigurationLoaded.connect(
        partial(_update_sim_sample, core=weakref.ref(core))
    )


def uninstall_sim_sample(core: CMMCorePlus) -> None:
    """Uninstall the simulated sample patch from the given core."""
    core.events.systemConfigurationLoaded.disconnect(_update_sim_sample)


def _update_sim_sample(core: CMMCorePlus | weakref.ReferenceType[CMMCorePlus]) -> None:
    """Patch core with a sim sample when using the demo camera."""
    # tear down any existing patch
    _core = core() if isinstance(core, weakref.ReferenceType) else core
    if _core is None:
        return

    global _SIM_CTX
    if _SIM_CTX is not None:
        _SIM_CTX.__exit__(None, None, None)
        _SIM_CTX = None

    if (cam := _core.getCameraDevice()) and _core.getDeviceLibrary(cam) == "DemoCamera":
        _SIM_CTX = ctx = create_sample().patch(_core)
        ctx.__enter__()
