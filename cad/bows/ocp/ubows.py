"""U 字の頭管(2 本の直線のピッチは任意。標準は 30 / 40 / 50 / 60)。12.8×12.0 のパイプ。
方針(頭管の中心線の方針。cad/bows/worklog.md の「方針」に一覧):
  ピッチ ≤ 30: 真円の半円。30 < ピッチ < 50: ピッチ 50 の曲線の相似形(2026-11-27)。ピッチ ≥ 50: 直線と曲率連続(G2)のスプライン(長円的)。最小曲げ半径はピッチに比例(40 で R15)、
  高さもピッチに応じて上がる(解がなければ自動で上げる)。設計値でなく、実際のスプライン曲線を測って最小曲げ半径を保証する。f2bow(ピッチ 20)も、直管の長さは 5(U 字系で統一)。

座標は f2bow と同じ: 管は XY 平面内。左の直線の始端 (-P/2, 0) から +Y 向きに長さ LEG の直管、キャップ(U の曲がり)、
右の直線に降りて (P/2, 0) で終わる。キャップの頂点は y = LEG + H。
  ピッチ 30: 真円の半円(R15)。直線とは曲率が不連続(0 → 1/15)。
  ピッチ 40 以上: 長円的なスプライン。直線(κ=0)から、なめらかに曲率が立ち上がり(5 次スムーズステップ、幅 W)、
    角の曲率 1/RC を保ってから、頂点側のゆるやかな曲率に移る。直線とは位置・接線・曲率が連続(G2)。左右対称。
    半分(直線の端 → 頂点)の κ(s) を解いて、折り返す。
解く未知数: 角の区間の長さ lc、頂点側の半分の長さ lt、頂点側の曲率 kt。条件は 3 つ
  (頂点で向きが水平 = 曲がりの合計が π/2、頂点の x = 0、頂点の高さ = LEG + H)。角の曲率 κc = 1/RC は決め打ち。
"""

import math

import numpy as np
from scipy.optimize import least_squares

import bows
from bow_spline import planar_tube, smooth, solid_volume

LEG = 5.0  # 直管の長さ(U 字系で統一。f2bow も 5)
RMIN_RATIO_50 = 21.6 / 50.0  # 2番管のピッチ 50 の形(最小 R 21.6 = ピッチの 0.432 倍、高さ 25.0)が基本(2026-11-24)。ピッチ 50 以上は、これを相対的に広げる(比例)
RMIN_RATIO_40 = 15.0 / 40.0  # ピッチ 40 以下は、この比(0.375)でないと解がない。40〜50 は線形に補間(SIMILAR_TO より狭いピッチは、2026-11-27 から使わない)
SIMILAR_TO = 50.0  # 2026-11-27: U_ARC_MAX < ピッチ < SIMILAR_TO は、ピッチ 50 の曲線を P/50 倍した相似形(直線 LEG はそのまま)。狭いピッチで角ばらないように
RMIN_40 = RMIN_RATIO_40 * 40.0  # 互換のため
H_RATIO = 0.5  # 高さの初期値 = ピッチ × この比(解がなければ 0.5 ずつ上げる)


def rmin_ratio(pitch: float) -> float:
    t = min(max((pitch - 40.0) / 10.0, 0.0), 1.0)
    return RMIN_RATIO_40 + (RMIN_RATIO_50 - RMIN_RATIO_40) * t


def rmin_for(pitch: float) -> float:
    """最小曲げ半径: ピッチ 50 で R21.6(2番管の基本)、50 以上はピッチに比例して広げる(60 で R25.92)。40 以下は比 0.375(40 で R15)、40〜50 は補間。"""
    return rmin_ratio(pitch) * pitch


def h_for(pitch: float) -> float:
    """高さの初期値(解がなければ 0.5 ずつ上げる)。"""
    return H_RATIO * pitch * rmin_ratio(pitch) / RMIN_RATIO_50


U_ARC_MAX = 30.0  # このピッチ以下は、真円の半円(R = ピッチ/2)。これより広いピッチは、スプライン(長円的)
RMIN = RMIN_40
RC = RMIN  # 互換のため
W = 6.0  # 曲率の遷移の幅
H_DEFAULT = 15.0  # キャップの高さ(直線の端から頂点まで)。ピッチ 30 の半円と同じ(仮の値)
N = 2000


def _half(params, pitch, rc, w):
    """半分(直線の端 → 頂点)の κ(s)(曲がりの大きさ、右折)を積分する。戻り値: s, k, 点列 (x, y)、向き。"""
    lc, lt, kt = params
    S = lc + lt
    s = np.linspace(0.0, S, N + 1)
    kc = 1.0 / rc
    k = kc * smooth(s / w) + (kt - kc) * smooth((s - (lc - w / 2)) / w)
    ds = np.diff(s)
    th = math.pi / 2 - np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * ds)])
    x = -pitch / 2 + np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(th[1:]) + np.cos(th[:-1])) * ds)])
    y = LEG + np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(th[1:]) + np.sin(th[:-1])) * ds)])
    return s, k, np.stack([x, y], axis=1), th


def solve_half(pitch, h, rc=RC, w=W):
    # 初期値: 角の円弧(R_c, 角度 α)+ 頂点側の円弧(R_t)で、同じ幅と高さを満たす幾何の解
    def geom(p):
        a, rt = p
        return [rc * (1 - math.cos(a)) + rt * math.cos(a) - pitch / 2, rc * math.sin(a) + rt * (1 - math.sin(a)) - h]

    g = least_squares(geom, [1.0, pitch / 2], bounds=([0.05, rc], [math.pi / 2 - 0.01, 1e4]))
    a, rt = g.x
    x0 = np.array([rc * a, rt * (math.pi - 2 * a) / 2, 1.0 / rt])

    def resid(p):
        s, k, xy, th = _half(p, pitch, rc, w)
        return [(np.trapezoid(k, s) - math.pi / 2) * 1e4, xy[-1, 0] * 1e4, (xy[-1, 1] - (LEG + h)) * 1e4]

    r = least_squares(resid, x0, bounds=([1.0, 1.0, 1e-4], [200, 400, 1.0 / rc]), x_scale=[10, 10, 0.01], xtol=1e-14, ftol=1e-14, max_nfev=400)
    res = float(np.max(np.abs(resid(r.x))))
    if res > 1e-2:
        raise ValueError(f"解なし(残差 {res:.2e}): pitch={pitch} h={h} rc={rc}")
    return r.x, (a, rt)


def curve_points(pitch, h, rc=RC):
    """全体(左の直線の端 → 頂点 → 右の直線の端)の点列と、κ(s)(右折を負)。"""
    p, (a, rt) = solve_half(pitch, h, rc)
    s, k, xy, th = _half(p, pitch, rc, W)
    pts = np.vstack([xy, np.stack([-xy[-2::-1, 0], xy[-2::-1, 1]], axis=1)])
    ss = np.concatenate([s, s[-1] + (s[-1] - s[-2::-1])])
    kk = -np.concatenate([k, k[-2::-1]])
    return pts, ss, kk, p, (a, rt)


def _spline(pitch, h, rc):
    """点列 → B スプライン曲線(0.45 mm 間隔、次数 3〜6、C2、許容 1e-5)。戻り値: (曲線, 点列, s, κ, 解, 幾何の解)。"""
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Pnt

    pts, ss, kk, p, geo = curve_points(pitch, h, rc)
    n_pts = max(300, int(ss[-1] / 0.45))
    idx = np.linspace(0, len(pts) - 1, n_pts + 1).astype(int)
    q = pts[idx].copy()
    q[0], q[-1] = (-pitch / 2, LEG), (pitch / 2, LEG)
    arr = Array1_gp_Pnt(1, len(q))
    for i, (x, y) in enumerate(q, start=1):
        arr.SetValue(i, gp_Pnt(float(x), float(y), 0.0))
    crv = GeomAPI_PointsToBSpline(arr, 3, 6, GeomAbs_Shape.GeomAbs_C2, 1e-5).Curve()
    return crv, pts, ss, kk, p, geo


def spline_kmax(crv, n=3000):
    """実際のスプライン曲線の、曲率の最大(曲線を直接測る)。"""
    from OCP.GeomLProp import GeomLProp_CLProps

    u0, u1 = crv.FirstParameter(), crv.LastParameter()
    return max(GeomLProp_CLProps(crv, u, 2, 1e-9).Curvature() for u in np.linspace(u0, u1, n))


def u_bow(pitch: float, h: float | None = None, rmin: float | None = None):
    """戻り値: (管のソリッド, 情報の dict)。ピッチ 30 は真円の半円、40 以上はスプライン。
    スプラインの最小曲げ半径(実際の曲線の曲率の最大の逆数)を rmin 以上にする: 設計の角の半径 rc に余裕を持たせ、
    実際の曲線が rmin を下回れば rc を大きくしてやり直す。解がなければ高さ h を 0.5 ずつ上げる。"""
    from build123d import BuildLine, CenterArc, Edge, Line, Vector, Wire
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge

    P = float(pitch)
    assert P > 2 * 6.4, "ピッチは管の外径(12.8)より大きく"
    if U_ARC_MAX + 1e-9 < P < SIMILAR_TO - 1e-9 and h is None and rmin is None:
        return _similar(P)
    h = h_for(P) if h is None else h
    rmin = rmin_for(P) if rmin is None else rmin
    if P <= U_ARC_MAX + 1e-9:
        with BuildLine() as bl:
            Line((-P / 2, 0), (-P / 2, LEG))
            CenterArc((0, LEG), P / 2, 180.0, -180.0)
            Line((P / 2, LEG), (P / 2, 0))
        wire = bl.wire()
        info = dict(kind="arc", curve_len=math.pi * P / 2, h=P / 2, kmax=2 / P, rmin=P / 2, rc=P / 2, h_req=P / 2)
    else:
        rc, hh = rmin, h
        crv = None
        for _ in range(40):
            try:
                crv, pts, ss, kk, p, geo = _spline(P, hh, rc)
            except ValueError:
                hh += 0.5  # 解がないので、高さを上げる
                continue
            km = spline_kmax(crv)
            if km <= 1.0 / rmin:
                break
            rc *= km * rmin * 1.0005  # 実際の曲率が rmin を超えた分だけ、設計の半径を大きくする
        else:
            raise RuntimeError("最小曲げ半径を満たす解が見つからない")
        e2 = Edge(BRepBuilderAPI_MakeEdge(crv).Edge())
        wire = Wire([Edge.make_line((-P / 2, 0, 0), (-P / 2, LEG, 0)), e2, Edge.make_line((P / 2, LEG, 0), (P / 2, 0, 0))])
        info = dict(kind="spline", curve_len=float(ss[-1]), h=float(pts[:, 1].max() - LEG), h_req=h, kmax=float(km), rmin=float(1 / km),
                    rc=rc, params=p, geom=geo, s=ss, k=kk, pts=pts, crv=crv, apex_y=float(pts[:, 1].max()))
    solid = planar_tube(wire, Vector(-P / 2, 0, 0), Vector(0, 1, 0))
    return solid, info


def _similar(P):
    """ピッチ SIMILAR_TO の曲線(直線の端 → 頂点 → 直線の端)を、直線の端を基準に P/SIMILAR_TO 倍した相似形の U(2026-11-27)。
    曲率は SIMILAR_TO/P 倍(最小曲げ半径 21.61·P/50、高さ 25·P/50)。直線 LEG は 5 のまま。"""
    from build123d import Edge, Vector, Wire
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Pnt

    _, base = u_bow(SIMILAR_TO)
    f = P / SIMILAR_TO
    pts = np.column_stack([base["pts"][:, 0] * f, LEG + (base["pts"][:, 1] - LEG) * f])
    ss, kk = base["s"] * f, base["k"] / f
    n_pts = max(300, int(ss[-1] / 0.45))
    idx = np.linspace(0, len(pts) - 1, n_pts + 1).astype(int)
    q = pts[idx].copy()
    q[0], q[-1] = (-P / 2, LEG), (P / 2, LEG)
    arr = Array1_gp_Pnt(1, len(q))
    for i, (x, y) in enumerate(q, start=1):
        arr.SetValue(i, gp_Pnt(float(x), float(y), 0.0))
    crv = GeomAPI_PointsToBSpline(arr, 3, 6, GeomAbs_Shape.GeomAbs_C2, 1e-5).Curve()
    km = spline_kmax(crv)
    e2 = Edge(BRepBuilderAPI_MakeEdge(crv).Edge())
    wire = Wire([Edge.make_line((-P / 2, 0, 0), (-P / 2, LEG, 0)), e2, Edge.make_line((P / 2, LEG, 0), (P / 2, 0, 0))])
    info = dict(kind="similar", curve_len=float(ss[-1]), h=float(pts[:, 1].max() - LEG), h_req=base["h"] * f, kmax=float(km), rmin=float(1 / km),
                rc=base["rc"] * f, params=None, geom=None, s=ss, k=kk, pts=pts, crv=crv, apex_y=float(pts[:, 1].max()), scale=f)
    solid = planar_tube(wire, Vector(-P / 2, 0, 0), Vector(0, 1, 0))
    return solid, info


def curve_ends(crv):
    from OCP.GeomLProp import GeomLProp_CLProps

    out = []
    for u in (crv.FirstParameter(), crv.LastParameter()):
        pr = GeomLProp_CLProps(crv, u, 2, 1e-9)
        t = pr.D1()
        out.append((math.degrees(math.atan2(t.Y(), t.X())), pr.Curvature()))
    return out


def main(h: float | None = None):
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    pitches = [30, 40, 50, 60]
    parts, names, x = [], [], 0.0
    f2 = bows.bow("f2bow")  # 参考(ピッチ 20、直管 5)
    bb = f2.bounding_box()
    parts.append(Pos(-bb.min.X, 0, 0) * f2)
    names.append("f2bow")
    x += bb.size.X + 15
    for P in pitches:
        solid, info = u_bow(P, h)
        bb = solid.bounding_box()
        parts.append(Pos(x - bb.min.X, 0, 0) * solid)
        names.append(f"u_bow_{P}")
        x += bb.size.X + 15
        expected = math.pi * (6.4**2 - 6.0**2) * (2 * LEG + info["curve_len"])
        line = f"ピッチ {P}: {info['kind']} valid={solid.is_valid} 体積(高精度)={solid_volume(solid):.2f}(期待 {expected:.2f}) 曲線の長さ {info['curve_len']:.3f} 高さ H={info['h']:.3f}(指定 {info['h_req']:g}) 最小曲げ半径(実際の曲線)R{info['rmin']:.3f} 設計の角の半径 {info['rc']:.3f}"
        if info["kind"] == "spline":
            (t0, k0), (t1, k1) = curve_ends(info["crv"])
            lc, lt, kt = info["params"]
            line += f" | 角 lc={lc:.2f} 頂点側(半分)lt={lt:.2f} 頂点の曲率 kt={kt:.4f}(R{1 / kt:.1f}) | 端: 接線 {t0:.4f}°/{t1:.4f}°(90/-90)曲率 {k0:.1e}/{k1:.1e}"
        bbx = solid.bounding_box()
        line += f" | 外形 x[{bbx.min.X:.1f},{bbx.max.X:.1f}] y[{bbx.min.Y:.1f},{bbx.max.Y:.1f}]"
        print(line)
    show(*parts, names=names, reset_camera=Camera.KEEP)


if __name__ == "__main__":
    import sys

    main(float(sys.argv[1]) if len(sys.argv) > 1 else None)
