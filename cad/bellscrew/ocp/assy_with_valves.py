"""管体組立: 植込組立(cad/valves)と、暫定の配置のベル(bell03 + 1番管)とベルスクリューを一緒に表示する。

ベルの配置は cad/valves/ocp/bell_place.py と同じ(組立の基本姿勢 +15°、曲げ内側の円の中心 (X, B, C)、
芯線の最高点の接線まわりに TILT_DEG の傾き)。ベルスクリューは、その同じ変換で置く(組立用の外形だけ)。
cad/valves のファイルは直さず、関数を借りる。

`--pull Bb3,F3 --tip -10`: 抜差を抜いた状態で出す(cad/valves/ocp/pullout_check.py と同じ決め方)。中管の先端が、
外管の開いた端から --tip mm の所まで(負なら外へ出る。-10 で完全に抜けて 10 mm 離れる)。中管・桂・頭管を -Y へ動かす。

`--mark-d12`: 1番管の内径が ⌀12.00 になる位置(メンズールの X_END。今は 1番管の末端)に、内径の円(⌀12)と
外面の円(⌀12 + 2·板厚)を描く。

    uv run python cad/bellscrew/ocp/assy_with_valves.py [--X 5] [--B -60] [--C 50] [--tilt 4.5] [--pull Bb3,F3 --tip -10]
        [--mark-d12]
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cad/valves/ocp"))


def main(hook=None) -> None:
    """hook(M, branch, others) -> (branch, parts, names, colors): ほかのスクリプト(cad/branch2 など)が、1番管を差し替えたり
    部品を足したりするための入り口。M はベル(設計の座標)から組立への変換。others は、ほかの部品の (名前, 形) の並び。"""
    from ocp_vscode import Camera

    import all_slides as A
    import bell_place as BP
    import bellscrew_thread as BT
    from bope_claude_cad.viewer import show
    from shape_cache import cached, phase
    from valve_row import build_row_cached

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    X, B, C = arg("--X", 5.0), arg("--B", -60.0), arg("--C", 50.0)
    deg = arg("--tilt", BP.TILT_DEG)
    pulls = sys.argv[sys.argv.index("--pull") + 1].split(",") if "--pull" in sys.argv else []
    tip = arg("--tip", -10.0)

    phase("start")
    info = cached("bell03_walls", BP.WALL, ROOT / "cad/bell03/ocp/bell03_surface.py", BP.build_bell)
    phase("bell walls cached load")
    _, _, M, ctr = BP.placed_manual(B, C, X)
    phase("placed_manual")
    if deg:
        M, _, _ = BP.tilt_about_top_tangent(M, deg)
    phase("tilt")
    bell, branch = BP.apply(info["bell"], M), BP.apply(info["branch"], M)
    phase("apply bell")
    screw = cached("bellscrew_outer", [BT.Y_SPLIT, BT.ARC_R, BT.D_BOT, BT.D_TOP], HERE / "bellscrew_thread.py",
                   lambda: BT.build(detail=False)[0])
    phase("bell + screw loaded")
    screw = BP.apply(screw, M)
    bb = screw.bounding_box(optimal=False)
    print(f"bend circle centre {ctr.round(3).tolist()}, tilt {deg:g} deg; bellscrew centre "
          f"({bb.center().X:.1f}, {bb.center().Y:.1f}, {bb.center().Z:.1f})")

    phase("screw placed")
    parts, names = [], []
    for v, (case, ks, nms) in build_row_cached().items():
        parts += [case] + ks
        names += [f"{v}_case"] + nms
    parts += A.valve4_knuckles()
    names += A.V4_NAMES
    from build123d import Pos

    phase("valve rows + valve4 knuckles")
    slides = A.collect()
    phase("slides collected")
    for tag in pulls:
        p = slides[tag]
        outer_end = p["outer_tube_L"].bounding_box().min.Y  # 外管の開いた端(つば側)
        inner_tip = p["inner_tube_L"].bounding_box().max.Y  # 中管の先端
        pull = (inner_tip - outer_end) - tip
        slides[tag] = {k: (v if k.startswith("outer_tube") else Pos(0, -pull, 0) * v) for k, v in p.items()}
        print(f"{tag}: pulled {pull:.2f} mm (inner tip {abs(tip):g} mm {'outside' if tip < 0 else 'inside'} the outer tube end)")
    for tag, p in slides.items():
        parts += list(p.values())
        names += [f"{tag}_{k}" for k in p]
    extra = ([], [], [])
    if hook is not None:
        others = list(zip(names, parts)) + [("bell03_bell_wall", bell), ("bellscrew", screw)]
        phase("before hook")
        branch, *extra = hook(M, branch, others)
        phase("hook done")
    parts += [bell, branch, screw]
    names += ["bell03_bell_wall", "bell03_branch1_wall", "bellscrew"]
    colors = [None] * len(parts)
    parts += extra[0]
    names += extra[1]
    colors += extra[2]
    if "--mark-d12" in sys.argv:
        circles, cnames = d12_circles(M, BP.WALL)
        parts += circles
        names += cnames
        colors += ["#00c0ff"] * len(circles)
    phase("before show")
    show(*parts, names=names, colors=colors, reset_camera=Camera.KEEP)


def d12_circles(M, wall):
    """1番管の内径が ⌀12.00 になる位置(芯線の上)の、芯線に垂直な円(内径と外面)。M は組立の変換。"""
    import bell_place as BP
    import numpy as np
    from build123d import Edge, Plane

    sys.path.insert(0, str(ROOT / "cad/bell03/tools"))
    from make_centerline import build_branch_wire, geometry
    from make_mensur import X_END, diameter

    import bell03_surface as BS

    bcl = build_branch_wire()
    s = X_END - BS.centerline().length  # 1番管の芯線に沿った距離
    u = min(s / bcl.length, 1.0)
    p, t = bcl.position_at(u), bcl.tangent_at(u)
    d = float(diameter(X_END))
    print(f"D 12 point: branch1 s {s:.3f} of {bcl.length:.3f} (L {X_END:g}, D {d:.4f}, "
          f"l_branch_end {geometry()['l_branch_end']:g})")
    out = []
    for r in (d / 2, d / 2 + wall):
        out.append(BP.apply(Edge.make_circle(r, Plane(origin=p, z_dir=t)), M))
    c = M[:3, :3] @ np.array([p.X, p.Y, p.Z]) + M[:3, 3]
    tw = M[:3, :3] @ np.array([t.X, t.Y, t.Z])
    print(f"  assembly: centre ({c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f}), axis ({tw[0]:.4f}, {tw[1]:.4f}, {tw[2]:.4f})")
    return out, ["branch1_D12_bore", f"branch1_D12_outer_D{d + 2 * wall:.1f}"]


if __name__ == "__main__":
    main()
