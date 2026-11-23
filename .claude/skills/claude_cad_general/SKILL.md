---
name: claude_cad_general
description: 部品・治具・型などの3Dモデルを、OCP CAD Viewer を見ながらユーザーと会話して設計する共通基盤のスキル。治具の種類を問わず、共通の決まり(uv、build123d、git、worklog、OCP Viewer と計測用バックエンド、値を推測しない、数値で確かめる、文字化け対策)と、共通の道具(STEP の調査・名称付け・向き決め、関数集、画像出力、面・辺の指し示し、MISUMI の部品選定、ボルト穴の寸法、STEP/STL の配布と git 管理、ビューアへの注記(寸法・孔の注記・表面粗さ記号)の重ね表示、履歴と取り消し、断面、複数ビューアの表示先)を持つ。検査治具(claude_cad_shape_check)・スポット治具(claude_cad_spot_jig)・可変断面スイープ(claude_cad_vss)などの個別スキルは、このスキルに従い、固有の情報だけを足す。入力は STEP、図面(DXF・PDF・画像)、スケッチ、寸法の言葉のどれでもよく、何もない状態からでも始められる。「会話しながら3D設計したい」「build123dでモデルを作りたい」「OCPで形を見ながら作りたい」「治具を設計したい」「型を設計したい」「MISUMIの部品を探したい」「ミスミの型番を確認したい」「Cナビ」「meviy」「ボルトの通し穴・ザグリの寸法」「成果物をReleaseに上げて」「STEPを配布したい」「最終稿をリリースして」「releaseフォルダにコミットして」「この面を直して」「どの部分か指したい」「面に番号をつけて」「辺に番号をつけて」「面を名前で呼びたい」「見ている部分を伝えたい」「寸法を付けて」「寸法線を出して」「孔の注記を付けて」「M4↧10 のような注記」「表面粗さ記号を付けて」「Ra を付けて」「annotation」「前の形に戻して」「取り消して」「履歴を見せて」「断面で見せて」「この軸で切って」「claude_cad_general」などのトリガーで起動する。
---

# claude_cad_general

## horn_design での使い方(このリポジトリでは、以下が本文より優先する)

このスキル一式は `bope_claude_cad` から `horn_design`(ホルンの設計)へ移植したもの(2026-11-22)。本文の「別のリポジトリで使うとき」の決まりは、ここでは次のように読み替える。

- **スキルの置き場所**: `~/.claude/skills/` ではなく、このリポジトリの `.claude/skills/`(プロジェクトのスキル)。原本もここ。個別スキルから共通の道具は `../claude_cad_general/...` で参照する(本文どおり)。
- **実行環境**: スキル専用の共有 `.venv` は使わない。build123d・ocp-vscode・ezdxf・numpy・scipy はリポジトリの `.venv`(`pyproject.toml` / `uv.lock`)に入れてあり、`src/bope_claude_cad` もパッケージとして入っている。実行は `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 uv run python ...`、テストは `uv run pytest`。`uv run --frozen --project .claude/skills/claude_cad_general` は使わない。依存を足すときは、ユーザーに断ってから `uv add`。
- **OCP CAD Viewer が使う Python**: 拡張に `scripts/ocp_python.py` のパッチを当て、`.vscode/settings.json` の `OcpCadViewer.advanced.pythonPath` で、このリポジトリの `.venv/bin/python` を指定している(`python.defaultInterpreterPath` も同じ)。
- **拡張へのパッチ(2026-11-22 に 4.3.0 へ当てた)**: `ocp_python.py`・`ocp_hover_name.py`・`ocp_mouse.py`(既定の geomagic)・`ocp_view_keys.py`(7 キー = top view。2026-11-24)。拡張を更新するとパッチが消えるので、`uv run --no-project python -I .claude/skills/claude_cad_general/scripts/<名前>.py apply` を4つとも当て直し、VS Code を Reload Window する。状態は `status` で見る。
- **ocp-vscode の版**: `.venv` には `ocp-vscode 4.3.x` が入っている。VS Code の OCP CAD Viewer 拡張も 4.3 系にそろえる(ずれたら `pyproject.toml` の範囲を拡張の系列に合わせて `uv lock`・`uv sync`)。
- **OS**: Linux。Windows 向けの文字化け対策(10)は、日本語を Write / Edit で書く・コミットメッセージを `git commit -F` で渡す、の部分だけ守ればよい。注記のフォント Segoe UI Symbol はこの PC に無いので、記号が出ないときは別のフォント(DejaVu Sans など)を使う。
- **作業場所**: `wd` = `cad/<名前>/`(例: `cad/bell_01/`。`cad/` には FreeCAD のファイルもある)。ビューアに出すモデルのコードは `wd/ocp/`。生成物は `output/`(git 管理外)。名前は最初にユーザーに確認する。
- **サンプル**: `jigs/refbell_seat/`(surface_map)と `claude_cad_vss/sample/`(vss)は 社内図面を含むため、`.gitignore` で git 管理外にしてある。このリポジトリの remote は GitHub なので、これらを commit・push しない。
- 治具・型(MISUMI、ボルト穴、プレスなど)向けの記述は、楽器の設計では使わないことが多いが、そのまま残してある。

治具の種類に縛られず、ユーザーと会話しながら 3D モデルを作る共通基盤のスキル。見て、指示を受けて、直して、また見る、の繰り返し。

## 個別スキルとの関係

- **このスキルが持つもの**: 共通の決まり、進め方の骨格、共通の道具(`scripts/`)と資料(`references/`)。OCP Viewer、市販部品(MISUMI)、ボルト穴、面・辺の指し示し、build123d の作り方は、すべてここ。
- **個別スキル**(`claude_cad_shape_check`: 検査治具、`claude_cad_spot_jig`: スポット治具、`claude_cad_press_dieset`: プレスのダイセットと抜き型、`claude_cad_vss`: 芯線に沿って径が変わる管(ベルなど)の可変断面スイープ、`claude_cad_surface_map`: 曲面に輪郭をマップして厚みを付ける座(支柱座など)。作成中で未インストールのもの: `claude_cad_tube_bend_mold`(曲げ型)、`claude_cad_calibration_mold`(玉通し型))は、このスキルを先に読み込んで従い、**その治具に固有の情報**(入力の形式、固有の決まり、固有の進め方、固有のスクリプトとデータ)だけを足す。共通の決まりは個別スキルに書き写さない。
- 個別スキルに当てはまらない案件、または種類がまだ決まらない案件は、このスキルだけで進める。途中で種類が定まったら、専用スキルへの切り替えを提案する。
- 個別スキルから共通の道具を呼ぶときは、`../claude_cad_general/scripts/...`、`../claude_cad_general/references/...` の形で参照する(`~/.claude/skills/` に `claude_cad_general` が入っていること)。

## 共通仕様(どの案件でも守る)

1. **ツール**: パッケージ管理と実行は uv(`uv run python ...`、pip は使わない)。3D は build123d、2D 図面は必要なとき ezdxf、表示は OCP CAD Viewer(`ocp_vscode`)。寸法は mm。データフレームは polars。別のリポジトリでは、このスキルの共有の実行環境で動かす(`uv run --frozen --project .claude/skills/claude_cad_general python ...`。下の「実行環境」)。`--with` での都度の導入や、相手のリポジトリへの `pyproject.toml`・`.venv` の追加はしない。
2. **作業場所**: リポジトリ `bope_claude_cad` の中では、従来どおり `jigs/<治具名>/`(治具名は最初にユーザーに確認する。決まっていなければ案件名)とし、Python ファイルもその直下に置く。別のリポジトリで呼ばれたときは、作業場所を `wd` と呼び、`wd` = `<リポジトリのルート>/draw/<治具名>/` とする。OCP CAD Viewer に表示するモデルを作る Python ファイルは、既定で `wd/ocp/` に保存する。そのほかの `.py` が増えたら `lib/`・`parts/`・`tools/` に分ける。治具に固有でない共通の部品・関数・知見は `src/bope_claude_cad/` に置いてよい。コード・名称ファイル・作業記録・手順書・画像は、すべて作業場所に保存する。生成物(STEP/STL/DXF)は `output/`(git 管理外)。出力形式と出力先も最初に確認する。
3. **git**: 作業フォルダが git のリポジトリであること(無ければ `git init` を提案する)。区切り(要件が決まった、土台ができた、部品を足した、検証した、手順書をまとめた)ごとに、頼まれなくてもコミットする。push はユーザーに言われるまでしない。
4. **作業記録**: 作業フォルダに `worklog.md` を置く(書式は `references/worklog_template.md`)。指示ごとに番号・時刻・指示・備考を1行で追記する。時刻は追記時に `date +%s`(epoch)で取り、JST(`TZ=JST-9 date`。`TZ=Asia/Tokyo` は UTC になる)も併記する。時間は epoch の差で測る。記録前の作業は「時刻不明の再構成」と書き、時刻は推測で書かない(「13:07頃」のような概算も書かない。取れなかった行は「時刻不明」とし、直前・直後の epoch だけを備考に残す)。時刻の列がない書式(過去の事例にある)は使わず、`references/worklog_template.md` の書式にする。
5. **OCP CAD Viewer**: 事前に VS Code で OCP CAD Viewer を開いてもらう。表示は `show(..., reset_camera=Camera.KEEP)`。`Camera.RESET` は使わない。形を変えたらその都度送り直す。新しく作った部品は、台も棒も、それぞれ表示する。ビューアーを使い始めるときは、計測用バックエンドも同時に起動する(下の「計測用バックエンドの起動」)。ビューアーが繋がらないときは、`scripts/render_step.py`(matplotlib)などで PNG を作って確認する。部品名は `show(..., names=[...])` で部品ごとに別の名前を付ける。`show` は `from bope_claude_cad.viewer import show`(`ocp_vscode.show` と引数は同じ)を使うと、表示した形を `output/viewer_registry/` に記録し、ホバーの部品名と ID だけで `pick_id --part <部品名> faces <ID>` と引ける(`references/pick_parts.md`)。マウスオーバーで部品名と ID を出したいときは `scripts/ocp_hover_name.py`(下の「ビューアーのホバーに部品名と面・辺の ID を出す」)。ウィンドウごとに別のビューアを開くときは、計測用バックエンドと同じポートで `viewer bind <ポート>` を実行して、表示先を記録する(`references/viewer_tools.md`)。寸法・注記を重ねるときは `references/annotation.md`。
6. **値を推測しない**: 解釈が分かれる指示、決まっていない寸法・向き・本数・材質・製法は、AskUserQuestion で確認する(選択肢と推奨を示す)。決めた解釈は、回答の中で根拠とともにユーザーに分かる形で書く。解釈が分かれる指示は、現状を図(PNG)で見せてから確認する。
7. **変更したら数値で確かめて報告する**: 体積、バウンディングボックス、重なり(干渉)、接触、肉厚、穴の位置、当たり面の被覆、アンダーカットなどを測り(`scripts/jig_toolkit.py` の検証関数)、結果を短く報告する。見落としや誤りに気づいたら、そのときに訂正する。
8. **取り消しやすく作る**: 部品は別々の変数で持ち、結合は別の変数に入れる。結合を取り消すのは**コードだけ**で、ユーザーが作った出力ファイルは勝手に削除しない(消すなら何を消すか先に言う)。
9. **最後に手順書**: 試行錯誤を除いて、同じ入力から同じモデルを再現できる手順書(md)をまとめる(書式は `references/report_template.md`)。出力画像も載せる。未確定の事項を明記し、末尾の備考に、設計にかかった時間とやり取り(指示・質問・コミットの数)を書く。
10. **日本語の文字化け対策(Windows)**: 日本語を含むファイルは Write / Edit で作る。Bash・PowerShell のヒアドキュメント、ヒアストリング、リダイレクト、`sed`、`echo` で日本語を書かない。日本語を含む Python は、Write でスクラッチパッドに `.py`(UTF-8)を作って `uv run python <ファイル>` で実行する。コミットメッセージは Write で一時ファイルに UTF-8 で書き、`git commit -F` で渡し、コミット後に `git log -1` で確認する。
10b. **バイトコードをコミットしない(別リポジトリで使うとき)**: このスキルは別のリポジトリの作業場所から呼ばれる。そこでスクリプトを動かすと `__pycache__/` や `*.pyc` ができ、`git add -A` で誤ってコミットされた事故がある。次を守る。
    - Python は必ず `PYTHONDONTWRITEBYTECODE=1`(または `python -B`)を付けて実行する(例: `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 uv run python ...`)。スキルの `scripts/` を import するスクリプトも同じ。
    - 作業を始めるとき、その作業場所のリポジトリの `.gitignore` に `__pycache__/` と `*.pyc` があるか確かめ、なければ追記する(追記してよいかはユーザーに一言断る)。
    - コミットの前に `git status` で `.pyc`・`__pycache__` が入っていないか確かめる。`git add -A` や `git add .` は使わず、ファイルを指定して追加する。すでに追跡されていたら `git rm --cached` で外す。
11. **市販部品(MISUMI)**: ノックピンなどは build123d で自作して型番だけ記録し(ネジは下の 15 のとおり簡略化する)、作りにくい部品は STEP を入手し、カタログにない形状は Cナビ/meviy、MISUMI で作れないものは図面でローカルベンダーへ。加工品(穴つきプレートなど)は meviy を優先し、アップロードはそのつど了解を得る。手順・ログインの扱い・部品名の付け方は `references/misumi.md`。
12. **出力する文**: NFKC 正規化に合う文字を使う(英数記号は半角、日本語は全角)。
13. **六角穴付きボルトの通し穴・ザグリ(座ぐり)の寸法**: 推測せず、NBK の表(`references/bolt_holes_nbk.md`)を見る。ザグリ深さは H2(M3 は 3.3)。`references/recipes.md` の「頭高さ + 約 0.4」の目安より、この表を優先する。
14. **面・辺を指し示す**: 「この面を直して」と言われたがどこか分からないとき、ユーザーがビューアーの ID(`faces_12`)を伝えたときは、`references/pick_parts.md` に従って面・辺を特定してから直す。
15. **ネジはモデルを簡略化する**(`scripts/screws.py`): ねじ山(めねじ・おねじ)は作らず、**呼び径の孔で代用する**(M6 のねじ穴は φ6、M8 は φ8、M5 は φ5)。
    - **めねじ孔(止まり)**は、ネジであることが分かるように、ねじの深さの先に、**タップ下穴の径をピッチ × 3 だけ深く**掘り、**先端を円錐**(ドリル先端 118°)にする(M6: φ6 を深さ 12、その先に φ5 を 3、先端の円錐)。モデルが重くなるときは、この下穴と円錐を省いてよい(`simple=True`)。通しのめねじ孔には、下穴の延長は付けない。
    - **ネジそのもの**(止めネジ、ボルトなど)を入れる必要があるときは、**呼び径の棒で代用**し、挿入する長さは指示に従う(孔の深さには、必要なら 1 mm 程度の余裕を持たせる)。棒は孔と同じ径で、別部品として出す(`rod_at`)。
    - 通し穴とザグリは対象外で、これまでどおり NBK の表(13)の寸法にする。呼び径は並目(M3〜M12)。それ以外はエラーにして、ユーザーに確認する。
    - 「M6 → φ6 の孔 + 下穴 φ5」のような簡略化の内容は、部品表や手順書に残す。
16. **STEP/STL の git 管理と配布**: 正は build123d のスクリプトで、STEP/STL は派生物。生成のたびにコミットしない(`output/` は git 管理外)。環境を作れない人へ最終稿を渡すときは、既定で **GitLab Release に成果物(STEP の ZIP と `manifest.json`)を添付**する(モード A)。ユーザーが希望したときだけ、タグごとに `release/<タグ>/` へコミットする(モード B)。タグの作成と push、Release の作成、`release/` へのコミットと push は、必ず実行前にユーザーの確認を取る。トークンは出さない・書かない。既存のタグ・Release・`release/<タグ>/` は上書き・削除しない。生成や検証に失敗したら Release へ進まない。手順・コマンド・事前確認は `references/release.md`。

## 進め方

案件に合わせて順序を入れ替えてよい。各段階で、ビューアーに送り、数値で確かめ、ユーザーの指示を待つ。

1. **開始**: 何を作るか、何を入力に持っているか(STEP、図面、スケッチ、寸法の言葉)、作業場所、製法、出力を確認する。`worklog.md` を作り、開始 epoch を記録する。
2. **要件の整理**: 機能(何を受ける・押さえる・位置決めする・成形するか)、相手の部品(ワーク・母治具・機械)との取り合い、材質、数量、製法(3D プリント / 切削 / 板金 / 市販品の組立)を聞く。分からない値は仮置きせず、未確定として記録する。**前工程・後工程・相手の機械が決める値**(余長、取り代、はめ合い、プレス能力、ダイハイトなど)は、「それはどの工程の設計で決まるか」を最初に聞く(曲げ型の余長が玉通し型で決まる前提を後から訂正されて作り直しになった例、抜き型の打抜き力を後から聞かれた例がある)。ユーザーの指示のうち、どの部品・どの寸法を指すかが 2 通りに読めるもの(「奥の段差」「下部の厚み」など)は、実行の前に、読みを 1 行で復唱し、図(PNG)で対象を示して確認する。
3. **入力の把握**: STEP があれば、ソリッド・面・エッジの一覧、範囲、体積を出し(`scripts/probe_step.py`)、名前を付けて(`scripts/render_names.py`、番号は `references/pick_parts.md`)ユーザーと同じ箇所を指していることを確かめる。図面があれば、寸法を読み取って表にし、読み違いが無いか確認する。入力が無ければ、基準となる寸法から作る。
4. **座標系**: 軸の向き、原点、基準面を決める(`scripts/orient_step.py`)。ユーザーが指す点(円の中心、穴の軸、基準面など)を原点にする。数値を出すときは、どの座標系かを明記する。
5. **土台と主要形状**: 最も大きい形から作り、小さい形(穴・溝・面取り・R)を後から足す。1つ決めるごとに表示と数値確認を挟む。作り方は `references/recipes.md`。
6. **取り合いと検証**: 部品同士・相手の部品との干渉と接触を表にする(干渉 0、接触は意図したものだけ)。工具や手の入り方、組立の順序、取り外し(アンダーカットの有無)、公差の指示方法も考える。
7. **出力**: 製法に合わせて STEP / STL / DXF / PNG を出す。組立のときは名前・色つきのアセンブリ STEP とし、同形の部品は名前が1つに集約されるので部品ごとに形を複製する。図面化は `step-to-draft` と `dxf-drafting-support` スキルを使う。最終稿を配布するときは、共通仕様 16(`references/release.md`)に従う。
8. **手順書**: `design_procedure.md` をまとめて、作業フォルダにコミットする。

## 共通の道具と資料

`scripts/` のスクリプトは、別のリポジトリでは `uv run --frozen --project .claude/skills/claude_cad_general python <path>/scripts/<name>.py ...` で動かす(下の「実行環境」。`python` を明示すると、冒頭のインライン指定ではなく共有の環境を使う)。`bope_claude_cad` の中では `uv run python ...`。

| 用途 | 場所 |
|------|------|
| 計測用バックエンドの起動(動いていれば何もしない) | `scripts/start_ocp_backend.py` |
| ビューアーのホバーに部品名を出す(拡張へのパッチ。当てる・戻す・状態) | `scripts/ocp_hover_name.py`(`apply` / `revert` / `status`) |
| ビューアーの数字キーの視点(7 = top view: X が左・+Y が上。当てる・戻す・状態) | `scripts/ocp_view_keys.py`(`apply` / `revert` / `status`) |
| ビューアーのマウスの割り当て(回転・パン・ズーム。Geomagic・RoboDK・Creo・SolidWorks の方式、ホイールの向き、ズームの中心) | `scripts/ocp_mouse.py`(`set` / `apply` / `revert` / `status` / `presets`) |
| STEP の面・エッジの一覧(円筒・円錐のパラメータ、エッジと平面の交点) | `scripts/probe_step.py` |
| 名称付けした面・エッジ・軸・点を重ねた PNG(iso/front/side/top) | `scripts/render_names.py` |
| 回転と原点を決めた STEP と `orientation.json` | `scripts/orient_step.py` |
| 形を調べる・作る・文字・検証・表示と出力の関数集(作業フォルダにコピーするか `sys.path` に追加して `import jig_toolkit as jt`) | `scripts/jig_toolkit.py` |
| アセンブリ STEP を部品色の PNG に(iso / 前 / 側 / 上。範囲指定可) | `scripts/render_step.py` |
| 面・辺に番号を振って表示、ID から面・辺を引く(部品名と ID だけで引く記録つきの `show` も) | `scripts/numbered_view.py`、`scripts/pick_id.py`、`scripts/viewer.py`(手順は `references/pick_parts.md`) |
| 注記(寸法・孔の注記・表面粗さ記号)をビューアに重ねる。平らな面・輪郭 OFF・Segoe UI Symbol・JIS B 0031:2003 | `scripts/annotation.py`(`dim_linear`、`hole_note`、`roughness_note`、`show_with_annotations`。方針・使い方・未実装は `references/annotation.md`) |
| 履歴と取り消し(`show` のたびにスクリプトの写しを残す。`.history/` は git 管理外)、断面・軸断面、常駐プログラムでの高速な再表示、複数ビューアの表示先(`bind`) | `scripts/history.py`、`scripts/viewer.py`、`scripts/runner.py`(`references/viewer_tools.md`) |
| ネジの簡略化(呼び径の孔 + 下穴の延長と円錐、ネジの代わりの棒) | `scripts/screws.py`(`tapped_hole`、`hole_at`、`rod_at`。決まりは共通仕様 15。使い方は `references/recipes.md` の「ボルト」) |
| 成果物の manifest.json(コミット SHA・バージョン・SHA256) | `scripts/make_manifest.py` |
| 成果物(STEP/STL)の配布と git 管理(Release 添付、release/ へのコミット) | `references/release.md`(共通仕様 16) |
| build123d の作り方 | `references/recipes.md` |
| 市販部品(MISUMI)の探し方・型番・STEP・BOM | `references/misumi.md` |
| ボルト穴・ザグリの寸法(NBK) | `references/bolt_holes_nbk.md` |
| 作業記録・手順書の雛形 | `references/worklog_template.md`、`references/report_template.md` |
| 別のリポジトリで使う共有の実行環境(依存と版の固定) | `pyproject.toml`、`uv.lock`(下の「実行環境」) |
| OCP CAD Viewer の拡張(ビューアとバックエンド)だけが共有の `.venv` の Python を使うようにする(拡張へのパッチ。ワークスペースのインタプリタは変えない) | `scripts/ocp_python.py`(`apply` / `revert` / `status`。下の「OCP CAD Viewer が使う Python を指定する」) |

## 実行環境(別のリポジトリで使うとき)

build123d・ocp_vscode などは、このスキルのフォルダ(`.claude/skills/claude_cad_general/`)の `.venv` に 1 つだけ入れ、どのリポジトリからも共有する。版は `uv.lock` で固定する(作業の途中で build123d の新しい版が入って形や API が変わるのを防ぐ)。相手のリポジトリには `pyproject.toml`・`uv.lock`・`.venv` を作らない(図面リポジトリを汚さない、OCP 一式をリポジトリごとに入れない)。

- **実行**: 作業場所(`wd`)で、`PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 uv run --frozen --project .claude/skills/claude_cad_general python <スクリプト>`。`--project` は環境を選ぶだけで、カレントディレクトリは変わらないので、相対パスはそのまま使える。`--frozen` は `uv.lock` を書き換えずに使う(インストール先の `uv.lock` が原本とずれないように)。
- **初回・更新後**: `.venv` が無い、または `uv.lock` が新しくなったときは、上の実行で自動的に入る(初回は数分かかる)。先に入れておくなら `uv sync --frozen --project .claude/skills/claude_cad_general`。
- **`--with` は使わない**: 版が固定されず、毎回の解決も入る。共有の環境に無いライブラリが要るときは、その場で `--with` を足さず、ユーザーに断ってから原本の `pyproject.toml` に足す(下の「依存を足す」)。
- **OCP CAD Viewer が使う Python(必須)**: 拡張は、ビューアを開くときに Python に `ocp_vscode` があるかを調べ(無ければ「OCP VS Code not found for ... Select another Python interpreter?」と聞き、no なら開かない)、計測用バックエンドもその Python で `-m ocp_vscode --backend` として起動する。元の拡張はワークスペースのインタプリタを使うが、作業リポジトリには測定などのための固有の `.venv` があることがあるので、ワークスペースのインタプリタや `.vscode/settings.json` は**変えない**。代わりに、拡張にパッチ(`scripts/ocp_python.py`)を当て、**OCP CAD Viewer だけ**が共有の `.venv` の Python を使うようにする(下の「OCP CAD Viewer が使う Python を指定する」)。一度当てれば、どのリポジトリでも効く。
- **OCP CAD Viewer の版**: Python 側の `ocp-vscode` は、VS Code の拡張と同じ系列に固定している(拡張 4.2.0 に対して `>=4.2.0,<4.3`)。版がずれると、拡張が「ocp_vscode library version ... is older than extension version ...」と出し、表示や計測が合わなくなるおそれがある。拡張の「Install」ボタン(Library Manager)で入れ直すと pip で `.venv` を書き換えてしまい `uv.lock` とずれるので、押さずに次の「拡張を更新したら」の手順で上げる。

### VS Code の OCP CAD Viewer 拡張を更新したら

拡張は自動で更新されることがあるので、ビューアの様子がおかしいときや、上の警告が出たときは、まずこれを確かめる。

1. 拡張の版を見る: `ls ~/.vscode/extensions | grep ocp-cad-viewer`(例: `bernhard-42.ocp-cad-viewer-4.3.0`)。
2. 原本 `bope_claude_cad/skills/claude_cad_general/pyproject.toml` の `ocp-vscode` の範囲を、拡張と同じ系列にする(例: 4.3.0 なら `>=4.3.0,<4.4`)。コメントの拡張の版、この SKILL.md の「4.2.0」の記述も直す。
3. `uv lock --project skills/claude_cad_general` で `uv.lock` を更新し、`pyproject.toml`・`uv.lock`・`SKILL.md` を `.claude/skills/claude_cad_general/` へ写して、`uv sync --frozen --project .claude/skills/claude_cad_general` を実行する。
4. `bope_claude_cad` 本体の `pyproject.toml` の `ocp-vscode` も同じ系列にそろえ、`uv lock`・`uv sync` する(本体の `.venv` も同じ拡張につなぐため)。
5. 拡張へのパッチを当て直す: `ocp_python.py apply`、`ocp_hover_name.py apply`、`ocp_mouse.py apply`、`ocp_view_keys.py apply`(更新でパッチが消えるため。下の各節)。
6. `uv run pytest tests/test_skill_consistency.py` で、拡張と `uv.lock` の版、原本とインストール先がそろったことを確かめ、コミットする。
- **依存を足す・版を上げる**: 原本(`bope_claude_cad` の `skills/claude_cad_general/pyproject.toml`)を直し、`uv lock --project skills/claude_cad_general` で `uv.lock` を更新して、`pyproject.toml` と `uv.lock` を `.claude/skills/claude_cad_general/` へ写し、`uv sync --frozen --project .claude/skills/claude_cad_general` を実行する。ずれは `tests/test_skill_consistency.py` が検出する。
- 個別スキル(`claude_cad_vss` など)のスクリプトも、この環境で動かす。

## 計測用バックエンドの起動

OCP CAD Viewer を使い始めるときは、計測用バックエンド(距離ツール・Properties ツール用)も同時に起動する。測るかどうかは問わず、ユーザーに頼まれなくても、最初の `show` の前に済ませる。

1. ユーザーに VS Code で OCP CAD Viewer を開いてもらう(既定のポートは 3939。`~/.ocpvscode` で確認できる)。その前に `scripts/ocp_python.py status` で、拡張が共有の `.venv` の Python を使うパッチが当たっているか確かめる(下の「OCP CAD Viewer が使う Python を指定する」)。
2. Bash の `run_in_background` で `PYTHONIOENCODING=utf-8 uv run python <このスキル>/scripts/start_ocp_backend.py`(別のリポジトリでは `uv run --frozen --project .claude/skills/claude_cad_general python ...`。「実行環境」)を動かしたままにする(ポートを変えるときは `--port`。動いていれば何もしないので、毎回実行してよい。動作確認だけなら `--check`)。素の起動は `PYTHONIOENCODING=utf-8 uv run python -m ocp_vscode --backend --port 3939`(`--port` は必須。「Viewer backend started」と出ればよい)。
3. そのあとで `show(..., reset_camera=Camera.KEEP)` でモデルを送る。順番が逆だと計測で `KeyError` を出して止まる。`show` で「backend is not connected」と警告が出たら、バックエンドが動いていないので手順2をやり直す。
4. ビューアーを再起動するとバックエンドも止まる。手順2からやり直す。

## ビューアーのホバーに部品名と面・辺の ID を出す

OCP CAD Viewer(VS Code 拡張 4.2.0 で確認)の下のステータス行は、マウスを重ねた面・辺・ソリッドの
種類と寸法(`plane: area ≈ …`、`solid: N faces, … vol ≈ …`)だけで、部品名も ID も出さない。
`scripts/ocp_hover_name.py` が、拡張の `three-cad-viewer.esm.js` の `hoverStatusText()` を包み、
行の頭に `[部品名 faces_6]`(`show()` の `names` の名前と、面・辺・頂点の ID)を付ける。ソリッドを重ねたときは
`[部品名]` だけ。ID は `shape.faces()` / `shape.edges()` の 0 始まりの添字で、「copy shape id」をしなくても、
そのまま `pick_id` に渡せる(`references/pick_parts.md`)。標準ライブラリだけで動く。
旧版(部品名だけ)のパッチが当たっていれば、`apply` が自動で新版に当て直す。

```
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_hover_name.py status   # 状態
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_hover_name.py apply    # 当てる(何度でも)
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_hover_name.py revert   # 戻す
```

- 当てたら、VS Code のウィンドウを再読み込みしてもらう(Developer: Reload Window)。
- 元のファイルは同じ場所の `.esm.js.orig` に保存する。拡張を更新すると改造は消えるので、`apply` をやり直す。
- 拡張のバージョンが変わって `hoverStatusText` が見つからないときは、何も書き換えずに終了コード 2 で終わる。
  そのときはスクリプトを直さず、ユーザーに伝える。
- VS Code の外のファイルを書き換えるので、初めて当てる前にユーザーに一言断る。
- 部品名がそのまま出る前提なので、`names` は部品ごとに別の名前にする(重複すると `Solid(0)` のような連番になる)。

## OCP CAD Viewer が使う Python を指定する

OCP CAD Viewer の拡張(4.2.0 で確認)は、Python 拡張で選ばれたワークスペースのインタプリタを、`out/utils.js` の
`getPythonPath` で取り出して使う(ビューアを開くときの `ocp_vscode` の確認、計測用バックエンドの起動、
Library Manager)。拡張の設定には、Python を指定する項目が無い。`scripts/ocp_python.py` が `getPythonPath` の頭に
OCP CAD Viewer 専用の指定を足し、ワークスペースのインタプリタ(Pylance、ターミナル、測定などの他のツール)は
そのままにして、拡張だけが共有の `.venv` の Python を使うようにする。`out/extension.js` の、ワークスペースの
インタプリタが変わったときの処理(そのままだとビューアを閉じて、ワークスペースの Python に切り替える)も、同じ指定を見るように直す。

- 指定は VS Code の設定 `OcpCadViewer.advanced.pythonPath`(`${userHome}` が使える)。**設定が無ければ**、
  `${userHome}/.claude/skills/claude_cad_general/.venv/Scripts/python.exe`(このスキルの共有の実行環境)を使う。
  通常は設定を書かなくてよい。
- 空文字列 `""` を設定したワークスペースでは、パッチは何もしない(元どおりワークスペースのインタプリタ)。
  指定した Python が無いときも、元どおりワークスペースのインタプリタに戻る。
- 設定に `OcpCadViewer.advanced.pythonPath` を書くと、拡張が宣言していない項目なので、設定画面に「不明な設定」と
  出ることがあるが、動作には関係ない。

```
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_python.py status   # 状態と既定の Python
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_python.py apply    # 当てる(何度でも)
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_python.py revert   # 戻す
```

- VS Code の外のファイルを書き換えるので、初めて当てる前にユーザーに一言断る。当てたら、VS Code の
  ウィンドウを再読み込みしてもらう(Developer: Reload Window)。
- 確かめ方: 「OCP CAD Viewer Log」の出力に `utils.PythonPath: '...claude_cad_general\.venv\Scripts\python.exe' (OcpCadViewer.advanced.pythonPath)` と出る。
  バックエンドのターミナル(OCP backend)のコマンドも、この Python になる。
- 拡張を更新すると改造は消えるので、`apply` をやり直す(「VS Code の OCP CAD Viewer 拡張を更新したら」)。
  `three-cad-viewer.esm.js` を書き換える `ocp_hover_name.py`・`ocp_mouse.py` とは、書き換えるファイルが別なので干渉しない。
- 書き換える箇所(`static async getPythonPath(document, notify = false) {`、`getExecutionDetails().execCommand[0]`)が
  見つからないときは、何も書き換えずに終了コード 2 で終わる。そのときはスクリプトを直さず、ユーザーに伝える。

## ビューアーのマウスの割り当てを変える

OCP CAD Viewer は、左ドラッグで回転、右ドラッグでパン、中ドラッグとホイールでズームする。拡張の設定では
修飾キーの読み替えしかできないので、`scripts/ocp_mouse.py` が拡張の `three-cad-viewer.esm.js` の `Controls` に
「ボタン+修飾キー → 操作」の表を差し込む(trackball / orbit の両方)。元の処理には手を入れず、押されたボタンを
元の処理が同じ操作をするボタンに読み替えて渡すだけなので、左クリックの選択と右クリックの選択取り消しは元のまま動く。

| 方式(`--preset`) | 回転 | パン | ズーム | 左ボタン |
|---|---|---|---|---|
| `geomagic`(既定) | 右ドラッグ(Alt+右=横だけ、Shift+Alt+右=縦だけ) | Ctrl+右、中ドラッグ | Shift+右 | 選択だけ |
| `robodk` | 右ドラッグ | 中ドラッグ | — | 選択だけ |
| `creo` | 中ドラッグ | Shift+中 | Ctrl+中 | 選択だけ |
| `solidworks` | 中ドラッグ | Ctrl+中 | Shift+中 | 選択だけ |
| `ocp`(拡張の元) | 左ドラッグ(Ctrl+左=縦だけ、Alt+左=横だけ。右+修飾キーも回転) | 右、Shift+左 | 中ドラッグ | 回転と選択 |

ホイールはどの方式でもズーム。向きは `--wheel normal|reverse`(normal が拡張の元の向き)、中心は
`--zoom-center target|cursor`(target が元の動きで回転中心へ、cursor はマウスの下の点を止めたまま)。
一部だけ変えるときは `--bind ボタン[+ctrl][+shift][+alt]=操作`(操作は rotate / rotate_h / rotate_v / pan / zoom / none。
修飾キーは完全一致)。設定は `~/.ocp_mouse.json` に保存され、`apply` はその設定で当てる。

```
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_mouse.py status                 # 状態と割り当て表
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_mouse.py set --preset geomagic   # 保存して当てる
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_mouse.py set --wheel reverse --zoom-center cursor
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_mouse.py apply                  # 拡張の更新後に当て直す
uv run --no-project python -I .claude/skills/claude_cad_general/scripts/ocp_mouse.py revert                 # このパッチだけ外す
```

- 当てたら、VS Code のウィンドウを再読み込みしてもらう(Developer: Reload Window)。
- 拡張を更新すると改造は消えるので、`ocp_hover_name.py apply` と `ocp_mouse.py apply` をやり直す(順はどちらでもよい)。
- `revert` は自分の差し込みだけを外す。`ocp_hover_name.py revert` は `.orig` に戻すので、マウスの割り当ても消える。そのあとは `ocp_mouse.py apply` をやり直す。
- 差し込み先(`class Controls {`、`new CADTrackballControls(...)`、`new CADOrbitControls(...)`)が見つからないときは、何も書き換えずに終了コード 2 で終わる。そのときはスクリプトを直さず、ユーザーに伝える。
- 左右同時押しのパン(Design X)は無い。

## 注意

- 共通基盤なので、特定の治具の決まり(スポット治具の基本設計基準 Z=50、刻印の規則、電極台・電極棒の流用の確認、検査治具の受け方針、曲げ型のスプリングバックなど)は持ち込まない。それらは各個別スキルの決まり。該当する案件なら個別スキルを使う。
- 過去の治具から流用できる形がないか、`<リポジトリのルート>/draw/` と `jigs/` の既存の部品とスクリプトを先に引く。近いものがあれば、流用か、寸法の寄せを提案する。
- 製品やワークのモデルそのものに気になる点(食い込み、隙間、寸法の矛盾)があれば、直さずに「未確認」として報告する。元の STEP は変えず、直すときは別名(`_fixed.stp`)で保存する。
- 専用スキルに育てる価値があると分かった案件は、手順書を `references/` に事例として残し、専用スキルへの切り出しをユーザーに提案する。
