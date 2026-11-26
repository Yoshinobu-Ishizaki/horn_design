"""F管の右側の経路(2026-11-27、芯線だけ): 第 4 植込の 2 階右上の枝管(valve4_knuckle_F2_45_twisted)から。座標は管体組立のワールド。

- 枝管側: 枝管の出口の端面の中心 E から、出口の軸の延長に BR_ST まっすぐ。
- ベル平面の直線: ベル平面(ベルの芯線の平面)の上で、y を左側の経路(f_route)の中管側の直線とそろえ、x = X0 .. X1。
- 中間部の作図(2026-11-27): 左側と同じ、ベルの曲げ内側の外面をベル平面の中で内側へ BELL_OFF(f_route と同じ 7.8)ずらした曲線の、
  x > 0 の部分、y = Y_LOW .. Y_HIGH(最初は左側と同じ [-40, 0] → [-40, -10] → [-50, -10]、2026-11-27)。
- つなぎ A: 枝管側の直線の端 → 桃色の曲線の y = Y_HIGH の端、つなぎ B: 桃色の曲線の y = Y_LOW の端 → ベル平面の直線の +X の端(G2 の 5 次ベジェ)。

    uv run python cad/model202611/body_assy/f_slide/ocp/f_route_r.py [--br-st 6] [--x0 -60] [--x1 45] [--bell-off 7.8] [--y-low -50] [--y-high -10] [--w-xy 5]
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

    # ベル平面の直線: y = 左側の経路の中管側の直線の y、x = x0 .. x1、z はベル平面の上
    y = d["f_route_centerline"].position_at(0.0).Y
    o, n = bell_plane(M)
    z_at = lambda x: o[2] - (n[0] * (x - o[0]) + n[1] * (y - o[1])) / n[2]  # noqa: E731
    P0, P1 = np.array([x0, y, z_at(x0)]), np.array([x1, y, z_at(x1)])
    e_bp = Edge.make_line(Vector(*P0), Vector(*P1))
    t = (P1 - P0) / np.linalg.norm(P1 - P0)
    print(f"bell-plane straight: y {y:.3f} (= f_route inner-tube straight), {P0.round(3).tolist()} -> {P1.round(3).tolist()} ({e_bp.length:.3f}), "
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
    return (branch, p0 + [w, e_mid], n0 + ["f_route_r_centerline", "f_route_r_bell_offset"], c0 + ["#ff2020", "#ff80ff"])


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
