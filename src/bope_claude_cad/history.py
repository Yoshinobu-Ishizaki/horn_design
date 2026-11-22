"""設計スクリプトの履歴(表示のたびに写しを残し、戻る・進むで行き来する)。

`bope_claude_cad.viewer.show` が、呼び出したスクリプトの写しを残す。スクリプトの隣の
`.history/<スクリプト名>/` に `0001.py`、`0002.py`、... と `index.json` を置く。

- 履歴は git に入れない。`.history/` に `.gitignore`(中身は `*`)を自動で作るので、
  どのリポジトリで使っても無視される(このリポジトリの .gitignore にも `.history/` を足してある)
- 写しは呼び出したスクリプト1ファイルだけ。そのスクリプトが読み込む別のモジュール(lib/ など)の変更は残らない
- 今の位置の写しと同じ内容なら、写しを増やさない(同じ形を何度表示しても増えない)
- 記録には親を残す。index.json の current が「今の位置」。戻る(undo)は親へ、進む(redo)は
  今の位置から作られた一番新しい記録へ移る。戻ったあとに直して表示すると枝分かれする(前の記録は消さない)
- 戻る・進む・restore は、スクリプトを写しの内容に書き換える。移る前に、まだ記録していない手直しは先に残す
- 環境変数 `BOPE_HISTORY=0` で記録しない

コマンドライン(標準ライブラリだけで動く)::

    uv run python -m bope_claude_cad.history list <スクリプト>
    uv run python -m bope_claude_cad.history undo <スクリプト> [--run]
    uv run python -m bope_claude_cad.history redo <スクリプト> [--run]
    uv run python -m bope_claude_cad.history restore <スクリプト> <No> [--run]

`--run` を付けると、移ったあとにそのスクリプトを実行して表示し直す。実行は常駐プログラム(runner.py)で行うので、
2回目からは速い(約 4 秒 → 1.5 秒)。使いたくないときは環境変数 `BOPE_RUNNER=0`。
<スクリプト> の代わりに `--last` を付けると、最後に `show` したスクリプトを使う
(`output/viewer_registry/last_script.json` に記録。VS Code 拡張 vscode-ext/bope-history のボタン・Ctrl+Z / Ctrl+Y が使う)。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HISTORY_DIR = ".history"


def _sibling(name: str):
    """同じフォルダの別モジュール。パッケージ(bope_claude_cad.<name>)としても、スキルの scripts/ の単体ファイルとしても読める。"""
    import importlib

    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


def enabled() -> bool:
    return os.environ.get("BOPE_HISTORY", "1") != "0"


def _folder(script: Path) -> Path:
    return script.parent / HISTORY_DIR / script.stem


def _load(script: Path) -> dict:
    index = _folder(script) / "index.json"
    if not index.exists():
        return {"current": None, "items": []}
    return json.loads(index.read_text(encoding="utf-8"))


def _save(script: Path, data: dict) -> None:
    folder = _folder(script)
    folder.mkdir(parents=True, exist_ok=True)
    # 履歴は git に入れない。.history/ の中身を全部無視する(.gitignore 自身も無視される)
    ignore = script.parent / HISTORY_DIR / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8", newline="\n")
    (folder / "index.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def entries(script: Path | str) -> list[dict]:
    return _load(Path(script).resolve())["items"]


def current(script: Path | str) -> int | None:
    return _load(Path(script).resolve())["current"]


def find(script: Path | str, no: int) -> dict:
    for item in entries(script):
        if item["no"] == no:
            return item
    raise KeyError(f"履歴 No.{no} はありません")


def _content(script: Path, item: dict) -> str:
    return (_folder(script) / item["file"]).read_text(encoding="utf-8")


def record(script: Path | str, note: str = "表示") -> int | None:
    """スクリプトの写しを残し、番号を返す。今の位置の写しと同じなら残さず None を返す。"""
    script = Path(script).resolve()
    content = script.read_text(encoding="utf-8")
    data = _load(script)
    items, cur = data["items"], data["current"]
    if cur is not None and _content(script, find(script, cur)) == content:
        return None
    no = items[-1]["no"] + 1 if items else 1
    name = f"{no:04d}.py"
    _folder(script).mkdir(parents=True, exist_ok=True)
    (_folder(script) / name).write_text(content, encoding="utf-8", newline="")
    items.append({
        "no": no, "epoch": int(time.time()), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note, "file": name, "parent": cur,
    })
    data["current"] = no
    _save(script, data)
    return no


def _move(script: Path, item: dict) -> dict:
    data = _load(script)
    script.write_text(_content(script, item), encoding="utf-8", newline="")
    data["current"] = item["no"]
    _save(script, data)
    return item


def restore(script: Path | str, no: int) -> dict:
    """No.no へ移る。まだ記録していない手直しがあれば、先に残す。"""
    script = Path(script).resolve()
    item = find(script, no)
    record(script, "戻す前の状態")
    return _move(script, item)


def undo(script: Path | str) -> dict | None:
    """1つ前(今の位置の親)へ戻る。戻れなければ None。"""
    script = Path(script).resolve()
    record(script, "戻る前の状態")
    cur = current(script)
    if cur is None:
        return None
    parent = find(script, cur)["parent"]
    return None if parent is None else _move(script, find(script, parent))


def redo(script: Path | str) -> dict | None:
    """1つ後(今の位置から作られた一番新しい記録)へ進む。進めなければ None。"""
    script = Path(script).resolve()
    record(script, "進む前の状態")
    children = [i for i in entries(script) if i["parent"] == current(script)]
    return _move(script, children[-1]) if children else None


def table(script: Path | str) -> str:
    items, cur = entries(script), current(script)
    if not items:
        return "履歴はまだありません\n"
    lines = ["No   時刻                 内容"]
    for item in reversed(items):
        mark = "  <- 今" if item["no"] == cur else ""
        lines.append(f"{item['no']:>3}  {item['time']}  {item['note']}{mark}")
    return "\n".join(lines) + "\n"


LAST_FILE = "last_script.json"


def _last_path() -> Path:
    return _sibling("viewer").registry_dir() / LAST_FILE


def set_last(script: Path | str) -> None:
    """最後に表示したスクリプトを覚える(VS Code のボタン・Ctrl+Z が、どのスクリプトを戻すか知るため)。"""
    p = _last_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"script": str(Path(script).resolve()), "epoch": int(time.time())}), encoding="utf-8")


def last_script() -> Path | None:
    p = _last_path()
    if not p.is_file():
        return None
    return Path(json.loads(p.read_text(encoding="utf-8"))["script"])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    run = "--run" in args
    args = [a for a in args if a != "--run"]
    if "--last" in args:  # スクリプトの代わりに、最後に表示したスクリプトを使う
        args.remove("--last")
        last = last_script()
        if last is None:
            print("最後に表示したスクリプトの記録がありません(show で表示してから)")
            return 1
        args.insert(1, str(last))
    if len(args) < 2 or args[0] not in ("list", "undo", "redo", "restore"):
        print(__doc__)
        return 2
    cmd, script = args[0], Path(args[1]).resolve()
    if not script.is_file():
        print(f"スクリプトがありません: {script}")
        return 1
    if cmd == "list":
        print(table(script), end="")
        return 0
    try:
        item = restore(script, int(args[2])) if cmd == "restore" else {"undo": undo, "redo": redo}[cmd](script)
    except (KeyError, IndexError, ValueError) as ex:
        print(f"できません: {ex}")
        return 1
    if item is None:
        print("これより" + ("前" if cmd == "undo" else "後") + "の履歴はありません")
        return 1
    print(f"No.{item['no']}({item['note']}、{item['time']})に移りました: {script.name}")
    if run:
        # 常駐プログラムで実行する(build123d を毎回読み込まない)
        return _sibling("runner").run_script(script, cwd=Path.cwd())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
