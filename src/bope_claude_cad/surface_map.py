"""曲面への輪郭のマップと、座(支柱座など)の厚み付け。

流れ
1. 輪郭(平らな板=ブランクの外形)を用意する: ``outline_from_dxf`` / ``outline_from_face`` /
   build123d の形(``Rectangle`` ``SlotOverall`` など)。ブランクは XY 平面、原点が基準点になる。
2. ``map_outline`` で、曲面の基準点の法線に垂直にブランクを置き、曲面へマップする。
   - ``mode="wrap"``: ブランクの縦横の長さを保つように貼る(``Face.wrap``)。曲面上の面のコピーになる。
   - ``mode="normal"``: 基準点の法線方向に平行投影する(``Face.project_to_shape``)。
3. ``thicken_seat`` で厚みを付け、ソリッドにする。
4. ``check_mapping`` で長さ・面積のずれを測る(警告だけで止めない)。

``wrap`` には 3 つの方法がある(``SeatParams.wrap_method``)。
- ``"section"``(既定): ブランクの縦横の長さ(長手 x と幅 y)を保つ。基準点から x 方向に、曲面を法線と x 方向を
  含む平面で切った線(子午線)を取り、その上に弧長 x の点を置く。その点で子午線の接線に直交する平面
  (接平面ベクトルと法線で張る)で曲面を切った断面線に沿って、弧長 y の点を取る。輪郭の各点をこの写像で写して
  スプラインで結ぶ。長手は子午線に沿って、幅は各断面線に沿って、元の長さと一致する(周の長さは保たない)。
  閉じ目の隙間は出ない。曲面を切る回数が多いので、数十秒かかる。
- ``"march"``: 自前。輪郭を細かい点列にし、基準点から曲面上を一歩ずつ進める(各ステップは
  接平面内で元の長さだけ進めて曲面へ射影し、基準方向は接平面へ射影して引き継ぐ)。閉じた輪郭が閉じない
  隙間(曲面の曲がりによる)は、周に沿って配る。速く、失敗しにくい。隙間の大きさを警告する。
- ``"build123d"``: ``Face.wrap``。辺ごとの長さを保つが、輪郭を閉じる最後の辺でずれる。許容誤差が厳しいと
  失敗するので、0.05 mm から 2 倍ずつ緩めて再試行し、継ぎ目の辺もずらす。巨大な B スプライン面では
  1 回に分単位かかり、ほぼ円錐の面では閉じ処理(延長の交点)が失敗することがある。

どちらも、二重曲率(球・自由曲面)で、輪郭が曲率半径に比べて大きいほどずれは増える。
"""

from __future__ import annotations

import itertools
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from build123d import (
    Axis,
    Edge,
    Face,
    Location,
    Plane,
    ShapeList,
    Solid,
    Vector,
    Vertex,
    Wire,
)

MODES = ("wrap", "normal")


@dataclass
class SeatParams:
    """座の生成パラメータ(寸法は mm)。"""

    point: tuple[float, float, float]  # 基準点(曲面上、または近く。最近点に寄せる)
    x_dir: tuple[float, float, float] = (1.0, 0.0, 0.0)  # ブランクの横方向(接平面へ射影して使う)
    thickness: float = 3.0
    mode: str = "wrap"
    outward: bool = True  # True: 曲面の法線の向き(表側)へ厚みを付ける。False: 逆
    wrap_method: str = "section"  # "section"(長手と幅を保つ) / "march"(周を保つ追跡) / "build123d"(Face.wrap)
    long_axis: str = "auto"  # section の長手: "auto"(長い方。同程度なら曲率が小さい方) / "length" / "curvature" / "x" / "y"
    width_tol: float = 0.05  # section の検証で、断面の幅が元の幅からこれを超えてずれたら警告する(mm)
    step: float | None = None  # 輪郭の標本間隔(mm)。None なら section は 1.0、march は 0.5。小さいほど精密で遅い
    fill_grid: float = 4.0  # march で面を張るときの、曲面上の通過点の格子間隔(mm)。小さいほど曲面から浮かない
    reproject: bool = False  # march の面を曲面へ投影し直す(実験的。既定では使わない)
    tolerance: float = 0.05  # build123d の wrap の許容誤差(失敗時は緩めて再試行)
    warn_ratio: float = 0.02  # 辺の長さ・面積のずれが、これを超えたら警告する
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- 輪郭の用意


def outline_from_face(face: Face, center: bool = True) -> Face:
    """平らな面(STEP の面など)を、XY 平面へ移した輪郭にする。

    ``center=True`` で、外形の重心を原点に置く(基準点=重心)。穴は残る。
    """
    pl = Plane(face)
    flat = pl.location.inverse() * face
    flat = Face(flat.outer_wire(), flat.inner_wires())
    if center:
        flat = flat.moved(Location(-flat.center()))
    return flat


def outline_from_dxf(
    path: str | Path,
    layer: str | None = None,
    center: bool | str = True,
    window: tuple[float, float, float, float] | None = None,
    solid_only: bool = False,
    types: tuple[str, ...] = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE"),
    close_open: bool = False,
    tol: float = 0.01,
) -> Face:
    """DXF の LINE・ARC・CIRCLE・LWPOLYLINE(直線のみ)から、輪郭の面を作る。

    つながった閉じた線のうち、外形が最大のものを外周、ほかを穴とする。

    - ``center``: ``True`` で外周の外形の中心を原点に寄せる。``"left"`` は、外形の左端・縦の中央を原点にする
      (左の頂点を基準点にしたいとき)。``False`` は DXF の座標のまま。
    - ``window=(x0, y0, x1, y1)``: 図形の端点が、すべてこの範囲に入るものだけを使う。図枠や別の図が
      同じシートにあるとき、展開図だけを取る。
    - ``solid_only``: 線種が実線(空または CONTINUOUS)のものだけを使う(想像線・破線・中心線を除く)。
    - ``types``: 使う図形の種類。寸法線(LINE)が混じる図では ``("ARC",)`` などに絞る。
    - ``close_open``: つないだ外周が開いていたら、両端を直線で結んで閉じる(図に描かれていない切断線の辺など)。
    - ``tol``: 端点のずれの許容(DXF 変換の端点は 1e-3 程度ずれる)。
    """
    import math

    import ezdxf

    def in_win(pts) -> bool:
        if window is None:
            return True
        x0, y0, x1, y1 = window
        return all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts)

    doc = ezdxf.readfile(str(path))
    edges: list[Edge] = []
    wires: list[Wire] = []
    for e in doc.modelspace():
        if layer is not None and e.dxf.layer != layer:
            continue
        if solid_only and e.dxf.get("linetype", "") not in ("", "CONTINUOUS", "BYLAYER"):
            continue
        t = e.dxftype()
        if t not in types:
            continue
        if t == "LINE":
            s, p = e.dxf.start, e.dxf.end
            if in_win([(s.x, s.y), (p.x, p.y)]):
                edges.append(Edge.make_line((s.x, s.y, 0), (p.x, p.y, 0)))
        elif t == "ARC":
            c, r = e.dxf.center, e.dxf.radius
            a0, a1 = e.dxf.start_angle, e.dxf.end_angle
            ends = [(c.x + r * math.cos(math.radians(a)), c.y + r * math.sin(math.radians(a))) for a in (a0, a1)]
            if in_win(ends):
                edges.append(Edge.make_circle(r, Plane(origin=(c.x, c.y, 0)), a0, a1))
        elif t == "CIRCLE":
            c, r = e.dxf.center, e.dxf.radius
            if in_win([(c.x - r, c.y - r), (c.x + r, c.y + r)]):
                wires.append(Wire.make_circle(r, Plane(origin=(c.x, c.y, 0))))
        elif t == "LWPOLYLINE":
            pts = [(x, y, 0) for x, y, *_ in e.get_points()]
            if any(b for *_, b in e.get_points("xyb")):
                raise ValueError("バルジ(円弧)つき LWPOLYLINE は未対応。ARC に分解してください")
            if not in_win([(x, y) for x, y, _ in pts]):
                continue
            if e.closed:
                pts.append(pts[0])
            wires.append(Wire.make_polygon([Vector(*p) for p in pts]))
    if edges:
        wires.extend(Wire.combine(edges, tol=tol))
    if not wires:
        raise ValueError("輪郭にできる図形が見つからない(レイヤ・window・solid_only を確認)")
    wires.sort(key=lambda w: w.bounding_box().size.X * w.bounding_box().size.Y, reverse=True)
    outer, inner = wires[0], wires[1:]
    if not outer.is_closed:
        if not close_open:
            raise ValueError("外周が閉じていない(端点のずれ、または close_open=True を確認)")
        ends = [v.center() for v in outer.vertices() if len([e for e in outer.edges() if v in e.vertices()]) == 1]
        if len(ends) != 2:
            raise ValueError(f"開いた外周の端が 2 点でない({len(ends)} 点)ので、閉じられない")
        outer = Wire(list(outer.edges()) + [Edge.make_line(ends[0], ends[1])])
    face = Face(outer, inner)
    bb = outer.bounding_box()
    if center == "left":
        face = face.moved(Location(-Vector(bb.min.X, bb.center().Y, 0)))
    elif center:
        face = face.moved(Location(-bb.center()))
    return face


def _as_face(outline) -> Face:
    """Face・Wire・Sketch(``Rectangle`` など)を、XY 平面上の Face にする。"""
    if isinstance(outline, Face):
        return outline
    if isinstance(outline, Wire):
        return Face(outline)
    return outline.faces()[0]


# ---------------------------------------------------------------- 基準の座標系


def surface_frame(surface: Face, point, x_dir=(1, 0, 0)) -> Plane:
    """基準点の最近点で、Z=面の法線、X=x_dir を接平面へ射影した向きの座標系を返す。"""
    _, on_surf, _ = surface.distance_to_with_closest_points(Vertex(*point))  # (距離, 自分上の点, 相手上の点)
    p = Vector(on_surf)
    n = surface.normal_at(p)
    xd = Vector(*x_dir)
    xd = xd - n * xd.dot(n)
    if xd.length < 1e-6:
        raise ValueError("x_dir が法線と平行で、接平面へ射影できない")
    return Plane(origin=p, x_dir=xd.normalized(), z_dir=n)


# ---------------------------------------------------------------- マップ


class _Marcher:
    """曲面上を、接平面内の平面ベクトルで一歩ずつ進める(基準方向を平行移動しながら)。"""

    def __init__(self, surface: Face, frame: Plane):
        self.surface = surface
        self.p = Vector(frame.origin)
        self.r = Vector(frame.x_dir)  # 平面の +x に当たる、曲面上の向き
        self.n = Vector(frame.z_dir)

    def _snap(self, q: Vector) -> Vector:
        _, on, _ = self.surface.distance_to_with_closest_points(Vertex(*q))
        return Vector(on)

    def step(self, dx: float, dy: float) -> Vector:
        n = Vector(self.surface.normal_at(self.p))
        if n.dot(self.n) < 0:
            n = -n
        r = self.r - n * self.r.dot(n)
        r = r.normalized()
        y = n.cross(r)  # 平面の +y(Z=n, X=r の右手系)
        p2 = self._snap(self.p + r * dx + y * dy)
        n2 = Vector(self.surface.normal_at(p2))
        if n2.dot(n) < 0:
            n2 = -n2
        r2 = self.r - n2 * self.r.dot(n2)
        self.r, self.n, self.p = r2.normalized(), n2, p2
        return p2


def _sample_wire(wire: Wire, step: float) -> list[list[Vector]]:
    """外周・穴の辺を、順に連続するように向きをそろえて、辺ごとの点列(平面座標)にする。"""
    import math

    edges = wire.order_edges()
    out: list[list[Vector]] = []
    cur: Vector | None = None
    for e in edges:
        m = max(4, math.ceil(e.length / step)) if e.length > 0 else 1
        pts = [e.position_at(i / m) for i in range(m + 1)]
        if cur is not None and (pts[0] - cur).length > (pts[-1] - cur).length:
            pts.reverse()
        out.append(pts)
        cur = pts[-1]
    return out


def _march_wire(surface: Face, frame: Plane, wire: Wire, step: float) -> tuple[Wire, float, list[float]]:
    """平面の輪郭 1 本を、曲面へ追跡で写した Wire と、閉じ目の隙間(補正前, mm)を返す。

    基準点(原点)から、輪郭の最初の点まで平面で直線に進み(刻み ``step`` 以下)、輪郭を一周する。
    一周して戻った点と最初の点の差(曲面の曲がりによる隙間)は、周に沿って一様に配って消す。
    """
    import math

    runs = _sample_wire(wire, step)
    start = runs[0][0]
    mar = _Marcher(surface, frame)
    n_lead = max(1, math.ceil(start.length / step))
    for i in range(1, n_lead + 1):
        a, b = start * ((i - 1) / n_lead), start * (i / n_lead)
        mar.step(b.X - a.X, b.Y - a.Y)
    first = Vector(mar.p)
    mapped: list[list[Vector]] = []
    prev = start
    for pts in runs:
        row = [Vector(mar.p)]  # 辺の始点 = 前の辺の終点(連続)
        for q in pts[1:]:
            row.append(Vector(mar.step(q.X - prev.X, q.Y - prev.Y)))
            prev = q
        mapped.append(row)
        prev = pts[-1]
    gap_vec = first - mapped[-1][-1]
    # 周に沿った累積長で、隙間を一様に配る
    lens = [sum((row[i + 1] - row[i]).length for i in range(len(row) - 1)) for row in mapped]
    total = sum(lens) or 1.0
    done = 0.0
    edges: list[Edge] = []
    last_end: Vector | None = None
    for row, ln in zip(mapped, lens):
        n = len(row) - 1
        pts = []
        for i, q in enumerate(row):
            s = (done + ln * i / n) / total
            pts.append(surface_snap(surface, q + gap_vec * s))
        pts[0] = last_end if last_end is not None else first  # 辺をつなぐ端点を共有する
        if row is mapped[-1]:
            pts[-1] = first  # 最後の端点は最初の点に一致させて、確実に閉じる
        done += ln
        last_end = pts[-1]
        edges.append(Edge.make_spline(pts))
    ratios = [m.length / p.length for m, p in zip(edges, wire.order_edges())]  # 辺ごとの長さの比(写した/元)
    return Wire(edges), gap_vec.length, ratios


def surface_snap(surface: Face, q: Vector) -> Vector:
    """点を曲面上の最近点へ寄せる。"""
    _, on, _ = surface.distance_to_with_closest_points(Vertex(*q))
    return Vector(on)


def _wrap_march(
    surface: Face,
    blank: Face,
    frame: Plane,
    step: float,
    info: dict | None = None,
    grid: float = 4.0,
    reproject: bool = False,
) -> ShapeList[Face]:
    """輪郭を追跡で曲面へ写し、曲面を輪郭で切り取った面(継ぎ目で分かれたら複数枚)を返す。

    ``info`` に、閉じ目の隙間と辺の長さの比を入れる。
    """
    outer, gap, ratios = _march_wire(surface, frame, blank.outer_wire(), step)
    holes_all = [_march_wire(surface, frame, w, step) for w in blank.inner_wires()]
    holes = [(w, g) for w, g, _ in holes_all]
    gaps = [gap] + [g for _, g in holes]
    if info is not None:
        info["edge_ratios"] = ratios
        info["closing_gap"] = max(gaps)
    if max(gaps) > 0.05:
        warnings.warn(f"輪郭の閉じ目の隙間 {max(gaps):.3f} mm を周に配った(曲面の曲がりによる)", stacklevel=3)
    # 面の内側の通過点: 輪郭の内側に格子点(間隔 grid)を取り、原点から粗い刻みで追跡して曲面上に置く。
    # 曲面を通る点が密なほど、点列から張る面が曲面から浮かない(円弧と弦の差は刻み 3 mm で 1e-3 以下)。
    inner_pts = [frame.origin]
    bb = blank.bounding_box()
    nx = max(2, math.ceil(bb.size.X / grid))
    ny = max(2, math.ceil(bb.size.Y / grid))
    coarse = min(3.0, max(step, grid))
    for i in range(nx + 1):
        for j in range(ny + 1):
            q = Vector(bb.min.X + bb.size.X * i / nx, bb.min.Y + bb.size.Y * j / ny, 0)
            if q.length < 1e-6 or blank.distance_to(Vertex(*q)) > 1e-6:
                continue
            m = _Marcher(surface, frame)
            n_lead = max(1, math.ceil(q.length / coarse))
            for k in range(1, n_lead + 1):
                a, b = q * ((k - 1) / n_lead), q * (k / n_lead)
                m.step(b.X - a.X, b.Y - a.Y)
            inner_pts.append(m.p)
    face = Face.make_surface(outer, surface_points=inner_pts, interior_wires=[w for w, _ in holes])
    if not reproject:
        return ShapeList([-face if Vector(face.normal_at(frame.origin)).dot(frame.z_dir) < 0 else face])
    # 実験的: 基準法線の向きに曲面へ投影し直し、曲面そのものを輪郭で切り取った面にする。
    # 閉じた管などでは、手前の壁(継ぎ目で複数枚に分かれる)と反対側の壁の両方が返るので、位置で選ぶ。
    # ただし投影後の面が曲面から浮いて見える場合があり(UV で測ると 0.19 mm)、既定では使わない。
    near = bb.diagonal
    pieces: list[Face] = []
    for d in (-frame.z_dir, frame.z_dir):
        try:
            cands = [f for r in face.project_to_shape(surface, tuple(d)) for f in r.faces()]
        except Exception as e:  # noqa: BLE001  OCC の投影失敗
            warnings.warn(f"投影し直しの試行が失敗({type(e).__name__})", stacklevel=3)
            continue
        pieces = [f for f in cands if (Vector(f.center()) - frame.origin).dot(frame.z_dir) > -0.25 * near]
        if pieces and abs(sum(f.area for f in pieces) / face.area - 1) < 0.1:
            break
        pieces = []
    if not pieces:
        warnings.warn("曲面への投影し直しに失敗。点列から張った面のままにした", stacklevel=3)
        pieces = [face]
    pieces = [-f if Vector(f.normal_at(f.center())).dot(frame.z_dir) < 0 else f for f in pieces]
    return ShapeList(pieces)


class _ArcCurve:
    """曲面上の曲線(Wire)で、基準点からの符号つき弧長で点と接線を引く。"""

    def __init__(self, wire: Wire, base: Vector, direction: Vector):
        self.w = wire
        self.len = wire.length
        self.closed = wire.is_closed
        _, on, _ = wire.distance_to_with_closest_points(Vertex(*base))
        self.u0 = wire.param_at_point(Vector(on))
        self.sgn = 1.0 if Vector(wire.tangent_at(self.u0)).dot(direction) >= 0 else -1.0

    def _u(self, s: float) -> float:
        u = self.u0 + self.sgn * s / self.len
        if self.closed:
            return u % 1.0
        if not -1e-9 <= u <= 1 + 1e-9:
            raise ValueError(f"曲面の範囲を超える(弧長 {s:.2f} mm。曲線の長さ {self.len:.2f} mm)。面が足りない")
        return min(1.0, max(0.0, u))

    def point(self, s: float) -> Vector:
        return Vector(self.w.position_at(self._u(s)))

    def tangent(self, s: float) -> Vector:
        return Vector(self.w.tangent_at(self._u(s))) * self.sgn


def _section_curve(surface: Face, plane: Plane, base: Vector, direction: Vector) -> _ArcCurve:
    """曲面を平面で切った交線のうち、基準点を通るものを、基準点からの弧長で引ける曲線にする。"""
    res = surface.intersect(plane)
    edges = res.edges() if res is not None else []
    if not edges:
        raise RuntimeError("曲面と断面の平面が交わらない(面が足りない)")
    wires = Wire.combine(edges, tol=1e-3)
    w = min(wires, key=lambda q: q.distance_to(Vertex(*base)))
    return _ArcCurve(w, base, direction)


class _SectionMap:
    """平面の点 (x, y) を、曲面の子午線と断面線に沿った弧長 (x, y) の点へ写す。

    - 子午線: 基準点 A を通り、法線 n と x 方向を含む平面で曲面を切った線。A から弧長 x の点 S(x) を取る。
    - 断面線: S(x) を通り、子午線の接線に直交する平面(接平面ベクトルと法線で張る)で曲面を切った線。
      S(x) から断面線に沿って弧長 y の点が、(x, y) の像。向きは n × (子午線の接線) を +y とする。
    長手 x は子午線に沿って、幅 y は各断面線に沿って、元の長さと一致する(周の長さは保たない)。
    """

    def __init__(self, surface: Face, frame: Plane, tol_x: float = 0.02):
        self.surface = surface
        self.tol_x = tol_x
        a, x_dir, n = Vector(frame.origin), Vector(frame.x_dir), Vector(frame.z_dir)
        self.n = n
        self.meridian = _section_curve(surface, Plane(origin=a, z_dir=n.cross(x_dir)), a, x_dir)
        self._cache: list[tuple[float, _ArcCurve, Vector]] = []

    def _station(self, x: float) -> tuple[_ArcCurve, Vector]:
        for xs, cur, s in self._cache:  # ほぼ同じ x の断面線は共有する(上下対称の輪郭で半分になる)
            if abs(xs - x) <= self.tol_x:
                return cur, s
        s = self.meridian.point(x)
        t = self.meridian.tangent(x)
        nn = Vector(self.surface.normal_at(s))
        if nn.dot(self.n) < 0:
            nn = -nn
        y_dir = nn.cross(t)  # (X=t, Z=nn の右手系の +y)
        cur = _section_curve(self.surface, Plane(origin=s, z_dir=t), s, y_dir)
        self._cache.append((x, cur, s))
        return cur, s

    def __call__(self, x: float, y: float) -> Vector:
        cur, s = self._station(x)
        return s if abs(y) < 1e-12 else cur.point(y)


def _map_wire_section(mapper: _SectionMap, wire: Wire, step: float) -> tuple[Wire, list[float]]:
    runs = _sample_wire(wire, step)
    mapped: list[list[Vector]] = []
    for pts in runs:
        row = [mapper(q.X, q.Y) for q in pts]
        if mapped:
            row[0] = mapped[-1][-1]  # 辺の継ぎ目の点は共有する(辺が確実につながる)
        mapped.append(row)
    mapped[-1][-1] = mapped[0][0]  # 一周して閉じる
    edges = [Edge.make_spline(row) for row in mapped]
    ratios = [m.length / p.length for m, p in zip(edges, wire.order_edges())]
    return Wire(edges), ratios


def _wrap_section(
    surface: Face, blank: Face, frame: Plane, step: float, info: dict | None = None, grid: float = 4.0
) -> ShapeList[Face]:
    """長手(x)を子午線に沿って、幅(y)を断面線に沿って、元の長さに保つ貼り付け(``_SectionMap``)。

    輪郭の各点を (x, y) → 曲面上の点へ写し、辺ごとにスプラインで結ぶ。閉じ目の隙間は出ない。
    周の長さは保たないので、辺の長さの比は参考(警告しない)。
    """
    mapper = _SectionMap(surface, frame)
    outer, ratios = _map_wire_section(mapper, blank.outer_wire(), step)
    holes = [_map_wire_section(mapper, w, step) for w in blank.inner_wires()]
    if info is not None:
        info["edge_ratios"] = ratios
        info["perimeter_ratio"] = outer.length / blank.outer_wire().length
    inner_pts = [mapper(0.0, 0.0)]
    bb = blank.bounding_box()
    nx = max(2, math.ceil(bb.size.X / grid))
    ny = max(2, math.ceil(bb.size.Y / grid))
    for i in range(nx + 1):
        for j in range(ny + 1):
            q = Vector(bb.min.X + bb.size.X * i / nx, bb.min.Y + bb.size.Y * j / ny, 0)
            if q.length < 1e-6 or blank.distance_to(Vertex(*q)) > 1e-6:
                continue  # 基準点は追加済み。輪郭の外の点は使わない
            if blank.outer_wire().distance_to(Vertex(*q)) < 0.3:
                continue  # 輪郭上や極端に近い点は、境界と重なって面が張れない
            inner_pts.append(mapper(q.X, q.Y))
    face = Face.make_surface(outer, surface_points=inner_pts, interior_wires=[w for w, _ in holes])
    return ShapeList([-face if Vector(face.normal_at(frame.origin)).dot(frame.z_dir) < 0 else face])


def normal_curvature(surface: Face, point, direction) -> float:
    """曲面上の点で、接線方向 ``direction`` の法曲率の絶対値(1/mm)。オイラーの式 k1·cos²θ + k2·sin²θ。

    平面は 0。主曲率が定義できない点(尖点など)は 0 を返す。
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.gp import gp_Dir, gp_Pnt
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface

    p = Vector(point)
    uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(surface.wrapped)).ValueOfUV(gp_Pnt(p.X, p.Y, p.Z), 1e-6)
    props = BRepLProp_SLProps(BRepAdaptor_Surface(surface.wrapped), uv.X(), uv.Y(), 2, 1e-6)
    if not props.IsCurvatureDefined():
        return 0.0
    k1, k2 = props.MaxCurvature(), props.MinCurvature()
    if props.IsUmbilic():
        return abs(k1)
    d1, d2 = gp_Dir(), gp_Dir()
    props.CurvatureDirections(d1, d2)
    d = Vector(direction).normalized()
    c = d.dot(Vector(d1.X(), d1.Y(), d1.Z()))
    return abs(k1 * c * c + k2 * (1 - c * c))


def _section_setup(surface: Face, blank: Face, frame: Plane, params: SeatParams) -> tuple[Face, Plane, str]:
    """section の長手(子午線に沿う方向)を決め、必要ならブランクと座標系を 90° 回して、長手を x にそろえる。

    ``params.long_axis``: "x"・"y"(ブランクのその軸が長手)、"length"(外形が長い方)、
    "curvature"(曲率が小さい方)、"auto"(既定。外形が長い方。差が 15% 未満なら曲率が小さい方)。
    y を長手にするときは、ブランクを -90° 回し(旧 y → 新 x)、座標系の x を n × x_dir に取り直す。
    返り値は (ブランク, 座標系, 長手の軸 "x" か "y")。
    """
    mode = params.long_axis
    bb = blank.bounding_box()
    sx, sy = bb.size.X, bb.size.Y
    n, xd = Vector(frame.z_dir), Vector(frame.x_dir)
    yd = n.cross(xd)

    def by_length() -> str | None:
        if max(sx, sy) > 1.15 * min(sx, sy):
            return "x" if sx > sy else "y"
        return None

    def by_curvature() -> str:
        kx, ky = normal_curvature(surface, frame.origin, xd), normal_curvature(surface, frame.origin, yd)
        return "y" if ky < kx - 1e-9 else "x"

    if mode in ("x", "y"):
        axis = mode
    elif mode == "length":
        axis = by_length() or ("x" if sx >= sy else "y")
    elif mode == "curvature":
        axis = by_curvature()
    elif mode == "auto":
        axis = by_length() or by_curvature()
    else:
        raise ValueError(f"long_axis は 'auto' 'length' 'curvature' 'x' 'y' のどれか: {mode}")
    params.extra["long_axis"] = axis
    if axis == "x":
        return blank, frame, "x"
    frame2 = Plane(origin=frame.origin, x_dir=yd, z_dir=n)
    return blank.rotate(Axis.Z, -90), frame2, "y"


def _planar_width(blank: Face, x: float) -> float:
    """ブランクの、垂直線 x での幅(交点の y の最大 - 最小)。"""
    ys = []
    for e in blank.outer_wire().edges():
        pts = [e.position_at(i / 400) for i in range(401)]
        for a, b in itertools.pairwise(pts):
            if (a.X - x) * (b.X - x) <= 0 and a.X != b.X:
                ys.append(a.Y + (b.Y - a.Y) * (x - a.X) / (b.X - a.X))
    return max(ys) - min(ys) if len(ys) >= 2 else 0.0


def check_section_widths(
    surface: Face, blank: Face, faces: ShapeList[Face], params: SeatParams, n: int = 7
) -> list[tuple[float, float, float]]:
    """貼った面を、子午線上の n か所で断面の平面で切り、面上の弧長がブランクの幅と一致するか測る。

    (x, ブランクの幅, 面上の幅) のリストを返す。面から独立に測るので、貼り付けの検証になる。
    """
    frame = surface_frame(surface, params.point, params.x_dir)
    blank, frame, _ = _section_setup(surface, blank, frame, params)  # 貼ったときと同じ長手・座標系
    mapper = _SectionMap(surface, frame)
    bb = blank.bounding_box()
    out = []
    for i in range(1, n + 1):
        x = bb.min.X + bb.size.X * i / (n + 1)
        w0 = _planar_width(blank, x)
        s, t = mapper.meridian.point(x), mapper.meridian.tangent(x)
        w1 = 0.0
        for f in faces:
            sec = f.intersect(Plane(origin=s, z_dir=t))
            if sec is not None:
                w1 += sum(e.length for e in sec.edges())
        out.append((x, w0, w1))
    return out


def _rotated_blanks(blank: Face):
    """外周の始点(=wrap が輪郭を閉じる継ぎ目)を、辺ごとにずらしたブランクを順に返す。

    wrap は外周の最初と最後の辺を延長して交差させるので、継ぎ目の位置で成否と精度が変わる。
    基準点(原点)は、始点が原点でなくても保たれる(wrap が補助線で移る)。
    """
    edges = blank.outer_wire().order_edges()
    inner = blank.inner_wires()
    yield blank
    for k in range(1, len(edges)):
        yield Face(Wire(list(edges[k:]) + list(edges[:k])), inner)


def _wrap(surface: Face, blank: Face, frame: Plane, tol: float) -> Face:
    """許容誤差を緩めながら、継ぎ目をずらしながら wrap する。最初に成功したものを返す。"""
    last: Exception | None = None
    for cand in _rotated_blanks(blank):
        t = tol
        while t <= 0.8:
            try:
                return surface.wrap(cand, Location(frame), tolerance=t)
            except RuntimeError as e:  # 長さの許容誤差超え: 緩めて再試行
                last = e
                t *= 2
            except Exception as e:  # noqa: BLE001  OCC の失敗(継ぎ目の延長が交差しない等): 継ぎ目をずらす
                last = e
                break
    raise RuntimeError(f"wrap に失敗(許容誤差と継ぎ目を変えても不可): {last}")


def _normal_projection(surface: Face, blank: Face, frame: Plane, reach: float) -> ShapeList[Face]:
    n = frame.z_dir
    start = Plane(origin=frame.origin + n * reach, x_dir=frame.x_dir, z_dir=-n)
    placed = start.location * blank
    out = ShapeList()
    for f in placed.project_to_shape(surface, tuple(-n)):
        faces = f.faces() if not isinstance(f, Face) else [f]
        out.extend(faces)
    if not out:
        raise RuntimeError("投影で面ができない(輪郭が曲面の外にある)")
    # 基準点に近く、表側(法線が基準法線と同じ向き)の面だけを残す
    keep = ShapeList(
        f for f in out if f.normal_at(f.center()).dot(n) > 0 and f.distance_to(Vertex(*frame.origin)) < reach
    )
    if not keep:
        raise RuntimeError("表側の投影面が見つからない")
    return keep


def map_outline(surface: Face, outline: Face | Wire, params: SeatParams) -> ShapeList[Face]:
    """輪郭を曲面へマップし、曲面上の面(コピー)のリストを返す。

    ``wrap`` は 1 枚。``normal`` は、継ぎ目で分かれて複数枚になることがある。
    """
    if params.mode not in MODES:
        raise ValueError(f"mode は {MODES} のどれか: {params.mode}")
    blank = _as_face(outline)
    frame = surface_frame(surface, params.point, params.x_dir)
    if params.mode == "wrap":
        if params.wrap_method == "section":
            sblank, sframe, _ = _section_setup(surface, blank, frame, params)
            return _wrap_section(surface, sblank, sframe, params.step or 1.0, params.extra, params.fill_grid)
        if params.wrap_method == "march":
            return _wrap_march(
                surface, blank, frame, params.step or 0.5, params.extra, params.fill_grid, params.reproject
            )
        if params.wrap_method == "build123d":
            return ShapeList([_wrap(surface, blank, frame, params.tolerance)])
        raise ValueError(f"wrap_method は 'section' か 'march' か 'build123d': {params.wrap_method}")
    reach = surface.bounding_box().diagonal + 1.0
    return _normal_projection(surface, blank, frame, reach)


# ---------------------------------------------------------------- 厚み付け


def thicken_seat(faces: ShapeList[Face], params: SeatParams, normal: Vector) -> Solid | list[Solid]:
    """面を法線方向に厚み付けする。``outward`` で向きを固定(基準点の法線 ``normal`` に対して)。"""
    solids = []
    for f in faces:
        # thicken は正の厚みで面の法線側へ付く。面の向きがばらつくので、基準法線に合わせる。
        t = params.thickness if params.outward else -params.thickness
        sign = 1.0 if f.normal_at(f.center()).dot(normal) >= 0 else -1.0
        solids.append(Solid.thicken(f, t * sign))
    if len(solids) == 1:
        return solids[0]
    # 曲面の継ぎ目で面が分かれていたら、1 つのソリッドに融合する(できなければ list のまま)
    try:
        fused = solids[0].fuse(*solids[1:]).clean()
        out = fused.solids()
        if len(out) == 1 and out[0].is_valid:
            return out[0]
    except Exception as e:  # noqa: BLE001  OCC の融合失敗
        warnings.warn(f"継ぎ目で分かれたソリッドを融合できなかった({type(e).__name__})。list のまま返す", stacklevel=2)
    return solids


def make_seat(surface: Face, outline: Face | Wire, params: SeatParams) -> tuple[Solid | list[Solid], dict]:
    """マップ→厚み付け→検査を通しで行う。(ソリッド, 検査結果)を返す。"""
    frame = surface_frame(surface, params.point, params.x_dir)
    faces = map_outline(surface, outline, params)
    solid = thicken_seat(faces, params, frame.z_dir)
    report = check_mapping(outline, faces, params)
    # 張った面が元の曲面から浮いていないか(wrap の面は点列から張るので、曲面とのずれを測る)
    # position_at(u, v) は輪郭の外(面の定義域のはみ出し)の点も返すので、面の上にある点だけを使う。
    dev = 0.0
    for f in faces:
        pts = [f.position_at(i / 12, j / 12) for i in range(1, 12) for j in range(1, 12)]
        pts = [q for q in pts if f.distance_to(Vertex(*q)) < 1e-3]
        pts += [e.position_at(k / 10) for e in f.edges() for k in range(11)]
        dev = max([dev] + [surface.distance_to(Vertex(*q)) for q in pts])
    report["surface_dev"] = dev
    if params.mode == "wrap" and params.wrap_method == "section":
        widths = check_section_widths(surface, _as_face(outline), faces, params)
        report["widths"] = widths
        worst = max(abs(w1 - w0) for _, w0, w1 in widths)
        report["width_worst"] = worst
        if worst > params.width_tol:
            msg = f"断面の幅が元の幅から最大 {worst:.3f} mm ずれた(面が足りない、または断面が複数に分かれた)"
            report["warnings"].append(msg)
            warnings.warn(msg, stacklevel=2)
    if dev > 0.05:
        msg = f"座の面が元の曲面から最大 {dev:.3f} mm 浮いている"
        report["warnings"].append(msg)
        warnings.warn(msg, stacklevel=2)
    return solid, report


# ---------------------------------------------------------------- 検査


def check_mapping(outline: Face | Wire, faces: ShapeList[Face], params: SeatParams) -> dict:
    """ずれを測る。警告(``warnings.warn``)を出すだけで、止めない。

    - wrap: 外周の辺ごとの長さの比(マップ後/元)と、面積比。辺の順序は保たれる前提。
    - normal: 面積比(法線方向の投影では、傾いた面で面積が増えるのが普通)。
    """
    blank = _as_face(outline)
    area0 = blank.area
    area1 = sum(f.area for f in faces)
    rep: dict = {"mode": params.mode, "area_ratio": area1 / area0, "valid": all(f.is_valid for f in faces)}
    msgs: list[str] = []
    if params.mode == "wrap":
        e0 = [e.length for e in blank.outer_wire().edges()]
        e1 = [e.length for e in faces[0].outer_wire().edges()]
        ratios = params.extra.get("edge_ratios")  # march は投影し直しで辺が分かれるので、投影前の値を使う
        if ratios is None and len(e0) == len(e1):
            ratios = [b / a for a, b in zip(e0, e1)]
        if ratios is not None:
            rep["edge_ratios"] = ratios
            worst = max(abs(r - 1) for r in ratios)
            rep["edge_worst"] = worst
            if worst > params.warn_ratio and params.wrap_method != "section":  # section は周を保たない(参考値)
                msgs.append(f"辺の長さが最大 {worst:.1%} ずれた(閉じる辺で出やすい)")
    if abs(rep["area_ratio"] - 1) > params.warn_ratio:
        msgs.append(f"面積比 {rep['area_ratio']:.3f}(元の平面に対して)")
    if not rep["valid"]:
        msgs.append("面が不正(is_valid=False)")
    rep["warnings"] = msgs
    for m in msgs:
        warnings.warn(m, stacklevel=2)
    return rep


__all__ = [
    "SeatParams",
    "check_mapping",
    "make_seat",
    "map_outline",
    "outline_from_dxf",
    "outline_from_face",
    "surface_frame",
    "thicken_seat",
]
