"""bell01 の基本形(メンズール関数)を、Bb 管・F 管の 3→6・4→8 倍音のオクターブの幅で合わせ込む。

変数: p, ANG, Q, X_END(⌀12 になる L = 全長)と、F 管で足す ⌀12 の円筒の長さ。
目標(a' = A4 Hz、セント):
- Bb 管の f'(第6倍音)= F_PRIME
- オクターブの幅(上の倍音のずれ − 下の倍音のずれ)が OCT(Bb・F の 3→6、4→8)
- F 管の f'(第8倍音)= Bb 管の f' + F_ABOVE_BB
第2倍音などの最低音域は、後で局所的な摂動で動かす(ここでは目標にしない)。
今のメンズールからの形のずれ(直径の差の二乗平均、mm)を SHAPE_W の重みで足して抑える。

    uv run python impedance/bell01/tune_octaves.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "cad/bell01/tools"))
import intonation as I  # noqa: E402
from make_mensur import ANG, P, Q, X_END, diameter  # noqa: E402

F_PRIME = 16.0
OCT = {("Bb", 3, 6): 10.0, ("Bb", 4, 8): 10.0, ("F", 3, 6): 10.0, ("F", 4, 8): 10.0}
SHAPE_W = 0.02
F_EXTRA0 = 939.3  # F 管の円筒の初期値 (mm)
L_CMP = np.linspace(0, 840, 400)
D_NOW = diameter(L_CMP)


def evaluate(v, up, verbose=False):
    p, ang, q, xe, fx = v
    if not (0.3 < p < 12 and -85 < ang < -40 and -0.1 < q < 0.05 and 1100 < xe < 1500 and 600 < fx < 1300):
        return 1e6
    try:
        d = diameter(np.linspace(0, xe, 1500), p=p, ang=ang, q=q, xe=xe)
        if not np.all(np.isfinite(d)) or np.any(np.diff(d) >= 0):
            return 1e6
        rows = I.bell01_rows(p=p, ang=ang, q=q, xe=xe)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", fx)):
            men = I.build(f"tuneo_{key}", up, rows, extra)
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(men), key)}
    except Exception:
        return 1e6
    shape = float(np.sqrt(np.mean((diameter(L_CMP, p=p, ang=ang, q=q, xe=xe) - D_NOW) ** 2)))
    res = [c["Bb"][6] - F_PRIME, c["F"][8] - (c["Bb"][6] + I.F_ABOVE_BB)]
    res += [(c[k][hi] - c[k][lo]) - t for (k, lo, hi), t in OCT.items()]
    err = sum(r * r for r in res) + SHAPE_W * shape**2
    if verbose:
        rel = lambda k, r: " ".join(f"{n}:{c[k][n] - c[k][r]:+.1f}" for n in range(2, 11))  # noqa: E731
        print(f"p {p:.4f} ang {ang:.3f} q {q:.6f} xe {xe:.2f} Fx {fx:.1f} | Bb f' {c['Bb'][6]:+.1f} F f' {c['F'][8]:+.1f} | "
              + " ".join(f"{k}{lo}-{hi} {c[k][hi] - c[k][lo]:+.1f}" for (k, lo, hi) in OCT)
              + f" | shape {shape:.2f} | err {err:.2f}\n   Bb vs f': {rel('Bb', 6)}\n   F  vs f': {rel('F', 8)}",
              flush=True)
    return err


def main() -> None:
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    x0 = np.array([P, ANG, Q, X_END, F_EXTRA0])
    print("start:")
    evaluate(x0, up, verbose=True)
    state = {"n": 0, "best": np.inf}

    def f(v):
        e = evaluate(v, up)
        state["n"] += 1
        if e < state["best"] - 0.05:
            state["best"] = e
            print(f"  eval {state['n']} ({time.time() - t:.0f}s): err {e:.2f}", flush=True)
        return e

    simplex = np.array([x0] + [x0 + d for d in np.diag([0.6, 1.5, 0.003, -25, 30])])
    best = minimize(f, x0, method="Nelder-Mead",
                    options={"maxiter": 700, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
    print(f"best ({time.time() - t:.0f}s, {state['n']} evals):")
    evaluate(best.x, up, verbose=True)
    for g in HERE.glob("tuneo_*"):
        g.unlink()


if __name__ == "__main__":
    main()
