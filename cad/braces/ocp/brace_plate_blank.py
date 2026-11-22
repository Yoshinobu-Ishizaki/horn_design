"""支柱座(葉形)の、曲げる前の平らなブランク。

座標: 長手(巻き付ける方向)が X、幅が Y、中心が原点。板の面は z=0、厚みは +Z 側(外向き)に t。
  ※管に貼るときは z=0 の面が管の外面に接する想定(貼り付けは claude_cad_surface_map)。

輪郭: 弦 CHORD=18(長手の両端の尖点間)、中央の幅 WIDTH=6 の葉形。
  2 本の円弧を中心線(X 軸)に対して対称に置く。矢高 s=WIDTH/2=3 から、円弧の半径
  R = ((CHORD/2)² + s²) / (2 s) = 15。両端の尖点に R0.8 の丸みを付ける。
  丸みの分だけ、実際の長さは CHORD(18)より短くなる(16.784。丸みの中心は円弧の中心から R15-0.8=14.2 の位置)。
厚み t は 0.4 または 0.7(0.8 から変更)。
"""

import math

from build123d import BuildLine, BuildSketch, ThreePointArc, extrude, fillet, make_face

CHORD = 18.0
WIDTH = 6.0
CORNER_R = 0.8
THICKNESSES = (0.4, 0.7)
SAGITTA = WIDTH / 2
ARC_R = ((CHORD / 2) ** 2 + SAGITTA**2) / (2 * SAGITTA)  # 15


def blank_face(corner_r: float = CORNER_R):
    h = CHORD / 2
    with BuildSketch() as sk:
        with BuildLine():
            ThreePointArc((-h, 0), (0, SAGITTA), (h, 0))
            ThreePointArc((h, 0), (0, -SAGITTA), (-h, 0))
        make_face()
        if corner_r > 0:
            fillet(sk.vertices(), corner_r)
    return sk.sketch


def brace_plate_blank(thickness: float = 0.8, corner_r: float = CORNER_R):
    assert thickness in THICKNESSES or thickness > 0
    return extrude(blank_face(corner_r), thickness)


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    parts = [Pos(0, i * 10, 0) * brace_plate_blank(t) for i, t in enumerate(THICKNESSES)]
    show(*parts, names=[f"brace_plate_blank_t{t}" for t in THICKNESSES], reset_camera=Camera.KEEP)

    # 検算
    phi = math.asin((CHORD / 2) / ARC_R)
    lens = 2 * (ARC_R**2 / 2) * (2 * phi - math.sin(2 * phi))  # 丸みを付ける前の面積
    f0, f = blank_face(0).area, blank_face().area
    print(f"ARC_R={ARC_R:.4f}  丸みなし面積={f0:.4f} (式 {lens:.4f})  丸みあり面積={f:.4f}")
    bb = blank_face().bounding_box()
    print(f"丸みあり: 長さ={bb.size.X:.4f}  幅={bb.size.Y:.4f}")
    for t in THICKNESSES:
        s = brace_plate_blank(t)
        print(f"t={t}: valid={s.is_valid} volume={s.volume:.4f} (面積×t={f * t:.4f}) z=[{s.bounding_box().min.Z},{s.bounding_box().max.Z}]")
    # 巻き付け角(接する面で長さを保つとして)
    for name, od in (("中管", 12.8), ("外管", 13.6)):
        for L, lab in ((CHORD, "丸みなし 18"), (bb.size.X, "丸みあり")):
            print(f"{name} φ{od}: {lab} {L:.3f} → 巻き付け角 {math.degrees(L / (od / 2)):.1f}°(上限 180°)")


if __name__ == "__main__":
    main()
