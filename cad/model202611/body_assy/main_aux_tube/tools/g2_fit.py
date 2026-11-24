"""補助管 1・2 の中間部(両端の直線の間)を、平面内の G2 連続な 7 次ベジェに置き換える探索。今の「直線+円弧+直線+円弧+直線」の芯線に近く、
両端は曲率 0(= 直線と G2 でつながる)、最小曲げ半径 ≥ R_MIN、障害物との隙間 ≥ 下限になるよう差分進化で決める。
障害物の頂点群は `main_aux_split.py --search --dump` が /tmp/claude-1000/split_obs.npy に保存したもの。結果は main_aux_split.G2_PRESET に書き写す。

    uv run python cad/model202611/body_assy/main_aux_tube/tools/g2_fit.py [隙間の下限 0.3] [最小半径 10]
"""
import sys, math, time, numpy as np
from pathlib import Path
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == "model202611")))
import model_paths  # noqa: E402

ROOT = model_paths.add()
import main_aux_split as S
from scipy.optimize import differential_evolution
from scipy.spatial import cKDTree

gap_req = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
r_min = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
obs = np.load("/tmp/claude-1000/split_obs.npy")
tree = cKDTree(obs)
ref = np.load("/tmp/claude-1000/split_ref.npy")
import main_aux as MA
E, u = MA.f1_225_exit()
S_end = ref[-1] + np.array([S.X_S_SPLIT - MA.X_S, 0, 0])
tS = np.array([1.0, 0, 0])
x = list(S.PRESET)
x[4] = S.r2_for_angle(np.array(x[:3]), S.tm_of(np.array(x[:3]), E, u, S_end, tS), S_end, tS, S.AUX2_MID_ANGLE, r_min)
Pm, tm, p1, p2 = S.build(x, E, u, S_end, tS)
T = np.linspace(0, 1, 120)


def bez(P, t):
    n = len(P) - 1
    from math import comb
    B = np.array([comb(n, i) * t**i * (1 - t) ** (n - i) for i in range(n + 1)])
    return B.T @ P


def kappa(P, t):
    n = len(P) - 1
    d1 = n * np.diff(P, axis=0)
    d2 = (n - 1) * np.diff(d1, axis=0)
    a, b = bez(d1, t), bez(d2, t)
    return (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) / np.linalg.norm(a, axis=1) ** 3


def frame(A, d1, B, d2, pts_ref):
    A2 = A + 0  # A: 曲線の始点(直線の終わり)、B: 終点
    nrm = np.cross(d1, B - A)
    nrm /= np.linalg.norm(nrm)
    ex, ey = d1, np.cross(nrm, d1)
    return ex, ey, nrm


def ctrl(v, G, th):
    a, db, c, dc, q3x, q3y, q4x, q4y = v  # b = a + db, e = c + dc(曲率 0 の端で P0,P1,P2 が直線上、順序を保つ)
    b, e = a + db, c + dc
    d2 = np.array([math.cos(th), math.sin(th)])
    return np.array([[0, 0], [a, 0], [b, 0], [q3x, q3y], [q4x, q4y], G - e * d2, G - c * d2, G])


def fit(A0, d1, B0, d2, ref_full, s0, s1, ext=0.0, ext2=0.0, unimodal=False, seed=0, warm=None):
    """A0 から st(s0 以上 s0 + ext 以下)の直線のあとに G2 曲線(7 次ベジェ)、終点 B(向き d2)。参照 ref_full は直線を含む全体の点列。"""
    nrm = np.cross(d1, B0 - A0)
    nrm /= np.linalg.norm(nrm)
    ex, ey = d1, np.cross(nrm, d1)
    th = math.atan2(float(d2 @ ey), float(d2 @ ex))
    tr = cKDTree(ref_full)
    to3 = lambda q, A: A + q[:, 0:1] * ex + q[:, 1:2] * ey  # noqa: E731
    L = np.linalg.norm(B0 - A0)

    def geom(v):
        st, en = v[8], v[9]
        B = B0 - en * d2
        A = A0 + st * d1
        G = np.array([(B - A) @ ex, (B - A) @ ey])
        P = ctrl(v[:8], G, th)
        C = to3(bez(P, T), A)
        line = A0 + np.outer(np.linspace(0, st, max(2, int(st / 1.5) + 1)), d1)
        endl = B + np.outer(np.linspace(0, 1, 4), B0 - B)
        return P, C, np.vstack([line, C, endl])

    def cost(v):
        P, C, W = geom(v)
        d_a = tr.query(W)[0]
        d_b = cKDTree(W).query(ref_full)[0]
        dev = d_a.mean() + d_b.mean() + 0.5 * max(d_a.max(), d_b.max())
        kap = kappa(P, T)
        pen_r = 400 * max(0, np.abs(kap).max() - 1 / r_min) / (1 / r_min)
        tv = np.abs(np.diff(kap)).sum()
        ideal = 2 * max(kap.max(), 0) + 2 * max(-kap.min(), 0)
        pen_u = 400 * (tv - ideal) / (1 / r_min)
        if not unimodal:  # 補助管 2: S 字。正負の曲率の山の大きさをそろえる(180° 回転対称に近づける。両端の向きが違うので厳密には不可)
            pen_u += 100 * abs(kap.max() + kap.min()) / (1 / r_min)
        if unimodal:  # 補助管 1: 曲がる向きは 1 つ、曲率の分布は左右対称
            pen_u += 100 * np.abs(kap - kap[::-1]).max() / (1 / r_min)
            pen_u += 400 * max(0, -kap.min()) / (1 / r_min)
        gap = tree.query(W)[0].min() - S.D / 2 - 0.4
        return dev + pen_r + pen_u + 1500 * max(0, gap_req - gap)

    bnd = [(0.1, L / 2), (0.0, L / 2), (0.1, L / 2), (0.0, L / 2)] + [(-L, L)] * 4 + [(s0, s0 + ext + 1e-9), (s1, s1 + ext2 + 1e-9)]
    rng = np.random.default_rng(seed)
    init = np.array([[rng.uniform(lo, hi) for lo, hi in bnd] for _ in range(200)])
    if warm is not None:
        for i in range(100):
            init[i] = np.clip(np.asarray(warm) + rng.normal(0, 0.03 + 0.04 * (i // 20), len(warm)) * np.array([5] * 8 + [3, 3]), [b[0] for b in bnd], [b[1] for b in bnd])
        init[0] = np.clip(np.asarray(warm), [b[0] for b in bnd], [b[1] for b in bnd])
    res = differential_evolution(cost, bnd, seed=seed, init=init, maxiter=250, tol=1e-10, polish=False)
    v = res.x
    P, C, W = geom(v)
    kap = kappa(P, T)
    d_a, d_b = tr.query(W)[0], cKDTree(W).query(ref_full)[0]
    ext_ = [q for q in range(1, len(kap) - 1) if (kap[q] - kap[q - 1]) * (kap[q + 1] - kap[q]) < 0]
    gap = tree.query(W)[0].min() - S.D / 2 - 0.4
    ln = float(np.linalg.norm(np.diff(W, axis=0), axis=1).sum())
    return v, dict(cost=res.fun, minR=1 / np.abs(kap).max(), extrema=len(ext_), straight=v[8], end_straight=v[9], gap=gap, dev_max=max(d_a.max(), d_b.max()), dev_mean=(d_a.mean() + d_b.mean()) / 2, length=ln)


if __name__ == "__main__":
    # 中間部 = 両端の直線の間(csc_path の点列から、始点側 st_start・終点側 st_end の直線を除く)
    WARM = {"aux1": [2.9763, 10.2009, 0.6245, 2.0575, 14.4097, 6.6772, 15.9019, 4.6957, 4.0, 4.0], "aux2": [2.9103, 16.9823, 2.9498, 18.9859, 11.0377, 18.8223, 16.1982, 8.281, 5.0, 5.0]}
    for nm, p, A0, d1, B0, d2, s0, s1, ext in (("aux1", p1, E, u, Pm, tm, 4.0, 4.0, 12.0), ("aux2", p2, Pm, tm, S_end, tS, 5.0, 5.0, 12.0)):
        if ("--aux1" in sys.argv and nm != "aux1") or ("--aux2" in sys.argv and nm != "aux2"):
            continue
        t0 = time.time()
        v, info = fit(A0, d1, B0, d2, p["P"], s0, s1, ext, ext, unimodal=(nm == "aux1"), warm=WARM[nm])
        print(nm, "v =", np.round(v, 4).tolist(), {k: round(float(x_), 3) for k, x_ in info.items()}, f"t {time.time() - t0:.0f}s", flush=True)
        print(nm, "current length (without the end straight)", round(p["length"] - s1, 3))
