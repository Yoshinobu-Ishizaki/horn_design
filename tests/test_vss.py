"""vss.variable_pipe_law: table / centerline length mismatch (synthetic centerline)."""

import math

import numpy as np
import pytest
from build123d import Line, ThreePointArc, Vector, Wire

from bope_claude_cad.vss import (
    check_variable_pipe,
    table_from_function,
    variable_pipe_law,
    variable_pipe_wall,
)


@pytest.fixture(scope="module")
def centerline():
    # straight 100 mm, then a quarter arc of R=200 (length 314.159) in the XY plane
    a = Line((0, 0), (0, 100))
    r = 200.0
    c = Vector(r, 100)
    mid = c + Vector(-r * math.cos(math.radians(45)), r * math.sin(math.radians(45)))
    end = c + Vector(0, r)
    b = ThreePointArc(Vector(0, 100), mid, end)
    return Wire([a, b])


@pytest.fixture(scope="module")
def centerline_3d():
    # straight, then two quarter arcs in different planes (tangent continuous, non-planar)
    r = 100.0
    k = r * math.cos(math.radians(45))
    c1, c2 = Vector(0, 100, 100), Vector(100, 100, 200)
    return Wire(
        [
            Line((0, 0, 0), (0, 0, 100)),
            ThreePointArc((0, 0, 100), c1 + Vector(0, -k, k), (0, 100, 200)),
            ThreePointArc((0, 100, 200), c2 + Vector(-k, k, 0), (100, 200, 200)),
        ]
    )


def test_3d_centerline_volume_and_diameter(centerline_3d):
    cl = centerline_3d
    ls = np.linspace(0, cl.length, 25)
    ds = np.linspace(40, 24, 25) + 3 * np.sin(ls / cl.length * 3 * math.pi)
    solid, prof = variable_pipe_law(cl, ls, ds, solid=True)
    res = check_variable_pipe(solid, cl, prof, n=40)
    assert res["is_valid"]
    assert res["volume_ratio"] == pytest.approx(1.0, abs=1e-3)
    assert res["dia_err_max"] < 0.01


def test_3d_centerline_wall_thickness(centerline_3d):
    cl = centerline_3d
    ls = np.linspace(0, cl.length, 25)
    ds = np.linspace(40, 24, 25)
    wall, _ = variable_pipe_wall(cl, ls, ds, 0.4)
    assert wall.is_valid and len(wall.solids()) == 1
    inner, _ = variable_pipe_law(cl, ls, ds)
    # wall volume ~ area x thickness (thin wall; B-spline volume is the reliable one)
    assert wall.volume == pytest.approx(inner.area * 0.4, rel=0.08)


def table(l0, l1, step=10.0):
    ls = np.arange(l0, l1 + 1e-9, step)
    return ls, 40.0 - 0.05 * ls  # D = 40 - 0.05 L (gentle taper)


def rim_diameters_and_positions(shell, cl):
    faces = shell.faces()
    out = []
    for e in shell.edges():
        if e.is_closed and sum(any(e.is_same(x) for x in f.edges()) for f in faces) == 1:
            s = min(np.linspace(0, cl.length, 2001), key=lambda x: (cl.position_at(x / cl.length) - e.center()).length)
            out.append((s, e.length / math.pi))
    return sorted(out)


def test_table_longer_than_centerline_ends_at_centerline_end(centerline):
    ls, ds = table(0, centerline.length + 100)
    shell, _prof = variable_pipe_law(centerline, ls, ds)
    (s0, d0), (s1, d1) = rim_diameters_and_positions(shell, centerline)
    assert s0 == pytest.approx(0, abs=0.5) and s1 == pytest.approx(centerline.length, abs=0.5)
    assert d0 == pytest.approx(40.0, abs=1e-3)
    assert d1 == pytest.approx(40.0 - 0.05 * centerline.length, abs=1e-3)  # interpolated at the centerline end


def test_table_shorter_than_centerline_stops_at_table_end(centerline):
    ls, ds = table(0, 250)
    shell, _prof = variable_pipe_law(centerline, ls, ds)
    (_s0, _d0), (s1, d1) = rim_diameters_and_positions(shell, centerline)
    assert s1 == pytest.approx(250, abs=0.5)  # not stretched over the whole centerline
    assert d1 == pytest.approx(40.0 - 0.05 * 250, abs=1e-3)


def test_table_starting_midway(centerline):
    ls, ds = table(50, 300)
    shell, _prof = variable_pipe_law(centerline, ls, ds)
    (s0, d0), (s1, _d1) = rim_diameters_and_positions(shell, centerline)
    assert s0 == pytest.approx(50, abs=0.5) and s1 == pytest.approx(300, abs=0.5)
    assert d0 == pytest.approx(40.0 - 0.05 * 50, abs=1e-3)


def test_function_law_string_and_callable_agree(centerline):
    ls1, ds1 = table_from_function("D = 40 - 0.05*x", 0, centerline.length)
    ls2, ds2 = table_from_function(lambda x: 40 - 0.05 * x, 0, centerline.length)
    assert np.allclose(ls1, ls2) and np.allclose(ds1, ds2)
    assert ds1[0] == pytest.approx(40.0)
    shell, _ = variable_pipe_law(centerline, ls1, ds1)
    (_s0, d0), (_s1, d1) = rim_diameters_and_positions(shell, centerline)
    assert d0 == pytest.approx(40.0, abs=1e-3)
    assert d1 == pytest.approx(40.0 - 0.05 * centerline.length, abs=1e-3)


def test_function_law_nonlinear_constant_and_errors():
    _, ds = table_from_function("20 + 30*exp(-x/200)^2", 0, 400)
    assert ds[0] == pytest.approx(50.0) and ds[-1] == pytest.approx(20 + 30 * math.exp(-4))
    _, dc = table_from_function("25", 0, 100)  # constant
    assert np.allclose(dc, 25.0)
    _, dsc = table_from_function(lambda x: 10 + float(x) * 0.1, 0, 100)  # scalar-only function
    assert dsc[-1] == pytest.approx(20.0)
    with pytest.raises(ValueError):
        table_from_function("10 - x", 0, 100)  # D <= 0
