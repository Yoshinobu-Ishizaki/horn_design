"""2番管(仮、L 字): 第 4 植込の 1 階左下の枝管(valve4_knuckle.twisted_knuckle)の出口の端面から、
接線連続に出て、1番管の末端の直線へつながる曲線。1番管は、接続点で切る。

- 座標は管体組立のワールド(cad/valves の座標。ベルは bell_place の暫定の配置)。
- 出口の軸 u(外向き)と、1番管の末端の直線(組立で +X)は、ねじれの位置にあるので、1 平面の L 字にはならない。
  出口から u に沿って S0 だけ直線(近くの外管に寄らないように)、そこから 3 次元の 5 次ベジエ曲線:
  制御点 P1, P1+a·u, P1+2a·u, Q+2b·t, Q+b·t, Q(P1 = P + S0·u、t は 1番管の末端の接線)。
  両端で接線と曲率 0 が連続(G2。出口の枝管の直線と、1番管の直線につながる)。
- 接続点 Q は、1番管の末端から CUT mm 戻った直線の上。a・b は、最小曲げ半径が最大になるように選ぶ。
- 管は ⌀12.0 × ⌀12.8(板厚 0.4)。

    uv run python cad/model202611/body_assy/branch2/ocp/branch2_l.py [--cut 105]
"""

from __future__ import annotations

import os
import sys
from math import comb
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

CUT = 105.0  # 1番管の末端から、直線に沿って切り落とす長さ(直線は 200.3 mm)
ID, WALL = 12.0, 0.4
GAP = 0.4  # ほかの部品(出口の枝管を除く)との表面最近接距離の下限。実物はこの隙間に半田を流す(モデルには入れない)
GAP_MARGIN = 0.1  # 点群での概算の誤差のぶんの余裕
START_SKIP = "valve4_knuckle_F1_225_twisted"  # つなぐ枝管は除く


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


def near(b1, b2, margin):
    """2 つの BoundBox が margin 以内にあるか(build123d の overlaps は、片方が他方を含むと False になるので使わない)。"""
    return all(getattr(b1.min, k) - margin <= getattr(b2.max, k) and getattr(b2.min, k) - margin <= getattr(b1.max, k)
               for k in "XYZ")


def face_points(face, step=0.5, cap=150):
    """面の上の点を、u・v 方向とも約 step mm 間隔で取る(三角形分割の頂点は、長い円筒では両端にしかないので使わない)。
    面の外(穴の部分)の点も入るが、隙間を小さく見積もる側なので安全。"""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    sf = BRepAdaptor_Surface(face.wrapped)
    u0, u1, v0, v1 = sf.FirstUParameter(), sf.LastUParameter(), sf.FirstVParameter(), sf.LastVParameter()

    def grid(nu, nv):
        out = np.empty((nu, nv, 3))
        for i, u in enumerate(np.linspace(u0, u1, nu)):
            for j, v in enumerate(np.linspace(v0, v1, nv)):
                q = sf.Value(u, v)
                out[i, j] = (q.X(), q.Y(), q.Z())
        return out
    q = grid(6, 6)
    lu = np.linalg.norm(np.diff(q, axis=0), axis=2).sum(axis=0).max()
    lv = np.linalg.norm(np.diff(q, axis=1), axis=2).sum(axis=1).max()
    nu, nv = (int(min(cap, max(4, x / step))) for x in (lu, lv))
    return grid(nu, nv).reshape(-1, 3)


def obstacle_tree(others, M, step=0.5, reach=20.0):
    """ほかの部品(つなぐ枝管は除く)の表面の点の KD 木。CUT 80〜160 の曲線(隙間を考えない設計)から reach mm 以内の
    部品・面だけ(全部の面を細かく取ると遅すぎた)。"""
    from build123d import Compound, Edge, Vector
    from scipy.spatial import cKDTree

    probe = Compound([Edge.make_bezier(*[Vector(*map(float, c)) for c in design(M, cut)["cp"]])
                      for cut in (80.0, 100.0, 120.0, 140.0, 160.0)])
    pb = probe.bounding_box(optimal=False)
    pts, used = [], []
    for name, s in others:
        if name == START_SKIP or not hasattr(s, "faces") or not near(s.bounding_box(optimal=False), pb, reach):
            continue
        try:
            if s.distance_to(probe) > reach:
                continue
        except Exception:  # noqa: BLE001  距離の計算が落ちる形(gp_Dir のゼロ)は、箱が近ければ含める
            pass
        used.append(name)
        for f in s.faces():
            if not near(f.bounding_box(optimal=False), pb, reach):
                continue
            try:
                ok = f.distance_to(probe) <= reach
            except Exception:  # noqa: BLE001
                ok = True
            if ok:
                pts.append(face_points(f, step))
    print(f"obstacles within {reach:g} mm: {', '.join(used)} ({sum(len(x) for x in pts)} points)")
    return cKDTree(np.vstack(pts))


def design(M, cut, tree=None, r_of_s=None):
    """2番管の芯線: 出口から軸 u = (0, -b, c) に沿って S0 だけ直線(近くの外管に寄らないように)、そこから 5 次ベジエで
    -x へ曲がって、1番管の横の直線の点 Q(末端から cut 戻った所)へ、-X の向きで入る(両端 G2)。
    S0・a・b を、最小曲げ半径が最大になるように選ぶ。tree があれば、ほかの部品との隙間 GAP を守る
    (芯線から点群までの距離 - 外半径 を隙間の概算にする)。r_of_s(出口からの芯線の長さ → 外半径)を渡すと、
    メンズールで太くなる分も入れる(既定は ⌀12 + 板厚 で一定)。"""
    from scipy.optimize import minimize

    P, u = knuckle_exit()
    E, t = branch1_end(M)
    Q = E - cut * t
    ro = ID / 2 + WALL

    def gap(pts, s0=0.0):
        if tree is None:
            return np.inf
        if r_of_s is None:
            return float(tree.query(pts)[0].min()) - ro
        sl = s0 + np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        return float((tree.query(pts)[0] - r_of_s(sl)).min())

    def curve(x, n):
        s0, a, b = x
        p1 = P + s0 * u
        cp, pts = bezier_points(p1, u, Q, t, a, b, n=n)
        line = P + np.linspace(0, 1, max(2, int(s0 / 0.5)))[:, None] * (p1 - P)
        return cp, pts, line

    def f(x):
        s0, a, b = x
        if s0 < 0 or a < 1 or b < 1:
            return 1e6
        _, pts, line = curve(x, 801)
        g = min(gap(pts, s0), gap(line[2:], 0.0)) if len(line) > 2 else gap(pts[8:], s0)
        pen = max(0.0, GAP + GAP_MARGIN - g)
        return -min(radius_min(pts)[0], 200.0) + 1e3 * pen
    best = min((minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-4, "maxiter": 3000})
                for x0 in [(10, 10, 10), (20, 10, 20), (30, 15, 15), (40, 10, 30)]), key=lambda r: r.fun)
    s0, a, b = best.x
    cp, pts, line = curve(best.x, 4001)
    r, i = radius_min(pts)
    return dict(P=P, u=u, Q=Q, t=t, E=E, s0=s0, a=a, b=b, cp=cp, pts=pts, r_min=r, r_at=pts[i],
                gap_est=min(gap(pts, s0), gap(line[2:]) if len(line) > 2 else np.inf), ok=best.fun < 1e2,
                length=s0 + float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()))


def centerline_edges(d):
    """2番管の芯線の辺: 出口からの直線(S0 > 0 のとき)とベジエ。"""
    from build123d import Edge, Line

    edges = []
    p1 = tuple(map(float, d["cp"][0]))
    if d["s0"] > 1e-3:
        edges.append(Line(tuple(map(float, d["P"])), p1))
    edges.append(Edge.make_bezier(*[tuple(map(float, c)) for c in d["cp"]]))
    return edges


def tube_const(d):
    """⌀12 一定の 2番管(直線は円環を押し出し、ベジエは MakePipe のフレネ。直線にはフレネが使えない)。"""
    from build123d import Circle, Edge, Face, Plane, Wire, extrude

    edges = centerline_edges(d)
    bz = edges[-1]
    p1, u = tuple(map(float, d["cp"][0])), tuple(map(float, d["u"]))
    pl = Plane(origin=p1, z_dir=u)
    tube = pipe(Wire([bz]), Face(Wire([Edge.make_circle(ID / 2 + WALL, pl)]), [Wire([Edge.make_circle(ID / 2, pl)])]))
    if len(edges) == 2:
        p0 = Plane(origin=tuple(map(float, d["P"])), z_dir=u)
        ring = p0 * (Circle(ID / 2 + WALL) - Circle(ID / 2))
        tube = tube + extrude(ring, d["s0"])
    return tube


def pipe(wire, face):
    """円環の断面を芯線に沿って掃引したソリッド(BRepOffsetAPI_MakePipe、フレネ)。
    build123d の sweep(MakePipeShell)は、この曲線で値の端数しだいで失敗し、外径・内径の差も空になったので使わない。"""
    from build123d import Solid
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCP.GeomFill import GeomFill_Trihedron

    mk = BRepOffsetAPI_MakePipe(wire.wrapped, face.wrapped, GeomFill_Trihedron.GeomFill_IsFrenet, False)
    mk.Build()
    return Solid(mk.Shape())


def checks_enabled():
    """隙間・干渉の確認をするか。作図に必要ないので、既定では何も測らない。指示されたとき(--check、または環境変数 OCP_CHECK=1)だけ測る。"""
    return "--check" in sys.argv or bool(os.environ.get("OCP_CHECK"))


def report_clearance(tube, others, near_mm=5.0):
    """2番管と、ほかの部品の表面最近接距離(near_mm 以内のものだけ表示)。--check のときだけ測る(既定は何もせず [] を返す)。"""
    if not checks_enabled():
        return []
    bb = tube.bounding_box(optimal=False)
    out = []
    for name, s in others:
        if not hasattr(s, "bounding_box") or not near(s.bounding_box(optimal=False), bb, near_mm):
            continue
        d = tube.distance_to(s)
        if d < near_mm:
            out.append((d, name))
    for d, name in sorted(out):
        print(f"  clearance branch2 - {name}: {d:.3f} mm")
    return sorted(out)


def hook_for(cut_arg):
    def hook(M, branch, others):
        cut = cut_arg
        from build123d import Box, Plane, Wire

        tree = obstacle_tree(others, M)
        if cut is None:  # 隙間を守れる範囲で、最小曲げ半径が最大になる CUT を探す
            cands = []
            for c in np.arange(90.0, 161.0, 10.0):
                dd = design(M, c, tree)
                print(f"  cut {c:5.1f}: R_min {dd['r_min']:6.2f}, gap est {dd['gap_est']:.3f}, ok {dd['ok']}")
                if dd["ok"]:
                    cands.append((dd["r_min"], c))
            cut = max(cands)[1] if cands else CUT
        d = design(M, cut, tree)
        wire = Wire(centerline_edges(d))
        ln = wire.length
        tube = tube_const(d)
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
        print(f"branch2: straight {d['s0']:.2f} along u, bezier a {d['a']:.2f} b {d['b']:.2f}, length {ln:.3f}, min bend R {d['r_min']:.2f} at "
              f"{d['r_at'].round(1).tolist()}; tube valid {tube.is_valid} volume ratio {ratio:.5f}")
        print(f"length rim -> knuckle exit: branch1 {b1_len:.3f} + branch2 {ln:.3f} = {b1_len + ln:.3f} "
              f"(now branch1 {b1_full:.3f}, diff {b1_len + ln - b1_full:+.3f})")
        print(f"branch1 after cut: solids {len(branch_cut.solids())} valid {branch_cut.is_valid}")
        report_clearance(tube, others)
        return branch_cut, [tube, wire], ["branch2_wall", "branch2_centerline"], ["#20c0a0", "#ff2020"]

    return hook


def main() -> None:
    import assy_with_valves as AW

    cut = float(sys.argv[sys.argv.index("--cut") + 1]) if "--cut" in sys.argv else CUT
    if "--scan" in sys.argv:
        cut = None
    AW.main(hook=hook_for(cut))


if __name__ == "__main__":
    main()
