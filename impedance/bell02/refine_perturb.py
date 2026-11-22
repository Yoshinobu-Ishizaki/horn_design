"""bell02 の試算(第2段): 第1段(scan_length.py)の結果から、基本形と局所的な摂動1つを同時に合わせ込む。

摂動: A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)、w = lam / WIN(約1波長に区切る)。L はリムからの距離。
変数: p, ANG, Q, A, L0, lam, dcyl, Fx。目標は scan_length.py と同じ。振幅に AMP_W·A² の罰則。

    uv run python impedance/bell02/refine_perturb.py 1400
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan_length as S  # noqa: E402

I = S.I  # noqa: E741
WIN = 4.3
AMP_W = 0.3


def rows_of(p, ang, q, xe, pert, step=1.0):
    ls = np.append(np.arange(xe, 0, -step), 0.0)
    d = S.diameter(ls, p=p, ang=ang, q=q, xe=xe, perturb=pert)
    return [(float(d[i]), float(d[i + 1]), float(ls[i] - ls[i + 1]), "bell02") for i in range(len(ls) - 1)], d


def evaluate(v, up, xe, tag, verbose=False):
    p, ang, q, a_, l0, lam, dcyl, fx = v
    if not (0.3 < p < 12 and -85 < ang < -40 and -0.1 < q < 0.05 and abs(a_) < 3 and 150 < lam < 1300
            and lam / 2 < l0 < xe - lam / 2 and -400 < dcyl < 150 and 600 < fx < 1300):
        return 1e6
    pert = [(a_, l0, lam / WIN, lam)]
    try:
        rows, d = rows_of(p, ang, q, xe, pert)
        if not np.all(np.isfinite(d)) or np.any(np.diff(d) <= 0):
            return 1e6
        u = S.adjust_up(up, dcyl)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", fx)):
            r = list(u) + ([(12.0, 12.0, extra, "F extra")] if extra else []) + rows
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(I.build_rows(f"tmpp_{tag}_{key}", r, HERE)), key)}
    except Exception:
        return 1e6
    b, f = c["Bb"], c["F"]
    res = [(f[2] - f[8]) - S.F_REL2, b[6] - S.F_PRIME, f[8] - (b[6] + I.F_ABOVE_BB)]
    res += [(c[k][hi] - c[k][lo]) - S.OCT for k, prs in S.PAIRS.items() for lo, hi in prs]
    err = sum(x * x for x in res) + AMP_W * a_**2
    if verbose:
        print(f"xe {xe:.0f} p {p:.4f} ang {ang:.3f} q {q:.6f} A {a_:+.3f} L0 {l0:.1f} lam {lam:.1f} dcyl {dcyl:+.1f} Fx {fx:.1f} "
              f"| Bb f' {b[6]:+.1f} F f' {f[8]:+.1f} | "
              + " ".join(f"{k}{lo}-{hi} {c[k][hi] - c[k][lo]:+.1f}" for k, prs in S.PAIRS.items() for lo, hi in prs)
              + f" | F2 {f[2] - f[8]:+.1f} | err {err:.2f}\n   Bb vs f': " + " ".join(f"{n}:{b[n] - b[6]:+.1f}" for n in range(1, 13))
              + "\n   F  vs f': " + " ".join(f"{n}:{f[n] - f[8]:+.1f}" for n in range(1, 13)), flush=True)
    return err


def main() -> None:
    xe = float(sys.argv[1])
    tag = f"x{xe:.0f}"
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    if len(sys.argv) > 2:  # 別の結果(refine_*.json)から始める。長さが違えば dcyl を差の分だけ変える
        src = json.loads(Path(sys.argv[2]).read_text())
        x0 = np.array(src["x"])
        x0[6] += src["xe"] - xe
        tag += "r"
        steps = [0.1, 0.4, 0.0008, 0.2, 30.0, -60.0, 3.0, 4.0]
        print(f"start (from {sys.argv[2]}):")
    else:
        p, ang, q, dcyl, fx = json.loads((HERE / f"scan_{tag}.json").read_text())["x"]
        x0 = np.array([p, ang, q, 0.0, xe / 2, 700.0, dcyl, fx])
        steps = [0.3, 1.0, 0.002, 0.6, 120.0, -200.0, 8.0, 10.0]
        print("start (stage 1 result, no perturbation):")
    evaluate(x0, up, xe, tag, verbose=True)
    state = {"n": 0, "best": np.inf}

    def f(v):
        e = evaluate(v, up, xe, tag)
        state["n"] += 1
        if e < state["best"] - 0.5:
            state["best"] = e
            print(f"  eval {state['n']} ({time.time() - t:.0f}s): err {e:.2f}", flush=True)
        return e

    simplex = np.array([x0] + [x0 + d for d in np.diag(steps)])
    best = minimize(f, x0, method="Nelder-Mead",
                    options={"maxiter": 900, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
    print(f"best ({time.time() - t:.0f}s, {state['n']} evals):")
    err = evaluate(best.x, up, xe, tag, verbose=True)
    (HERE / f"refine_{tag}.json").write_text(json.dumps({"xe": xe, "x": list(map(float, best.x)), "err": err}, indent=1))
    for g in HERE.glob(f"tmpp_{tag}_*"):
        g.unlink()


if __name__ == "__main__":
    main()
