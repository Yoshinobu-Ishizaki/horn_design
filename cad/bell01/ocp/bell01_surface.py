"""bell01: 芯線 bell01-ctr.dxf と L-D 表 bell_20180330_xyrev.csv(1 mm 間隔)からベルの内径面を作る。

- 芯線は 840.635 mm、表は 850 mm。表が長いので芯線の終点で切る(終点の直径は 16.125、FreeCAD の bell_01 と同じ)。
- 基本はサーフェス(端面なし)。`--wall t` で外向きに板厚 t を付けたソリッド。

    uv run python cad/bell01/ocp/bell01_surface.py [--show] [--step] [--wall 0.4]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import ezdxf
import numpy as np
from build123d import Edge, Line, ThreePointArc, Vector, Wire, export_step

from bope_claude_cad.vss import check_variable_pipe, variable_pipe_law, variable_pipe_wall

WD = Path(__file__).resolve().parent.parent
ROOT = WD.parent.parent
CTR_DXF = WD / "bell01-ctr.dxf"
LD_CSV = ROOT / "mensur/bell/bell_20180330_xyrev.csv"
OUT = ROOT / "output/bell01"


def read_centerline(path: Path, start=(0.0, 0.0)) -> Wire:
    """DXF の LINE・ARC を、始点 ``start`` から端点でつないで1本のワイヤにする。

    DXF の ARC は常に反時計回りなので、つなぐ向きに合わせて始点と終点を入れ替える。
    円弧の始点は、前の要素の終点に合わせる(端点の小さなずれを吸収する)。
    """
    items = []
    for e in ezdxf.readfile(path).modelspace():
        if e.dxftype() == "LINE":
            items.append(("L", Vector(e.dxf.start.x, e.dxf.start.y), Vector(e.dxf.end.x, e.dxf.end.y), None))
        elif e.dxftype() == "ARC":
            c, r = e.dxf.center, e.dxf.radius
            a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
            if a1 < a0:
                a1 += 2 * math.pi
            am = (a0 + a1) / 2
            p = lambda a: Vector(c[0] + r * math.cos(a), c[1] + r * math.sin(a))  # noqa: E731
            items.append(("A", p(a0), p(a1), p(am)))
    cur = Vector(*start)
    edges: list[Edge] = []
    while items:
        i, rev = min(
            ((i, rev) for i in range(len(items)) for rev in (False, True)),
            key=lambda k: ((items[k[0]][2] if k[1] else items[k[0]][1]) - cur).length,
        )
        kind, s, t, m = items.pop(i)
        if rev:
            s, t = t, s
        if (s - cur).length > 1e-3:
            raise ValueError(f"gap {(s - cur).length:.4f} mm at {cur}")
        edges.append(Line(cur, t) if kind == "L" else ThreePointArc(cur, m, t))
        cur = t
    return Wire(edges)


def read_ld(path: Path) -> tuple[np.ndarray, np.ndarray]:
    a = np.loadtxt(path, delimiter=",", skiprows=1)
    return a[:, 0], a[:, 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="OCP Viewer に表示")
    ap.add_argument("--step", action="store_true", help="output/bell01/ に STEP を出す")
    ap.add_argument("--wall", type=float, default=0.0, help="外向きの板厚 (mm)。0 はサーフェスだけ")
    a = ap.parse_args()

    cl = read_centerline(CTR_DXF)
    L, D = read_ld(LD_CSV)
    shell, prof = variable_pipe_law(cl, L, D)
    print(f"centerline {cl.length:.3f} mm, table L {L[0]:.0f}..{L[-1]:.0f}, end L {prof.l_end:.3f} "
          f"D_start {float(prof(0)):.3f} D_end {float(prof(prof.l_end)):.3f}")
    # 面積を理想値 ∫ 2π r √(1 + r'²) dL と比べる
    g = np.linspace(0, prof.l_end, 200001)
    r = prof(g) / 2
    dr = prof.spline(g, 1) / 2
    area_ideal = float(np.trapezoid(2 * math.pi * r * np.sqrt(1 + dr**2), g))
    print(f"surface: faces {len(shell.faces())} valid {shell.is_valid} area {shell.area:.1f} "
          f"ideal {area_ideal:.1f} ratio {shell.area / area_ideal:.6f}")
    solid, _ = variable_pipe_law(cl, L, D, solid=True)
    chk = check_variable_pipe(solid, cl, prof)
    print(f"check: dia_err_max {chk['dia_err_max']:.4f} mm rms {chk['dia_err_rms']:.4f} "
          f"volume_ratio {chk['volume_ratio']:.6f}")

    shapes, names, colors = [shell], ["bell01_bore"], ["#cf9f30"]
    if a.wall > 0:
        wall, _ = variable_pipe_wall(cl, L, D, a.wall)
        print(f"wall t={a.wall}: faces {len(wall.faces())} valid {wall.is_valid}")
        shapes, names = [wall], [f"bell01_wall_t{a.wall}"]

    if a.step:
        from build123d import Solid
        from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

        OUT.mkdir(parents=True, exist_ok=True)
        export_step(shell, str(OUT / "bell01_bore_surface.step"))
        if a.wall > 0:
            bs = Solid(BRepBuilderAPI_NurbsConvert(shapes[0].wrapped, True).Shape())
            export_step(bs, str(OUT / f"bell01_wall_t{a.wall}.step"))
        print(f"STEP -> {OUT}")

    if a.show:
        from ocp_vscode import Camera, StudioBackground, StudioEnvironment, StudioToneMapping

        from bope_claude_cad.viewer import show

        show(
            *shapes, cl,
            names=[*names, "centerline"],
            colors=[*colors, "red"],
            reset_camera=Camera.KEEP,
            tab="studio",
            metalness=1.0,
            roughness=0.02,
            studio_environment=StudioEnvironment.HIGH_CONTRAST_STUDIO,
            studio_tone_mapping=StudioToneMapping.NEUTRAL,
            studio_exposure=0.8,
            studio_background=StudioBackground.GRADIENT_DARK,
        )


if __name__ == "__main__":
    main()
