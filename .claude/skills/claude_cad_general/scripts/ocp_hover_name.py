"""OCP CAD Viewer 拡張のホバー表示に、部品名と面・辺の ID を足すパッチ(標準ライブラリだけで動く)。

OCP CAD Viewer の下のステータス行は、マウスを重ねた面・辺・ソリッドの種類と寸法
(`plane: area ≈ …`、`solid: N faces, … vol ≈ …`)だけを出し、部品名も ID も出さない。
VS Code にインストールされた拡張の three-cad-viewer.esm.js の `hoverStatusText()` を
包んで、行の頭に `[部品名 faces_6]`(show() に渡した名前と、面・辺・頂点の ID)を付ける。
ソリッドにマウスを重ねたときは `[部品名]` だけ。ID は、その部品の `shape.faces()` / `shape.edges()` の
0 始まりの添字なので、「copy shape id」をしなくても、`pick_id` にそのまま渡せる。
旧版のパッチ(部品名だけ)が当たっているときは、`apply` が .orig から作り直して新版にする。

使い方:
    python ocp_hover_name.py status   # 対象ファイルと、パッチ済みかどうか
    python ocp_hover_name.py apply    # パッチを当てる(元のファイルを .orig に保存。何度実行しても同じ)
    python ocp_hover_name.py revert   # .orig から元に戻す

当てたあとは VS Code のウィンドウを再読み込みする(Developer: Reload Window)。
拡張を更新すると改造は消えるので、そのときは apply をやり直す。
拡張のバージョン(three-cad-viewer)が変わって `function hoverStatusText(` が見つからないときは、
何も書き換えずに終了コード 2 で終わる。
"""

import argparse
import sys
from pathlib import Path

EXT_GLOB = "bernhard-42.ocp-cad-viewer-*"
REL = Path("node_modules/three-cad-viewer/dist/three-cad-viewer.esm.js")
MARK_OLD = "PATCH(local): hover name - prefix"  # 旧版(部品名だけ)。見つけたら .orig から作り直す
MARK = "PATCH(local): hover name+id"
ORIG_DEF = "function hoverStatusText("
RENAMED_DEF = "function hoverStatusTextOrig("
WRAPPER = f"""// {MARK} - prefix the hover status line with the part name and, for a face/edge/vertex, its id (e.g. faces_6).
function hoverStatusText(info, fromSolid, provider) {{
    const t = hoverStatusTextOrig(info, fromSolid, provider);
    const solid = fromSolid && info.solidPath != null;
    const p = solid ? info.solidPath : String(info.path).replace(/\\/(faces|edges|vertices)\\/[^/]+$/, "");
    const name = p.split("/").filter(Boolean).pop() || "";
    const id = solid ? "" : (String(info.path).split("/").filter(Boolean).pop() || "");
    const head = id && id !== name ? `${{name}} ${{id}}` : name;
    return head ? `[${{head}}] ${{t}}` : t;
}}
"""


def find_targets() -> list[Path]:
    root = Path.home() / ".vscode" / "extensions"
    found = sorted(d / REL for d in root.glob(EXT_GLOB) if (d / REL).is_file())
    # 独立ビューア(ocp_viewer パッケージ)の JS も対象にする。カレントの .venv から探す
    found += sorted(Path.cwd().glob(".venv/lib/python*/site-packages/ocp_viewer/server/static/js/three-cad-viewer.esm.js"))
    return found


def is_patched(text: str) -> bool:
    return MARK in text


def apply(path: Path) -> int:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if is_patched(text):
        print(f"パッチ済み: {path}")
        return 0
    if MARK_OLD in text:  # 旧版(部品名だけ)を、バックアップから戻して新版を当て直す
        orig = path.with_name(path.name + ".orig")
        if not orig.exists():
            print(f"旧版のパッチだが、バックアップが無い: {orig}", file=sys.stderr)
            return 2
        raw = orig.read_bytes()
        text = raw.decode("utf-8")
        print("旧版のパッチを、バックアップから戻して当て直す")
    if text.count(ORIG_DEF) != 1:
        print(f"hoverStatusText が見つからない(または複数): {path}", file=sys.stderr)
        return 2
    orig = path.with_name(path.name + ".orig")
    if not orig.exists():
        orig.write_bytes(raw)
        print(f"バックアップ: {orig}")
    nl = "\r\n" if "\r\n" in text else "\n"
    wrapper = WRAPPER.replace("\n", nl)
    path.write_bytes((text.replace(ORIG_DEF, wrapper + RENAMED_DEF, 1)).encode("utf-8"))
    print(f"パッチを当てた: {path}\nVS Code のウィンドウを再読み込みしてください(Developer: Reload Window)")
    return 0


def revert(path: Path) -> int:
    orig = path.with_name(path.name + ".orig")
    if not orig.exists():
        print(f"バックアップが無い: {orig}", file=sys.stderr)
        return 2
    path.write_bytes(orig.read_bytes())
    print(f"元に戻した: {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["status", "apply", "revert"])
    args = ap.parse_args()
    targets = find_targets()
    if not targets:
        print("OCP CAD Viewer の拡張が見つからない(~/.vscode/extensions)", file=sys.stderr)
        return 2
    rc = 0
    for t in targets:
        if args.cmd == "status":
            print(("パッチ済み" if is_patched(t.read_text(encoding="utf-8")) else "未パッチ") + f": {t}")
        elif args.cmd == "apply":
            rc = max(rc, apply(t))
        else:
            rc = max(rc, revert(t))
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
