"""ベル(bell01 / bell02 など)の内径面と芯線を、設計の座標(回す前)で BREP に書き出す(比較表示用)。

bell01 と bell02 は同じ名前のモジュール(make_centerline など)を使うので、ベルごとに別のプロセスで実行する。

    uv run python cad/bell02/tools/export_bores.py bell02 output/compare
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def main(name: str, out: Path) -> None:
    wd = ROOT / "cad" / name
    sys.path[:0] = [str(wd / "tools"), str(wd / "ocp")]
    import make_centerline as M
    from make_mensur import X_END, diameter
    from build123d import export_brep

    from bope_claude_cad.vss import variable_pipe_law

    surf = __import__(f"{name}_surface")
    cl = surf.centerline()
    L, D = surf.read_ld(surf.LD_CSV)
    bore, _ = variable_pipe_law(cl, L, D)
    bcl = M.build_branch_wire()
    g = M.geometry()
    lb = np.linspace(cl.length, g["l_branch_end"], 401)
    bbore, _ = variable_pipe_law(bcl, lb - cl.length, diameter(np.minimum(lb, X_END)))
    out.mkdir(parents=True, exist_ok=True)
    for shape, part in [(bore, "bore"), (cl, "centerline"), (bbore, "branch1_bore"), (bcl, "branch1_centerline")]:
        export_brep(shape, str(out / f"{name}_{part}.brep"))
    print(f"{name}: bell {cl.length:.1f} + branch1 {bcl.length:.1f} mm -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], ROOT / (sys.argv[2] if len(sys.argv) > 2 else "output/compare"))
