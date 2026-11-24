"""吹込管の芯線を、端点を固定した作図で作る(2026-11-24、試し。管(外形)はまだ作らない)。

作図(すべて吹込管平面の中。平面と両端は mouthpipe.py の今の設計のキャッシュから取り、固定):
1. ベルの曲げ内側の円(曲げに使う円板の縁、φ275)を吹込管平面へ法線方向に投影する(平面の中では楕円)。
2. それを平面の中で外側へ OFFSET_OUT ずらす(オフセット曲線)。
3. 入口 M からオフセット曲線へ接線を引く(上側に接する方)。接点からオフセット曲線を x = FOLLOW_X_END まで沿わせる。
4. 太い端から -X の直線を x = THICK_X_END まで(直線は x >= 0 だけ)。
5. 4 の端と 3 の x = FOLLOW_X_END の端を、G2 の円弧的な曲線(7 次ベジェ)でつなぐ。
   直線側は曲率 0、オフセット曲線側はその曲率に合わせる。曲率の変化と最大を小さく、曲がりは一方向(時計回り)。

    uv run python cad/mouthpipe/ocp/mouthpipe_try.py [--follow-x-end -35] [--thick-x-end 0] [--offset-out 6]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mouthpipe as MP  # noqa: E402

FOLLOW_X_END = -35.0  # オフセット曲線に沿う区間の左端の x(後で変えるかも)
THICK_X_END = 0.0  # 太端側の直線の左端の x(直線は x >= 0 だけ)
OFFSET_OUT = 6.0  # φ275 の投影を外側へずらす量
DEG = 7  # つなぎのベジェの次数


def arg(k, d):
    return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def fixed_ends(M, T):
    """mouthpipe.py の今の設計(キャッシュ)から、太い端 T0・入口 Mp・平面の法線。"""
    import shape_cache as SC

    bd = MP.bell_data(M)
    psi = SC.memo_value("mouthpipe_psi", [round(float(v), 6) for v in (*T, *M.ravel())] + [MP.CLEAR, MP.LEFT_X, MP.LEN_XY, MP.INNER_DEG],
                        MP.__file__, lambda: MP.solve_psi(bd, T)[0])
    d = SC.memo_value("mouthpipe_design", [round(float(v), 6) for v in (*T, *M.ravel(), psi)] + [MP.LEFT_X, MP.LEN_XY, MP.INNER_DEG],
                      MP.__file__, lambda: MP.design(bd, T, psi))
    X = np.array([1.0, 0.0, 0.0])
    T0 = d["A"] + d["x"][0] * X
    nrm = np.cross(X, d["en"]["Yp"])
    return T0, d["en"]["M"], nrm / np.linalg.norm(nrm), psi


class OffsetEllipse:
    """平面の 2 次元座標で、p(φ) = C + A cos φ + B sin φ(投影した円)を外側へ dist ずらした曲線。φ の向きは 3 次元の円と同じ。"""

    def __init__(self, C, A, B, dist):
        self.C, self.A, self.B, self.d = C, A, B, dist
        self.s = 1.0 if A[0] * B[1] - A[1] * B[0] > 0 else -1.0  # φ が増える向きが反時計回りなら +1

    def p1(self, f):
        return -np.outer(np.sin(f), self.A) + np.outer(np.cos(f), self.B)

    def n(self, f):  # 外向きの単位法線
        t = self.p1(f)
        t /= np.linalg.norm(t, axis=1)[:, None]
        return self.s * np.c_[t[:, 1], -t[:, 0]]

    def pos(self, f):
        f = np.atleast_1d(f)
        return self.C + np.outer(np.cos(f), self.A) + np.outer(np.sin(f), self.B) + self.d * self.n(f)

    def tan(self, f):  # 単位接線(φ が増える向き)
        t = self.p1(np.atleast_1d(f))
        return t / np.linalg.norm(t, axis=1)[:, None]

    def kappa(self, f):  # オフセット曲線の曲率の大きさ(凸、外側へずらすので 1/(1/κ + d))
        f = np.atleast_1d(f)
        p1 = self.p1(f)
        p2 = -np.outer(np.cos(f), self.A) - np.outer(np.sin(f), self.B)
        k = np.abs(p1[:, 0] * p2[:, 1] - p1[:, 1] * p2[:, 0]) / np.linalg.norm(p1, axis=1) ** 3
        return k / (1 + self.d * k)


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def construct(M, T0, Mp, nrm, follow_x, thick_x, off):
    """作図 1〜5。戻り値は、平面の座標系(原点 T0、e1 = X、e2)と、各部の 2 次元の値。"""
    from scipy.optimize import brentq

    from make_centerline import geometry

    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.cross(nrm, e1)
    e2 *= np.sign(e2[1]) / np.linalg.norm(e2)
    to2 = lambda p: np.array([(p - T0) @ e1, (p - T0) @ e2])  # noqa: E731
    R3, t3 = M[:3, :3], M[:3, 3]
    g = geometry()
    c3 = R3 @ np.array([g["c"][0], g["c"][1], 0.0]) + t3
    a3, b3 = R3 @ np.array([g["ri"], 0, 0]), R3 @ np.array([0, g["ri"], 0])
    oe = OffsetEllipse(to2(c3), np.array([a3 @ e1, a3 @ e2]), np.array([b3 @ e1, b3 @ e2]), off)
    M2 = to2(Mp)
    # 3. 接点: (M - o(φ)) × t(φ) = 0。φ を細かく調べて符号の変わる所を brentq で。上側(y 最大)の解
    cr = lambda f: float(cross2(oe.tan(f)[0], M2 - oe.pos(f)[0]))  # noqa: E731
    fs = np.linspace(0, 2 * np.pi, 3601)
    v = np.array([cr(f) for f in fs])
    roots = [brentq(cr, fs[k], fs[k + 1], xtol=1e-14) for k in np.where(np.sign(v[:-1]) != np.sign(v[1:]))[0]]
    ft = max(roots, key=lambda f: oe.pos(f)[0, 1])
    Pt = oe.pos(ft)[0]
    u = (Pt - M2) / np.linalg.norm(Pt - M2)  # 入口 → 接点
    sgn = 1.0 if oe.tan(ft)[0] @ u > 0 else -1.0  # 入口から進むとき φ が増えるか
    # x = follow_x の φ(接点から入口と反対へ進んで最初に x が follow_x になる所)
    fsweep = ft + sgn * np.linspace(0, np.pi, 3601)
    xs = oe.pos(fsweep)[:, 0] + T0[0]
    k = int(np.argmax(xs < follow_x)) if (xs < follow_x).any() else None
    if not k:
        raise ValueError(f"offset curve does not reach x = {follow_x} from the tangent point")
    fe = brentq(lambda f: oe.pos(f)[0, 0] + T0[0] - follow_x, fsweep[k - 1], fsweep[k], xtol=1e-14)
    # 4. 太端側の直線の端(平面の座標で (thick_x - T0x, 0))
    S2 = np.array([thick_x - T0[0], 0.0])
    # 5. つなぎ: S2 から向き -X、曲率 0 → E2 = o(fe)、向き(太端 → 入口)= -sgn·t、曲率 κ(fe)、中心は内側(-n)
    E2 = oe.pos(fe)[0]
    de = -sgn * oe.tan(fe)[0]
    ne = -oe.n(fe)[0]
    kap = float(oe.kappa(fe)[0])
    return dict(e1=e1, e2=e2, oe=oe, M2=M2, ft=ft, fe=fe, Pt=Pt, u=u, sgn=sgn, S2=S2, E2=E2, de=de, ne=ne, kap=kap)


def join_ctrl(x, S, E, de, ne, kap, m=DEG):
    """始点 S、向き -X、曲率 0(P0・P1・P2 が直線上)。終点 E、向き de、曲率 kap(中心は ne の側)。
    x = (a1, a2, b, c, p3u, p3v, p4u, p4v)(P3・P4 は S からの相対)。P6 = E - b·de、P5 = P6 - c·de + h·ne、h = kap·m·b²/(m - 1)。"""
    a1, a2, b, c, p3u, p3v, p4u, p4v = x
    P6 = E - b * de
    h = kap * m * b * b / (m - 1)
    return np.array([S, S + [-a1, 0.0], S + [-a1 - a2, 0.0], S + [p3u, p3v], S + [p4u, p4v], P6 - c * de + h * ne, P6, E])


def fit_join(S, E, de, ne, kap):
    """円弧的: 曲率の変化(∫κ'²)と最大を小さく、曲がりは一方向(時計回り)だけ。差分進化 + 仕上げ。"""
    from scipy.optimize import differential_evolution

    def cost(x):
        cp = join_ctrl(x, S, E, de, ne, kap)
        s, k = MP.curv2(cp, 300)
        dk = np.diff(k) / np.maximum(np.diff(s), 1e-9)
        f = 100 * np.abs(k).max() + 30 * float(np.sum(dk**2 * np.diff(s)))
        f += 1e6 * max(float(k.max()), 0.0)  # 反時計回りは不可(わずかでも)
        return f

    H = float(np.linalg.norm(E - S))
    bounds = [(1.0, H), (1.0, H), (1.0, H), (1.0, H), (-2 * H, 0.0), (-0.5 * H, 1.5 * H), (-2 * H, 0.0), (-0.5 * H, 1.5 * H)]
    r = differential_evolution(cost, bounds, seed=0, popsize=20, maxiter=600, tol=1e-9, polish=True, init="sobol")
    return r.x


def edge_kappa(e, u):
    """エッジの u(0..1)での曲率(build123d、3 次元)。"""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepLProp import BRepLProp_CLProps

    c = BRepAdaptor_Curve(e.wrapped)
    p = c.FirstParameter() + u * (c.LastParameter() - c.FirstParameter())
    pr = BRepLProp_CLProps(c, p, 2, 1e-9)
    return pr.Curvature()


def hook(M, branch, others):
    import main_slide as MSL
    import shape_cache as SC
    from build123d import Edge, Vector, Wire

    branch, p0, n0, c0 = MSL.hook(M, branch, others)
    b2 = dict(zip(n0, p0))["main_slide_inner_tube2"].bounding_box(optimal=False)
    T = np.array([b2.min.X - MP.GAP, 0.5 * (b2.min.Y + b2.max.Y), 0.5 * (b2.min.Z + b2.max.Z)])
    T0, Mp, nrm, psi = fixed_ends(M, T)
    fx, tx, off = arg("--follow-x-end", FOLLOW_X_END), arg("--thick-x-end", THICK_X_END), arg("--offset-out", OFFSET_OUT)
    c = construct(M, T0, Mp, nrm, fx, tx, off)
    to3 = lambda q: T0 + np.asarray(q)[..., 0, None] * c["e1"] + np.asarray(q)[..., 1, None] * c["e2"]  # noqa: E731
    key = [round(float(v), 6) for v in (*c["S2"], *c["E2"], *c["de"], *c["ne"], c["kap"])]
    xb = SC.memo_value("mouthpipe_try_join", key, __file__, lambda: fit_join(c["S2"], c["E2"], c["de"], c["ne"], c["kap"]))
    cp2 = join_ctrl(xb, c["S2"], c["E2"], c["de"], c["ne"], c["kap"])

    # 芯線(太い端 → 入口): 太端の直線 + つなぎ(ベジェ) + オフセット曲線(x = fx → 接点) + 入口の直線
    oe = c["oe"]
    fseg = np.linspace(c["fe"], c["ft"], max(40, int(abs(c["ft"] - c["fe"]) * 140 / (2 * math.pi) * 20)))
    Q = to3(oe.pos(fseg))
    tq = oe.tan(fseg) * (-c["sgn"])
    t3 = lambda t: t[0] * c["e1"] + t[1] * c["e2"]  # noqa: E731
    e_thick = Edge.make_line(Vector(*T0), Vector(*to3(c["S2"])))
    e_join = Edge.make_bezier(*[Vector(*q) for q in to3(cp2)])
    e_follow = Edge.make_spline([Vector(*q) for q in Q], tangents=[Vector(*t3(tq[0])), Vector(*t3(tq[-1]))])
    e_entry = Edge.make_line(Vector(*Q[-1]), Vector(*Mp))
    w = Wire([e_thick, e_join, e_follow, e_entry])

    s, kj = MP.curv2(cp2)
    pts = MP.bez(cp2, np.linspace(0, 1, 600))
    Pt3, Pe3 = to3(c["Pt"]), to3(c["E2"])
    ang = math.degrees(math.atan2(-c["u"][1], -c["u"][0]))
    print(f"mouthpipe (fixed ends): thick end {T0.round(3).tolist()}, entry M {Mp.round(3).tolist()}, psi {psi:.3f} deg (from the cached design); no tube")
    print(f"offset {off:g} of the projected D275 bell inner circle: tangent point from M {Pt3.round(3).tolist()} (entry straight {np.linalg.norm(Pt3 - Mp):.3f}, "
          f"XY angle to X {math.degrees(math.atan2(Pt3[1] - Mp[1], Pt3[0] - Mp[0])) - 180:.3f} deg, in-plane {ang:.3f}); follows to x = {fx:g} {Pe3.round(3).tolist()} "
          f"({e_follow.length:.3f}, R {1 / c['oe'].kappa(c['fe'])[0]:.3f} .. {1 / c['oe'].kappa(c['ft'])[0]:.3f})")
    print(f"thick-end straight {T0.round(3).tolist()} -> {to3(c['S2']).round(3).tolist()} ({e_thick.length:.3f})")
    print(f"G2 join (deg-{DEG} Bezier) {e_join.length:.3f}: min R {1 / np.abs(kj).max():.2f}, curvature {'one sign (cw)' if (kj <= 1e-9).all() else 'MIXED SIGN'}, "
          f"leftmost x {(T0[0] + pts[:, 0]).min():.2f}, lowest-y-to-highest {(to3(pts)[:, 1]).min():.2f}..{(to3(pts)[:, 1]).max():.2f}")
    print(f"joints (curvature on the edges): thick|join {edge_kappa(e_thick, 1):.2e}|{edge_kappa(e_join, 0):.2e}; "
          f"join|follow {edge_kappa(e_join, 1):.6f}|{edge_kappa(e_follow, 0):.6f} (target {c['kap']:.6f}); follow|entry {edge_kappa(e_follow, 1):.6f}|0 (G1 here)")
    tan_err = [math.degrees(math.acos(min(1.0, abs(a.tangent_at(1).dot(b.tangent_at(0))) / (a.tangent_at(1).length * b.tangent_at(0).length))))
               for a, b in ((e_thick, e_join), (e_join, e_follow), (e_follow, e_entry))]
    print(f"tangent mismatch at the joints {np.round(tan_err, 5).tolist()} deg; plane flatness {np.abs([(Vector(*q) - Vector(*T0)).dot(Vector(*nrm)) for q in (to3(pts))]).max():.1e}")
    print(f"centerline: {e_thick.length:.3f} + {e_join.length:.3f} + {e_follow.length:.3f} + {e_entry.length:.3f} = {w.length:.3f}")
    return branch, p0 + [w], n0 + ["mouthpipe_centerline"], c0 + ["#00c0ff"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
