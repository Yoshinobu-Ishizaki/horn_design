"""頭管(bow)。12.8×12.0 のパイプ(外径 12.8、内径 12.0)を、中心線に沿って曲げたもの。

形は 3 種類: U 字、長靴(外径に見える形)、胃袋(第 3 抜差の形)。FreeCAD の cad/basic_parts/*bow*.FCStd の
Body の面(円筒・円環)から読み取った中心線(直線と円弧の連なり)を、build123d で作り直した。

座標: FreeCAD と同じ。管は XY 平面内(z=0)に、中心線の始端が START、向きが HEADING [deg] で始まる。
中心線の構成 segs: ("L", 長さ) は直線、("A", 半径, 角度) は円弧(角度の符号 + は左折・反時計回り、- は右折)。
bow_p35 だけは中心線が B スプライン(3 次ベジェ)なので、別に作る。
"""

import math

from build123d import (
    Axis, BuildLine, BuildSketch, Circle, CenterArc, Line, Plane, Vector, make_face, sweep,
)

OD = 12.8
ID = 12.0

# 名前 → 始点、始端の向き [deg]、中心線の構成
BOWS = {
    # U 字(細い)。半径 10 の半円と、長さ 5 の直管 2 本
    # 直管の長さは、U 字系で統一して 5(FreeCAD の f2bow は 8 だった。一時 4 にしたが、他の U 字管と同じ 5 に統一)
    "f2bow": dict(start=(-10.0, 0.0), heading=90.0, segs=[("L", 5.0), ("A", 10.0, -180.0), ("L", 5.0)], kind="U"),
    # 長靴(小・大)
    "b1bow": dict(start=(0.0, 0.0), heading=-90.0, kind="boot",
                  segs=[("L", 8.0), ("A", 12.0, -65.0), ("L", 9.1241), ("A", 22.1729, 213.197), ("A", 46.5128, 31.803), ("L", 30.0)]),
    "f1bow": dict(start=(0.0, 0.0), heading=-90.0, kind="boot",
                  segs=[("L", 10.0), ("A", 15.0, -85.0), ("L", 25.0), ("A", 33.3052, 175.0), ("A", 55.6948, 90.0), ("L", 37.9107)]),
    # 胃袋(小・大)
    "b3bow": dict(start=(0.0, 0.0), heading=-90.0, kind="stomach",
                  segs=[("L", 18.0), ("A", 41.5, 110.0), ("A", 74.0, 17.8791), ("A", 57.4603, 71.7967), ("A", 28.1441, 201.1037),
                        ("L", 6.0), ("A", 17.5, -220.7795), ("L", 25.0)]),
    "f3bow": dict(start=(0.0, 0.0), heading=-90.0, kind="stomach",
                  segs=[("L", 33.7068), ("A", 44.7932, 90.0), ("A", 83.2068, 123.0118), ("A", 40.5573, 188.1249),
                        ("L", 25.0), ("A", 26.5, -221.1366), ("L", 35.0)]),
}


def _annulus(origin: Vector, heading: Vector):
    pl = Plane(origin=origin, z_dir=heading)
    with BuildSketch(pl) as sk:
        Circle(OD / 2)
        Circle(ID / 2, mode=__import__("build123d").Mode.SUBTRACT)
    return sk.sketch.faces()[0]


def centerline(start, heading_deg, segs):
    """中心線(Wire)と、終端の位置・向きを返す。"""
    x, y = start
    h = math.radians(heading_deg)
    with BuildLine() as bl:
        for seg in segs:
            if seg[0] == "L":
                L = seg[1]
                nx, ny = x + L * math.cos(h), y + L * math.sin(h)
                Line((x, y), (nx, ny))
                x, y = nx, ny
            else:
                R, ang = seg[1], seg[2]
                sgn = 1.0 if ang > 0 else -1.0
                cx, cy = x - sgn * R * math.sin(h), y + sgn * R * math.cos(h)  # 左折なら進行方向の左に中心
                a0 = math.degrees(math.atan2(y - cy, x - cx))
                CenterArc((cx, cy), R, a0, ang)
                h += math.radians(ang)
                x, y = cx + R * math.cos(math.radians(a0 + ang)), cy + R * math.sin(math.radians(a0 + ang))
    return bl.wire(), (x, y), math.degrees(h)


def bow(name: str):
    d = BOWS[name]
    wire, end, hend = centerline(d["start"], d["heading"], d["segs"])
    h = math.radians(d["heading"])
    prof = _annulus(Vector(d["start"][0], d["start"][1], 0), Vector(math.cos(h), math.sin(h), 0))
    return sweep(prof, path=wire)


def _bezier_as_bspline_edge(ctrl):
    """3 次ベジェ(制御点 ctrl)を、同じ形の B スプライン曲線の辺にする(sweep はベジェ辺を通せないため)。"""
    from build123d import Edge
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BezierCurve
    from OCP.GeomConvert import GeomConvert
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt

    arr = Array1_gp_Pnt(1, len(ctrl))
    for i, (x, y) in enumerate(ctrl, start=1):
        arr.SetValue(i, gp_Pnt(x, y, 0.0))
    bsp = GeomConvert.CurveToBSplineCurve_s(Geom_BezierCurve(arr))
    return Edge(BRepBuilderAPI_MakeEdge(bsp).Edge())


def bow_p35():
    """幅広の U 字: 長さ 5 の直管 + 3 次ベジェ(制御点 (0,5),(0,25),(35,25),(35,5))+ 長さ 5 の直管。始端 (0,0) で +Y 向き。"""
    from build123d import Edge, Wire

    e1 = Edge.make_line((0, 0, 0), (0, 5, 0))
    e2 = _bezier_as_bspline_edge([(0, 5), (0, 25), (35, 25), (35, 5)])
    e3 = Edge.make_line((35, 5, 0), (35, 0, 0))
    wire = Wire([e1, e2, e3])
    prof = _annulus(Vector(0, 0, 0), Vector(0, 1, 0))
    return sweep(prof, path=wire, is_frenet=True)  # ベジェ(B スプライン)の辺は、Frenet フレームでないと sweep できない


def all_bows():
    out = {"bow_p35": bow_p35()}
    for n in BOWS:
        out[n] = bow(n)
    return out


FREECAD_VOLUME = {"bow_p35": 960.2, "f2bow": 738.8,  # f2bow は直管を 8 → 5 に変えたので、体積は 738.8 より小さい(661.5)
                   "b1bow": 2634.3, "f1bow": 4431.2, "b3bow": 6076.9, "f3bow": 9009.0}


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    bows = all_bows()
    parts, names, x = [], [], 0.0
    for n, s in bows.items():
        bb = s.bounding_box()
        parts.append(Pos(x - bb.min.X, -bb.min.Y, 0) * s)
        names.append(n)
        x += bb.size.X + 20
    show(*parts, names=names, reset_camera=Camera.KEEP)
    for n, s in bows.items():
        bb = s.bounding_box()
        print(f"{n}: valid={s.is_valid} volume={s.volume:.1f} (FreeCAD {FREECAD_VOLUME[n]}) "
              f"x=[{bb.min.X:.1f},{bb.max.X:.1f}] y=[{bb.min.Y:.1f},{bb.max.Y:.1f}] z=[{bb.min.Z:.1f},{bb.max.Z:.1f}]")


if __name__ == "__main__":
    main()
