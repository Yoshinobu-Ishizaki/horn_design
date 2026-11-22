"""外管(アウターチューブ)。外径 13.6 / 内径 12.8、全長 55 の管の片端(z=0 側)につばが付く。管軸は Z。

元: cad/basic_parts/outer_tube.FCStd (Pad 長さ 55、Sketch001 を管軸まわりに 360° Revolution)。
つばの断面(r, z)は、管の外面 r=6.8 から r=7.8、z=0〜3.6。
  (6.8,0) → (7.0,0) → R0.8 の円弧(中心 (7.0,0.8))→ (7.8,0.8)
  → R5.3 の円弧(中心 (2.5,0.8))→ (7.0,3.6) → (6.8,3.6) → (6.8,0)
"""

import math

from build123d import (
    Align, BuildLine, BuildSketch, Cylinder, CenterArc, Line, Plane, make_face, revolve, Axis,
)

OD = 13.6
ID = 12.8
LENGTH = 55.0
COLLAR_H = 3.6
COLLAR_R_IN = OD / 2  # 6.8
COLLAR_R_OUT = 7.8


def outer_tube(length: float = LENGTH):
    """length: 管の全長(つばの側 z=0 から)。既定は FreeCAD の 55。"""
    tube = Cylinder(OD / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # つば(断面は XZ 面。x=半径、y=軸方向 Z)
    a = 5.3  # 先端の円弧の半径
    cx, cy = 2.5, 0.8
    end_ang = math.degrees(math.asin((3.6 - cy) / a))  # 約 31.9°
    with BuildSketch(Plane.XZ) as sk:
        with BuildLine():
            Line((6.8, 0), (7.0, 0))
            CenterArc((7.0, 0.8), 0.8, -90, 90)  # (7.0,0) → (7.8,0.8)
            CenterArc((cx, cy), a, 0, end_ang)  # (7.8,0.8) → (7.0,3.6)
            Line((7.0, 3.6), (6.8, 3.6))
            Line((6.8, 3.6), (6.8, 0))
        make_face()
    collar = revolve(sk.sketch, Axis.Z)
    solid = tube + collar
    bore = Cylinder(ID / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return solid - bore


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from inner_tube import LENGTHS, inner_tube

    ot = outer_tube()
    names = ["outer_tube"] + [f"inner_tube_{n}" for n in LENGTHS]
    parts = [ot] + [Pos((i + 1) * 25, 0, 0) * inner_tube(L) for i, L in enumerate(LENGTHS.values())]
    show(*parts, names=names, reset_camera=Camera.KEEP)
    bb = ot.bounding_box()
    print(f"outer_tube valid={ot.is_valid} volume={ot.volume:.2f} "
          f"z=[{bb.min.Z:.2f},{bb.max.Z:.2f}] xy=±{bb.max.X:.2f}")


if __name__ == "__main__":
    main()
