"""植込管 3 つを x 方向に並べる(第 3 / 第 2 / 第 1 = x が -35 / 0 / +35)。

各植込管はユニット(ケース + 8 本の枝管、valve_assy.build())を、向きを反転して置く:
  ケースの上端(フランジのない側の端面、元の座標で z=47)を Z=0 の面に置き、Z 方向が逆を向くようにする。
  変換: (x, y, z) → (X0 - x, y, 47 - z)   … Y 軸まわり 180° 回転(x 反転・z 反転)して z を +47 動かし、x を X0 に置く。
  回転は Y 軸まわり(-Y 向きの枝管は -Y のまま)。X 軸まわりにする案もある(要確認)。
植込み中心間距離は 35(valve_units.py、隣り合う y 向き枝管の軸間距離 15)。
"""

from build123d import Pos, Rot

from valve_assy import build
from valve_units import PITCH

Z_TOP = 47.0  # ケース上端(フランジのない側)の元の z
VALVES = {"valve2": 0.0, "valve1": +PITCH, "valve3": -PITCH}  # 名前 → x


def place_unit(x0: float):
    case, ks, names = build()
    T = Pos(x0, 0, Z_TOP) * Rot(0, 180, 0)
    return T * case, [T * k for k in ks], names


def build_row():
    out = {}
    for vname, x0 in VALVES.items():
        case, ks, names = place_unit(x0)
        out[vname] = (case, ks, [f"{vname}_{n}" for n in names])
    return out


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    row = build_row()
    parts, names = [], []
    for vname, (case, ks, nms) in row.items():
        parts += [case] + ks
        names += [f"{vname}_case"] + nms
    show(*parts, names=names, reset_camera=Camera.KEEP)
    for vname, (case, ks, nms) in row.items():
        bb = case.bounding_box()
        print(f"{vname}: x 中心 {VALVES[vname]:+.0f}  case z=[{bb.min.Z:.3f},{bb.max.Z:.3f}]")


if __name__ == "__main__":
    main()
