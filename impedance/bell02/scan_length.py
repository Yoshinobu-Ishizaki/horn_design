"""bell02 の試算(第1段): テーパーの長さ X_END を決めて、基本形の関数を合わせ込む。

bell01 と同じ構成(上流は kanutils の refhornBb000.men の x=0〜1413、右手 220 mm、a' = 442 Hz)で、
ベルのメンズールを D = a/(x+b)^p + c + q·x(リム ⌀300、X_END で ⌀12)とする。摂動はなし。
変数: p, ANG, Q、dcyl(⌀12 の円筒の増減。Bb 管の f' を保つ)、Fx(F 管の延長管の長さ)。
目標(セント):
- F 管の第2倍音 − f'(第8倍音)= F_REL2
- オクターブの幅(上 − 下)3→6、4→8、6→12 が Bb 管・F 管とも OCT
- Bb 管の f'(第6倍音)= F_PRIME、F 管の f' = Bb 管の f' + F_ABOVE_BB

    uv run python impedance/bell02/scan_length.py 1300
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "impedance/bell01"))
sys.path.insert(0, str(ROOT / "cad/bell01/tools"))
import intonation as I  # noqa: E402
from make_mensur import diameter  # noqa: E402

F_REL2 = -30.0
OCT = 10.0
PAIRS = {"Bb": [(3, 6), (4, 8), (6, 12)], "F": [(3, 6), (4, 8), (6, 12)]}
F_PRIME = 16.0
X0 = {"p": 2.1061, "ang": -70.733, "q": -0.005524}  # bell01 の基本形から始める
FX0 = 939.6


def rows_of(p, ang, q, xe, step=1.0):
    ls = np.append(np.arange(xe, 0, -step), 0.0)
    d = diameter(ls, p=p, ang=ang, q=q, xe=xe, perturb=[])
    return [(float(d[i]), float(d[i + 1]), float(ls[i] - ls[i + 1]), "bell02") for i in range(len(ls) - 1)], d


def adjust_up(up, dcyl):
    """上流の末尾の ⌀12 の円筒を dcyl だけ伸縮する(縮めるときは末尾から複数の行にわたって削る)。"""
    up = list(up)
    if dcyl >= 0:
        df, db, r, c = up[-1]
        return up[:-1] + [(df, db, r + dcyl, c)]
    cut = -dcyl
    while cut > 0:
        df, db, r, c = up[-1]
        if abs(df - 12.0) > 1e-6 or abs(db - 12.0) > 1e-6:
            raise ValueError("⌀12 の円筒が足りない")
        if r > cut + 1.0:
            up[-1] = (df, db, r - cut, c)
            cut = 0
        else:
            up.pop()
            cut -= r
    return up


def evaluate(v, up, xe, tag, verbose=False):
    p, ang, q, dcyl, fx = v
    if not (0.3 < p < 12 and -85 < ang < -40 and -0.1 < q < 0.05 and -400 < dcyl < 150 and 600 < fx < 1300):
        return 1e6, None
    try:
        rows, d = rows_of(p, ang, q, xe)  # d はマウスピース側から(⌀12 → ⌀300)
        if not np.all(np.isfinite(d)) or np.any(np.diff(d) <= 0):
            return 1e6, None
        u = adjust_up(up, dcyl)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", fx)):
            r = list(u) + ([(12.0, 12.0, extra, "F extra")] if extra else []) + rows
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(I.build_rows(f"tmp_{tag}_{key}", r, HERE)), key)}
    except Exception:
        return 1e6, None
    b, f = c["Bb"], c["F"]
    res = [(f[2] - f[8]) - F_REL2, b[6] - F_PRIME, f[8] - (b[6] + I.F_ABOVE_BB)]
    res += [(c[k][hi] - c[k][lo]) - OCT for k, prs in PAIRS.items() for lo, hi in prs]
    err = sum(x * x for x in res)
    if verbose:
        print(f"xe {xe:.0f} p {p:.4f} ang {ang:.3f} q {q:.6f} dcyl {dcyl:+.1f} Fx {fx:.1f} | Bb f' {b[6]:+.1f} F f' {f[8]:+.1f} | "
              + " ".join(f"{k}{lo}-{hi} {c[k][hi] - c[k][lo]:+.1f}" for k, prs in PAIRS.items() for lo, hi in prs)
              + f" | err {err:.2f}\n   Bb vs f': " + " ".join(f"{n}:{b[n] - b[6]:+.1f}" for n in range(1, 13))
              + "\n   F  vs f': " + " ".join(f"{n}:{f[n] - f[8]:+.1f}" for n in range(1, 13)), flush=True)
    return err, c


def main() -> None:
    xe = float(sys.argv[1])
    tag = f"x{xe:.0f}"
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    # Bb の f' をおおよそ保つ dcyl の初期値: 長さの差の分だけ円筒を縮める
    x0 = np.array([X0["p"], X0["ang"], X0["q"], 1304.93 - xe, FX0])
    print("start:")
    evaluate(x0, up, xe, tag, verbose=True)
    state = {"n": 0, "best": np.inf}

    def f(v):
        e = evaluate(v, up, xe, tag)[0]
        state["n"] += 1
        if e < state["best"] - 0.5:
            state["best"] = e
            print(f"  eval {state['n']} ({time.time() - t:.0f}s): err {e:.2f}", flush=True)
        return e

    simplex = np.array([x0] + [x0 + d for d in np.diag([0.6, 2.0, 0.003, -15.0, 25.0])])
    best = minimize(f, x0, method="Nelder-Mead",
                    options={"maxiter": 500, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
    print(f"best ({time.time() - t:.0f}s, {state['n']} evals):")
    err, _ = evaluate(best.x, up, xe, tag, verbose=True)
    out = HERE / f"scan_{tag}.json"
    out.write_text(json.dumps({"xe": xe, "x": list(map(float, best.x)), "err": err}, indent=1))
    for g in HERE.glob(f"tmp_{tag}_*"):
        g.unlink()


if __name__ == "__main__":
    main()
