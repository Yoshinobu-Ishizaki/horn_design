"""bb-return の「への字」: 2 つの端点・向きを、直線 + 左右対称な 5 次ベジェ(G2)+ 直線でつなぐ(平面内)。

2 本の直線(始点 A の向き tA、終点 B へ入る向き tB)の交点を Q(への字の頂点)とする。ベジェは Q の前後 d の点で始まり・終わり、
Q の角の二等分線について左右対称(2 つの直線への進入を入れ替えても同じ形)。両端の曲率は 0(直線と G2)。
制御点: P0 = Q - d·tA, P1 = P0 + a·tA, P2 = P0 + (a+b)·tA, P5 = Q + d·tB, P4 = P5 - a·tB, P3 = P5 - (a+b)·tB。
d・a・b は最小曲げ半径が最大になるように決める(d は、A 側の直線が ST_MIN 以上残る範囲)。
"""

from __future__ import annotations

from math import comb

import numpy as np

ST_MIN = 4.0  # 端の直線の最小長さ


def corner(A, tA, B, tB):
    """直線 A + s·tA と 直線 B - u·tB の交点 Q と、s, u(Q までの長さ)。平面内(z 一定)を仮定。"""
    M = np.column_stack([tA[:2], tB[:2]])
    s, u = np.linalg.solve(M, (B - A)[:2])  # A + s tA = B - u tB の u は符号を反転して使う
    return A + s * tA, float(s), float(u)


def ctrl(Q, tA, tB, d, a, b):
    P0, P5 = Q - d * tA, Q + d * tB
    return np.array([P0, P0 + a * tA, P0 + (a + b) * tA, P5 - (a + b) * tB, P5 - a * tB, P5])


def curvature(P, n=600):
    t = np.linspace(0, 1, n)
    k = len(P) - 1
    Bn = lambda m, tt: np.array([comb(m, i) * tt**i * (1 - tt) ** (m - i) for i in range(m + 1)]).T  # noqa: E731
    d1, d2 = k * np.diff(P, axis=0), k * (k - 1) * np.diff(P, n=2, axis=0)
    f1, f2 = Bn(k - 1, t) @ d1[:, :2], Bn(k - 2, t) @ d2[:, :2]
    kap = (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0]) / np.linalg.norm(f1, axis=1) ** 3
    return kap, Bn(k, t) @ P


def solve(A, tA, B, tB, st_min=ST_MIN):
    """(下の _solve の結果をディスクに覚える。入力とソースが同じなら最適化しない。2026-11-24、表示を速くするため)"""
    from pathlib import Path

    from shape_cache import memo_value

    key = [round(float(x), 9) for x in [*np.ravel(A), *np.ravel(tA), *np.ravel(B), *np.ravel(tB), st_min]]
    return memo_value("chevron_solve", key, Path(__file__), lambda: _solve(A, tA, B, tB, st_min))


def _solve(A, tA, B, tB, st_min=ST_MIN):
    from scipy.optimize import differential_evolution

    Q, sA, sB = corner(A, tA, B, tB)
    d_max = min(sA, sB) - st_min

    def cost(v):
        d, a, b = v
        if a + b > d * 1.0 + 1e-9:
            return 1e3
        kap, _ = curvature(ctrl(Q, tA, tB, d, a, b), 300)
        return 100.0 * np.abs(kap).max()

    res = differential_evolution(cost, [(2.0, d_max), (0.3, d_max), (0.3, d_max)], seed=0, maxiter=300, popsize=30, tol=1e-10, polish=True)
    return Q, sA, sB, res.x


def wire(A, tA, B, tB, Q, d, a, b):
    from build123d import Edge, Vector, Wire

    P = ctrl(Q, tA, tB, d, a, b)
    es = [Edge.make_line(Vector(*A), Vector(*P[0])), Edge.make_bezier(*[Vector(*p) for p in P]), Edge.make_line(Vector(*P[5]), Vector(*B))]
    kap, _ = curvature(P)
    return Wire(es), kap, es[1].length
