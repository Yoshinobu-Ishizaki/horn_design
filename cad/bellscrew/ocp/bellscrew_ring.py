"""ベルスクリューの座(仮): bell03 の直管部の太い所を、平面 y = Y_CUT(設計の座標)で切ると考え、
そこを挟む ±HALF の円環を作る。

- 座標は bell03 の設計の座標(回す前。リム中心 (0,0)、直管部は +Y)。ベルの軸は Y 軸。
- 外側: 下面(y = Y_CUT - HALF)・上面(y = Y_CUT + HALF)の直径は、その高さのベルの外径 + EXTRA_D。
  その間は半径 ARC_R の円弧で、中央を外へ膨らませる(デザイン上の理由。ARC_R = None なら円錐台)。
- 内側はベルの外面(板厚 WALL を付けた外面)で切り取る。ベルのモデルは切らない。

    uv run python cad/bellscrew/ocp/bellscrew_ring.py [--show]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/bell03/ocp"))
sys.path.insert(0, str(ROOT / "cad/bell03/tools"))

Y_CUT = 125.0  # 切ると考える平面
HALF = 6.0  # 円環は y = Y_CUT ± HALF
EXTRA_D = 2.0  # 下面・上面の外径 = ベルの外径 + EXTRA_D
WALL = 0.4  # ベルの板厚(外向き)
ARC_R = 11.0  # 外側の断面の円弧の半径。最も厚い所(ベルの外面から半径方向)が約 3 mm になる切りのよい値


def outer_diameter(wall_solid, y: float) -> float:
    """平面 y とベルの交線のうち、最も大きい円(外面)の直径。"""
    from bell03_surface import section_edges

    return max(e.bounding_box().size.X for e in section_edges(wall_solid, y))


def build():
    from build123d import Axis, Face, Line, ThreePointArc, Wire, revolve

    from bell03_surface import LD_CSV, centerline, read_ld
    from bope_claude_cad.vss import variable_pipe_law, variable_pipe_wall

    cl = centerline()
    L, D = read_ld(LD_CSV)
    wall, _ = variable_pipe_wall(cl, L, D, WALL, method="sweep")
    bore, _ = variable_pipe_law(cl, L, D, solid=True)
    y0, y1 = Y_CUT - HALF, Y_CUT + HALF
    d0, d1 = outer_diameter(wall, y0), outer_diameter(wall, y1)
    # 断面(XY 平面、x が半径)を Y 軸まわりに回す。外側は下面の縁から上面の縁への円弧(中心はベルの軸の側)
    p0, p1 = np.array([(d0 + EXTRA_D) / 2, y0]), np.array([(d1 + EXTRA_D) / 2, y1])
    if ARC_R is None:
        side = Line((*p0, 0), (*p1, 0))
    else:
        chord = np.linalg.norm(p1 - p0)
        u = (p1 - p0) / chord
        n = np.array([u[1], -u[0]])  # 弦の法線。軸の側(-x)を向ける
        if n[0] > 0:
            n = -n
        c = (p0 + p1) / 2 + n * np.sqrt(ARC_R**2 - chord**2 / 4)
        m = c - n * ARC_R  # 円弧の中点(最も外へ出た所)
        side = ThreePointArc((*p0, 0), (*m, 0), (*p1, 0))
    prof = Face(Wire([Line((0, y0, 0), (*p0, 0)), side, Line((*p1, 0), (0, y1, 0)), Line((0, y1, 0), (0, y0, 0))]))
    body = revolve(prof, Axis.Y, 360)
    ring = body - wall - bore
    info = {"y0": y0, "y1": y1, "d0": d0, "d1": d1}
    return ring, wall, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="OCP Viewer に表示(ベルと一緒に、設計の座標で)")
    a = ap.parse_args()

    ring, wall, info = build()
    bb = ring.bounding_box()
    print(f"bell outer D: y={info['y0']:g} {info['d0']:.3f}, y={info['y1']:g} {info['d1']:.3f}")
    print(f"ring outer D: bottom {info['d0'] + EXTRA_D:.3f}, top {info['d1'] + EXTRA_D:.3f}, side arc R {ARC_R}")
    print(f"ring: solids {len(ring.solids())} faces {len(ring.faces())} valid {ring.is_valid} "
          f"volume {ring.volume:.1f} mm3, y {bb.min.Y:.3f}..{bb.max.Y:.3f}")

    # 厚さ(ベルの外面から半径方向)。平面 y で切った円の直径の差の半分
    from bell03_surface import section_edges

    ys = np.linspace(info["y0"] + 1e-3, info["y1"] - 1e-3, 121)
    t = [np.diff(sorted(e.bounding_box().size.X for e in section_edges(ring, y)))[0] / 2 for y in ys]
    i = int(np.argmax(t))
    print(f"thickness (radial): max {t[i]:.3f} mm at y {ys[i]:.2f}, bottom {t[0]:.3f}, top {t[-1]:.3f}")

    if a.show:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(wall, ring, names=[f"bell03_wall_t{WALL}", "bellscrew_ring"], colors=["#e0a020", "#3080e0"],
             alphas=[0.5, 1.0], reset_camera=Camera.KEEP, tab="tree",
             metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)


if __name__ == "__main__":
    main()
