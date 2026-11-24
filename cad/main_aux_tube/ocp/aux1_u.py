"""主管補助管 1(第 4 側、2026-11-24 やり直し)。

平面 Π: 第 4 の 1 階左下の枝管(valve4_knuckle_F1_225_twisted)の出口の中心を通る YZ 平面を、出口を正面(-Y 側、出口の外から)
見て反時計回りに ROT_DEG 回した面(回転軸 = 出口の軸 u。法線 n = Rot(u, ROT_DEG)·(1,0,0))。出口の軸 u は Π に乗る。
芯線: Π の上の開いた U 字。出口 E から直線 ST → 左右対称な 5 次ベジェ(両端の曲率 0 = G2)→ 直線 ST → 終点 F。
F は Π とベルの芯線の平面の交線の上(芯線はそこで止める)。左右対称: 曲線は弦 EF の垂直二等分線について対称で、
F での向きは tF = 2(u·c)c - u(c = 弦の向き)。変数は F の交線上の位置 t とベジェの a, b。
bb34 の L 字管と 1番管の間を通す: 隙間(表面)≥ GAP_REQ を守り、最小曲げ半径が最大になるよう差分進化で決める。
"""

from __future__ import annotations

import math

import numpy as np

ROT_DEG = 8.0  # 10 → 8(2026-11-24、外管との隙間を増やす)
ST = 5.0  # 両端の直線
GAP_REQ = 0.4  # 隙間(表面どうし)の下限
UP_MIN = 0.9  # 終点の向き tF の +Z 成分の下限(bb34 の L 字管と 1番管の間を通して、出口を +Z へ持ち上げる)
D = 12.0
OD = 12.8


def rot(v, axis, deg):
    k = axis / np.linalg.norm(axis)
    th = math.radians(deg)
    return v * math.cos(th) + np.cross(k, v) * math.sin(th) + k * (k @ v) * (1 - math.cos(th))


def plane_normal(u, deg=ROT_DEG):
    return rot(np.array([1.0, 0.0, 0.0]), u, deg)


def line_of(E, n, Pb, Nb):
    """Π(E, n)とベルの平面(Pb, Nb)の交線: (点, 向き)。点は E に最も近い点。"""
    d = np.cross(n, Nb)
    d /= np.linalg.norm(d)
    A = np.array([n, Nb, d])
    p = np.linalg.solve(A, np.array([n @ E, Nb @ Pb, d @ E]))
    return p, d


def ctrl(E, u, F, a, b, st=ST):
    c = (F - E) / np.linalg.norm(F - E)
    tF = 2 * (u @ c) * c - u
    P0, P5 = E + st * u, F - st * tF
    return np.array([P0, P0 + a * u, P0 + (a + b) * u, P5 - (a + b) * tF, P5 - a * tF, P5]), tF


def bezier(P, n=400):
    from math import comb

    t = np.linspace(0, 1, n)
    k = len(P) - 1
    Bn = lambda m, tt: np.array([comb(m, i) * tt**i * (1 - tt) ** (m - i) for i in range(m + 1)]).T  # noqa: E731
    f1 = Bn(k - 1, t) @ (k * np.diff(P, axis=0))
    f2 = Bn(k - 2, t) @ (k * (k - 1) * np.diff(P, n=2, axis=0))
    kap = np.linalg.norm(np.cross(f1, f2), axis=1) / np.linalg.norm(f1, axis=1) ** 3
    return Bn(k, t) @ P, kap


def points(E, u, F, tF, P, n=400):
    """芯線の点(直線 2 本 + ベジェ)。"""
    C, _ = bezier(P, n)
    s = np.linspace(0, 1, 12)[:, None]
    return np.vstack([E + s * (P[0] - E), C, P[5] + s * (F - P[5])])


def solve(E, u, n, Pb, Nb, tree, gap_req=GAP_REQ, up_min=UP_MIN, t_range=150.0, seed=0, y_min=None):
    """y_min: 終点 F の y の下限(1番管の末端の直線の軸 y。F を 1番管より +Y 側 = bb34 の L 字管との間に置く)。"""
    from scipy.optimize import differential_evolution

    p, d = line_of(E, n, Pb, Nb)
    t0 = float((E - p) @ d)

    def evaluate(v):
        t, a, b = v
        F = p + t * d
        P, tF = ctrl(E, u, F, a, b)
        C, kap = bezier(P, 300)
        pts = points(E, u, F, tF, P, 200)
        gap = float(tree.query(pts[3:])[0].min()) - OD / 2  # 出口の直後は枝管と接するので除く(点群に枝管は入れない)
        return F, P, tF, kap, gap

    def cost(v):
        F, P, tF, kap, gap = evaluate(v)
        return 100.0 * kap.max() + 3000.0 * max(0.0, gap_req - gap) + 3000.0 * max(0.0, up_min - float(tF[2])) + (0.0 if y_min is None else 300.0 * max(0.0, y_min - float(F[1])))

    bounds = [(t0 - t_range, t0 + t_range), (0.5, 80.0), (0.5, 80.0)]
    res = differential_evolution(cost, bounds, seed=seed, maxiter=200, popsize=40, tol=1e-10, polish=True)
    F, P, tF, kap, gap = evaluate(res.x)
    return dict(v=[float(x) for x in res.x], F=F, P=P, tF=tF, rmin=1.0 / kap.max(), gap=gap, line=(p, d), cost=float(res.fun))


def wire(E, F, P):
    from build123d import Edge, Vector, Wire

    return Wire([Edge.make_line(Vector(*E), Vector(*P[0])), Edge.make_bezier(*[Vector(*q) for q in P]), Edge.make_line(Vector(*P[5]), Vector(*F))])


# 試し(2026-11-24 ユーザー指示): Π の上に、直線 5 + 円弧 R30 + 直線 5 の管。片方を枝管の出口につなぎ、内角 100°(曲がり 80°)、もう一方は +Z 側へ向く。
ARC_R = 30.0
INNER_DEG = 110.0  # 100 → 110(2026-11-24)


def arc_pipe(E, u, n, r=ARC_R, inner_deg=INNER_DEG, st=ST):
    """戻り値: (Wire, 終点 F, 終点の向き tF, 円弧の中心 C)。曲がる向きは、終点の向きの +Z 成分が大きい方。"""
    from build123d import Edge, Vector, Wire

    turn = 180.0 - inner_deg
    best = None
    for sgn in (+1, -1):
        tF = rot(u, n, sgn * turn)
        if best is None or tF[2] > best[1][2]:
            best = (sgn, tF)
    sgn, tF = best
    m = np.cross(sgn * n, u)  # 曲がる側(u を sgn·n まわりに回す向き)
    m /= np.linalg.norm(m)
    P1 = E + st * u
    C = P1 + r * m
    th = math.radians(turn)
    P2 = C - r * (math.cos(th) * m - math.sin(th) * u)
    Pm = C - r * (math.cos(th / 2) * m - math.sin(th / 2) * u)
    F = P2 + st * tF
    w = Wire([Edge.make_line(Vector(*E), Vector(*P1)), Edge.make_three_point_arc(Vector(*P1), Vector(*Pm), Vector(*P2)), Edge.make_line(Vector(*P2), Vector(*F))])
    return w, F, tF, C


# ヒントによる形(2026-11-24 ユーザー): +X 側から見て(YZ に投影)、1番管の末端の直線の軸と bb34 の直管の軸は点に見える。
# その 2 点の中点を通り、第 4 の枝管側の軸(出口 E から u)となす内角が HINT_INNER の直線を考え、間を円弧で結ぶ。
# 枝管側の直線は ST(円弧の R はそれで決まる)。できた形を、接続軸(u)まわりに HINT_TILT 回す。終点はベルの芯線の平面との交点。
HINT_INNER = 90.0  # 120 → 90 → 80 → 90(2026-11-24、傾き 0 で探索して採用)
HINT_DY = 3.265  # 2 点の中点から、直線の通る点を +Y へずらす量(終点を 1番管から離す)。0 → 2.5(2026-11-24、bb34 L と 1番管の間の通り道へ) → 3.56(2026-11-24、探索 tools/aux1_search.py、傾き 0) → 3.265(内角 90)
HINT_EXT = 0.0  # 終点をベルの芯線の平面より先(+Z 側)へ延ばす長さ(2026-11-24: 上げてよい)
HINT_ST1 = 20.036  # 枝管側の直線(長くすると円弧の R が小さくなる)。5 → 20 → 12 → 20(2026-11-24、R を小さく) → 20.337(同) → 20.036(内角 90)
HINT_TILT = 0.0  # 8 → 0(2026-11-24。+ に倒すと 1番管に近づき 5° で接触、- は採らない → 0 に決定)
HINT_END_MIN = 5.0  # +Z 側の直線の最小長さ(ベルの平面が円弧の途中に来るときは、平面より上まで延ばす)
# 円弧の代わりの G2 スプライン(2026-11-24): 角 Q からの距離 (d0, d1, d2, d3) の点を 2 本の直線の上に左右対称に置いた 7 次ベジェ
# (制御点 Q-d0·u, Q-d1·u, Q-d2·u, Q-d3·u, Q+d3·d, Q+d2·d, Q+d1·d, Q+d0·d)。両端で 3 点が直線上にあるので端の曲率は 0(直線と G2)。
# None なら円弧。値は tools/aux1_search.py --g2 で決める。
HINT_G2 = None


def hint_pipe(E, u, yz1, yz2, Pb, Nb, inner=HINT_INNER, tilt=HINT_TILT, st=HINT_ST1, dy=HINT_DY, ext=HINT_EXT, g2="default"):
    """戻り値: (Wire, info)。yz1, yz2: 2 本の軸の YZ の点。g2: (d0, d1, d2, d3) なら円弧の代わりに G2 スプライン(st は使わない)。"""
    if isinstance(g2, str):
        g2 = HINT_G2
    from build123d import Edge, Vector, Wire

    M2 = 0.5 * (np.asarray(yz1, float) + np.asarray(yz2, float)) + np.array([dy, 0.0])
    u2 = np.array([u[1], u[2]]) / np.hypot(u[1], u[2])
    turn = math.radians(180.0 - inner)
    best = None
    for sgn in (+1, -1):  # +Z 側へ曲がる方
        c, s_ = math.cos(sgn * turn), math.sin(sgn * turn)
        d2 = np.array([c * u2[0] - s_ * u2[1], s_ * u2[0] + c * u2[1]])
        if best is None or d2[1] > best[1][1]:
            best = (sgn, d2)
    sgn, d2 = best
    e2 = np.array([E[1], E[2]])
    s, t = np.linalg.solve(np.column_stack([u2, -d2]), M2 - e2)  # 角 Q = E + s·u = M + t·d2
    Q2 = e2 + s * u2
    T = s - st  # 接線の長さ
    r = T / math.tan(turn / 2)
    to3 = lambda p: np.array([E[0], p[0], p[1]])  # noqa: E731  YZ 平面(x = E.x)の点
    # 回転(接続軸まわり)
    def R(p):
        return E + rot(p - E, u, tilt)

    d3 = R(E + np.array([0.0, d2[0], d2[1]])) - E
    d3 /= np.linalg.norm(d3)
    P1 = E + st * u
    Q3 = R(to3(Q2))
    P2 = Q3 + T * d3
    nrm = rot(np.array([1.0, 0.0, 0.0]), u, tilt)
    m = np.cross(np.cross(u, d3), u)
    m /= np.linalg.norm(m)
    C = P1 + r * m
    Pm = C + r * ((Q3 - C) / np.linalg.norm(Q3 - C))
    # 終点: 2 本目の直線とベルの平面の交点
    k = max(float((Pb - P2) @ Nb) / float(d3 @ Nb) + ext, HINT_END_MIN)
    F = P2 + k * d3
    if g2 is not None:
        d0, d1, d2_, d3_ = (float(v) for v in g2)
        kq = max(float((Pb - Q3) @ Nb) / float(d3 @ Nb) + ext, d0 + HINT_END_MIN)  # Q から終点まで
        F = Q3 + kq * d3
        A, B = Q3 - d0 * u, Q3 + d0 * d3
        cp = [Q3 - d * u for d in (d0, d1, d2_, d3_)] + [Q3 + d * d3 for d in (d3_, d2_, d1, d0)]
        w = Wire([Edge.make_line(Vector(*E), Vector(*A)), Edge.make_bezier(*[Vector(*c) for c in cp]), Edge.make_line(Vector(*B), Vector(*F))])
        return w, dict(M=M2, Q=Q3, r=r, d=d3, F=F, end_straight=kq - d0, start_straight=s - d0, normal=nrm, s=s, ctrl=np.array(cp))
    w = Wire([Edge.make_line(Vector(*E), Vector(*P1)), Edge.make_three_point_arc(Vector(*P1), Vector(*Pm), Vector(*P2)), Edge.make_line(Vector(*P2), Vector(*F))])
    return w, dict(M=M2, Q=Q3, r=r, d=d3, F=F, end_straight=k, start_straight=st, normal=nrm, s=s)
