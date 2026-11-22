"""surface_map のテスト(円筒・球・自由曲面)。"""

import math
import warnings

import ezdxf
import pytest
from build123d import Cylinder, Face, GeomType, Rectangle, Sphere, Vector

from bope_claude_cad.surface_map import (
    SeatParams,
    make_seat,
    map_outline,
    outline_from_dxf,
    outline_from_face,
    surface_frame,
)


def _cyl_side(r=20.0):
    return Cylinder(r, 100).faces().filter_by(GeomType.CYLINDER)[0]


def _freeform():
    pts = [
        [
            Vector(i * 15 - 45, j * 15 - 45, 12 * math.sin((i * 15 - 45) / 30) + 8 * math.cos((j * 15 - 45) / 25))
            for j in range(7)
        ]
        for i in range(7)
    ]
    return Face.make_surface_from_array_of_points(pts)


def test_surface_frame_normal_on_cylinder():
    pl = surface_frame(_cyl_side(), (25, 0, 0), (0, 0, 1))
    assert pl.z_dir.X == pytest.approx(1, abs=1e-6)
    assert pl.x_dir.Z == pytest.approx(1, abs=1e-6)
    assert pl.origin.X == pytest.approx(20, abs=1e-6)


def test_wrap_cylinder_axial_edges_keep_length():
    # 軸方向(直線方向)の長さは厳密に保たれる
    p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), thickness=3)
    faces = map_outline(_cyl_side(), Rectangle(30, 12), p)
    assert len(faces) == 1 and faces[0].is_valid
    bb = faces[0].bounding_box()
    # 閉じる辺の延長ぶんだけ、元の 30 よりわずかに伸びる(最大 2%)
    assert bb.size.Z == pytest.approx(30, rel=0.02)


def test_march_cylinder_is_developable():
    # 円筒は展開できるので、追跡で貼ると閉じ目の隙間も長さのずれもほぼ 0、曲面から浮かない
    p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), thickness=2, wrap_method="march")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # 警告が出たら失敗
        solid, rep = make_seat(_cyl_side(), Rectangle(30, 12), p)
    assert solid.is_valid
    assert p.extra["closing_gap"] < 0.01
    assert rep["edge_worst"] < 0.005
    assert rep["area_ratio"] == pytest.approx(1, abs=0.005)
    assert rep["surface_dev"] < 0.01


def test_march_cone_like_surface_reports_gap():
    # 負の曲率をもつ面(ベルのフレアなど)では、長さを保つと閉じ目が閉じない。隙間を周に配り、警告する
    pts = [
        [Vector(i * 10 - 30, j * 10 - 30, -0.02 * ((i * 10 - 30) ** 2 + (j * 10 - 30) ** 2)) for j in range(7)]
        for i in range(7)
    ]
    saddle = Face.make_surface_from_array_of_points(
        [[Vector(x, y, 0.01 * (x * x - y * y)) for x, y, _ in [(p.X, p.Y, 0) for p in row]] for row in pts]
    )
    p = SeatParams(point=(0, 0, 0), x_dir=(1, 0, 0), thickness=1, wrap_method="march")
    with pytest.warns(UserWarning):
        faces = map_outline(saddle, Rectangle(30, 30), p)
    assert faces[0].is_valid
    assert p.extra["closing_gap"] > 0.05


def test_section_keeps_length_and_widths_on_cylinder():
    # 円筒(管軸方向 = 長手): 幅は周方向の弧長。長手・幅とも、元の長さと一致する
    p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), thickness=2)  # 既定 = section
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        solid, rep = make_seat(_cyl_side(), Rectangle(30, 12), p)
    assert solid.is_valid
    assert rep["width_worst"] < 0.01
    assert rep["surface_dev"] < 0.01
    bb = map_outline(_cyl_side(), Rectangle(30, 12), p)[0].bounding_box()
    assert bb.size.Z == pytest.approx(30, abs=0.02)  # 長手(管軸方向)は厳密


def test_section_widths_match_on_freeform_and_sphere():
    # 二重曲率の面でも、断面の幅は元の幅と一致する(周の長さは保たない)
    for surf, pt, xd in (
        (_freeform(), (0, 0, 8), (1, 0, 0)),
        (Sphere(40).faces()[0], (40, 0, 0), (0, 0, 1)),
    ):
        p = SeatParams(point=pt, x_dir=xd, thickness=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            solid, rep = make_seat(surf, Rectangle(24, 10), p)
        solids = solid if isinstance(solid, list) else [solid]
        assert all(s.is_valid for s in solids)
        assert rep["width_worst"] < 0.05, rep["widths"]


def test_normal_curvature_cylinder_and_sphere():
    from bope_claude_cad.surface_map import normal_curvature

    cyl = _cyl_side()
    assert normal_curvature(cyl, (20, 0, 0), (0, 0, 1)) == pytest.approx(0, abs=1e-9)  # 軸方向
    assert normal_curvature(cyl, (20, 0, 0), (0, 1, 0)) == pytest.approx(1 / 20, rel=1e-6)  # 周方向
    assert normal_curvature(cyl, (20, 0, 0), (0, 1, 1)) == pytest.approx(0.5 / 20, rel=1e-6)  # 45°
    sph = Sphere(40).faces()[0]
    assert normal_curvature(sph, (40, 0, 0), (0, 0, 1)) == pytest.approx(1 / 40, rel=1e-6)


def test_long_axis_auto_picks_longer_side_then_lower_curvature():
    cyl = _cyl_side()
    cases = [
        # (blank 幅 x 高さ, x_dir, 期待する長手)
        ((12, 30), (0, 0, 1), "y"),  # 縦(y)が長い → y
        ((30, 12), (0, 0, 1), "x"),  # 横(x)が長い → x
        ((20, 20), (0, 0, 1), "x"),  # 同程度: x = 軸方向(曲率 0)が小さい → x
        ((20, 20), (0, 1, 0), "y"),  # 同程度: x = 周方向、y = 軸方向(曲率 0)が小さい → y
    ]
    for (w, h), xd, expect in cases:
        p = SeatParams(point=(20, 0, 0), x_dir=xd, thickness=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            solid, rep = make_seat(cyl, Rectangle(w, h), p)
        assert p.extra["long_axis"] == expect, (w, h, xd)
        assert solid.is_valid
        assert rep["width_worst"] < 0.01  # 長手を入れ替えても、長手と幅は保たれる
    # 手動指定
    p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), thickness=1, long_axis="curvature")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        make_seat(cyl, Rectangle(12, 30), p)
    assert p.extra["long_axis"] == "x"  # 曲率が小さいのは軸方向(x)


def test_wrap_thickness_outward_and_inward():
    s = _cyl_side()
    for outward in (True, False):
        p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), thickness=3, outward=outward)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            solid, _ = make_seat(s, Rectangle(30, 12), p)
        assert solid.is_valid
        r = max(math.hypot(v.X, v.Y) for v in solid.vertices())
        r_min = min(math.hypot(v.X, v.Y) for v in solid.vertices())
        if outward:
            assert r == pytest.approx(23, abs=0.05)
        else:
            assert r_min == pytest.approx(17, abs=0.05)


def test_normal_projection_cylinder_area():
    p = SeatParams(point=(20, 0, 0), x_dir=(0, 0, 1), mode="normal", thickness=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        solid, rep = make_seat(_cyl_side(), Rectangle(30, 12), p)
    solids = solid if isinstance(solid, list) else [solid]
    assert all(s.is_valid for s in solids)
    # 12 mm 幅の弧に投影: 弧長 > 12。面積比は 1 を少し超える
    assert 1.0 < rep["area_ratio"] < 1.05


def test_normal_projection_sphere_keeps_front_only():
    s = Sphere(40).faces()[0]
    p = SeatParams(point=(40, 0, 0), x_dir=(0, 0, 1), mode="normal")
    faces = map_outline(s, Rectangle(20, 20), p)
    n = Vector(1, 0, 0)
    assert all(f.normal_at(f.center()).dot(n) > 0 for f in faces)
    assert sum(f.area for f in faces) == pytest.approx(400, rel=0.05)


def test_wrap_freeform_retries_tolerance():
    s = _freeform()
    p = SeatParams(point=(0, 0, 8), x_dir=(1, 0, 0), tolerance=0.02, wrap_method="build123d")
    faces = map_outline(s, Rectangle(30, 12), p)
    assert len(faces) == 1 and faces[0].is_valid


def test_large_outline_on_sphere_warns():
    s = Sphere(40).faces()[0]
    p = SeatParams(point=(40, 0, 0), x_dir=(0, 0, 1), warn_ratio=0.02, wrap_method="march")
    with pytest.warns(UserWarning):
        make_seat(s, Rectangle(50, 30), p)


def test_outline_from_dxf_with_hole(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(100, 50), (140, 50), (140, 70), (100, 70)], close=True)
    msp.add_circle((120, 60), 4)
    f = tmp_path / "o.dxf"
    doc.saveas(f)
    face = outline_from_dxf(f)
    assert face.area == pytest.approx(40 * 20 - math.pi * 16, rel=1e-3)
    assert face.center().X == pytest.approx(0, abs=1e-3)
    assert len(face.inner_wires()) == 1


def test_outline_from_face_moves_to_xy():
    box_face = Rectangle(10, 6).moved(__import__("build123d").Location((5, 5, 7)))
    f = outline_from_face(Face(box_face.wire()))
    assert f.area == pytest.approx(60)
    assert f.center().Z == pytest.approx(0, abs=1e-6)
