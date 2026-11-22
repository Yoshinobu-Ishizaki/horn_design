# /// script
# requires-python = ">=3.10"
# dependencies = ["build123d>=0.13", "numpy"]
# ///
"""STEP の面・エッジを一覧にする。製品の形を把握し、名称を付ける面・エッジを選ぶ最初の調査に使う。

使い方:
  uv run probe_step.py <step>                      面の一覧(番号、種類、面積、中心、法線、円筒・円錐のパラメータ)
  uv run probe_step.py <step> --edges              エッジの一覧(番号、種類、長さ、両端の座標)も出す
  uv run probe_step.py <step> --min-area 20        小さい面を省く
  uv run probe_step.py <step> --plane-y 0 --edge 63   エッジ 63 と Y=0 の平面の交点

番号は build123d の import_step で読んだ shape.faces() / shape.edges() の順(会話で指すときの記号 Fxx / Exx)。
単位は mm。座標は STEP のまま(回転・平行移動の前)。
"""

from __future__ import annotations

import argparse
import math
import sys

from build123d import Plane, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface


def r(v, n=3):
    return round(float(v), n)


def vec(v):
    return [r(v.X), r(v.Y), r(v.Z)]


def face_line(i, f):
    c = f.center()
    s = f"F{i:02d} {f.geom_type.name:<10} area {f.area:9.2f} centre {vec(c)}"
    try:
        s += f" normal {[r(x, 3) for x in f.normal_at(c)]}"
    except Exception:  # noqa: BLE001 - 法線が取れない面は省く
        pass
    ad = BRepAdaptor_Surface(f.wrapped)
    name = f.geom_type.name
    if name == "CYLINDER":
        cy = ad.Cylinder()
        a, p = cy.Axis().Direction(), cy.Location()
        s += f"\n      cylinder R={r(cy.Radius())} axis=({r(a.X(), 4)},{r(a.Y(), 4)},{r(a.Z(), 4)}) point=({r(p.X())},{r(p.Y())},{r(p.Z())})"
    elif name == "CONE":
        co = ad.Cone()
        a, ap = co.Axis().Direction(), co.Apex()
        s += (
            f"\n      cone semi-angle={r(math.degrees(co.SemiAngle()))}deg axis=({r(a.X(), 4)},{r(a.Y(), 4)},{r(a.Z(), 4)})"
            f" apex=({r(ap.X())},{r(ap.Y())},{r(ap.Z())}) ref-radius={r(co.RefRadius())}"
        )
    elif name == "SPHERE":
        sp = ad.Sphere()
        s += f"\n      sphere R={r(sp.Radius())}"
    elif name == "TORUS":
        t = ad.Torus()
        s += f"\n      torus R={r(t.MajorRadius())} r={r(t.MinorRadius())}"
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step")
    ap.add_argument("--edges", action="store_true")
    ap.add_argument("--min-area", type=float, default=0.0)
    ap.add_argument("--plane-y", type=float, default=None, help="--edge と組み合わせて Y=値 の平面との交点を出す")
    ap.add_argument("--edge", type=int, default=None)
    a = ap.parse_args()

    shape = import_step(a.step)
    faces, edges = shape.faces(), shape.edges()
    bb = shape.bounding_box()
    print(f"solids {len(shape.solids())}  faces {len(faces)}  edges {len(edges)}  volume {r(shape.volume, 1)}")
    print(f"bbox min {vec(bb.min)} max {vec(bb.max)} size {vec(bb.size)}")

    if a.edge is not None:
        e = edges[a.edge]
        print(f"E{a.edge:02d} {e.geom_type.name} length {r(e.length)} start {vec(e @ 0)} end {vec(e @ 1)}")
        if a.plane_y is not None:
            inter = e.intersect(Plane.XZ.offset(-a.plane_y))  # XZ 平面の法線は -Y
            pts = [] if inter is None else [vec(v) for v in inter.vertices()]
            print(f"E{a.edge:02d} x plane Y={a.plane_y}: {pts if pts else '交点なし'}")
        return 0

    for i, f in enumerate(faces):
        if f.area >= a.min_area:
            print(face_line(i, f))
    if a.edges:
        for i, e in enumerate(edges):
            if e.length >= 0.0:
                print(f"E{i:02d} {e.geom_type.name:<8} length {e.length:8.2f} start {vec(e @ 0)} end {vec(e @ 1)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
