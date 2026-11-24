"""Bb の戻りループの後半: 2 本目の中管(slide_u.py)の先から GAP2 mm 離した点から、第 1 の 2 階・右上(v1-f2-45 = valve1_tube_F2_45)の出口へ。
座標は管体組立のワールド。管体組立(assy_with_valves)の hook で足す。

経路: 始点から +Y 向きに STRAIGHT_END の直線 → 3 次ベジェのスプライン(円弧とは限らない)→ 終点へ入る STRAIGHT_END の直線(向きは出口の外向きの逆)。
すべて z = 34 の平面内。スプラインは両端の直線に G1 でつながり、最小曲げ半径 R_MIN 以上・隙間 GAP_REQ 以上のうち芯線が最短のものを選ぶ。
管は内径 12.0・板厚 0.4(外径 12.8)。

    uv run python cad/bb_return/ocp/bb_return.py [--rmin 20] [--straight 20] [--gap2 1.0]
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
R_MIN = 20.0  # 経路の最小曲げ半径の下限(芯線をなるべく短くするので、この値に近づく)
GAP_REQ = 0.3  # 軸と他の部品の頂点の距離から出した隙間の下限(サンプリング誤差の余裕)
START_NAME = "valve4_knuckle_F1_315_45deg_plusx"
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


STRAIGHT_END = 20.0  # 両端の直線部の長さ(5 では曲げが強すぎたので 20 に。--straight で変える)
ARC_R = 30.0  # 円弧の半径(2 直線をつなぐ 1 つの円弧)。大きいほど経路は短い。直線が残る上限は min(|Q-始点|, |Q-終点|) / tan(θ/2)
GAP2 = 1.0  # 2 本目の中管の先から始点までの距離


def arc_path(p_start, t_start, p_end, t_end, straight):
    """2 直線(始点の直線と、終点の出口を通る直線)を 1 つの真の円弧でつないだ平面内の芯線。半径 R は、始点側の直線部が straight になるように決まる
    (接線の長さ tl = R·tan(θ/2) = |Q - 始点| - straight)。終点側の直線部は、その残り(straight 以上になるよう、短い方に合わせる)。戻り値: (Wire, info)。"""
    from build123d import Edge, Vector, Wire

    t1, t2 = np.asarray(t_start, float), np.asarray(t_end, float)
    A = np.column_stack([t1[:2], t2[:2]])
    s, u = np.linalg.solve(A, (np.asarray(p_end, float) - np.asarray(p_start, float))[:2])  # 角 Q までの長さ(始点側 s、終点側 u)
    Q = np.asarray(p_start, float) + s * t1
    theta = math.acos(float(np.clip(t1 @ t2, -1, 1)))  # 曲がり角
    tl = min(s, u) - straight  # 接線の長さ(両側で同じ)。短い方の直線が straight になる
    r = tl / math.tan(theta / 2)
    a, b = Q - tl * t1, Q + tl * t2
    n = np.cross([0, 0, 1.0], t1) * np.sign(np.cross(t1, t2)[2])
    o = a + r * n
    mid = o + r * (Q - o) / np.linalg.norm(Q - o)
    arc = Edge.make_three_point_arc(Vector(*a), Vector(*mid), Vector(*b))
    p_start, p_end = np.asarray(p_start, float), np.asarray(p_end, float)
    w = Wire([Edge.make_line(Vector(*p_start), Vector(*a)), arc, Edge.make_line(Vector(*b), Vector(*p_end))])
    return w, dict(Q=Q, r=r, theta=math.degrees(theta), s1=s - tl, s2=u - tl, arc_len=r * theta, C=np.array([a + (b - a) * k for k in np.linspace(0, 1, 2)]), o=o)


def spline_path(p_start, t_start, p_end, t_end, straight, k0, k1):
    """両端に straight mm の直線 + その間を 3 次ベジェ(接線の大きさ k0, k1)でつないだ、平面内の芯線。戻り値: (Wire, 制御点)。"""
    from build123d import Edge, Vector, Wire

    ps, ts, pe, te = (np.asarray(v, float) for v in (p_start, t_start, p_end, t_end))
    A, B = ps + straight * ts, pe - straight * te
    Pc = np.array([A, A + k0 * ts / 3, B - k1 * te / 3, B])
    w = Wire([Edge.make_line(Vector(*ps), Vector(*A)), Edge.make_bezier(*[Vector(*p) for p in Pc]), Edge.make_line(Vector(*B), Vector(*pe))])
    return w, Pc


def bezier_stats(Pc, n=200):
    t = np.linspace(0, 1, n)[:, None]
    C = (1 - t) ** 3 * Pc[0] + 3 * (1 - t) ** 2 * t * Pc[1] + 3 * (1 - t) * t**2 * Pc[2] + t**3 * Pc[3]
    d1 = 3 * ((1 - t) ** 2 * (Pc[1] - Pc[0]) + 2 * (1 - t) * t * (Pc[2] - Pc[1]) + t**2 * (Pc[3] - Pc[2]))
    d2 = 6 * ((1 - t) * (Pc[2] - 2 * Pc[1] + Pc[0]) + t * (Pc[3] - 2 * Pc[2] + Pc[1]))
    kap = np.linalg.norm(np.cross(d1, d2), axis=1) / np.linalg.norm(d1, axis=1) ** 3
    return C, 1 / kap.max(), float(np.linalg.norm(np.diff(C, axis=0), axis=1).sum())


def hook(M, branch, others):
    """Bb 抜差(U 字)の先から第 1 の 2 階右上の枝管(v1-f2-45)へ。両端に直線、中間は左右対称な G2 スプライン(への字、chevron.py)。z = 34 の平面内。"""
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    import chevron as CH
    import slide_u as BS

    branch, p0, n0, c0 = BS.hook(M, branch, others)  # 2番管・bb34・主管補助管・第 4 の 1 階右下の枝管につけた U 字も一緒に出す
    others = others + list(zip(n0, p0))
    wu = dict(zip(n0, p0))["v4_f1_315_U_centerline"]
    q, t = wu.position_at(1.0), wu.tangent_at(1.0)
    A, tA = np.array([q.X, q.Y, q.Z]), np.array([t.X, t.Y, t.Z])
    P_e, n_e = exit_of(END_NAME, (35.0, 0.0))
    B, tB = P_e, -n_e
    Q, sA, sB, (d, a, b) = CH.solve(A, tA, B, tB)
    w, kap, clen = CH.wire(A, tA, B, tB, Q, d, a, b)
    print(f"start {A.round(3).tolist()} dir {tA.round(3).tolist()}; end {END_NAME} {B.round(3).tolist()} travel {tB.round(3).tolist()}; apex Q {Q.round(3).tolist()} (A side {sA:.3f}, B side {sB:.3f})")
    print(f"chevron: straight {sA - d:.3f} + symmetric quintic Bezier {clen:.3f} (d {d:.3f}, a {a:.3f}, b {b:.3f}) + straight {sB - d:.3f} = {w.length:.3f}; "
          f"min bend R {1 / np.abs(kap).max():.2f}, curvature ends {kap[0]:.1e} / {kap[-1]:.1e}")
    tube = U.const_d_tube(w, D, BP.WALL, np.array([0.0, 0.0, 1.0]))
    print(f"tube D {D:g} wall {BP.WALL:g}: valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (<5 mm) of the outer surface:")
    B2.report_clearance(tube, others)
    return branch, p0 + [tube, w], n0 + ["bb_return_wall", "bb_return_centerline"], c0 + ["#e0a020", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
