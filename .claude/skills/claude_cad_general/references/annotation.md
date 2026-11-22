# 注記(寸法・孔の注記・表面粗さ記号)を OCP Viewer に重ねる

`scripts/annotation.py`(原本は `src/bope_claude_cad/annotation.py`)。ビューアに、図面のような寸法・孔の注記・表面粗さ記号を重ねて見せる。
画像化(`render_*` や図面化)の前に、位置や値をユーザーと確かめるために使う。

## 使い方

```python
from bope_claude_cad.annotation import dim_linear, hole_note, roughness_note, show_with_annotations

dim = dim_linear(plate.vertices()[0], base.vertices()[1], view="front", direction="vertical", offset=12)
note = hole_note(plate.edges()[10], "M4↧10", view="top", angle=135)      # M4↧10
ra = roughness_note(plate.vertices()[0], "Ra 1.6", view="front")
show_with_annotations([plate, base], {"DIM-24": dim, "NOTE-M4": note, "RA-1": ra}, names=["plate", "base"])
```

別のリポジトリで使うときは、スキルの `scripts/` を `sys.path` に足してから `import annotation`(`bope_claude_cad` の名前空間は無い)。
build123d と `ocp_vscode` が、その作業場所の環境に入っていること。

| 関数 | 内容 |
|---|---|
| `dim_linear(pa, pb, view, direction, offset, side, label)` | 2 点(Vector か頂点)の間の寸法。`direction` は `vertical`(画面の上下)か `horizontal`。補助線は各点から外へ引き出し、寸法線・矢印・数値を付ける。数値は測った長さ(単位なし)。`side` で寸法線の側(`vertical` は `low` = 左 / `high` = 右、`horizontal` は `high` = 上 / `low` = 下)。 |
| `hole_note(edge, label, view, angle)` | 孔の縁(円の辺)から矢印付きの引出線を引き、水平の折れ線の上に文字を置く。`angle` は引出線を出す向き(度)。矢印は孔の中心を指す。 |
| `roughness_note(point, label, kind, view)` | 面の上の点に粗さ記号の頂点を当てて置く。`kind` は `required`(▽ = 除去加工あり)か `any`(V = 要否を問わない)。 |
| `roughness_symbol(label, kind, h)` | 記号そのもの(スケッチ座標)。`roughness_note` が置く。 |
| `show_with_annotations(objs, annotations, names, outline)` | 部品と注記を表示する。注記は既定で輪郭 OFF・黒。`outline=True` で輪郭を出す。 |

頂点・辺は、ビューアのホバーの `[部品名 vertices_N]`・`edges_N` の N を使い、`shape.vertices()[N]`・`shape.edges()[N]` で取る(`references/pick_parts.md`)。

## 見る向き(view)

`front`(−Y 側から見る。右 = +X、上 = +Z)・`back`・`left`・`right`・`top`(+Z 側から。右 = +X、上 = +Y)・`bottom`。
注記は、その向きの平面(対象の手前 0.5 mm)に置く平らな面。**その向きから見る**(違う向きから見ると、細い線にしか見えない)。
注記を出したあと、`set_viewer_config(reset_camera=Camera.FRONT)` などで向きを合わせる。**切り替えが取りこぼされて視点が変わらないことがある**ので、少し待って 2 回送る。

## 方針(人の決定。2026-11-13)

- **輪郭表示は OFF(`Render.FACES`)が既定**。ビューアは面の縁に灰色の輪郭線を引くので、細い文字が中空(袋文字)に見える。`show_with_annotations` が既定にしているので、注記を `show` に直接渡すときも `modes` に `Render.FACES`、`colors` に `"black"` を付ける。
- **フォントは Segoe UI Symbol に統一**。深さ ↧(U+21A7)・ざぐり ⌴(U+2334)・皿穴 ⌵(U+2335)・直径 ⌀(U+2300)を 1 つのフォントで出せる。
  **カタカナは出ない**ので、注記は記号だけで書く(`M4↧10`、`⌴⌀11↧6.5`)。MS Gothic は ↧ はあるが ⌴ ⌵ が無い。Arial は ↧ が無い。
  Windows 標準のフォントなので、別の PC・OS では字形が出ないことがある。配るときは画像化した結果にする。
- **ソリッドではなく平らな面**で作る(build123d の `Sketch` / `Text` / `Rectangle` / `DimensionLine` / `ArrowHead`)。ソリッドにすると部品と同じ色に潰れて読みにくい。
- **補助線は対象の頂点・縁から外へ引き出す**。面間の寸法でも、面ではなく頂点から(2 点の外側の位置が違えば、補助線の起点も違う)。矢印は build123d の既定(塗りつぶし)でよい。
- **粗さ記号は JIS B 0031:2003 の新しい書き方**: ▽(除去加工あり)+ 右上の長い斜線 + 水平線。**Ra の値は水平線の下・斜線の右**(旧 JIS の「上」ではない)。▽ の 1 辺は 3 mm が既定(文字高さ h ≒ 1.742 mm)。

## 粗さ記号の寸法の出典

文字高さ h に対する比で、`dxf-drafting-support` スキルの `scripts/rules.toml [roughness]` と同じ値(▽ の底辺の半幅 0.861h、高さ 1.491h、頂点から水平線まで 2.994h、水平線の左端まで 1.727h、値の左端は水平線の左端から 0.773h、基準線は水平線の 1.249h 下)。
**規格本文(JIS B 0031)の寸法表との照合は未了**(ユーザーが行う)。参照した解説ページ(吉田SKT)と JSA のプレビューには、記号の寸法も記入位置も載っていなかった。
`dxf-drafting-support` 側の値を直したら、`annotation.py` も揃える(出典が 2 か所にあるため)。

## 未実装・注意

- 粗さ記号: 除去加工禁止(円付き)、加工方法(c)・筋目(d)・削り代(e)・全周記号。面の向きが違うときの引出線(矢印)付きの置き方。
- 寸法: 画面の上下・左右の 2 方向だけ(斜めの寸法、直径・半径・角度は未対応)。同じ側に複数の寸法を出すときの段の自動送りは無い(`offset` を変えて並べる)。
- 注記同士・部品との重なりを避ける処理は無い(置く位置を `offset` や `angle` で調整する)。
- 注記の文字は、画面の拡大・縮小に関わらず mm で決まる(小さくて読みにくいときは、ビューアで拡大する)。
