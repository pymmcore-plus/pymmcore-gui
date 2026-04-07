from __future__ import annotations

from dataclasses import dataclass
from math import hypot, pi
from pathlib import Path
from typing import TYPE_CHECKING

import ezdxf
import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class ChipCurve:
    points: np.ndarray
    closed: bool = False


@dataclass(slots=True)
class ChipOverlayData:
    curves: list[ChipCurve]
    reference_points: list[tuple[float, float]]
    source: Path | None


def load_chip_overlay_data(path: str | Path) -> ChipOverlayData:
    """Load a DXF file and extract a 2D XY projection for overlay display."""
    src = Path(path)
    doc = ezdxf.readfile(src)
    curves: list[ChipCurve] = []
    ref_points: list[tuple[float, float]] = []

    for entity in doc.modelspace():
        if entity.dxftype() == "3DSOLID":
            sat_lines = getattr(entity, "sat", None) or getattr(entity, "acis_data", ())
            c, pts = _curves_from_acis_lines(sat_lines)
            curves.extend(c)
            ref_points.extend(pts)

    return ChipOverlayData(
        curves=curves, reference_points=_unique_points(ref_points), source=src
    )


def _curves_from_acis_lines(
    lines: Iterable[str],
) -> tuple[list[ChipCurve], list[tuple[float, float]]]:
    curves: list[ChipCurve] = []
    points: list[tuple[float, float]] = []

    for line in lines:
        text = line.strip()
        if text.startswith("straight-curve"):
            segment = _parse_straight_curve(text)
            if segment is not None:
                curves.append(
                    ChipCurve(points=np.asarray(segment, dtype=float), closed=False)
                )
                points.extend((tuple(segment[0]), tuple(segment[-1])))
        elif text.startswith("ellipse-curve"):
            ellipse = _parse_ellipse_curve(text)
            if ellipse is not None:
                curves.append(ChipCurve(points=ellipse, closed=True))
                points.extend(_sample_reference_points(ellipse))
        elif text.startswith("point"):
            pt = _parse_point(text)
            if pt is not None:
                points.append(pt)

    return curves, points


def _parse_straight_curve(line: str) -> np.ndarray | None:
    values = _extract_numeric_tokens(line)
    if len(values) < 8:
        return None

    origin = np.array(values[0:3], dtype=float)
    direction = np.array(values[3:6], dtype=float)
    scalars = values[6:]

    if len(scalars) >= 2:
        start = origin + direction * scalars[0]
        end = origin + direction * scalars[1]
    else:
        start = origin
        end = origin + direction

    return np.array([[start[0], start[1]], [end[0], end[1]]], dtype=float)


def _parse_ellipse_curve(line: str, samples: int = 64) -> np.ndarray | None:
    values = _extract_numeric_tokens(line)
    if len(values) < 9:
        return None

    center = np.array(values[0:3], dtype=float)
    major = np.array(values[6:9], dtype=float)
    radius = hypot(float(major[0]), float(major[1]))
    if radius <= 0:
        return None

    angles = np.linspace(0, 2 * pi, samples, endpoint=False)
    pts = np.column_stack(
        (
            center[0] + radius * np.cos(angles),
            center[1] + radius * np.sin(angles),
        )
    )
    return pts.astype(float)


def _parse_point(line: str) -> tuple[float, float] | None:
    values = _extract_numeric_tokens(line)
    if len(values) < 2:
        return None
    return float(values[0]), float(values[1])


def _extract_numeric_tokens(text: str) -> list[float]:
    out: list[float] = []
    for token in text.replace("#", " ").split():
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out


def _sample_reference_points(points: np.ndarray) -> list[tuple[float, float]]:
    if len(points) < 4:
        return [tuple(p) for p in points]
    idxs = (0, len(points) // 4, len(points) // 2, (3 * len(points)) // 4)
    return [tuple(points[i]) for i in idxs]


def _unique_points(
    points: Iterable[tuple[float, float]], precision: int = 3
) -> list[tuple[float, float]]:
    seen: set[tuple[float, float]] = set()
    out: list[tuple[float, float]] = []
    for x, y in points:
        key = (round(float(x), precision), round(float(y), precision))
        if key in seen:
            continue
        seen.add(key)
        out.append((float(x), float(y)))
    return out
