"""bell03 の探索: bell02 と同じ目標に、次の拘束を足して、基本形と局所的な摂動1つを合わせ込む。

- 摂動の振幅を小さく抑える(AMP_W·A²、bell02 の 10 倍)
- Bb 管の bb'(第8倍音)の f' との差が負にならない(BB8_MIN を下回った分に W_BB8 の罰則)
- フレア(リムから FLARE_L mm 以内)が bell01 より太くならない(bell01 の径の 1 + FLARE_TOL 倍を超えた分 (mm) に W_FLARE の罰則)
- F 管の c'(第6倍音)の f' との差を F6_REL(0)に近づける

目標(セント): F の第2倍音 − f' = -30、オクターブの幅 3→6・4→8・6→12 が Bb・F とも +10、
Bb の f' = +16、F の f' = Bb の f' + 10。変数: p, ANG, Q, A, L0, lam, dcyl, Fx(X_END は開始点ごとに固定)。

    uv run python impedance/bell03/search.py <name> <X_END> <start: bell02json | bell01>
"""

from __future__ import annotations

import importlib.util
import os
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "impedance/bell02"))
import refine_perturb as R  # noqa: E402
import scan_length as S  # noqa: E402

I = S.I  # noqa: E741
WIN = 4.3
AMP_W = 3.0
BB8_MIN, W_BB8 = 1.0, 4.0
FLARE_L, FLARE_TOL = 150.0, 0.02
W_FLARE = float(os.environ.get("BELL03_W_FLARE", "10.0"))  # 0 にするとフレアの拘束を外す(切り分け用)
F6_REL = 0.0


def _bell01_mensur():
    spec = importlib.util.spec_from_file_location("bell01_mensur", ROOT / "cad/bell01/tools/make_mensur.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L_FL = np.linspace(0, FLARE_L, 151)
D01_FL = _bell01_mensur().diameter(L_FL)  # bell01(決定版)のフレアの径


def evaluate(v, up, xe, tag, verbose=False):
    p, ang, q, a_, l0, lam, dcyl, fx = v
    if not (0.3 < p < 12 and -85 < ang < -40 and -0.1 < q < 0.05 and abs(a_) < 3 and 150 < lam < 1300
            and lam / 2 < l0 < xe - lam / 2 and -400 < dcyl < 150 and 600 < fx < 1300):
        return 1e6
    pert = [(a_, l0, lam / WIN, lam)]
    try:
        rows, d = R.rows_of(p, ang, q, xe, pert)
        if not np.all(np.isfinite(d)) or np.any(np.diff(d) <= 0):
            return 1e6
        u = S.adjust_up(up, dcyl)
        c = {}
        for key, extra in (("Bb", 0.0), ("F", fx)):
            r = list(u) + ([(12.0, 12.0, extra, "F extra")] if extra else []) + rows
            c[key] = {n: ct for n, _, _, ct in I.cents_vs_series(I.peaks(I.build_rows(f"tmp_{tag}_{key}", r, HERE)), key)}
    except Exception:
        return 1e6
    b, f = c["Bb"], c["F"]
    res = [(f[2] - f[8]) - S.F_REL2, b[6] - S.F_PRIME, f[8] - (b[6] + I.F_ABOVE_BB)]
    res += [(c[k][hi] - c[k][lo]) - S.OCT for k, prs in S.PAIRS.items() for lo, hi in prs]
    res += [(f[6] - f[8]) - F6_REL]
    d_fl = S.diameter(L_FL, p=p, ang=ang, q=q, xe=xe, perturb=pert)
    flare_over = float(np.max(np.maximum(0.0, d_fl - D01_FL * (1 + FLARE_TOL))))
    bb8 = b[8] - b[6]
    pen = AMP_W * a_**2 + W_BB8 * max(0.0, BB8_MIN - bb8) ** 2 + W_FLARE * flare_over**2
    err = sum(x * x for x in res) + pen
    if verbose:
        print(f"xe {xe:.0f} p {p:.4f} ang {ang:.3f} q {q:.6f} A {a_:+.3f} L0 {l0:.1f} lam {lam:.1f} dcyl {dcyl:+.1f} Fx {fx:.1f} "
              f"| Bb f' {b[6]:+.1f} F f' {f[8]:+.1f} | "
              + " ".join(f"{k}{lo}-{hi} {c[k][hi] - c[k][lo]:+.1f}" for k, prs in S.PAIRS.items() for lo, hi in prs)
              + f" | F2 {f[2] - f[8]:+.1f} bb' {bb8:+.1f} flare+ {flare_over:.2f}mm | err {err:.2f}\n"
              "   Bb vs f': " + " ".join(f"{n}:{b[n] - b[6]:+.1f}" for n in range(1, 13)) + "\n"
              "   F  vs f': " + " ".join(f"{n}:{f[n] - f[8]:+.1f}" for n in range(1, 13)), flush=True)
    return err


def main() -> None:
    name, xe, start = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    tag = name
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up = hr[:i_up]
    if start == "bell01":
        x0 = np.array([2.1061, -70.733, -0.005524, 0.5, xe / 2.5, 500.0, 1304.93 - xe, 939.6])
        steps = [0.3, 1.0, 0.002, 0.4, 100.0, -150.0, 8.0, 10.0]
    else:
        src = json.loads((ROOT / start).read_text())
        x0 = np.array(src["x"])
        x0[3] *= 0.4  # 振幅を小さくして始める
        x0[6] += src["xe"] - xe
        steps = [0.15, 0.6, 0.001, 0.3, 50.0, -80.0, 4.0, 5.0]
    t = time.time()
    print(f"start ({start}):")
    evaluate(x0, up, xe, tag, verbose=True)
    state = {"n": 0, "best": np.inf}

    def f(v):
        e = evaluate(v, up, xe, tag)
        state["n"] += 1
        if e < state["best"] - 0.5:
            state["best"] = e
            print(f"  eval {state['n']} ({time.time() - t:.0f}s): err {e:.2f}", flush=True)
        return e

    x = x0
    for rnd in range(2):  # 止まったところから刻みを小さくしてもう一度
        simplex = np.array([x] + [x + d for d in np.diag(np.array(steps) / (1 + 2 * rnd))])
        r = minimize(f, x, method="Nelder-Mead",
                     options={"maxiter": 700, "xatol": 1e-3, "fatol": 1e-2, "initial_simplex": simplex})
        x = r.x
        print(f"round {rnd + 1} ({time.time() - t:.0f}s, {state['n']} evals):", flush=True)
        err = evaluate(x, up, xe, tag, verbose=True)
    (HERE / f"result_{name}.json").write_text(json.dumps({"xe": xe, "x": list(map(float, x)), "err": err}, indent=1))
    for g in HERE.glob(f"tmp_{tag}_*"):
        g.unlink()


if __name__ == "__main__":
    main()
