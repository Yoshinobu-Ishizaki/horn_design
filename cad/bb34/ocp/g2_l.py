"""bb34 の直管の端と、第 4 の 2 階左下の枝管の出口をつなぐ L 字の芯線(2026-11-24)。

平面: 枝管の出口の軸(kp1 を通る直線)を X 方向に投影した平面 = 出口の軸と +X を含む平面(直管の中心もこの上にある)。
形: 直管側の直線 st + 平面内の 5 次ベジェ(始端・終端の曲率 0 = 直線と G2 連続)+ 枝管側の直線 en(en ≥ EN_MIN = 4)。
制御点(平面内、A = 曲線の始まり、向き ex = +X、B = 曲線の終わり、向き d2):
    P0 = A, P1 = A + a·ex, P2 = A + (a+b)·ex, P3 = B - (e+f)·d2, P4 = B - e·d2, P5 = B。
最小曲げ半径が最大になるように a, b, e, f と st(≥ ST_MIN)、en を決める(差分進化)。
"""

from __future__ import annotations

import numpy as np

EN_MIN = 4.0  # 枝管側の直線の最小長さ(ユーザー指示)
ST_MIN = 4.0  # 直管側の直線の最小長さ(枝管側と同じにした)


def frame(p_start, ex, F, d2):
    """平面の基底 (ex, ey = d2 の ex に垂直な成分)と、平面の法線。F は p_start を通り ex・d2 が張る平面上にあること。"""
    ey = d2 - (d2 @ ex) * ex
    ey /= np.linalg.norm(ey)
    nrm = np.cross(ex, ey)
    assert abs((F - p_start) @ nrm) < 1e-6, "出口が平面に乗っていない"
    return ey, nrm


def ctrl(p_start, ex, ey, F, d2, v):
    """v = (st, en, a, b, e, f)。戻り値: 3 次元の制御点 6 個(曲線)と A, B。"""
    st, en, a, b, e, f = v
    A = p_start + st * ex
    B = F - en * d2
    G = np.array([(B - A) @ ex, (B - A) @ ey])
    dd = np.array([d2 @ ex, d2 @ ey])
    P = np.array([[0, 0], [a, 0], [a + b, 0], G - (e + f) * dd, G - e * dd, G])
    return np.array([A + q[0] * ex + q[1] * ey for q in P]), P, A, B


def curvature(P2, n=600):
    t = np.linspace(0, 1, n)
    from math import comb

    k = len(P2) - 1
    Bn = lambda m, tt: np.array([comb(m, i) * tt**i * (1 - tt) ** (m - i) for i in range(m + 1)]).T  # noqa: E731
    d1, d2_ = k * np.diff(P2, axis=0), k * (k - 1) * np.diff(P2, n=2, axis=0)
    f1, f2 = Bn(k - 1, t) @ d1, Bn(k - 2, t) @ d2_
    kap = (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0]) / np.linalg.norm(f1, axis=1) ** 3
    pts = Bn(k, t) @ P2
    return kap, pts


def solve(p_start, ex, F, d2, st_min=ST_MIN, en_min=EN_MIN, seed=0):
    from scipy.optimize import differential_evolution

    ey, _ = frame(p_start, ex, F, d2)

    def cost(v):
        _, P, _, _ = ctrl(p_start, ex, ey, F, d2, v)
        if P[:, 0].min() < -1e-9:
            return 1e3
        kap, pts = curvature(P, 300)
        length = np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() + v[0] + v[1]
        return 1.0 / (1.0 / np.abs(kap).max()) * 100 + 0.01 * length

    L1 = float((F - p_start) @ ex)
    L2 = float((F - p_start) @ ey)
    bounds = [(st_min, max(st_min + 1, L1 - 1)), (en_min, max(en_min + 1, L2 - 1)), (0.5, 30), (0.5, 30), (0.5, 30), (0.5, 30)]
    res = differential_evolution(cost, bounds, seed=seed, maxiter=300, popsize=30, tol=1e-10, polish=True)
    return res.x


def wire(p_start, ex, F, d2, v):
    """Wire(直線 + ベジェ + 直線)、平面の法線、曲率の配列、曲線部の長さ。"""
    from build123d import Edge, Vector, Wire

    ey, nrm = frame(p_start, ex, F, d2)
    P3, P, A, B = ctrl(p_start, ex, ey, F, d2, v)
    es = [Edge.make_line(Vector(*p_start), Vector(*A)), Edge.make_bezier(*[Vector(*q) for q in P3]), Edge.make_line(Vector(*B), Vector(*F))]
    kap, _ = curvature(P)
    return Wire(es), nrm, kap, es[1].length
