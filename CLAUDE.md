# horn_design

ホルンの設計。3D モデルは build123d で作り、VS Code の OCP CAD Viewer(ocp-vscode)で見ながら進める。
スキルは `.claude/skills/`(`claude_cad_general`・`claude_cad_vss`・`claude_cad_surface_map`。bope_claude_cad から移植。読み替えは `claude_cad_general/SKILL.md` の冒頭)。

## 開発ルール

- パッケージ管理は uv のみ(`uv add` / `uv sync` / `uv run`)。pip は使わない。
- 実行は `uv run python ...`、テストは `uv run pytest`、静的解析は `uv run ruff check`。バイトコードを作らないよう `PYTHONDONTWRITEBYTECODE=1` を付ける。
- 3Dモデルは build123d で作る。寸法はmm単位。
- 共通の実装は `src/bope_claude_cad/`(`vss`・`surface_map`・`viewer`・`pick_id`・`numbered_view`・`history`・`runner`・`annotation`・`screws`)。`.claude/skills/claude_cad_general/scripts/` の同名ファイルはその写しなので、直したら両方をそろえる。
- OCP Viewer への表示は、修正のたびに視点を戻さない(`show(..., reset_camera=Camera.KEEP)`)。`Camera.RESET` は使わない。
- `show` は `from bope_claude_cad.viewer import show` を使う(`ocp_vscode.show` と引数は同じ)。表示した形を `output/viewer_registry/` に記録し、ホバーの `[部品名 faces_6]` の部品名と ID だけで `uv run python -m bope_claude_cad.pick_id --part <部品名> faces <ID>` と引ける。部品名は必ず `names=[...]` で付ける。
- OCP Viewer を使い始めるときは、計測用バックエンドも必ず同時に起動する(測るかどうかを問わない。最初の `show` の前に済ませる)。ビューアを開いてもらったら、頼まれなくても手順2を `run_in_background` で実行する。
  1. VS Code で OCP CAD Viewer を開いておく(インタプリタはこのリポジトリの `.venv/bin/python`。既定のポートは 3939。`~/.ocpvscode` で確認できる)。
  2. バックエンドを起動して動かしたままにする(すでに動いていれば再起動しない。`.claude/skills/claude_cad_general/scripts/start_ocp_backend.py` は、動いていれば何もせず、ポートを `~/.ocpvscode` から読む): `PYTHONIOENCODING=utf-8 uv run python -m ocp_vscode --backend --port 3939`(`--port` は必須。「Viewer backend started」と出ればよい)。
     続けて `uv run python -m bope_claude_cad.viewer bind 3939` で、このリポジトリが使うビューアを記録する(開いているビューアが1つだけなら自動で記録される)。
  3. 起動後に `show(..., reset_camera=Camera.KEEP)` でモデルを送る。順番が逆だと計測で `KeyError` を出して止まる。「backend is not connected」と出たら、バックエンドが動いていない。
  4. ビューアの距離ツールで測りたい2か所を選ぶ。結果は3Dビューの線と数値、サイドバーの Distance に出る。
  - ビューアを再起動するとバックエンドも止まるので、手順2からやり直す。
- 寸法・注記を重ねるときは `bope_claude_cad.annotation`(詳細は `.claude/skills/claude_cad_general/references/annotation.md`)。
- 生成物(STEP/STL/DXF)は `output/` に出力する(git管理外)。

## 作業の置き場所

- 設計の作業は `cad/<名前>/` で行う(名前は最初にユーザーに確認する。`cad/` には FreeCAD のファイルもある)。ビューアに出すモデルのコードは `cad/<名前>/ocp/`。`.py` が増えたら `lib/`・`parts/`・`tools/` に分ける。
- 作業フォルダに `worklog.md` を置き、作業履歴を時刻と一緒に記録する(書式は `.claude/skills/claude_cad_general/references/worklog_template.md`)。時刻は追記時に `date +%s` で取り、JST(`TZ=JST-9 date`)も併記する。推測で書かない。

## 社内図面の扱い

- `jigs/*_seat/input/` と `.claude/skills/claude_cad_vss/sample/` は 社内図面(サンプル)。remote が GitHub なので、`.gitignore` で除外してある。commit・push しない。
