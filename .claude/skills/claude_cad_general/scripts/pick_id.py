"""OCP Viewer が示す面・辺の ID(`faces_12`、`edges_5` の数字)から、その面・辺の中身を引く。

ビューアーで面や辺にマウスを重ねる/選ぶと、ツリーのパスに `<部品>/faces/faces_12` のような ID が出る。
この数字は、その部品の `shape.faces()` / `shape.edges()` の並びの 0 始まりの添字。
ここでは ID から種類・大きさ・中心・向き・範囲を表にして、「その面は何か」を言葉で確かめられるようにする。
色替えや番号振りはしない(表示はそのまま)。

使い方(どのフォルダからでも。`bope_claude_cad.viewer.show` で表示した形を、部品名と ID だけで引く):
    uv run python -m bope_claude_cad.pick_id --part clamp_jaw faces 6 7
    uv run python -m bope_claude_cad.pick_id --part clamp_jaw edges 12
    uv run python -m bope_claude_cad.pick_id --list          # 最後に表示した部品の一覧

`show` を使っていない形は、従来どおり、形を返すものを指定して引く(リポジトリルートから):
    uv run python -m bope_claude_cad.pick_id <STEP ファイル | モジュール:関数> faces 12 30 31
    uv run python -m bope_claude_cad.pick_id <STEP ファイル | モジュール:関数> edges 5
"""

import contextlib
import sys
import time

from bope_claude_cad.numbered_view import load_shape


def describe_face(f, i):
    c = f.center()
    n = f.normal_at(c)
    bb = f.bounding_box()
    extra = ""
    if f.geom_type.name in ("CYLINDER", "CONE", "SPHERE", "TORUS"):
        with contextlib.suppress(Exception):  # 半径が取れない面は省く
            extra = f"  R≈{f.radius:.2f}"
    return (
        f"faces_{i}: {f.geom_type.name} area {f.area:.1f}{extra}\n"
        f"    center ({c.X:.2f}, {c.Y:.2f}, {c.Z:.2f})  normal@center ({n.X:.2f}, {n.Y:.2f}, {n.Z:.2f})\n"
        f"    bbox X[{bb.min.X:.2f}, {bb.max.X:.2f}] Y[{bb.min.Y:.2f}, {bb.max.Y:.2f}] "
        f"Z[{bb.min.Z:.2f}, {bb.max.Z:.2f}]"
    )


def describe_edge(e, i):
    a, b, m = e.position_at(0), e.position_at(1), e.position_at(0.5)
    extra = ""
    if e.geom_type.name == "CIRCLE":
        with contextlib.suppress(Exception):
            extra = f"  R≈{e.radius:.2f}"
    return (
        f"edges_{i}: {e.geom_type.name} len {e.length:.2f}{extra}\n"
        f"    start ({a.X:.2f}, {a.Y:.2f}, {a.Z:.2f})  mid ({m.X:.2f}, {m.Y:.2f}, {m.Z:.2f})  "
        f"end ({b.X:.2f}, {b.Y:.2f}, {b.Z:.2f})"
    )


def describe(shape, kind, ids):
    """``kind`` は "faces" か "edges"。ID ごとの説明の文字列のリストを返す。"""
    items = list(shape.faces() if kind == "faces" else shape.edges())
    fn = describe_face if kind == "faces" else describe_edge
    out = []
    for i in ids:
        out.append(
            fn(items[i], i) if 0 <= i < len(items) else f"{kind}_{i}: 範囲外(0..{len(items) - 1})"
        )
    return out


def list_parts():
    """最後に表示した部品の一覧(名前、面数、辺数、保存時刻)。"""
    from bope_claude_cad.viewer import read_index

    index = read_index()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(index["saved_at"]))
    lines = [f"最後に表示した部品({stamp}、epoch {index['saved_at']})"]
    lines += [f"  {n}: faces {p['faces']}, edges {p['edges']}" for n, p in index["parts"].items()]
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--list"]:
        print(list_parts())
        return
    if argv[:1] == ["--part"]:
        if len(argv) < 4 or argv[2] not in ("faces", "edges"):
            raise SystemExit(__doc__)
        from bope_claude_cad.viewer import load_part

        try:
            shape = load_part(argv[1])
        except (KeyError, FileNotFoundError) as ex:
            raise SystemExit(str(ex.args[0])) from ex
        print("\n".join(describe(shape, argv[2], [int(a) for a in argv[3:]])))
        return
    if len(argv) < 3 or argv[1] not in ("faces", "edges"):
        raise SystemExit(__doc__)
    shape = load_shape(argv[0])
    print("\n".join(describe(shape, argv[1], [int(a) for a in argv[2:]])))


if __name__ == "__main__":
    main()
