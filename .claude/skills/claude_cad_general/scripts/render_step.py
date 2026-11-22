"""スポット治具のアセンブリ STEP を部品ごとの色で PNG にする(OCP Viewer が使えないときの確認用)。

使い方(リポジトリルートから):
    uv run --with matplotlib python jigs/brace_spot_lowbrass/tools/render_step.py <step> <out.png> \
        [x0 x1 y0 y1 z0 z1]
範囲を省くと全体。iso / 前(-Y から見る) / 側(+X から見る) / 上 の4枚を1枚にまとめる。
部品名のキーワードで色を決める(母治具は薄い灰色で半透明)。
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from bope_claude_cad.stepcompare import load_reference

# (キーワード, 色, 不透明度)。上から順に最初に一致したものを使う。
PALETTE = [
    ("CBJ", "#aaaaaa", 0.12),
    ("SICHU", "#e45756", 0.95),
    ("ELECTRODE-BASE", "#f58518", 0.95),
    ("STOPPER", "#54a24b", 0.95),
    ("HOLD-PLATE", "#b279a2", 0.95),
    ("SCREW", "#222222", 0.95),
    ("ELECTRODE-BAR", "#4c78a8", 0.9),
    ("DIREC", "#e377c2", 0.9),
]
VIEWS = {"iso": (25, -60), "front (from -Y)": (0, -90), "side (from +X)": (0, 0), "top": (90, -90)}


def style(label):
    for key, color, alpha in PALETTE:
        if key in label:
            return color, alpha
    return "#888888", 0.5


def main(step, out, window):
    parts = [(label, s) for label, shapes in load_reference(step).items() for s in shapes]
    x0, x1, y0, y1, z0, z1 = window
    fig = plt.figure(figsize=(16, 12))
    for k, (name, (elev, azim)) in enumerate(VIEWS.items()):
        ax = fig.add_subplot(2, 2, k + 1, projection="3d")
        for label, solid in parts:
            color, alpha = style(label)
            verts, tris = solid.tessellate(0.2, 0.2)
            v = np.array([[p.X, p.Y, p.Z] for p in verts])
            ax.add_collection3d(
                Poly3DCollection([v[list(t)] for t in tris], facecolor=color, edgecolor="none", alpha=alpha)
            )
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_zlim(z0, z1)
        ax.set_box_aspect((x1 - x0, y1 - y0, z1 - z0))
        ax.view_init(elev, azim)
        ax.set_title(name)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
    fig.savefig(out, dpi=80, bbox_inches="tight")
    print("saved", out)


if __name__ == "__main__":
    nums = [float(v) for v in sys.argv[3:9]] or [-45, 45, -75, 15, 0, 160]
    main(sys.argv[1], sys.argv[2], nums)
