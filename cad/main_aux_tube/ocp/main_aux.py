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
STRAIGHT_END = 5.0  # S から +X へ足す直線部(ここまでが主管補助管)
STRAIGHT = 4.0  # E(枝管の出口)につながる、芯線の直線部の長さ(以上)
X_S = 92.0  # 端点 S の x(P1 の x=87.5 から +X へ延ばして、右側の端点への曲がりを緩やかにする)
D = 12.0
R_MIN = 10.0  # 軸線の最小曲げ半径の下限(外面の半径 6.4 より十分大きく)
ANGLE = 5.0  # P1(YZ)に投影した芯線の、S へ入る側の向きと (0,0,-1) のなす角(deg)。S から +Y 側へ傾いて下がる
GAP_REQ = 0.3  # 1番管などとの表面距離の下限(0 以上が条件。サンプリング誤差の余裕)
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


def tess_world(sh, tol):
    """ワールド座標の頂点の並び。Shape.tessellate は Location を無視するので、面ごとに located の三角形分割から取る。"""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location

    BRepMesh_IncrementalMesh(sh.wrapped, tol, False, 0.3, True)
    out = []
    for f in sh.faces():
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if tri is None:
            continue
        tr = loc.Transformation()
        for i in range(1, tri.NbNodes() + 1):
            q = tri.Node(i).Transformed(tr)
            out.append((q.X(), q.Y(), q.Z()))
    return out


def l_axis(E, u, S, R, n=120):
    """+Z から見て L 字の軸線。XY では E から u の XY 成分の向き(-Y)へ直進 → 半径 R で 90° 曲がって +X → S。角は (E.x, S.y)。
    Z は XY の道のり s の 3 次エルミート(始点で u の傾き、終点で傾き 0)。戻り値: 点列 (n, 3)、始点・終点の接線。"""
    d1 = np.array([u[0], u[1]]) / np.hypot(u[0], u[1])
    d2 = np.array([1.0, 0.0])
    Q = np.array([E[0], S[1]])  # 角
    if abs(d1 @ (Q - E[:2]) - np.linalg.norm(Q - E[:2])) > 1e-6:
        raise ValueError("E の出口が角の向きでない")
    a, b = Q - R * d1, Q + R * d2
    if np.linalg.norm(a - E[:2]) < 0 or np.linalg.norm(S[:2] - b) < 0 or (a - E[:2]) @ d1 < 0 or (S[:2] - b) @ d2 < 0:
        return None
    o = a + R * d2  # 円弧の中心
    l1, la, l3 = (a - E[:2]) @ d1, R * math.pi / 2, (S[:2] - b) @ d2
    Lt = l1 + la + l3
    ss = np.linspace(0, Lt, n)
    xy = np.empty((n, 2))
    for i, s_ in enumerate(ss):
        if s_ <= l1:
            xy[i] = E[:2] + d1 * s_
        elif s_ <= l1 + la:
            th = (s_ - l1) / R  # 0..π/2: a - o の方向から回す(d1 → d2)
            xy[i] = o + R * (math.cos(th) * (a - o) / R + math.sin(th) * (b - o) / R)
        else:
            xy[i] = b + d2 * (s_ - l1 - la)
    m0 = u[2] / math.hypot(u[0], u[1])
    t = ss / Lt
    h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
    z = h00 * E[2] + h10 * Lt * m0 + h01 * S[2]
    P = np.column_stack([xy, z])
    t0 = np.array([*d1, m0]); t0 /= np.linalg.norm(t0)
    return P, t0, np.array([1.0, 0.0, 0.0]), Lt


def hook(M, branch, others):
    import bb34_u

    branch, p0, n0, c0 = bb34_u.make_hook()(M, branch, others)  # 2番管と Bb の第 3→第 4 の回路(bb34)も一緒に出す
    others = others + list(zip(n0, p0))
    branch, p1, n1, c1 = aux_hook(M, branch, others)
    return branch, p0 + p1, n0 + n1, c0 + c1


def aux_hook(M, branch, others):
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
    S = np.array([arg("--xs", X_S), ys_, a * ys_ + b2])  # 端点は P2 上で、x だけ X_S へ延ばす(P1 の上の点から +X へ)
    tS = np.array([1.0, 0.0, 0.0])
    E, u = f1_225_exit()
    print(f"S (on P2, y {ys_:g}, x extended to {S[0]:g}) = {S.round(3).tolist()}, direction (1, 0, 0)")
    print(f"E (valve4 F1-225 exit) = {E.round(3).tolist()}, outward axis {u.round(4).tolist()}")
    # 直線部(E → E2 = E + STRAIGHT·u)+ 5 次ベジェ(制御点 6 つ): E2, E2 + a·u, P2, P3, S − b·(1,0,0), S。a, b, P2, P3(計 8 変数)を、差分進化で決める。
    # 条件: 軸と他の部品の頂点の距離から出した隙間 ≥ GAP_REQ、最小曲げ半径 ≥ R_MIN。そのうえで長さを短く。
    from scipy.optimize import differential_evolution

    tt6 = np.linspace(0, 1, 200)
    from math import comb

    Bm = np.array([[comb(5, k) * t**k * (1 - t) ** (5 - k) for k in range(6)] for t in tt6])
    gap_req, r_min_req = arg("--gap", GAP_REQ), arg("--rmin", R_MIN)

    E2 = E + arg("--straight", STRAIGHT) * u  # 直線部の終わり = ベジェの始点

    def ctrl(x):
        th = math.radians(arg("--angle", ANGLE))
        P3 = np.array([x[5], S[1] + x[6] * math.sin(th), S[2] - x[6] * math.cos(th)])  # 投影で S から (sinθ, -cosθ) の向きの線の上
        return np.array([E2, E2 + x[0] * u, x[2:5], P3, S - x[1] * tS, S])

    def solve():
        """差分進化(遅い: 全部品の三角形分割 + 探索で 1〜2 分)。結果は shape_cache に覚えて、条件とソースが同じなら計算しない。"""
        from scipy.spatial import cKDTree

        allo = others + [("bell03_branch1_wall", branch)]
        pts, lab = [], []
        for n, sh in allo:
            if n == "valve4_knuckle_F1_225_twisted" or not hasattr(sh, "tessellate") or n.endswith("centerline"):
                continue
            v = tess_world(sh, 0.15)
            pts += v
            lab += [n] * len(v)
        tree = cKDTree(np.array(pts))
        def evaluate(x):
            Pc = ctrl(x)
            C = Bm @ Pc
            d1 = np.gradient(C, axis=0)
            d2 = np.gradient(d1, axis=0)
            kap = np.linalg.norm(np.cross(d1, d2), axis=1) / np.maximum(np.linalg.norm(d1, axis=1), 1e-9) ** 3
            kap = kap[2:-2]
            d, i_ = tree.query(C[6:])
            # +Z から見た(XY)形: ゆるい U 字(y は減るだけ、x は増えるだけ、曲がりは一方向 = 反時計回りだけ)にするための違反量
            sk = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.hypot(d1[:, 0], d1[:, 1]), 1e-9) ** 3
            viol = float(np.maximum(d1[1:-1, 1], 0).sum() + np.maximum(-d1[1:-1, 0], 0).sum() + 20 * np.maximum(-sk[3:-3], 0).sum())
            return d.min() - D / 2 - 0.4, 1 / max(kap.max(), 1e-9), float(np.linalg.norm(np.diff(C, axis=0), axis=1).sum()), lab[int(i_[int(np.argmin(d))])]

        def xy_viol(x):
            """+Z から見た(XY)形をゆるい U 字にするための違反量: y は減るだけ、x は増えるだけ、曲がりは反時計回りだけ。"""
            C = Bm @ ctrl(x)
            d1 = np.gradient(C, axis=0)
            d2 = np.gradient(d1, axis=0)
            sk = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.hypot(d1[:, 0], d1[:, 1]), 1e-9) ** 3
            return float(np.maximum(d1[1:-1, 1], 0).sum() + np.maximum(-d1[1:-1, 0], 0).sum() + 400 * np.maximum(-sk[3:-3], 0).sum())

        def cost(x):
            g, r, ln, _ = evaluate(x)
            return 3 * xy_viol(x) + ln + 400 * max(0, gap_req - g) + 40 * max(0, r_min_req - r)

        lo = np.minimum(E, S) - 25
        hi = np.maximum(E, S) + 25
        lo[0] = 40
        bounds = [(1, 120), (1, 120)] + list(zip(lo, hi)) + [(lo[0], hi[0]), (5, 90)]
        res = differential_evolution(cost, bounds, seed=1, popsize=25, maxiter=400, tol=1e-8, polish=False)
        g, rmin, ln, nm = evaluate(res.x)
        print(f"straight {arg('--straight', STRAIGHT):g} from E + quintic Bezier -> S: gap {g:.3f} ({nm}), min bend R {rmin:.2f}, length {ln:.2f} (cost {res.fun:.2f}); a, b = {res.x[0]:.1f}, {res.x[1]:.1f}")
        print(f"  XY shape violation (0 = a gentle U seen from +Z): {xy_viol(res.x):.4f}")
        return [float(v) for v in res.x]

    from shape_cache import cached

    xs = cached("main_aux_ctrl", [round(float(v), 6) for v in [*S, *E, gap_req, r_min_req, arg("--angle", ANGLE), arg("--straight", STRAIGHT)]] + [len(others)],
                Path(__file__), solve)
    x_best = np.array(xs)
    Pc = ctrl(x_best)
    print(f"  control points: {Pc.round(2).tolist()}")
    w = Wire([Edge.make_line(Vector(*E), Vector(*E2)), Edge.make_bezier(*[Vector(*p) for p in Pc]),
                  Edge.make_line(Vector(*S), Vector(*(S + arg("--straight-end", STRAIGHT_END) * tS)))])
    print(f"axis length {w.length:.3f}")
    ends = [w.position_at(0.0), w.position_at(1.0)]
    t0, t1 = w.tangent_at(0.0), w.tangent_at(1.0)
    print(f"check: start {np.round([ends[0].X, ends[0].Y, ends[0].Z], 3).tolist()}, tangent {np.round([t0.X, t0.Y, t0.Z], 4).tolist()}; "
          f"end {np.round([ends[1].X, ends[1].Y, ends[1].Z], 3).tolist()}, tangent {np.round([t1.X, t1.Y, t1.Z], 4).tolist()}")
    import branch2_u as U
    import bell_place as BP
    import branch2_l as B2

    tube = U.const_d_tube(w, D, BP.WALL)
    print(f"tube D {D:g} wall {BP.WALL:g}: valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (<5 mm) of the outer surface:")
    allo = others + [("bell03_branch1_wall", branch)]
    cl = B2.report_clearance(tube, allo)
    for n_, sh_ in (allo if B2.checks_enabled() else []):  # 食い込み(体積の重なり)の確認。接触だけなら 0
        if n_ == "valve4_knuckle_F1_225_twisted" or not hasattr(sh_, "bounding_box") or not B2.near(sh_.bounding_box(optimal=False), tube.bounding_box(optimal=False), 0.1):
            continue
        inter = tube.intersect(sh_) if tube.distance_to(sh_) < 1e-6 else None
        ov = sum(x.volume for x in inter.solids()) if inter else 0.0
        print(f"  overlap volume with {n_}: {ov:.4f}")
        if ov > 0:
            bb_ = inter.solids()[0].bounding_box()
            print(f"    overlap bbox x {bb_.min.X:.1f}..{bb_.max.X:.1f}, y {bb_.min.Y:.1f}..{bb_.max.Y:.1f}, z {bb_.min.Z:.1f}..{bb_.max.Z:.1f}")
    print(f"min clearance {cl[0][0]:.3f} ({cl[0][1]})" if cl else "no part within 5 mm")
    # 表示用: 近似直線(P1 上)、P1 上のオフセット直線、点 S、P1・P2 の見える範囲の薄い板
    y0, y1 = FIT_Y
    fit_line = Edge.make_line(Vector(x1, y0, a * y0 + b), Vector(x1, y1, a * y1 + b))
    off_line = Edge.make_line(Vector(x1, y0, a * y0 + b2), Vector(x1, y1, a * y1 + b2))
    prof = Polyline(*[(x1, float(y), float(z)) for y, z in zip(ys, zs)])
    import build123d as bd

    sphere = bd.Pos(*S) * bd.Sphere(1.5)
    p1 = Face(Wire.make_polygon([Vector(x1, y0, 20), Vector(x1, y1, 20), Vector(x1, y1, 100), Vector(x1, y0, 100)], close=True))
    return branch, [tube, w, prof, fit_line, off_line, sphere, p1], [
        "main_aux_tube_wall", "main_aux_axis", "main_aux_profile_on_P1", "main_aux_fit_line", "main_aux_P2_on_P1", "main_aux_S", "main_aux_P1"
    ], ["#20c0a0", "#ff2020", "#808080", "#00c0ff", "#00c0ff", "#ff2020", "#80c0ff"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
