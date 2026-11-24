# 作業記録 (model202611)

2026-11 に設計中のホルン(model202611)の、モデル全体の整理の記録。部品ごとの記録は各フォルダの worklog.md。時刻は JST。

## 指示ログ

| # | 時刻 | 指示 | 備考 |
|---|------|------|------|
| 1 | 2026-11-25 00:15:27 (epoch 1795533327) | 「ファイルの整理をします。今設計中のモデルをmodel202611とします。bb_length, bb_return, bb34, branch2, main_aux_tube, main_slide, mouthpipe はこのモデルの固有の形になるので、model202611 の下のサブフォルダとして配置します。管体組立のレベルと植込組立のレベルを分けて…」「深すぎると却って管理しにくくなるようなら無理に階層は作らないで良い」 | `git mv` で: `bb_length/`(全長の集計)、`valve_assy/bb34`・`valve_assy/bb_return`(植込組立)、`body_assy/branch2`・`main_aux_tube`・`main_slide`・`mouthpipe`(管体組立)。共通の部品(cad/valves・bell03・bellscrew・bows・tubes)は動かさない。`model_paths.py`(新規): ルート(このファイルから 2 つ上)・各部品のフォルダ(`PARTS`)・共通の部品の import パスを 1 か所で決める。16 本のスクリプトの冒頭(`HERE.parents[2]`・`parents[3]`・絶対パスの sys.path)をこれに置き換え、docstring・コメントのパスも新しい場所に。モジュール名の重なりなし。確認: 18 モジュールが新しい場所から import できる、ruff の件数は移動前と同じ 63(どれも前からのもの)。過去の worklog のパスは当時のまま。CLAUDE.md・メモリのパスを更新。バックグラウンドの session が本体を直接編集できるよう `.claude/settings.json` に `worktree.bgIsolation: none` |
