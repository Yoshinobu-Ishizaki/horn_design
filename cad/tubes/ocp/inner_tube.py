"""中管(インナーチューブ)。外径 12.8 / 内径 12.0 のストレートパイプ。管軸は Z、片端が原点。

全長は部品種ごとに違う(既存 cad/basic_parts/inner_tube.FCStd のスプレッドシートの値)。
"""

from build123d import Cylinder, Align, Pos, Compound

OD = 12.8
ID = 12.0
LENGTHS = {"sl-b1": 71.0, "sl-b2": 42.0, "sl-b3": 56.0}  # mm


def inner_tube(length: float):
    outer = Cylinder(OD / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    bore = Cylinder(ID / 2, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return outer - bore


def main():
    from ocp_vscode import Camera
    from bope_claude_cad.viewer import show

    names = list(LENGTHS)
    parts = [Pos(i * 25, 0, 0) * inner_tube(LENGTHS[n]) for i, n in enumerate(names)]
    show(*parts, names=[f"inner_tube_{n}" for n in names], reset_camera=Camera.KEEP)
    for n in names:
        t = inner_tube(LENGTHS[n])
        print(n, f"L={LENGTHS[n]}", f"volume={t.volume:.1f}", f"valid={t.is_valid}")


if __name__ == "__main__":
    main()
