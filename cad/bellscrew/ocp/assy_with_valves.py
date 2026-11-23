"""管体組立: 植込組立(cad/valves)と、暫定の配置のベル(bell03 + 1番管)とベルスクリューを一緒に表示する。

ベルの配置は cad/valves/ocp/bell_place.py と同じ(組立の基本姿勢 +15°、曲げ内側の円の中心 (X, B, C)、
芯線の最高点の接線まわりに TILT_DEG の傾き)。ベルスクリューは、その同じ変換で置く(組立用の外形だけ)。
cad/valves のファイルは直さず、関数を借りる。

    uv run python cad/bellscrew/ocp/assy_with_valves.py [--X 5] [--B -60] [--C 50] [--tilt 4.5]
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cad/valves/ocp"))


def main() -> None:
    from ocp_vscode import Camera

    import all_slides as A
    import bell_place as BP
    import bellscrew_thread as BT
    from bope_claude_cad.viewer import show
    from shape_cache import cached
    from valve_row import build_row_cached

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    X, B, C = arg("--X", 5.0), arg("--B", -60.0), arg("--C", 50.0)
    deg = arg("--tilt", BP.TILT_DEG)

    info = cached("bell03_walls", BP.WALL, ROOT / "cad/bell03/ocp/bell03_surface.py", BP.build_bell)
    _, _, M, ctr = BP.placed_manual(B, C, X)
    if deg:
        M, _, _ = BP.tilt_about_top_tangent(M, deg)
    bell, branch = BP.apply(info["bell"], M), BP.apply(info["branch"], M)
    screw = cached("bellscrew_outer", [BT.Y_SPLIT, BT.ARC_R, BT.D_BOT, BT.D_TOP], HERE / "bellscrew_thread.py",
                   lambda: BT.build(detail=False)[0])
    screw = BP.apply(screw, M)
    bb = screw.bounding_box()
    print(f"bend circle centre {ctr.round(3).tolist()}, tilt {deg:g} deg; bellscrew centre "
          f"({bb.center().X:.1f}, {bb.center().Y:.1f}, {bb.center().Z:.1f})")

    parts, names = [], []
    for v, (case, ks, nms) in build_row_cached().items():
        parts += [case] + ks
        names += [f"{v}_case"] + nms
    parts += A.valve4_knuckles()
    names += A.V4_NAMES
    for tag, p in A.collect().items():
        parts += list(p.values())
        names += [f"{tag}_{k}" for k in p]
    parts += [bell, branch, screw]
    names += ["bell03_bell_wall", "bell03_branch1_wall", "bellscrew"]
    show(*parts, names=names, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    main()
