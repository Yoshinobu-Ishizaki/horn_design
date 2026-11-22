"""bell01 のメンズール(p, ANG, Q)と ⌀12 になる L(X_END、= 全長)を、Bb 管の音程の目標に合わせて探す。

目標(Bb 管、a' = A4 Hz の平均律からのセント): TARGET の倍音。リムの ⌀300 と ⌀12(1番管の終わり)は固定。
目標の数(3)より変数(4)が多いので、今のメンズールからの形のずれ(直径の差の二乗平均、mm)を
SHAPE_W の重みで足して抑える。D(L) が単調に減らないものは除く。

    uv run python impedance/bell01/tune_mensur.py
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

TARGET = {2: -20.0, 3: -10.0, 6: 16.0}  # 倍音: セント(Bb 管)
SHAPE_W = 0.02  # 形のずれ (mm rms) の重み。セント² に足す
L_CMP = np.linspace(0, 840, 400)  # 形のずれを測る範囲(ベル)
D_NOW = diameter(L_CMP)


def evaluate(v, up, verbose=False):
    p, ang, q, xe = v
    if not (0.3 < p < 12 and -85 < ang < -40 and -0.1 < q < 0.05 and 1100 < xe < 1500):
        return 1e6, None
    try:
        ls = np.linspace(0, xe, 1500)
        d = diameter(ls, p=p, ang=ang, q=q, xe=xe)
        if not np.all(np.isfinite(d)) or np.any(np.diff(d) >= 0):
            return 1e6, None
        rows = I.bell01_rows(p=p, ang=ang, q=q, xe=xe)
        men = I.build("tune_Bb", up, rows, 0.0)
        c = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(men), "Bb")}
    except Exception:
        return 1e6, None
    shape = float(np.sqrt(np.mean((diameter(L_CMP, p=p, ang=ang, q=q, xe=xe) - D_NOW) ** 2)))
    err = sum((c[n] - t) ** 2 for n, t in TARGET.items()) + SHAPE_W * shape**2
    if verbose:
        print(f"p {p:.4f} ang {ang:.3f} q {q:.6f} xe {xe:.2f} | " +
              " ".join(f"n{n} {c[n]:+.1f}" for n in sorted(c) if n <= 8) + f" | shape {shape:.2f} mm | err {err:.2f}")
    return err, c


def main() -> None:
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    x0 = np.array([P, ANG, Q, X_END])
    print("start:")
    evaluate(x0, up, verbose=True)
    count = [0, np.inf]

    def f(v):
        e = evaluate(v, up)[0]
        count[0] += 1
        if e < count[1]:
            count[1] = e
            print(f"  eval {count[0]} ({time.time() - t:.0f}s): err {e:.2f}", flush=True)
            evaluate(v, up, verbose=True)
        return e

    simplex = np.array([x0, x0 + [0.8, 0, 0, 0], x0 + [0, 2.0, 0, 0], x0 + [0, 0, 0.004, 0], x0 + [0, 0, 0, -30]])
    best = minimize(f, x0, method="Nelder-Mead",
                    options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
    print(f"best ({time.time() - t:.0f}s):")
    evaluate(best.x, up, verbose=True)
    for f in HERE.glob("tune_Bb*"):
        f.unlink()


if __name__ == "__main__":
    main()
