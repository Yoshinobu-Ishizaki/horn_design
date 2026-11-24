"""Bb の戻り回路の抜差部(Bb抜差組立のレベル): 第 4 の 1 階右下の枝管 v4-knuckle-f1-315(valve4_knuckle_F1_315_45deg_plusx)の出口から
GAP mm 離して、Bb 第 2 の中管と同じ寸法の中管を同軸に置く(Bb2 とは連動しない独立の部品。長さは INNER_TUBE_LEN / --len で後から調整)。中管の先端(桂のない側)を枝管へ向ける。

    uv run python cad/bb_return/ocp/slide_u.py [--gap 1.0]
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
KNUCKLE = "valve4_knuckle_F1_315_45deg_plusx"
# 中管は、Bb 第 2 の中管とは連動させない独立の部品(寸法は最初に Bb2 の中管と同じ値で置き、長さは後で調整する)
INNER_TUBE_OD = 12.8
INNER_TUBE_ID = 12.0
INNER_TUBE_LEN = 33.0  # 後で調整する(Bb2 の中管の長さを変えても、ここは変わらない)


def inner_tube_part(length: float = INNER_TUBE_LEN):
    """軸は Y。先端の端面が y = 0、桂の側へ -Y に length。"""
    from build123d import Axis, Cylinder, Pos, Rot

    t = Cylinder(INNER_TUBE_OD / 2, length) - Cylinder(INNER_TUBE_ID / 2, length)
    return Pos(0, -length / 2, 0) * (Rot(-90, 0, 0) * t)


U_PITCH = 50.0  # 50 → 40 → 50(2026-11-24、組立し直し)
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
    """Bb 抜差組立は一旦削除(2026-11-24 ユーザー指示)。主管補助管までの組立(2番管・bb34・主管補助管)だけを返す。
    中管・U 字・2 本目の中管の作り方(inner_tube_part・u_placement)は残してある。"""
    if "--unsplit" in sys.argv:
        import main_aux as MA
    else:
        import main_aux_split as MA  # 主管補助管は分割版(aux1・aux2、G2 スプライン)

    branch, p0, n0, c0 = MA.hook(M, branch, others)
    others = others + list(zip(n0, p0))

    # 第 4 の 1 階右下の枝管(出口 +X)につけるピッチ U_PITCH の U 字管。接続軸(+X)まわりに回して、もう一方の直線の軸を 2 階平面(z = U_Z)に乗せる。+Y 側
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    import bb_return as BR
    from valve_row import VALVE4_X

    P, n = BR.exit_of(KNUCKLE, (VALVE4_X, 0.0))  # 枝管の出口の端面の中心と外向きの軸(+X)
    pitch = float(sys.argv[sys.argv.index("--pitch") + 1]) if "--pitch" in sys.argv else U_PITCH
    side = +1 if "--side" in sys.argv and sys.argv[sys.argv.index("--side") + 1] == "minus" else -1  # a×Z = -Y(a = +X)なので、+Y 側は side=-1
    T, nn, phi = u_placement(P, n, pitch, U_Z, side)
    w, info = U.u_wire_local(pitch)
    ww = BP.apply(w, T)
    q1, t1 = ww.position_at(1.0), ww.tangent_at(1.0)
    print(f"{KNUCKLE} exit {P.round(3).tolist()}, out {n.round(3).tolist()}")
    print(f"U pitch {pitch:g}: rotation {phi:.2f} deg about the exit axis, n = {nn.round(4).tolist()}, curve {info['curve_len']:.3f} + legs 2 x 5 = {w.length:.3f}, min bend R {info['rmin']:.2f}, height {info['h']:.2f}")
    print(f"other leg end ({q1.X:.3f}, {q1.Y:.3f}, {q1.Z:.3f}), direction ({t1.X:.3f}, {t1.Y:.3f}, {t1.Z:.3f}) (z target {U_Z:g})")
    utube = BP.apply(U.const_d_tube(w, INNER_TUBE_ID, BP.WALL), T)
    print(f"U tube D {INNER_TUBE_ID:g} wall {BP.WALL:g}: valid {utube.is_valid}, volume {sum(x.volume for x in utube.solids()):.2f}")
    print("clearance (U):")
    B2.report_clearance(utube, others)
    return branch, p0 + [utube, ww], n0 + ["v4_f1_315_U_wall", "v4_f1_315_U_centerline"], c0 + ["#e0a020", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
