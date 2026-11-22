"""bell03 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c + q·x と局所的な摂動から作る。

bell01(cad/bell01/tools/make_mensur.py)と同じ関数。値は impedance/bell03 の探索の候補 c(result_c.json)。
⌀12 の円筒の増減 -119.6 mm は上流(バルブ部の円筒)を縮めるもので、1番管には含めない(D12_EXTRA = 0)。

    uv run python cad/bell03/tools/make_mensur.py [out.csv]
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
P = 1.5869990410476502  # 形の指数
ANG = -70.661057592086  # リムの開き角 (deg)
Q = -0.002777158374287746  # 1次の項の係数 (mm/mm)
# 局所的な摂動(基本形に足す): (A, L0, w, lam) ごとに A·exp(-((L-L0)/w)^2)·cos(2π(L-L0)/lam)。L はリムからの距離 (mm)
# 局所的な摂動(impedance/bell03/search.py の候補 c)。リムから 115〜1188 mm、径は最大 +9.1%
PERTURB: list[tuple[float, float, float, float]] = [(1.8180638970243952, 651.650909740222, 1073.2558882203675 / 4.3, 1073.2558882203675)]
# ⌀12 になった先に足す ⌀12 の円筒 (mm)。bell03 では上流を縮めるので 0
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
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell03-ld.csv"
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
