"""主管抜差(main-slide)の設計。まず、モデル済みの部品(ベル・1番管・2番管・bb34・主管補助管 aux1/aux2・Bb 抜差・Bb 戻り)を全部出し、
主管抜差の中管を 1 本置く: Bb 第 2 の中管と同じ長さ(INNER_TUBE_LEN)、補助管 2 の右側の口(終端、向き +X)の先へ GAP mm 離して同軸に。

    uv run python cad/main_slide/ocp/main_slide.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "cad/bb_return/ocp"), str(ROOT / "cad/main_aux_tube/ocp"), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"),
                str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

GAP = 1.0  # 補助管 2 の口から中管の桂の側の端まで


def hook(M, branch, others):
    import bb_return as BR
    import branch2_l as B2
    import slide_u as SU
    from build123d import Pos, Rot

    branch, p0, n0, c0 = BR.hook(M, branch, others)
    others = others + list(zip(n0, p0))
    d = dict(zip(n0, p0))
    if "main_aux2_wall" not in d:  # 主管補助管 2 はやり直し中(2026-11-24)。中管は置かない
        print("main-slide inner tube: skipped (no main_aux2)")
        return branch, p0, n0, c0
    ref = d["main_aux2_wall"]
    # 補助管 2 の口 = 補助管 2 の芯線の終点(向き +X)
    q = d["main_aux2_centerline"].position_at(1.0)
    P = np.array([q.X, q.Y, q.Z])
    length = SU.INNER_TUBE_LEN
    # inner_tube_part は軸 Y(先端 y = 0、桂側へ -Y)。Z まわり +90° で軸 +X(先端 x = 0、桂側へ +X)
    part = Pos(*(P + np.array([GAP, 0.0, 0.0]))) * (Rot(0, 0, 90) * SU.inner_tube_part(length))
    bb = part.bounding_box(optimal=False)
    print(f"main-slide inner tube (length {length:g}): aux2 opening {P.round(3).tolist()}, x {bb.min.X:.3f}..{bb.max.X:.3f}, y {bb.min.Y:.3f}..{bb.max.Y:.3f}, z {bb.min.Z:.3f}..{bb.max.Z:.3f}; "
          + (f"distance to aux2 {part.distance_to(ref):.3f}" if B2.checks_enabled() else ""))
    B2.report_clearance(part, others)
    return branch, p0 + [part], n0 + ["main_slide_inner_tube"], c0 + ["#e0a020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
