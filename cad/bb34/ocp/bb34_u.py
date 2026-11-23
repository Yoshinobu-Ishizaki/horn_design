"""Bb の第 3 → 第 4 の回路: 第 3 植込の 2 階・左上(135°)の枝管(valve3_knuckle_L1_45、出口 -X)に、ピッチ 40 の U 字をつなぐ。

- U 字の曲がりは基本の U 字管(cad/bows/ocp/ubows.py、直管 LEG = 5)と同じ。内径は ⌀12.0 一定、板厚はベルと同じ。
- 出口の軸(-X)まわりに U を回して、もう一方の直線の軸が、水平面 z = 34 + RISE(= 49)に乗るようにする
  (ユーザー指示。傾き 15° ではなく、高さ 15)。ピッチ 40 なので n の z 成分 = RISE / ピッチ(回転角 asin(15/40) = 22.02°)。
  向きは -Y 側(n = (0, -cos, +sin))。逆側は --side plus(+Y 側)。
- 管体組立(cad/bellscrew/ocp/assy_with_valves.py)の hook で足す。座標は管体組立のワールド。

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

PITCH = 40.0
RISE = 15.0  # もう一方の直線の軸の高さ: 2 階の軸平面(z = 34)から +15
D = 12.0
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
    pitch, rise = arg("--pitch", PITCH), arg("--rise", RISE)
    side = +1 if "--side" in sys.argv and sys.argv[sys.argv.index("--side") + 1] == "plus" else -1

    def hook(M, branch, others):
        w, info = U.u_wire_local(pitch)
        T, pl = placement(pitch, rise, side)
        ww = BP.apply(w, T)
        q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
        q1 = np.array([q1.X, q1.Y, q1.Z])
        print(f"exit {KNUCKLE}: {pl['P0'].round(3).tolist()}, axis {pl['a'].round(4).tolist()}")
        print(f"U pitch {pitch:g}: curve {info['curve_len']:.3f} + legs 2 x 5, total {w.length:.3f}; min bend R {info['rmin']:.2f}, "
              f"height {info['h']:.2f}")
        print(f"n = {pl['n'].round(4).tolist()} (rotation {math.degrees(math.asin(rise / pitch)):.2f} deg, rise {rise:g}, side {'+Y' if side > 0 else '-Y'})")
        off = q1 - pl["P0"]
        perp = off - (off @ pl["a"]) * pl["a"]
        print(f"other leg end {q1.round(3).tolist()}, direction {np.round([t1.X, t1.Y, t1.Z], 4).tolist()}; "
              f"axis offset {np.linalg.norm(perp):.3f}, z {q1[2]:.3f} (target {pl['P0'][2] + rise:.3f})")
        tube = BP.apply(U.const_d_tube(w, D, BP.WALL), T)
        print(f"U tube D {D:g} valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
        import branch2_l as B2

        B2.report_clearance(tube, others)
        return branch, [tube, ww], ["bb34_U_wall", "bb34_U_centerline"], ["#e0a020", "#ff2020"]

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
