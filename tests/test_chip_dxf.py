from __future__ import annotations

import numpy as np

from pymmcore_gui.widgets._chip_dxf import (
    _curves_from_acis_lines,
    _parse_ellipse_curve,
    _parse_straight_curve,
)


def test_parse_straight_curve_projects_to_xy() -> None:
    line = "straight-curve $-1 -1 $-1 10 20 0 1 0 0 F 0 F 30 #"
    segment = _parse_straight_curve(line)

    assert segment is not None
    np.testing.assert_allclose(segment, np.array([[10.0, 20.0], [40.0, 20.0]]))


def test_parse_ellipse_curve_creates_xy_circle_samples() -> None:
    line = "ellipse-curve $-1 -1 $-1 100 200 0 0 0 1 50 0 0 1 I I #"
    curve = _parse_ellipse_curve(line, samples=8)

    assert curve is not None
    assert curve.shape == (8, 2)
    assert np.isclose(curve[:, 0].mean(), 100.0)
    assert np.isclose(curve[:, 1].mean(), 200.0)


def test_curves_from_acis_lines_extract_geometry_and_points() -> None:
    curves, points = _curves_from_acis_lines(
        [
            "straight-curve $-1 -1 $-1 10 20 0 1 0 0 F 0 F 30 #",
            "ellipse-curve $-1 -1 $-1 100 200 0 0 0 1 50 0 0 1 I I #",
            "point $-1 -1 $-1 5 6 0 #",
        ]
    )

    assert len(curves) == 2
    assert (10.0, 20.0) in points
    assert (40.0, 20.0) in points
    assert (5.0, 6.0) in points
