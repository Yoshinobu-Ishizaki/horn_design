"""Export the bell wall (and bore surface) to STEP and report file size / re-import check.

Usage: uv run python skills/claude_cad_vss/scripts/export_bell_step.py DXF OUTDIR [--wall 0.4]
"""

import argparse
import sys
from pathlib import Path

import ezdxf
from build123d import Solid, export_step, import_step
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

sys.path.insert(0, str(Path(__file__).parent))
from bell_from_dxf import build_centerline, read_table

from bope_claude_cad.vss import variable_pipe_law, variable_pipe_wall

ap = argparse.ArgumentParser()
ap.add_argument("dxf")
ap.add_argument("outdir")
ap.add_argument("--wall", type=float, default=0.4)
a = ap.parse_args()

out = Path(a.outdir)
out.mkdir(parents=True, exist_ok=True)
msp = ezdxf.readfile(a.dxf).modelspace()
L, D = read_table(msp)
cl = build_centerline(msp)
wall, _ = variable_pipe_wall(cl, L, D, a.wall)
bore, _ = variable_pipe_law(cl, L, D)
# MakeOffsetShape の外面は OffsetSurface のまま STEP に出る。他の CAD で扱いにくく、体積の
# 数値積分も不安定になる(約6%ずれた)ので、B-スプライン面に変換した版も出す(ずれは 1e-5 mm)。
wall_bs = Solid(BRepBuilderAPI_NurbsConvert(wall.wrapped, True).Shape())
for name, shape in (
    (f"bell_wall_t{a.wall}.step", wall),
    (f"bell_wall_t{a.wall}_bspline.step", wall_bs),
    ("bell_bore_surface.step", bore),
):
    p = out / name
    export_step(shape, str(p))
    back = import_step(str(p))
    print(
        name,
        f"{p.stat().st_size / 1024:.0f} KB",
        "faces",
        len(back.faces()),
        "valid",
        back.is_valid,
        "vol",
        round(back.volume, 1),
    )
