"""植込管を x 方向に並べる(第 3 / 第 2 / 第 1 / 第 4 = x が -35 / 0 / +35 / +70)。
第 4 植込は暫定で、枝管なし(ケースだけ)。第 4 植込のねじり(枝管を回して組み込む)はこれから。

各植込管はユニット(ケース + 8 本の枝管、valve_assy.build())を、向きを反転して置く:
  ケースの上端(フランジのない側の端面、元の座標で z=47)を Z=0 の面に置き、Z 方向が逆を向くようにする。
  変換: (x, y, z) → (X0 - x, y, 47 - z)   … Y 軸まわり 180° 回転(x 反転・z 反転)して z を +47 動かし、x を X0 に置く。
  回転は Y 軸まわり(-Y 向きの枝管は -Y のまま)。X 軸まわりにする案もある(要確認)。
植込み中心間距離は 35(valve_units.py、隣り合う y 向き枝管の軸間距離 15)。
"""

from build123d import Pos, Rot

from valve_assy import build
from valve_case import valve_case
from valve_units import PITCH

Z_TOP = 47.0  # ケース上端(フランジのない側)の元の z
VALVES = {"valve2": 0.0, "valve1": +PITCH, "valve3": -PITCH, "valve4": +2 * PITCH}  # 名前 → x
NO_KNUCKLE = {"valve4"}  # 枝管を付けない植込(暫定)

# 第 4 植込の孔(ワールドの角度 [deg]、+x から反時計回り)。各階 3 個。
#   1 階(F 階、z 小 = z=17): 第 1 側(-x)の (-x,+y) の孔(135°)をやめる → 45°, 225°, 315°
#   2 階(B 階、z 大 = z=34): (+x,+y) の孔(45°)をやめる → 135°, 225°, 315°
VALVE4_HOLES_WORLD = {"F1": [45.0, 225.0, 315.0], "F2": [135.0, 225.0, 315.0]}


def valve4_case():
    """第 4 植込のケース(孔 6 個)。ケースの座標へ変換して作る: 反転(x → -x, z → 47 - z)なので、
    ワールドの角度 φ はケースの角度 180° - φ、ワールドの階 F1(z=17)/F2(z=34)はケースの z=30/13。"""
    to_local = lambda angs: [(180.0 - a) % 360.0 for a in angs]
    z_f1_local, z_f2_local = Z_TOP - 17.0, Z_TOP - 34.0  # 30, 13
    return valve_case(openings={z_f1_local: to_local(VALVE4_HOLES_WORLD["F1"]),
                                z_f2_local: to_local(VALVE4_HOLES_WORLD["F2"])})


def place_unit(x0: float, knuckles: bool = True):
    case, ks, names = build()
    T = Pos(x0, 0, Z_TOP) * Rot(0, 180, 0)
    if not knuckles:
        return T * valve4_case(), [], []
    return T * case, [T * k for k in ks], names


def build_row():
    out = {}
    for vname, x0 in VALVES.items():
        case, ks, names = place_unit(x0, vname not in NO_KNUCKLE)
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
