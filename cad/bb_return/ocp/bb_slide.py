"""Bb の戻り回路の抜差部(Bb抜差組立のレベル): 第 4 の 1 階右下の枝管 v4-knuckle-f1-315(valve4_knuckle_F1_315_45deg_minusy)の出口から
GAP mm 離して、Bb 第 2 の中管(Bb2 inner_tube_R)と同じ部品を同軸に置く。中管の先端(桂のない側)を枝管へ向ける。

    uv run python cad/bb_return/ocp/bb_slide.py [--gap 1.0]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"),
                str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

GAP = 1.0
KNUCKLE = "valve4_knuckle_F1_315_45deg_minusy"
SRC = ("Bb2", "inner_tube_R")


def hook(M, branch, others):
    import all_slides as A
    import bb_return as BR
    import branch2_l as B2
    from build123d import Pos

    gap = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else GAP
    P, n = BR.exit_of(KNUCKLE, (70.0, 0.0))  # 枝管の出口の端面の中心と外向きの軸(-Y)
    src = A.collect()[SRC[0]][SRC[1]]
    bb = src.bounding_box()
    c = bb.center()
    # 元の中管: 軸は Y(x, z が中心)。先端 = 桂のない側 = 外管の中に入る側(Y が大きい方)
    tip = bb.max.Y
    shift = np.array([P[0] - c.X, P[1] + n[1] * gap - tip, P[2] - c.Z])  # n = (0,-1,0): 先端が出口から gap だけ -Y 側
    part = Pos(*shift) * src
    b2 = part.bounding_box()
    print(f"{KNUCKLE} exit {P.round(3).tolist()}, out {n.round(3).tolist()}")
    print(f"placed {SRC[0]} {SRC[1]}: shift {shift.round(3).tolist()}; y {b2.min.Y:.3f}..{b2.max.Y:.3f}, x {b2.min.X:.2f}..{b2.max.X:.2f}, z {b2.min.Z:.2f}..{b2.max.Z:.2f}")
    ks = dict(others)[KNUCKLE]
    print(f"distance to {KNUCKLE}: {part.distance_to(ks):.3f} mm")
    B2.report_clearance(part, others)
    return branch, [part], ["Bb_return_inner_tube"], ["#e0a020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
