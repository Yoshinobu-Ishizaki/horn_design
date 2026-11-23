"""2番管(仮、L 字): 第 4 植込の 1 階左下の枝管(valve4_knuckle.twisted_knuckle)の出口の端面から、
接線連続に出て、1番管の末端の直線へつながる曲線。1番管は、接続点で切る。

- 座標は管体組立のワールド(cad/valves の座標。ベルは bell_place の暫定の配置)。
- 出口の軸 u(外向き)と、1番管の末端の直線(組立で +X)は、ねじれの位置にあるので、1 平面の L 字にはならない。
  3 次元の 5 次ベジエ曲線にする: 制御点 P, P+a·u, P+2a·u, Q+2b·t, Q+b·t, Q(t は 1番管の末端の接線)。
  両端で接線と曲率 0 が連続(G2。出口の枝管の直線と、1番管の直線につながる)。
- 接続点 Q は、1番管の末端から CUT mm 戻った直線の上。a・b は、最小曲げ半径が最大になるように選ぶ。
- 管は ⌀12.0 × ⌀12.8(板厚 0.4)。

    uv run python cad/branch2/ocp/branch2_l.py [--cut 105]
"""

from __future__ import annotations

import sys
from math import comb
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"),
                str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

CUT = 105.0  # 1番管の末端から、直線に沿って切り落とす長さ(直線は 200.3 mm)
ID, WALL = 12.0, 0.4


def knuckle_exit():
    """第 4 の枝管の出口の端面の中心と、外向きの軸。"""
    import valve4_knuckle as V

    u = np.array(V.exit_axis_world(*V.solve()[:2]), float)
    k = V.twisted_knuckle()
    f = next(f for f in k.faces() if f.geom_type.name == "PLANE" and np.dot(list(f.normal_at()), u) > 1 - 1e-6)
    c = f.center()
    return np.array([c.X, c.Y, c.Z]), u


def branch1_end(M):
    """1番管の末端の位置と接線(組立のワールド)。"""
    from make_centerline import build_branch_wire

    bcl = build_branch_wire()
    p, t = bcl.position_at(1.0), bcl.tangent_at(1.0)
    return M[:3, :3] @ np.array(list(p)) + M[:3, 3], M[:3, :3] @ np.array(list(t))


def bezier_points(P, u, Q, t, a, b, n=4001):
    cp = np.array([P, P + a * u, P + 2 * a * u, Q + 2 * b * t, Q + b * t, Q])
    s = np.linspace(0, 1, n)[:, None]
    return cp, sum(comb(5, i) * s**i * (1 - s) ** (5 - i) * cp[i] for i in range(6))


def radius_min(pts):
    d1 = np.gradient(pts, axis=0)
    d2 = np.gradient(d1, axis=0)
    k = np.linalg.norm(np.cross(d1, d2), axis=1) / np.linalg.norm(d1, axis=1) ** 3
    i = int(k[3:-3].argmax()) + 3
    return 1 / k[i], i


def design(M, cut):
    from scipy.optimize import minimize

    P, u = knuckle_exit()
    E, t = branch1_end(M)
    Q = E - cut * t
    f = lambda ab: -radius_min(bezier_points(P, u, Q, t, *ab, n=1501)[1])[0]  # noqa: E731
    best = min((minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-4}) for x0 in
                [(10, 10), (20, 10), (10, 20), (20, 30)]), key=lambda r: r.fun)
    a, b = best.x
    cp, pts = bezier_points(P, u, Q, t, a, b)
    r, i = radius_min(pts)
    return dict(P=P, u=u, Q=Q, t=t, E=E, a=a, b=b, cp=cp, pts=pts, r_min=r, r_at=pts[i])


def pipe(wire, face):
    """円環の断面を芯線に沿って掃引したソリッド(BRepOffsetAPI_MakePipe、フレネ)。
    build123d の sweep(MakePipeShell)は、この曲線で値の端数しだいで失敗し、外径・内径の差も空になったので使わない。"""
    from build123d import Solid
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCP.GeomFill import GeomFill_Trihedron

    mk = BRepOffsetAPI_MakePipe(wire.wrapped, face.wrapped, GeomFill_Trihedron.GeomFill_IsFrenet, False)
    mk.Build()
    return Solid(mk.Shape())


def hook_for(cut):
    def hook(M, branch):
        from build123d import Box, Edge, Face, Plane, Wire

        d = design(M, cut)
        edge = Edge.make_bezier(*[tuple(c) for c in d["cp"]])
        wire = Wire([edge])
        ln = edge.length
        # 断面は一定なので、外径・内径の円をそれぞれ芯線に沿って掃引して差を取る(円環の面の掃引は MakeSolid で失敗した)
        pl = Plane(origin=tuple(d["P"]), z_dir=tuple(d["u"]))
        tube = pipe(wire, Face(Wire([Edge.make_circle(ID / 2 + WALL, pl)]), [Wire([Edge.make_circle(ID / 2, pl)])]))
        ratio = tube.volume / (np.pi * ((ID / 2 + WALL) ** 2 - (ID / 2) ** 2) * ln)
        # 1番管を Q で切る(Q から末端までの直線の部分だけを、箱で除く。渦巻きの部分は別の所にあるので触らない)
        cutter = Plane(origin=tuple(d["Q"] + d["t"] * (cut + 10) / 2), z_dir=tuple(d["t"])) * Box(40, 40, cut + 10)
        branch_cut = branch - cutter
        from make_centerline import build_branch_wire

        b1_full = build_branch_wire().length
        b1_len = b1_full - cut
        print(f"knuckle exit P {d['P'].round(3).tolist()}, axis u {d['u'].round(4).tolist()}")
        print(f"branch1 end {d['E'].round(3).tolist()}, tangent {d['t'].round(4).tolist()}; cut {cut:g} -> join Q "
              f"{d['Q'].round(3).tolist()}")
        print(f"branch2: bezier a {d['a']:.2f} b {d['b']:.2f}, length {ln:.3f}, min bend R {d['r_min']:.2f} at "
              f"{d['r_at'].round(1).tolist()}; tube valid {tube.is_valid} volume ratio {ratio:.5f}")
        print(f"length rim -> knuckle exit: branch1 {b1_len:.3f} + branch2 {ln:.3f} = {b1_len + ln:.3f} "
              f"(now branch1 {b1_full:.3f}, diff {b1_len + ln - b1_full:+.3f})")
        print(f"branch1 after cut: solids {len(branch_cut.solids())} valid {branch_cut.is_valid}")
        return branch_cut, [tube, wire], ["branch2_wall", "branch2_centerline"], ["#20c0a0", "#ff2020"]

    return hook


def main() -> None:
    import assy_with_valves as AW

    cut = float(sys.argv[sys.argv.index("--cut") + 1]) if "--cut" in sys.argv else CUT
    AW.main(hook=hook_for(cut))


if __name__ == "__main__":
    main()
