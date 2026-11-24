"""補助管 1(aux1_u.hint_pipe)の探索(2026-11-24): 1番管との隙間を最大に、bb34 L とはほぼ接触(0〜0.2)、面を接続軸まわりに倒す。

変数: 傾き tilt・内角 inner・直線の通る点の Y ずらし dy・枝管側の直線 st1(R は inner・dy・st1 で決まる)。
隙間は、近くの部品の面を UV で細かく点にして KD 木で引く(芯線からの距離 - 外半径 6.4)。最後に管を作って厳密に測る。

前準備(端点・軸・ベルの平面を保存):
    python3 cad/valves/ocp/warm.py run cad/main_aux_tube/ocp/main_aux_split.py --dump-aux1 $PWD/output/cache/aux1_geom.npz
実行(部品は output/viewer_registry の、いま表示している形を使う):
    python3 cad/valves/ocp/warm.py run cad/main_aux_tube/tools/aux1_search.py [--minutes 40]
"""

from __future__ import annotations


import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cad/main_aux_tube/ocp"), str(ROOT / "cad/branch2/ocp"), str(ROOT / "cad/valves/ocp")]

RO = 6.4  # 外半径
BOX = ((40.0, 78.0), (-72.0, -8.0), (10.0, 90.0))  # aux1 のまわり
SKIP = ("main_aux", "centerline", "valve4_knuckle_F1_225_twisted")  # 自分と、つながる枝管
STEP = 0.15  # 面の点の間隔
BB34_RANGE = (0.03, 0.17)  # 点群での bb34 L の隙間(厳密値で 0〜0.2 に入るよう少し内側)
OTHER_MIN = 0.08
R_MIN = 10.0


def face_points(face, step=STEP):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools

    s = BRepAdaptor_Surface(face.wrapped)
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face.wrapped)

    def length(fixed_u, a, b, other):
        ts = np.linspace(a, b, 25)
        p = np.array([[*s.Value(t, other).Coord()] if fixed_u else [*s.Value(other, t).Coord()] for t in ts])
        return np.linalg.norm(np.diff(p, axis=0), axis=1).sum()

    lu = max(length(True, u0, u1, v) for v in (v0, 0.5 * (v0 + v1), v1))
    lv = max(length(False, v0, v1, u) for u in (u0, 0.5 * (u0 + u1), u1))
    nu, nv = max(2, int(lu / step) + 2), max(2, int(lv / step) + 2)
    if nu * nv > 3_000_000:
        nu, nv = min(nu, 1500), min(nv, 2000)
    out = np.empty((nu * nv, 3))
    k = 0
    for u in np.linspace(u0, u1, nu):
        for v in np.linspace(v0, v1, nv):
            out[k] = s.Value(u, v).Coord()
            k += 1
    return out


def obstacles():
    from build123d import import_brep

    lo, hi = np.array([b[0] for b in BOX]), np.array([b[1] for b in BOX])
    res = {}
    for f in sorted((ROOT / "output/viewer_registry").glob("*.brep")):
        if any(k in f.name for k in SKIP):
            continue
        sh = import_brep(str(f))
        bb = sh.bounding_box()
        if np.any(np.array([bb.max.X, bb.max.Y, bb.max.Z]) < lo) or np.any(np.array([bb.min.X, bb.min.Y, bb.min.Z]) > hi):
            continue
        pts = []
        for fc in sh.faces():
            b = fc.bounding_box()
            if np.any(np.array([b.max.X, b.max.Y, b.max.Z]) < lo) or np.any(np.array([b.min.X, b.min.Y, b.min.Z]) > hi):
                continue
            p = face_points(fc)
            pts.append(p[np.all((p >= lo) & (p <= hi), axis=1)])
        if pts and sum(len(p) for p in pts):
            res[f.stem] = np.vstack(pts)
    return res


def main():
    import aux1_u as A1
    from scipy.optimize import differential_evolution
    from scipy.spatial import cKDTree

    arg = lambda k, d: float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d  # noqa: E731
    minutes = arg("--minutes", 40.0)
    g = np.load(ROOT / "output/cache/aux1_geom.npz")
    E, u, Pb, Nb, yz1, yz2 = (g[k] for k in ("E", "u", "Pb", "Nb", "yz1", "yz2"))
    t0 = time.time()
    cache = ROOT / "output/cache/aux1_obstacles.npz"
    if cache.exists() and "--rebuild" not in sys.argv:
        obs = dict(np.load(cache))
    else:
        obs = obstacles()
        np.savez(cache, **obs)
    trees = {k: cKDTree(v) for k, v in obs.items()}
    print(f"obstacles ({time.time() - t0:.1f} s): " + ", ".join(f"{k} {len(v)}" for k, v in obs.items()), flush=True)

    if "--g2" in sys.argv:
        return g2_main(A1, E, u, Pb, Nb, yz1, yz2, obs, trees, minutes)

    def path(x):
        tilt, inner, dy, st = x
        w, info = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, inner, tilt, st, dy, 0.0)
        n = max(200, int(w.length / 0.1))
        p = np.array([tuple(w.position_at(t)) for t in np.linspace(0, 1, n)])
        return w, info, p

    def clear(p):
        return {k: float(t.query(p, distance_upper_bound=RO + 5)[0].min()) - RO for k, t in trees.items()}

    def cost(x, detail=False):
        try:
            w, info, p = path(x)
        except Exception:  # noqa: BLE001
            return 1e3
        if not (info["r"] > 0):
            return 1e3
        c = clear(p)
        cb = c.get("bell03_branch1_wall", 99.0)
        bb = c.get("bb34_L_wall", 99.0)
        pen = 0.0
        pen += 50 * max(0.0, BB34_RANGE[0] - bb) + 50 * max(0.0, bb - BB34_RANGE[1])
        for k, v in c.items():
            if k not in ("bell03_branch1_wall", "bb34_L_wall"):
                pen += 50 * max(0.0, OTHER_MIN - v)
        pen += 5 * max(0.0, R_MIN - info["r"])
        f = -min(cb, 3.0) + 0.05 * min(c.get("Bb1_outer_tube_R", 0.0), 3.0) + pen
        if detail:
            return f, w, info, c
        return f

    results = []
    inners = [float(v) for v in sys.argv[sys.argv.index("--inners") + 1].split(",")] if "--inners" in sys.argv else [None]
    runs = [(f"inner {i:g} " if i else "", tb, i) for i in inners for tb in ((-9.0, -3.0), (3.0, 9.0)) if ("--plus" not in sys.argv or tb[0] > 0)]
    runs = [(f"{nm}tilt {'+' if tb[0] > 0 else '-'}", tb, i) for nm, tb, i in runs]
    if "--tilts" in sys.argv:  # 傾きを固定して、それぞれ dy・st1 を探す
        tl = [float(v) for v in sys.argv[sys.argv.index("--tilts") + 1].split(",")]
        runs = [(f"inner {i:g} tilt {t:g}", (t - 1e-6, t + 1e-6), i) for i in inners for t in tl]
    per = minutes * 60 / len(runs)
    for nm, tb, inner_fix in runs:
        t1 = time.time()
        bounds = [tb, (inner_fix - 1e-6, inner_fix + 1e-6) if inner_fix else (60.0, 110.0), (-3.0, 8.0), (5.0, 32.0)]
        best = {"f": 1e9}

        def cb_(xk, convergence=0.0):
            return time.time() - t1 > per

        r = differential_evolution(cost, bounds, seed=1, popsize=15, maxiter=400, tol=1e-6, polish=False, callback=cb_,
                                   init="sobol", x0=[0.5 * (tb[0] + tb[1]), inner_fix or 80.0, 2.5, 20.0])
        f, w, info, c = cost(r.x, True)
        best.update(f=f)
        print(f"[{nm}] {time.time() - t1:.0f} s, nfev {r.nfev}: tilt {r.x[0]:.3f}, inner {r.x[1]:.3f}, dy {r.x[2]:.3f}, st1 {r.x[3]:.3f}; "
              f"R {info['r']:.3f}, end straight {info['end_straight']:.3f}, length {w.length:.3f}; cost {f:.4f}", flush=True)
        print("   cloud clearance: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(c.items(), key=lambda kv: kv[1]) if v < 5), flush=True)
        results.append((f, nm, r.x))

    # 厳密な確認(管を作って distance_to)
    import bell_place as BP
    import branch2_u as U
    from build123d import import_brep

    reg = ROOT / "output/viewer_registry"
    for f, nm, x in sorted(results):
        w, info = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, x[1], x[0], x[3], x[2], 0.0)
        tube = U.const_d_tube(w, A1.D, BP.WALL, info["normal"])
        ex = {k: tube.distance_to(import_brep(str(reg / f"{k}.brep"))) for k in obs}
        print(f"[{nm}] exact: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(ex.items(), key=lambda kv: kv[1]) if v < 5), flush=True)
        print(f"   --aux1-tilt {x[0]:.3f} --inner {x[1]:.3f} --dy {x[2]:.3f} --st1 {x[3]:.3f}; end F {info['F'].round(3).tolist()}, "
              f"end vs bell plane {float((info['F'] - Pb) @ Nb):+.3f}, direction {info['d'].round(4).tolist()}", flush=True)
    print(f"total {time.time() - t0:.0f} s")


def bezier_min_radius(cp, n=400):
    """7 次ベジェの最小曲率半径。"""
    from math import comb

    t = np.linspace(0, 1, n)[:, None]
    m = len(cp) - 1
    d1 = sum(comb(m - 1, i) * t**i * (1 - t) ** (m - 1 - i) * m * (cp[i + 1] - cp[i]) for i in range(m))
    d2 = sum(comb(m - 2, i) * t**i * (1 - t) ** (m - 2 - i) * m * (m - 1) * (cp[i + 2] - 2 * cp[i + 1] + cp[i]) for i in range(m - 1))
    k = np.linalg.norm(np.cross(d1, d2), axis=1) / np.linalg.norm(d1, axis=1) ** 3
    return 1 / max(k.max(), 1e-12)


def g2_main(A1, E, u, Pb, Nb, yz1, yz2, obs, trees, minutes):
    """円弧を G2 スプライン(aux1_u.HINT_G2)に。変数: dy、d0、比 a・b・c(d1 = a·d0、d2 = b·d1、d3 = c·d2)。内角・傾きは既定。"""
    from scipy.optimize import differential_evolution

    START_MIN = 4.0  # 枝管側の直線の下限

    def make(x):
        dy, d0, a, b, c = x
        g = (d0, a * d0, a * b * d0, a * b * c * d0)
        w, info = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, A1.HINT_INNER, A1.HINT_TILT, A1.HINT_ST1, dy, 0.0, g2=g)
        return w, info, g

    def cost(x, detail=False):
        try:
            w, info, g = make(x)
        except Exception:  # noqa: BLE001
            return 1e3
        n = max(200, int(w.length / 0.1))
        p = np.array([tuple(w.position_at(t)) for t in np.linspace(0, 1, n)])
        c = {k: float(t.query(p, distance_upper_bound=RO + 5)[0].min()) - RO for k, t in trees.items()}
        rmin = bezier_min_radius(info["ctrl"])
        cb, bb = c.get("bell03_branch1_wall", 99.0), c.get("bb34_L_wall", 99.0)
        pen = 50 * max(0.0, BB34_RANGE[0] - bb) + 50 * max(0.0, bb - BB34_RANGE[1])
        pen += sum(50 * max(0.0, OTHER_MIN - v) for k, v in c.items() if k not in ("bell03_branch1_wall", "bb34_L_wall"))
        pen += 5 * max(0.0, R_MIN - rmin) + 20 * max(0.0, START_MIN - info["start_straight"])
        f = -min(cb, 3.0) + pen
        return (f, w, info, g, c, rmin) if detail else f

    t1 = time.time()
    s0 = A1.hint_pipe(E, u, yz1, yz2, Pb, Nb, A1.HINT_INNER, A1.HINT_TILT, A1.HINT_ST1, A1.HINT_DY, 0.0, g2=None)[1]["s"]
    bounds = [(0.0, 7.0), (8.0, s0 - START_MIN + 3), (0.3, 0.95), (0.3, 0.95), (0.0, 0.95)]
    r = differential_evolution(cost, bounds, seed=1, popsize=20, maxiter=1000, tol=1e-7, polish=False, init="sobol",
                               callback=lambda xk, convergence=0.0: time.time() - t1 > minutes * 60)
    f, w, info, g, c, rmin = cost(r.x, True)
    print(f"[g2] {time.time() - t1:.0f} s, nfev {r.nfev}: dy {r.x[0]:.4f}, ctrl distances {np.round(g, 4).tolist()}; min R {rmin:.3f}, "
          f"straights {info['start_straight']:.3f} / {info['end_straight']:.3f}, length {w.length:.3f}; cost {f:.4f}", flush=True)
    print("   cloud clearance: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(c.items(), key=lambda kv: kv[1]) if v < 5), flush=True)
    import bell_place as BP
    import branch2_u as U
    from build123d import import_brep

    tube = U.const_d_tube(w, A1.D, BP.WALL, info["normal"])
    reg = ROOT / "output/viewer_registry"
    ex = {k: tube.distance_to(import_brep(str(reg / f"{k}.brep"))) for k in obs}
    print("[g2] exact: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(ex.items(), key=lambda kv: kv[1]) if v < 5), flush=True)
    print(f"   HINT_DY = {r.x[0]:.4f}, HINT_G2 = {tuple(round(float(v), 4) for v in g)}; end F {info['F'].round(3).tolist()}, valid {tube.is_valid}", flush=True)


if __name__ == "__main__":
    main()
