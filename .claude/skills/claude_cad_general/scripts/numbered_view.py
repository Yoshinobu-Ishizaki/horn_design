"""面・辺に番号を振って OCP Viewer に表示する。「面 12」「辺 5」のようにユーザーが指し示すための道具。

- faces: 各面を別の色の部品 `F<番号>` として送り、面の中心の少し外側に番号のラベルを置く。
- edges: 形を半透明の `body` として出し、各辺を別の色の部品 `E<番号>` として送り、辺の中央の
  少し外側に番号のラベルを置く。
面積(辺は長さ)が小さいもの(刻印の文字など)は、番号を振らず 1 つにまとめて灰色で出す。
番号と種類・大きさ・位置・向きは、表にして標準出力にも出す。視点は戻さない(Camera.KEEP)。

使い方(リポジトリルートから):
    uv run python -m bope_claude_cad.numbered_view <STEP ファイル | モジュール:関数> [faces|edges] [最小値]
"""

import importlib
import math
import sys
from pathlib import Path

from build123d import Align, Compound, Plane, Text, Vector, import_step

PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46b8c8",
    "#f032e6", "#b5a600", "#008080", "#9a6324", "#800000", "#808000",
]  # fmt: skip
GRAY = "#9a9a9a"


def _text_at(text, point, normal, size):
    """``point`` の少し外側に、``normal`` 向きに読める文字を置く(薄い板)。"""
    n = normal.normalized()
    up = Vector(0, 0, 1) if abs(n.Z) < 0.95 else Vector(0, 1, 0)
    plane = Plane(origin=point + n * 0.25, z_dir=n, x_dir=up.cross(n))
    return plane * Text(text, size, align=(Align.CENTER, Align.CENTER))


def _snap_axis(v: Vector) -> Vector:
    """向き ``v`` を、いちばん近い座標軸の向きに丸める(ラベルを読みやすくする)。"""
    comps = [(abs(v.X), Vector(math.copysign(1, v.X), 0, 0)),
             (abs(v.Y), Vector(0, math.copysign(1, v.Y), 0)),
             (abs(v.Z), Vector(0, 0, math.copysign(1, v.Z)))]  # fmt: skip
    return max(comps, key=lambda c: c[0])[1]


def numbered_faces(shape, small_area=5.0):
    """(表示する部品, 名前, 色, 表の行)。面積 ``small_area`` mm2 未満は番号なしでまとめる。"""
    all_faces = list(shape.faces())
    faces = [f for f in all_faces if f.area >= small_area]
    small = [f for f in all_faces if f.area < small_area]
    labels, rows = [], []
    for i, f in enumerate(faces, start=1):
        c = f.center()
        n = f.normal_at(c)
        size = min(3.0, max(1.2, math.sqrt(f.area) / 3))
        labels.append(_text_at(str(i), c, n, size))
        rows.append((f"F{i}", f.geom_type.name, f"area {f.area:.1f}", c, n))
    objects = [*faces, Compound(labels, label="labels")]
    names = [f"F{i}" for i in range(1, len(faces) + 1)] + ["labels"]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(faces))] + ["#000000"]
    if small:
        objects.append(Compound(small, label="small"))
        names.append("small")
        colors.append(GRAY)
    return objects, names, colors, rows, len(small)


def numbered_edges(shape, min_len=3.0):
    """(表示する部品, 名前, 色, 表の行, 透明度)。長さ ``min_len`` mm 未満の辺は番号なしでまとめる。"""
    edges = list(shape.edges())
    big = [e for e in edges if e.length >= min_len]
    small = [e for e in edges if e.length < min_len]
    center = shape.center()
    labels, rows = [], []
    for i, e in enumerate(big, start=1):
        mid = e.position_at(0.5)
        out = _snap_axis(mid - center)  # 形の外側へ向けて読めるようにする
        labels.append(_text_at(str(i), mid, out, 2.0))
        d = e.tangent_at(0.5)
        rows.append((f"E{i}", e.geom_type.name, f"len {e.length:.1f}", mid, d))
    objects = [shape, *big, Compound(labels, label="labels")]
    names = ["body"] + [f"E{i}" for i in range(1, len(big) + 1)] + ["labels"]
    colors = ["#c0c0c0"] + [PALETTE[i % len(PALETTE)] for i in range(len(big))] + ["#000000"]
    alphas = [0.25] + [1.0] * (len(big) + 1)
    if small:
        objects.append(Compound(small, label="small"))
        names.append("small")
        colors.append(GRAY)
        alphas.append(1.0)
    return objects, names, colors, rows, alphas, len(small)


def print_table(rows, n_small, unit):
    print(f"{'id':<5}{'type':<10}{'size':<14}center (X, Y, Z)            normal / direction")
    for name, t, size, c, v in rows:
        print(
            f"{name:<5}{t:<10}{size:<14}({c.X:7.1f},{c.Y:7.1f},{c.Z:7.1f})   "
            f"({v.X:5.2f},{v.Y:5.2f},{v.Z:5.2f})"
        )
    print(f"(小さな{unit} {n_small} 個は番号なし、灰色の small でまとめた)")


def show_numbered(shape, mode="faces", threshold=None):
    """``mode`` は "faces" か "edges"。``threshold`` は小さい面の面積(既定 5)/辺の長さ(既定 3)。"""
    from ocp_vscode import Camera, show

    if mode == "faces":
        objects, names, colors, rows, n_small = numbered_faces(
            shape, 5.0 if threshold is None else threshold
        )
        print_table(rows, n_small, "面")
        show(*objects, names=names, colors=colors, reset_camera=Camera.KEEP)
    elif mode == "edges":
        objects, names, colors, rows, alphas, n_small = numbered_edges(
            shape, 3.0 if threshold is None else threshold
        )
        print_table(rows, n_small, "辺")
        show(*objects, names=names, colors=colors, alphas=alphas, reset_camera=Camera.KEEP)
    else:
        raise ValueError(f"mode must be 'faces' or 'edges', got {mode!r}")
    return rows


def load_shape(spec):
    """STEP ファイルのパス、または ``モジュール:関数``(形を返す)から形を得る。"""
    if ":" in spec and not Path(spec).exists():
        module, func = spec.split(":", 1)
        sys.path.insert(0, ".")
        return getattr(importlib.import_module(module), func)()
    return import_step(spec)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit(__doc__)
    spec = argv[0]
    mode = argv[1] if len(argv) > 1 else "faces"
    threshold = float(argv[2]) if len(argv) > 2 else None
    show_numbered(load_shape(spec), mode, threshold)


if __name__ == "__main__":
    main()
