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
  得られた曲線(κ(s) の積分)を B スプライン(300 点・次数 6・C2・許容 1e-5)にして、副法線を Z に固定して掃引する管
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
    v0: np.ndarray  # 今の値 (l1, l2, l3, l4, k1, k3, k4)
    wire: object  # 今の中心線
    total: float
    l_in: float
    l_out: float


def config(name: str) -> Cfg:
    d = bows.BOWS[name]
    segs = d["segs"]
    assert segs[0][0] == "L" and segs[-1][0] == "L"
    mid = segs[1:-1]
    assert [m[0] for m in mid] == ["A", "L", "A", "A"], f"{name}: 想定外の構成 {mid}"
    wire, end, hend = bows.centerline(d["start"], d["heading"], segs)
    total = wire.length
    l_in, l_out = segs[0][1], segs[-1][1]
    p_at = lambda s: wire.position_at(s / total)
    q0, q1, qe = p_at(l_in), p_at(total - l_out), p_at(total)
    (_, r1, a1), (_, ll), (_, r3, a3), (_, r4, a4) = mid[0], mid[1], mid[2], mid[3]
    sgn = lambda a: 1.0 if a > 0 else -1.0
    v0 = np.array([r1 * math.radians(abs(a1)), ll, r3 * math.radians(abs(a3)), r4 * math.radians(abs(a4)),
                   sgn(a1) / r1, sgn(a3) / r3, sgn(a4) / r4])
    th0 = math.radians(d["heading"])
    th1 = th0 + math.radians(a1 + a3 + a4)
    return Cfg(name, np.array(d["start"]), th0, np.array([q0.X, q0.Y]), np.array([q1.X, q1.Y]), th1,
               np.array([qe.X, qe.Y]), v0, wire, total, l_in, l_out)


def kappa(s, v, w):
    l1, l2, l3, l4, k1, k3, k4 = v
    b1, b2, b3 = l1, l1 + l2, l1 + l2 + l3
    L = b3 + l4
    return (
        k1 * smooth(s / w)  # 入口: 0 → κ1
        - k1 * smooth((s - (b1 - w / 2)) / w)  # κ1 → 0(直線)
        + k3 * smooth((s - (b2 - w / 2)) / w)  # 0 → κ3
        + (k4 - k3) * smooth((s - (b3 - w / 2)) / w)  # κ3 → κ4
        - k4 * smooth((s - (L - w)) / w)  # 出口: κ4 → 0
    )


def length(v):
    return float(v[0] + v[1] + v[2] + v[3])


def integrate(cfg: Cfg, v, w):
    L = length(v)
    s = np.linspace(0.0, L, N + 1)
    k = kappa(s, v, w)
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


def solve(cfg: Cfg, w: float = W_DEFAULT, wshape: float = 0.3):
    ref = reference_points(cfg)
    tree = cKDTree(ref)
    v0 = cfg.v0
    scale = np.array([v0[0], max(v0[1], 10.0), v0[2], v0[3], abs(v0[4]), abs(v0[5]), abs(v0[6])])

    def resid(v):
        s, k, th, xy = integrate(cfg, v, w)
        c = np.concatenate([[(th[-1] - cfg.th1) * 1e5], (xy[-1] - cfg.p1) * 1e5])
        dv = (v - v0) / scale
        d1 = tree.query(xy[::8])[0] * wshape
        d2 = cKDTree(xy).query(ref[::40])[0] * wshape
        return np.concatenate([c, dv * 3.0, d1, d2])

    # 曲げは今より急にしない: κ1 ≥ 今の κ1(R ≥ R1)。ほかは今の値の付近
    lo = np.array([0.3 * v0[0], 0.0, 0.4 * v0[2], 0.2 * v0[3], v0[4], 0.2 * v0[5], 0.2 * v0[6]])
    hi = np.array([3.0 * v0[0], max(3.0 * v0[1], 30.0), 2.0 * v0[2], 3.0 * v0[3], 0.2 * v0[4], 4.0 * v0[5], 4.0 * v0[6]])
    r = least_squares(resid, v0, bounds=(lo, hi), x_scale=scale, max_nfev=400, xtol=1e-12, ftol=1e-12)
    return r.x, ref


def analyze(cfg: Cfg, v, ref, w):
    s, k, th, xy = integrate(cfg, v, w)
    d_new = cKDTree(ref).query(xy)[0]
    d_old = cKDTree(xy).query(ref)[0]
    zeros = [float(s[i]) for i in np.where(np.diff(np.sign(k[5:-5])) != 0)[0] + 5]
    flat = s[np.abs(k) < 1e-6]
    flat_mid = flat[(flat > 0.1 * s[-1]) & (flat < 0.9 * s[-1])]
    return dict(L=length(v), end=xy[-1], end_th=math.degrees(th[-1] - cfg.th1), kmin=float(k.min()), kmax=float(k.max()),
                dmax=float(max(d_new.max(), d_old.max())), dmean=float(d_new.mean()), zeros=zeros,
                dk=float(np.abs(np.gradient(k, s)).max()), flat=(float(flat_mid[0]), float(flat_mid[-1])) if len(flat_mid) else None,
                s=s, k=k, xy=xy)


def spline_edge(cfg: Cfg, v, w=W_DEFAULT, n_pts=300):
    """κ(s) を積分した曲線(N+1 点)から、B スプライン曲線(次数 3〜6、C2、許容 1e-5)の辺を作る。"""
    from build123d import Edge
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Pnt

    s, k, th, xy = integrate(cfg, v, w)
    idx = np.linspace(0, N, n_pts + 1).astype(int)
    pts = xy[idx].copy()
    pts[0], pts[-1] = cfg.p0, cfg.p1  # 直線部と厳密につなぐ
    arr = Array1_gp_Pnt(1, len(pts))
    for i, (x, y) in enumerate(pts, start=1):
        arr.SetValue(i, gp_Pnt(float(x), float(y), 0.0))
    crv = GeomAPI_PointsToBSpline(arr, 3, 6, GeomAbs_Shape.GeomAbs_C2, 1e-5).Curve()
    return Edge(BRepBuilderAPI_MakeEdge(crv).Edge()), crv


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


def bow_spline(name: str, w: float = W_DEFAULT):
    """戻り値: (管のソリッド, cfg, v, ref, スプライン曲線, 中心線の Wire)。"""
    from build123d import Edge, Vector, Wire

    cfg = config(name)
    v, ref = solve(cfg, w)
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


def report(name: str, w: float = W_DEFAULT, show_viewer: bool = True):
    solid, cfg, v, ref, crv, wire = bow_spline(name, w)
    a = analyze(cfg, v, ref, w)
    old = bows.bow(name)
    if show_viewer:
        from ocp_vscode import Camera

        from bope_claude_cad.viewer import show

        show(old, solid, names=[f"{name}_old", f"{name}_spline"], alphas=[0.25, 1.0], colors=["gray", None], reset_camera=Camera.KEEP)
    legs = cfg.l_in + cfg.l_out
    print(f"{name} W={w}: valid={solid.is_valid} 体積={solid.volume:.2f} (期待 π(6.4²-6²)·({legs:g}+{a['L']:.3f})={math.pi * (6.4**2 - 6**2) * (legs + a['L']):.2f})")
    print("今の値   l1..l4 =", np.round(cfg.v0[:4], 3), " κ1,κ3,κ4 =", np.round(cfg.v0[4:], 5))
    print("新しい値 l1..l4 =", np.round(v[:4], 3), " κ1,κ3,κ4 =", np.round(v[4:], 5), " (半径 %s)" % np.round(1 / np.abs(v[4:]), 2))
    (t0, k0), (t1, k1) = curve_ends(crv)
    print("終点誤差 %.1e 向き誤差 %+.1e° / スプライン端: 始端の接線 %.4f°(入口 %.1f°)曲率 %.1e / 終端の接線 %.4f°(出口 %.1f°)曲率 %.1e" % (
        float(np.hypot(*(a["end"] - cfg.p1))), a["end_th"], t0, math.degrees(cfg.th0), k0, t1, math.degrees(cfg.th1), k1))
    print("κ 最小 %.4f(R=%.2f) 最大 %.4f(R=%.2f) / κ=0 の平らな区間 %s / |dκ/ds| 最大 %.4f" % (
        a["kmin"], 1 / abs(a["kmin"]), a["kmax"], 1 / a["kmax"], None if a["flat"] is None else "s=[%.2f,%.2f]" % a["flat"], a["dk"]))
    bb, bo = solid.bounding_box(), old.bounding_box()
    print("今の形との距離: 最大 %.3f 平均 %.3f" % (a["dmax"], a["dmean"]))
    print("外形 新 x[%.1f,%.1f] y[%.1f,%.1f] / 旧 x[%.1f,%.1f] y[%.1f,%.1f]" % (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bo.min.X, bo.max.X, bo.min.Y, bo.max.Y))
    pts = np.vstack([np.array([[cfg.start[0] + (cfg.p0[0] - cfg.start[0]) * t, cfg.start[1] + (cfg.p0[1] - cfg.start[1]) * t] for t in np.linspace(0, 1, 40)]),
                     a["xy"][::4],
                     np.array([[cfg.p1[0] + (cfg.end[0] - cfg.p1[0]) * t, cfg.p1[1] + (cfg.end[1] - cfg.p1[1]) * t] for t in np.linspace(0, 1, 150)])])
    sl = np.concatenate([np.linspace(0, cfg.l_in, 40), cfg.l_in + a["s"][::4], cfg.l_in + a["s"][-1] + np.linspace(0, cfg.l_out, 150)])
    D = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    m = np.abs(sl[:, None] - sl[None, :]) > 25.0
    print("弧長で離れた中心線間隔の最小 %.3f(外径 12.8 以上なら管が重ならない)" % D[m].min())
    return solid, cfg, v


if __name__ == "__main__":
    import sys

    report(sys.argv[1] if len(sys.argv) > 1 else "b1bow", float(sys.argv[2]) if len(sys.argv) > 2 else W_DEFAULT)
