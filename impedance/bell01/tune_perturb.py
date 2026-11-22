"""基本形に局所的な摂動 A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam) を1つ足し、Bb 管の bb(第4倍音)を f' に合わせる。

摂動はガウス窓で約1波長に区切る(w = lam / WIN。L0 ± lam/2 で窓は exp(-(WIN/2)^2) ≈ 0.01)。その外は基本形のまま。
基本形(p, ANG, Q, X_END)は変えない。Bb 管の f' は、⌀12 の円筒(上流の最後の円筒 = 1番管の末端の直線にあたる)の
長さの増減 dcyl で保つ。
変数: A, L0, lam, dcyl。F 管の円筒は固定(F_EXTRA)。
目標(セント、a' = A4 Hz):
- Bb 管: bb − f' = REL4、bb' − bb = OCT48、f' = F_PRIME、f − f' は KEEP3(基本形の値)
- F 管: 3→6・4→8 のオクターブの幅を基本形の値に保つ(重み W_F)
拘束: D は単調に減る。振幅には AMP_W·A² の罰則(表面のうねりを抑える)。

    uv run python impedance/bell01/tune_perturb.py
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
from make_mensur import X_END, diameter, perturbation  # noqa: E402

F_PRIME, REL4, OCT48, KEEP3 = 16.0, 0.0, 10.0, -9.6
F_OCT = {(3, 6): 10.0, (4, 8): 10.6}
W_F = 0.5
AMP_W = 0.5
F_EXTRA = 939.6
WIN = 4.3  # w = lam / WIN
LAM_FIX = None  # 摂動の周期 lam を固定するとき (mm)。None なら変数にする


def adjust_up(up, dcyl):
    """上流の最後の行(⌀12 の円筒)の長さを dcyl だけ変える。"""
    df, db, r, c = up[-1]
    assert abs(df - 12.0) < 1e-6 and abs(db - 12.0) < 1e-6 and r + dcyl > 1.0
    return up[:-1] + [(df, db, r + dcyl, c)]


def evaluate(v, up, verbose=False):
    if LAM_FIX is not None:
        a_, l0, dcyl = v
        lam = LAM_FIX
    else:
        a_, l0, lam, dcyl = v
    xe = X_END
    if not (abs(a_) < 5 and 60 < lam < 900 and lam / 2 < l0 < xe - lam / 2 and -100 < dcyl < 100):
        return 1e6
    w = lam / WIN
    pert = [(a_, l0, w, lam)]
    up = adjust_up(up, dcyl)
    try:
        ls = np.linspace(0, xe, 3000)
        d = diameter(ls, xe=xe, perturb=pert)
        if np.any(np.diff(d) >= 0) or abs(perturbation(xe, pert)) > 0.01 or abs(perturbation(0.0, pert)) > 0.01:
            return 1e6
        rows = I.bell01_rows(d12_extra=0.0, xe=xe, perturb=pert)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", F_EXTRA)):
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(I.build(f"tunep_{key}", up, rows, extra)), key)}
    except Exception:
        return 1e6
    b, f = c["Bb"], c["F"]
    res = [(b[4] - b[6]) - REL4, (b[8] - b[4]) - OCT48, b[6] - F_PRIME, (b[3] - b[6]) - KEEP3]
    res += [W_F * ((f[hi] - f[lo]) - t) for (lo, hi), t in F_OCT.items()]
    err = sum(r * r for r in res) + AMP_W * a_**2
    if verbose:
        rel = lambda k, r: " ".join(f"{n}:{c[k][n] - c[k][r]:+.1f}" for n in range(2, 11))  # noqa: E731
        print(f"A {a_:+.3f} L0 {l0:.1f} lam {lam:.1f} (w {w:.1f}, range {l0 - lam / 2:.0f}..{l0 + lam / 2:.0f}) "
              f"dcyl {dcyl:+.2f} | Bb f' {b[6]:+.1f} F f' {f[8]:+.1f} "
              f"| Bb 3-6 {b[6] - b[3]:+.1f} 4-8 {b[8] - b[4]:+.1f} F 3-6 {f[6] - f[3]:+.1f} 4-8 {f[8] - f[4]:+.1f} "
              f"| err {err:.2f}\n   Bb vs f': {rel('Bb', 6)}\n   F  vs f': {rel('F', 8)}", flush=True)
    return err


def main() -> None:
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    t = time.time()
    if LAM_FIX is not None:
        x0 = np.array([0.5, 640.0, 0.0])
        steps = [0.4, 80.0, -10.0]
    else:
        x0 = np.array([1.0, 640.0, 400.0, 0.0])
        steps = [0.5, 60.0, 150.0, -10.0]
    print("base (no perturbation):")
    evaluate(np.where(np.arange(len(x0)) == 0, 0.0, x0), up, verbose=True)
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

    simplex = np.array([x0] + [x0 + d for d in np.diag(steps)])
    best = minimize(f, x0, method="Nelder-Mead",
                    options={"maxiter": 600, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
    print(f"best ({time.time() - t:.0f}s, {state['n']} evals):")
    evaluate(best.x, up, verbose=True)
    for g in HERE.glob("tunep_*"):
        g.unlink()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        LAM_FIX = float(sys.argv[1])
    main()
