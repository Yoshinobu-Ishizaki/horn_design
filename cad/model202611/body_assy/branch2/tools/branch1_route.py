"""1番管の新しい道筋(設計の座標、z = 0 の平面。bell03 の芯線とメンズールを使う。cad/bell03 は直さない)。

1. A: bell03 の 1番管の渦巻き(内側の円の半径を BRANCH_DRI·s² で減らす)を、ベルとの隙間が最小(1.4)になる所まで。
   (今の 1番管は、ここで R50 の円弧でベルから離れていく。それをやめる)
2. B: ベルの曲げの内側の表面(直管部の側面から、円板 R137.5 に沿う面)との隙間を GAP に保ったまま、上へ進む。
   ベルの芯線の L で SIGMA_TURN まで。
3. C: 右下へ向きを変えて、今の横の直線(組立姿勢で +X、円板の中心より BRANCH_END_DY 上)につなぐ。
   5 次ベジエで、B の端で位置・接線・曲率が連続(G2)、直線の側で曲率 0(G2)。
4. 直線: 今の 1番管の末端の直線と同じ直線の上を、末端(または 2番管との接続点)まで。

    uv run python cad/model202611/body_assy/branch2/tools/branch1_route.py
"""

from __future__ import annotations

import sys
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()

WALL = 0.4
GAP = 1.4  # ベルの外面と 1番管の外面の距離
BRANCH_ARC_R = 50.0  # 今の 1番管の円弧の半径(make_centerline.BRANCH_ARC_R。今の長さの計算だけに使う)
STRAIGHT = 250.0  # bell03 の直管部(make_centerline.STRAIGHT)


def _bell():
    from make_centerline import STRAIGHT as ST
    from make_centerline import TOTAL, geometry
    from make_mensur import X_END, diameter

    assert ST == STRAIGHT
    g = geometry()
    return g, TOTAL, (lambda ll: diameter(np.minimum(np.asarray(ll, float), X_END)))


def bell_point(g, ll):
    """ベルの芯線の位置と単位接線(L は 0〜TOTAL)。直管部は (0, L)、その先は渦巻きの細かい点列から内挿。"""
    ll = np.atleast_1d(np.asarray(ll, float))
    ls, P, T = g["L_fine"], g["fine"], g["tan_fine"]
    p = np.column_stack([np.interp(ll, ls, P[:, 0]), np.interp(ll, ls, P[:, 1])])
    t = np.column_stack([np.interp(ll, ls, T[:, 0]), np.interp(ll, ls, T[:, 1])])
    s = ll <= STRAIGHT
    p[s] = np.column_stack([np.zeros(s.sum()), ll[s]])
    t[s] = (0.0, 1.0)
    return p, t / np.linalg.norm(t, axis=1)[:, None]


def arclen(p):
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])


def segment_ab(sigma_turn, n_b=1200):
    """A と B の点列(2D)、各点の 1番管の L(リムから)、B の端の接線・曲率。"""
    from scipy.spatial import cKDTree

    g, total, D = _bell()
    # ベルの曲げの内側の外面(進む向きの右の法線の側。直管部では +x 側)
    lb = np.linspace(0.0, total, 8401)
    pb, tb = bell_point(g, lb)
    nb = np.column_stack([tb[:, 1], -tb[:, 0]])
    surf = pb + nb * (D(lb) / 2 + WALL)[:, None]
    tree = cKDTree(surf)
    # A: 1番管の渦巻き(ベルの終点から)。ベルとの隙間が最小の所まで
    ls, P = g["L_fine"], g["fine"]
    m = ls > total
    la, pa = ls[m], P[m]
    gap = tree.query(pa)[0] - (D(la) / 2 + WALL)
    ic = int(np.argmin(np.where(la > total + 150.0, gap, np.inf)))
    sig0 = float(lb[tree.query(pa[ic])[1]])
    la, pa = la[: ic + 1], pa[: ic + 1]
    # B: ベルの芯線の L = sig0 .. sigma_turn で、ベルの芯線から右の法線の側へ、
    # ベルの半径 + 板厚 + GAP + 板厚 + 1番管の半径 だけ離れた点。1番管の半径は、その点の 1番管の L で決まる
    sig = np.linspace(sig0, sigma_turn, n_b)
    ps, ts = bell_point(g, sig)
    ns = np.column_stack([ts[:, 1], -ts[:, 0]])
    off0 = D(sig) / 2 + WALL + GAP + WALL
    db = np.full(n_b, float(D(la[-1])))
    for _ in range(4):  # 1番管の直径は、B の長さに沿った L で決まるので、数回くり返して合わせる
        pbb = ps + ns * (off0 + db / 2)[:, None]
        lbb = la[-1] + arclen(np.vstack([pa[-1], pbb]))[1:]
        db = D(lbb)
    pts = np.vstack([pa, pbb])
    L = np.concatenate([la, lbb])
    # B の端の接線と曲率(数値)
    d1 = np.gradient(pbb, axis=0)
    d2 = np.gradient(d1, axis=0)
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.linalg.norm(d1, axis=1) ** 3
    t_end = d1[-1] / np.linalg.norm(d1[-1])
    return dict(pts=pts, L=L, i_b=len(pa), sig0=sig0, sig_max=sigma_turn, gap_a=float(gap[ic]), t_end=t_end, k_end=float(np.median(k[-20:])),
                g=g, total=total, D=D, tree=tree)


def line_frame(g):
    """今の 1番管の末端の直線: 始点(今の円弧の終点)と向き(単位)。"""
    l0, l1 = g["line"]
    u = (l1 - l0) / np.linalg.norm(l1 - l0)
    return np.asarray(l0, float), u


def bezier_c(p0, t0, k0, q, u, a, b, n=1201):
    """C: 5 次ベジエ。始点で位置・接線・曲率(符号つき k0、左回りが正)、終点で位置・接線・曲率 0。"""
    nrm = np.array([-t0[1], t0[0]])
    h = 1.25 * k0 * a * a  # κ(0) = (4/5)·h/a²
    cp = np.array([p0, p0 + a * t0, p0 + 2 * a * t0 + h * nrm, q - 2 * b * u, q - b * u, q])
    s = np.linspace(0, 1, n)[:, None]
    return cp, sum(comb(5, i) * s**i * (1 - s) ** (5 - i) * cp[i] for i in range(6))


def curvature(p):
    d1 = np.gradient(p, axis=0)
    d2 = np.gradient(d1, axis=0)
    return (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.linalg.norm(d1, axis=1) ** 3


def design_c(ab, tau_max, n_opt=401):
    """C の a・b・接続点 τ(直線の始点からの距離)を、C の最小曲げ半径が最大になるように選ぶ。"""
    from scipy.optimize import minimize

    g = ab["g"]
    l0, u = line_frame(g)
    p0, t0, k0 = ab["pts"][-1], ab["t_end"], ab["k_end"]

    def f(x):
        a, b, tau = x
        if a <= 1 or b <= 1 or tau > tau_max or tau < -100:
            return 1e6
        _, pc = bezier_c(p0, t0, k0, l0 + tau * u, u, a, b, n_opt)
        k = np.abs(curvature(pc))[3:-3]
        # ベルとの隙間(ベルの外面の点群からの距離 - 1番管の外半径)が GAP を下回らないこと
        gap = ab["tree"].query(pc)[0] - (ab["D"](ab["L"][-1]) / 2 + WALL)
        pen = max(0.0, GAP - float(gap[20:].min()))
        return float(k.max()) + 10.0 * pen
    best = min((minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-7, "maxiter": 4000})
                for x0 in [(30, 30, 0.6 * tau_max), (50, 40, 0.4 * tau_max), (20, 60, 0.8 * tau_max)]), key=lambda r: r.fun)
    a, b, tau = best.x
    cp, pc = bezier_c(p0, t0, k0, l0 + tau * u, u, a, b)
    k = curvature(pc)
    return dict(cp=cp, pts=pc, a=a, b=b, tau=tau, r_min=1 / np.abs(k[3:-3]).max(), q=l0 + tau * u, u=u, l0=l0)


def cut_ab(ab, sigma_turn):
    """segment_ab を、B の途中(ベルの芯線の L = sigma_turn)で切ったもの。B の端の接線・曲率もそこで取り直す。"""
    ib = ab["i_b"]
    nb = len(ab["pts"]) - ib
    sig = np.linspace(ab["sig0"], ab["sig_max"], nb)
    j = ib + max(3, int(np.searchsorted(sig, sigma_turn)))
    out = dict(ab, pts=ab["pts"][:j], L=ab["L"][:j])
    seg = out["pts"][-12:]
    d1 = np.gradient(seg, axis=0)
    d2 = np.gradient(d1, axis=0)
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.linalg.norm(d1, axis=1) ** 3
    out["t_end"] = d1[-2] / np.linalg.norm(d1[-2])
    out["k_end"] = float(np.median(k[2:-2]))
    return out


def solve_route(gain, tau_q, sigma_max=420.0, straight_end=30.0):
    """1番管の長さ(ベルの終点から、直線上の点 τ_q まで)が、今の 1番管より gain だけ長くなる道筋。
    変数は SIGMA_TURN・C の a・b・接続点 τ1。細い端に、長さ straight_end 以上の横の直線を必ず残す(τ1 ≤ τ_q - straight_end)。
    C の最小曲げ半径が最大になるように選ぶ。"""
    from scipy.optimize import minimize

    ab0 = segment_ab(sigma_max)
    ab0["sig_max"] = sigma_max
    g, total = ab0["g"], ab0["total"]
    l0, u = line_frame(g)
    old = g["l_exit"] - total + BRANCH_ARC_R * g["arc_sweep"] + tau_q
    target = old + gain
    ro = float(ab0["D"](ab0["L"][-1])) / 2 + WALL

    def evaluate(x, n=401):
        st, a, b, tau1 = x
        if not (ab0["sig0"] + 2 < st < sigma_max - 2) or a <= 1 or b <= 1 or tau1 > tau_q - straight_end or tau1 < -80:
            return None
        ab = cut_ab(ab0, st)
        _, pc = bezier_c(ab["pts"][-1], ab["t_end"], ab["k_end"], l0 + tau1 * u, u, a, b, n)
        length = ab["L"][-1] - total + float(arclen(pc)[-1]) + (tau_q - tau1)
        k = np.abs(curvature(pc))[3:-3]
        gap = float(ab["tree"].query(pc)[0][20:].min()) - ro
        return ab, pc, length, 1 / k.max(), gap

    def f(x):
        e = evaluate(x)
        if e is None:
            return 1e6
        _, _, length, r, gap = e
        # 長さは target 以上を強く(足りない分は 1 mm で 1000)、超える分は弱く罰する
        return -r + 1000.0 * max(0.0, target - length) ** 2 + 0.5 * max(0.0, length - target) ** 2 \
            + 100.0 * max(0.0, GAP - gap) ** 2
    t_hi = tau_q - straight_end
    starts = [(st, a, b, t) for st in (270, 310, 350) for a, b, t in ((40, 20, t_hi - 20), (60, 30, t_hi - 2))]
    best = min((minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-6, "maxiter": 6000})
                for x0 in starts), key=lambda r: r.fun)
    ab, pc, length, r, gap = evaluate(best.x, n=2001)
    st, a, b, tau1 = best.x
    cp, _ = bezier_c(ab["pts"][-1], ab["t_end"], ab["k_end"], l0 + tau1 * u, u, a, b)
    return dict(ab=ab, cp=cp, c_pts=pc, sigma_turn=st, a=a, b=b, tau1=tau1, tau_q=tau_q, length=length, target=target,
                old=old, r_min=r, gap_c=gap, l0=l0, u=u)


def route(sigma_turn, tau_max):
    ab = segment_ab(sigma_turn)
    c = design_c(ab, tau_max)
    len_ab = ab["L"][-1] - ab["total"]
    len_c = float(arclen(c["pts"])[-1])
    return ab, c, len_ab, len_c


def main() -> None:
    g, total, D = _bell()
    l0, u = line_frame(g)
    old_end_tau = g["straight_len"]
    print(f"line start {l0.round(3).tolist()}, dir {u.round(4).tolist()}, old straight {old_end_tau:.3f}")
    for st in (300.0, 350.0, 400.0, 450.0, 500.0):
        ab, c, la, lc = route(st, tau_max=old_end_tau - 110.0)
        to_tau = la + lc  # 1番管の L(ベルの終点から)の、直線上の点 τ まで
        print(f"sigma_turn {st:5.0f}: A gap {ab['gap_a']:.3f} at bell L {ab['sig0']:.1f}; A+B {la:7.2f}, C {lc:6.2f} "
              f"(a {c['a']:.1f} b {c['b']:.1f} tau {c['tau']:.1f}, R_min {c['r_min']:.1f}); branch1 length to tau = "
              f"{to_tau:.2f} (old to the same tau {g['l_exit'] - total + 50 * g['arc_sweep'] + c['tau']:.2f})")


if __name__ == "__main__":
    main()
