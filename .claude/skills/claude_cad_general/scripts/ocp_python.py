"""OCP CAD Viewer 拡張が使う Python を、ワークスペースのインタプリタとは別に指定するパッチ(標準ライブラリだけで動く)。

OCP CAD Viewer 拡張は、VS Code で選ばれた Python インタプリタ(Python 拡張の選択)を使う。ビューアを開くときに
その Python に `ocp_vscode` があるかを調べ(無ければ「OCP VS Code not found for ... Select another Python
interpreter?」と聞き、no なら開かない)、計測用バックエンドもその Python で起動する。作業リポジトリに測定などの
ための固有の .venv があると、ワークスペースのインタプリタを差し替えるわけにはいかない。

このパッチは、拡張の `out/utils.js` の `getPythonPath` の頭に、OCP CAD Viewer 専用の Python の指定を足す。
ワークスペースのインタプリタ(Python 拡張・Pylance・ターミナル・他のツール)は変えない。

- 指定は VS Code の設定 `OcpCadViewer.advanced.pythonPath`(ユーザー設定でもワークスペース設定でもよい。
  `${userHome}` が使える)。設定が無いときは、このスキルの共有の実行環境
  `${userHome}/.claude/skills/claude_cad_general/.venv/Scripts/python.exe` を使う。
- 空文字列 `""` を設定すると、このパッチは何もしない(従来どおりワークスペースのインタプリタ)。
- 指定した Python が無いときも、従来どおりワークスペースのインタプリタに戻る。
- `out/extension.js` の、ワークスペースのインタプリタが変わったときの処理も、同じ指定を見るように直す
  (そのままだと、インタプリタを変えたときにビューアを閉じ、ワークスペースの Python に切り替えてしまう)。

使い方:
    python ocp_python.py status   # 対象ファイル、パッチ済みかどうか、既定の Python があるか
    python ocp_python.py apply    # パッチを当てる(元のファイルを .orig に保存。何度実行しても同じ)
    python ocp_python.py revert   # .orig から元に戻す

当てたあとは VS Code のウィンドウを再読み込みする(Developer: Reload Window)。
拡張を更新すると改造は消えるので、そのときは apply をやり直す。書き換える箇所が見つからないとき
(拡張の版が変わったとき)は、何も書き換えずに終了コード 2 で終わる。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

EXT_GLOB = "bernhard-42.ocp-cad-viewer-*"
MARK = "PATCH(local): ocp python"

# utils.js: getPythonPath の頭で、OCP CAD Viewer 専用の Python を返す
UTILS = Path("out/utils.js")
UTILS_ANCHOR = "    static async getPythonPath(document, notify = false) {"
UTILS_INSERT = """
        // PATCH(local): ocp python - use OcpCadViewer.advanced.pythonPath (default: shared venv of the claude_cad_general skill)
        const ocpPython = ocpPythonOverride();
        if (ocpPython) {
            if (notify) {
                output.info(`utils.PythonPath: '${ocpPython}' (OcpCadViewer.advanced.pythonPath)`);
            }
            return ocpPython;
        }"""
UTILS_FUNC_ANCHOR = "function getPythonPath(notify = false) {"
UTILS_FUNC = """// PATCH(local): ocp python - the Python used only by OCP CAD Viewer (undefined: use the workspace interpreter)
function ocpPythonOverride() {
    let p = vscode.workspace.getConfiguration("OcpCadViewer.advanced").get("pythonPath");
    if (p === undefined || p === null) {
        const sub = process.platform === "win32" ? "Scripts/python.exe" : "bin/python";
        p = "${userHome}/.claude/skills/claude_cad_general/.venv/" + sub;
    }
    if (typeof p !== "string" || p.trim() === "") {
        return undefined;
    }
    p = path.normalize(p.split("${userHome}").join(os.homedir()));
    if (!fs.existsSync(p)) {
        output.info(`utils.ocpPythonOverride: '${p}' not found, using the workspace interpreter`);
        return undefined;
    }
    return p;
}
"""

# extension.js: ワークスペースのインタプリタが変わったときも、同じ指定を見る
EXT = Path("out/extension.js")
EXT_OLD = "let pythonPath = extension.exports.settings.getExecutionDetails().execCommand[0];"
EXT_NEW = "let pythonPath = await (0, utils_1.getPythonPath)(); // PATCH(local): ocp python"


def default_python() -> Path:
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return Path.home() / ".claude" / "skills" / "claude_cad_general" / ".venv" / Path(*sub)


def find_exts(root: Path | None = None) -> list[Path]:
    root = root or Path.home() / ".vscode" / "extensions"
    return sorted(d for d in root.glob(EXT_GLOB) if (d / UTILS).is_file() and (d / EXT).is_file())


def _nl(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def patch_utils(text: str) -> str:
    if text.count(UTILS_ANCHOR) != 1 or text.count(UTILS_FUNC_ANCHOR) != 1:
        raise ValueError("utils.js の getPythonPath が見つからない(または複数)")
    nl = _nl(text)
    text = text.replace(UTILS_ANCHOR, UTILS_ANCHOR + UTILS_INSERT.replace("\n", nl), 1)
    return text.replace(UTILS_FUNC_ANCHOR, UTILS_FUNC.replace("\n", nl) + UTILS_FUNC_ANCHOR, 1)


def patch_ext(text: str) -> str:
    if text.count(EXT_OLD) != 1:
        raise ValueError("extension.js の getExecutionDetails().execCommand[0] が見つからない(または複数)")
    return text.replace(EXT_OLD, EXT_NEW, 1)


def is_patched(ext: Path) -> bool:
    return all(MARK in (ext / rel).read_text(encoding="utf-8") for rel in (UTILS, EXT))


def apply(ext: Path) -> int:
    jobs = [(ext / UTILS, patch_utils), (ext / EXT, patch_ext)]
    new = {}
    for path, fn in jobs:  # 両方とも書き換えられると確かめてから書く
        text = path.read_bytes().decode("utf-8")
        if MARK in text:
            continue
        try:
            new[path] = (text, fn(text))
        except ValueError as e:
            print(f"{e}: {path}(拡張の版が変わった。何も書き換えない)", file=sys.stderr)
            return 2
    if not new:
        print(f"パッチ済み: {ext}")
        return 0
    for path, (old, text) in new.items():
        orig = path.with_name(path.name + ".orig")
        if not orig.exists():
            orig.write_bytes(old.encode("utf-8"))
            print(f"バックアップ: {orig}")
        path.write_bytes(text.encode("utf-8"))
    print(f"パッチを当てた: {ext}\nVS Code のウィンドウを再読み込みしてください(Developer: Reload Window)")
    return 0


def revert(ext: Path) -> int:
    rc = 0
    for rel in (UTILS, EXT):
        path = ext / rel
        orig = path.with_name(path.name + ".orig")
        if MARK not in path.read_text(encoding="utf-8"):
            print(f"パッチは当たっていない: {path}")
            continue
        if not orig.exists():
            print(f"バックアップが無い: {orig}", file=sys.stderr)
            rc = 2
            continue
        path.write_bytes(orig.read_bytes())
        print(f"元に戻した: {path}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["status", "apply", "revert"])
    ap.add_argument("--ext-root", type=Path, help="拡張のフォルダ(既定: ~/.vscode/extensions。テスト用)")
    args = ap.parse_args(argv)
    exts = find_exts(args.ext_root)
    if not exts:
        print("OCP CAD Viewer の拡張が見つからない(~/.vscode/extensions)", file=sys.stderr)
        return 2
    rc = 0
    for ext in exts:
        if args.cmd == "status":
            print(("パッチ済み" if is_patched(ext) else "未パッチ") + f": {ext}")
        elif args.cmd == "apply":
            rc = max(rc, apply(ext))
        else:
            rc = max(rc, revert(ext))
    if args.cmd == "status":
        py = default_python()
        print(f"既定の Python(設定 OcpCadViewer.advanced.pythonPath が無いとき): {py.as_posix()}"
              + ("" if py.is_file() else "(無い。`uv sync --frozen --project .claude/skills/claude_cad_general` で作る)"))
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
