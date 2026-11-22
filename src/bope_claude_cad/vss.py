"""可変断面スイープ(芯線に沿って円断面の直径が変わる管)。

入力
- 芯線: build123d の Wire(平面でも3次元でもよい。始点が L=0)。
- 表: 芯線に沿った距離 L と直径 D の組(CSV または配列)。

規則
- 表の L を3次スプラインで当てはめ、任意の L の直径を内挿する(粗い表でも滑らかにする)。
- 表が芯線より長い: 芯線の終点までで切る(終点の直径は、スプラインで内挿)。
- 表が芯線より短い: 表の最後の L でモデル化を終える(外挿しない)。
- 法則が D = f(x) の関数形のとき: x = L として ``table_from_function(f, 0, 芯線の長さ)`` で表にする。

モデル化
- ``variable_pipe_law``(本線): MakePipeShell + 法則関数。誤差が小さく、断面間隔の調整が不要。
- ``variable_pipe``(比較用)は、芯線に垂直な円断面を多数置き、``Solid.make_loft`` で滑らかに通す。
- 断面の間隔は ``ds``(mm)。粗いと膨らみ・うねりが出るので、``check_variable_pipe`` で
  中間位置の直径誤差を測って決める。
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from build123d import (
    Circle,
    Plane,
    Shell,
    Solid,
    Vector,
    Wire,
)
from OCP.BRepOffset import BRepOffset_Skin
from OCP.BRepOffsetAPI import (
    BRepOffsetAPI_MakeOffsetShape,
    BRepOffsetAPI_MakePipeShell,
    BRepOffsetAPI_ThruSections,
)
from OCP.GeomAbs import GeomAbs_Arc
from OCP.gp import gp_Dir
from OCP.Law import Law_BSpFunc, Law_BSpline
from OCP.OCP.collections import Array1_double, Array1_int
from scipy.interpolate import CubicSpline, make_interp_spline


@dataclass(frozen=True)
class DiameterProfile:
    """L → D のスプライン。``l_end`` は、モデル化する終点の L(表と芯線の短いほう)。"""

    spline: CubicSpline
    l_table_min: float
    l_table_max: float
    l_end: float

    def __call__(self, length) -> np.ndarray:
        return self.spline(np.asarray(length, dtype=float))


def read_ld_csv(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """L,D の CSV(ヘッダ行は任意)を読む。UTF-8。"""
    ls, ds = [], []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                ls.append(float(row[0]))
                ds.append(float(row[1]))
            except ValueError:
                continue
    return np.array(ls), np.array(ds)


_EXPR_NAMES = {
    k: getattr(np, k)
    for k in (
        "sin", "cos", "tan", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
        "exp", "log", "log10", "sqrt", "abs", "minimum", "maximum", "power", "pi", "e",
    )
}  # fmt: skip
_EXPR_NAMES["ln"] = np.log


def table_from_function(
    func, l_min: float, l_max: float, step: float = 5.0
) -> tuple[np.ndarray, np.ndarray]:
    """法則が D = f(x) の関数形で与えられたとき、L-D 表(L = x)に変換する。

    ``func`` は、x(= L, mm)を受けて D(mm)を返す Python の関数、または式の文字列
    (例: ``"D = 40 - 0.05*x"``、``"20 + 30*exp(-x/200)"``。左辺の ``D =`` は省略可、
    べき乗は ``**`` か ``^``、使える関数は numpy の sin/cos/exp/log/sqrt など)。
    ``[l_min, l_max]`` を間隔 ``step`` 以下で等分した点で評価する。
    戻り値の表は、そのまま ``variable_pipe_law`` などに渡せる(3次スプラインで内挿される)。
    定義域外で値が有限でない(0 割り、負の平方根など)ときは ValueError。
    """
    if isinstance(func, str):
        expr = func.split("=", 1)[1] if "=" in func else func
        expr = expr.replace("^", "**").strip()
        code = compile(expr, "<D=f(x)>", "eval")

        def f(x):
            return eval(code, {"__builtins__": {}}, {**_EXPR_NAMES, "x": x, "L": x})
    else:
        f = func
    n = max(21, math.ceil((l_max - l_min) / step) + 1)
    ls = np.linspace(l_min, l_max, n)
    try:
        ds = np.asarray(f(ls), dtype=float)
    except (TypeError, ValueError):  # スカラー専用の関数(配列を受けられない)
        ds = np.array([float(f(float(v))) for v in ls])
    ds = np.broadcast_to(ds, ls.shape).astype(float)  # 定数式は全点に広げる
    if not np.all(np.isfinite(ds)) or np.any(ds <= 0):
        bad = ls[~np.isfinite(ds) | (ds <= 0)]
        raise ValueError(f"D が有限の正値でない L がある(例: L={bad[0]:.3f})")
    return ls, ds


def fit_profile(
    lengths, diameters, centerline_length: float
) -> DiameterProfile:
    """L-D 表をスプラインに当てはめ、終点 ``l_end`` を決める。"""
    order = np.argsort(lengths)
    ls = np.asarray(lengths, dtype=float)[order]
    ds = np.asarray(diameters, dtype=float)[order]
    keep = np.concatenate([[True], np.diff(ls) > 1e-9])  # 同じ L の重複を除く
    ls, ds = ls[keep], ds[keep]
    spline = CubicSpline(ls, ds, bc_type="not-a-knot")
    return DiameterProfile(
        spline=spline,
        l_table_min=float(ls[0]),
        l_table_max=float(ls[-1]),
        l_end=float(min(ls[-1], centerline_length)),
    )


def station_lengths(l_start: float, l_end: float, ds: float) -> np.ndarray:
    """L_start..L_end を、間隔 ds 以下で等分した断面位置。"""
    n = max(2, math.ceil((l_end - l_start) / ds) + 1)
    return np.linspace(l_start, l_end, n)


def _frame(wire: Wire, length: float) -> tuple[Vector, Vector]:
    t = min(max(length / wire.length, 0.0), 1.0)
    return wire.position_at(t), wire.tangent_at(t)


def _circle_wire(center: Vector, tangent: Vector, diameter: float) -> Wire:
    plane = Plane(origin=center, z_dir=tangent)
    return Wire(Circle(diameter / 2).wire().moved(plane.location))


def variable_pipe(
    centerline: Wire,
    lengths,
    diameters,
    ds: float = 4.0,
) -> tuple[Solid, DiameterProfile, np.ndarray]:
    """芯線と L-D 表から、可変直径の管ソリッドを作る。

    戻り値: (ソリッド, 直径プロファイル, 断面位置の L 配列)
    """
    prof = fit_profile(lengths, diameters, centerline.length)
    l_start = max(0.0, prof.l_table_min)
    ls = station_lengths(l_start, prof.l_end, ds)
    wires = []
    for s, d in zip(ls, prof(ls)):
        c, t = _frame(centerline, float(s))
        wires.append(_circle_wire(c, t, float(d)))
    solid = Solid.make_loft(wires, ruled=False)
    return solid, prof, ls


def variable_pipe_law(
    centerline: Wire,
    lengths,
    diameters,
    binormal=None,
    tol: float | None = None,
    max_degree: int | None = None,
    max_segments: int | None = None,
    solid: bool = False,
) -> tuple[Solid | Shell, DiameterProfile]:
    """本線。OCC の MakePipeShell に、直径の法則関数(L→D/D0 の B-スプライン)を渡して掃引する。

    断面は始点の円1つだけで、法則関数が芯線の長さ(曲線座標 L)に沿って拡縮する。
    法則関数の節点は表の L そのものなので、``fit_profile`` のスプラインと一致する。
    ``binormal`` の既定は None で、補正フレネル(SetMode(False))。平面でも3次元でも使える
    (断面が円なので、断面のねじれは形に影響しない)。方向ベクトルを渡すと、その向きに
    副法線を固定する(SetMode(gp_Dir))が、芯線が1つの平面にないと破綻する
    (直線+別平面の2円弧で、体積比0.60・直径誤差14mm)。
    """
    prof = fit_profile(lengths, diameters, centerline.length)
    nodes = prof.spline.x
    nodes = np.append(nodes[nodes < prof.l_end - 1e-6], prof.l_end)
    nodes = nodes[nodes >= prof.l_table_min]
    d0 = float(prof(nodes[0]))
    # 芯線を [表の最初の L, 終点] に切り詰める。MakePipeShell は法則関数の定義域を、掃引する
    # 芯線の全長に割り当てるので、切り詰めないと、短い表・途中から始まる表で形が引き伸ばされる。
    l0, l1 = float(nodes[0]), float(nodes[-1])
    spine = centerline
    # 許容差は 1e-4 mm。1e-9 だと、表の終わりと芯線の長さの数値誤差(1e-5 mm 程度)でも切り詰めが走り、
    # 複数の辺(スプライン・円弧・直線)からなる芯線では、その切り詰めの後の MakePipeShell が落ちた。
    if l0 > 1e-4 or l1 < centerline.length - 1e-4:
        spine = centerline.trim(l0 / centerline.length, l1 / centerline.length)
    nodes = nodes - l0  # 法則関数の変数は、切り詰めた芯線の始点からの距離
    bs = make_interp_spline(nodes, prof(nodes + l0) / d0, k=3)
    knots = np.unique(bs.t)
    mult = [int((bs.t == k).sum()) for k in knots]
    poles = Array1_double(1, len(bs.c))
    kn = Array1_double(1, len(knots))
    mu = Array1_int(1, len(knots))
    for i, v in enumerate(bs.c):
        poles.SetValue(i + 1, float(v))
    for i, (k, m) in enumerate(zip(knots, mult)):
        kn.SetValue(i + 1, float(k))
        mu.SetValue(i + 1, m)
    law = Law_BSpFunc(Law_BSpline(poles, kn, mu, 3), float(nodes[0]), float(nodes[-1]))
    c, t = _frame(spine, 0.0)
    profile = _circle_wire(c, t, d0)
    ps = BRepOffsetAPI_MakePipeShell(spine.wrapped)
    if binormal is None:
        ps.SetMode(False)
    else:
        ps.SetMode(gp_Dir(*binormal))
    ps.SetLaw(profile.wrapped, law, False, False)
    if tol is not None:
        ps.SetTolerance(tol, tol, 1e-4)
    if max_degree is not None:
        ps.SetMaxDegree(max_degree)
    if max_segments is not None:
        ps.SetMaxSegments(max_segments)
    ps.Build()
    if not ps.IsDone():
        raise RuntimeError("MakePipeShell failed")
    if solid:
        ps.MakeSolid()
        return Solid(ps.Shape()), prof
    # サーフェス: 側面だけのシェル(両端の端面なし。中身は詰まらない)
    return Shell(ps.Shape()), prof


def variable_pipe_wall(
    centerline: Wire, lengths, diameters, thickness: float, outward: bool = True,
    method: str = "join", **kw
) -> tuple[Solid, DiameterProfile]:
    """L-D 表の面(内径面)を、面に垂直に ``thickness`` だけ外側(または内側)へオフセットして、
    厚みを付けた管のソリッドを作る。

    手順: 内径面のシェルを開いたまま ``BRepOffsetAPI_MakeOffsetShape`` で法線方向にオフセットし、
    両端は、内外の縁を結ぶ面(``BRepFill.Face_s``)で閉じる。つまり端面は、面の法線方向で切れる
    (芯線に垂直な平面で切るのではない)。リムのように面が大きく傾いた所では、この差が効く。
    なお、閉じたソリッドの両端を開口にして ``offset``(MakeThickSolid)する方法は、端が
    芯線に垂直な平面で切れてしまうので使わない。``thicken`` を面ごとにかけて融合する方法も、
    融合が壊れる(ソリッドが割れる)ので使わない。

    ``method``:
    - ``"join"``(既定): ``MakeOffsetShape.PerformByJoin``。面どうしのつなぎを OCC が解くので遅い
      (渦巻きの1番管で 6 分以上)。外面は OffsetSurface なので、STEP には NURBS 変換が要る(これも遅い)。
    - ``"sweep"``: 外面を、法線方向のずれを補正した L'-D 表で、同じ芯線に沿ってもう一度掃引する
      (``_offset_sweep``)。直径に板厚の2倍を足しただけのスイープとは違い、法線方向の厚みになる。
      速く(数秒)、外面は最初から B-スプライン面。面ごとの OffsetSurface を B-スプライン面に近似する方法は、
      内径面の極が多い(1番管で 403)と近似が発散して使えなかった。
    """
    inner, prof = variable_pipe_law(centerline, lengths, diameters, **kw)
    if method == "sweep":
        outer = _offset_sweep(centerline, prof, thickness if outward else -thickness)
        return _close_wall(inner, outer), prof
    mo = BRepOffsetAPI_MakeOffsetShape()
    mo.PerformByJoin(
        inner.wrapped,
        thickness if outward else -thickness,
        1e-6,
        BRepOffset_Skin,
        False,
        False,
        GeomAbs_Arc,
    )
    if not mo.IsDone():
        raise RuntimeError("オフセットに失敗した")
    outer = Shell(mo.Shape())
    return _close_wall(inner, outer), prof


def _close_wall(inner: Shell, outer: Shell) -> Solid:
    """内面と外面のシェルの両端を、内外の縁を結ぶ面で閉じてソリッドにする。"""

    def rims(shell: Shell) -> list:
        # 1つの面にしか属さない閉じた縁(継ぎ目の線は閉じていないので除く)
        faces = shell.faces()
        return [
            e
            for e in shell.edges()
            if e.is_closed and sum(any(e.is_same(x) for x in f.edges()) for f in faces) == 1
        ]

    ri, ro = rims(inner), rims(outer)
    if len(ri) != 2 or len(ro) != 2:
        raise RuntimeError(f"端の縁が2つではない: 内 {len(ri)}、外 {len(ro)}")
    caps = []
    for ei in ri:
        eo = min(ro, key=lambda x: (x.center() - ei.center()).length)
        # 内外の縁の円を線織面で結ぶ。BRepFill.Face_s は2つの円の始点・向きをそろえないので、ずれると面が
        # ねじれて膨らむ(ベルの終端でドーム状になった)。ThruSections は CheckCompatibility でそろえる。
        ts = BRepOffsetAPI_ThruSections(False, True)
        ts.AddWire(Wire([ei]).wrapped)
        ts.AddWire(Wire([eo]).wrapped)
        ts.CheckCompatibility(True)
        ts.Build()
        if not ts.IsDone():
            raise RuntimeError("端の面を作れない")
        caps.append(Shell(ts.Shape()).faces()[0])
    wall = Solid(Shell(list(inner.faces()) + list(outer.faces()) + caps))
    if wall.volume < 0:
        wall = Solid(wall.wrapped.Reversed())
    return wall


def _offset_sweep(centerline: Wire, prof: DiameterProfile, dist: float, n: int = 4001, **kw) -> Shell:
    """内径面を法線方向に ``dist``(正は外向き)だけずらした面を、もう1つの可変断面スイープで作る。

    内径面の点 X(L, θ) = P(L) + r(L)·e(θ) の法線は、芯線の曲がりを無視すると (e - r'·T)/√(1+r'²)。
    これを ``dist`` だけ動かすと、芯線に垂直な断面の円のまま、
      位置 L' = L - dist·r'/√(1+r'²)、半径 r' = r + dist/√(1+r'²)
    になる(芯線が直線なら厳密。曲がりの影響は κ·r·r'·dist 程度で、ベルでは 0.01 mm 以下)。
    これを L'-D 表にして ``variable_pipe_law`` で掃引する。``variable_pipe_wall(method="sweep")`` 用。
    """
    ls = np.linspace(prof.l_table_min, prof.l_end, n)
    r = prof(ls) / 2
    dr = prof.spline(ls, 1) / 2
    k = np.sqrt(1 + dr**2)
    lo = ls - dist * dr / k
    ro = r + dist / k
    if np.any(np.diff(lo) <= 0):
        raise RuntimeError("オフセット後の L が単調でない(曲率が大きすぎる)")
    # 芯線の範囲 [0, 芯線の長さ] に収める(端のはみ出しは dist·r'/√(1+r'²) 程度)。
    # 切ったら、その端ちょうど(0 または芯線の長さ)の点を補間して足す。足さないと、外面が表の点の間隔だけ
    # 手前で終わり、端の面が斜めの帯になる(ベルの終端で 0.21 mm 手前になっていた)。
    keep = (lo >= 0) & (lo <= centerline.length)
    lk, rk = lo[keep], ro[keep]
    if lo[-1] > centerline.length and lk[-1] < centerline.length - 1e-9:
        lk = np.append(lk, centerline.length)
        rk = np.append(rk, np.interp(centerline.length, lo, ro))
    if lo[0] < 0 and lk[0] > 1e-9:
        lk = np.insert(lk, 0, 0.0)
        rk = np.insert(rk, 0, np.interp(0.0, lo, ro))
    outer, _ = variable_pipe_law(centerline, lk, 2 * rk, **kw)
    return outer


def check_variable_pipe(
    solid: Solid, centerline: Wire, prof: DiameterProfile, n: int = 40
) -> dict:
    """滑らかさ・精度の確認。

    - 体積: ∫π D²/4 dL(芯線が断面の図心を通るので、曲がりに関係なく一致する)との比。
    - 中間位置の断面で、等価直径(断面積から)と D(L) の差。
    """
    l0, l1 = prof.l_table_min, prof.l_end
    g = np.linspace(l0, l1, 20001)
    vol_ideal = float(np.trapezoid(math.pi * prof(g) ** 2 / 4, g))
    errs = []
    for s in np.linspace(l0 + 0.5, l1 - 0.5, n):
        c, t = _frame(centerline, float(s))
        plane = Plane(origin=c, z_dir=t)
        faces = solid.intersect(plane)  # 平面との共通部分(面)
        # 渦巻き状の芯線では、平面が別の枝も切る。芯線上の点に最も近い面だけを使う。
        fl = list(faces.faces()) if faces else []
        area = min(fl, key=lambda f: f.distance_to(c)).area if fl else 0.0
        d_eq = 2 * math.sqrt(area / math.pi) if area > 0 else float("nan")
        errs.append((float(s), d_eq - float(prof(s))))
    arr = np.array([e for _, e in errs])
    return {
        "is_valid": solid.is_valid,
        "volume": solid.volume,
        "volume_ideal": vol_ideal,
        "volume_ratio": solid.volume / vol_ideal,
        "dia_err_max": float(np.nanmax(np.abs(arr))),
        "dia_err_rms": float(np.sqrt(np.nanmean(arr**2))),
        "samples": errs,
    }
