"""板厚付けの各段階にかかる時間を測り、厚みを確かめる。

    uv run python cad/bell01/tools/time_wall.py [branch|bell] [--wall 0.4] [--method sweep|join] [--step]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

WD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WD / "tools"))
sys.path.insert(0, str(WD / "ocp"))

from make_centerline import TOTAL, build_branch_wire, geometry  # noqa: E402
from make_mensur import diameter  # noqa: E402

from build123d import Shell  # noqa: E402

from bope_claude_cad.vss import _offset_sweep, variable_pipe_law, variable_pipe_wall  # noqa: E402


def thickness_samples(inner, outer, n=8):
    """内径面の点から、外面(シェル)までの距離(=厚み)を測る。"""
    outer = list(outer.faces())
    ds = []
    for f in inner.faces():
        for u in np.linspace(0.02, 0.98, n):
            for v in np.linspace(0.02, 0.98, n):
                p = f.position_at(u, v)
                ds.append(min(o.distance_to(p) for o in outer))
    return np.array(ds)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["branch", "bell"])
    ap.add_argument("--wall", type=float, default=0.4)
    ap.add_argument("--method", default="sweep", choices=["sweep", "join"])
    ap.add_argument("--step", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    if a.part == "branch":
        cl = build_branch_wire()
        g = geometry()
        L = np.linspace(TOTAL, g["l_branch_end"], 401)
        Lr, D = L - TOTAL, diameter(L)
    else:
        from bell01_surface import LD_CSV, centerline, read_ld

        cl = centerline()
        Lr, D = read_ld(LD_CSV)
    print(f"centerline {time.time() - t0:.1f}s", flush=True)

    t = time.time()
    wall, _ = variable_pipe_wall(cl, Lr, D, a.wall, method=a.method)
    print(f"wall ({a.method}) {time.time() - t:.1f}s faces {len(wall.faces())} valid {wall.is_valid}", flush=True)

    t = time.time()
    inner, prof = variable_pipe_law(cl, Lr, D)
    if a.method == "sweep":
        outer = _offset_sweep(cl, prof, a.wall)
    else:
        outer = Shell([f for f in wall.faces() if min(f.distance_to(f2.center()) for f2 in inner.faces()) > 1e-3])
    ds = thickness_samples(inner, outer)
    print(f"thickness {ds.min():.5f}..{ds.max():.5f} (n={len(ds)}) volume {wall.volume:.1f} [{time.time() - t:.1f}s]",
          flush=True)

    if a.step:
        from build123d import Solid, export_step
        from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

        t = time.time()
        bs = wall if a.method == "sweep" else Solid(BRepBuilderAPI_NurbsConvert(wall.wrapped, True).Shape())
        out = WD.parents[1] / "output/bell01"
        out.mkdir(parents=True, exist_ok=True)
        name = "branch1" if a.part == "branch" else "bell01"
        p = out / f"{name}_wall_t{a.wall}.step"
        export_step(bs, str(p))
        print(f"export step {time.time() - t:.1f}s -> {p} ({p.stat().st_size / 1e6:.2f} MB)", flush=True)


if __name__ == "__main__":
    main()
