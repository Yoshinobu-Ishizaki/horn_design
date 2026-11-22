"""支柱組立の 1 例。φ13.6 の管 2 本(外管)の向かい合う側に、t=0.7 の座を巻き付け、L=2 の芯を挟む。

座標: 管軸が Z(外管と同じ、つば側が z=0)。管 1 の軸は (-a, 0)、管 2 の軸は (+a, 0)。芯の軸は X、中心は原点側。
座の外面の頂点(R = 6.8 + 0.7 = 7.5)に、芯の端面(平面)が接する。芯の中心平面は x=0 で、全体はこの面に対して対称。
中心間距離 2a は、接するとき 2·(6.8+0.7) + L = 17.0。DIST で変えられる(t=0.8 だった頃は 17.2)。
座の中央の φ3 の孔は再現しない。
"""

import math
import sys
from pathlib import Path

from build123d import Plane, Pos, Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tubes" / "ocp"))
sys.path.insert(0, str(HERE))
from outer_tube import ID as OT_ID, LENGTH as OT_LENGTH, OD as OT_OD, outer_tube  # noqa: E402

from brace_core import brace_core  # noqa: E402
from brace_plate_wrap import seat_on_cylinder, solid_volume  # noqa: E402

R_TUBE = OT_OD / 2  # 6.8
T_SEAT = 0.7
L_CORE = 2.0
DIST_CONTACT = 2 * (R_TUBE + T_SEAT) + L_CORE  # 17.0
Z_SEAT = OT_LENGTH / 2  # 座の軸方向の位置(管の中央)


def build(dist: float = DIST_CONTACT):
    a = dist / 2
    # 管 1(左、軸 (-a,0))の座は +X 向き(角度 0°)、管 2(右)の座は -X 向き(角度 180°)
    seat1, _ = seat_on_cylinder(R_TUBE, 0.0, Z_SEAT, T_SEAT)
    seat2, _ = seat_on_cylinder(R_TUBE, math.pi, Z_SEAT, T_SEAT)
    tube1 = Pos(-a, 0, 0) * outer_tube()
    tube2 = Pos(a, 0, 0) * outer_tube()
    seat1 = Pos(-a, 0, 0) * seat1
    seat2 = Pos(a, 0, 0) * seat2
    # 芯: Z 軸の 0..L を、X 軸の -L/2..+L/2 へ(Y まわり 90° 回して中心を原点側へ)
    core = Pos(0, 0, Z_SEAT) * Rot(0, 90, 0) * Pos(0, 0, -L_CORE / 2) * brace_core(L_CORE)
    return tube1, tube2, seat1, seat2, core


def overlap(a, b) -> float:
    """2 つのソリッドの重なり体積(重なりなしなら 0)。"""
    r = a.intersect(b)
    solids = r.solids() if r is not None else []
    return sum(solid_volume(x) for x in solids)


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    tube1, tube2, seat1, seat2, core = build()
    show(tube1, tube2, seat1, seat2, core,
         names=["outer_tube_1", "outer_tube_2", "brace_seat_1", "brace_seat_2", "brace_core"],
         reset_camera=Camera.KEEP)

    for dist in (DIST_CONTACT, 17.0):
        t1, t2, s1, s2, c = build(dist)
        d1, d2 = c.distance_to(s1), c.distance_to(s2)
        ov = overlap(c, s1) + overlap(c, s2)
        print(f"中心間距離 {dist}: 芯-座1 の距離 {d1:.4f}, 芯-座2 {d2:.4f}, 芯と座の重なり体積 {ov:.4f}, "
              f"座と管の重なり {overlap(s1, t1):.2e}/{overlap(s2, t2):.2e}")
    # 対称性: x=0 面で鏡映した座 1 と座 2 の体積・重心の比較
    t1, t2, s1, s2, c = build()
    m = s1.mirror(Plane.YZ)
    print(f"座 1 を x=0 で鏡映 → 座 2: 重心差 {(m.center() - s2.center()).length:.2e}, "
          f"体積差 {abs(solid_volume(m) - solid_volume(s2)):.2e}")
    cb = c.bounding_box()
    print(f"芯の範囲 x=[{cb.min.X:.4f},{cb.max.X:.4f}] y=[{cb.min.Y:.4f},{cb.max.Y:.4f}] z=[{cb.min.Z:.4f},{cb.max.Z:.4f}]")


if __name__ == "__main__":
    main()
