"""植込管の組立: ケース + 8 本の枝管(knuckle)。FreeCAD の valve_case1.FCStd の Body001〜008 と同じ配置。

各段(z = Z_LOW, Z_LOW + SPACING)に 4 本ずつ。枝管の 1 本目の方向(Z まわり、+X から)と、折れる向き:
  225° 反時計回り(+) → 2 本目は -Y      315° 時計回り(-) → 2 本目は -Y
   45° 時計回り(-)   → 2 本目は +X      135° 反時計回り(+) → 2 本目は -X
(曲がる向き - は、局所座標で y を反転した形。)
"""

from build123d import Plane, Pos, Rot

from knuckle import knuckle
from valve_case import SPACING, Z_LOW, valve_case

# (1 本目の方向 [deg], 折れる向き +1/-1)
KNUCKLE_LAYOUT = [(225.0, +1), (315.0, -1), (45.0, -1), (135.0, +1)]


def place_knuckle(angle: float, turn: int, z: float, bend: float = 45.0, twist: float = 0.0):
    """枝管 1 本を置く。angle: 1 本目の方向、turn: +1 反時計回り / -1 時計回り、z: 段の高さ。
    twist: 1 本目の軸まわりに枝管を回す角度(第 4 植込のねじり。0 なら無し。向きの扱いは要確認)。"""
    k = knuckle(bend)
    if turn < 0:
        k = k.mirror(Plane.XZ)
    if twist:
        k = Rot(twist, 0, 0) * k  # 1 本目の軸(局所 +X)まわり
    return Pos(0, 0, z) * Rot(0, 0, angle) * k


def build(spacing: float = SPACING, z_low: float = Z_LOW, bend: float = 45.0):
    case = valve_case(spacing, z_low)
    knuckles, names = [], []
    for lv, z in enumerate((z_low, z_low + spacing), start=1):
        for angle, turn in KNUCKLE_LAYOUT:
            knuckles.append(place_knuckle(angle, turn, z, bend))
            names.append(f"knuckle_L{lv}_{int(angle)}")
    return case, knuckles, names


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    case, knuckles, names = build()
    show(case, *knuckles, names=["valve_case"] + names, reset_camera=Camera.KEEP)
    print(f"case valid={case.is_valid}; knuckles={len(knuckles)} valid={all(k.is_valid for k in knuckles)}")


if __name__ == "__main__":
    main()
