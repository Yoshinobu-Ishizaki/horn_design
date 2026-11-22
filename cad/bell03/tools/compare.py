"""ベル(既定は bell03 と bell01)と RefBell を、設計の座標(回す前、リム中心が原点、直管部は +Y)で重ねて表示する。

各ベルは cad/bell02/tools/export_bores.py(ベルごとに別プロセス)で BREP に書き出してから読む。
RefBell は bope_claude_cad.refs.refbell()(社内図面、git 管理外。DXF は実行時に探す)で作る。

    uv run python cad/bell03/tools/compare.py [bell03 bell01 ...]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output/compare"
EXPORT = ROOT / "cad/bell02/tools/export_bores.py"
sys.path.insert(0, str(ROOT / ".claude/skills/claude_cad_vss/scripts"))
# ベルごとの色(内径面、芯線、不透明度)
STYLE = {
    "bell03": ("#8a50d0", "#5a2090", 0.7),
    "bell02": ("#20a070", "#0a6040", 0.55),
    "bell01": ("#e0a020", "#e02020", 0.45),
}


def main(names: list[str]) -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for name in names:
        subprocess.run([sys.executable, str(EXPORT), name, str(OUT.relative_to(ROOT))], check=True, env=env, cwd=ROOT)

    from build123d import import_brep
    from ocp_vscode import Camera

    from bope_claude_cad.refs import refbell
    from bope_claude_cad.viewer import show
    from bope_claude_cad.vss import variable_pipe_law

    shapes, labels, colors, alphas = [], [], [], []
    for name in names:
        bore_c, line_c, al = STYLE.get(name, ("#909090", "#404040", 0.5))
        for part, col, a in [("bore", bore_c, al), ("branch1_bore", bore_c, al), ("centerline", line_c, 1.0),
                             ("branch1_centerline", line_c, 1.0)]:
            shapes.append(import_brep(str(OUT / f"{name}_{part}.brep")))
            labels.append(f"{name}_{part}")
            colors.append(col)
            alphas.append(a)
    try:
        clh, lh, dh = refbell()
    except FileNotFoundError as e:
        print(f"{e}。RefBell なしで表示する")
        clh = None
    if clh is not None:
        bore_h, _ = variable_pipe_law(clh, lh, dh)
        shapes += [bore_h, clh]
        labels += ["refbell_bore", "refbell_centerline"]
        colors += ["#2070e0", "#00b0d0"]
        alphas += [0.45, 1.0]
    show(*shapes, names=labels, colors=colors, alphas=alphas, reset_camera=Camera.KEEP, tab="tree",
         metalness=0.3, roughness=0.65, ambient_intensity=1.0, direct_intensity=1.1)
    print("shown:", ", ".join(labels))


if __name__ == "__main__":
    main(sys.argv[1:] or ["bell03", "bell01"])
