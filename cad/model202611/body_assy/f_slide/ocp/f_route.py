"""F管抜差の中管 1 → 第 3 植込の F 側(1 階、z = 17)左上(135°)の枝管(valve3_tube_F1_135)の経路(2026-11-26、芯線だけ)。座標は管体組立のワールド。

- 中管側: 中管 1 の -X の端面から GAP 離した点 S(中管 1 の軸の上)から、-X へまっすぐ x = X_END まで(暫定)。
- 枝管側: 枝管の端面の中心 E から、外向きの軸に沿ってまっすぐ BR_ST。
- 中間部の作図(2026-11-26): ベル平面(ベルの芯線の平面)の中で、ベルの曲げの内側の外面の曲線(branch1_route と同じ: 芯線から
  進む向きの右の法線の側へ D/2 + 板厚)を、さらに BELL_OFF = 1.4 + 6.4(隙間 + 外半径)だけ内側(右の法線の側)へオフセットする。
  ワールドで y = Y_LOW .. Y_HIGH、x < 0 の部分だけ描く(最初は 0 .. 1番管の横の直線の芯線の y → [-50, 0] → [-50, 10] → [-50, 0]、2026-11-26)。
- つなぎ 1: 中管側の直線の端(x = X_END)→ オフセット曲線の y = Y_LOW の端を、G2 の 5 次ベジェで。
- つなぎ 2: オフセット曲線の y = Y_HIGH の端 → 枝管側の直線の端を、G2 の 5 次ベジェで。
- 管: 外径 12.8・内径 12.0 を芯線に沿って掃引。

    uv run python cad/model202611/body_assy/f_slide/ocp/f_route.py [--gap 1] [--x-end -60] [--br-st 6] [--bell-off 7.8] [--y-low -40] [--b1-clear 6.6] [--y-high 0] [--w-xy 5] [--check]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

GAP = 1.0  # 中管 1 の -X の端面から芯線の始点まで
X_END = -60.0  # 中管側の直線の終わりの x(暫定)。-50 → -60(2026-11-26)
BR_ST = 6.0  # 枝管の端面から外向きに出す直線の長さ。8 → 6(2026-11-26)
Y_LOW, Y_HIGH = -40.0, 0.0  # 中間部の作図の曲線の y の範囲(ワールド)。Y_HIGH 10 → 0、Y_LOW -50 → -40(2026-11-26、つなぎ 1 を 1番管から離す)
B1_CLEAR = 6.6  # つなぎ 1 の芯線から 1番管(bell03_branch1_wall)の外面までの最小距離(2026-11-26 ユーザー指示)
BELL_OFF = 1.4 + 6.4  # ベルの曲げ内側の外面から(隙間 1.4 + 管の外半径 6.4)
W_XY = 5.0  # (1 → 5)つなぎ 2 で、XY へ投影した曲線の最大曲率を小さくする重み(2026-11-26、上から見て y の頂点が尖らないように)
EXT = 300  # オフセット曲線のスプラインを範囲の外へ延ばす点の数(bell_inner_offset の点列の間隔で)
TUBE_OD, TUBE_ID = 12.8, 12.0  # 経路の管の外径・内径
BRANCH = "valve3_tube_F1_135"  # 第 3 の 1 階・左上(ワールドの孔軸 135°、z = 17)


def arg(k, d):
    return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def branch_exit():
    """枝管の端面の中心と外向きの軸(valve_row: 植込み中心から孔軸の向きに STRAIGHT_TUBE_END、高さ z)。"""
    import valve_row as VR

    old, ang, new, z = next(t for t in VR.STRAIGHT_TUBES["valve3"] if t[2] == "tube_F1_135")
    u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
    return np.array([VR.VALVES["valve3"], 0.0, z]) + VR.STRAIGHT_TUBE_END * u, u


def bell_inner_offset(off, n=8401):
    """ベル平面(設計の z = 0)の中で、ベルの曲げ内側の外面の曲線を、その法線の内側へ off ずらした点列(2D、設計の座標)。"""
    import branch1_route as BR1

    g, total, D = BR1._bell()
    lb = np.linspace(0.0, total, n)
    pb, tb = BR1.bell_point(g, lb)
    nb = np.column_stack([tb[:, 1], -tb[:, 0]])  # 進む向きの右(直管部では +x 側)= 曲げの内側
    surf = pb + nb * (D(lb) / 2 + BR1.WALL)[:, None]
    ds = np.gradient(surf, axis=0)
    ds /= np.linalg.norm(ds, axis=1)[:, None]
    ns = np.column_stack([ds[:, 1], -ds[:, 0]])  # 外面の曲線の右の法線(同じく曲げの内側)
    return surf + off * ns


def hook(M, branch, others):
    import branch2_l as B2
    import f_slide_inner as FS
    from build123d import Edge, Vector

    branch, p0, n0, c0 = FS.hook(M, branch, others)
    d = dict(list(others) + list(zip(n0, p0)))
    gap, x_end, br_st = arg("--gap", GAP), arg("--x-end", X_END), arg("--br-st", BR_ST)

    # 中管側: 中管 1 の軸(y・z は外形の中心)、-X の端面の x - gap から x_end まで
    bb = d["f_slide_inner_tube1"].bounding_box(optimal=False)
    S = np.array([bb.min.X - gap, (bb.min.Y + bb.max.Y) / 2, (bb.min.Z + bb.max.Z) / 2])
    S1 = np.array([x_end, S[1], S[2]])
    e_in = Edge.make_line(Vector(*S), Vector(*S1))

    # 枝管側: 端面の中心 E から外向き u に br_st
    E, u = branch_exit()
    E1 = E + br_st * u
    e_br = Edge.make_line(Vector(*E), Vector(*E1))
    # 確かめ: 枝管の形の上で E から最も近い点までの距離(端面の中心なら外半径・内半径の円の上、≈ 6.0〜6.4)
    tb = d[BRANCH].bounding_box(optimal=False)
    print(f"F route (centerlines only): inner-tube side S {S.round(3).tolist()} -> {S1.round(3).tolist()} ({e_in.length:.3f}, dir -X); "
          f"branch {BRANCH} exit E {E.round(3).tolist()} (axis {u.round(4).tolist()}) -> {E1.round(3).tolist()} ({e_br.length:.3f}); "
          f"branch bbox x {tb.min.X:.3f}..{tb.max.X:.3f} y {tb.min.Y:.3f}..{tb.max.Y:.3f} z {tb.min.Z:.3f}..{tb.max.Z:.3f}")
    gapv = E1 - S1
    print(f"between the two straight ends: {gapv.round(3).tolist()} (distance {np.linalg.norm(gapv):.3f})")
    # 中間部の作図: ベルの曲げ内側の外面を BELL_OFF ずらした曲線(ワールドで y = Y_LOW .. Y_HIGH、x < 0)
    off = arg("--bell-off", BELL_OFF)
    q2 = bell_inner_offset(off)
    Mw = np.asarray(M, float)
    qw = q2 @ Mw[:3, :2].T + Mw[:3, 3]  # 設計の (x, y, 0) → ワールド
    y_b1, y_hi = arg("--y-low", Y_LOW), arg("--y-high", Y_HIGH)
    m = (qw[:, 1] <= y_hi) & (qw[:, 1] >= y_b1) & (qw[:, 0] < 0.0)
    idx = np.flatnonzero(m)
    runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
    run = max(runs, key=len)
    pts = qw[run]
    # スプラインは範囲の外へ少し(各 EXT 点)延ばして作り、範囲の端で切る(端の曲率を確かに取るため)
    i0, i1 = max(0, run[0] - EXT), min(len(qw) - 1, run[-1] + EXT)
    step = max(1, (run[-1] - run[0]) // 200)
    nodes = sorted(set(range(i0, i1 + 1, step)) | {run[0], run[-1], i1})
    e_ext = Edge.make_spline([Vector(*qw[i]) for i in nodes])
    e_mid = e_ext.trim(Vector(*qw[run[0]]), Vector(*qw[run[-1]]))
    print(f"bell inner offset {off:g} (bell plane): world y {y_b1:g} .. {y_hi:g}, x < 0: {len(runs)} run(s), "
          f"from {pts[0].round(3).tolist()} to {pts[-1].round(3).tolist()} ({e_mid.length:.3f}), x {pts[:, 0].min():.3f}..{pts[:, 0].max():.3f}")

    # つなぎ(2026-11-26): 中管側の直線の端 S1(向き -X、曲率 0)→ オフセット曲線の y = Y_LOW の端(向き・曲率ベクトルを合わせる)。G2 の 5 次ベジェ
    B, t1, K = frame(e_mid, 0.0)
    t0 = np.array([-1.0, 0.0, 0.0])
    b1_clear = arg("--b1-clear", B1_CLEAR)
    cp, info = memo_join("f_route_join1", (S1, t0, np.zeros(3), B, t1, K, b1_clear),
                         lambda: g2_join(S1, t0, np.zeros(3), B, t1, K, obstacles=[(surface_tree(branch, S1, B), b1_clear + 0.1)]))
    e_j = Edge.make_bezier(*[Vector(*q) for q in cp])
    Bj, tj, Kj = frame(e_j, 1.0)
    A0, ta, Ka = frame(e_j, 0.0)
    print(f"join (straight x = {x_end:g} -> offset curve y = {y_b1:g}): quintic Bezier {e_j.length:.3f}, min R {info['rmin']:.2f}, "
          f"curvature 0 -> {np.linalg.norm(K):.6f} (1/R {1 / np.linalg.norm(K):.3f}); legs a {info['a'].round(3).tolist()} b {info['b'].round(3).tolist()}")
    print(f"  G2 check: start curvature {np.linalg.norm(Ka):.2e}, tangent {np.degrees(np.arccos(min(1, ta @ t0))):.2e} deg; "
          f"end position {np.linalg.norm(Bj - B):.1e}, tangent {np.degrees(np.arccos(min(1, tj @ t1))):.2e} deg, curvature vector diff {np.linalg.norm(Kj - K):.2e}")
    print(f"  join to bell wall {e_j.distance_to(d['bell03_bell_wall']):.3f} (centerline; tube outer radius 6.4)")
    d_b1 = e_j.distance_to(branch)
    print(f"  join to branch1 (bell03_branch1_wall) {d_b1:.3f} (required >= {b1_clear:g}: {'OK' if d_b1 >= b1_clear else 'NG'})")

    # つなぎ 2(2026-11-26): オフセット曲線の y = Y_HIGH の端(向き・曲率ベクトル)→ 枝管側の直線の端 E1(枝管へ入る向き -u、曲率 0)
    C, tc, Kc = frame(e_mid, 1.0)
    w_xy = arg("--w-xy", W_XY)
    cp2, info2 = memo_join("f_route_join2", (C, tc, Kc, E1, -u, w_xy), lambda: g2_join(C, tc, Kc, E1, -u, np.zeros(3), w_xy=w_xy))
    e_j2 = Edge.make_bezier(*[Vector(*q) for q in cp2])
    C2, tc2, Kc2 = frame(e_j2, 0.0)
    D2, td2, Kd2 = frame(e_j2, 1.0)
    print(f"join 2 (offset curve y = {y_hi:g} -> branch straight end): quintic Bezier {e_j2.length:.3f}, min R {info2['rmin']:.2f}, "
          f"curvature {np.linalg.norm(Kc):.6f} (1/R {1 / np.linalg.norm(Kc):.3f}) -> 0; legs a {info2['a'].round(3).tolist()} b {info2['b'].round(3).tolist()}")
    print(f"  G2 check: start position {np.linalg.norm(C2 - C):.1e}, tangent {np.degrees(np.arccos(min(1, tc2 @ tc))):.2e} deg, curvature vector diff {np.linalg.norm(Kc2 - Kc):.2e}; "
          f"end position {np.linalg.norm(D2 - E1):.1e}, tangent {np.degrees(np.arccos(min(1, td2 @ -u))):.2e} deg, curvature {np.linalg.norm(Kd2):.2e}")
    pj = bez(cp2, np.linspace(0, 1, 2001))
    kxy = curv3(np.column_stack([pj[:, 0], pj[:, 1], np.zeros(len(pj))]))[2:-2]
    iy = int(np.argmax(pj[2:-2, 1]))
    print(f"  XY projection: min R {1 / kxy.max():.2f} at {pj[2 + int(np.argmax(kxy)), :2].round(2).tolist()}; at the y apex {pj[2 + iy, :2].round(2).tolist()} R {1 / kxy[iy]:.2f}")
    print(f"  join 2 to bell wall {e_j2.distance_to(d['bell03_bell_wall']):.3f} (centerline; tube outer radius 6.4)")
    total = e_in.length + e_j.length + e_mid.length + e_j2.length + e_br.length
    for nm, e in (("inner straight", e_in), ("join 1", e_j), ("bell offset", e_mid), ("join 2", e_j2), ("branch straight", e_br)):
        print(f"  {nm}: to branch1 {e.distance_to(branch):.3f}, to bell {e.distance_to(d['bell03_bell_wall']):.3f}")
    print(f"F route centerline: {e_in.length:.3f} + {e_j.length:.3f} + {e_mid.length:.3f} + {e_j2.length:.3f} + {e_br.length:.3f} = {total:.3f}")
    # 管(2026-11-26): 外径 TUBE_OD・内径 TUBE_ID を芯線に沿って掃引(辺ごと、branch2_u.const_d_tube)。枝管側の直線は E1 → E の向きにする
    import branch2_u as U
    from build123d import Wire

    w = Wire([e_in, e_j, e_mid, e_j2, Edge.make_line(Vector(*E1), Vector(*E))])
    from shape_cache import cached

    key = [np.round(np.array([[v.X, v.Y, v.Z] for v in w.vertices()]), 9).tolist(), round(w.length, 9), TUBE_OD, TUBE_ID]
    tube = cached("f_route_tube", key, __file__, lambda: U.const_d_tube(w, TUBE_ID, (TUBE_OD - TUBE_ID) / 2))
    vol = sum(x.volume for x in tube.solids())
    vexp = np.pi / 4 * (TUBE_OD**2 - TUBE_ID**2) * w.length
    print(f"F route tube D {TUBE_ID:g}/{TUBE_OD:g}: valid {tube.is_valid}, {len(tube.solids())} solids, volume {vol:.2f} (expected {vexp:.2f}, {100 * (vol / vexp - 1):+.3f}%), "
          f"centerline {w.length:.3f}")
    print("clearance (F route tube):")
    B2.report_clearance(tube, others + [("bell03_branch1_wall", branch)])
    return (branch, p0 + [tube, w, e_mid],
            n0 + ["f_route_wall", "f_route_centerline", "f_route_bell_offset"],
            c0 + ["#40c040", "#ff2020", "#ff80ff"])


def memo_join(tag, params, fn):
    """g2_join の結果(制御点と情報)を、入力と(import をたどった)ソースが同じなら、ディスクから読む。"""
    from shape_cache import memo_value

    key = [np.round(np.asarray(q, float), 9).tolist() for q in params]
    return memo_value(tag, key, Path(__file__), fn)


def surface_tree(shape, A, B, margin=60.0):
    """shape の表面の点群(メッシュの頂点、A・B を囲む箱 + margin の中だけ)の cKDTree。"""
    from scipy.spatial import cKDTree

    v, _ = shape.tessellate(0.01, 0.05)
    P = np.array([(q.X, q.Y, q.Z) for q in v])
    lo, hi = np.minimum(A, B) - margin, np.maximum(A, B) + margin
    return cKDTree(P[((P >= lo) & (P <= hi)).all(axis=1)])


def frame(e, u):
    """エッジの u(0 または 1)での位置・単位接線・曲率ベクトル(κ·主法線)。"""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepLProp import BRepLProp_CLProps
    from OCP.gp import gp_Dir, gp_Pnt

    c = BRepAdaptor_Curve(e.wrapped)
    t = c.FirstParameter() + u * (c.LastParameter() - c.FirstParameter())
    pr = BRepLProp_CLProps(c, t, 2, 1e-9)
    p, tg, nn = gp_Pnt(), gp_Dir(), gp_Dir()
    p = pr.Value()
    pr.Tangent(tg)
    k = pr.Curvature()
    K = np.zeros(3)
    if k > 1e-12:
        pr.Normal(nn)
        K = k * np.array([nn.X(), nn.Y(), nn.Z()])
    return np.array([p.X(), p.Y(), p.Z()]), np.array([tg.X(), tg.Y(), tg.Z()]), K


def bez(cp, s):
    from math import comb

    n = len(cp) - 1
    s = np.atleast_1d(s)[:, None]
    return sum(comb(n, i) * s**i * (1 - s) ** (n - i) * cp[i] for i in range(n + 1))


def curv3(p):
    d1 = np.gradient(p, axis=0)
    d2 = np.gradient(d1, axis=0)
    return np.linalg.norm(np.cross(d1, d2), axis=1) / np.linalg.norm(d1, axis=1) ** 3


def g2_join(A, t0, K0, B, t1, K1, n=401, w_xy=0.0, obstacles=()):
    """5 次ベジェ: A(向き t0、曲率ベクトル K0)→ B(向き t1、曲率ベクトル K1)。曲率 0 の端は K = 0。
    P1 = A + a1·t0、P2 = P1 + a2·t0 + 1.25·a1²·K0、P4 = B - b1·t1、P3 = P4 - b2·t1 + 1.25·b1²·K1(端の曲率ベクトルが K0・K1 に一致)。
    a1・a2・b1・b2 は、曲率の変化(Σ(dκ)²)と最大曲率が小さくなるように決める。w_xy > 0 なら、XY 平面へ投影した曲線の最大曲率も小さくする。
    obstacles: (cKDTree(表面の点群), 最小距離) の並び。芯線がその距離より近づかないように(罰則)。"""
    from scipy.optimize import minimize

    L0 = np.linalg.norm(B - A)
    s = np.linspace(0, 1, n)

    def ctrl(x):
        a1, a2, b1, b2 = np.exp(x) * L0
        P1 = A + a1 * t0
        P2 = P1 + a2 * t0 + 1.25 * a1**2 * K0
        P4 = B - b1 * t1
        P3 = P4 - b2 * t1 + 1.25 * b1**2 * K1
        return np.array([A, P1, P2, P3, P4, B])

    def f(x):
        p = bez(ctrl(x), s)
        k = curv3(p)[2:-2]
        ds = np.linalg.norm(np.diff(p, axis=0), axis=1).sum() / n
        val = float((np.diff(k) ** 2).sum() / ds * L0**3 + 0.1 * (k.max() * L0) ** 2)
        if w_xy > 0:
            kxy = curv3(np.column_stack([p[:, 0], p[:, 1], np.zeros(len(p))]))[2:-2]
            val += w_xy * (kxy.max() * L0) ** 2
        for tree, dmin in obstacles:
            val += 1e3 * max(0.0, dmin - float(tree.query(p)[0].min())) ** 2
        return val

    best = min((minimize(f, np.log(np.array(x0)), method="Nelder-Mead", options=dict(maxiter=4000, xatol=1e-6, fatol=1e-10))
                for x0 in [(0.2, 0.15, 0.2, 0.15), (0.3, 0.1, 0.3, 0.1), (0.1, 0.2, 0.1, 0.2)]), key=lambda r: r.fun)
    cp = ctrl(best.x)
    k = curv3(bez(cp, s))[2:-2]
    a1, a2, b1, b2 = np.exp(best.x) * L0
    return cp, dict(rmin=1 / k.max(), a=np.array([a1, a2]), b=np.array([b1, b2]))


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
