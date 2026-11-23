"""主管補助管を、おおよそ中央の分割点で補助管 1(第 4 植込 = 出口 E に近い側)と補助管 2 に分ける。座標は管体組立のワールド。

- 分割点 P_m の前後に 4 mm ずつの直線部(合わせて 8 mm の直線)。分割点での向き t_m は共通。
- 補助管 1: E(向き u、最初の 4 mm は直線)→ 平面 Π1 の中で「直線 + 円弧 + 直線 + 円弧 + 直線(最後の 4 mm は P_m の手前)」→ P_m。
- 補助管 2: P_m(向き t_m、最初の 4 mm は直線)→ 平面 Π2 の中で「直線 + 円弧 + 直線 + 円弧 + 直線(最後の 5 mm)」→ S の先 5 mm(向き (1,0,0))。
  円弧は 2 つとも同じ半径(補助管ごと)、2 つの円弧の間の直線は 0 以上。
- Π1 と Π2 は t_m を含む別の平面で、分割点で捩れる(t_m まわりの回転)。
- P_m の位置(3)と、補助管 1・2 の円弧の半径(2)を、今の主管補助管(main_aux.py の 5 次ベジェ)の芯線にできるだけ近く、隙間 ≥ GAP_REQ・半径 ≥ R_MIN
  になるように決める。t_m は、2 つの平面の条件(E, u, P_m が Π1、P_m, S, (1,0,0) が Π2)の交線から一意に決まる(`tm_of`)。
  結果は PRESET に書き写してある(tools/split_search.py の探索)。`--search` で、この場で探索し直す。

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

# 手元の探索(tools/split_search.py)の結果 y = (P_m の x, y, z、補助管 1 の円弧の半径、補助管 2 の円弧の半径)。--search で探索し直す
PRESET = [69.4892, -34.5027, 39.6341, 13.6442, 11.4307]
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


def csc_path(A, d1, B, d2, r, st_start, st_end, n=160):
    """A(向き d1)→ B(向き d2)の、平面内の「直線(st_start)+ 円弧 + 直線 + 円弧 + 直線(st_end)」(2 つの円弧は同じ半径 r。最短の組)。
    A, d1, B, d2 は同一平面内でなければならない(resid はそのずれ)。戻り値: dict(ok, P(点列), length, segs(Wire 用: ("line", p, q) / ("arc", p, mid, q)), R, resid)。"""
    A, B, d1, d2 = (np.asarray(v, float) for v in (A, B, d1, d2))
    A2, B2 = A + st_start * d1, B - st_end * d2
    nrm = np.cross(d1, B2 - A2)
    if np.linalg.norm(nrm) < 1e-9:
        nrm = np.cross(d1, d2)
    if np.linalg.norm(nrm) < 1e-9:
        return dict(ok=False, resid=0.0, viol=1.0)
    nrm /= np.linalg.norm(nrm)
    ex, ey = d1, np.cross(nrm, d1)
    resid = abs(float(nrm @ d2))  # d2 が平面から出る成分
    G = np.array([(B2 - A2) @ ex, (B2 - A2) @ ey])
    th = math.atan2(float(d2 @ ey), float(d2 @ ex))
    TWO = 2 * math.pi
    cl0, cr0 = np.array([0.0, r]), np.array([0.0, -r])
    cl1 = G + r * np.array([-math.sin(th), math.cos(th)])
    cr1 = G + r * np.array([math.sin(th), -math.cos(th)])
    cands = []

    def add(kind, c0, c1, psi, L):
        if L < -1e-9:
            return
        if kind[0] == "L":
            al = psi % TWO
        else:
            al = (-psi) % TWO
        if kind[1] == "L":
            be = (th - psi) % TWO
        else:
            be = (psi - th) % TWO
        cands.append((r * (al + be) + max(L, 0.0), kind, c0, c1, psi, max(L, 0.0), al, be))

    for kind, c0, c1 in (("LL", cl0, cl1), ("RR", cr0, cr1)):
        c = c1 - c0
        psi = math.atan2(c[1], c[0])
        add(kind, c0, c1, psi, float(np.linalg.norm(c)))
    for kind, c0, c1, sg in (("LR", cl0, cr1, +1), ("RL", cr0, cl1, -1)):
        c = c1 - c0
        d = float(np.linalg.norm(c))
        if d < 2 * r:
            continue
        phic = math.atan2(c[1], c[0])
        for psi in (phic + sg * math.asin(2 * r / d), phic + math.pi - sg * math.asin(2 * r / d)):
            dirv = np.array([math.cos(psi), math.sin(psi)])
            if kind == "LR":
                p0, p1 = c0 + r * np.array([math.sin(psi), -math.cos(psi)]), c1 + r * np.array([-math.sin(psi), math.cos(psi)])
            else:
                p0, p1 = c0 + r * np.array([-math.sin(psi), math.cos(psi)]), c1 + r * np.array([math.sin(psi), -math.cos(psi)])
            L = float((p1 - p0) @ dirv)
            if abs(float((p1 - p0)[0] * dirv[1] - (p1 - p0)[1] * dirv[0])) < 1e-6:
                add(kind, c0, c1, psi, L)
    if not cands:
        return dict(ok=False, resid=resid, viol=1.0)
    tot, kind, c0, c1, psi, L, al, be = min(cands, key=lambda c: c[0])
    to3 = lambda q: A2 + q[0] * ex + q[1] * ey  # noqa: E731

    def arc_pts(c, a0, ang, left, k=40):
        ts = np.linspace(0, 1, k)
        sgn = 1 if left else -1
        # 位置 = c + r·(円の上の点)。ヘディング h の位置: 左 c + r(sin h, -cos h)、右 c + r(-sin h, cos h)
        hs = a0 + sgn * ang * ts
        return np.array([c + r * (np.array([math.sin(h), -math.cos(h)]) if left else np.array([-math.sin(h), math.cos(h)])) for h in hs])

    a_pts = arc_pts(c0, 0.0, al, kind[0] == "L")
    b_pts = arc_pts(c1, psi, be, kind[1] == "L")
    pts2 = [a_pts, b_pts]
    segs = []
    pts = [A, A2]
    segs.append(("line", A, A2))
    a0, a1 = to3(a_pts[0]), to3(a_pts[-1])
    if al > 1e-6:
        segs.append(("arc", a0, to3(a_pts[len(a_pts) // 2]), a1))
    b0, b1 = to3(b_pts[0]), to3(b_pts[-1])
    if L > 1e-6:
        segs.append(("line", a1, b0))
    if be > 1e-6:
        segs.append(("arc", b0, to3(b_pts[len(b_pts) // 2]), b1))
    segs.append(("line", b1, B2))
    segs.append(("line", B2, B))
    P = [A, A2] + [to3(q) for q in a_pts] + [to3(q) for q in b_pts] + [B2, B]
    P = np.array(P)
    # 点列を等間隔に近くして返す(距離の評価用)
    dense = []
    for q0, q1 in zip(P[:-1], P[1:]):
        k = max(2, int(np.linalg.norm(q1 - q0) / 1.5))
        dense += [q0 + (q1 - q0) * t for t in np.linspace(0, 1, k, endpoint=False)]
    dense.append(P[-1])
    return dict(ok=True, P=np.array(dense), length=float(st_start + st_end + tot), segs=segs, R=r, resid=resid, kind=kind, al=math.degrees(al), be=math.degrees(be), L=L,
                viol=0.0)


def tm_of(Pm, E, u, S_end, tS):
    """P_m での向き t_m: 平面 Π1(E, u, P_m を含む)と Π2(P_m, S_end, tS を含む)の交線の向き(E → S_end 側へ)。"""
    n1, n2 = np.cross(u, Pm - E), np.cross(tS, S_end - Pm)
    t = np.cross(n1, n2)
    nt = np.linalg.norm(t)
    if nt < 1e-9:
        return None
    t = t / nt
    return t if t @ (S_end - E) >= 0 else -t


def build(y, E, u, S_end, tS):
    """変数 y = (P_m の x, y, z、補助管 1 の円弧の半径、補助管 2 の円弧の半径)から、P_m、t_m、補助管 1、補助管 2 を作る。"""
    Pm = np.asarray(y[:3], float)
    tm = tm_of(Pm, E, u, S_end, tS)
    if tm is None:
        return Pm, None, dict(ok=False), dict(ok=False)
    p1 = csc_path(E, u, Pm, tm, y[3], STRAIGHT_E, STRAIGHT_SPLIT)
    p2 = csc_path(Pm, tm, S_end, tS, y[4], STRAIGHT_SPLIT, STRAIGHT_END)
    return Pm, tm, p1, p2


def solve(E, u, S_end, tS, ref, tree_obs, r_min, gap_req):
    from scipy.optimize import differential_evolution
    from scipy.spatial import cKDTree

    tref = cKDTree(ref)
    mid = ref[len(ref) // 2]

    def cost(y):
        Pm, tm, p1, p2 = build(y, E, u, S_end, tS)
        if tm is None or not (p1["ok"] and p2["ok"]):
            return 1e3
        Pn = np.vstack([p1["P"], p2["P"]])
        d1_ = tref.query(Pn)[0]
        d2_ = cKDTree(Pn).query(ref)[0]
        dev = d1_.mean() + d2_.mean() + 0.5 * max(d1_.max(), d2_.max())
        gap = tree_obs.query(Pn)[0].min() - D / 2 - 0.4
        la, lb = p1["length"], p2["length"]
        return dev + 1500 * max(0, gap_req - gap) + 60 * max(0, abs(la / (la + lb) - 0.5) - 0.15) + 0.05 * (la + lb)

    rng = np.random.default_rng(0)
    bounds = [(mid[i] - 40, mid[i] + 40) for i in range(3)] + [(r_min, 60), (r_min, 60)]
    init = np.array([np.concatenate([mid + rng.normal(0, 12, 3), [rng.uniform(r_min, 40), rng.uniform(r_min, 40)]]) for _ in range(60)])
    res = differential_evolution(cost, bounds, seed=0, init=init, maxiter=100, tol=1e-10, polish=False)
    return [float(v) for v in res.x], float(res.fun), 0.0


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
    print(f"solution y(P_m, r1, r2) = {np.round(x, 4).tolist()}")
    print(f"split point P_m {Pm.round(3).tolist()}, direction t_m {tm.round(4).tolist()}")
    n1, n2 = np.cross(u, tm), np.cross(tm, tS)
    n1, n2 = n1 / np.linalg.norm(n1), n2 / np.linalg.norm(n2)
    twist = math.degrees(math.acos(float(np.clip(n1 @ n2, -1, 1))))
    print(f"plane normals: Π1 {n1.round(4).tolist()}, Π2 {n2.round(4).tolist()}; twist about t_m {twist:.2f} deg")
    for nm, p in (("aux1", p1), ("aux2", p2)):
        print(f"{nm}: {p['kind']} arcs R {p['R']:.3f} x {p['al']:.1f} / {p['be']:.1f} deg, middle straight {p['L']:.3f}; length {p['length']:.3f}; coplanarity {p['resid']:.1e}")
    Pn = np.vstack([p1["P"], p2["P"]])
    d1_ = cKDTree(ref).query(Pn)[0]
    d2_ = cKDTree(Pn).query(ref)[0]
    print(f"deviation from the unsplit axis: max {max(d1_.max(), d2_.max()):.3f}, mean {d1_.mean():.3f}; total length {p1['length'] + p2['length']:.3f}")

    def wire(p):
        es = [Edge.make_line(Vector(*q[1]), Vector(*q[2])) if q[0] == "line" else Edge.make_three_point_arc(Vector(*q[1]), Vector(*q[2]), Vector(*q[3])) for q in p["segs"]
              if not (q[0] == "line" and np.linalg.norm(np.asarray(q[1]) - np.asarray(q[2])) < 1e-6)]
        return Wire(es)

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
