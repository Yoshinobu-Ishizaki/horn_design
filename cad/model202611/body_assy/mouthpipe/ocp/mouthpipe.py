"""吹込管(mouthpipe、2026-11-24)。主管抜差の中管 2 の先端から GAP 離した所(太い端、向き -X)から、弁の外側を大きく回って入口(細い端)へ。

条件(ユーザー、image/mouthpipe-image.drawio.png):
1. 芯線は 1 つの平面の中。平面は主管頭平面を、中管 2 の軸(太い端を通る X 方向の直線)まわりに ψ 回した面。
2. 入口の点 M とベル縁の近接点 R を結ぶ線を XY に投影すると、ベルの細い部分(ベル芯線の弧長 NARROW_S 以降 + 1番管)の
   外側の境界にほぼ接し、長さ LEN_XY。
3. 入口側の直線とベルの出口(直線部)の芯線のなす内角 INNER_DEG(3 次元の角)。
4. ψ は、ベル・1番管との表面間距離が CLEAR になるように(ベルへ近づける向き)。
5. 管の太さは bell03 のメンズールの吹込管の区間(RefHorn と同じ)。入口から測った距離で内径を引く(全長の調整は後)。
入口にはマウスピースを 18 mm 差し込み、46 mm 飛び出る(モデルにしない)。

形: 太い端からの直線(-X、ST_MIN 以上)+ 7 次ベジェ(両端で 3 点が直線上 = 直線と G2)+ 入口の直線(ST_MIN 以上)。
ベジェは、両端の直線を長く(W_ST)、曲率の最大と変化を小さく(最小 R は R_MIN 以上)、左端の x を LEFT_X(画像の赤線の左端)に近く、
曲がる向きは一方向(時計回り)に決める。

    uv run python cad/model202611/body_assy/mouthpipe/ocp/mouthpipe.py [--psi 角度(固定)] [--check]
"""

from __future__ import annotations

import math
import sys
from math import comb
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

GAP = 1.0  # 中管 2 の先端から吹込管の太い端まで
LEN_XY = 370.0  # 入口 M とベル縁の近接点 R の XY 投影の長さ
INNER_DEG = 50.0  # 入口側の直線とベルの直線部の芯線の内角。70 → 50(2026-11-24 ユーザー訂正)
CLEAR = 1.4  # ベル・1番管との表面間距離
LEFT_X = -83.0  # 曲線の左端の x の目安(画像の赤線、ローターの中心で縮尺を合わせた値)
ST_MIN = 5.0  # 両端の直線の最小
W_ST = 0.15  # 両端の直線を長くする重み(2026-11-24 ユーザー: 両端は結構長い直線、曲線部だけ G2 スプライン)
R_MIN = 25.0  # 曲線部の最小曲げ半径(仮)
NARROW_S = 280.0  # ベルの細い部分: ベル芯線の弧長(リムから)がこれ以上(直線部は約 250 まで)
NEAR_R = 60.0  # 接する点は R から XY で NEAR_R 以上離れた所(R の近くを通る 1番管を除く)
WALL = 0.4
MEN = ROOT / "impedance/bell03/bell03_Bb.men"
MEN_KEY = "吹込管"


def mensur():
    """(入口からの距離, 内径) の表。"""
    rows = []
    for line in MEN.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split(",")
        if len(c) >= 4 and MEN_KEY in c[3]:
            rows.append((float(c[0]), float(c[1]), float(c[2])))
    s, L, D = 0.0, [0.0], [rows[0][0]]
    for d0, d1, r in rows:
        s += r
        L.append(s)
        D.append(d1)
    return np.array(L), np.array(D)


def bell_data(M):
    """ベル・1番管の表面の点(ベル芯線の弧長つき)、細い部分の XY 凸包、リムの中心・軸・外半径。M ごとにキャッシュ。"""
    import shape_cache as SC

    def build():
        import bell03_surface as BS
        import bell_place as BP
        from aux1_search import face_points
        from make_centerline import build_branch_wire
        from scipy.spatial import ConvexHull, cKDTree

        info = SC.cached("bell03_walls", BP.WALL, ROOT / "cad/bell03/ocp/bell03_surface.py", BP.build_bell)
        bell, br = BP.apply(info["bell"], M), BP.apply(info["branch"], M)
        cl, bcl = BS.centerline(), build_branch_wire()

        def tw(w, n):
            p = np.array([tuple(w.position_at(t)) for t in np.linspace(0, 1, n)])
            return (M[:3, :3] @ p.T).T + M[:3, 3]

        C = np.vstack([tw(cl, 3000), tw(bcl, 2000)])
        Sc = np.concatenate([np.linspace(0, cl.length, 3000), cl.length + np.linspace(0, bcl.length, 2000)])
        P = np.vstack([face_points(f, 0.8) for sh in (bell, br) for f in sh.faces()])
        s = Sc[cKDTree(C).query(P)[1]]
        nar = P[s >= NARROW_S][:, :2]
        hull = nar[ConvexHull(nar).vertices]
        p0, t0 = cl.position_at(0), cl.tangent_at(0)
        rim = M[:3, :3] @ np.array([p0.X, p0.Y, p0.Z]) + M[:3, 3]
        ax = M[:3, :3] @ np.array([t0.X, t0.Y, t0.Z])
        r0 = P[s < 0.3] - rim
        rr = float(np.linalg.norm(r0 - np.outer(r0 @ ax, ax), axis=1).max())
        return dict(P=P.astype(np.float32), hull=hull, rim=rim, ax=ax, rim_r=rr)

    return SC.memo_value("mouthpipe_bell", [round(float(v), 6) for v in M.ravel()] + [NARROW_S, 0.8], __file__, build)


def entry(bd, T, psi):
    """平面(主管頭平面を、T を通る X 軸まわりに psi 度回した面)の上で、条件 2・3 を満たす入口 M・向き e(M へ向かう)・R。"""
    from scipy.optimize import fsolve

    import aux2_u as A2

    X = np.array([1.0, 0.0, 0.0])
    Yp = np.array([0.0, 1.0, A2.MB_A]) / math.hypot(1.0, A2.MB_A)
    c, s_ = math.cos(math.radians(psi)), math.sin(math.radians(psi))
    Yp = np.array([0.0, c * Yp[1] - s_ * Yp[2], s_ * Yp[1] + c * Yp[2]])
    rim, ax, H = bd["rim"], bd["ax"], bd["hull"]
    e1 = np.cross(ax, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    ph = np.linspace(0, 2 * np.pi, 7200, endpoint=False)
    rimpts = rim + bd["rim_r"] * (np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2)

    def Mof(uv):
        return T + uv[0] * X + uv[1] * Yp

    def near_rim(P):
        return rimpts[np.argmin(np.linalg.norm(rimpts - P, axis=1))]

    def F(uv):
        P = Mof(uv)
        R = near_rim(P)
        d = P[:2] - R[:2]
        L = np.linalg.norm(d)
        d /= L
        al = (H - R[:2]) @ d
        m = (al > NEAR_R) & (al < L - 10)
        return [(d[0] * (H[m, 1] - R[1]) - d[1] * (H[m, 0] - R[0])).min(), L - LEN_XY]

    uv = fsolve(F, [145.0, 102.0])
    Mp = Mof(uv)
    th = np.radians(np.arange(-60, 60, 0.001))
    E = np.cos(th)[:, None] * X + np.sin(th)[:, None] * Yp
    ang = np.degrees(np.arccos(np.clip(np.abs(E @ ax), 0, 1)))
    k = np.argmin(np.abs(ang - INNER_DEG) + 1e3 * (np.abs(th) > math.radians(45)))  # +X に近い方(ほぼ水平、画像と同じ)
    return dict(M=Mp, e=E[k], R=near_rim(Mp), uv=uv, res=F(uv), Yp=Yp, angle=float(ang[k]))


def bez(cp, t):
    m = len(cp) - 1
    t = np.asarray(t)[:, None]
    return sum(comb(m, i) * t**i * (1 - t) ** (m - i) * cp[i] for i in range(m + 1))


def curv2(cp, n=500):
    """平面(2 次元)のベジェの符号つき曲率と弧長。"""
    t = np.linspace(0, 1, n)[:, None]
    m = len(cp) - 1
    d1 = sum(comb(m - 1, i) * t**i * (1 - t) ** (m - 1 - i) * m * (cp[i + 1] - cp[i]) for i in range(m))
    d2 = sum(comb(m - 2, i) * t**i * (1 - t) ** (m - 2 - i) * m * (m - 1) * (cp[i + 2] - 2 * cp[i + 1] + cp[i]) for i in range(m - 1))
    sp = np.linalg.norm(d1, axis=1)
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / sp**3
    s = np.concatenate([[0.0], np.cumsum(0.5 * (sp[1:] + sp[:-1]) * np.diff(t[:, 0]))])
    return s, k


def ctrl2(x, uM, e2):
    """x = (s1, s2, a2, ra, b2, rb, p3u, p3v, p4u, p4v)。平面の座標(u = X、v = Yp、原点 = 太い端)。a1 = ra·a2、b1 = rb·b2。"""
    s1, s2, a2, ra, b2, rb, p3u, p3v, p4u, p4v = x
    A = np.array([-s1, 0.0])
    B = uM - s2 * e2
    return np.array([A, A + [-ra * a2, 0.0], A + [-a2, 0.0], [p3u, p3v], [p4u, p4v], B - b2 * e2, B - rb * b2 * e2, B])


def fit_curve(uM, e2, u_left, x0=None):
    """両端の直線を長く、左端 LEFT_X、曲率の大きさ・変化を小さく(最小 R ≥ R_MIN)、時計回りだけ。差分進化。"""
    from scipy.optimize import differential_evolution

    L_e = float(np.linalg.norm(uM))
    tt = np.linspace(0, 1, 300)

    def cost(x):
        s1, s2 = x[:2]
        cp = ctrl2(x, uM, e2)
        s, k = curv2(cp, 300)
        pts = bez(cp, tt)
        dk = np.diff(k) / np.maximum(np.diff(s), 1e-9)
        f = 100 * np.abs(k).max() + 0.3 * float(np.sum(dk**2 * np.diff(s))) * 100 - W_ST * (s1 + s2)
        f += 1e6 * max(0.0, np.abs(k).max() - 1 / R_MIN) ** 2
        f += 1e5 * float(np.maximum(k, 0).max()) ** 2  # 反時計回り(逆向き)の曲がりは不可
        f += 20.0 * (pts[:, 0].min() - u_left) ** 2
        return f

    bounds = [(ST_MIN, 160.0), (ST_MIN, L_e - 20), (1.0, 150.0), (0.05, 0.95), (1.0, 150.0), (0.05, 0.95),
              (-260.0, 0.0), (-60.0, 200.0), (-260.0, 0.0), (-60.0, 200.0)]
    if x0 is not None:  # 近い条件の解から(ψ の探索で)
        from scipy.optimize import minimize

        return minimize(cost, x0, method="Powell", options=dict(maxiter=20000, xtol=1e-5, ftol=1e-9)).x
    r = differential_evolution(cost, bounds, seed=0, popsize=15, maxiter=400, tol=1e-8, polish=True, init="sobol")
    return r.x


def design(bd, T, psi, x0=None):
    """psi のときの芯線(3 次元の点列と制御点など)。"""
    en = entry(bd, T, psi)
    X, Yp = np.array([1.0, 0.0, 0.0]), en["Yp"]
    to2 = lambda p: np.array([(p - T) @ X, (p - T) @ Yp])  # noqa: E731
    uM = to2(en["M"])
    e2 = np.array([en["e"] @ X, en["e"] @ Yp])
    x = fit_curve(uM, e2, LEFT_X - T[0], x0)
    cp2 = ctrl2(x, uM, e2)
    to3 = lambda q: T + q[..., 0, None] * X + q[..., 1, None] * Yp  # noqa: E731
    return dict(en=en, x=x, cp=to3(cp2), cp2=cp2, A=to3(cp2[0]), B=to3(cp2[-1]))


def centerline_points(d, n=1500):
    """太い端 → 入口の点列と、入口からの距離。"""
    T0 = d["A"] + d["x"][0] * np.array([1.0, 0.0, 0.0])
    seg1 = T0 + np.linspace(0, 1, 30)[:, None] * (d["A"] - T0)
    curve = bez(d["cp"], np.linspace(0, 1, n))
    seg2 = d["B"] + np.linspace(0, 1, 60)[:, None] * (d["en"]["M"] - d["B"])
    P = np.vstack([seg1, curve[1:], seg2[1:]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    return P, s[-1] - s


def clearance(bd, tree, d, Lm, Dm):
    P, dist = centerline_points(d)
    od = np.interp(dist, Lm, Dm) + 2 * WALL
    c = tree.query(P)[0] - od / 2
    return float(c.min()), P[int(c.argmin())]


def solve_psi(bd, T):
    from scipy.spatial import cKDTree

    Lm, Dm = mensur()
    tree = cKDTree(bd["P"])
    lo, hi = -8.0, 0.0  # 負がベルへ近づく向き
    d_hi = design(bd, T, hi)
    c_hi = clearance(bd, tree, d_hi, Lm, Dm)[0]
    x0 = d_hi["x"]
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        dm = design(bd, T, mid, x0)
        cm = clearance(bd, tree, dm, Lm, Dm)[0]
        if cm > CLEAR:
            hi, x0 = mid, dm["x"]
        else:
            lo = mid
    return hi, c_hi


def hook(M, branch, others):
    import main_slide as MSL

    branch, p0, n0, c0 = MSL.hook(M, branch, others)
    others = others + list(zip(n0, p0))
    import branch2_l as B2
    import shape_cache as SC
    from bope_claude_cad.vss import variable_pipe_wall
    from build123d import Edge, Vector, Wire

    d_ = dict(zip(n0, p0))
    b2 = d_["main_slide_inner_tube2"].bounding_box(optimal=False)
    T = np.array([b2.min.X - GAP, 0.5 * (b2.min.Y + b2.max.Y), 0.5 * (b2.min.Z + b2.max.Z)])
    bd = bell_data(M)
    if "--psi" in sys.argv:
        psi = float(sys.argv[sys.argv.index("--psi") + 1])
    else:
        psi = SC.memo_value("mouthpipe_psi", [round(float(v), 6) for v in (*T, *M.ravel())] + [CLEAR, LEFT_X, LEN_XY, INNER_DEG], __file__,
                            lambda: solve_psi(bd, T)[0])
    d = SC.memo_value("mouthpipe_design", [round(float(v), 6) for v in (*T, *M.ravel(), psi)] + [LEFT_X, LEN_XY, INNER_DEG], __file__,
                      lambda: design(bd, T, psi))
    en = d["en"]
    T0 = d["A"] + d["x"][0] * np.array([1.0, 0.0, 0.0])
    w = Wire([Edge.make_line(Vector(*T0), Vector(*d["A"])), Edge.make_bezier(*[Vector(*c) for c in d["cp"]]),
              Edge.make_line(Vector(*d["B"]), Vector(*en["M"]))])
    Lm, Dm = mensur()
    s2, k2 = curv2(d["cp2"])
    print(f"mouthpipe: thick end {T0.round(3).tolist()} (inner tube 2 tip - {GAP:g} along X), psi {psi:.3f} deg about the inner-tube-2 axis (main-bow plane rotated)")
    print(f"mouthpipe: entry M {en['M'].round(3).tolist()}, rim point R {en['R'].round(3).tolist()}; |RM| xy {np.linalg.norm(en['M'][:2] - en['R'][:2]):.3f}, 3D {np.linalg.norm(en['M'] - en['R']):.3f}; "
          f"residual {np.round(en['res'], 5).tolist()}; entry direction {en['e'].round(4).tolist()} ({en['angle']:.3f} deg to the bell axis)")
    print(f"mouthpipe: straight {d['x'][0]:.3f} + Bezier (deg 7) {s2[-1]:.3f} (min R {1 / np.abs(k2).max():.2f}, max ccw curvature {max(k2.max(), 0):.2e}) + straight {d['x'][1]:.3f} = {w.length:.3f} "
          f"(mensur section {Lm[-1]:.2f}); leftmost x {bez(d['cp'], np.linspace(0, 1, 400))[:, 0].min():.2f} (target {LEFT_X:g})")
    # 管: 太い端からの距離 L → 入口からの距離 total - L で内径を引く
    total = w.length
    Lw = np.linspace(0, total, 301)
    Dw = np.interp(total - Lw, Lm, Dm)
    tube = SC.cached("mouthpipe_tube", [round(float(v), 5) for v in (*T0, *d["cp"].ravel(), *en["M"])] + [WALL],
                     __file__, lambda: variable_pipe_wall(w, Lw, Dw, WALL, method="sweep")[0])
    print(f"mouthpipe tube: ID {Dw[0]:.2f} (thick end) -> {Dw[-1]:.2f} (entry), wall {WALL:g}, valid {tube.is_valid}")
    if B2.checks_enabled():
        print(f"mouthpipe: surface distance to bell {tube.distance_to(dict(others)['bell03_bell_wall']):.3f}, to branch1 {tube.distance_to(branch):.3f} (target {CLEAR:g})")
    print("clearance (mouthpipe):")
    B2.report_clearance(tube, others + [("bell03_branch1_wall", branch)])
    return branch, p0 + [tube, w], n0 + ["mouthpipe_wall", "mouthpipe_centerline"], c0 + ["#e0a020", "#ff2020"]


def main() -> None:
    import assy_with_valves as AW

    AW.main(hook=hook)
    __import__("shape_cache").phase("show done")


if __name__ == "__main__":
    main()
