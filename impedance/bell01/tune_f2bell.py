"""F 管の第2倍音を持ち上げる: bell01 に2つ目の局所的な摂動を足す。

F 管の第2倍音(約 86 Hz)は Bb 管にとって 1.5 倍音にあたる低い音なので、これを狙った長い周期の摂動は、
Bb 側のほとんどの共鳴では影響が打ち消し合う(と期待する)。
摂動: A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)、w = lam / WIN、L はリムからの距離。bell01 の中に収める。
変数: A, L0, lam(2つ目の摂動)、dcyl(⌀12 の円筒の増減。Bb 管の f' を保つ)、Fx(F 管の延長管の長さ)。
目標(a' = A4 Hz、f' に対するセント):
- F 管: 第2倍音 = F_REL2、第3・4・6倍音は F_KEEP、f' = Bb 管の f' + F_ABOVE_BB
- Bb 管: f' = BB_FPRIME、第2・3・4・8倍音は BB_KEEP
振幅に AMP_W·A² の罰則。D は単調に減る。

    uv run python impedance/bell01/tune_f2bell.py
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
from make_mensur import D12_EXTRA, PERTURB, X_END, diameter, perturbation  # noqa: E402
from tune_perturb import adjust_up  # noqa: E402

F_REL2 = -30.0
F_KEEP = {3: -17.6, 4: -11.9, 6: -9.0}
BB_FPRIME = 16.1
BB_KEEP = {2: -15.4, 3: -11.3, 4: 1.9, 8: 13.0}
AMP_W = 0.3
WIN = 4.3
FX0 = 939.6


def evaluate(v, up, verbose=False):
    a_, l0, lam, dcyl, fx = v
    if not (abs(a_) < 3 and 300 < lam < 1300 and lam / 2 < l0 < X_END - lam / 2 and -60 < dcyl < 60 and 800 < fx < 1100):
        return 1e6
    pert = list(PERTURB) + [(a_, l0, lam / WIN, lam)]
    try:
        d = diameter(np.linspace(0, X_END, 3000), perturb=pert)
        if np.any(np.diff(d) >= 0) or abs(perturbation(X_END, pert)) > 0.01 or abs(perturbation(0.0, pert)) > 0.01:
            return 1e6
        rows = I.bell01_rows(d12_extra=0.0, perturb=pert)
        u = adjust_up(up, D12_EXTRA + dcyl)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", fx)):
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(I.build(f"tunef2b_{key}", u, rows, extra)), key)}
    except Exception:
        return 1e6
    b, f = c["Bb"], c["F"]
    res = [(f[2] - f[8]) - F_REL2, f[8] - (b[6] + I.F_ABOVE_BB), b[6] - BB_FPRIME]
    res += [(f[n] - f[8]) - t for n, t in F_KEEP.items()]
    res += [(b[n] - b[6]) - t for n, t in BB_KEEP.items()]
    err = sum(x * x for x in res) + AMP_W * a_**2
    if verbose:
        print(f"A {a_:+.3f} L0 {l0:.1f} lam {lam:.1f} (range {l0 - lam / 2:.0f}..{l0 + lam / 2:.0f}) dcyl {dcyl:+.2f} "
              f"Fx {fx:.1f} | Bb f' {b[6]:+.1f} F f' {f[8]:+.1f} | err {err:.2f}\n"
              "   Bb vs f': " + " ".join(f"{n}:{b[n] - b[6]:+.1f}" for n in range(1, 11)) + "\n"
              "   F  vs f': " + " ".join(f"{n}:{f[n] - f[8]:+.1f}" for n in range(1, 11)), flush=True)
    return err


def main() -> None:
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    print("now:")
    evaluate(np.array([0.0, 650.0, 1200.0, 0.0, FX0]), up, verbose=True)
    best = None
    for l0, lam in ((650.0, 1200.0), (400.0, 700.0)):
        x0 = np.array([0.8, l0, lam, 0.0, FX0])
        simplex = np.array([x0] + [x0 + d for d in np.diag([0.6, 60.0, -150.0, 3.0, 15.0])])
        state = {"n": 0}

        def f(v):
            state["n"] += 1
            return evaluate(v, up)

        r = minimize(f, x0, method="Nelder-Mead",
                     options={"maxiter": 260, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
        print(f"start L0 {l0} lam {lam}: {state['n']} evals, err {r.fun:.2f} ({time.time() - t:.0f}s)", flush=True)
        evaluate(r.x, up, verbose=True)
        if best is None or r.fun < best.fun:
            best = r
    print("best:")
    evaluate(best.x, up, verbose=True)
    for g in HERE.glob("tunef2b_*"):
        g.unlink()


if __name__ == "__main__":
    main()
