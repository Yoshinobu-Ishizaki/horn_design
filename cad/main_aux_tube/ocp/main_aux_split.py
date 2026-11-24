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
# 補助管 2 の中間の直線(+Z へ立ち上がる)の、-Y から見た(XZ への射影の)傾き。+Z から +X 側へ測って角度(負 = -X 側へ倒す)。None なら PRESET の半径のまま
AUX2_MID_ANGLE = -10.0
X_S_SPLIT = 90.0  # 右側の端点 S の x(分割前は main_aux.X_S = 92)。最後の 5 mm の直線はそのまま(S_end = S + 5 mm)


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


def mid_angle(p):
    """csc_path の結果 p の中間の直線の、XZ への射影の +Z からの角度(+X 側が正、度)。中間の直線がなければ None。"""
    lines = [q for q in p["segs"] if q[0] == "line"]
    if len(lines) != 4:
        return None
    d = np.asarray(lines[1][2], float) - np.asarray(lines[1][1], float)
    return math.degrees(math.atan2(d[0], d[2]))


def r2_for_angle(Pm, tm, S_end, tS, target, lo=10.0, hi=15.2):
    """補助管 2 の円弧の半径 r2 を、中間の直線の傾きが target(度)になるように決める(平面は変えない。二分法。lo は最小曲げ半径)。"""
    f = lambda r: mid_angle(csc_path(Pm, tm, S_end, tS, r, STRAIGHT_SPLIT, STRAIGHT_END)) - target  # noqa: E731
    a, b = lo, hi
    if f(a) * f(b) > 0:
        raise ValueError(f"傾き {target} 度になる半径が [{lo}, {hi}] にない(両端 {f(a) + target:.1f}, {f(b) + target:.1f})")
    for _ in range(60):
        m = 0.5 * (a + b)
        if f(a) * f(m) <= 0:
            b = m
        else:
            a = m
    return 0.5 * (a + b)


# G2 版(スプライン): 中間部を、平面内の 7 次ベジェ(両端の曲率 0 = 直線と G2 連続)にする。v = (a, db, c, dc, Q3x, Q3y, Q4x, Q4y, 始端側の直線長さ, 終端側の直線長さ)。
# 制御点(平面内、始点 A = 曲線の始まり、向き d1 を x、終点 B・向き d2): P0=A, P1=A+a·d1, P2=A+(a+db)·d1, P3=Q3, P4=Q4, P5=B-(c+dc)·d2, P6=B-c·d2, P7=B。
# tools/g2_fit.py(差分進化)の結果。aux1 は曲がる向き 1 つ・曲率の分布が左右対称に近い、aux2 は S 字で正負の曲率の山の大きさをそろえた形。
G2_PRESET = {
    "aux1": [5.4439, 6.3654, 0.8076, 2.6447, 13.8555, 3.2322, 15.7261, 4.3673, 4.1483, 4.1195],
    "aux2": [2.701, 15.7766, 4.3108, 15.9607, 8.2956, 20.7862, 18.57, 8.0274, 5.1319, 5.242],
}


def g2_piece(A0, d1, B0, d2, v):
    """A0(向き d1)→ B0(向き d2)の、直線 + 7 次ベジェ + 直線の Wire(各辺の点・平面の法線・曲率の最大/最小・曲線の長さ)。"""
    from build123d import Edge, Vector, Wire

    v = np.asarray(v, float)
    st, en = v[8], v[9]
    A, B = A0 + st * d1, B0 - en * d2
    nrm = np.cross(d1, B0 - A0)
    nrm /= np.linalg.norm(nrm)
    ex, ey = d1, np.cross(nrm, d1)
    G = np.array([(B - A) @ ex, (B - A) @ ey])
    th = math.atan2(float(d2 @ ey), float(d2 @ ex))
    a, db, c, dc = v[:4]
    dd = np.array([math.cos(th), math.sin(th)])
    P2 = np.array([[0, 0], [a, 0], [a + db, 0], v[4:6], v[6:8], G - (c + dc) * dd, G - c * dd, G])
    P3 = [A + q[0] * ex + q[1] * ey for q in P2]
    t = np.linspace(0, 1, 400)
    from math import comb

    n = 7
    Bn = lambda k, tt: np.array([comb(k, i) * tt**i * (1 - tt) ** (k - i) for i in range(k + 1)]).T  # noqa: E731
    d_1, d_2 = n * np.diff(P2, axis=0), n * (n - 1) * np.diff(P2, n=2, axis=0)
    f1, f2 = Bn(n - 1, t) @ d_1, Bn(n - 2, t) @ d_2
    kap = (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0]) / np.linalg.norm(f1, axis=1) ** 3
    es = [Edge.make_line(Vector(*A0), Vector(*A)), Edge.make_bezier(*[Vector(*q) for q in P3]), Edge.make_line(Vector(*B), Vector(*B0))]
    return Wire(es), nrm, kap, es[1].length


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
    """主管補助管(2026-11-24 やり直し)。前の aux1・aux2 は消した(_hook_split_g2 に残す)。補助管 1(第 4 側)は aux1_u.py。"""
    import aux1_u as A1
    import bb34_u
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    import main_aux as MA

    branch, p0, n0, c0 = bb34_u.make_hook()(M, branch, others)  # 2番管・bb34 も一緒に出す
    allo = others + list(zip(n0, p0)) + [("bell03_branch1_wall", branch)]
    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    rot_deg = arg("--rot", A1.ROT_DEG)
    E, u = MA.f1_225_exit()
    n = A1.plane_normal(u, rot_deg)
    Nb = M[:3, :3] @ np.array([0.0, 0.0, 1.0])  # ベルの芯線の平面の法線
    Pb = B2.branch1_end(M)[0]

    if "--trial" in sys.argv:
        # 試し: 直線 5 + 円弧 R30 + 直線 5、内角 100°、もう一方は +Z 側(aux1_u.arc_pipe)。終点はベルの平面で止めない
        r_arc, inner = arg("--R", A1.ARC_R), arg("--inner", A1.INNER_DEG)
        if "--scan" in sys.argv:  # R ごとの bb34 L 字管・Bb1 外管 R との表面距離
            dd = dict(allo)
            for r_ in (30.0, 46.0):
                w_, F_, tF_, _ = A1.arc_pipe(E, u, n, float(r_), inner)
                t_ = U.const_d_tube(w_, A1.D, BP.WALL, n)
                from OCP.BRepExtrema import BRepExtrema_DistShapeShape
                ex_ = BRepExtrema_DistShapeShape(t_.wrapped, dd["bb34_L_wall"].wrapped)
                ex_.Perform()
                pa, pb = ex_.PointOnShape1(1), ex_.PointOnShape2(1)
                print(f"  nearest to bb34_L: aux1 ({pa.X():.2f}, {pa.Y():.2f}, {pa.Z():.2f}), bb34_L ({pb.X():.2f}, {pb.Y():.2f}, {pb.Z():.2f})")
                print(f"scan R {r_:g}: bb34_L {t_.distance_to(dd['bb34_L_wall']):.3f}, Bb1_outer_R {t_.distance_to(dd['Bb1_outer_tube_R']):.3f}, "
                      f"branch1 {t_.distance_to(branch):.3f}, end {F_.round(2).tolist()}, end vs bell plane {float((F_ - Pb) @ Nb):+.2f}")
        w, F, tF, C = A1.arc_pipe(E, u, n, r_arc, inner)
        print(f"aux1: plane normal {n.round(4).tolist()} (YZ plane rotated {rot_deg:g} deg about the exit axis {u.round(4).tolist()}); E {E.round(3).tolist()}")
        print(f"aux1 (trial): straight {A1.ST:g} + arc R {r_arc:g} (turn {180 - inner:g} deg, inner angle {inner:g}) + straight {A1.ST:g} = {w.length:.3f}; "
              f"end {F.round(3).tolist()}, direction {tF.round(4).tolist()}; arc centre {C.round(3).tolist()}; end vs bell plane {float((F - Pb) @ Nb):+.3f}")
    else:  # ヒントの形(aux1_u.hint_pipe)
        import valve4_knuckle as V

        tilt, inner = arg("--aux1-tilt", A1.HINT_TILT), arg("--inner", A1.HINT_INNER)
        yz1, yz2 = (float(Pb[1]), float(Pb[2])), V.BB34_STRAIGHT_YZ
        st1 = arg("--st1", A1.HINT_ST1)
        if "--dump-aux1" in sys.argv:  # 探索用(tools/aux1_search.py): 端点・軸・ベルの平面
            np.savez(sys.argv[sys.argv.index("--dump-aux1") + 1], E=E, u=u, Pb=Pb, Nb=Nb, yz1=np.array(yz1), yz2=np.array(yz2))
        if "--scan" in sys.argv:  # 枝管側の直線の長さごとの R・隙間
            dd = dict(allo)
            for st_, dy_ in ([(float(x), arg("--dy", A1.HINT_DY)) for x in np.arange(12.5, 16.01, 0.5)] if "--scan-dy" not in sys.argv
                             else [(st1, float(x)) for x in np.arange(0.0, 4.01, 0.5)]):
                ext_ = arg("--ext", A1.HINT_EXT)
                try:
                    w_, i_ = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, inner, tilt, st_, dy_, ext_)
                except Exception as e:  # noqa: BLE001
                    print(f"scan st1 {st_:g}: {e}")
                    continue
                if i_["r"] <= 0:
                    print(f"scan st1 {st_:g}: R {i_['r']:.2f} (no arc)")
                    continue
                t_ = U.const_d_tube(w_, A1.D, BP.WALL, i_["normal"])
                print(f"scan st1 {st_:g} dy {dy_:g}: R {i_['r']:.3f}, end straight {i_['end_straight']:.3f}, length {w_.length:.3f}; bb34_L {t_.distance_to(dd['bb34_L_wall']):.3f}, "
                      f"branch1 {t_.distance_to(branch):.3f}, Bb1_outer_R {t_.distance_to(dd['Bb1_outer_tube_R']):.3f}")
        dy = arg("--dy", A1.HINT_DY)
        ext = arg("--ext", A1.HINT_EXT)
        w, info = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, inner, tilt, st1, dy, ext)
        n = info["normal"]
        F = info["F"]
        print(f"aux1 (hint): YZ points branch1 {np.round(yz1, 3).tolist()}, bb34 straight {np.round(yz2, 3).tolist()}, middle {info['M'].round(3).tolist()}; inner angle {inner:g}, tilt {tilt:g} deg about the exit axis")
        mid_ = (f"G2 spline (7th-degree Bezier, ctrl distances from Q {np.round(A1.HINT_G2, 4).tolist()})" if "ctrl" in info else f"arc R {info['r']:.3f}")
        print(f"aux1 (hint): straight {info['start_straight']:.3f} + {mid_} ({180 - inner:g} deg) + straight {info['end_straight']:.3f} = {w.length:.3f}; corner Q {info['Q'].round(3).tolist()}; "
              f"end F {F.round(3).tolist()} (vs the bell plane {float((F - Pb) @ Nb):+.3f}), direction {info['d'].round(4).tolist()}; plane normal {n.round(4).tolist()}")
    tube = U.const_d_tube(w, A1.D, BP.WALL, n)
    if B2.checks_enabled():  # 近い部品との最近接点(どこで当たるか)
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape

        dd = dict(allo)
        for nm in ("bb34_L_wall", "bell03_branch1_wall", "Bb1_outer_tube_R"):
            ex_ = BRepExtrema_DistShapeShape(tube.wrapped, dd[nm].wrapped)
            ex_.Perform()
            pa = ex_.PointOnShape1(1)
            print(f"  nearest to {nm}: {ex_.Value():.3f} at aux1 ({pa.X():.2f}, {pa.Y():.2f}, {pa.Z():.2f})")
    print(f"aux1 tube: valid {tube.is_valid}, volume {sum(x.volume for x in tube.solids()):.2f}")
    print("clearance aux1:")
    B2.report_clearance(tube, allo)
    p0, n0, c0 = p0 + [tube, w], n0 + ["main_aux1_wall", "main_aux1_centerline"], c0 + ["#20c0a0", "#ff2020"]
    if "--trial" not in sys.argv:  # 補助管 2(aux2_u): 補助管 1 の出口から 1 つの G2 スプラインで +X 向きの口(主管頭平面の上、x = X_END)へ
        import aux2_u as A2

        w2, i2 = A2.aux2_pipe(F, info["d"])
        tube2 = U.const_d_tube(w2, A2.D, BP.WALL, i2["normal"])
        print(f"aux2: start {np.round(F, 3).tolist()} dir {info['d'].round(4).tolist()}; corner Q {i2['Q'].round(3).tolist()} (on the main-bow plane); "
              f"opening {i2['G'].round(3).tolist()} dir [1, 0, 0]; legs {np.round(i2['legs'], 3).tolist()}")
        print(f"aux2: straight {i2['straights'][0]:g} + G2 spline {i2['spline_len']:.3f} (min R {i2['min_r']:.3f}, curvature peak at {i2['k_peak_at']:.2f} of the spline) "
              f"+ straight {i2['straights'][1]:g} = {w2.length:.3f}; ratios {np.round(i2['ratios'], 4).tolist()}")
        print(f"aux2 tube: valid {tube2.is_valid}, volume {sum(x.volume for x in tube2.solids()):.2f}")
        print("clearance aux2:")
        B2.report_clearance(tube2, allo + [("main_aux1_wall", tube)])
        p0, n0, c0 = p0 + [tube2, w2], n0 + ["main_aux2_wall", "main_aux2_centerline"], c0 + ["#20a0c0", "#ff2020"]
    if "--aux1-alt" in sys.argv:  # 比べる形を並べて出す: "傾き,内角,dy,st1;..."(例 0,90,3.265,20.036)
        for k, s_ in enumerate(sys.argv[sys.argv.index("--aux1-alt") + 1].split(";")):
            ta, ia, da, sa = (float(v) for v in s_.split(","))
            wa, ia_ = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, ia, ta, sa, da, 0.0)
            print(f"aux1 alt {k}: tilt {ta:g}, inner {ia:g}, dy {da:g}, st1 {sa:g}: R {ia_['r']:.3f}, end straight {ia_['end_straight']:.3f}, "
                  f"length {wa.length:.3f}, end F {ia_['F'].round(3).tolist()}")
            p0 += [U.const_d_tube(wa, A1.D, BP.WALL, ia_["normal"]), wa]
            n0 += [f"main_aux1_alt_i{ia:g}_wall", f"main_aux1_alt_i{ia:g}_centerline"]
            c0 += [("#4080ff", "#c040ff", "#ff8020")[k % 3], "#ff2020"]
    return branch, p0, n0, c0


def _hook_split_g2(M, branch, others):
    """(使わない)2026-11-24 まで の分割版 aux1・aux2(G2)。新しい補助管 1 は aux1_u.py。"""
    import main_aux as MA
    import bell_place as BP
    import branch2_l as B2
    import branch2_u as U
    from build123d import Edge, Vector, Wire
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
    S_end = ref[-1] + np.array([X_S_SPLIT - MA.X_S, 0.0, 0.0])
    tS = np.array([1.0, 0.0, 0.0])
    print(f"E {E.round(3).tolist()}, S_end {S_end.round(3).tolist()}, reference axis length {np.linalg.norm(np.diff(ref, axis=0), axis=1).sum():.3f}")

    def build_solution():
        lo, hi = np.minimum(E, S_end) - 25, np.maximum(E, S_end) + 25
        pts = []
        for n, sh in allo:
            if n in ("valve4_knuckle_F1_225_twisted",) or n.startswith("main_aux") or n.endswith("centerline") or not hasattr(sh, "bounding_box"):
                continue
            bb = sh.bounding_box(optimal=False)
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
    if AUX2_MID_ANGLE is not None:
        tm0 = tm_of(np.asarray(x[:3], float), E, u, S_end, tS)
        try:
            x[4] = r2_for_angle(np.asarray(x[:3], float), tm0, S_end, tS, AUX2_MID_ANGLE, r_min)
            print(f"aux2 middle straight tilted {AUX2_MID_ANGLE:g} deg from +Z (seen from -Y, + = toward +X): r2 = {x[4]:.4f}")
        except ValueError as e:  # 第 4 を +1 mm 動かした後は区間に解がない。G2 版(既定)は r2 を使わないので、円弧版(--csc)の参考値だけが狂う
            print(f"warning: r2_for_angle: {e}; r2 stays {x[4]:.4f} (only the --csc arc version uses it)")
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

    if "--csc" in sys.argv:
        w1_, w2_ = wire(p1), wire(p2)
        t1, t2 = U.const_d_tube(w1_, D, BP.WALL), U.const_d_tube(w2_, D, BP.WALL)
    else:  # G2 版(スプライン)
        w1_, n1_, k1_, c1_ = g2_piece(E, u, Pm, tm, G2_PRESET["aux1"])
        w2_, n2_, k2_, c2_ = g2_piece(Pm, tm, S_end, tS, G2_PRESET["aux2"])
        t1, t2 = U.const_d_tube(w1_, D, BP.WALL, n1_), U.const_d_tube(w2_, D, BP.WALL, n2_)
        for nm, w_, k_ in (("aux1", w1_, k1_), ("aux2", w2_, k2_)):
            print(f"{nm} G2: length {w_.length:.3f}, curvature ends {k_[0]:.1e} / {k_[-1]:.1e}, min bend R {1 / np.abs(k_).max():.2f}, peaks {k_.max():+.4f} / {k_.min():+.4f}")
        d1_ = cKDTree(ref).query(np.array([[q.X, q.Y, q.Z] for q in (w.position_at(float(s_)) for w in (w1_, w2_) for s_ in np.linspace(0, 1, 150))]))[0]
        print(f"G2 deviation from the unsplit axis: max {d1_.max():.3f}, mean {d1_.mean():.3f}; total length {w1_.length + w2_.length:.3f}")
    for nm, t in (("aux1", t1), ("aux2", t2)):
        print(f"{nm} tube: valid {t.is_valid}, volume {sum(x_.volume for x_ in t.solids()):.2f}")
    print("clearance aux1:")
    B2.report_clearance(t1, [(n, s) for n, s in allo if not n.startswith("main_aux")])
    print("clearance aux2:")
    B2.report_clearance(t2, [(n, s) for n, s in allo if not n.startswith("main_aux")])
    if B2.checks_enabled():
        print(f"aux1-aux2 distance {t1.distance_to(t2):.3f}")
    return (branch, p0k + [t1, t2, w1_, w2_], n0k + ["main_aux1_wall", "main_aux2_wall", "main_aux1_centerline", "main_aux2_centerline"],
            c0k + ["#20c0a0", "#20a0e0", "#ff2020", "#ff2020"])  # 分割点の球(作図用の補助)は出さない


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)


if __name__ == "__main__":
    main()
