"""bell01 のメンズール(L-D 表、1 mm 間隔)を関数 D = a/(x+b)^p + c + q·x から作る。

`mensur/bell/make_bell.ipynb` の関数 a/(x+b)^p + c に、1次の項 q·x を足したもの(q=0 で元と同じ):
- D(0) = DF(リム径)、D'(0) = 2·tan(ANG)(リムの開き角)、D(X_END) = D_END(1番管の終わり)。
- a, c は D'(0) と D(0) から、b は D(X_END) = D_END から決まる。p, ANG, Q が形を決める。
- 表は L = 0〜X_END。ベルは芯線の長さ(840.635)で切り、その先は1番管。

履歴:
- 2018-03-30: p=0.83081841、ANG=-80°、Q=0、D(850)=16(D(120)=65 に合わせた)。
- 2026-11-22: flare を RefBell に似せて p=2.5、ANG=-68°、Q=0、D(850)=16。中間部が 3〜5 mm 細くなった。
- 2026-11-22: Q を足して RefBell に似せた。p=6、ANG=-67°、Q=-0.0227、D(850)=16。D=12 は L=1022.7。
- 2026-11-22: D=12 を L=1350 にした(1番管を長く)。D(850)=16 の条件は外し、L≤840 で RefBell に当てはめた:
  p=4.025、ANG=-67.41°、Q=-0.01165(差はリム以外 -1.5〜+2.2 mm、ベルの終点 D=18.37)。音程は後で calcimp で確かめる。

    uv run python cad/bell01/tools/make_mensur.py [out.csv]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

WD = Path(__file__).resolve().parent.parent
DF = 300.0  # リム径 (mm)
X_END, D_END = 1350.0, 12.0  # 1番管の終わりの L (mm) と径 (mm)
P = 4.025  # 形の指数
ANG = -67.41  # リムの開き角 (deg)
Q = -0.01165  # 1次の項の係数 (mm/mm)


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


def diameter(x, p: float = P, ang: float = ANG, q: float = Q):
    a, b, c = coefficients(p, ang, q)
    x = np.asarray(x, dtype=float)
    return a / (x + b) ** p + c + q * x


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else WD / "bell01-ld.csv"
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
