"""頭管(bow)の、直線以外の中心線を、曲率が穏やかに変動する 1 本のスプラインにする(曲線論の自然方程式 κ(s))。

b1bow で作った方法を、どの頭管にも使えるよう一般化したもの(b1bow_spline.py は b1bow を指定して呼ぶ)。
対象は、中心線が「入口の直線、円弧、直線、円弧、円弧、出口の直線」の並びの頭管(b1bow・f1bow など。bows.BOWS)。

条件:
  ・入口と出口の 2 つの直線部(ピッチ)はそのまま。出口の直線は、入口と同じ向きの反対(+π 回って戻る)
  ・曲率 κ は +Z から見て反時計回りを正とし、入口側で負 → なめらかに正 → 出口、と変わる(振動しない)
  ・直線とは接線連続。曲率も連続にするため、直線との接続点で κ = 0
  ・今の形状に近づける。入口側の曲げは今より急にしない(κ1 ≥ -1/R1)
作り方: 今の曲率(区間ごとに一定、境目で不連続)の階段を、5 次のスムーズステップ(幅 W)でつなぐ。
  遷移でずれる「向きの変化」「終点」を厳密に満たすよう、区間の長さと曲率の値を、今の値からの変化が最小になるよう決める。
  得られた曲線(κ(s) の積分)を B スプライン(0.45 mm 間隔の点・次数 6・C2・許容 1e-5)にして、副法線を Z に固定して掃引する管
  (外径 12.8 / 内径 12.0)にする。Frenet フレームは変曲点で向きが反転するので使わない。
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

import bows

W_DEFAULT = 6.0
N = 2000  # 積分の分割数


def smooth(x):
    """5 次のスムーズステップ(0→1、両端で 1・2 階微分が 0)。"""
    x = np.clip(x, 0.0, 1.0)
    return x**3 * (10 - 15 * x + 6 * x**2)


@dataclass
class Cfg:
    name: str
    start: np.ndarray  # 入口の始端
    th0: float  # 入口の向き [rad]
    p0: np.ndarray  # スプラインの始点(入口の直線の終端)
    p1: np.ndarray  # スプラインの終点(出口の直線の始端)
    th1: float  # 終端の向き [rad]
    end: np.ndarray  # 出口の直線の終端
    L0: np.ndarray  # 今の各区間の長さ(円弧・直線)
    K0: np.ndarray  # 今の各区間の曲率(直線は 0、+ は左折)
    wire: object  # 今の中心線
    total: float
    l_in: float
    l_out: float

    @property
    def n(self):
        return len(self.L0)

    @property
    def arc(self):
        return self.K0 != 0.0

    @property
    def v0(self):
        return np.concatenate([self.L0, self.K0[self.arc]])

    @property
    def cap(self):
        """曲げは今より急にしない: 全体の最小曲げ半径(最大の |κ|)。"""
        return float(np.abs(self.K0).max())


def config(name: str) -> Cfg:
    """入口の直線 + 任意個の(円弧 / 直線)+ 出口の直線、の並びの頭管。"""
    d = bows.BOWS[name]
    segs = d["segs"]
    assert segs[0][0] == "L" and segs[-1][0] == "L"
    mid = segs[1:-1]
    wire, end, hend = bows.centerline(d["start"], d["heading"], segs)
    total = wire.length
    l_in, l_out = segs[0][1], segs[-1][1]
    p_at = lambda s: wire.position_at(s / total)
    q0, q1, qe = p_at(l_in), p_at(total - l_out), p_at(total)
    L0, K0, turn = [], [], 0.0
    for m in mid:
        if m[0] == "L":
            L0.append(m[1]); K0.append(0.0)
        else:
            _, r, a = m
            L0.append(r * math.radians(abs(a))); K0.append((1.0 if a > 0 else -1.0) / r); turn += a
    th0 = math.radians(d["heading"])
    return Cfg(name, np.array(d["start"]), th0, np.array([q0.X, q0.Y]), np.array([q1.X, q1.Y]), th0 + math.radians(turn),
               np.array([qe.X, qe.Y]), np.array(L0), np.array(K0), wire, total, l_in, l_out)


def unpack(cfg: Cfg, v):
    L = np.asarray(v[: cfg.n], float)
    K = np.zeros(cfg.n)
    K[cfg.arc] = v[cfg.n:]
    return L, K


def kappa(s, L, K, w):
    """各区間の曲率 K[j](長さ L[j])の階段を、境目ごとの 5 次スムーズステップ(幅 w)でつないだ κ(s)。
    入口で 0 → K[0]、出口で K[-1] → 0。"""
    b = np.cumsum(L)
    tot = b[-1]
    k = K[0] * smooth(s / w)
    for j in range(len(L) - 1):
        k = k + (K[j + 1] - K[j]) * smooth((s - (b[j] - w / 2)) / w)
    return k - K[-1] * smooth((s - (tot - w)) / w)


def length(v, cfg=None):
    return float(np.sum(v[: cfg.n])) if cfg is not None else float(np.sum(v))


def integrate(cfg: Cfg, v, w):
    L, K = unpack(cfg, v)
    tot = float(L.sum())
    s = np.linspace(0.0, tot, N + 1)
    k = kappa(s, L, K, w)
    ds = np.diff(s)
    th = cfg.th0 + np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * ds)])
    x = cfg.p0[0] + np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(th[1:]) + np.cos(th[:-1])) * ds)])
    y = cfg.p0[1] + np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(th[1:]) + np.sin(th[:-1])) * ds)])
    return s, k, th, np.stack([x, y], axis=1)


def reference_points(cfg: Cfg, step: float = 0.05):
    pts = []
    for s in np.arange(cfg.l_in, cfg.total - cfg.l_out + 1e-9, step):
        p = cfg.wire.position_at(s / cfg.total)
        pts.append((p.X, p.Y))
    return np.array(pts)


def separation(cfg: Cfg, xy, s_mid, n_leg=15, min_arc=25.0):
    """中心線(入口の直線 + スプライン(または今の中心線)+ 出口の直線)の、弧長で min_arc 以上離れた点どうしの最小間隔。
    管の外径(12.8)以上であれば、管は自分自身と重ならない。"""
    t = np.linspace(0, 1, n_leg)[:, None]
    leg_in = cfg.start + (cfg.p0 - cfg.start) * t
    leg_out = cfg.p1 + (cfg.end - cfg.p1) * t
    pts = np.vstack([leg_in, xy, leg_out])
    sl = np.concatenate([np.linspace(0, cfg.l_in, n_leg), cfg.l_in + s_mid, cfg.l_in + s_mid[-1] + np.linspace(0, cfg.l_out, n_leg)])
    D = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    m = np.abs(sl[:, None] - sl[None, :]) > min_arc
    return float(D[m].min())


def reference_separation(cfg: Cfg):
    ref = reference_points(cfg, 0.2)
    s = np.arange(len(ref)) * 0.2
    return separation(cfg, ref[::4], s[::4])


def solve(cfg: Cfg, w: float = W_DEFAULT, wshape: float = 0.3, gap: float | None = None):
    ref = reference_points(cfg)
    tree = cKDTree(ref)
    v0 = cfg.v0
    n = cfg.n
    scale = np.concatenate([np.maximum(cfg.L0, 10.0), np.abs(cfg.K0[cfg.arc])])
    # 管どうしの距離の下限(中心線の間隔)。gap を指定すると、表面どうしの最近接距離 gap(= 間隔 - 外径 12.8)以上にする。
    # 指定しなければ、今より近づけない(2 本の直線のピッチ 20 も上限)。
    sep_target = (bows.OD + gap + 0.01) if gap is not None else min(reference_separation(cfg), 20.0) - 0.05  # gap の 0.01 は、やわらかい罰則の分の余裕

    def resid(v):
        s, k, th, xy = integrate(cfg, v, w)
        c = np.concatenate([[(th[-1] - cfg.th1) * 1e5], (xy[-1] - cfg.p1) * 1e5])
        dv = (v - v0) / scale
        d1 = tree.query(xy[::8])[0] * wshape
        d2 = cKDTree(xy).query(ref[::40])[0] * wshape
        sep = separation(cfg, xy[::8], s[::8], n_leg=8)
        return np.concatenate([c, dv * 3.0, d1, d2, [max(0.0, sep_target - sep) * 300.0]])

    # 長さ: 円弧は今の 0.3〜3 倍、直線は 0〜max(3 倍, 30)。曲率: 同じ符号で、今の 0.2 倍〜(全体の最小曲げ半径 = cap)
    lo_L = np.where(cfg.arc, 0.3 * cfg.L0, 0.0)
    hi_L = np.where(cfg.arc, 3.0 * cfg.L0, np.maximum(3.0 * cfg.L0, 30.0))
    K0a = cfg.K0[cfg.arc]
    lo_K = np.where(K0a > 0, 0.2 * K0a, -cfg.cap)
    hi_K = np.where(K0a > 0, cfg.cap, 0.2 * K0a)
    r = least_squares(resid, v0, bounds=(np.concatenate([lo_L, lo_K]), np.concatenate([hi_L, hi_K])), x_scale=scale,
                      max_nfev=400, xtol=1e-12, ftol=1e-12)
    return r.x, ref


def analyze(cfg: Cfg, v, ref, w):
    s, k, th, xy = integrate(cfg, v, w)
    d_new = cKDTree(ref).query(xy)[0]
    d_old = cKDTree(xy).query(ref)[0]
    zeros = [float(s[i]) for i in np.where(np.diff(np.sign(k[5:-5])) != 0)[0] + 5]
    flat = s[np.abs(k) < 1e-6]
    flat_mid = flat[(flat > 0.1 * s[-1]) & (flat < 0.9 * s[-1])]
    return dict(L=float(s[-1]), end=xy[-1], end_th=math.degrees(th[-1] - cfg.th1), kmin=float(k.min()), kmax=float(k.max()),
                dmax=float(max(d_new.max(), d_old.max())), dmean=float(d_new.mean()), zeros=zeros,
                dk=float(np.abs(np.gradient(k, s)).max()), flat=(float(flat_mid[0]), float(flat_mid[-1])) if len(flat_mid) else None,
                sep=separation(cfg, xy[::4], s[::4]), s=s, k=k, xy=xy)


def spline_edge(cfg: Cfg, v, w=W_DEFAULT, n_pts=None):
    """κ(s) を積分した曲線(N+1 点)から、B スプライン曲線(次数 3〜6、C2、許容 1e-5)の辺を作る。"""
    from build123d import Edge
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Pnt

    s, k, th, xy = integrate(cfg, v, w)
    if n_pts is None:
        n_pts = max(300, int(s[-1] / 0.45))  # 点の間隔 0.45 mm 以下(長い頭管でも端の接線・曲率を精度よく合わせる)
    idx = np.linspace(0, N, n_pts + 1).astype(int)
    pts = xy[idx].copy()
    pts[0], pts[-1] = cfg.p0, cfg.p1  # 直線部と厳密につなぐ
    arr = Array1_gp_Pnt(1, len(pts))
    for i, (x, y) in enumerate(pts, start=1):
        arr.SetValue(i, gp_Pnt(float(x), float(y), 0.0))
    crv = GeomAPI_PointsToBSpline(arr, 3, 6, GeomAbs_Shape.GeomAbs_C2, 1e-5).Curve()
    return Edge(BRepBuilderAPI_MakeEdge(crv).Edge()), crv


def solid_volume(shape, eps=1e-9):
    """高精度の体積。build123d の .volume は B スプライン面で最大 0.1% ほどずれる。"""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    pr = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, pr, eps)
    return pr.Mass()


def planar_tube(wire, start, heading, r_out=bows.OD / 2, r_in=bows.ID / 2):
    """平面(XY)内の経路に沿った管。副法線を Z に固定して掃引する(経路に変曲点があっても管がねじれない)。"""
    from build123d import Plane, Solid, Wire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.gp import gp_Dir

    def one(r):
        circ = Wire.make_circle(r, Plane(origin=start, z_dir=heading))
        ps = BRepOffsetAPI_MakePipeShell(wire.wrapped)
        ps.SetMode(gp_Dir(0, 0, 1))
        ps.Add(circ.wrapped)
        ps.Build()
        ps.MakeSolid()
        return Solid(ps.Shape())

    return one(r_out) - one(r_in)


def bow_spline(name: str, w: float = W_DEFAULT, gap: float | None = None):
    """戻り値: (管のソリッド, cfg, v, ref, スプライン曲線, 中心線の Wire)。"""
    from build123d import Edge, Vector, Wire

    cfg = config(name)
    v, ref = solve(cfg, w, gap=gap)
    e2, crv = spline_edge(cfg, v, w)
    e1 = Edge.make_line((cfg.start[0], cfg.start[1], 0), (cfg.p0[0], cfg.p0[1], 0))
    e3 = Edge.make_line((cfg.p1[0], cfg.p1[1], 0), (cfg.end[0], cfg.end[1], 0))
    wire = Wire([e1, e2, e3])
    h = Vector(math.cos(cfg.th0), math.sin(cfg.th0), 0)
    return planar_tube(wire, Vector(cfg.start[0], cfg.start[1], 0), h), cfg, v, ref, crv, wire


def curve_ends(crv):
    from OCP.GeomLProp import GeomLProp_CLProps

    out = []
    for u in (crv.FirstParameter(), crv.LastParameter()):
        pr = GeomLProp_CLProps(crv, u, 2, 1e-9)
        t = pr.D1()
        out.append((math.degrees(math.atan2(t.Y(), t.X())), pr.Curvature()))
    return out


def report(name: str, w: float = W_DEFAULT, show_viewer: bool = True, gap: float | None = None):
    solid, cfg, v, ref, crv, wire = bow_spline(name, w, gap)
    a = analyze(cfg, v, ref, w)
    old = bows.bow(name)
    if show_viewer:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(old, solid, names=[f"{name}_old", f"{name}_spline"], alphas=[0.25, 1.0], colors=["gray", None], reset_camera=Camera.KEEP)
    legs = cfg.l_in + cfg.l_out
    print(f"{name} W={w}: valid={solid.is_valid} 体積(高精度)={solid_volume(solid):.2f} [build123d {solid.volume:.2f}] (期待 π(6.4²-6²)·({legs:g}+{a['L']:.3f})={math.pi * (6.4**2 - 6**2) * (legs + a['L']):.2f})")
    Ln, Kn = unpack(cfg, v)
    print("今の値   長さ =", np.round(cfg.L0, 3), " κ =", np.round(cfg.K0, 5))
    print("新しい値 長さ =", np.round(Ln, 3), " κ =", np.round(Kn, 5), " (半径 %s)" % np.round(1 / np.where(np.abs(Kn) > 1e-9, np.abs(Kn), np.nan), 2))
    (t0, k0), (t1, k1) = curve_ends(crv)
    print("終点誤差 %.1e 向き誤差 %+.1e° / スプライン端: 始端の接線 %.4f°(入口 %.1f°)曲率 %.1e / 終端の接線 %.4f°(出口 %.1f°)曲率 %.1e" % (
        float(np.hypot(*(a["end"] - cfg.p1))), a["end_th"], t0, math.degrees(cfg.th0), k0, t1, math.degrees(cfg.th1), k1))
    print("κ 最小 %.4f(R=%.2f) 最大 %.4f(R=%.2f) / κ=0 の平らな区間 %s / |dκ/ds| 最大 %.4f" % (
        a["kmin"], 1 / abs(a["kmin"]), a["kmax"], 1 / a["kmax"], None if a["flat"] is None else "s=[%.2f,%.2f]" % a["flat"], a["dk"]))
    bb, bo = solid.bounding_box(), old.bounding_box()
    print("今の形との距離: 最大 %.3f 平均 %.3f" % (a["dmax"], a["dmean"]))
    print("外形 新 x[%.1f,%.1f] y[%.1f,%.1f] / 旧 x[%.1f,%.1f] y[%.1f,%.1f]" % (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bo.min.X, bo.max.X, bo.min.Y, bo.max.Y))
    print("弧長で離れた中心線間隔の最小: 新 %.3f / 旧 %.3f(外径 12.8 以上なら管が重ならない。2 本の直線のピッチ 20 が上限)" % (a["sep"], reference_separation(cfg)))
    print("自分自身との表面最近接距離(= 間隔 - 12.8): 新 %.3f / 旧 %.3f" % (a["sep"] - bows.OD, reference_separation(cfg) - bows.OD))
    return solid, cfg, v


if __name__ == "__main__":
    import sys

    # 使い方: bow_spline.py 名前 [W] [表面最近接距離 gap]
    report(sys.argv[1] if len(sys.argv) > 1 else "b1bow", float(sys.argv[2]) if len(sys.argv) > 2 else W_DEFAULT,
           gap=float(sys.argv[3]) if len(sys.argv) > 3 else None)
