"""桂(フェルール)。外径 13.6 / 内径 12.8 のストレート管の外周に、飾り線(山形のリブ)が付く。管軸は Z、片端が原点。

飾り線: 底辺(管の外面上)の幅 0.4、頂角 120° の二等辺三角形断面を 360° 回転。高さ = 0.2 / tan(60°) ≈ 0.1155。
位置は、線の中心が端から 3 mm(片側)/ 2 mm(両側)。全長 L ごとに飾り線の位置(原点側の端からの距離 z)を持つ。
  L=6 : 片側(z=3)。結果として中央に1本の対称部品
  L=8 : 両側(z=2, 6)
  L=12: 片側(z=3)
"""

import math

from build123d import Align, Axis, BuildLine, BuildSketch, Cylinder, Line, Plane, make_face, revolve

OD = 13.6
ID = 12.8
R = OD / 2  # 6.8
BEAD_W = 0.4  # 底辺の幅
BEAD_APEX = 120.0  # 頂角 [deg]
BEAD_H = (BEAD_W / 2) / math.tan(math.radians(BEAD_APEX / 2))  # ≈ 0.1155
BEAD_OFFSET = 3.0  # 片側のとき、端から飾り線の中心まで
BEAD_OFFSET_BOTH = 2.0  # 両側のとき、端から飾り線の中心まで

# 全長 → 飾り線の中心の z(原点側の端から)
VARIANTS = {
    6: [BEAD_OFFSET],
    8: [BEAD_OFFSET_BOTH, 8 - BEAD_OFFSET_BOTH],
    12: [BEAD_OFFSET],
}


def _bead(zc: float):
    w = BEAD_W / 2
    with BuildSketch(Plane.XZ) as sk:  # x=半径、y=軸方向 Z
        with BuildLine():
            Line((R, zc - w), (R + BEAD_H, zc))
            Line((R + BEAD_H, zc), (R, zc + w))
            Line((R, zc + w), (R, zc - w))
        make_face()
    return revolve(sk.sketch, Axis.Z)


def ferrule(length: float, beads=None, decor: bool = True):
    """decor=False で飾り線を作らない(組立で重いとき用。管だけの形になる)。"""
    beads = VARIANTS[length] if beads is None else beads
    if not decor:
        beads = []
    solid = Cylinder(R, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for zc in beads:
        solid = solid + _bead(zc)
    return solid - Cylinder(ID / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    names = [f"ferrule_{L}" for L in VARIANTS]
    parts = [Pos(i * 25, 0, 0) * ferrule(L) for i, L in enumerate(VARIANTS)]
    show(*parts, names=names, reset_camera=Camera.KEEP)
    for L, beads in VARIANTS.items():
        f = ferrule(L)
        tube = math.pi * (R**2 - (ID / 2) ** 2) * L
        a = 0.5 * BEAD_W * BEAD_H
        expected = tube + len(beads) * 2 * math.pi * (R + BEAD_H / 3) * a  # パップス
        bb = f.bounding_box()
        print(f"L={L} beads={beads} valid={f.is_valid} volume={f.volume:.4f} expected={expected:.4f} "
              f"diff={f.volume - expected:.1e} z=[{bb.min.Z:.2f},{bb.max.Z:.2f}] r={bb.max.X:.4f}")


if __name__ == "__main__":
    main()
