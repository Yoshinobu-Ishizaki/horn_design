"""主管補助管(main-aux-tube)の軸線。管体組立(assy_with_valves.py)の hook で足す。座標は管体組立のワールド。

1. P1: 平面 x = 87.5。これより +X 側のベルと 1番管の +Z 側の表面を、P1 へ(X 方向に)投影し、上側の輪郭を直線で近似する(最小二乗)。
2. P2: その近似直線を通る(YZ に直交する = X 方向に伸びる)平面を、+Z 側へ法線方向に OFFSET だけずらした平面。
3. 点 S: P2 と P1 の交線の上で Y = Y_S の点。ここでの軸線の向きは (1, 0, 0)。
4. 軸線: 第 4 の 1 階・左下(225°)のねじった枝管の出口の端面の中心 E(外向きの軸 u)から S へ、なめらかな 3 次(ベジェ)の曲線。
   E での向きは u、S での向きは (+1, 0, 0)(E → S の進む向き)。接線の大きさ(2 つ)は、最小曲率半径が最大になるように決める。

    uv run python cad/main_aux_tube/ocp/main_aux.py [--y -40] [--offset 10] [--x 87.5]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"),
                str(ROOT / "cad/bell03/tools"), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/branch2/ocp")]

X_P1 = 87.5
OFFSET = 10.0
Y_S = -40.0
FIT_Y = (-175.0, 60.0)  # 近似に使う Y の範囲(ベルのリム端の立ち上がりを除く)
BIN = 4.0


def f1_225_exit():
    """第 4 の 1 階・左下(225°)のねじった枝管の出口の端面の中心と外向きの軸(-Y 側へ向く方の円環)。"""
    import valve4_knuckle as V

    k = V.twisted_knuckle()
    a_ring = math.pi / 4 * (12.8**2 - 12.0**2)
    f = max((f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.area - a_ring) < 0.5), key=lambda f: -f.normal_at().Y)
    c, n = f.center(), f.normal_at()
    return np.array([c.X, c.Y, c.Z]), np.array([n.X, n.Y, n.Z])


def upper_profile(shapes, x_p1=X_P1):
    """x >= x_p1 の表面を P1(x = x_p1)へ投影して、Y ごとの Z の最大(上側の輪郭)を返す (ys, zs)。"""
    pts = []
    for s in shapes:
        v, _ = s.tessellate(0.05, 0.1)
        pts += [(p.X, p.Y, p.Z) for p in v]
    P = np.array(pts)
    P = P[P[:, 0] >= x_p1]
    edges = np.arange(P[:, 1].min(), P[:, 1].max() + BIN, BIN)
    ys, zs = [], []
    for lo in edges:
        m = (P[:, 1] >= lo) & (P[:, 1] < lo + BIN)
        if m.any():
            i = np.argmax(P[m, 2])
            ys.append(P[m][i, 1])
            zs.append(P[m][i, 2])
    return np.array(ys), np.array(zs)


def bezier(E, tE, S, tS, k0, k1):
    return np.array([E, E + k0 * tE / 3, S - k1 * tS / 3, S])


def min_radius(B, n=400):
    t = np.linspace(0, 1, n)[:, None]
    d1 = 3 * ((1 - t) ** 2 * (B[1] - B[0]) + 2 * (1 - t) * t * (B[2] - B[1]) + t**2 * (B[3] - B[2]))
    d2 = 6 * ((1 - t) * (B[2] - 2 * B[1] + B[0]) + t * (B[3] - 2 * B[2] + B[1]))
    kappa = np.linalg.norm(np.cross(d1, d2), axis=1) / np.linalg.norm(d1, axis=1) ** 3
    return 1 / kappa.max(), kappa


def best_scales(E, tE, S, tS):
    best = None
    L = np.linalg.norm(S - E)
    for k0 in np.linspace(0.3, 3.0, 55) * L:
        for k1 in np.linspace(0.3, 3.0, 55) * L:
            r = min_radius(bezier(E, tE, S, tS, k0, k1))[0]
            if best is None or r > best[0]:
                best = (r, k0, k1)
    return best


def hook(M, branch, others):
    import bell_place as BP
    from build123d import Compound, Edge, Face, Plane, Polyline, Vector, Wire

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    x1, off, ys_ = arg("--x", X_P1), arg("--offset", OFFSET), arg("--y", Y_S)

    bell = dict(others)["bell03_bell_wall"]
    ys, zs = upper_profile([bell, branch], x1)
    m = (ys >= FIT_Y[0]) & (ys <= FIT_Y[1])
    a, b = np.polyfit(ys[m], zs[m], 1)
    res = zs[m] - (a * ys[m] + b)
    print(f"P1 x = {x1:g}: upper profile of bell + branch1 (x >= {x1:g}), {m.sum()} bins in y {FIT_Y}")
    print(f"fit line z = {a:.5f} y + {b:.4f} (slope {math.degrees(math.atan(a)):.3f} deg); residual max {np.abs(res).max():.3f}, rms {np.sqrt((res**2).mean()):.3f}")
    # P2: 近似直線を +Z 側へ法線方向に off ずらす。法線 n = (0, -a, 1)/√(1+a²)
    nrm = np.array([0.0, -a, 1.0]) / math.sqrt(1 + a * a)
    b2 = b + off * math.sqrt(1 + a * a)
    print(f"P2: plane through the fit line offset {off:g} along its +Z normal {nrm.round(4).tolist()}; on P1: z = {a:.5f} y + {b2:.4f}")
    S = np.array([x1, ys_, a * ys_ + b2])
    tS = np.array([1.0, 0.0, 0.0])
    E, u = f1_225_exit()
    print(f"S (P1 ∩ P2, y {ys_:g}) = {S.round(3).tolist()}, direction (1, 0, 0)")
    print(f"E (valve4 F1-225 exit) = {E.round(3).tolist()}, outward axis {u.round(4).tolist()}")
    r, k0, k1 = best_scales(E, u, S, tS)
    B = bezier(E, u, S, tS, k0, k1)
    rmin, kap = min_radius(B)
    L = np.linalg.norm(S - E)
    print(f"cubic Bezier E -> S: tangent scales {k0:.2f}, {k1:.2f} (chord {L:.2f}); min bend R {rmin:.2f}")
    edge = Edge.make_bezier(*[Vector(*p) for p in B])
    w = Wire([edge])
    print(f"axis length {w.length:.3f}")
    ends = [w.position_at(0.0), w.position_at(1.0)]
    t0, t1 = w.tangent_at(0.0), w.tangent_at(1.0)
    print(f"check: start {np.round([ends[0].X, ends[0].Y, ends[0].Z], 3).tolist()}, tangent {np.round([t0.X, t0.Y, t0.Z], 4).tolist()}; "
          f"end {np.round([ends[1].X, ends[1].Y, ends[1].Z], 3).tolist()}, tangent {np.round([t1.X, t1.Y, t1.Z], 4).tolist()}")
    # 表示用: 近似直線(P1 上)、P1 上のオフセット直線、点 S、P1・P2 の見える範囲の薄い板
    y0, y1 = FIT_Y
    fit_line = Edge.make_line(Vector(x1, y0, a * y0 + b), Vector(x1, y1, a * y1 + b))
    off_line = Edge.make_line(Vector(x1, y0, a * y0 + b2), Vector(x1, y1, a * y1 + b2))
    prof = Polyline(*[(x1, float(y), float(z)) for y, z in zip(ys, zs)])
    import build123d as bd

    sphere = bd.Pos(*S) * bd.Sphere(1.5)
    p1 = Face(Wire.make_polygon([Vector(x1, y0, 20), Vector(x1, y1, 20), Vector(x1, y1, 100), Vector(x1, y0, 100)], close=True))
    return branch, [w, prof, fit_line, off_line, sphere, p1], [
        "main_aux_axis", "main_aux_profile_on_P1", "main_aux_fit_line", "main_aux_P2_on_P1", "main_aux_S", "main_aux_P1"
    ], ["#ff2020", "#808080", "#00c0ff", "#00c0ff", "#ff2020", "#80c0ff"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
