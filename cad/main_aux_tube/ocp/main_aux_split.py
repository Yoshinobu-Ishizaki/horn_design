"""主管補助管を、おおよそ中央の分割点で補助管 1(第 4 植込 = 出口 E に近い側)と補助管 2 に分ける。座標は管体組立のワールド。

- 分割点 P_m の前後に 4 mm ずつの直線部(合わせて 8 mm の直線)。分割点での向き t_m は共通。
- 補助管 1: E(向き u)→ 平面 Π1 の中で「直線 + 円弧 + 直線(最後の 4 mm は P_m の手前)」→ P_m。
- 補助管 2: P_m(向き t_m)→ 平面 Π2 の中で「直線(最初の 4 mm)+ 円弧 + 直線」→ S の先 5 mm(向き (1,0,0))。
- Π1 と Π2 は t_m を含む別の平面で、分割点で捩れる(t_m まわりの回転)。
- P_m・t_m・Π1 は、今の主管補助管(main_aux.py の 5 次ベジェ)の芯線にできるだけ近く、隙間 ≥ GAP_REQ・最小曲げ半径 ≥ R_MIN になるように決める。
  変数 5 つ(P_m の位置 3 と t_m の向き 2)を、基準の芯線の中央付近から始めた差分進化 + SLSQP で。2 つの平面の条件(E, u, P_m, t_m が同一平面、P_m, t_m, S, (1,0,0) が
  同一平面)は、SLSQP の等式で満たす。結果は shape_cache に覚える。

    uv run python cad/main_aux_tube/ocp/main_aux_split.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "cad/bb34/ocp"), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/bellscrew/ocp"), str(ROOT / "cad/valves/ocp"),
                str(ROOT / "cad/bows/ocp"), str(ROOT / "cad/bell03/ocp"), str(ROOT / "cad/bell03/tools")]

from main_aux import D, GAP_REQ, R_MIN, tess_world  # noqa: E402,F401

# 手元の探索(tools/split_search.py、種 1。範囲 ±45 mm・全方向、隙間 ≥ 0.3 を重く)の結果 y = (P_m, θ, φ)。--search を付けると、この場で探索し直す
PRESET = [72.486, -52.791, 75.196, 1.21, 1.21]
STRAIGHT_SPLIT = 4.0  # 分割点の前後の直線部
STRAIGHT_E = 4.0  # E 側の直線部の下限
STRAIGHT_END = 5.0  # 終端側の直線部の下限


def planar_path(A, d1, B, d2, exact, st_exact, st_min, n=120):
    """A(向き d1)→ B(向き d2)の、平面内の直線 + 円弧 + 直線。exact: "start"/"end" のどちらの直線部を st_exact にそろえるか(残りは st_min 以上)。
    戻り値: dict(ok, viol(条件を破っている量。0 なら ok), resid(同一平面からのずれ)、ok のとき P(点列)・R・theta・s1・s2・length・円弧の a, mid, b)。"""
    A, B, d1, d2 = (np.asarray(v, float) for v in (A, B, d1, d2))
    M = np.column_stack([d1, d2])
    sol, *_ = np.linalg.lstsq(M, B - A, rcond=None)  # A + s d1 = B - v d2  →  s d1 + v d2 = B - A
    s, v = float(sol[0]), float(sol[1])
    resid = float(np.linalg.norm(M @ sol - (B - A)))
    theta = math.acos(float(np.clip(d1 @ d2, -1, 1)))
    tl = (s - st_exact) if exact == "start" else (v - st_exact)
    other = (v - tl) if exact == "start" else (s - tl)
    viol = max(0.0, -s) + max(0.0, -v) + max(0.0, -tl) + max(0.0, st_min - other) + max(0.0, 0.05 - theta) * 50 + max(0.0, theta - (math.pi - 0.05)) * 50
    out = dict(resid=resid, ok=False, viol=viol)
    if viol > 0:
        return out
    Q = A + s * d1
    R = tl / math.tan(theta / 2)
    axis = np.cross(d1, d2)
    axis /= np.linalg.norm(axis)
    a, b = Q - tl * d1, Q + tl * d2
    r0 = np.cross(d1, axis)
    o = a - R * r0
    l1, la, l2 = np.linalg.norm(a - A), R * theta, np.linalg.norm(B - b)
    L = l1 + la + l2
    sv = np.linspace(0, L, n)
    P = np.empty((n, 3))
    m1 = sv <= l1
    m2 = (sv > l1) & (sv <= l1 + la)
    m3 = sv > l1 + la
    P[m1] = A + np.outer(sv[m1], d1)
    ph = (sv[m2] - l1) / R
    P[m2] = o + R * (np.outer(np.cos(ph), r0) + np.outer(np.sin(ph), np.cross(axis, r0)))
    P[m3] = b + np.outer(sv[m3] - l1 - la, d2)
    mid_r = r0 * math.cos(theta / 2) + np.cross(axis, r0) * math.sin(theta / 2)
    out.update(ok=True, P=P, R=R, theta=math.degrees(theta), s1=(s - tl), s2=(v - tl), tl=tl, length=L, Q=Q, a=a, b=b, mid=o + R * mid_r, axis=axis, A=A, B=B)
    return out


def build(y, E, u, S_end, tS):
    """変数 y = (P_m の x, y, z, t_m の極角 θ, 方位角 φ)から、P_m、t_m、補助管 1、補助管 2 を作る。"""
    Pm = np.asarray(y[:3], float)
    th, ph = y[3], y[4]
    tm = np.array([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
    p1 = planar_path(E, u, Pm, tm, "end", STRAIGHT_SPLIT, STRAIGHT_E)
    p2 = planar_path(Pm, tm, S_end, tS, "start", STRAIGHT_SPLIT, STRAIGHT_END)
    return Pm, tm, p1, p2


def solve(E, u, S_end, tS, ref, tree_obs, r_min, gap_req):
    from scipy.optimize import differential_evolution, minimize
    from scipy.spatial import cKDTree

    tref = cKDTree(ref)
    ref_s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(ref, axis=0), axis=1))])
    i_mid = int(np.searchsorted(ref_s, ref_s[-1] / 2))
    Pm0 = ref[i_mid]
    t0 = ref[min(i_mid + 3, len(ref) - 1)] - ref[max(i_mid - 3, 0)]
    t0 /= np.linalg.norm(t0)
    th0, ph0 = math.acos(t0[2]), math.atan2(t0[1], t0[0])

    def resid2(y):
        _, _, p1, p2 = build(y, E, u, S_end, tS)
        return p1["resid"], p2["resid"]

    def cost(y, soft=True):
        Pm, tm, p1, p2 = build(y, E, u, S_end, tS)
        r1, r2 = p1["resid"], p2["resid"]
        c = (100.0 if soft else 0.0) * (r1 + r2)
        if not (p1["ok"] and p2["ok"]):
            return 1e3 + 200 * (p1["viol"] + p2["viol"]) + c
        Pn = np.vstack([p1["P"], p2["P"]])
        d1_, _ = tref.query(Pn)
        d2_, _ = cKDTree(Pn).query(ref)
        dev = d1_.mean() + d2_.mean() + 0.5 * max(d1_.max(), d2_.max())
        gap = tree_obs.query(Pn)[0].min() - D / 2 - 0.4
        rmin = min(p1["R"], p2["R"])
        _, i0 = tref.query(Pm)
        fr = ref_s[i0] / ref_s[-1]
        return dev + c + 400 * max(0, gap_req - gap) + 40 * max(0, r_min - rmin) + 50 * max(0, abs(fr - 0.5) - 0.1)

    bounds = [(Pm0[0] - 25, Pm0[0] + 25), (Pm0[1] - 25, Pm0[1] + 25), (Pm0[2] - 25, Pm0[2] + 25), (th0 - 0.8, th0 + 0.8), (ph0 - 0.8, ph0 + 0.8)]
    rng = np.random.default_rng(3)
    pop = np.column_stack([Pm0[0] + rng.normal(0, 6, 150), Pm0[1] + rng.normal(0, 6, 150), Pm0[2] + rng.normal(0, 6, 150),
                           th0 + rng.normal(0, 0.25, 150), ph0 + rng.normal(0, 0.25, 150)])
    res = differential_evolution(cost, bounds, seed=3, init=pop, maxiter=250, tol=1e-9, polish=False)
    r2 = minimize(lambda y: cost(y, False), res.x, method="SLSQP", bounds=bounds,
                  constraints=[{"type": "eq", "fun": lambda y: resid2(y)[0]}, {"type": "eq", "fun": lambda y: resid2(y)[1]}], options=dict(maxiter=300, ftol=1e-10))
    y = r2.x if (max(resid2(r2.x)) < 1e-4 and cost(r2.x) <= cost(res.x) + 1e-6) else res.x
    return [float(v) for v in y], float(cost(y)), float(max(resid2(y)))


def hook(M, branch, others):
    import main_aux as MA
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    from build123d import Edge, Sphere, Pos, Vector, Wire
    from scipy.spatial import cKDTree
    from shape_cache import cached

    branch, p0, n0, c0 = MA.hook(M, branch, others)
    names = list(n0)
    ref_axis = p0[names.index("main_aux_axis")]
    ref = np.array([[q.X, q.Y, q.Z] for q in (ref_axis.position_at(float(t)) for t in np.linspace(0, 1, 400))])
    keep = [i for i, n in enumerate(names) if n not in ("main_aux_tube_wall", "main_aux_axis")]  # 分割前の管と芯線は出さない(基準にだけ使う)
    p0k, n0k, c0k = [p0[i] for i in keep], [names[i] for i in keep], [c0[i] for i in keep]
    allo = others + list(zip(n0, p0)) + [("bell03_branch1_wall", branch)]
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    r_min, gap_req = arg("--rmin", R_MIN), arg("--gap", GAP_REQ)
    E, u = MA.f1_225_exit()
    S_end = ref[-1]
    tS = np.array([1.0, 0.0, 0.0])
    print(f"E {E.round(3).tolist()}, S_end {S_end.round(3).tolist()}, reference axis length {np.linalg.norm(np.diff(ref, axis=0), axis=1).sum():.3f}")

    def build_solution():
        lo, hi = np.minimum(E, S_end) - 25, np.maximum(E, S_end) + 25
        pts = []
        for n, sh in allo:
            if n in ("valve4_knuckle_F1_225_twisted",) or n.startswith("main_aux") or n.endswith("centerline") or not hasattr(sh, "bounding_box"):
                continue
            bb = sh.bounding_box()
            if bb.max.X < lo[0] or bb.min.X > hi[0] or bb.max.Y < lo[1] or bb.min.Y > hi[1] or bb.max.Z < lo[2] or bb.min.Z > hi[2]:
                continue
            pts += MA.tess_world(sh, 0.15)
        tree = cKDTree(np.array(pts))
        if "--dump" in sys.argv:  # 手元で探索を繰り返すための保存(障害物の頂点・基準の芯線)
            np.save("/tmp/claude-1000/split_obs.npy", np.array(pts))
            np.save("/tmp/claude-1000/split_ref.npy", ref)
        x, c, cp = solve(E, u, S_end, tS, ref, tree, r_min, gap_req)
        return x + [c, cp]

    if "--search" not in sys.argv:
        sol = list(PRESET) + [0.0, 0.0]
    else:
        sol = cached("main_aux_split", [round(float(v), 4) for v in [*E, *S_end, r_min, gap_req, STRAIGHT_SPLIT, STRAIGHT_E, STRAIGHT_END]] + [len(others), "--dump" in sys.argv],
                     Path(__file__), build_solution)
    x = sol[:5]
    Pm, tm, p1, p2 = build(x, E, u, S_end, tS)
    print(f"solution y(P_m, θ, φ) = {np.round(x, 4).tolist()}, cost {sol[5]:.3f}, line-intersection residual {sol[6]:.2e}")
    print(f"split point P_m {Pm.round(3).tolist()}, direction t_m {tm.round(4).tolist()}")
    n1, n2 = np.cross(u, tm), np.cross(tm, tS)
    n1, n2 = n1 / np.linalg.norm(n1), n2 / np.linalg.norm(n2)
    twist = math.degrees(math.acos(float(np.clip(n1 @ n2, -1, 1))))
    print(f"plane normals: Π1 {n1.round(4).tolist()}, Π2 {n2.round(4).tolist()}; twist about t_m {twist:.2f} deg")
    for nm, p in (("aux1", p1), ("aux2", p2)):
        print(f"{nm}: straight {p['s1']:.3f} + arc R {p['R']:.3f} ({p['theta']:.2f} deg) + straight {p['s2']:.3f}; length {p['length']:.3f}; coplanarity {p['resid']:.1e}")
    Pn = np.vstack([p1["P"], p2["P"]])
    d1_ = cKDTree(ref).query(Pn)[0]
    d2_ = cKDTree(Pn).query(ref)[0]
    print(f"deviation from the unsplit axis: max {max(d1_.max(), d2_.max()):.3f}, mean {d1_.mean():.3f}; total length {p1['length'] + p2['length']:.3f}")

    def wire(p):
        return Wire([Edge.make_line(Vector(*p["A"]), Vector(*p["a"])), Edge.make_three_point_arc(Vector(*p["a"]), Vector(*p["mid"]), Vector(*p["b"])),
                     Edge.make_line(Vector(*p["b"]), Vector(*p["B"]))])

    w1_, w2_ = wire(p1), wire(p2)
    t1, t2 = U.const_d_tube(w1_, D, BP.WALL), U.const_d_tube(w2_, D, BP.WALL)
    for nm, t in (("aux1", t1), ("aux2", t2)):
        print(f"{nm} tube: valid {t.is_valid}, volume {sum(x_.volume for x_ in t.solids()):.2f}")
    print("clearance aux1:")
    B2.report_clearance(t1, [(n, s) for n, s in allo if not n.startswith("main_aux")])
    print("clearance aux2:")
    B2.report_clearance(t2, [(n, s) for n, s in allo if not n.startswith("main_aux")])
    print(f"aux1-aux2 distance {t1.distance_to(t2):.3f}")
    sph = Pos(*Pm) * Sphere(1.5)
    return (branch, p0k + [t1, t2, w1_, w2_, sph], n0k + ["main_aux1_wall", "main_aux2_wall", "main_aux1_centerline", "main_aux2_centerline", "main_aux_split_point"],
            c0k + ["#20c0a0", "#20a0e0", "#ff2020", "#ff2020", "#ff2020"])


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
