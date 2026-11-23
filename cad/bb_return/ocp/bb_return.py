"""Bb の残りのループ: 第 4 の 1 階右下(v4-knuckle-f1-315 = valve4_knuckle_F1_315_45deg_minusy)の出口から、
第 1 の 2 階・右上(v1-f2-45 = valve1_tube_F2_45)の出口へ。座標は管体組立のワールド。管体組立(assy_with_valves)の hook で足す。

経路: 始点の出口から 4 mm 直線 → +Y 側へ回り込むスプライン → 終点の出口の手前 4 mm から直線(入る向き)。
スプラインは、途中の 3 点と両端の接線の大きさを差分進化で決める(長さ最短。隙間 ≥ GAP_REQ、最小曲げ半径 ≥ R_MIN)。
管は内径 12.0・板厚 0.4(外径 12.8)。

    uv run python cad/bb_return/ocp/bb_return.py [--gap 0.3] [--rmin 10] [--straight 4]
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


def hook(M, branch, others):
    import main_aux as MA
    from build123d import Edge, Spline, Vector, Wire
    from scipy.interpolate import CubicSpline
    from scipy.optimize import differential_evolution
    from scipy.spatial import cKDTree

    import branch2_l as B2
    import branch2_u as U
    import bell_place as BP

    branch, p0, n0, c0 = MA.hook(M, branch, others)  # 2番管・bb34・主管補助管も一緒に出す
    others = others + list(zip(n0, p0)) + [("bell03_branch1_wall", branch)]
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    st, gap_req, r_min = arg("--straight", STRAIGHT), arg("--gap", GAP_REQ), arg("--rmin", R_MIN)

    P_s, n_s = exit_of(START_NAME, (70.0, 0.0))  # 第 4 の中心から遠い方
    P_e, n_e = exit_of(END_NAME, (35.0, 0.0))  # 第 1 の中心から遠い方
    t_s, t_e = n_s, -n_e  # 進む向き: 始点では外向き、終点では入る向き(外向きの逆)
    A_, B_ = P_s + st * t_s, P_e - st * t_e  # 直線部の先 / 終点の手前
    print(f"start {START_NAME}: {P_s.round(3).tolist()}, out {n_s.round(3).tolist()}")
    print(f"end   {END_NAME}: {P_e.round(3).tolist()}, out {n_e.round(3).tolist()} (travel in {t_e.round(3).tolist()})")

    pts, lab = [], []
    for n, sh in others:
        if n in (START_NAME, END_NAME) or n.endswith("centerline") or not hasattr(sh, "tessellate"):
            continue
        v = MA.tess_world(sh, 0.15)
        pts += v
        lab += [n] * len(v)
    tree = cKDTree(np.array(pts))

    def curve(x, n=160):
        V = x[:9].reshape(3, 3)
        Q = np.vstack([A_, V, B_])
        u = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
        cs = CubicSpline(u, Q, bc_type=((1, x[9] * t_s), (1, x[10] * t_e)))
        uu = np.linspace(0, u[-1], n)
        return cs(uu), cs(uu, 1), cs(uu, 2)

    def evaluate(x):
        C, d1, d2 = curve(x)
        kap = np.linalg.norm(np.cross(d1, d2), axis=1) / np.maximum(np.linalg.norm(d1, axis=1), 1e-9) ** 3
        d, i_ = tree.query(C[6:-6])
        ln = float(np.linalg.norm(np.diff(C, axis=0), axis=1).sum())
        return d.min() - D / 2 - 0.4, 1 / max(kap.max(), 1e-9), ln, lab[int(i_[int(np.argmin(d))])]

    def cost(x):
        g, r, ln, _ = evaluate(x)
        return ln + 400 * max(0, gap_req - g) + 40 * max(0, r_min - r)

    lo = np.array([20, -70, 0.0]); hi = np.array([150, 70, 100.0])
    bounds = list(zip(np.tile(lo, 3), np.tile(hi, 3))) + [(0.3, 3.0), (0.3, 3.0)]
    x0 = np.array([90, -30, 20, 105, 5, 28, 75, 28, 34, 1.0, 1.0], float)
    res = differential_evolution(cost, bounds, seed=1, popsize=30, maxiter=500, tol=1e-8, polish=False, x0=x0)
    g, r, ln, nm = evaluate(res.x)
    print(f"spline: gap {g:.3f} ({nm}), min bend R {r:.2f}, length {ln:.2f}; via {res.x[:9].reshape(3, 3).round(2).tolist()}, end tangent scales {res.x[9]:.2f}, {res.x[10]:.2f}")
    C, d1, _ = curve(res.x, 60)
    tn = d1 / np.linalg.norm(d1, axis=1)[:, None]
    spl = Spline(*[Vector(*p) for p in C], tangents=[Vector(*tn[0]), Vector(*tn[-1])])
    w = Wire([Edge.make_line(Vector(*P_s), Vector(*A_)), spl, Edge.make_line(Vector(*B_), Vector(*P_e))])
    print(f"axis length {w.length:.3f}")
    tube = U.const_d_tube(w, D, BP.WALL)
    print(f"tube D {D:g} wall {BP.WALL:g}: valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (<5 mm) of the outer surface:")
    B2.report_clearance(tube, others)
    for n_, sh_ in others:
        if n_ in (START_NAME, END_NAME) or not hasattr(sh_, "bounding_box") or not B2.near(sh_.bounding_box(), tube.bounding_box(), 0.1):
            continue
        if tube.distance_to(sh_) < 1e-6:
            inter = tube.intersect(sh_)
            ov = sum(x.volume for x in inter.solids())
            if ov > 0:
                print(f"  overlap volume with {n_}: {ov:.4f}")
    return branch, p0 + [tube, w], n0 + ["bb_return_wall", "bb_return_centerline"], c0 + ["#e0a020", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
