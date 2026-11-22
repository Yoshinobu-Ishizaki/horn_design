# 移植パッケージ: claude_cad_vss / claude_cad_surface_map (+ claude_cad_general)

bope_claude_cad (dev, 2026-11-22 時点) から、楽器そのものの設計に使う2つの機能を、サンプルと一緒に取り出したもの。
フォルダ構成は元のリポジトリと同じなので、移植先のリポジトリのルートにそのまま展開できる。

| 機能 | スキル | 実装 | テスト | サンプル |
|---|---|---|---|---|
| 可変断面スイープ(芯線 + L-D 表 → ベル・テーパー管) | `skills/claude_cad_vss/` | `src/bope_claude_cad/vss.py` | `tests/test_vss.py` | `skills/claude_cad_vss/sample/`(RefBell ベルの .cad、STEP 3 つ)、`scripts/` |
| 曲面への輪郭のマップと座(支柱座など) | `skills/claude_cad_surface_map/` | `src/bope_claude_cad/surface_map.py` | `tests/test_surface_map.py` | `jigs/refbell_seat/`(RefBell 支柱座、入力 DXF、worklog) |
| 共通の決まりと道具 | `skills/claude_cad_general/` | `src/bope_claude_cad/` の `viewer`・`pick_id`・`numbered_view`・`history`・`runner`・`annotation`・`screws` | - | - |

## 中身

```
README_porting.md        このファイル
CLAUDE_snippet.md        元の CLAUDE.md の「開発ルール」「作業の置き場所」(移植先の CLAUDE.md に貼る)
pyproject.example.toml   依存の例(移植先に pyproject.toml が無いとき)
src/bope_claude_cad/     実装(パッケージ名は bope_claude_cad のまま)
tests/                   test_vss.py, test_surface_map.py
skills/                  claude_cad_general, claude_cad_vss, claude_cad_surface_map
jigs/refbell_seat/         surface_map のサンプル(vss のベルの外面に支柱座を貼る)
```

## 移植の手順

1. 移植先のリポジトリのルートに展開する。
2. 依存を入れる。移植先に pyproject.toml があれば:
   ```
   uv add build123d ezdxf ocp-vscode numpy scipy
   uv add --dev pytest ruff
   ```
   無ければ `pyproject.example.toml` を `pyproject.toml` にして `uv sync`。
   `src/bope_claude_cad` をパッケージとして入れるため、`[tool.hatch.build.targets.wheel] packages = ["src/bope_claude_cad"]` が要る(例の中にある)。
3. 動作確認: `uv run pytest tests/test_vss.py tests/test_surface_map.py`(この zip を展開した別フォルダで、全件通ることを確認済み)。
4. スキルを使えるようにする: `skills/` の3つを `~/.claude/skills/` へコピーする(元のリポジトリと同じ運用)。
   - 移植先のリポジトリにも `skills/` を原本として置くなら、直したら両方をそろえる。
5. `CLAUDE_snippet.md` の内容を、移植先の CLAUDE.md に足す(OCP Viewer と計測用バックエンドの起動手順、worklog の決まりなど)。

## サンプルの動かし方

```
# vss: RefBell ベル(.cad は cadra-converter スキルで DXF にする。jigs/*_seat/input/refbell_bell_assy.dxf が変換済み)
uv run python skills/claude_cad_vss/scripts/show_bell.py jigs/*_seat/input/refbell_bell_assy.dxf --wall 0.4
uv run python skills/claude_cad_vss/scripts/export_bell_step.py jigs/*_seat/input/refbell_bell_assy.dxf output/

# surface_map: RefBell 支柱座
uv run python jigs/refbell_seat/build_seat.py --mode wrap --show
```

`--show` などの表示は、OCP CAD Viewer と計測用バックエンドを先に起動しておく(`CLAUDE_snippet.md`)。

## 注意

- パッケージ名・スキル内の記述は `bope_claude_cad` のまま。名前を変えるなら、`src/`・`tests/`・`skills/*/SKILL.md`・`skills/*/scripts/`・`jigs/refbell_seat/` の `bope_claude_cad` をまとめて置き換える。
- `skills/claude_cad_general/scripts/` の `viewer.py` などは `src/bope_claude_cad/` の写し(元のリポジトリでは `tests/test_skill_sync.py` で一致を検査)。この zip には、その検査は入れていない。
- `claude_cad_general` は治具・型の設計用の記述(MISUMI、ボルト穴、リリースなど)も含む。楽器の設計で使わない部分はそのまま置いてよい。
- 元のリポジトリでは `skills/claude_cad_vss/sample/step/*.step` は再生成できるので git 管理外。移植先でも `.gitignore` に入れるかを決める。
- `render_bell_blender.py` は Blender の中で動かすスクリプト(`bpy` が要る)。
- 社内図面(RefBell の .cad・DXF)を含む。部門の外へは渡さない。
