"""bell02 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c + q·x と局所的な摂動から作る。

bell01(cad/bell01/tools/make_mensur.py)と同じ関数。値は impedance/bell02 の試算の結果(refine_x1450r.json):
F 管の第2倍音が f' に対して -30、オクターブの幅 3→6・4→8・6→12 が Bb・F とも +10(±1.1 セント)。
⌀12 の円筒の増減 -80.8 mm は上流(バルブ部の円筒)を縮めるもので、1番管には含めない(D12_EXTRA = 0)。

    uv run python cad/bell02/tools/make_mensur.py [out.csv]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

WD = Path(__file__).resolve().parent.parent
DF = 300.0  # リム径 (mm)
X_END, D_END = 1450.0, 12.0  # 1番管の終わりの L (mm) と径 (mm)
P = 2.632951012960445  # 形の指数
ANG = -65.31284870554165  # リムの開き角 (deg)
Q = -0.00817000347157465  # 1次の項の係数 (mm/mm)
# 局所的な摂動(基本形に足す): (A, L0, w, lam) ごとに A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)。L はリムからの距離 (mm)
# 局所的な摂動(impedance/bell02/refine_perturb.py)。リムから 286〜776 mm、径は最大 +11.7%
PERTURB: list[tuple[float, float, float, float]] = [(2.963027340398071, 531.0802344735008, 489.93682564573953 / 4.3, 489.93682564573953)]
# ⌀12 になった先に足す ⌀12 の円筒 (mm)。bell02 では上流を縮めるので 0
D12_EXTRA = 0.0


def coefficients(p: float = P, ang: float = ANG, q: float = Q, df: float = DF, xe: float = X_END, de: float = D_END):
    k = 2 * math.tan(math.radians(ang))

    def ac(b):
        a = -(k - q) * b ** (p + 1) / p  # D'(0) = -p·a·b^(-p-1) + q = k
        return a, df - a / b**p  # D(0) = a/b^p + c = df

    def f(x, b):
        a, c = ac(b)
        return a / (x + b) ** p + c + q * x

    b = brentq(lambda b: f(xe, b) - de, 1e-3, 1e7)
    a, c = ac(b)
    return a, b, c


def perturbation(x, items=None):
    """局所的な摂動 Σ A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)(mm)。"""
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    for a_, l0, w, lam in (PERTURB if items is None else items):
        t = (x - l0) / w
        out += a_ * np.exp(-t * t) * np.cos(2 * math.pi * (x - l0) / lam)
    return out


def diameter(x, p: float = P, ang: float = ANG, q: float = Q, xe: float = X_END, perturb=None):
    """D(L)。perturb は局所的な摂動の並び(None なら PERTURB)。D(xe) = D_END は基本形で決まり、
    摂動は xe の近くで 0 になるように置く。"""
    a, b, c = coefficients(p, ang, q, xe=xe)
    x = np.asarray(x, dtype=float)
    return a / (x + b) ** p + c + q * x + perturbation(x, perturb)


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell02-ld.csv"
    a, b, c = coefficients()
    x = np.append(np.arange(0, X_END, 1.0), X_END)
    d = diameter(x)
    if np.any(np.diff(d) >= 0):
        raise ValueError("D が単調に減っていない")
    np.savetxt(out, np.column_stack([x, d]), delimiter=",", header="x,y", comments="", fmt="%.10g")
    print(f"p={P} ang={ANG} q={Q} a={a:.6g} b={b:.6f} c={c:.6f}")
    for xi in [0, 10, 20, 50, 120, 200, 300, 500, 840.635, 850, 1000, 1200, X_END]:
        print(f"  D({xi}) = {float(diameter(xi)):.3f}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv)
