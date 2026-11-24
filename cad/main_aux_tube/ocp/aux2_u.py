"""主管補助管 2(aux2、2026-11-24): 補助管 1 の出口 F から、1 つの円弧的な G2 スプラインで +X 向きの口へ。

- 芯線の平面: 補助管 1 の出口の直線(F、向き d)を含み、YZ 平面に直交する(= X 方向を含む)平面。
- 角 Q: 出口の直線と主管頭平面(main-bow-plane、z = MB_A·y + MB_B、X 方向に伸びる)の交点。
- 口: Q から +X へ進み x = X_END で終わる。向き +X。主管頭平面の上。
- 形: 7 次ベジェ 1 本(制御点は Q から 2 本の直線の上に 4 つずつ。両端で 3 点が直線上なので端の曲率 0 = 直線と G2)。
  両端に直線(少なくとも START_ST・END_ST = 5 mm、2026-11-24 ユーザー)。スプラインは Q から両側へ同じ長さ(短い方の脚に合わせ、
  長い方の脚の余りは直線にする)、制御点も左右対称。脚が違うと片側だけ曲率がだらだら残り、円弧らしくならないため。制御点の距離は、曲率の最大を小さく・曲率の変化をなめらかに(円弧に近く)決める。
"""

from __future__ import annotations

from math import comb

import numpy as np

MB_A, MB_B = -0.06624, 77.6983  # 主管頭平面 z = MB_A·y + MB_B(worklog 1 件目、P2)
X_END = 90.0  # 口の x(2026-11-24 ユーザー)
START_ST = 5.0  # 補助管 1 とのつなぎ目(F)からの直線
END_ST = 5.0  # 口の手前の直線
D = 12.0
OD = 12.8


def bez(cp, t):
    m = len(cp) - 1
    t = np.asarray(t)[:, None]
    return sum(comb(m, i) * t**i * (1 - t) ** (m - i) * cp[i] for i in range(m + 1))


def curvature(cp, n=400):
    """(弧長, 曲率) の列。"""
    t = np.linspace(0, 1, n)[:, None]
    m = len(cp) - 1
    d1 = sum(comb(m - 1, i) * t**i * (1 - t) ** (m - 1 - i) * m * (cp[i + 1] - cp[i]) for i in range(m))
    d2 = sum(comb(m - 2, i) * t**i * (1 - t) ** (m - 2 - i) * m * (m - 1) * (cp[i + 2] - 2 * cp[i + 1] + cp[i]) for i in range(m - 1))
    sp = np.linalg.norm(d1, axis=1)
    k = np.linalg.norm(np.cross(d1, d2), axis=1) / sp**3
    s = np.concatenate([[0.0], np.cumsum(0.5 * (sp[1:] + sp[:-1]) * np.diff(t[:, 0]))])
    return s, k


def ctrl(Q, d, X, la, lb, r):
    """r = (a1, a2, a3, b1, b2, b3): 各脚の長さに対する比(a1 > a2 > a3、b1 > b2 > b3)。"""
    a = [la, la * r[0], la * r[0] * r[1], la * r[0] * r[1] * r[2]]
    b = [lb, lb * r[3], lb * r[3] * r[4], lb * r[3] * r[4] * r[5]]
    return np.array([Q - v * d for v in a] + [Q + v * X for v in b[::-1]])


SMOOTH = 1.0  # 曲率の変化の重み(0 だと両端で曲率が急に立ち上がる)


def fit(Q, d, X, la, lb):
    """曲率の最大 + 曲率の変化を小さくする比(左右対称: 3 つを両側に使う)。"""
    from scipy.optimize import minimize

    def cost(r3):
        r = np.r_[r3, r3]
        if np.any(r <= 0.02) or np.any(r >= 0.995):
            return 1e6
        s, k = curvature(ctrl(Q, d, X, la, lb, r))
        dk = np.diff(k) / np.maximum(np.diff(s), 1e-9)
        # 両端 0 の曲率から 1 つの山へ: 最大曲率と、変化の 2 乗積分(なめらかさ)
        return k.max() * 100 + SMOOTH * float(np.sum(dk**2 * np.diff(s))) * 100

    best = None
    for r0 in ([0.7, 0.6, 0.5], [0.8, 0.7, 0.4], [0.6, 0.5, 0.3], [0.5, 0.5, 0.5], [0.9, 0.6, 0.2]):
        res = minimize(cost, r0, method="Nelder-Mead", options=dict(maxiter=8000, xatol=1e-8, fatol=1e-11))
        if best is None or res.fun < best.fun:
            best = res
    return np.r_[best.x, best.x]


def aux2_pipe(F, d, x_end=X_END, start_st=START_ST, end_st=END_ST):
    """戻り値: (Wire, info)。F: 補助管 1 の出口、d: その向き(単位)。"""
    from build123d import Edge, Vector, Wire

    F, d = np.asarray(F, float), np.asarray(d, float) / np.linalg.norm(d)
    X = np.array([1.0, 0.0, 0.0])
    # 出口の直線と主管頭平面 z - MB_A·y = MB_B の交点
    g = np.array([0.0, -MB_A, 1.0])
    a = (MB_B - g @ F) / (g @ d)
    Q = F + a * d
    lx = x_end - Q[0]  # Q から口まで
    L = min(a - start_st, lx - end_st)  # スプラインの脚(両側同じ)
    if L <= 0:
        raise ValueError(f"aux2: no room (leg to the main-bow plane {a:.3f}, +X leg {lx:.3f})")
    la = lb = L
    start_st, end_st = a - L, lx - L
    try:
        import shape_cache as SC

        r = SC.memo_value("aux2_g2_ratios", [round(float(v), 6) for v in (*Q, *d, la, lb)], __file__, lambda: fit(Q, d, X, la, lb))
    except ImportError:
        r = fit(Q, d, X, la, lb)
    cp = ctrl(Q, d, X, la, lb, r)
    A, B = cp[0], cp[-1]
    G = Q + (x_end - Q[0]) * X
    s, k = curvature(cp)
    w = Wire([Edge.make_line(Vector(*F), Vector(*A)), Edge.make_bezier(*[Vector(*c) for c in cp]), Edge.make_line(Vector(*B), Vector(*G))])
    nrm = np.cross(d, X)
    nrm /= np.linalg.norm(nrm)
    return w, dict(Q=Q, G=G, legs=(a, lx), straights=(start_st, end_st), ratios=r, ctrl=cp, min_r=1 / k.max(), k_peak_at=float(s[k.argmax()] / s[-1]),
                   spline_len=float(s[-1]), normal=nrm)
