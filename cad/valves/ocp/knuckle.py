"""枝管(knuckle / elbow)。外径 12.8 / 内径 12.0 の管が、角で bend 度だけ折れ曲がる。

FreeCAD の valve_case1.FCStd の Body001(基本は 45°)を build123d で作り直したもの。
局所座標(ケースの軸上の点が原点、z=0 の平面内で曲がる):
  経路: 原点 → 角 C = (D1, 0, 0) → C + L2·(cos(bend), sin(bend), 0)
  1 本目の直線: 原点から s=S_START(=7)〜 C(始端は経路に垂直な平面で切る)
  2 本目の直線: C から長さ L2(=7.5)(端面は 2 本目の経路に垂直)
  角: FreeCAD の Pipe の遷移「Round」なので、角 C を中心とする球(半径 = 管の半径)が付く。
元の寸法: D1 = 10·√2 ≈ 14.142(原点から角まで)、L2 = 7.5、S_START = 7。
bend は 45°(基本)。54°・60° などのバリエーションを想定(どの寸法を固定するかは要確認)。
曲がる向きは +Y 側(反時計回り)。place_like_freecad_body001() で、FreeCAD の Body001 と同じ位置(z=13、1 本目が 225° 方向)に置く。
"""

import math

from build123d import Align, Cylinder, Plane, Pos, Rot, Sphere, Vector

OD = 12.8
ID = 12.0
D1 = 10 * math.sqrt(2)  # 原点から角まで
L2 = 7.5
S_START = 7.0
EPS = 0.5  # 内側の穴を端面から出す余裕


def _cyl(r: float, p0: Vector, direction: Vector, length: float):
    pl = Plane(origin=p0, z_dir=direction)
    return pl * Cylinder(r, length, align=(Align.CENTER, Align.CENTER, Align.MIN))


def knuckle(bend: float = 45.0, d1: float = D1, l2: float = L2, s_start: float = S_START, od: float = OD, id_: float = ID):
    ro, ri = od / 2, id_ / 2
    u1 = Vector(1, 0, 0)
    u2 = Vector(math.cos(math.radians(bend)), math.sin(math.radians(bend)), 0)
    c = u1 * d1
    p0 = u1 * s_start
    outer = (
        _cyl(ro, p0, u1, d1 - s_start)
        + _cyl(ro, c, u2, l2)
        + Pos(c.X, c.Y, c.Z) * Sphere(ro)
    )
    inner = (
        _cyl(ri, u1 * (s_start - EPS), u1, d1 - s_start + EPS)
        + _cyl(ri, c, u2, l2 + EPS)
        + Pos(c.X, c.Y, c.Z) * Sphere(ri)
    )
    return outer - inner


def place_like_freecad_body001(k, z: float = 13.0):
    """FreeCAD の Body001 と同じ位置(1 本目が 225° 方向、z=13)に置く。"""
    return Pos(0, 0, z) * Rot(0, 0, 225) * k


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    from valve_case import valve_case

    k = place_like_freecad_body001(knuckle(45.0))
    show(valve_case(), k, names=["valve_case", "knuckle_45"], reset_camera=Camera.KEEP)
    print(f"valid={k.is_valid} volume={k.volume:.3f} faces={len(k.faces())}")


if __name__ == "__main__":
    main()
