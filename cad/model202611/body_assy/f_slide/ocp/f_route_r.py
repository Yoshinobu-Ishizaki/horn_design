"""F管の右側の経路(2026-11-27、芯線だけ): 第 4 植込の 2 階右上の枝管(valve4_knuckle_F2_45_twisted)から。座標は管体組立のワールド。

- 枝管側: 枝管の出口の端面の中心 E から、出口の軸の延長に BR_ST まっすぐ。
- ベル平面の直線: ベル平面(ベルの芯線の平面)の上で X 方向、x = X0 .. X1。最初は y を左側の経路(f_route)の中管側の直線とそろえた。
  2026-11-27: 中管 2 側の直線(X 方向)との軸間距離が PITCH_T2 になるまで -Y へ(ベル平面の上を)動かす。
- 中間部の作図(2026-11-27): 左側と同じ、ベルの曲げ内側の外面をベル平面の中で内側へ BELL_OFF(f_route と同じ 7.8)ずらした曲線の、
  x > 0 の部分、y = Y_LOW .. Y_HIGH(最初は左側と同じ [-40, 0] → [-40, -10] → [-50, -10]、2026-11-27)。
- 中管 2 側(2026-11-27): F管抜差の中管 2 の -X の端面から GAP2 離した点(中管 2 の軸の上)から、-X へまっすぐ x = X2_END まで。
- U: ベル平面の直線の -X の端 → 中管 2 側の直線の -X の端。2026-11-27 から基本の U 字管(ubows、ピッチ 50)、頂点の x = U_APEX_X(-81.175、非対称な U と同じ)。
  2 本の直線の -X の端は U の直線の端に合わせる(X0・X2_END は使わない)。--u-asym で前の非対称な U(7 次ベジェ、平面、両端 G2)。
- 管: 外径 12.8・内径 12.0 を、第 4 の出口から中管 2 側の直線の始点まで 1 本の芯線に沿って掃引。
- つなぎ A: 枝管側の直線の端 → 桃色の曲線の y = Y_HIGH の端、つなぎ B: 桃色の曲線の y = Y_LOW の端 → ベル平面の直線の +X の端(G2 の 5 次ベジェ)。

    uv run python cad/model202611/body_assy/f_slide/ocp/f_route_r.py [--br-st 6] [--x0 -60] [--x1 45] [--bell-off 7.8] [--y-low -50] [--y-high -10] [--w-xy 5] [--pitch-t2 50] [--u-r-plus 20] [--u-r-minus 20] [--gap2 1] [--x2-end -35]
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

BRANCH = "valve4_knuckle_F2_45_twisted"  # 第 4 の 2 階・右上(孔 45°)のねじった枝管
BR_ST = 6.0  # 枝管の出口から軸の延長にまっすぐ出す長さ
X0, X1 = -60.0, 45.0  # ベル平面の直線の x の範囲。[-60, 35] → [-60, 45](2026-11-27)
U_STD = True  # 2026-11-27: U を基本の U 字管(ubows、ピッチ = PITCH_T2)にする。False(--u-asym)なら非対称な U(asym_u)
U_APEX_X = -71.161549  # (+5、2026-11-27 さらに) 基本の U の頂点の x。-81.175(非対称な U の頂点の x と同じ)→ +5.013451(2026-11-27、F管抜差の U とベルの曲げ内側の円の中心 x = 5 についてほぼ対称に)。直線の -X の端はここから決まる
U_R_PLUS, U_R_MINUS = 20.0, 20.0  # 非対称な U の最小曲げ半径: +Y 側の半分・-Y 側の半分。+Y 40 → 20(2026-11-27)
PITCH_T2 = 50.0  # ベル平面の直線と中管 2 側の直線の軸間距離
GAP2 = 1.0  # 中管 2 の -X の端面から直線の始点まで
X2_END = -35.0  # 中管 2 側の直線の終わりの x
Y_LOW, Y_HIGH = -50.0, -10.0  # 中間部の作図の曲線の y の範囲(ワールド)。[-40, 0](左と同じ)→ [-40, -10] → [-50, -10](2026-11-27)


def arg(k, d):
    return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d


def vec(v):
    return np.array([v.X, v.Y, v.Z])


def branch_exit(shape):
    """枝管の出口の端面の中心と外向きの軸。端面 = 平面の面のうち、第 4 の中心から最も遠いもの。
    軸は valve4_knuckle の式(twisted_knuckle_2f_upper_right と同じ θ・ψ)で、端面の法線と向きを確かめる。"""
    import valve4_knuckle as VK

    c0 = np.array([VK.X_VALVE4, 0.0, VK.Z_F2])
    faces = [f for f in shape.faces() if f.geom_type.name == "PLANE"]
    f = max(faces, key=lambda f: np.linalg.norm(vec(f.center()) - c0))
    E = vec(f.center())
    th = math.radians(VK.THETA)
    ps = math.degrees(math.acos(-1.0 / math.tan(th)))
    u = np.array(VK.exit_axis_world(VK.THETA, ps, 45.0))
    nf = vec(f.normal_at())
    return E, u, float(abs(nf @ u))


def bell_plane(M):
    """ベル平面(設計の z = 0 の平面を組立の変換 M で動かした面)の点と単位法線。"""
    Mw = np.asarray(M, float)
    n = Mw[:3, 2] / np.linalg.norm(Mw[:3, 2])
    return Mw[:3, 3], n


def hook(M, branch, others):
    import f_route as FR
    from build123d import Edge, Vector

    branch, p0, n0, c0 = FR.hook(M, branch, others)
    d = dict(list(others) + list(zip(n0, p0)))
    br_st, x0, x1 = arg("--br-st", BR_ST), arg("--x0", X0), arg("--x1", X1)

    # 枝管側の直線
    E, u, par = branch_exit(d[BRANCH])
    E1 = E + br_st * u
    e_br = Edge.make_line(Vector(*E), Vector(*E1))
    print(f"F route (right, centerlines only): branch {BRANCH} exit E {E.round(3).tolist()}, axis {u.round(4).tolist()} (|face normal . axis| {par:.6f}) "
          f"-> {E1.round(3).tolist()} ({e_br.length:.3f})")

    # ベル平面の直線: X 方向、x = x0 .. x1、ベル平面の上。y は中管 2 側の直線との軸間距離が pitch_t2 になる所(左側の経路の y から -Y へ)
    from scipy.optimize import brentq

    o, n = bell_plane(M)
    zp = lambda x, yy: o[2] - (n[0] * (x - o[0]) + n[1] * (yy - o[1])) / n[2]  # noqa: E731
    gap2, x2_end, pitch_t2 = arg("--gap2", GAP2), arg("--x2-end", X2_END), arg("--pitch-t2", PITCH_T2)
    b2 = d["f_slide_inner_tube2"].bounding_box(optimal=False)
    T0 = np.array([b2.min.X - gap2, (b2.min.Y + b2.max.Y) / 2, (b2.min.Z + b2.max.Z) / 2])
    y_left = d["f_route_centerline"].position_at(0.0).Y
    assert abs(n[0]) < 1e-9  # ベル平面の直線が X 方向なら、軸間距離は YZ での距離
    y = brentq(lambda yy: np.hypot(yy - T0[1], zp(0.0, yy) - T0[2]) - pitch_t2, T0[1], y_left)
    z_at = lambda x: zp(x, y)  # noqa: E731
    import branch2_u as U

    u_std = U_STD and "--u-asym" not in sys.argv
    if u_std:  # 基本の U: 頂点の x を U_APEX_X に保ち、2 本の直線の -X の端を U の直線の端にそろえる
        w_u, info_u = U.u_wire_local(pitch_t2)
        apex = arg("--u-apex-x", U_APEX_X)
        x0 = x2_end = apex + info_u["apex_y"] if "apex_y" in info_u else apex + 5.0 + info_u["h"]
    P0, P1 = np.array([x0, y, z_at(x0)]), np.array([x1, y, z_at(x1)])
    e_bp = Edge.make_line(Vector(*P0), Vector(*P1))
    t = (P1 - P0) / np.linalg.norm(P1 - P0)
    print(f"bell-plane straight: y {y:.3f} ({y - y_left:+.3f} from the f_route inner-tube straight; pitch {pitch_t2:g} to the inner-tube-2 straight), {P0.round(3).tolist()} -> {P1.round(3).tolist()} ({e_bp.length:.3f}), "
          f"direction {t.round(5).tolist()}, on the bell plane {float((P0 - o) @ n):+.1e} / {float((P1 - o) @ n):+.1e}; bell-plane normal {n.round(5).tolist()}")
    print(f"between E1 and the straight's +X end: {(P1 - E1).round(3).tolist()} (distance {np.linalg.norm(P1 - E1):.3f})")
    # 中間部の作図: ベルの曲げ内側の外面を BELL_OFF ずらした曲線(y = Y_LOW .. Y_HIGH、x > 0)
    off = arg("--bell-off", FR.BELL_OFF)
    y_lo, y_hi = arg("--y-low", Y_LOW), arg("--y-high", Y_HIGH)
    e_mid, info = offset_edge(M, off, y_lo, y_hi)
    print(f"bell inner offset {off:g} (bell plane): world y {y_lo:g} .. {y_hi:g}, x > 0: {info['runs']} run(s), from {info['p0'].round(3).tolist()} "
          f"to {info['p1'].round(3).tolist()} ({e_mid.length:.3f}), x {info['xmin']:.3f}..{info['xmax']:.3f}")
    print(f"  to bell wall: {e_mid.distance_to(d['bell03_bell_wall']):.3f}")

    # つなぎ(2026-11-27、左側と同じ G2 の 5 次ベジェ f_route.g2_join):
    #   A: 枝管側の直線の端 E1(向き u、曲率 0)→ 桃色の曲線の y = Y_HIGH の端(向き・曲率ベクトル)。XY へ投影した曲率も小さく(W_XY)
    #   B: 桃色の曲線の y = Y_LOW の端 → ベル平面の直線の +X の端 P1(向き -X、曲率 0)
    w_xy = arg("--w-xy", FR.W_XY)
    A, ta, Ka = FR.frame(e_mid, 0.0)
    cpa, ia = FR.memo_join("f_route_r_joinA", (E1, u, A, ta, Ka, w_xy), lambda: FR.g2_join(E1, u, np.zeros(3), A, ta, Ka, w_xy=w_xy))
    Bp, tb, Kb = FR.frame(e_mid, 1.0)
    tx = np.array([-1.0, 0.0, 0.0])
    cpb, ib = FR.memo_join("f_route_r_joinB", (Bp, tb, Kb, P1, tx), lambda: FR.g2_join(Bp, tb, Kb, P1, tx, np.zeros(3)))
    e_bp_r = Edge.make_line(Vector(*P1), Vector(*P0))  # 経路の向き(+X の端 → -X の端)
    joins = []
    for nm, cp, info, (Q0, q0, K0), (Q1, q1, K1) in (("join A (branch straight -> offset curve y = %g)" % y_hi, cpa, ia, (E1, u, np.zeros(3)), (A, ta, Ka)),
                                                     ("join B (offset curve y = %g -> bell-plane straight x = %g)" % (y_lo, x1), cpb, ib, (Bp, tb, Kb), (P1, tx, np.zeros(3)))):
        e = Edge.make_bezier(*[Vector(*q) for q in cp])
        s0, s1 = FR.frame(e, 0.0), FR.frame(e, 1.0)
        pj = FR.bez(cp, np.linspace(0, 1, 2001))
        kxy = FR.curv3(np.column_stack([pj[:, 0], pj[:, 1], np.zeros(len(pj))]))[2:-2]
        err = max(np.linalg.norm(s0[0] - Q0), np.linalg.norm(s1[0] - Q1))
        ang = max(np.degrees(np.arccos(min(1.0, s0[1] @ q0))), np.degrees(np.arccos(min(1.0, s1[1] @ q1))))
        kerr = max(np.linalg.norm(s0[2] - K0), np.linalg.norm(s1[2] - K1))
        print(f"{nm}: quintic Bezier {e.length:.3f}, min R {info['rmin']:.2f} (XY projection {1 / kxy.max():.2f}); legs a {info['a'].round(3).tolist()} b {info['b'].round(3).tolist()}")
        print(f"  G2 check: position {err:.1e}, tangent {ang:.2e} deg, curvature vector {kerr:.2e}; to bell wall {e.distance_to(d['bell03_bell_wall']):.3f}, "
              f"to branch1 {e.distance_to(branch):.3f} (centerline; tube outer radius 6.4)")
        joins.append(e)
    total = e_br.length + joins[0].length + e_mid.length + joins[1].length + e_bp.length
    print(f"F route (right) centerline: {e_br.length:.3f} + {joins[0].length:.3f} + {e_mid.length:.3f} + {joins[1].length:.3f} + {e_bp.length:.3f} = {total:.3f}")
    from build123d import Wire

    w = Wire([Edge.make_line(Vector(*E), Vector(*E1)), joins[0], e_mid, joins[1], e_bp_r])
    # 中管 2 側の直線: 中管 2 の -X の端面から gap2 離して、-X へ x = x2_end まで
    T1 = np.array([x2_end, T0[1], T0[2]])
    e_t2 = Edge.make_line(Vector(*T0), Vector(*T1))
    print(f"inner-tube-2 side straight: {T0.round(3).tolist()} -> {T1.round(3).tolist()} ({e_t2.length:.3f}, dir -X); "
          f"to the bell-plane straight's -X end {P0.round(3).tolist()}: {(P0 - T1).round(3).tolist()} (distance {np.linalg.norm(P0 - T1):.3f}); axis distance {np.hypot(*(P0 - T1)[1:]):.6f}")
    if u_std:
        # 基本の U(ubows の座標: 左の直線の始端 (-P/2, 0) → +Y)を、局所 X → 中管 2 側の直線への向き、局所 Y → -X、左の直線の始端 → P0 に置く
        import bell_place as BP

        ex = np.array([1.0, 0.0, 0.0])
        ev = (T1 - P0) - ((T1 - P0) @ ex) * ex
        ev /= np.linalg.norm(ev)
        R = np.column_stack([ev, -ex, np.cross(ev, -ex)])
        Tm = np.eye(4)
        Tm[:3, :3] = R
        Tm[:3, 3] = P0 - R @ np.array([-pitch_t2 / 2, 0.0, 0.0])
        wu = BP.apply(w_u, Tm)
        q_end = wu.position_at(1.0)
        xs = [wu.position_at(t).X for t in np.linspace(0, 1, 2001)]
        print(f"standard U (ubows, pitch {pitch_t2:g}): legs at x {x0:.3f} (apex x {min(xs):.3f}, set {apex:g}); curve {info_u['curve_len']:.3f} + legs 2 x 5 = {wu.length:.3f}, "
              f"min bend R {info_u['rmin']:.2f}, height {info_u['h']:.2f}; end vs T1 {np.linalg.norm(np.array([q_end.X, q_end.Y, q_end.Z]) - T1):.1e}")
        print(f"  to bell wall {wu.distance_to(d['bell03_bell_wall']):.3f}, to branch1 {wu.distance_to(branch):.3f} (centerline; tube outer radius 6.4)")
        u_edges = wu.edges()
    else:
        u_edges = asym_edge(P0, T1, d, branch)
    return finish(branch, p0, n0, c0, others, w, u_edges, T0, T1, e_mid)


def asym_edge(P0, T1, d, branch):
    """非対称な U(2026-11-27): ベル平面の直線の -X の端 P0(向き -X)→ 中管 2 側の直線の -X の端 T1(向き +X)。2 本の直線を含む平面の 7 次ベジェ。
    両端の曲率 0(G2)。+Y 側(ベル平面の直線の側)の曲率を小さく、-Y 側を大きく(「つ」を左右反転した形)。"""
    import f_route as FR
    from build123d import Edge, Vector

    r_plus, r_minus = arg("--u-r-plus", U_R_PLUS), arg("--u-r-minus", U_R_MINUS)
    cpu, iu = FR.memo_join("f_route_r_u", (P0, T1, r_plus, r_minus), lambda: asym_u(P0, T1, r_plus, r_minus))
    e_u = Edge.make_bezier(*[Vector(*q) for q in cpu])
    s0, s1 = FR.frame(e_u, 0.0), FR.frame(e_u, 1.0)
    print(f"asymmetric U (P0 {P0.round(3).tolist()} -> T1 {T1.round(3).tolist()}, pitch {np.hypot(*(T1 - P0)[1:]):.3f}): deg-7 Bezier {e_u.length:.3f}, "
          f"min R +Y half {iu['r_plus']:.2f} (>= {r_plus:g}) / -Y half {iu['r_minus']:.2f} (>= {r_minus:g}), reaches x {iu['xmin']:.3f}, plane offset {iu['planar']:.1e}; "
          f"signed curvature max {iu['k_sign_max']:+.2e} (<= 0: one sign), v {iu['v_range'][0]:.3f}..{iu['v_range'][1]:.3f} (0..pitch)")
    print(f"  G2 check: start tangent {np.degrees(np.arccos(min(1.0, s0[1] @ np.array([-1.0, 0, 0])))):.2e} deg, curvature {np.linalg.norm(s0[2]):.1e}; "
          f"end position {np.linalg.norm(s1[0] - T1):.1e}, tangent {np.degrees(np.arccos(min(1.0, s1[1] @ np.array([1.0, 0, 0])))):.2e} deg, curvature {np.linalg.norm(s1[2]):.1e}")
    print(f"  to bell wall {e_u.distance_to(d['bell03_bell_wall']):.3f}, to branch1 {e_u.distance_to(branch):.3f} (centerline; tube outer radius 6.4)")
    return [e_u]


def finish(branch, p0, n0, c0, others, w, u_edges, T0, T1, e_mid):
    import f_route as FR
    from build123d import Edge, Vector

    # 管(2026-11-27): 外径 12.8・内径 12.0(f_route と同じ)を、第 4 の出口 → … → U → 中管 2 側の直線の始点 まで 1 本の芯線に沿って掃引(辺ごと、キャッシュ)
    import branch2_l as B2
    import branch2_u as U
    from build123d import Wire
    from shape_cache import cached

    wt = Wire(w.edges() + list(u_edges) + [Edge.make_line(Vector(*T1), Vector(*T0))])
    key = [np.round(np.array([[v.X, v.Y, v.Z] for v in wt.vertices()]), 9).tolist(), round(wt.length, 9), FR.TUBE_OD, FR.TUBE_ID]
    tube = cached("f_route_r_tube", key, __file__, lambda: U.const_d_tube(wt, FR.TUBE_ID, (FR.TUBE_OD - FR.TUBE_ID) / 2))
    vol = sum(x.volume for x in tube.solids())
    vexp = np.pi / 4 * (FR.TUBE_OD**2 - FR.TUBE_ID**2) * wt.length
    print(f"F route (right) tube D {FR.TUBE_ID:g}/{FR.TUBE_OD:g}: valid {tube.is_valid}, {len(tube.solids())} solids, volume {vol:.2f} "
          f"(expected {vexp:.2f}, {100 * (vol / vexp - 1):+.3f}%), centerline {wt.length:.3f}")
    print("clearance (F route right tube):")
    B2.report_clearance(tube, others + list(zip(n0, p0)) + [("bell03_branch1_wall", branch)])
    return (branch, p0 + [tube, wt, e_mid], n0 + ["f_route_r_wall", "f_route_r_centerline", "f_route_r_bell_offset"],
            c0 + ["#40c040", "#ff2020", "#ff80ff"])


def asym_u(A, B, r_plus, r_minus, n=201):
    """A(向き -X、曲率 0)→ B(向き +X、曲率 0)の 7 次ベジェ。A・B を通る X 方向の 2 直線を含む平面の中。
    P1 = A - a1·X、P2 = P1 - a2·X、P5 = P6 - b2·X、P6 = B - b1·X、P3・P4 は平面の中で自由(平面の座標 (x, v)、v は A の直線から B の直線へ)。
    目的: 長さ + 0.01·Σ(dκ)²、条件(罰則): +Y 側の半分(A の直線に近い側 v < pitch/2)の最小 R ≥ r_plus、-Y 側の半分 ≥ r_minus。
    (曲率だけを小さくすると U がいくらでも大きくなるので、長さを最小にする。2026-11-27)
    さらに(2026-11-27): 2 本の直線の外へ出ない(0 ≤ v ≤ pitch)、曲率の符号が途中で変わらない(平面の中の符号付き曲率が一定の符号)。"""
    import f_route as FR
    from scipy.optimize import minimize

    ex = np.array([1.0, 0.0, 0.0])
    dv = (B - A) - ((B - A) @ ex) * ex
    pitch = np.linalg.norm(dv)
    ev = dv / pitch
    to3 = lambda x, v: A + x * ex + v * ev  # noqa: E731  (x は A からの X の差)
    xb = (B - A) @ ex
    s = np.linspace(0, 1, n)

    def ctrl(q):
        a1, a2, b1, b2 = np.exp(q[:4]) * pitch
        x3, v3, x4, v4 = q[4:] * pitch
        return np.array([to3(0, 0), to3(-a1, 0), to3(-a1 - a2, 0), to3(x3, v3), to3(x4, v4), to3(xb - b1 - b2, pitch), to3(xb - b1, pitch), B])

    def parts(q):
        p = FR.bez(ctrl(q), s)
        k = FR.curv3(p)[2:-2]
        v = (p[2:-2] - A) @ ev
        return p, k, v

    def signed(p):
        x, v = (p - A) @ ex, (p - A) @ ev
        x1, v1 = np.gradient(x), np.gradient(v)
        x2, v2 = np.gradient(x1), np.gradient(v1)
        return ((x1 * v2 - v1 * x2) / np.hypot(x1, v1) ** 3)[2:-2]  # -X → +v → +X の向きに回るので負

    def f(q):
        p, k, v = parts(q)
        kp, km = k[v < pitch / 2].max(initial=0.0), k[v >= pitch / 2].max(initial=0.0)
        ds = np.linalg.norm(np.diff(p, axis=0), axis=1).sum() / n
        ln = ds * n
        pen = max(0.0, kp - 1.0 / r_plus) ** 2 + max(0.0, km - 1.0 / r_minus) ** 2
        pen += max(0.0, float(signed(p).max())) ** 2  # 曲率の符号が変わらない
        vv = (p - A) @ ev
        pen += (max(0.0, float(vv.max()) - pitch) ** 2 + max(0.0, -float(vv.min())) ** 2) / pitch**2  # 直線の外へ出ない
        return float(ln / pitch + 0.01 * (np.diff(k) ** 2).sum() / ds * pitch**3 + 1e5 * pen * pitch**2)

    starts = [np.r_[np.log([0.3, 0.3, 0.3, 0.3]), [-1.2, 0.2, -1.0, 0.9]], np.r_[np.log([0.5, 0.4, 0.2, 0.2]), [-1.6, 0.4, -1.2, 1.0]],
              np.r_[np.log([0.6, 0.6, 0.15, 0.15]), [-2.0, 0.5, -1.3, 1.1]]]
    best = min((minimize(f, q0, method="Nelder-Mead", options=dict(maxiter=8000, xatol=1e-7, fatol=1e-12)) for q0 in starts), key=lambda r: r.fun)
    cp = ctrl(best.x)
    p, k, v = parts(best.x)
    nrm = np.cross(ex, ev)
    ks = signed(p)
    vv = (p - A) @ ev
    return cp, dict(r_plus=1 / k[v < pitch / 2].max(), r_minus=1 / k[v >= pitch / 2].max(), xmin=float(p[:, 0].min()),
                    k_sign_max=float(ks.max()), v_range=(float(vv.min()), float(vv.max())),
                    planar=float(np.abs((cp - A) @ nrm).max()))


def offset_edge(M, off, y_lo, y_hi):
    """f_route.bell_inner_offset の曲線(ワールド)のうち、y_lo ≤ y ≤ y_hi・x > 0 の部分のスプライン(左側と同じ作り方: 範囲の外へ延ばして作り、端で切る)。"""
    import f_route as FR
    from build123d import Edge, Vector

    Mw = np.asarray(M, float)
    qw = FR.bell_inner_offset(off) @ Mw[:3, :2].T + Mw[:3, 3]
    idx = np.flatnonzero((qw[:, 1] <= y_hi) & (qw[:, 1] >= y_lo) & (qw[:, 0] > 0.0))
    runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
    run = max(runs, key=len)
    i0, i1 = max(0, run[0] - FR.EXT), min(len(qw) - 1, run[-1] + FR.EXT)
    step = max(1, (run[-1] - run[0]) // 200)
    nodes = sorted(set(range(i0, i1 + 1, step)) | {run[0], run[-1], i1})
    e = Edge.make_spline([Vector(*qw[i]) for i in nodes]).trim(Vector(*qw[run[0]]), Vector(*qw[run[-1]]))
    pts = qw[run]
    return e, dict(runs=len(runs), p0=pts[0], p1=pts[-1], xmin=pts[:, 0].min(), xmax=pts[:, 0].max())


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
