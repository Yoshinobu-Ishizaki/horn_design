"""植込管ユニット(ケース + 8 本の枝管)を x 方向に並べる。

隣り合う、y 方向を向いた枝管(2 本目が -Y の枝管)の軸間距離を 15 にする。
ユニット内の y 向き枝管の軸は x=±10(1 本目の方向 225° と 315°)なので、ユニットの x ピッチ(植込み中心間距離)は
  PITCH = 15 + 2·10 = 35。
このとき、ユニット 1 の 45° の枝管(2 本目が +X)と、ユニット 2 の 135° の枝管(2 本目が -X)は、端面(x=17.5)で突き合う。
"""

from build123d import Pos

from valve_assy import build

AXIS_GAP_Y = 15.0  # 隣り合う y 向き枝管の軸間距離
Y_AXIS_X = 10.0  # ユニット内の y 向き枝管の軸の x(±)
PITCH = AXIS_GAP_Y + 2 * Y_AXIS_X  # 35


def build_units(n: int = 2, pitch: float = PITCH):
    """戻り値: [(case, [knuckles], [names])] を n ユニット分(x 方向に pitch ずつずらす)。"""
    units = []
    for i in range(n):
        case, ks, names = build()
        off = Pos(i * pitch, 0, 0)
        units.append((off * case, [off * k for k in ks], [f"u{i + 1}_{nm}" for nm in names]))
    return units


def main():
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    units = build_units(2)
    parts, names = [], []
    for i, (case, ks, nms) in enumerate(units, start=1):
        parts += [case] + ks
        names += [f"u{i}_valve_case"] + nms
    show(*parts, names=names, reset_camera=Camera.KEEP)
    print(f"ピッチ {PITCH}, ユニット数 {len(units)}")


if __name__ == "__main__":
    main()
