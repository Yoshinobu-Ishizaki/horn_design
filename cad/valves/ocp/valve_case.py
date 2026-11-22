"""植込管のケース(valve の外側の部品)。FreeCAD の valve_case1.FCStd の Body(簡略モデル)を build123d で作り直したもの。

座標: 中心軸が Z。回転体のプロファイル(r, z)を Z まわりに回し、側面に ±45° 方向の R6 の貫通穴を 2 段(z = Z_LOW と Z_LOW + SPACING)開ける。
  外形: 小径部 R5.5(z=-11〜-3.5)、フランジ R15(z=-3.5〜-1)、胴 R13(z=-1〜42.5)、上端の段 R12.65(z=42.5〜47)
  内側: 上端 R11(z=47)から R9.565(z=-0.5)へテーパー(1.73°)、R5.5 の段、下の小径部の穴は R3.75(z=0)から R3.418(z=-11)へ同じテーパー
  穴(枝管の取り付け口): 軸が中心軸を通る方向 ±45°(+X+Y 方向と +X-Y 方向)、R6、全貫通。
2 つの穴の段(平面)の間隔は 17(元の FreeCAD と同じ。一度 17.2 にしたが 17 に戻した)。下の段 z=13、上の段 z=30。
"""

import math

from build123d import Axis, BuildLine, BuildSketch, Cylinder, Line, Plane, Pos, Rot, make_face, revolve

TAPER_DEG = 1.73
R_TOP_IN = 11.0
Z_TOP = 47.0
Z_BORE_END = -0.5
R_BORE_END = R_TOP_IN - (Z_TOP - Z_BORE_END) * math.tan(math.radians(TAPER_DEG))  # 9.565
R_NECK_IN_TOP = 3.75  # 下の小径部の穴(z=0 で)
R_NECK_IN_BOT = R_NECK_IN_TOP - 11.0 * math.tan(math.radians(TAPER_DEG))  # 3.418 (z=-11)

R_HOLE = 6.0
Z_LOW = 13.0
SPACING = 17.0
HOLE_ANGLES = (45.0, -45.0)  # 穴の軸の方向(Z まわり、+X から)


def profile_points():
    return [
        (5.5, -11.0),
        (5.5, -3.5),
        (15.0, -3.5),
        (15.0, -1.0),
        (13.0, -1.0),
        (13.0, 42.5),
        (12.65, 42.5),
        (12.65, Z_TOP),
        (R_TOP_IN, Z_TOP),
        (R_BORE_END, Z_BORE_END),
        (5.5, Z_BORE_END),
        (5.5, 0.0),
        (R_NECK_IN_TOP, 0.0),
        (R_NECK_IN_BOT, -11.0),
    ]


def valve_case(spacing: float = SPACING, z_low: float = Z_LOW):
    pts = profile_points()
    with BuildSketch(Plane.XZ) as sk:  # x=半径、y=Z
        with BuildLine():
            for a, b in zip(pts, pts[1:] + pts[:1]):
                Line(a, b)
        make_face()
    body = revolve(sk.sketch, Axis.Z)
    for z in (z_low, z_low + spacing):
        for ang in HOLE_ANGLES:
            hole = Pos(0, 0, z) * Rot(0, 0, ang) * Rot(0, 90, 0) * Cylinder(R_HOLE, 60)
            body = body - hole
    return body


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    case = valve_case()
    show(case, names=["valve_case"], reset_camera=Camera.KEEP)
    bb = case.bounding_box()
    print(f"valid={case.is_valid} volume={case.volume:.2f} faces={len(case.faces())} "
          f"x=[{bb.min.X:.2f},{bb.max.X:.2f}] z=[{bb.min.Z:.2f},{bb.max.Z:.2f}]  上の段 z={Z_LOW + SPACING}")


if __name__ == "__main__":
    main()
