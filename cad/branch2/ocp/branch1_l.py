"""1番管の細い端を L 字に曲げて、第 4 の 2 階右下の枝管(2 階左下の鏡像、valve4_knuckle.mirrored_twisted_knuckle_2f)につなぐ(2026-11-24)。

- 角 Q: 枝管の出口の軸とベル平面(ベルの芯線の平面)の交点。1番管の末端の直線の軸は Q を通る(make_centerline.BRANCH_END_DY)。
- 1番管は Q の手前 LEG_B1(= 出口から Q までと同じ長さ)で終わる(make_centerline.BRANCH_END_S)。
- そこから枝管の出口までを、bb34 の L 字管(cad/bb34/ocp/g2_l.py)と同じ形でつなぐ: 直線 + 5 次ベジェ(両端の曲率 0 = 直線と G2)+ 直線。
  平面は 1番管の末端の直線と出口の軸を含む平面。枝管側の直線は EN_MIN(5 mm)以上、1番管側の直線は ST_MIN(0 以上)。最小曲げ半径が最大になるように。
- 管は内径 ⌀12 一定(2番管と同じ扱い。1番管の末端の内径は ⌀12 より少し太い)、板厚はベルと同じ。

    python3 cad/valves/ocp/warm.py run cad/branch2/ocp/branch1_l.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"), str(ROOT / "cad/bows/ocp"),
                str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

D = 12.0
EN_MIN = 5.0  # 枝管側の直線の最小長さ(ユーザー指示: 枝管の接続部に 5 mm 以上の直線)
ST_MIN = 0.0  # 1番管側の直線の最小長さ(1番管の直線がその手前に続く)


def knuckle_exit():
    """第 4 の 2 階右下の枝管の出口の端面の中心と、外向きの軸(ワールド)。"""
    import valve4_knuckle as V

    a_ring = math.pi / 4 * (12.8**2 - 12.0**2)
    k = V.mirrored_twisted_knuckle_2f()
    f = max((f for f in k.faces() if f.geom_type.name == "PLANE" and abs(f.area - a_ring) < 0.5), key=lambda f: -f.normal_at().Y)
    return np.array(list(f.center())), np.array(list(f.normal_at()))


def corner(M):
    """角 Q(出口の軸とベル平面の交点)と、出口から Q までの長さ。"""
    P, a = knuckle_exit()
    N, org = M[:3, :3] @ np.array([0.0, 0.0, 1.0]), M[:3, 3]
    t = -float((P - org) @ N) / float(a @ N)
    return P + t * a, t


def hook(M, branch, others):
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    import g2_l as GL

    P, a = knuckle_exit()
    Q, leg = corner(M)
    E, ex = B2.branch1_end(M)  # 1番管の末端(ワールド)と向き
    ex = ex / np.linalg.norm(ex)
    d2 = -a  # 枝管へ入る向き
    off = Q - E
    print(f"valve 4 floor-2 lower-right (mirror) exit {P.round(3).tolist()}, axis {a.round(4).tolist()}; corner Q (exit axis x bell plane) {Q.round(3).tolist()}, exit -> Q {leg:.3f}")
    print(f"branch1 end {E.round(3).tolist()}, direction {ex.round(5).tolist()}; Q - end: along {float(off @ ex):.3f}, off the axis {np.linalg.norm(off - (off @ ex) * ex):.2e}")
    v = GL.solve(E, ex, P, d2, st_min=ST_MIN, en_min=EN_MIN)
    lw, nrm, kap, clen = GL.wire(E, ex, P, d2, v)
    tube = U.const_d_tube(lw, D, BP.WALL, nrm)
    print(f"branch1 L (G2): straight {v[0]:.3f} + quintic Bezier {clen:.3f} + straight {v[1]:.3f} (knuckle side, >= {EN_MIN:g}) = {lw.length:.3f}; "
          f"min bend R {1 / np.abs(kap).max():.2f}, curvature ends {kap[0]:.1e} / {kap[-1]:.1e}; plane normal {nrm.round(4).tolist()}; "
          f"tube D {D:g} valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance (branch1 L):")
    B2.report_clearance(tube, others)
    return branch, [tube, lw], ["branch1_L_wall", "branch1_L_centerline"], ["#20c0a0", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
