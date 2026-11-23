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
    # 長靴(小・大)。b1bow は、全長を 4 mm 短くするため縦を少し浅くした(FreeCAD の値は L9.1241, R22.1729/213.197°, R46.5128/31.803°。出口は同じ位置)
    "b1bow": dict(start=(0.0, 0.0), heading=-90.0, kind="boot",
                  segs=[("L", 8.0), ("A", 12.0, -55.7251), ("L", 7.1545), ("A", 19.1396, 217.6314), ("A", 44.1297, 18.0937), ("L", 30.0)]),
    "f1bow": dict(start=(0.0, 0.0), heading=-90.0, kind="boot",
                  segs=[("L", 10.0), ("A", 15.0, -90.0), ("L", 16.0), ("A", 29.1426, 163.1973), ("A", 46.0985, 106.8027), ("L", 37.9107)]),
    # f1bow は、横を +2.2 mm 張り出し(反転後に +x)、縦(深さ)を約 6 mm 浅くした。入口の曲げは R15・90° のまま(コンパクト)、横向きの直線部は 35.6 → 16 mm、張り出し端の R は 24.1 → 29.1 に大きくして丸みを持たせた(曲線部の長さは同じ)。
    # 胃袋(小・大)。b1bow・f1bow・b3bow は、外管・中管を長くするため(外管約 64)、曲線部を短くした(fit_head_length.py。FreeCAD の値は git 履歴)
    "b3bow": dict(start=(0.0, 0.0), heading=-90.0, kind="stomach",
                  segs=[("L", 18.0), ("A", 41.6949, 105.9513), ("A", 73.9455, 13.0021), ("A", 56.5813, 67.7902), ("A", 25.5658, 202.5403),
                        ("L", 6.1818), ("A", 17.5, -209.2838), ("L", 25.0)]),
    # f3bow は F 第 3 抜差で、上側の横向き枝管の延長と干渉しないよう、頭の高さを約 10.5 mm 低くした(FreeCAD の値: R44.7932/90°, R83.2068/123.0118°, R40.5573/188.1249°, 直線 25, R26.5/-221.1366°)。さらに、第 3 外管との距離を 10.3 → 約 4 mm にするため、S 字部を 6.3 mm 内側へ、張り出しも 6.3 mm 内側へ寄せた(曲線部の長さは同じ)
    "f3bow": dict(start=(0.0, 0.0), heading=-90.0, kind="stomach",
                  segs=[("L", 33.7068), ("A", 45.5413, 96.1164), ("A", 80.1408, 121.4496), ("A", 37.5765, 188.2866),
                        ("L", 22.2391), ("A", 26.7484, -225.8526), ("L", 35.0)]),
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
