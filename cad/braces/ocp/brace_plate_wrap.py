"""支柱座のブランクを中管(φ12.8)に巻き付ける。

方法(円筒専用で、近似なし):
  1. ブランクの輪郭を、管の外面(R = R管 = 6.4)の (u, v) = (角度, 軸方向) に厳密にマップし、
     円柱面そのものを輪郭で切り取る。長手 x は管の外面の弧長(u = u0 + x/R管)、幅 y は軸方向(v = z0 + y)。
  2. 切り取った面を、外向きに板厚 t だけオフセットしてソリッドにする(内面が管の外面 R管、外面が R管 + t)。
  ※ 長さは管の外面で元の長さと一致する。外面(R管 + t)側の弧長は (R管 + t)/R管 倍に伸びる(許容)。
長手(ブランクの X)は管の周方向、幅(Y、6 mm)は管軸方向。基準点は管の中央(z=L/2)、角度 90°。
"""

import math
import sys
from pathlib import Path

from build123d import Face, GeomType, Pos, Solid, Vector
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.Geom import Geom_CylindricalSurface
from OCP.collections import Array1_gp_Pnt2d
from OCP.Geom2dAPI import Geom2dAPI_PointsToBSpline
from OCP.GeomAbs import GeomAbs_Shape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Pnt2d
from OCP.ShapeFix import ShapeFix_Face

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tubes" / "ocp"))
from inner_tube import LENGTHS, OD, inner_tube  # noqa: E402

from brace_plate_blank import blank_face  # noqa: E402

R_TUBE = OD / 2  # 6.4
N_SAMPLE = 200  # 輪郭の辺ごとの標本数(2D 曲線の補間用。円弧なので 1e-6 mm 以下で合う)


def cylinder_trimmed_face(outline: Face, r: float, u0: float, v0: float) -> Face:
    """半径 r の円柱面を、outline(XY 平面、原点中心)で切り取った面。
    (x, y) → (u, v) = (u0 + x / r, v0 + y)。弧長 x が r の円柱上で保たれる。"""
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1), gp_Dir(1, 0, 0)), r)
    mk = BRepBuilderAPI_MakeWire()
    for e in outline.faces()[0].outer_wire().edges():
        pts = [e.position_at(i / N_SAMPLE) for i in range(N_SAMPLE + 1)]
        arr = Array1_gp_Pnt2d(1, len(pts))
        for i, p in enumerate(pts, start=1):
            arr.SetValue(i, gp_Pnt2d(u0 + p.X / r, v0 + p.Y))
        curve = Geom2dAPI_PointsToBSpline(arr, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-8).Curve()
        edge = BRepBuilderAPI_MakeEdge(curve, surf).Edge()
        BRepLib.BuildCurves3d_s(edge, 1e-8)
        mk.Add(edge)
    face = BRepBuilderAPI_MakeFace(surf, mk.Wire(), True).Face()
    fx = ShapeFix_Face(face)
    fx.Perform()
    return Face(fx.Face())


def seat_on_cylinder(r_tube: float, u0: float, v0: float, thickness: float):
    """半径 r_tube の円筒の外面(軸は Z、原点まわり)に、角度 u0・軸方向 v0 を中心に座を巻き付ける。
    戻り値は (座のソリッド, 管の外面で切り取った面)。内面が r_tube、外面が r_tube + thickness。"""
    surf_face = cylinder_trimmed_face(blank_face(), r_tube, u0, v0)
    # 面の法線の向きを確かめ、外向き(半径が増える方)へ厚み付けする
    c = surf_face.center()
    s = 1.0 if surf_face.normal_at(c).dot(Vector(c.X, c.Y, 0)) > 0 else -1.0
    return Solid.thicken(surf_face, thickness * s), surf_face


def seat_on_tube(length: float, thickness: float):
    """中管(長さ length)の中央、角度 90° に、厚み thickness の座を巻き付ける。戻り値は (管, 座, 切り取った面)。"""
    seat, surf_face = seat_on_cylinder(R_TUBE, math.pi / 2, length / 2, thickness)
    return inner_tube(length), seat, surf_face


def solid_volume(shape, eps=1e-9):
    """高精度の体積。build123d の .volume は B スプラインの側面で 2% ほど小さく出る。"""
    pr = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, pr, eps)
    return pr.Mass()


def radial_range(face, n=25):
    out = []
    for i in range(n + 1):
        for j in range(n + 1):
            p = face.position_at(i / n, j / n)
            if face.distance_to(p) < 1e-6:
                out.append(math.hypot(p.X, p.Y))
    return min(out), max(out)


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    thick = {"sl-b1": 0.7, "sl-b2": 0.4}
    parts, labels = [], []
    for i, n in enumerate(LENGTHS):
        off = Pos(i * 25, 0, 0)
        if n in thick:
            t = thick[n]
            tube, seat, surf_face = seat_on_tube(LENGTHS[n], t)
            parts += [off * tube, off * seat]
            labels += [f"inner_tube_{n}", f"brace_plate_t{t}_on_{n}"]
            cyl = sorted(
                (f for f in seat.faces() if f.geom_type == GeomType.CYLINDER), key=lambda f: f.radius
            )
            rin, rout = cyl[0].radius, cyl[-1].radius
            bb = seat.bounding_box()
            a_flat = blank_face().faces()[0].area
            v_exp = a_flat * t * (1 + t / (2 * R_TUBE))  # 円柱殻の体積(厚み方向に r が増える分)
            ang = math.degrees(blank_face().bounding_box().size.X / R_TUBE)
            print(f"{n} t={t}: valid={seat.is_valid} solids={len(seat.solids())} faces={len(seat.faces())}")
            print(f"  内面 R={rin:.6f} (管 {R_TUBE}) 外面 R={rout:.6f} (目標 {R_TUBE + t:.6f}) 厚み={rout - rin:.6f}")
            print(f"  管の外面で切り取った面積={surf_face.area:.4f}(平らなブランク {a_flat:.4f})")
            print(f"  体積(高精度)={solid_volume(seat):.4f} 期待={v_exp:.4f}  (build123d の .volume は {seat.volume:.4f} と小さく出る)")
            print(f"  z 範囲(中央から)=[{bb.min.Z - LENGTHS[n]/2:.4f}, {bb.max.Z - LENGTHS[n]/2:.4f}] 巻き付け角={ang:.1f}°")
            print(f"  外面側の弧長 = 内面の {(R_TUBE + t) / R_TUBE:.4f} 倍({blank_face().bounding_box().size.X * (R_TUBE + t) / R_TUBE:.3f} mm、許容)")
        else:
            parts.append(off * inner_tube(LENGTHS[n]))
            labels.append(f"inner_tube_{n}")
    show(*parts, names=labels, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
