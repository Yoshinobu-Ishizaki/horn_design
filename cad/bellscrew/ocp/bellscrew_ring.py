"""ベルスクリューの座(仮): bell03 の直管部の太い所を、平面 y = Y_CUT(設計の座標)で切ると考え、
そこを挟む ±HALF の円環を作る。

- 座標は bell03 の設計の座標(回す前。リム中心 (0,0)、直管部は +Y)。ベルの軸は Y 軸。
- 外側は円錐台: 下面(y = Y_CUT - HALF)・上面(y = Y_CUT + HALF)の直径は、その高さのベルの外径 + EXTRA_D。
- 内側はベルの外面(板厚 WALL を付けた外面)で切り取る。ベルのモデルは切らない。

    uv run python cad/bellscrew/ocp/bellscrew_ring.py [--show]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/bell03/ocp"))
sys.path.insert(0, str(ROOT / "cad/bell03/tools"))

Y_CUT = 125.0  # 切ると考える平面
HALF = 6.0  # 円環は y = Y_CUT ± HALF
EXTRA_D = 2.0  # 円錐台の直径 = ベルの外径 + EXTRA_D
WALL = 0.4  # ベルの板厚(外向き)


def outer_diameter(wall_solid, y: float) -> float:
    """平面 y とベルの交線のうち、最も大きい円(外面)の直径。"""
    from bell03_surface import section_edges

    return max(e.bounding_box().size.X for e in section_edges(wall_solid, y))


def build():
    from build123d import Align, Cone, Pos, Rot

    from bell03_surface import LD_CSV, centerline, read_ld
    from bope_claude_cad.vss import variable_pipe_law, variable_pipe_wall

    cl = centerline()
    L, D = read_ld(LD_CSV)
    wall, _ = variable_pipe_wall(cl, L, D, WALL, method="sweep")
    bore, _ = variable_pipe_law(cl, L, D, solid=True)
    y0, y1 = Y_CUT - HALF, Y_CUT + HALF
    d0, d1 = outer_diameter(wall, y0), outer_diameter(wall, y1)
    # Cone は +Z 向き。X 軸まわりに -90° で +Y 向きにして、下面を y0 に置く
    cone = Pos(0, y0, 0) * Rot(-90, 0, 0) * Cone((d0 + EXTRA_D) / 2, (d1 + EXTRA_D) / 2, y1 - y0,
                                               align=(Align.CENTER, Align.CENTER, Align.MIN))
    ring = cone - wall - bore
    info = {"y0": y0, "y1": y1, "d0": d0, "d1": d1}
    return ring, wall, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="OCP Viewer に表示(ベルと一緒に、設計の座標で)")
    a = ap.parse_args()

    ring, wall, info = build()
    bb = ring.bounding_box()
    print(f"bell outer D: y={info['y0']:g} {info['d0']:.3f}, y={info['y1']:g} {info['d1']:.3f}")
    print(f"cone D: bottom {info['d0'] + EXTRA_D:.3f}, top {info['d1'] + EXTRA_D:.3f}")
    print(f"ring: solids {len(ring.solids())} faces {len(ring.faces())} valid {ring.is_valid} "
          f"volume {ring.volume:.1f} mm3, y {bb.min.Y:.3f}..{bb.max.Y:.3f}")

    if a.show:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(wall, ring, names=[f"bell03_wall_t{WALL}", "bellscrew_ring"], colors=["#e0a020", "#3080e0"],
             alphas=[0.5, 1.0], reset_camera=Camera.KEEP, tab="tree",
             metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)


if __name__ == "__main__":
    main()
