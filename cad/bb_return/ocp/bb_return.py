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


STRAIGHT_END = 20.0  # 両端の直線部の長さ(5 では曲げが強すぎたので 20 に。--straight で変える)
ARC_R = 30.0  # 円弧の半径(2 直線をつなぐ 1 つの円弧)。大きいほど経路は短い。直線が残る上限は min(|Q-始点|, |Q-終点|) / tan(θ/2)
GAP2 = 1.0  # 2 本目の中管の先から始点までの距離


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
    import slide_u as BS
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U

    branch, p0, n0, c0 = BS.hook(M, branch, others)  # 2番管・bb34・主管補助管・抜差の中管と U も一緒に出す
    others = others + list(zip(n0, p0))
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    gap2 = arg("--gap2", GAP2)
    tube2 = dict(others)["Bb_return_inner_tube_2"]
    tip = tube2.bounding_box().max.Y  # 2 本目の中管の先端(+Y)
    cx = tube2.bounding_box().center()
    p_start = np.array([cx.X, tip + gap2, cx.Z])
    P_e, n_e = exit_of(END_NAME, (35.0, 0.0))
    t_s, t_e = np.array([0.0, 1.0, 0.0]), -n_e
    print(f"start {p_start.round(3).tolist()} (2nd inner tube tip y {tip:.3f} + {gap2:g}), direction {t_s.tolist()}")
    print(f"end {END_NAME}: {P_e.round(3).tolist()}, out {n_e.round(3).tolist()} (travel in {t_e.round(3).tolist()})")
    straight, rmin_req, gap_req = arg("--straight", STRAIGHT_END), arg("--rmin", R_MIN), arg("--gap", GAP_REQ)
    # 障害物: 経路の近く(包絡)にある部品だけ、ワールド座標の頂点を取る(全部品の三角形分割は遅い)
    from build123d import Box, Pos
    from main_aux import tess_world
    from scipy.spatial import cKDTree

    lo = np.minimum(p_start, P_e) - 15
    hi = np.maximum(p_start, P_e) + 15
    near_box = Pos(*((lo + hi) / 2)) * Box(*(hi - lo))
    nb = near_box.bounding_box()
    pts = []
    for n_, sh_ in others:
        if n_ in (END_NAME, "Bb_return_inner_tube_2") or n_.endswith("centerline") or not hasattr(sh_, "bounding_box"):
            continue
        if B2.near(sh_.bounding_box(), nb, 0.0):
            pts += tess_world(sh_, 0.2)
    tree = cKDTree(np.array(pts)) if pts else None
    print(f"obstacle vertices near the path: {len(pts)}")
    def best_for(st):
        Lab = np.linalg.norm((P_e - st * t_e) - (p_start + st * t_s))
        best = None
        for f0 in np.linspace(0.2, 2.0, 37):
            for f1 in np.linspace(0.2, 2.0, 37):
                _, Pc = spline_path(p_start, t_s, P_e, t_e, st, f0 * Lab, f1 * Lab)
                C, rmin_, ln = bezier_stats(Pc)
                gap = (tree.query(C)[0].min() - D / 2 - 0.4) if tree is not None else 99.0
                if rmin_ >= rmin_req and gap >= gap_req and (best is None or ln < best[0]):
                    best = (ln, f0 * Lab, f1 * Lab, rmin_, gap)
        return best

    print("両端の直線部 → 芯線の長さ(直線 2 本を含む)・ベジェの最小 R・隙間:")
    for st in (5, 10, 15, 20, 25, 30, 35):
        bs = best_for(st)
        print(f"  straight {st:2d}: " + (f"length {bs[0] + 2 * st:.2f}, min R {bs[3]:.2f}, gap {bs[4]:.3f}" if bs else "no solution"))
    best = best_for(straight)
    if best is None:
        raise RuntimeError("条件(最小 R・隙間)を満たす解がない")
    ln, k0, k1, rmin_, gap = best
    w, Pc = spline_path(p_start, t_s, P_e, t_e, straight, k0, k1)
    print(f"spline: straight {straight:g} + cubic Bezier + straight {straight:g}; tangent scales {k0:.2f}, {k1:.2f}; min bend R {rmin_:.2f} (required {rmin_req:g}); "
          f"axis-based gap {gap:.3f}; Bezier length {ln:.3f}")
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
