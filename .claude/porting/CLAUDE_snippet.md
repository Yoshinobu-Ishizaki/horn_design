## 開発ルール

- パッケージ管理は uv のみ(`uv add` / `uv sync` / `uv run`)。pip は使わない。
- 実行は `uv run python ...`、テストは `uv run pytest`、静的解析は `uv run ruff check`。
- 3Dモデルは build123d で作る。寸法はmm単位。
- OCP Viewer への表示は、修正のたびに視点を戻さない(`show(..., reset_camera=Camera.KEEP)`)。`Camera.RESET` は使わない。
- `show` は `from bope_claude_cad.viewer import show` を使う(`ocp_vscode.show` と引数は同じ)。表示した形を `output/viewer_registry/` に記録し、ホバーの `[部品名 faces_6]` の部品名と ID だけで `uv run python -m bope_claude_cad.pick_id --part <部品名> faces <ID>` と引ける。部品名は必ず `names=[...]` で付ける。
- OCP Viewer を使い始めるときは、計測用バックエンドも必ず同時に起動する(測るかどうかを問わない。最初の `show` の前に済ませる)。ビューアを開いてもらったら、頼まれなくても手順2を `run_in_background` で実行する。バックエンドが動いていないと距離ツールが使えない。
  1. VS Code で OCP CAD Viewer を開いておく(既定のポートは 3939。`~/.ocpvscode` で確認できる)。
  2. バックエンドを起動して動かしたままにする(Bash の `run_in_background`。すでに動いていれば再起動しない。`skills/claude_cad_general/scripts/start_ocp_backend.py` は、動いていれば何もせず、ポートを `~/.ocpvscode` から読む): `PYTHONIOENCODING=utf-8 uv run python -m ocp_vscode --backend --port 3939`(`--port` は必須。「Viewer backend started」と出ればよい)。
     続けて、このリポジトリが使うビューアを記録する: `uv run python -m bope_claude_cad.viewer bind 3939`(バックエンドと同じポート。
     ウィンドウ(リポジトリ)ごとに別のビューアを開くので、`show`・断面・常駐プログラム(`bope_claude_cad.runner`)の表示先が
     混ざらないようにするため。開いているビューアが1つだけなら自動で記録される。複数あって未記録だとエラーになる)。
  3. 起動後に `show(..., reset_camera=Camera.KEEP)` でモデルを送る。バックエンドはこの時にモデルを受け取るので、順番が逆だと計測で `KeyError` を出して止まる。`show` で「backend is not connected」と警告が出たら、バックエンドが動いていない。
  4. ビューアの距離ツールで測りたい2か所(平行な2面など)を選ぶ。結果は3Dビューの線と数値、サイドバーの Distance に出る。
  - ビューアを再起動するとバックエンドも止まるので、手順2からやり直す。`show` を実行するスクリプトは送信後に終了してよい。
  - 文字コードのエラーが出るときは `PYTHONIOENCODING=utf-8` を付ける。
- OCP Viewer に寸法・孔の注記・表面粗さ記号を重ねるときは `bope_claude_cad.annotation` を使う(`dim_linear`・`hole_note`・`roughness_note`・`show_with_annotations`)。
  注記はソリッドではなく平らな面で、**輪郭表示 OFF(`Render.FACES`)・黒が既定**、フォントは Segoe UI Symbol(↧ ⌴ ⌵ ⌀ を出すため。カタカナは出ないので記号だけで書く)。
  見る向き(`view`)の平面に置くので、その向きから見る。補助線は対象の頂点から外へ引き出す。粗さ記号は JIS B 0031:2003(値は水平線の下)。詳細はモジュールの docstring。
- 履歴(`bope_claude_cad.history`)・常駐プログラム(`bope_claude_cad.runner`)・断面(`viewer.section` / `axis_section`)は各モジュールの docstring を参照。
- 治具の種類ごとに、パラメータ(dataclass)と生成関数を分け、`src/bope_claude_cad/` 配下にモジュールとして置く。
- 生成物(STEP/STL/DXF)は `output/` に出力する(git管理外)。

## 作業の置き場所

- 治具の種類ごとにモデル化の手順が異なるため、作業は原則として `jigs/<治具名>/` で行う(例: `jigs/brace_spot_lowbrass/`)。
- 治具フォルダの `.py` が増えたら、`lib/`(共通部品)・`parts/`(図ごとの生成スクリプト)・`tools/`(一覧・表示ほか)に分ける(例: `jigs/brace_spot_lowbrass/`。詳細はその README の「スクリプトの構成」)。
- 治具に固有でない共通の部品・関数・知見は、`src/bope_claude_cad/` やこのファイルに保存してよい。
- サンプル等で実際に設計するときは、作業フォルダに `worklog.md` を置き、作業履歴を時刻と一緒に記録する。後でまとめたり再現したりできるようにするため。
  - 形式は `skills/claude_cad_general/references/worklog_template.md` に従う(指示ごとに番号・時刻・指示・備考を1行)。
  - 時刻は追記時に `date +%s`(epoch)で取り、JST の時刻も併記する。時間は epoch の差で測る。
  - 記録を始める前の作業は、時刻不明の再構成と明記して書く。時刻を推測で書かない。
  - 例: `jigs/brace_spot_lowbrass/sample/bb106_brc13_assy/worklog.md`
