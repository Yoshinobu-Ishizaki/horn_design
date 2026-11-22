"""bell01: 芯線 bell03-ctr.dxf と L-D 表 bell_20180330_xyrev.csv(1 mm 間隔)からベルの内径面を作る。

- 芯線は 840.635 mm、表は 850 mm。表が長いので芯線の終点で切る(終点の直径は 16.125、FreeCAD の bell_01 と同じ)。
- 基本はサーフェス(端面なし)。`--wall t` で外向きに板厚 t を付けたソリッド。

    uv run python cad/bell03/ocp/bell03_surface.py [--show] [--step] [--wall 0.4]
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
CTR_DXF = WD / "bell03-ctr.dxf"
LD_CSV = WD / "bell03-ld.csv"  # tools/make_mensur.py で作る(元は mensur/bell/bell_20180330_xyrev.csv)
OUT = ROOT / "output/bell03"
# 管体組立の基本姿勢は make_centerline.ASSEMBLY_ROT_Z(リム中心まわりに Z 軸で +15°)。設計の計算
# (芯線・メンズール・隙間)は設計の座標のまま行い、STEP 出力と表示のときだけこの姿勢にする。


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


WALL_FOR_CLEARANCE = 0.4  # 隙間を測るときの板厚 (mm)。板厚を付けていなくても、この厚みで測る


def _outline(cl, prof, n=1500):
    """芯線の平面での、管の両側の輪郭(芯線 ± D/2·法線)。平面の芯線なので厳密。"""
    pts = []
    for s in np.linspace(0, prof.l_end, n):
        p, t = cl.position_at(s / cl.length), cl.tangent_at(s / cl.length)
        r = float(prof(s)) / 2
        pts += [(p.X - r * t.Y, p.Y + r * t.X), (p.X + r * t.Y, p.Y - r * t.X)]
    return np.array(pts)


def clearance(cl, prof, bcl, bprof, wall=0.4, skip=60.0):
    """1番管とベルの外面どうしの最短距離。継ぎ目の近く(ベルの終わりと1番管の始め skip mm)は除く。"""
    from scipy.spatial import cKDTree

    bell_end = prof.l_end
    lb = np.linspace(0, bell_end - skip, 2000)
    bell = []
    for s in lb:
        p, t = cl.position_at(s / cl.length), cl.tangent_at(s / cl.length)
        r = float(prof(s)) / 2
        bell += [(p.X - r * t.Y, p.Y + r * t.X), (p.X + r * t.Y, p.Y - r * t.X)]
    br = []
    for s in np.linspace(skip, bprof.l_end, 800):
        p, t = bcl.position_at(s / bcl.length), bcl.tangent_at(s / bcl.length)
        r = float(bprof(s)) / 2
        br += [(p.X - r * t.Y, p.Y + r * t.X), (p.X + r * t.Y, p.Y - r * t.X)]
    br = np.array(br)
    d, _ = cKDTree(np.array(bell)).query(br)
    i = int(d.argmin())
    return float(d[i]) - 2 * wall, br[i]


def centerline() -> Wire:
    """芯線は tools/make_centerline.py の寸法から直接作る(渦巻きを含むので、DXF は参考)。"""
    import sys

    sys.path.insert(0, str(WD / "tools"))
    from make_centerline import build_wire

    return build_wire()


def read_ld(path: Path) -> tuple[np.ndarray, np.ndarray]:
    a = np.loadtxt(path, delimiter=",", skiprows=1)
    return a[:, 0], a[:, 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="OCP Viewer に表示")
    ap.add_argument("--step", action="store_true", help="output/bell03/ に STEP を出す")
    ap.add_argument("--wall", type=float, default=0.0, help="外向きの板厚 (mm)。0 はサーフェスだけ")
    ap.add_argument("--check", action="store_true", help="断面の直径誤差を測る(約 1 分かかる)")
    a = ap.parse_args()

    cl = centerline()
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
    if a.check:
        solid, _ = variable_pipe_law(cl, L, D, solid=True)
        chk = check_variable_pipe(solid, cl, prof)
        print(f"check: dia_err_max {chk['dia_err_max']:.4f} mm rms {chk['dia_err_rms']:.4f} "
              f"volume_ratio {chk['volume_ratio']:.6f}")

    # 1番管: ベルの終点から、メンズール関数が 12.00 になる L まで(L はベルの終点からの距離にずらす)
    from make_centerline import ASSEMBLY_ROT_Z, build_branch_wire, geometry
    from make_mensur import X_END, diameter

    bcl = build_branch_wire()
    g = geometry()
    l0b = cl.length  # 1番管のメンズールは、ベルの芯線の実際の長さから
    Lb = np.linspace(l0b, g["l_branch_end"], 401)
    Db = diameter(np.minimum(Lb, X_END))  # ⌀12 になった先(1番管の末端の直線の延長分)は ⌀12
    bshell, bprof = variable_pipe_law(bcl, Lb - l0b, Db)
    print(f"branch1: centerline {bcl.length:.3f}, D {Db[0]:.3f} -> {Db[-1]:.3f}, faces {len(bshell.faces())} "
          f"valid {bshell.is_valid}")
    if a.check:
        bsolid, _ = variable_pipe_law(bcl, Lb - l0b, Db, solid=True)
        bchk = check_variable_pipe(bsolid, bcl, bprof)
        print(f"branch1 check: dia_err_max {bchk['dia_err_max']:.4f} mm volume_ratio {bchk['volume_ratio']:.6f}")
    gap, where = clearance(cl, prof, bcl, bprof, wall=a.wall if a.wall > 0 else WALL_FOR_CLEARANCE)
    print(f"clearance branch1 - bell (outer surfaces, wall {a.wall if a.wall > 0 else WALL_FOR_CLEARANCE}): "
          f"{gap:.2f} mm at branch1 ({where[0]:.1f}, {where[1]:.1f})")

    shapes, names, colors = [shell, bshell], ["bell03_bore", "bell03_branch1_bore"], ["#e0a020", "#c06020"]
    if a.wall > 0:
        wall, _ = variable_pipe_wall(cl, L, D, a.wall, method="sweep")
        bwall, _ = variable_pipe_wall(bcl, Lb - l0b, Db, a.wall, method="sweep")
        print(f"wall t={a.wall}: bell faces {len(wall.faces())} valid {wall.is_valid}, "
              f"branch1 faces {len(bwall.faces())} valid {bwall.is_valid}")
        shapes, names = [wall, bwall], [f"bell03_wall_t{a.wall}", f"bell03_branch1_wall_t{a.wall}"]

    # 組立の基本姿勢に回す(リム中心 (0,0) まわり、Z 軸で ASSEMBLY_ROT_Z)
    from build123d import Circle, Pos, Rot

    pose = Rot(0, 0, ASSEMBLY_ROT_Z)
    disk = pose * (Pos(g["c"][0], g["c"][1], 0) * Circle(g["ri"]).face())
    shell, bshell, cl, bcl = (pose * x for x in (shell, bshell, cl, bcl))
    shapes = [pose * x for x in shapes]

    if a.step:
        OUT.mkdir(parents=True, exist_ok=True)
        export_step(shell, str(OUT / "bell03_bore_surface.step"))
        export_step(bshell, str(OUT / "bell03_branch1_bore_surface.step"))
        if a.wall > 0:
            for s, n in zip(shapes, names):
                export_step(s, str(OUT / f"{n}.step"))  # method="sweep" の外面は B-スプライン面なので変換不要
        print(f"STEP -> {OUT}")

    if a.show:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(
            *shapes, cl, bcl, disk,
            names=[*names, "bell03_centerline", "bell03_branch1_centerline", f"inner_disk_D{2 * g['ri']:.0f}"],
            colors=[*colors, "#e02020", "#a000c0", "#30c050"],
            alphas=[1.0, 1.0, 1.0, 1.0, 0.4],
            reset_camera=Camera.KEEP,
            tab="tree",
            metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1,
        )


if __name__ == "__main__":
    main()
