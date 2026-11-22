"""bell02・bell01・RefBell を、設計の座標(回す前、リム中心が原点、直管部は +Y)で重ねて表示する。

bell01・bell02 は export_bores.py(別プロセス)で BREP に書き出してから読む。RefBell は claude_cad_vss のサンプル
(社内図面。jigs/refbell_seat/input、git 管理外)から作る。

    uv run python cad/bell02/tools/compare.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output/compare"
sys.path.insert(0, str(ROOT / ".claude/skills/claude_cad_vss/scripts"))


def main() -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for name in ("bell01", "bell02"):
        subprocess.run([sys.executable, str(Path(__file__).with_name("export_bores.py")), name, str(OUT.relative_to(ROOT))],
                       check=True, env=env, cwd=ROOT)

    from bell_from_dxf import build_centerline, read_table
    from build123d import import_brep
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from bope_claude_cad.vss import variable_pipe_law

    shapes, names, colors, alphas = [], [], [], []
    style = {"bell02": ("#20a070", "#0a6040", 0.7), "bell01": ("#e0a020", "#e02020", 0.45)}
    for name in ("bell02", "bell01"):
        bore_c, line_c, al = style[name]
        for part, col, a in [("bore", bore_c, al), ("branch1_bore", bore_c, al), ("centerline", line_c, 1.0),
                             ("branch1_centerline", line_c, 1.0)]:
            shapes.append(import_brep(str(OUT / f"{name}_{part}.brep")))
            names.append(f"{name}_{part}")
            colors.append(col)
            alphas.append(a)
    msp = ezdxf.readfile(ROOT / "jigs/*_seat/input/refbell_bell_assy.dxf").modelspace()
    lh, dh = read_table(msp)
    clh = build_centerline(msp)
    bore_h, _ = variable_pipe_law(clh, lh, dh)
    shapes += [bore_h, clh]
    names += ["refbell_bore", "refbell_centerline"]
    colors += ["#2070e0", "#00b0d0"]
    alphas += [0.45, 1.0]
    show(*shapes, names=names, colors=colors, alphas=alphas, reset_camera=Camera.KEEP, tab="tree",
         metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)
    print("shown:", ", ".join(names))


if __name__ == "__main__":
    main()
