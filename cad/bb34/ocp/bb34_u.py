"""Bb の第 3 → 第 4 の回路: 第 3 植込の 2 階・左上(135°)の枝管(valve3_knuckle_L1_45、出口 -X)に、U 字をつなぐ。

- U 字の曲がりは基本の U 字管(cad/bows/ocp/ubows.py、直管 LEG = 5)と同じ。ピッチは下の条件で決まる。内径は ⌀12.0 一定、板厚はベルと同じ。
- 出口の軸(-X)まわりに U を回して、もう一方の直線の軸が、水平面 z = 34 + RISE(= 49)に乗るようにする(ユーザー指示)。
- U 字の浮いている端から、+X 方向にまっすぐな管をつなぐ。右側の端は x = X_END(= 25)。
- 直管の右端(x = X_END)と第 4 の 2 階左下(225°)の枝管の端面を、L 字の管(平面内の 90° 曲げ)で結ぶ。角は出口の軸の延長と
  z = 49 の交点。曲げ R は、Bb1_outer_tube_R との表面間距離が TARGET_GAP(0.4)になるように決める(--R で指定も可)。
- 管体組立(cad/bellscrew/ocp/assy_with_valves.py)の hook で足す。座標は管体組立のワールド。
- もう一方の直線の軸は、水平面 z = 34 + RISE(= 49)の上で、第 4 の 2 階左下(225°、ねじった枝管 valve4_knuckle_F2_225_twisted)の
  出口の軸を伸ばして z = 49 と交わる点(X, -37.553, 49)を通る(ユーザー指示)。ピッチ = hypot(Δy, RISE) ≒ 49.86、
  回転角 = asin(RISE / ピッチ)。向きは -Y 側(n = (0, -cos, +sin))。`--pitch 40` のように指定すると、その値で置く(交点は無視)。

    python3 cad/valves/ocp/warm.py run cad/bb34/ocp/bb34_u.py [--pitch 40] [--rise 15] [--side plus]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"),
                str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

PITCH = None  # None なら、第 4 の枝管の出口の軸の延長の交点を通るように決める
RISE = 15.0  # もう一方の直線の軸の高さ: 2 階の軸平面(z = 34)から +15
D = 12.0
REF_NAME = "Bb1_outer_tube_R"  # L 字の曲げ R は、この部品との表面間距離が TARGET_GAP になるように決める
TARGET_GAP = 0.4
X_END = 25.0  # U 字の浮いている端から +X へ伸ばす直線の管の、右側の端の x
KNUCKLE = "valve3_knuckle_L1_45"  # 第 3 の 2 階・左上(ワールド 135°)


def exit_of_knuckle(name=KNUCKLE):
    """第 3 の 2 階・左上の枝管の、出口の端面の中心と外向きの軸。(端面は、つばのない側の平面の円環で、中心が植込みから遠い方)"""
    from valve_row import build_row_cached

    _, ks, names = build_row_cached()["valve3"]
    k = ks[names.index(name)]
    a_ring = math.pi / 4 * (12.8**2 - 12.0**2)
    ends = [f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.area - a_ring) < 0.5]
    f = max(ends, key=lambda f: abs(f.center().X - (-35.0)))  # 植込み中心 x = -35 から遠い方
    c, n = f.center(), f.normal_at()
    return np.array([c.X, c.Y, c.Z]), np.array([n.X, n.Y, n.Z])


def f2_225_exit():
    """第 4 の 2 階左下(225°)のねじった枝管の、出口の端面の中心と外向きの軸。"""
    import valve4_knuckle as V

    k = V.twisted_knuckle_2f()
    a_ring = math.pi / 4 * (12.8**2 - 12.0**2)
    f = max((f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.area - a_ring) < 0.5), key=lambda f: -f.normal_at().Y)
    c, n = f.center(), f.normal_at()  # 出口の端面は、外向きが -Y 側(+Z 寄り)
    return np.array([c.X, c.Y, c.Z]), np.array([n.X, n.Y, n.Z])


def target_point(z_plane):
    """第 4 の 2 階左下(225°)のねじった枝管の出口の軸を伸ばして、水平面 z = z_plane と交わる点。"""
    P, u = f2_225_exit()
    return P + (z_plane - P[2]) / u[2] * u


def l_wire(p_start, corner, p_end, r):
    """直管の右端 p_start(向き d1)→ 角 corner → 枝管の端面の中心 p_end(入る向き d2)の L 字の芯線。90° の曲げを R r で丸める。
    平面内(d1 と d2 を含む面)。曲げの両側の直線は、長さ 0 のとき省く。"""
    from build123d import Edge, Wire

    d1 = (corner - p_start) / np.linalg.norm(corner - p_start)
    d2 = (p_end - corner) / np.linalg.norm(p_end - corner)
    assert abs(float(d1 @ d2)) < 1e-6, f"L 字にならない(d1・d2 = {float(d1 @ d2):.6f})"
    a, b = corner - r * d1, corner + r * d2
    o = a + r * d2
    m = o + r * (d1 - d2) / math.sqrt(2.0)
    es = []
    if np.linalg.norm(a - p_start) > 1e-9:
        es.append(Edge.make_line(tuple(p_start), tuple(a)))
    es.append(Edge.make_three_point_arc(tuple(a), tuple(m), tuple(b)))
    if np.linalg.norm(p_end - b) > 1e-9:
        es.append(Edge.make_line(tuple(b), tuple(p_end)))
    return Wire(es)


def placement(pitch=PITCH, rise=RISE, side=-1):
    """U の置き方。局所: 左の直線の始端 (-P/2, 0) → 出口、局所 +Y → 出口の軸、局所 +X(もう一方の直線への向き)→ n。
    n = cos(φ)·e_h + sin(φ)·Z、sin φ = rise / pitch。e_h は軸に垂直な水平方向(side=-1 で -Y 側)。"""
    P0, a = exit_of_knuckle()
    z = np.array([0.0, 0.0, 1.0])
    e_h = np.cross(a, z)
    e_h = side * e_h / np.linalg.norm(e_h)
    t = math.asin(rise / pitch)
    n = math.cos(t) * e_h + math.sin(t) * z
    R = np.column_stack([n, a, np.cross(n, a)])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = P0 - R @ np.array([-pitch / 2, 0.0, 0.0])
    return T, dict(P0=P0, a=a, n=n)


def main() -> None:
    import assy_with_valves as AW
    import bell_place as BP
    import branch2_u as U

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    rise = arg("--rise", RISE)
    P0 = exit_of_knuckle()[0]
    Q = target_point(P0[2] + rise)
    pitch = arg("--pitch", math.hypot(Q[1] - P0[1], rise))
    side = +1 if "--side" in sys.argv and sys.argv[sys.argv.index("--side") + 1] == "plus" else -1

    def hook(M, branch, others):
        w, info = U.u_wire_local(pitch)
        T, pl = placement(pitch, rise, side)
        ww = BP.apply(w, T)
        q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
        q1 = np.array([q1.X, q1.Y, q1.Z])
        print(f"target point (valve4 F2-225 exit axis extended to z={P0[2] + rise:g}): {Q.round(3).tolist()}")
        print(f"exit {KNUCKLE}: {pl['P0'].round(3).tolist()}, axis {pl['a'].round(4).tolist()}")
        print(f"U pitch {pitch:g}: curve {info['curve_len']:.3f} + legs 2 x 5, total {w.length:.3f}; min bend R {info['rmin']:.2f}, "
              f"height {info['h']:.2f}")
        print(f"n = {pl['n'].round(4).tolist()} (rotation {math.degrees(math.asin(rise / pitch)):.2f} deg, rise {rise:g}, side {'+Y' if side > 0 else '-Y'})")
        off = q1 - pl["P0"]
        perp = off - (off @ pl["a"]) * pl["a"]
        print(f"other leg end {q1.round(3).tolist()}, direction {np.round([t1.X, t1.Y, t1.Z], 4).tolist()}; "
              f"axis offset {np.linalg.norm(perp):.3f}, y {q1[1]:.3f}, z {q1[2]:.3f} (target y {Q[1]:.3f}, z {pl['P0'][2] + rise:.3f})")
        tube = BP.apply(U.const_d_tube(w, D, BP.WALL), T)
        print(f"U tube D {D:g} valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
        # 直線の管: U の浮いている端(向き +X)から x = X_END まで
        from build123d import Edge, Wire

        sx = np.array([q1[0], q1[1], q1[2]])
        if abs(float(t1.X) - 1.0) > 1e-6:
            raise ValueError(f"U の端の向きが +X でない: {t1}")
        line = Wire([Edge.make_line(tuple(sx), (X_END, sx[1], sx[2]))])
        straight = U.const_d_tube(line, D, BP.WALL)
        print(f"straight tube: x {sx[0]:.3f} -> {X_END:g} at y {sx[1]:.3f}, z {sx[2]:.3f}; length {line.length:.3f}, valid {straight.is_valid}, "
              f"volume {sum(x.volume for x in straight.solids()):.2f}")
        import branch2_l as B2

        # L 字の管: 直管の右端(x = X_END)→ 角(出口の軸の延長と z=49 の交点)→ 第 4 の 2 階左下(225°)の枝管の端面
        p_start = np.array([X_END, sx[1], sx[2]])
        F, uo = f2_225_exit()
        L_ref = [o for o in others if o[0] == REF_NAME]
        if not L_ref:
            raise ValueError(f"{REF_NAME} が組立にない")
        ref = L_ref[0][1]

        def build_l(r):
            lw = l_wire(p_start, Q, F, r)
            return lw, U.const_d_tube(lw, D, BP.WALL)

        r_max = min(float(np.linalg.norm(Q - p_start)), float(np.linalg.norm(F - Q)))
        if "--R" in sys.argv:
            r_l = float(sys.argv[sys.argv.index("--R") + 1])
        else:
            scan = []
            for r in np.linspace(5.0, r_max, 9):
                scan.append((float(r), build_l(float(r))[1].distance_to(ref)))
            print("L bend R scan (R, surface distance to " + REF_NAME + "): " + ", ".join(f"({r:.2f}, {d:.3f})" for r, d in scan))
            from scipy.optimize import brentq

            fs = [d - TARGET_GAP for _, d in scan]
            br = [(scan[i][0], scan[i + 1][0]) for i in range(len(scan) - 1) if fs[i] * fs[i + 1] <= 0]
            if br:
                r_l = brentq(lambda r: build_l(r)[1].distance_to(ref) - TARGET_GAP, *br[0], xtol=1e-3)
            else:
                r_l = min(scan, key=lambda x: abs(x[1] - TARGET_GAP))[0]
                print(f"  (target {TARGET_GAP:g} is not crossed; nearest R {r_l:.2f})")
        lw, ltube = build_l(r_l)
        print(f"L tube: R {r_l:.3f} (max {r_max:.3f}), corner {Q.round(3).tolist()}, length {lw.length:.3f}, valid {ltube.is_valid}, "
              f"volume {sum(x.volume for x in ltube.solids()):.2f}; distance to {REF_NAME} {ltube.distance_to(ref):.3f}")
        print("clearance (L):")
        B2.report_clearance(ltube, others)
        print("clearance (U):")
        B2.report_clearance(tube, others)
        print("clearance (straight):")
        B2.report_clearance(straight, others)
        return (branch, [tube, straight, ltube, ww, lw], ["bb34_U_wall", "bb34_straight_wall", "bb34_L_wall", "bb34_U_centerline", "bb34_L_centerline"],
                ["#e0a020", "#e0a020", "#e0a020", "#ff2020", "#ff2020"])

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
