"""OCP Viewer に重ねる注記(寸法・孔の注記・表面粗さ記号)。ソリッドではなく、平らな面で作る。

    from bope_claude_cad.annotation import dim_linear, hole_note, roughness_note, show_with_annotations

    dim = dim_linear(plate.vertices()[0], base.vertices()[1], view="front", direction="vertical", offset=12)
    note = hole_note(plate.edges()[10], "M4↧10", view="top", angle=135)    # M4↧10
    ra = roughness_note(plate.vertices()[0], "Ra 1.6", view="front")
    show_with_annotations([plate, base], {"DIM-24": dim, "NOTE-M4": note, "RA-1": ra}, names=["plate", "base"])

方針(人の決定、2026-11-13):
- **輪郭表示は OFF が既定**: 注記は `Render.FACES`(面だけ表示)で出す。ビューアは面の縁に灰色の輪郭線を引き、細い文字が中空(袋文字)に見えるため。
  色は黒。`show_with_annotations` が既定にする(`outline=True` で戻せる)
- **フォントは Segoe UI Symbol に統一**(`FONT`)。深さ ↧・ざぐり ⌴・皿穴 ⌵・直径 ⌀ を 1 つのフォントで出せる。日本語(カタカナ)は無いので、
  注記は記号だけで書く(`M4↧10`、`⌴⌀11↧6.5`)。Windows 標準のフォントなので、別の PC・OS では字形が出ないことがある(配るときは画像化した結果で)
- 寸法の補助線は、対象の頂点・縁から外へ引き出す(面間の寸法でも、頂点から)。矢印は build123d の既定
- 粗さ記号は JIS B 0031:2003 の新しい書き方: ▽(除去加工あり)+ 右上の長い斜線 + 水平線、**Ra の値は水平線の下・斜線の右**。
  寸法は文字高さ h に対する比で、`dxf-drafting-support` スキルの `rules.toml [roughness]` と同じ(規格本文との照合は未了)。▽ の 1 辺 3 mm が既定

見る向き(view): `front`(−Y 側から見る。画面の右 = +X、上 = +Z)・`back`・`left`・`right`・`top`(+Z 側から。右 = +X、上 = +Y)・`bottom`。
注記は、見る向きの平面(対象の手前 `lift` mm)に置く。見る向きと違う向きから見ると、細い線にしか見えない。
"""

from __future__ import annotations

import math

from build123d import (
    Align,
    ArrowHead,
    Compound,
    DimensionLine,
    Draft,
    Line,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Text,
    Vector,
)

FONT = "Segoe UI Symbol"
LINE_W = 0.25          # 引出線・補助線・記号の線の太さ(mm)
LIFT = 0.5             # 注記を、対象より手前へ出す距離(mm)(対象の面との重なりを避ける)

# 見る向きごとの、画面の右(x_dir)と、見る人へ向かう向き(normal)。画面の上 = normal × x_dir
VIEWS = {
    "front": ((1, 0, 0), (0, -1, 0)),
    "back": ((-1, 0, 0), (0, 1, 0)),
    "left": ((0, -1, 0), (-1, 0, 0)),
    "right": ((0, 1, 0), (1, 0, 0)),
    "top": ((1, 0, 0), (0, 0, 1)),
    "bottom": ((1, 0, 0), (0, 0, -1)),
}


def _basis(view: str):
    """(画面の右, 画面の上, 見る人へ向かう向き)の単位ベクトル。"""
    if view not in VIEWS:
        raise ValueError(f"view は {', '.join(VIEWS)} のどれか: {view!r}")
    x, n = (Vector(*v) for v in VIEWS[view])
    return x, n.cross(x), n


def _sibling(name: str):
    """同じフォルダの別モジュール。パッケージ(bope_claude_cad.<name>)としても、スキルの scripts/ の単体ファイルとしても読める。"""
    import importlib

    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _line(p, q) -> Compound:
    """スケッチ座標(2D)の p から q への細い線(面)。"""
    d = Vector(q[0] - p[0], q[1] - p[1], 0)
    mid = Vector(p[0], p[1], 0) + d / 2
    return Pos(mid.X, mid.Y, 0) * Rot(0, 0, math.degrees(math.atan2(d.Y, d.X))) * Rectangle(d.length, LINE_W)


def _place(sketch, view: str, points) -> Compound:
    """スケッチ(座標 = 見る向きの画面の (右, 上) の絶対位置)を、見る向きの平面に置く。
    平面の位置は、points(対象の点)のうち最も手前の点から LIFT だけ手前。"""
    _, _, n = _basis(view)
    x, _, _ = _basis(view)
    depth = max(Vector(p).dot(n) for p in points) + LIFT
    return Plane(origin=tuple(n * depth), x_dir=tuple(x), z_dir=tuple(n)) * sketch


def _uv(p, view: str) -> tuple[float, float]:
    x, y, _ = _basis(view)
    v = Vector(p)
    return v.dot(x), v.dot(y)


def _vec(p) -> Vector:
    return p.center() if hasattr(p, "center") and not isinstance(p, Vector) else Vector(p)


# ---- 寸法 ----
def dim_linear(pa, pb, *, view: str = "front", direction: str = "vertical", offset: float = 12.0,
               side: str | None = None, label: str | None = None, font_size: float = 3.0,
               gap: float = 1.5, over: float = 2.0) -> Compound:
    """2 点 pa・pb(Vector か頂点)の間の寸法。補助線は各点から外へ引き出し、寸法線・矢印・数値を付ける。

    direction: "vertical"(画面の上下に測る)か "horizontal"(左右)。view の平面に投影した距離を測る。
    offset: 外側の点から寸法線までの距離。side: 寸法線を置く側。vertical は "low"(左、既定)/"high"(右)、
            horizontal は "high"(上、既定)/"low"(下)。補助線は各点の位置から出るので、2 点の外側の位置が違ってもよい。
    label: 数値の文字(既定は測った長さ。単位なし)。矢印・文字は build123d の DimensionLine の既定。
    """
    if direction not in ("vertical", "horizontal"):
        raise ValueError("direction は vertical か horizontal")
    a, b = _vec(pa), _vec(pb)
    ux, vy, n = _basis(view)
    if direction == "vertical":
        m, o = vy, -ux              # 測る向き = 画面の上、外向き = 左(m × o = n)
        sign = -1 if side == "high" else 1
    else:
        m, o = ux, vy               # 測る向き = 右、外向き = 上
        sign = -1 if side == "low" else 1
    s = [a.dot(m), b.dot(m)]
    t = [a.dot(o), b.dot(o)]
    length = abs(s[1] - s[0])
    t_ext = max(t) if sign > 0 else min(t)
    t_dim = t_ext + sign * offset
    draft = Draft(font_size=font_size, font=FONT, line_width=LINE_W, display_units=False)
    parts = [DimensionLine(Line((min(s), t_dim), (max(s), t_dim)), draft=draft, label=label or _num(length))]
    for si, ti in zip(s, t, strict=True):
        y0, y1 = ti + sign * gap, t_dim + sign * over
        parts.append(Pos(si, (y0 + y1) / 2, 0) * Rectangle(LINE_W, abs(y1 - y0)))     # 補助線(細い長方形の面)
    # スケッチの座標は (m 方向, o 方向)。m × o = n なので、平面は x_dir = m、z_dir = n
    depth = max(a.dot(n), b.dot(n)) + LIFT
    return Plane(origin=tuple(n * depth), x_dir=tuple(m), z_dir=tuple(n)) * Compound(children=parts)


# ---- 孔の注記 ----
def hole_note(edge, label: str, *, view: str = "top", angle: float = 135.0, font_size: float = 3.0,
              arrow: float = 3.0, elbow: float = 10.0) -> Compound:
    """孔の縁(円の辺 `edge`)から矢印付きの引出線を引き、水平の折れ線の上に文字を置く。

    label は記号だけで書く(例 "M4↧10"、"⌴⌀11↧6.5")。angle は、孔の中心から見て引出線を出す向き
    (度。画面の右から反時計回り)。矢印は孔の中心を指し、折れ線は外側(左右)へ伸ばす。view は孔の軸の向きから見る向き
    (Z 軸の孔なら "top")。
    """
    c, r = edge.arc_center, edge.radius
    cu, cv = _uv(c, view)
    u = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    tip = (cu + u[0] * r, cv + u[1] * r)                           # 孔の縁の点(矢印の先端)
    el = (tip[0] + u[0] * elbow, tip[1] + u[1] * elbow)            # 折れ点
    side = -1 if u[0] < 0 else 1
    text = Text(label, font_size, font=FONT, align=(Align.MIN, Align.MIN))
    width = text.bounding_box().size.X
    end = (el[0] + side * (width + 2), el[1])
    arrow_face = Pos(tip[0], tip[1], 0) * ArrowHead(arrow, rotation=math.degrees(math.atan2(-u[1], -u[0])))
    tx = el[0] + (1 if side > 0 else -(width + 1))
    parts = [arrow_face,
             _line((tip[0] + u[0] * arrow, tip[1] + u[1] * arrow), el),
             _line(el, end),
             Pos(tx, el[1] + 1.0, 0) * text]                       # 折れ線の上に文字
    return _place(Compound(children=parts), view, [c])


# ---- 表面粗さ記号 ----
# 形は文字高さ h に対する比。出典: dxf-drafting-support の rules.toml [roughness](JIS B 0031:2003 に合わせて調整済み。規格本文との照合は未了)
TRI_SIDE = 3.0             # ▽ の 1 辺(mm)。これで h が決まり、記号全体と文字が比例して拡大縮小する
TRI_HALF_WIDTH = 0.861     # ▽ の底辺の半幅 / h
TRI_HEIGHT = 1.491         # ▽ の高さ(頂点から底辺まで) / h
LONG_LEG_DX = 1.727        # 頂点から水平線の左端までの水平距離 / h
TOTAL_HEIGHT = 2.994       # 頂点から水平線まで / h
TEXT_X = 0.773             # 値の左端: 水平線の左端から右へ / h
TEXT_Y = -1.249            # 値の基準線: 水平線から下へ / h(新 JIS は水平線の下)
TEXT_MARGIN = 1.0          # 文字の右側の余白 / h
BAR_BLANK = 4.0            # 文字が無いときの水平線の長さ / h
ROUGHNESS_KINDS = ("required", "any")   # required = ▽(除去加工あり)、any = V(除去加工の要否を問わない)


def default_h() -> float:
    """▽ の 1 辺が TRI_SIDE になる文字高さ h(mm)。"""
    return TRI_SIDE / (2 * TRI_HALF_WIDTH)


def roughness_symbol(label: str | None = None, kind: str = "required", h: float | None = None) -> Compound:
    """表面粗さ記号(JIS B 0031:2003)。スケッチ座標で、頂点が原点(面に当てる点)、記号は面の上(+Y)に立つ。

    required: ▽ + 右上の長い斜線 + 水平線。値(Ra 1.6 など)は水平線の下・斜線の右。
    any: ▽ の底辺の短線が無い V(除去加工の要否を問わない)。
    未実装: 除去加工禁止(円付き)、加工方法・筋目・削り代・全周。
    """
    if kind not in ROUGHNESS_KINDS:
        raise ValueError(f"kind は {', '.join(ROUGHNESS_KINDS)} のどれか: {kind!r}")
    h = default_h() if h is None else h
    tw, th = TRI_HALF_WIDTH * h, TRI_HEIGHT * h
    bar_x, bar_y = LONG_LEG_DX * h, TOTAL_HEIGHT * h
    text = None
    if label:
        text = Text(label, h, font=FONT, align=(Align.MIN, Align.MIN))
        bar_len = TEXT_X * h + text.bounding_box().size.X + TEXT_MARGIN * h
    else:
        bar_len = BAR_BLANK * h
    parts = [_line((0, 0), (-tw, th)),                              # 左の脚
             _line((0, 0), (bar_x, bar_y)),                         # 長い斜線(▽ の右辺の延長)
             _line((bar_x, bar_y), (bar_x + bar_len, bar_y))]       # 水平線
    if kind == "required":
        parts.append(_line((-tw, th), (tw, th)))                    # ▽ の底辺
    if text is not None:
        parts.append(Pos(bar_x + TEXT_X * h, bar_y + TEXT_Y * h, 0) * text)
    return Compound(children=parts)


def roughness_note(point, label: str | None = None, *, kind: str = "required", view: str = "front",
                   h: float | None = None) -> Compound:
    """面の上の点 `point`(Vector か頂点)に記号の頂点を当てて置く。view は、その面が線に見える向き。"""
    p = _vec(point)
    u, v = _uv(p, view)
    return _place(Pos(u, v, 0) * roughness_symbol(label, kind, h), view, [p])


# ---- 表示 ----
def show_with_annotations(objs, annotations: dict, *, names=None, outline: bool = False, color: str = "black", **kwargs):
    """部品 objs と注記 annotations({名前: 形})を `bope_claude_cad.viewer.show` で表示する。

    注記は、既定で輪郭表示 OFF(`Render.FACES`)・黒で出す(`outline=True` で輪郭を出す)。部品は通常の表示。
    names は部品の名前のリスト(省略時は Part_<番号>)。ほかの引数は `show` にそのまま渡す。
    """
    from ocp_vscode import Render

    viewer = _sibling("viewer")

    objs = list(objs)
    names = list(names) if names else [f"Part_{i}" for i in range(len(objs))]
    if len(names) != len(objs):
        raise ValueError("names と objs の数が違います")
    mode = Render.ALL if outline else Render.FACES
    kwargs.setdefault("colors", [None] * len(objs) + [color] * len(annotations))
    kwargs.setdefault("modes", [Render.ALL] * len(objs) + [mode] * len(annotations))
    return viewer.show(*objs, *annotations.values(), names=[*names, *annotations], **kwargs)
