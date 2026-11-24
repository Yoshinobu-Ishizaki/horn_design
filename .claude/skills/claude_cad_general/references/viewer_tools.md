# ビューアの道具(履歴・常駐プログラム・断面・複数のビューア)

llm_usage の `press-die-design-assist/cad/`(山田さんの OCP Viewer 改良)を参考に、bope_claude_cad 向けに取り込んだもの。
`scripts/viewer.py`・`history.py`・`runner.py`(原本は `src/bope_claude_cad/`)。選択機能(クリックで面を選ぶ)は取り込まない(2026-11-13 決定。
距離・property ツールと干渉し、公式バックエンドの置き換えが要るため。面はホバーの ID で指す: `references/pick_parts.md`)。
注記(寸法・粗さ)は `references/annotation.md`。

別のリポジトリで使うときは、スキルの `scripts/` を `sys.path` に足して `import viewer` などとする、またはファイルを直接実行する
(`uv run python <スキル>/scripts/history.py list --last`)。パッケージ内なら `python -m bope_claude_cad.history ...`。

## ビューアと表示先(viewer.py)

ウィンドウ(リポジトリ)ごとに別の OCP Viewer を開く運用で、表示先が混ざらないようにする。

- `bind_viewer(port)` / `python -m bope_claude_cad.viewer bind <ポート>`: このリポジトリが使うビューアのポートを `output/viewer_registry/viewer.json` に記録する。**バックエンドを起動するときに、同じポートで実行する**(`CLAUDE.md` の手順)。
- `resolve_viewer_port()`: 環境変数 `OCP_VIEWER_PORT` > 記録したポート(生きていれば)> 開いているビューアが 1 つだけならそれ(記録もする)。
  複数あって未記録なら、ocp_vscode の対話の問い合わせ(端末で止まる)にせず、`bind` を促す例外にする。`viewer status` で確認できる。
- `show`・`set_config`(`set_viewer_config` の代わり)・断面は、この表示先に出す。

## 視点・表示の切り替え・断面をコマンドで(viewer.py)

スクリプトを書かずに、1 行で呼べる。`uv run python -m bope_claude_cad.viewer <コマンド>`(スキルの単体ファイルなら `uv run python <スキル>/scripts/viewer.py <コマンド>`)。

| コマンド | 内容 |
|---|---|
| `view top\|bottom\|front\|back\|left\|right\|iso\|fit` / `view +x\|-x\|+y\|-y\|+z\|-z` | 視点(`+x` は +X 側から見る)。**`show` の直後は切り替えが取りこぼされることがある**ので、間を置いて 2 回送る(実装済み)。 |
| `section x\|y\|z <位置> [+\|-]` / `section off` | 軸に垂直な面で切る(`+` は大きい側を残す。既定は小さい側)/ 断面をやめる。 |
| `axis <部品名> [faces\|edges <N>]` | 穴・ボルトの軸を通る面で切り、正面から見る(N はホバーの ID。省略時は一番大きい円筒面)。 |
| `only <部品名>...` / `hide <部品名>...` / `all` | 部品の表示・非表示(`show(names=...)` の名前。組立の入れ子なら組立名でも部品名でもよい)。次に `show` し直すと戻る。`hide` は、すでに隠した部品を表示し直さない。 |
| `transparent on\|off` | 半透明。 |
| `shot <保存先.png>` | 画面を PNG に保存する(見え方を確かめる。視点を変えた直後は少し待つ)。 |
| `bind <ポート>` / `status` | このリポジトリが使うビューアの記録・確認(次の節)。 |

関数としても呼べる: `set_view`・`visibility`・`screenshot`・`section`・`section_off`・`axis_section`(`from bope_claude_cad.viewer import ...`)。

## 断面(viewer.py)

- `section(axis, position, keep_plus)`: 軸に垂直な面で切る(切り口は部品ごとの色)。`section_off()` でやめる。
- `feature_axis(shape, kind, index)`: ホバーの ID(`faces_N` / `edges_N`)から、穴・ボルトの軸を求める。
- `axis_section(part, kind, index)`: 軸を通る面で切り、標準の視点(LEFT / FRONT)で見る。部品は `viewer_registry` から名前で引く。
- **カメラの `position` / `target` だけを指定しない**(回転が合わずに図が全部消えた。2026-11-13 実機で確認)。視点は `Camera.*` を使う。

## 履歴(history.py)

`show` が、呼び出したスクリプト 1 ファイルの写しを、スクリプトの隣の `.history/<名前>/` に残す(同じ内容なら増やさない)。

- `python -m bope_claude_cad.history list|undo|redo|restore <スクリプト> [--run]`。`<スクリプト>` の代わりに `--last`(最後に `show` したスクリプト)。`--run` で、移ったあとに再実行して表示し直す。
- 親を持つ木構造。戻ったあとに直すと枝分かれする(記録は消さない)。移る前の未記録の手直しは先に保存する。
- **git に入れない**: `.history/` に `.gitignore`(中身 `*`)を自動で作る。リポジトリの `.gitignore` にも `.history/` を足してよい。`OCP_HISTORY=0` で記録しない。
- 写しはスクリプト 1 ファイルだけ。`lib/` など別モジュールの変更は残らない。
- **OCP Viewer 上の Ctrl+Z(戻る)/ Ctrl+Y(進む)は、VS Code 拡張が必要**(ビューア自身には履歴の機能が無い)。拡張は `vscode-ext/bope-history/`
  (ボタンは出さない。2026-11-13 決定)。`uv run python vscode-ext/bope-history/make_vsix.py` で `.vsix` を作り、
  `code --install-extension <.vsix のパス(スラッシュ区切り)>` で入れ、VS Code を再読み込みする(Developer: Reload Window)。
  拡張は、ワークスペースに `src/bope_claude_cad/history.py` があるときだけ動き、`history undo|redo --last --run` を呼ぶ。拡張なしでも、「戻して」と頼むか、コマンドで同じことができる。
  アンインストールしても、VS Code を再読み込みするまでは古い拡張が動き続ける。

## 常駐プログラム(runner.py)

build123d などの読み込みを起動時の 1 回で済ませ、スクリプトを常駐プログラムの中で実行する。`history ... --run` が使う(約 4 秒 → 1.5 秒)。

- **ビューア 1 つにつき常駐プログラム 1 つ**。待ち受けは `ビューアのポート + 1000`。起動時にビューアへ固定し、スクリプトにも `OCP_VIEWER_PORT` を渡す。ビューアが閉じたら(2 回続けて確認)終わる。4 時間使わなくても終わる。
- `python -m bope_claude_cad.runner run <スクリプト>` / `start|stop|status [--viewer V]` / `list`。`OCP_RUNNER=0` で使わない。
- 実行のたびにスクリプトを読み直し、実行で新しく読み込まれたリポジトリ内のモジュールは終了後に捨てる(`lib/` の修正が次の実行に反映される)。
- 起動は pythonw(黒い窓なし)。ログは `~/.bope_claude_cad/runner.log`。止めるのは `runner stop`。
