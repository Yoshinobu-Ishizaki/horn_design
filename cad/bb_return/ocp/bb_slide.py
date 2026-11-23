"""Bb の戻り回路の抜差部(Bb抜差組立のレベル): 第 4 の 1 階右下の枝管 v4-knuckle-f1-315(valve4_knuckle_F1_315_45deg_minusy)の出口から
GAP mm 離して、Bb 第 2 の中管と同じ寸法の中管を同軸に置く(Bb2 とは連動しない独立の部品。長さは INNER_TUBE_LEN / --len で後から調整)。中管の先端(桂のない側)を枝管へ向ける。

    uv run python cad/bb_return/ocp/bb_slide.py [--gap 1.0]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/main_aux_tube/ocp"), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"),
                str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

GAP = 1.0
KNUCKLE = "valve4_knuckle_F1_315_45deg_minusy"
# 中管は、Bb 第 2 の中管とは連動させない独立の部品(寸法は最初に Bb2 の中管と同じ値で置き、長さは後で調整する)
INNER_TUBE_OD = 12.8
INNER_TUBE_ID = 12.0
INNER_TUBE_LEN = 33.0  # 後で調整する(Bb2 の中管の長さを変えても、ここは変わらない)


def inner_tube_part(length: float = INNER_TUBE_LEN):
    """軸は Y。先端の端面が y = 0、桂の側へ -Y に length。"""
    from build123d import Axis, Cylinder, Pos, Rot

    t = Cylinder(INNER_TUBE_OD / 2, length) - Cylinder(INNER_TUBE_ID / 2, length)
    return Pos(0, -length / 2, 0) * (Rot(-90, 0, 0) * t)


U_PITCH = 50.0
U_Z = 34.0  # もう一方の直線の軸が乗る 2 階の軸平面の高さ
U_SIDE = +1  # 軸に垂直な水平方向: +1 で +X 側、-1 で -X 側(-X 側は Bb1 などの外管に当たる)


def u_placement(P0, a, pitch, z_plane, side):
    """U の置き方。局所: 左の直線の始端 (-P/2, 0) → 接続点 P0、局所 +Y → 接続軸 a、局所 +X(もう一方の直線への向き)→ n。
    n = cos(φ)·e_h + sin(φ)·Z、sin φ = (z_plane - P0.z) / pitch。e_h は軸に垂直な水平方向(side × (a×Z) の向き、a = -Y なら side=-1 が +X)。"""
    import math

    z = np.array([0.0, 0.0, 1.0])
    e_h = np.cross(a, z)
    e_h = side * e_h / np.linalg.norm(e_h)
    t = math.asin((z_plane - P0[2]) / pitch)
    n = math.cos(t) * e_h + math.sin(t) * z
    R = np.column_stack([n, a, np.cross(n, a)])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = P0 - R @ np.array([-pitch / 2, 0.0, 0.0])
    return T, n, math.degrees(t)


def hook(M, branch, others):
    import bb_return as BR
    import branch2_l as B2
    import main_aux as MA
    from build123d import Pos

    branch, p0, n0, c0 = MA.hook(M, branch, others)  # 2番管・bb34・主管補助管も一緒に出す
    others = others + list(zip(n0, p0))

    gap = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else GAP
    P, n = BR.exit_of(KNUCKLE, (70.0, 0.0))  # 枝管の出口の端面の中心と外向きの軸(-Y)
    length = float(sys.argv[sys.argv.index("--len") + 1]) if "--len" in sys.argv else INNER_TUBE_LEN
    shift = np.array([P[0], P[1] + n[1] * gap, P[2]])  # n = (0,-1,0): 先端が出口から gap だけ -Y 側
    part = Pos(*shift) * inner_tube_part(length)
    b2 = part.bounding_box()
    print(f"{KNUCKLE} exit {P.round(3).tolist()}, out {n.round(3).tolist()}")
    print(f"placed independent inner tube (OD {INNER_TUBE_OD:g}, ID {INNER_TUBE_ID:g}, length {length:g}, volume {part.volume:.2f}): shift {shift.round(3).tolist()}; y {b2.min.Y:.3f}..{b2.max.Y:.3f}, x {b2.min.X:.2f}..{b2.max.X:.2f}, z {b2.min.Z:.2f}..{b2.max.Z:.2f}")
    ks = dict(others)[KNUCKLE]
    print(f"distance to {KNUCKLE}: {part.distance_to(ks):.3f} mm")
    B2.report_clearance(part, others)
    # 中管の先(桂の側の端 y = P.y + n.y·(gap + length))に、ピッチ U_PITCH の U 字管。接続軸(-Y)まわりに回して、もう一方の直線の軸を z = U_Z に乗せる
    import bell_place as BP
    import branch2_u as U

    pitch = float(sys.argv[sys.argv.index("--pitch") + 1]) if "--pitch" in sys.argv else U_PITCH
    side = -1 if "--side" in sys.argv and sys.argv[sys.argv.index("--side") + 1] == "minus" else (-1 if U_SIDE > 0 else 1)  # a×Z = -X なので +X 側は side=-1
    P0 = np.array([P[0], P[1] + n[1] * (gap + length), P[2]])
    T, nn, phi = u_placement(P0, n, pitch, U_Z, side)
    w, info = U.u_wire_local(pitch)
    ww = BP.apply(w, T)
    q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
    print(f"U pitch {pitch:g} at {P0.round(3).tolist()}: rotation {phi:.2f} deg, n = {nn.round(4).tolist()}, curve {info['curve_len']:.3f} + legs 2 x 5, min bend R {info['rmin']:.2f}")
    print(f"other leg end ({q1.X:.3f}, {q1.Y:.3f}, {q1.Z:.3f}), direction ({t1.X:.3f}, {t1.Y:.3f}, {t1.Z:.3f}) (z target {U_Z:g})")
    utube = BP.apply(U.const_d_tube(w, INNER_TUBE_ID, BP.WALL), T)
    print(f"U tube D {INNER_TUBE_ID:g} wall {BP.WALL:g}: valid {utube.is_valid}, volume {sum(x.volume for x in utube.solids()):.2f}; distance to the inner tube {utube.distance_to(part):.3f}")
    print("clearance (U):")
    B2.report_clearance(utube, others + [("Bb_return_inner_tube", part)])
    # U 字のもう一方の端(+Y 向き)に、中管をもう 1 本。長さは反対側の中管と同じ(INNER_TUBE_LEN を共有)。桂の側が U、先端が +Y 側
    length2 = float(sys.argv[sys.argv.index("--len2") + 1]) if "--len2" in sys.argv else length
    q = np.array([q1.X, q1.Y, q1.Z])
    part2 = Pos(q[0], q[1] + length2, q[2]) * inner_tube_part(length2)  # 先端 y = q.y + length2、桂側 y = q.y
    b3 = part2.bounding_box()
    print(f"2nd inner tube (length {length2:g}): at {q.round(3).tolist()}, y {b3.min.Y:.3f}..{b3.max.Y:.3f}, x {b3.min.X:.2f}..{b3.max.X:.2f}, z {b3.min.Z:.2f}..{b3.max.Z:.2f}; distance to the U tube {part2.distance_to(utube):.3f}")
    print("clearance (2nd inner tube):")
    B2.report_clearance(part2, others + [("Bb_return_U_wall", utube)])
    return (branch, p0 + [part, utube, ww, part2],
            n0 + ["Bb_return_inner_tube", "Bb_return_U_wall", "Bb_return_U_centerline", "Bb_return_inner_tube_2"],
            c0 + ["#e0a020", "#e0a020", "#ff2020", "#e0a020"])


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
