# /// script
# requires-python = ">=3.10"
# dependencies = ["build123d>=0.13", "numpy", "matplotlib"]
# ///
"""名称付けした面・エッジ・軸・点を STEP の上に重ねて PNG にする。会話で面やエッジを指すときの共通の絵。

使い方: uv run render_names.py <step> <names.json> <outdir>

names.json(座標は渡した STEP のもの):
  {
    "faces": {"F00": "外面-底", "F41": "外面-曲げ"},          # 色つきで描く面
    "edges": {"E63": "羽先端"},                                 # 赤い線とラベル
    "axes":  {"A0": {"name": "F00の中心軸", "point": [x,y,z], "direction": [dx,dy,dz], "extent": [t0, t1]}},
    "points": {"P1": {"name": "羽先端とXZ平面の交点", "xyz": [x,y,z]}}
  }
  axes.extent は point からの距離 t の範囲(軸の線を描く長さ)。省略すると ±20。

名前の付いた面は色付き、他の面は薄いグレー。出力は iso / front / side / top の4枚。
日本語ラベルの文字化けを避けるため、フォントに Yu Gothic / Meiryo を指定する(Windows)。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from build123d import import_step
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

VIEWS = {"iso": (20, -60), "front": (0, -90), "side": (0, 0), "top": (90, -90)}
COLORS = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2"]


def main() -> int:
    step, names_path, outdir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    names = json.loads(Path(names_path).read_text(encoding="utf-8"))
    outdir.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "sans-serif"]

    shape = import_step(step)
    faces, edges = shape.faces(), shape.edges()
    bb = shape.bounding_box()
    named_f = {int(k[1:]): v for k, v in names.get("faces", {}).items()}

    for vname, (elev, azim) in VIEWS.items():
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111, projection="3d")
        for i, f in enumerate(faces):
            verts, tris = f.tessellate(0.05)
            polys = [[(verts[a].X, verts[a].Y, verts[a].Z) for a in t] for t in tris]
            if i in named_f:
                color, alpha = COLORS[list(named_f).index(i) % len(COLORS)], 0.55
            else:
                color, alpha = "#cccccc", 0.25
            ax.add_collection3d(Poly3DCollection(polys, facecolor=color, edgecolor="none", alpha=alpha))
            if i in named_f:
                c = f.center()
                ax.text(c.X, c.Y, c.Z, f"F{i:02d} {named_f[i]}", fontsize=11, color="black", weight="bold")
        for k, label in names.get("edges", {}).items():
            e = edges[int(k[1:])]
            pts = [e @ (j / 20) for j in range(21)]
            seg = [[(a.X, a.Y, a.Z), (b.X, b.Y, b.Z)] for a, b in zip(pts, pts[1:])]
            ax.add_collection3d(Line3DCollection(seg, colors="red", linewidths=2))
            m = e @ 0.5
            ax.text(m.X, m.Y, m.Z, f"{k} {label}", fontsize=7, color="darkred")
        for k, a in names.get("axes", {}).items():
            p, d = a["point"], a["direction"]
            t0, t1 = a.get("extent", [-20, 20])
            ends = [[p[j] + t * d[j] for j in range(3)] for t in (t0, t1)]
            ax.plot(*zip(*ends), color="blue", lw=3)
            ax.text(*ends[1], f"{k} {a['name']}", fontsize=10, color="blue", weight="bold")
        for k, p in names.get("points", {}).items():
            ax.scatter(*p["xyz"], color="red", s=40)
            ax.text(*p["xyz"], f" {k} {p['name']}", fontsize=10, color="red", weight="bold")
        ax.set_xlim(bb.min.X, bb.max.X)
        ax.set_ylim(bb.min.Y, bb.max.Y)
        ax.set_zlim(bb.min.Z, bb.max.Z)
        ax.set_box_aspect((bb.size.X, bb.size.Y, bb.size.Z))
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        fig.savefig(outdir / f"{vname}.png", dpi=110)
        plt.close(fig)
    print("done", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
