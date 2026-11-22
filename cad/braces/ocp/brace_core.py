"""支柱芯。菱形断面の回転体。両端の直径 3.5、中央の直径 5。長さ L は様々(最小 2 mm)。

軸は Z、片端が原点。半断面(r, z)は (0,0)-(1.75,0)-(2.5,L/2)-(1.75,L)-(0,L) を Z 軸まわりに回転。
(両端は直径 3.5 の平らな面、そこから中央へ直線で直径 5 まで太る。円すい台 2 つを合わせた形)
座の中央の φ3 の孔は、モデルが重くなるので座の側には再現しない。
"""

import math

from build123d import Axis, BuildLine, BuildSketch, Line, Plane, make_face, revolve

D_END = 3.5
D_MID = 5.0
L_MIN = 2.0


def brace_core(length: float):
    assert length >= L_MIN, f"長さは {L_MIN} mm 以上"
    r0, r1, h = D_END / 2, D_MID / 2, length / 2
    with BuildSketch(Plane.XZ) as sk:  # x=半径、y=軸方向 Z
        with BuildLine():
            Line((0, 0), (r0, 0))
            Line((r0, 0), (r1, h))
            Line((r1, h), (r0, length))
            Line((r0, length), (0, length))
            Line((0, length), (0, 0))
        make_face()
    return revolve(sk.sketch, Axis.Z)


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    lengths = [2.0, 5.0, 10.0]  # 2 は最小。5, 10 は表示用のサンプル
    parts = [Pos(i * 8, 0, 0) * brace_core(L) for i, L in enumerate(lengths)]
    show(*parts, names=[f"brace_core_L{L:g}" for L in lengths], reset_camera=Camera.KEEP)
    r0, r1 = D_END / 2, D_MID / 2
    for L in lengths:
        c = brace_core(L)
        h = L / 2
        expected = 2 * math.pi * h / 3 * (r0**2 + r0 * r1 + r1**2)  # 円すい台 2 つ
        bb = c.bounding_box()
        print(f"L={L:g}: valid={c.is_valid} volume={c.volume:.4f} expected={expected:.4f} "
              f"z=[{bb.min.Z:.3f},{bb.max.Z:.3f}] 最大径={2 * bb.max.X:.3f} faces={len(c.faces())}")


if __name__ == "__main__":
    main()
