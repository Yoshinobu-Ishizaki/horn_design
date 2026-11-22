"""ネジのモデルの簡略化: めねじの孔と、ネジの代わりの棒。

決まり(`claude_cad_general` の共通仕様 15):
- ねじ山は作らず、呼び径の孔で代用する(M6 のねじ穴は φ6)。
- めねじ孔(止まり)は、ネジであることが分かるように、ねじの深さの先に、下穴(タップ下穴の径)を
  ピッチ × 3 だけ深く掘り、先端を円錐(ドリル先端 118°)にする。モデルが重くなるときは省略できる(`simple=True`)。
- ネジそのもの(止めネジなど)を入れるときは、呼び径の棒で代用する(`rod`)。

孔の向き: 開口面が z=0、奥は +Z。`hole_at` で、開口面の中心と、奥へ向かう向きを指定して置く。
呼び径は coarse(並目)のみ: M3、M4、M5、M6、M8、M10、M12。それ以外はエラー(ユーザーに確認する)。
"""

from __future__ import annotations

import math

from build123d import Align, Cone, Cylinder, Plane, Pos

# 呼び径 → (並目のピッチ, タップ下穴径)
COARSE = {
    3: (0.5, 2.5),
    4: (0.7, 3.3),
    5: (0.8, 4.2),
    6: (1.0, 5.0),
    8: (1.25, 6.8),
    10: (1.5, 8.5),
    12: (1.75, 10.2),
}
DRILL_EXTRA_PITCHES = 3.0  # ねじの深さの先に、下穴をピッチの何倍深く掘るか
TIP_ANGLE_DEG = 118.0  # ドリル先端の角度
_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def _size(nominal) -> int:
    """`6`、`6.0`、`"M6"` のどれでも、呼び径の整数にする。"""
    n = int(float(str(nominal).upper().lstrip("M")))
    if n not in COARSE:
        raise ValueError(f"呼び径 M{n} の並目のピッチと下穴径が未登録(対応: {sorted(COARSE)})。ユーザーに確認する")
    return n


def pitch_and_drill(nominal) -> tuple[float, float]:
    """(並目のピッチ, タップ下穴径)。"""
    return COARSE[_size(nominal)]


def total_depth(nominal, thread_depth: float, *, simple: bool = False) -> float:
    """開口面から、下穴の円筒の奥まで(円錐の先端は含まない)。"""
    if simple:
        return thread_depth
    return thread_depth + DRILL_EXTRA_PITCHES * pitch_and_drill(nominal)[0]


def tapped_hole(nominal, thread_depth: float, *, simple: bool = False):
    """めねじ孔(止まり)の抜き型。開口面 z=0、奥は +Z。

    呼び径の円柱(深さ thread_depth)+ 下穴径の円柱(ピッチ × 3 深く)+ 先端の円錐(118°)。
    `simple=True` なら、呼び径の円柱だけ(軽くする)。
    """
    n = _size(nominal)
    pitch, drill = COARSE[n]
    thread = Cylinder(n / 2, thread_depth, align=_MIN)
    if simple:
        return thread
    extra = DRILL_EXTRA_PITCHES * pitch
    drill_part = Pos(0, 0, thread_depth) * Cylinder(drill / 2, extra, align=_MIN)
    tip_h = (drill / 2) / math.tan(math.radians(TIP_ANGLE_DEG / 2))
    cone = Pos(0, 0, thread_depth + extra) * Cone(drill / 2, 0, tip_h, align=_MIN)
    return thread + drill_part + cone


def rod(nominal, length: float):
    """ネジの代わりの棒(呼び径)。z=0 から +Z へ length。孔に入れる側の向きは `hole_at` と同じ。"""
    return Cylinder(_size(nominal) / 2, length, align=_MIN)


def hole_at(origin, direction, nominal, thread_depth: float, *, simple: bool = False):
    """開口面の中心 `origin` に、奥へ向かう向き `direction` で、めねじ孔を置く。"""
    return Plane(origin=tuple(origin), z_dir=tuple(direction)) * tapped_hole(nominal, thread_depth, simple=simple)


def rod_at(origin, direction, nominal, length: float):
    """`origin` から `direction` へ length の、ネジの代わりの棒を置く。"""
    return Plane(origin=tuple(origin), z_dir=tuple(direction)) * rod(nominal, length)
