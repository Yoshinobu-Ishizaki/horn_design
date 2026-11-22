# 作業記録 (bell01)

作業時間と指示の記録。時刻は JST。開始時刻は epoch 1795325812 (`date +%s`)。
指示ごとに、番号・指示(ユーザーの言葉を要約)・備考(決めた解釈、数値、確認の結果)を1行で追記する。

## 指示ログ

| # | 時刻 | 指示 | 備考 |
|---|------|------|------|
| 1 | 2026-11-22 14:36:52 (epoch 1795325812) | ホルンのベルを `cad/bell01` で設計する。旧 FreeCAD ファイルを移し、ベルの芯線を `bell01-ctr.dxf` に出す | `cad/bell_01.FCStd`(と FCBak)を `cad/bell01/` へ移動。芯線はスケッチ `Sketch`(Label `CenterPath`)。直線 180 + 円弧 R300(104.720)・R165(230.383)・R140(171.042)・R152(154.490)、全長 840.635 mm。XY 平面、始点 (0,0)(R150 のリム側。Sketch002)、終点 (266.910, 135.336)(R8 の細い側。Sketch001)。`tools/extract_centerline.py` で LINE・ARC のまま DXF に出し、読み戻して長さと半径の一致を確認 |
| 2 | 2026-11-22 14:48:03 (epoch 1795326483) | L-D を `mensur/bell` から取る(`bell_20180330_p10.csv` が FreeCAD と一致するはず)。vss スキルで作る | `make_bell.ipynb` は D = a/(x+b)^p + c(p=0.83081841、D(0)=300、リム角 -80°、D(850)=16、D(120)=65)。p10 は FreeCAD の Spreadsheet001 と同じ。FreeCAD の Face_Pipe は表の点で一致(L≥10)、リム付近は粗い(L=5 で 265.9 に対し式は 253.1)。p10 をスプラインにすると 1 mm 表から最大 1.04 mm(L=3)ずれる。確認の結果: **1 mm 表 `bell_20180330_xyrev.csv` を使う**、**芯線 840.635 で切る**(表は 850。終点 D=16.125、FreeCAD と同じ)。`ocp/bell01_surface.py`(`variable_pipe_law`)でサーフェス 5 面、面積比 1.000001、直径誤差 0.0000 mm、体積比 1.000001。Viewer に表示、STEP `output/bell01/bell01_bore_surface.step`(95 KB) |

## 経過

- 開始 epoch 1795325812
- 形状: FCStd には Face_Pipe(サーフェス)・Offset_Pipe(板厚付き)と、L-D 表らしい Spreadsheet001 がある(未確認)
- 未決: 板厚(ソリッドにするか、厚み)
