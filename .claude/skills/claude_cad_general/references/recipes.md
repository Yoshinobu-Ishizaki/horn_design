# build123d のレシピ

bb106_mpbrc の設計で作って、数値を確かめたもの。完成例は `../../claude_cad_shape_check/references/example_bb106_show_jig.py`、関数は `../scripts/jig_toolkit.py`。
座標は検査治具の座標系(上=Z+)。`BASE_Z` はベース面の高さ。

```python
import sys
sys.path.insert(0, "<skill>/scripts")   # または jig_toolkit.py を作業フォルダにコピー
import jig_toolkit as jt
```

## ベースのブロック

```python
base = Plane.XY.offset(BASE_Z) * Pos((RIGHT_X + LEFT_X) / 2, 0, 0) * Rectangle(RIGHT_X - LEFT_X, 2 * TOP_Y)
block = extrude(base, amount=BLOCK_H)                                  # +Z へ押し出す
block = chamfer(block.edges().filter_by(Axis.Z), 2.0)                  # 上から見た4角(縦の4辺)
BASE_TOP = BASE_Z + BLOCK_H
```

- 四角は「上から見て X 軸に対して対称」なら Y を ±TOP_Y にする。右辺・左辺は X で指定。

## 円筒面の受け(PIN): 同軸の凸円柱

```python
p = jt.cylinder_params(face)              # radius, axis, point(元の座標)。回転後の STEP の face で呼ぶ
t0 = jt.embed_start_s(a0, direction, R, BASE_TOP, 2.0)   # 下端: いちばん浅い点が 2mm 埋まる
t1 = <面の端の軸方向位置>                      # 上端は面の端
pin = jt.axial_cyl(a0, direction, t0, t1, 2 * R)
pin = chamfer(<下端の円周の縁>, 0.5)           # 埋まる側のみ。縁は GeomType.CIRCLE のうち軸方向位置が最小のもの
```

- 面が軸の側へへこむか(外向き法線が軸の方を向くか)を確かめる。へこむなら受けは凸の円柱。
- 軸が傾いているとき、下端の円板も傾く。埋め込み量は「いちばん浅い点」で決める。

## 円錐面の受け(BLOCK): 円錐台の一部

```python
cone = jt.cone_params(face20)                              # apex, axis, semi_angle
# 軸が Y のとき、頂点から軸方向の距離 s = y - apex.Y
fr = jt.cone_frustum(cone, -HALF_Y - cone["apex"].Y, HALF_Y - cone["apex"].Y)   # Y を ±HALF_Y で切り出す
bb = face20.bounding_box()
box = Pos(cx, 0, cz) * Box(x_hi - x_lo, 2 * HALF_Y + 2, z_hi - z_lo)             # X は面の範囲 + 余白、下端はベースに埋める
block = fr & box
# 点 P1 を通り面に直交する平面で切り落とす(法線と軸方向を含む平面)
t = jt.cone_tangent(cone, p1, face20.center())             # P1 での円周方向の接線。面の中心の側を向ける
block = jt.keep_side(block, p1, t)
# 切断面の側辺(Y=±HALF_Y)の2本に C5
block = chamfer([e for e in block.edges() if abs(abs(e.center().Y) - HALF_Y) < 1e-3
                 and all(abs((v.center() - p1.center()).dot(t)) < 1e-3 for v in e.vertices())], 5.0)
# 上から見た4角(左壁・右壁と側面の縦の4辺)に C1
block = chamfer([e for e in block.edges().filter_by(Axis.Z)
                 if abs(abs(e.center().Y) - HALF_Y) < 1e-3
                 and (abs(e.center().X - x_lo) < 1e-3 or abs(e.center().X - x_hi) < 1e-3)], 1.0)
```

- 幅は、製品の面の最大幅に合わせる(ユーザーが「F20 の最大幅(20)に合わせる」と指示した)。
- 右端は、円錐面が下向きになる手前(面の右端ぴったり)で止めると、アンダーカットが無い。余白を付けるなら、`downward_area` で確認する。
- 切断面を作る平面の選び方が複数あるので、「面に直交する平面」の意味(法線を含む)をユーザーに確認する。

## ベースの座(ポケット)、逃げ、ear

```python
pocket = Pos(cx, 0, cz) * Box(x1 - x0, 2 * HALF_Y, depth_z)           # 受けの下端の輪郭(+ 片側に広げた逃げ)
pocket = fillet(pocket.edges().filter_by(Axis.Z).filter_by_position(Axis.X, x1 - .01, x1 + .01), 2.0)  # 広げた側の隅 R2
for sy in (1, -1):                                                    # ear: 隅の点に中心を合わせた円、隅ごとに1つ
    pocket = pocket + Pos(x0, sy * HALF_Y, cz) * Cylinder(EAR_D / 2, depth_z)
base_part = block - pin - pocket
```

- 受けと同じ形(`block - pin - block_shape`)で引くと、ポケットは受けぴったり。はめあいの隙間は図面の公差で指示する(ユーザーの方針)。
- ポケットの上は、ベース上面より少し上まで伸ばして、面を確実に抜く。

## ボルト(組立のとき)

下から上へ。穴はボルトの軸方向(傾いた円柱ならその軸)に開ける。`o` は軸がベース下面と交わる点、`ax` は軸の向き、`cb` は座ぐりの深さ(軸方向)。

```python
base_part = base_part - jt.axial_cyl(o, ax, -3.0, s_top, CLEAR_D)      # 通し穴(s_top: ベース上面まで)
base_part = base_part - jt.axial_cyl(o, ax, -3.0, cb, CBORE_D)         # 座ぐり
support   = support   - jt.axial_cyl(o, ax, 0.0, cb + BOLT_L + 1.6, TAP_D)   # 受け側の下穴(先端 + 1.6 まで)
head = jt.axial_cyl(o, ax, cb - HEAD_H, cb, HEAD_D); shank = jt.axial_cyl(o, ax, cb, cb + BOLT_L, D)
bolt = head + shank                                                    # 干渉確認と表示用
```

寸法の目安(六角穴付きボルト。JIS B 1176 / JIS B 1001 とカタログで確認する):

| 呼び | 頭径 | 頭高さ | 通し穴(中級) | 座ぐり径 | 下穴 |
|------|------|--------|----------------|----------|------|
| M3 | 5.5 | 3 | 3.4 | 6.5 | 2.5 |
| M4 | 7 | 4 | 4.5 | 8 | 3.3 |
| M5 | 8.5 | 5 | 5.5 | 9.5 | 4.2 |
| M6 | 10 | 6 | 6.6 | 11 | 5.0 |
| M8 | 13 | 8 | 9 | 14 | 6.8 |

- 表の「下穴」の列は、めねじ孔の下穴の部分の径(`SKILL.md` の共通仕様 15)。ねじの深さの部分は、呼び径の孔(M6 なら φ6)で描き、その先に、この下穴の径をピッチ × 3 深く、先端を円錐にして足す(`scripts/screws.py`)。以下の `TAP_D` を下穴の径で描くコードは、この決まりより前の例。
- 座ぐりの深さは頭高さ + 約 0.4。**傾けた軸では、座ぐりの下面側の縁が浅くなる**ので、頭が下面から出ないように深くする(15° 傾けた M4 で 5.5)。
- ねじのかかりは、`受けの下端の軸方向位置` から `ボルト先端` まで。M の 1.5 倍以上を目安にする。
- 座ぐり底から受けの座までの肉厚が薄くなりがち(2〜3mm)。数値で報告する。
- ボルトの位置は、ベースの左端からの距離を切りよく(13、28、50 など)。受けの幅の中心に対して均等にする、などの指示に合わせる。

## 文字

```python
tx = jt.left_aligned_text("1行目\n2行目", cap_height=3.2, font="MS Gothic", center_xy=(cx, cy), z=BASE_TOP)
engrave = extrude(tx, amount=-1.5)                  # 単品用: 彫り込む(深さ 1.5)
base_part = base_part - engrave
text_obj = Compound(tx.faces())                     # 組立用: 厚さ 0 の面を上面に置くだけ
text_view = Pos(0, 0, 0.02) * text_obj              # ビューアーと PNG のときだけ持ち上げる(ちらつき防止)
```

- `Text` のサイズは、大文字の高さではなくフォントサイズ。`jt.cap_ratio(font)` で比を実測して逆算する。
- 複数行は行ごとに中央揃えで並ぶので、`left_aligned_text` で左揃えにする。
- 位置は、面の帯(ワークが入らない側)の中央。製品の外形と重ならないことを確認する。

## 検証(変更のたびに)

```python
jt.is_single_valid_solid(part)                    # 正常なソリッドが1つ
jt.overlap_volume(a, b)                           # 部品どうし・製品との重なり。0 が理想(円柱と面の接触で 0.01 程度の誤差は出る)
jt.uncovered_points(block, face20)                # 製品の面の点が受けの中に入っているか(0 が理想)
jt.downward_area(cone_face)                       # 下向きの面の面積(底面を除いて 0 が理想)
section = part & (Pos(...) * Box(..., 0.002))     # 断面の確認。材料の有無は part.is_inside(Vector(x, y, z))
```

- 検証の値は、報告にそのまま書く(体積、重なり、かかり、肉厚など)。手順書の「検証」の期待値にする。
- 面の法線は、テッセレーションの三角形の向きではなく、`face.normal_at(点)` で取る(三角形の向きは面の向きと一致しない)。

## 出力

```python
export_stl(solid, path, tolerance=0.02, angular_tolerance=0.0873, ascii_format=False)   # 3D プリント用
jt.export_assembly_step([(base, "BASE", "steelblue"), (block, "BLOCK", "limegreen"), ...], path)   # 組立
jt.save_view_png(path)                            # ビューアーの今の画面(事前に表示してから)
```

- STL の確認: 三角形の辺がすべて2回現れ(向きは逆)、符号つき体積が STEP の体積とほぼ一致すること。
- STEP の確認: `import_step` で読み直し、子の数・名前・体積・色を確かめる。
- 結合は `a.fuse(b, c).clean()`。ソリッドが1つになるか確かめる。結合は別の変数に入れて、元の部品は残す。

## ビューアーの扱い

- `show(...)` は部品ごとに名前・色・透明度を付ける。更新のたびに送る。`reset_camera=Camera.KEEP`。
- 警告 "OCP CAD Viewer backend is not connected" は、寸法の計測が使えないだけで、表示には影響しない。
- `ocp_vscode` 4.x のスタンドアロン表示は別パッケージ `ocp_viewer`(ブラウザで見たいとき)。通常は VS Code の拡張を使う。ポートは 3939。
- 画面保存を使う場合は、ビューアーを開いた状態で、表示してから 4 秒ほど待って保存する。画像の大きさはビューアーのパネルの大きさで決まる(パネルが小さいと小さい画像になる)ので、手順書に載せる画像は、パネルを十分に広げてから保存する。
