"""ベルスクリュー(詳細): bellscrew_ring.py の円環を、平面 y = Y_SPLIT でオス・メスに分けてねじにする。

- 座標は bell03 の設計の座標(回す前。リム中心 (0,0)、直管部は +Y)。ベルの軸は Y 軸。
- 円環は y = Y_SPLIT - THREAD_LEN - FLANGE .. Y_SPLIT + ABOVE(分割面と一緒に動く)。
  外側は bellscrew_ring.py と同じ考え方の円弧(半径 ARC_R)。端の直径は D_BOT(下端)・D_TOP(上端)。
- オス(下側、リム側): 分割面のすぐ下 THREAD_LEN がおねじ(M80×1)、その下の FLANGE が外側の円弧のツバ。
- メス(上側): y = Y_SPLIT - THREAD_LEN .. Y_SPLIT + ABOVE。分割面より下の THREAD_LEN はおねじにかぶさる
  めねじ、分割面より上はベルの外面に沿う。外から見える合わせ目は y = Y_SPLIT - THREAD_LEN。
- 内側はどちらもベルの外面(板厚 WALL)で切り取る。ベルのモデルは切らない。
- 既定は、組立のモデルを軽くするため、ねじもオス・メスの分割もない、組み合わせた状態の外形だけ。
  `--detail` でオス・メスに分けてねじを付ける。
- ねじは ISO の基準山形(60°、山頂の平らは P/8、谷は P/4 の平ら)を螺旋に沿って掃引した形。
  おねじは半径で CLEAR だけ小さくして、めねじとのすき間にする(公差域は未決)。

    uv run python cad/bellscrew/ocp/bellscrew_thread.py [--show] [--detail]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/bell03/ocp"))
sys.path.insert(0, str(ROOT / "cad/bell03/tools"))

Y_SPLIT = 131.0  # 分割面。おねじは y = Y_SPLIT - THREAD_LEN .. Y_SPLIT。ねじ部の下端でおねじの谷の下が
# 0.78 mm(132 で 1.02 mm、127 以下ではベルの外径がおねじの谷の径より太い)。132 から 1 mm 下げた
FLANGE = 2.0  # オスのツバの厚さ(軸方向)
ABOVE = 6.0  # 分割面から円環の上端まで
THREAD_D = 80.0  # M80
PITCH = 1.0  # P1
THREAD_LEN = 4.0  # ねじ部の長さ
CLEAR = 0.05  # おねじを半径で小さくする量(めねじとのすき間)
D_BOT = 80.0  # 下端の外径。最初は 82(めねじの肉厚 1 mm から)で、厚すぎたので -2
D_TOP = 74.0  # 上端の外径。最初は 82 で、厚すぎたので -8
ARC_R = 10.0  # 外側の断面の円弧の半径(見た目で R10。R11 ではめねじの外が 0.3〜0.6 mm と薄く、R8 は膨らみすぎ)
WALL = 0.4  # ベルの板厚(外向き)

H = math.sqrt(3) / 2 * PITCH  # 基準山形のとがり山の高さ
D1 = THREAD_D - 1.0825 * PITCH  # めねじの内径(78.917)
D3 = THREAD_D - 1.2269 * PITCH  # おねじの谷の径(78.773)


def tooth_face(r_in: float, r_out: float, w_out: float):
    """ねじ山の断面(XZ 平面、x が半径、z が軸方向)。60° の台形で、r_out での幅が w_out。"""
    from build123d import Face, Vector, Wire

    w_in = w_out + 2 * (r_out - r_in) * math.tan(math.radians(30))
    pts = [(r_in, -w_in / 2), (r_out, -w_out / 2), (r_out, w_out / 2), (r_in, w_in / 2)]
    return Face(Wire.make_polygon([Vector(x, 0, z) for x, z in pts]))


def helix_tooth(r_in: float, r_out: float, w_out: float, y0: float, y1: float):
    """y0..y1 の範囲に切りそろえた、螺旋のねじ山(右ねじ、軸は Y)。"""
    from build123d import Align, Cylinder, Helix, Location, Pos, Rot, sweep

    z0 = -PITCH  # 両端を1ピッチずつ長く掃引してから切る
    path = Helix(PITCH, (y1 - y0) + 2 * PITCH, (r_in + r_out) / 2, center=(0, 0, z0))
    prof = tooth_face(r_in, r_out, w_out).moved(Location((0, 0, z0)))
    t = sweep(prof, path, is_frenet=True)
    slab = Cylinder(r_out + 1, y1 - y0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    t = t & slab
    return Pos(0, y0, 0) * Rot(-90, 0, 0) * t  # +Z を +Y に


def outer_profile(d_bot: float, d_top: float, y0: float, y1: float):
    """円環の外側の断面(XY 平面、x が半径)を Y 軸まわりに回した本体。"""
    from build123d import Axis, Face, Line, ThreePointArc, Wire, revolve

    p0, p1 = np.array([d_bot / 2, y0]), np.array([d_top / 2, y1])
    chord = np.linalg.norm(p1 - p0)
    u = (p1 - p0) / chord
    n = np.array([u[1], -u[0]])
    if n[0] > 0:
        n = -n
    c = (p0 + p1) / 2 + n * np.sqrt(ARC_R**2 - chord**2 / 4)
    m = c - n * ARC_R
    side = ThreePointArc((*p0, 0), (*m, 0), (*p1, 0))
    prof = Face(Wire([Line((0, y0, 0), (*p0, 0)), side, Line((*p1, 0), (0, y1, 0)), Line((0, y1, 0), (0, y0, 0))]))
    return revolve(prof, Axis.Y, 360), (c, ARC_R)


def build(detail: bool = False):
    """detail=False(既定): ねじもオス・メスの分割もない、組み合わせた状態の外形1つ(組立用に軽く)。
    detail=True: オス・メスに分け、ねじを付ける。"""
    from build123d import Align, Cylinder, Pos, Rot

    from bell03_surface import LD_CSV, centerline, read_ld
    from bellscrew_ring import outer_diameter
    from bope_claude_cad.vss import variable_pipe_law, variable_pipe_wall

    cl = centerline()
    L, D = read_ld(LD_CSV)
    wall, _ = variable_pipe_wall(cl, L, D, WALL, method="sweep")
    bore, _ = variable_pipe_law(cl, L, D, solid=True)
    bell = wall + bore  # ベルの外面の内側すべて

    y0, yt, ys, y1 = Y_SPLIT - THREAD_LEN - FLANGE, Y_SPLIT - THREAD_LEN, Y_SPLIT, Y_SPLIT + ABOVE  # yt..ys がねじ部
    d_bot, d_top = D_BOT, D_TOP
    for y, d in ((y0, d_bot), (y1, d_top)):
        print(f"end y {y:g}: outer D {d:.3f}, bell outer D {outer_diameter(wall, y):.3f}")
    body, arc = outer_profile(d_bot, d_top, y0, y1)
    info = {"y": (y0, yt, ys, y1), "d_bot": d_bot, "d_top": d_top, "arc": arc}
    if not detail:
        return body - bell, None, wall, info

    def cyl(r, ya, yb):
        return Pos(0, ya, 0) * Rot(-90, 0, 0) * Cylinder(r, yb - ya, align=(Align.CENTER, Align.CENTER, Align.MIN))

    big = d_bot + d_top  # 切り分け用の十分大きい半径
    # オス: ツバ(本体の y0..yt) + おねじ(谷の径の円筒 + 螺旋の山、yt..ys)
    r_root, r_crest = D3 / 2 - CLEAR, THREAD_D / 2 - CLEAR
    male_tooth = helix_tooth(r_root - 0.02, r_crest, PITCH / 8, yt, ys)
    male = (body & cyl(big, y0, yt)) + cyl(r_root, yt, ys) + male_tooth
    male = male - bell
    # メス: 本体の yt..y1 から、めねじの内径の穴と、螺旋の溝(おねじの基準山形と同じ形)を除く
    groove = helix_tooth(D1 / 2 - 0.02, THREAD_D / 2, PITCH / 8, yt, ys)
    female = (body & cyl(big, yt, y1)) - cyl(D1 / 2, yt, ys) - groove - bell
    return male, female, wall, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="OCP Viewer に表示(ベルと一緒に、設計の座標で)")
    ap.add_argument("--detail", action="store_true",
                    help="オス・メスに分けてねじを付ける(既定は組み合わせた状態の外形だけ)")
    a = ap.parse_args()

    from bell03_surface import section_edges

    male, female, wall, info = build(detail=a.detail)
    y0, yt, ys, y1 = info["y"]
    if not a.detail:
        bb = male.bounding_box()
        print(f"bellscrew (outer shape only): solids {len(male.solids())} faces {len(male.faces())} "
              f"valid {male.is_valid} volume {male.volume:.1f} mm3 y {bb.min.Y:.3f}..{bb.max.Y:.3f} "
              f"D_max {bb.size.X:.3f}")
        if a.show:
            from ocp_vscode import Camera

            from bope_claude_cad.viewer import show

            show(wall, male, names=[f"bell03_wall_t{WALL}", "bellscrew"], colors=["#e0a020", "#3080e0"],
                 alphas=[0.5, 1.0], reset_camera=Camera.KEEP, tab="tree",
                 metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)
        return
    print(f"split y {ys:g}, ring y {y0:g}..{y1:g}, thread y {yt:g}..{ys:g} (M{THREAD_D:g}x{PITCH:g}, "
          f"D1 {D1:.3f}, d3 {D3:.3f}, clear {CLEAR} radial)")
    print(f"outer D: bottom {info['d_bot']:.3f}, top {info['d_top']:.3f}, arc R {ARC_R}")
    for name, s in (("male", male), ("female", female)):
        bb = s.bounding_box()
        print(f"{name}: solids {len(s.solids())} faces {len(s.faces())} valid {s.is_valid} volume {s.volume:.1f} mm3 "
              f"y {bb.min.Y:.3f}..{bb.max.Y:.3f} D_max {bb.size.X:.3f}")
    print(f"male-female interference volume {(male & female).volume if (male & female).solids() else 0:.4f}")
    # 肉厚: おねじの谷の下(ベルの外面から)、めねじの谷の外(⌀80 から外側まで)
    for y in (yt + 1e-3, (yt + ys) / 2, ys - 1e-3):
        bd = max(e.bounding_box().size.X for e in section_edges(wall, y))  # ベルの外面
        fd = max(e.bounding_box().size.X for e in section_edges(female, y))
        print(f"y {y:.3f}: under male root {(D3 - 2 * CLEAR - bd) / 2:.3f} mm (bell outer D {bd:.3f}), "
              f"female outside root {(fd - THREAD_D) / 2:.3f} mm (outer D {fd:.3f})")

    if a.show:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(wall, male, female, names=[f"bell03_wall_t{WALL}", "bellscrew_male", "bellscrew_female"],
             colors=["#e0a020", "#3080e0", "#d04080"], alphas=[0.5, 1.0, 0.6], reset_camera=Camera.KEEP,
             tab="tree", metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)


if __name__ == "__main__":
    main()
