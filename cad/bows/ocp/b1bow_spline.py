"""b1bow のアレンジ: 2 つの直線部(ピッチ 20)はそのままに、直線以外の中心線を 1 本のスプラインにする。

曲線論(自然方程式 κ(s))で作る:
  今の形状の曲率は、区間ごとに一定で、境目で不連続:
    R12 の右折(κ1 = -1/12)→ 直線(0)→ R22.1729 の左折(κ3 = +1/22.1729)→ R46.5128 の左折(κ4 = +1/46.5128)→ 出口の直線(0)
  この階段状の κ(s) の境目を、5 次のスムーズステップ(幅 W)でつなぐ。入口・出口では 0 からなめらかに立ち上がり、0 へなめらかに戻る
  ので、直線とは位置・接線・曲率が連続(G2)。曲率は、負(入口側)→ なめらかに正 → 出口、と単調に変わる(振動しない)。
  遷移でずれる「向きの変化 +π」「終点 (20,-30)」を厳密に満たすよう、区間の長さと曲率の値を、今の値からの変化が最小になるように決める。
  得られた曲線(κ(s) の積分)を高次の B スプラインにして、管(外径 12.8 / 内径 12.0)を sweep する。
座標: bows.py(FreeCAD)と同じ。入口は (0,0)→(0,-8) の -Y 向き、出口は (20,-30)→(20,0) の +Y 向き。
"""

import math

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

import bows

P0 = np.array([0.0, -8.0])  # スプラインの始点(入口の直線の終端)
P1 = np.array([20.0, -30.0])  # スプラインの終点(出口の直線の始端)
TH0 = -math.pi / 2  # 始端の向き(-Y)
TH1 = math.pi / 2  # 終端の向き(+Y)
W = 8.0  # 曲率の遷移の幅 [mm]
N = 2000  # 積分の分割数

# 今の形状(FreeCAD)の、直線以外の区間: (長さ, 曲率)
NOMINAL = dict(
    l1=12.0 * math.radians(65.0), k1=-1 / 12.0,  # R12 の右折
    l2=9.1241, k2=0.0,  # 直線
    l3=22.1729 * math.radians(213.197), k3=1 / 22.1729,  # R22.1729 の左折
    l4=46.5128 * math.radians(31.803), k4=1 / 46.5128,  # R46.5128 の左折
)


def smooth(x):
    """5 次のスムーズステップ(0→1、両端で 1・2 階微分が 0)。"""
    x = np.clip(x, 0.0, 1.0)
    return x**3 * (10 - 15 * x + 6 * x**2)


def kappa(s, v, w=W):
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


def integrate(v, w=W):
    L = length(v)
    s = np.linspace(0.0, L, N + 1)
    k = kappa(s, v, w)
    ds = np.diff(s)
    th = TH0 + np.concatenate([[0.0], np.cumsum(0.5 * (k[1:] + k[:-1]) * ds)])
    x = P0[0] + np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(th[1:]) + np.cos(th[:-1])) * ds)])
    y = P0[1] + np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(th[1:]) + np.sin(th[:-1])) * ds)])
    return s, k, th, np.stack([x, y], axis=1)


def reference_points(step: float = 0.05):
    d = bows.BOWS["b1bow"]
    wire, _, _ = bows.centerline(d["start"], d["heading"], d["segs"])
    total = wire.length
    return np.array([(p.X, p.Y) for p in (wire.position_at(s / total) for s in np.arange(8.0, total - 30.0 + 1e-9, step))])


V0 = np.array([NOMINAL["l1"], NOMINAL["l2"], NOMINAL["l3"], NOMINAL["l4"], NOMINAL["k1"], NOMINAL["k3"], NOMINAL["k4"]])


def solve(w: float = W, wshape: float = 0.3):
    ref = reference_points()
    tree = cKDTree(ref)
    scale = np.array([V0[0], 10.0, V0[2], V0[3], abs(V0[4]), abs(V0[5]), abs(V0[6])])

    def resid(v):
        s, k, th, xy = integrate(v, w)
        c = np.concatenate([[(th[-1] - TH1) * 1e5], (xy[-1] - P1) * 1e5])
        dv = (v - V0) / scale  # 今の値からの変化(相対)
        d1 = tree.query(xy[::8])[0] * wshape
        d2 = cKDTree(xy).query(ref[::40])[0] * wshape
        return np.concatenate([c, dv * 3.0, d1, d2])

    # 曲げは今より急にしない: 入口側の曲率 κ1 ≥ -1/12(R ≥ 12)。ほかは今の値の付近
    lo = np.array([5.0, 0.0, 40.0, 5.0, -1 / 12.0, 0.01, 0.005])
    hi = np.array([40.0, 30.0, 140.0, 80.0, -0.02, 0.2, 0.2])
    r = least_squares(resid, V0, bounds=(lo, hi), x_scale=scale, max_nfev=400, xtol=1e-12, ftol=1e-12)
    return r.x, ref


def analyze(v, ref, w=W):
    s, k, th, xy = integrate(v, w)
    tree = cKDTree(ref)
    d_new = tree.query(xy)[0]
    d_old = cKDTree(xy).query(ref)[0]
    dk = np.gradient(k, s)
    ext = []
    for i in range(3, len(s) - 3):
        if np.sign(dk[i - 1]) != np.sign(dk[i + 1]) and np.sign(dk[i - 1]) != 0 and abs(dk[i - 1]) + abs(dk[i + 1]) > 1e-9:
            if not ext or s[i] - ext[-1][0] > 2.0:
                ext.append((float(s[i]), float(k[i])))
    zeros = [float(s[i]) for i in np.where(np.diff(np.sign(k[5:-5])) != 0)[0] + 5]
    return dict(L=length(v), end=xy[-1], end_th=math.degrees(th[-1]), kmin=float(k.min()), kmax=float(k.max()),
                dmax=float(max(d_new.max(), d_old.max())), dmean=float(d_new.mean()), ext=ext, zeros=zeros, s=s, k=k, xy=xy)


W_DEFAULT = 6.0


def spline_edge(v, w=W_DEFAULT, n_pts=300):
    """κ(s) を積分した曲線(N+1 点)から、B スプライン曲線(次数 3〜6、C2、許容 1e-5)の辺を作る。
    300 点・次数 6 で、両端の接線のずれ 0.0015°、端の曲率 2.6e-4(R ≈ 3800)。"""
    from build123d import Edge
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BSplineCurve  # noqa: F401
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.gp import gp_Pnt

    s, k, th, xy = integrate(v, w)
    idx = np.linspace(0, N, n_pts + 1).astype(int)
    pts = xy[idx].copy()
    pts[0], pts[-1] = P0, P1  # 直線部と厳密につなぐ
    arr = Array1_gp_Pnt(1, len(pts))
    for i, (x, y) in enumerate(pts, start=1):
        arr.SetValue(i, gp_Pnt(float(x), float(y), 0.0))
    crv = GeomAPI_PointsToBSpline(arr, 3, 6, GeomAbs_Shape.GeomAbs_C2, 1e-5).Curve()
    return Edge(BRepBuilderAPI_MakeEdge(crv).Edge()), crv


def planar_tube(wire, start, heading, r_out=bows.OD / 2, r_in=bows.ID / 2):
    """平面(XY)内の経路に沿った管。副法線を Z に固定して掃引する(経路に変曲点があっても管がねじれない)。
    Frenet フレームだと、曲率が 0 になる変曲点で向きが反転して、体積が合わなくなる。"""
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


def b1bow_spline(w=W_DEFAULT):
    from build123d import Edge, Vector, Wire

    v, ref = solve(w)
    e2, crv = spline_edge(v, w)
    e1 = Edge.make_line((0, 0, 0), (0, -8, 0))
    e3 = Edge.make_line((20, -30, 0), (20, 0, 0))
    wire = Wire([e1, e2, e3])
    return planar_tube(wire, Vector(0, 0, 0), Vector(0, -1, 0)), v, ref, crv, wire


def curve_ends(crv):
    """スプライン両端の接線の向き [deg] と曲率。"""
    from OCP.GeomLProp import GeomLProp_CLProps

    out = []
    for u in (crv.FirstParameter(), crv.LastParameter()):
        pr = GeomLProp_CLProps(crv, u, 2, 1e-9)
        t = pr.D1()
        out.append((math.degrees(math.atan2(t.Y(), t.X())), pr.Curvature()))
    return out


def main():
    from build123d import Pos
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show

    solid, v, ref, crv, wire = b1bow_spline()
    a = analyze(v, ref, W_DEFAULT)
    old = bows.bow("b1bow")
    show(old, solid, names=["b1bow_old", "b1bow_spline"], alphas=[0.25, 1.0], colors=["gray", None], reset_camera=Camera.KEEP)
    print(f"W={W_DEFAULT}: valid={solid.is_valid} 体積={solid.volume:.2f} (期待 π(6.4²-6²)·(8+{a['L']:.3f}+30)={math.pi * (6.4**2 - 6**2) * (38 + a['L']):.2f})")
    print("区間の長さ l1..l4 =", np.round(v[:4], 4), " 曲率 κ1, κ3, κ4 =", np.round(v[4:], 5), " (半径 %s)" % np.round(1 / np.abs(v[4:]), 3))
    print("スプラインの長さ %.4f / 積分した曲線の長さ %.4f" % (crv.Length() if hasattr(crv, "Length") else float("nan"), a["L"]))
    (t0, k0), (t1, k1) = curve_ends(crv)
    print("スプライン端: 始端の接線 %.5f°(入口は -90°)曲率 %.2e / 終端の接線 %.5f°(出口は +90°)曲率 %.2e" % (t0, k0, t1, k1))
    print("κ 最小 %.4f(R=%.2f) 最大 %.4f(R=%.2f) 零点 s=%s" % (a["kmin"], 1 / abs(a["kmin"]), a["kmax"], 1 / a["kmax"], [round(z, 1) for z in a["zeros"]]))
    print("今の形との距離: 最大 %.3f 平均 %.3f" % (a["dmax"], a["dmean"]))
    bb = solid.bounding_box(); bo = old.bounding_box()
    print("外形 新 x[%.1f,%.1f] y[%.1f,%.1f] / 旧 x[%.1f,%.1f] y[%.1f,%.1f]" % (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bo.min.X, bo.max.X, bo.min.Y, bo.max.Y))
    print("wire 長さ %.3f 連続 %s / 入口の直線の終端 (0,-8)、出口の直線の始端 (20,-30)、ピッチ 20" % (wire.length, wire.is_valid))


if __name__ == "__main__":
    main()
