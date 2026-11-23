"""Bb の戻りループの後半: 2 本目の中管(slide_u.py)の先から GAP2 mm 離した点から、第 1 の 2 階・右上(v1-f2-45 = valve1_tube_F2_45)の出口へ。
座標は管体組立のワールド。管体組立(assy_with_valves)の hook で足す。

経路: 始点から +Y 向きの直線 → 1 つの円弧(半径 R)→ 終点へ入る直線(向きは出口の外向きの逆)。2 直線の角 Q は、
始点の直線と、終点の出口を通る直線の交点。すべて z = 34 の平面内。円弧は 2 直線に接する。管は内径 12.0・板厚 0.4(外径 12.8)。

    uv run python cad/bb_return/ocp/bb_return.py [--R 30] [--gap2 1.0]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "cad/main_aux_tube/ocp"), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"),
                str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

D = 12.0
STRAIGHT = 4.0
R_MIN = 10.0
GAP_REQ = 0.3
START_NAME = "valve4_knuckle_F1_315_45deg_minusy"
END_NAME = "valve1_tube_F2_45"


def exit_of(name, far_from):
    """部品の出口の端面(円環の平面)の中心と外向きの軸。far_from(植込み中心の xy)から遠い方。"""
    import all_slides as A
    from valve_row import build_row_cached

    a = math.pi / 4 * (12.8**2 - 12.0**2)
    shapes = dict(zip(A.V4_NAMES, A.valve4_knuckles()))
    for _, (_, ks, ns) in build_row_cached().items():
        shapes.update(dict(zip(ns, ks)))
    fs = [f for f in shapes[name].faces() if f.geom_type.name == "PLANE" and abs(f.area - a) < 0.5]
    f = max(fs, key=lambda f: math.hypot(f.center().X - far_from[0], f.center().Y - far_from[1]))
    c, n = f.center(), f.normal_at()
    return np.array([c.X, c.Y, c.Z]), np.array([n.X, n.Y, n.Z])


ARC_R = 30.0  # 円弧の半径(2 直線をつなぐ 1 つの円弧)。大きいほど経路は短い。直線が残る上限は min(|Q-始点|, |Q-終点|) / tan(θ/2)
GAP2 = 1.0  # 2 本目の中管の先から始点までの距離


def arc_path(p_start, t_start, p_end, t_end, r):
    """始点(向き t_start)と終点(入る向き t_end)の、2 直線を 1 つの円弧でつないだ平面内の芯線。戻り値 (Wire, info)。"""
    from build123d import Edge, Vector, Wire

    t1, t2 = np.asarray(t_start, float), np.asarray(t_end, float)
    # 角 Q: p_start + s t1 = p_end - u t2
    A = np.column_stack([t1[:2], t2[:2]])
    s, u = np.linalg.solve(A, (np.asarray(p_end, float) - np.asarray(p_start, float))[:2])
    Q = np.asarray(p_start, float) + s * t1
    theta = math.acos(float(np.clip(t1 @ t2, -1, 1)))  # 曲がり角
    tl = r * math.tan(theta / 2)
    if tl > s or tl > u:
        raise ValueError(f"R {r:g} は大きすぎる(接点までの長さ {tl:.2f} > 直線 {s:.2f} / {u:.2f})")
    a, b = Q - tl * t1, Q + tl * t2
    # 円弧の中点: 中心 o = a + r·n(n: 曲がる側の法線)、中点 = o + r·(t1 - t2)/|t1 - t2|... を a, b の中点方向から取る
    n = np.cross([0, 0, 1.0], t1) * np.sign(np.cross(t1, t2)[2])
    o = a + r * n
    mid = o + r * (Q - o) / np.linalg.norm(Q - o)
    arc = Edge.make_three_point_arc(Vector(*a), Vector(*mid), Vector(*b))
    w = Wire([Edge.make_line(Vector(*p_start), Vector(*a)), arc, Edge.make_line(Vector(*b), Vector(*p_end))])
    return w, dict(Q=Q, a=a, b=b, theta=math.degrees(theta), s=s, u=u, tl=tl, rmax=min(s, u) / math.tan(theta / 2))


def hook(M, branch, others):
    import slide_u as BS
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U

    branch, p0, n0, c0 = BS.hook(M, branch, others)  # 2番管・bb34・主管補助管・抜差の中管と U も一緒に出す
    others = others + list(zip(n0, p0))
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    r, gap2 = arg("--R", ARC_R), arg("--gap2", GAP2)
    tube2 = dict(others)["Bb_return_inner_tube_2"]
    tip = tube2.bounding_box().max.Y  # 2 本目の中管の先端(+Y)
    cx = tube2.bounding_box().center()
    p_start = np.array([cx.X, tip + gap2, cx.Z])
    P_e, n_e = exit_of(END_NAME, (35.0, 0.0))
    t_s, t_e = np.array([0.0, 1.0, 0.0]), -n_e
    print(f"start {p_start.round(3).tolist()} (2nd inner tube tip y {tip:.3f} + {gap2:g}), direction {t_s.tolist()}")
    print(f"end {END_NAME}: {P_e.round(3).tolist()}, out {n_e.round(3).tolist()} (travel in {t_e.round(3).tolist()})")
    w, info = arc_path(p_start, t_s, P_e, t_e, r)
    print(f"corner Q {info['Q'].round(3).tolist()}, turn {info['theta']:.2f} deg, R {r:g} (max {info['rmax']:.2f}); straight {info['s'] - info['tl']:.3f} + arc {math.radians(info['theta']) * r:.3f} + straight {info['u'] - info['tl']:.3f}")
    print(f"axis length {w.length:.3f}")
    tube = U.const_d_tube(w, D, BP.WALL)
    print(f"tube D {D:g} wall {BP.WALL:g}: valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (<5 mm) of the outer surface:")
    B2.report_clearance(tube, others)
    return branch, p0 + [tube, w], n0 + ["bb_return_wall", "bb_return_centerline"], c0 + ["#e0a020", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
